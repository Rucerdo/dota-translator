"""Retrato del héroe que habla, recortado de la barra superior de Dota 2.

GSI solo dice el player_id (0-9) de quien escribe, no su héroe. Pero la barra superior del HUD
muestra los 10 retratos en orden de player_id: Radiant 0-4 a la izquierda del reloj y Dire 5-9
a la derecha. Recortamos ese retrato de la ventana de Dota en el momento del mensaje.

Las medidas están tomadas a 1080 px de alto y se escalan con la altura de la ventana
(el HUD de Dota escala con la altura y se centra en horizontal).
"""
import ctypes
import ctypes.wintypes as wt
import io
import logging
import threading

from PIL import Image, ImageGrab, ImageStat

log = logging.getLogger(__name__)
user32 = ctypes.windll.user32

# Medidas a 1080 px de alto, relativas al centro horizontal de la ventana
DEFAULT_TOPBAR = {
    "radiant_first_center": -386,  # centro del retrato del player 0
    "dire_first_center": 137,      # centro del retrato del player 5
    "pitch": 62,                   # distancia entre retratos
    "half_width": 28,
    "top": 5,
    "bottom": 39,
}


def _dota_hwnd(require_foreground: bool) -> int | None:
    if require_foreground:
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return hwnd if buf.value.strip().lower().startswith("dota 2") else None
    return user32.FindWindowW(None, "Dota 2") or None


def _client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wt.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top


def tile_box(player_id: int, client: tuple[int, int, int, int], cfg: dict) -> tuple[int, int, int, int]:
    x0, y0, w, h = client
    s = h / 1080.0
    if player_id < 5:
        cx = cfg["radiant_first_center"] + cfg["pitch"] * player_id
    else:
        cx = cfg["dire_first_center"] + cfg["pitch"] * (player_id - 5)
    cx = x0 + w / 2 + cx * s
    hw = cfg["half_width"] * s
    return int(cx - hw), int(y0 + cfg["top"] * s), int(cx + hw), int(y0 + cfg["bottom"] * s)


def _looks_valid(img: Image.Image) -> bool:
    """Descarta capturas negras o planas (menú, pantalla de carga, ventana tapada)."""
    stat = ImageStat.Stat(img.convert("L"))
    return stat.mean[0] > 18 and stat.stddev[0] > 14


def capture(player_id: int, cfg: dict | None = None, require_foreground: bool = True,
            validate: bool = True) -> Image.Image | None:
    if not (isinstance(player_id, int) and 0 <= player_id < 10):
        return None
    hwnd = _dota_hwnd(require_foreground)
    if not hwnd:
        return None
    client = _client_rect(hwnd)
    if not client or client[3] < 400:
        return None
    try:
        img = ImageGrab.grab(tile_box(player_id, client, {**DEFAULT_TOPBAR, **(cfg or {})}), all_screens=True)
    except OSError:
        log.exception("no se pudo capturar la pantalla")
        return None
    return img if (not validate or _looks_valid(img)) else None


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


class PortraitCache:
    """Último retrato válido de cada jugador en la partida actual."""

    def __init__(self):
        self._cache: dict[tuple[str, int], bytes] = {}
        self._lock = threading.Lock()

    def get(self, match_id: str, player_id: int | None, cfg: dict | None = None) -> bytes | None:
        if player_id is None:
            return None
        key = (match_id or "", player_id)
        img = capture(player_id, cfg)  # con Dota en primer plano: captura fresca (gris si está muerto)
        if img is not None:
            png = to_png(img)
            with self._lock:
                if len(self._cache) > 200:
                    self._cache.clear()
                self._cache[key] = png
            return png
        with self._lock:  # Dota en segundo plano o captura inválida: el último conocido
            return self._cache.get(key)


STRIP_HEIGHT = 80  # alto de la franja superior capturada para calibrar (a 1080 px)

# Rangos de los deslizadores del calibrador (unidades a 1080 px de alto)
CALIBRATION_RANGES = {
    "radiant_first_center": (-700, -150),
    "dire_first_center": (50, 600),
    "pitch": (35, 110),
    "half_width": (12, 55),
    "top": (0, 40),
    "bottom": (15, 79),
}


def capture_strip() -> tuple[Image.Image, tuple[int, int, int, int]] | None:
    """Captura la franja superior de la ventana de Dota (para el calibrador).
    Devuelve (imagen, (0, 0, ancho, alto de la ventana)): tile_box() con ese 'client'
    da coordenadas directamente dentro de la imagen."""
    hwnd = _dota_hwnd(require_foreground=False)
    if not hwnd:
        return None
    client = _client_rect(hwnd)
    if not client or client[3] < 400:
        return None
    x0, y0, w, h = client
    try:
        img = ImageGrab.grab((x0, y0, x0 + w, y0 + int(STRIP_HEIGHT * h / 1080)), all_screens=True)
    except OSError:
        log.exception("no se pudo capturar la pantalla")
        return None
    return img, (0, 0, w, h)
