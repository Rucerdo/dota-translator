"""Atajos globales con RegisterHotKey (API nativa de Windows) y envío de teclas con SendInput.

NO hay gancho de teclado: Windows solo avisa a la app cuando se pulsa la combinación registrada;
el resto de teclas (Alt, Shift, habilidades...) ni pasan por la app y llegan al juego intactas.
(La librería 'keyboard' que se usaba antes interceptaba TODAS las teclas y dejaba Alt enganchada.)
"""
import ctypes
import ctypes.wintypes as wt
import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY, WM_QUIT, WM_APP = 0x0312, 0x0012, 0x8000
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
VK_SHIFT, VK_CONTROL, VK_MENU, VK_RETURN, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x0D, 0x5B, 0x5C
KEYEVENTF_KEYUP = 0x2

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
_NAMED = {"enter": 0x0D, "return": 0x0D, "space": 0x20, "tab": 0x09, "insert": 0x2D, "home": 0x24, "end": 0x23,
          "pageup": 0x21, "pagedown": 0x22, "pause": 0x13, **{f"f{i}": 0x6F + i for i in range(1, 25)}}


def parse(hotkey: str) -> tuple[int, int]:
    """'ctrl+shift+enter' → (MOD_CONTROL|MOD_SHIFT, VK_RETURN). ValueError si no se entiende."""
    parts = [p for p in hotkey.lower().replace(" ", "").split("+") if p]
    if not parts:
        raise ValueError("atajo vacío")
    *mods, key = parts
    flags = 0
    for m in mods:
        if m not in _MODS:
            raise ValueError(f"modificador desconocido: {m}")
        flags |= _MODS[m]
    if key in _NAMED:
        vk = _NAMED[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        raise ValueError(f"tecla desconocida: {key}")
    return flags, vk


class GlobalHotkeys:
    """Registra atajos con RegisterHotKey en un hilo propio con su bucle de mensajes."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._wanted: dict[int, tuple[int, int]] = {}
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._lock = threading.Lock()
        self.failed: list[str] = []  # atajos que Windows no dejó registrar (ya en uso por otro programa)
        self._names: dict[int, str] = {}

    def set(self, hotkeys: dict[str, tuple[str, Callable[[], None]]]):
        """{nombre: ('ctrl+enter', callback)}. Sustituye los atajos registrados."""
        wanted, callbacks, names = {}, {}, {}
        for i, (name, (combo, cb)) in enumerate(hotkeys.items(), start=1):
            try:
                wanted[i] = parse(combo)
                callbacks[i], names[i] = cb, f"{name} ({combo})"
            except ValueError as e:
                log.warning("atajo no válido %s: %s", combo, e)
        with self._lock:
            self._wanted, self._callbacks, self._names = wanted, callbacks, names
        if self._thread is None:
            ready = threading.Event()
            self._thread = threading.Thread(target=self._loop, args=(ready,), name="hotkeys", daemon=True)
            self._thread.start()
            ready.wait(3)
        else:
            user32.PostThreadMessageW(self._tid, WM_APP, 0, 0)  # re-registrar en su hilo

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread = None

    def _register_all(self, registered: set):
        for hid in list(registered):
            user32.UnregisterHotKey(None, hid)
        registered.clear()
        self.failed = []
        with self._lock:
            wanted, names = dict(self._wanted), dict(self._names)
        for hid, (mods, vk) in wanted.items():
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                registered.add(hid)
            else:
                self.failed.append(names[hid])
                log.warning("Windows no dejó registrar el atajo %s (¿lo usa otro programa?)", names[hid])

    def _loop(self, ready: threading.Event):
        self._tid = kernel32.GetCurrentThreadId()
        registered: set = set()
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # crea la cola de mensajes del hilo
        self._register_all(registered)
        ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                with self._lock:
                    cb = self._callbacks.get(msg.wParam)
                if cb:
                    try:
                        cb()
                    except Exception:
                        log.exception("error en un atajo")
            elif msg.message == WM_APP:
                self._register_all(registered)
        for hid in registered:
            user32.UnregisterHotKey(None, hid)


# ---------------- envío de teclas (solo cuando tú mandas un mensaje) ----------------
def _down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def wait_modifiers_released(timeout: float = 2.0):
    """Espera a que sueltes Ctrl/Shift/Alt/Win, para que las teclas simuladas no se combinen con ellas."""
    t0 = time.time()
    while time.time() - t0 < timeout and any(_down(v) for v in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN)):
        time.sleep(0.02)


def tap(*vks: int):
    """Pulsa y suelta una combinación (tap(VK_CONTROL, ord('V')))."""
    for vk in vks:
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), 0, 0)
        time.sleep(0.01)
    for vk in reversed(vks):
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)


def focus_window(hwnd: int):
    """Trae una ventana al frente (con el truco de AttachThreadInput por si Windows lo bloquea)."""
    if not hwnd:
        return
    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    my_tid = kernel32.GetCurrentThreadId()
    attached = fg_tid and fg_tid != my_tid and user32.AttachThreadInput(my_tid, fg_tid, True)
    try:
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(my_tid, fg_tid, False)


def dota_hwnd() -> int:
    return user32.FindWindowW(None, "Dota 2") or 0


def send_to_dota_chat(all_chat: bool, hwnd: int, press_enter: bool = True):
    """Abre el chat de Dota (Enter = equipo, Shift+Enter = todos), pega (Ctrl+V) y envía (Enter)."""
    wait_modifiers_released()
    focus_window(hwnd)
    time.sleep(0.15)
    if all_chat:
        tap(VK_SHIFT, VK_RETURN)
    else:
        tap(VK_RETURN)
    time.sleep(0.18)  # que el cuadro de chat de Dota esté abierto
    tap(VK_CONTROL, ord("V"))
    if press_enter:
        time.sleep(0.12)
        tap(VK_RETURN)


hotkeys = GlobalHotkeys()
