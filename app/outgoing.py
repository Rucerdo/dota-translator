"""Ctrl+Enter en el chat de Dota: traduce lo escrito y lo envía en el idioma del equipo.

Solo se captura la tecla mientras Dota está en primer plano, así no interfiere con otras apps.
Mecanismo: Ctrl+A, Ctrl+C → traducir → Ctrl+A, Ctrl+V → Enter. No se toca la memoria del juego.
"""
import ctypes
import logging
import threading
import time

import keyboard
import pyperclip

log = logging.getLogger(__name__)
user32 = ctypes.windll.user32


def dota_is_foreground() -> bool:
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value.strip().lower().startswith("dota 2")


class OutgoingTranslator:
    def __init__(self, translate_fn, lang_fn, notify_fn):
        self.translate_fn, self.lang_fn, self.notify = translate_fn, lang_fn, notify_fn
        self.hotkey = "ctrl+enter"
        self.enabled = True
        self._handle = None
        self._busy = False
        self._lock = threading.Lock()

    def configure(self, hotkey: str, enabled: bool):
        with self._lock:
            if hotkey != self.hotkey or not enabled:
                self._unhook()
            self.hotkey, self.enabled = hotkey, enabled

    def start(self):
        threading.Thread(target=self._watch_focus, daemon=True).start()

    def _unhook(self):
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except (KeyError, ValueError):
                pass
            self._handle = None

    def _watch_focus(self):
        while True:
            try:
                # Fuera del candado: GetWindowText espera al hilo dueño de la ventana (puede ser nuestra GUI)
                fg = dota_is_foreground()
                with self._lock:
                    active = self.enabled and fg
                    if active and self._handle is None:
                        self._handle = keyboard.add_hotkey(self.hotkey, self._on_hotkey, suppress=True)
                    elif not active and self._handle is not None:
                        self._unhook()
            except Exception:
                log.exception("error gestionando el atajo de envío")
            time.sleep(0.4)

    def _on_hotkey(self):
        if not self._busy:
            self._busy = True
            threading.Thread(target=self._do, daemon=True).start()

    def _do(self):
        old_clip = None
        try:
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass
            t0 = time.time()
            while keyboard.is_pressed("ctrl") and time.time() - t0 < 1.5:  # esperar a que suelte Ctrl
                time.sleep(0.02)
            pyperclip.copy("")
            keyboard.send("ctrl+a")
            time.sleep(0.04)
            keyboard.send("ctrl+c")
            time.sleep(0.12)
            text = pyperclip.paste().strip()
            if not text:
                keyboard.send("enter")
                return
            lang = self.lang_fn()
            translated, detected = self.translate_fn(text, lang)
            pyperclip.copy(translated)
            keyboard.send("ctrl+a")
            time.sleep(0.04)
            keyboard.send("ctrl+v")
            time.sleep(0.08)
            keyboard.send("enter")
            self.notify(text, translated, detected, lang)
        except Exception:
            log.exception("error enviando mensaje traducido; se envía el original")
            keyboard.send("enter")
        finally:
            time.sleep(0.2)
            if old_clip is not None:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass
            self._busy = False
