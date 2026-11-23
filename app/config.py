"""Rutas, configuración por defecto y persistencia en %APPDATA%."""
import copy
import ctypes
import json
import locale
import os
import sys
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "DotaChatTranslator"
CONFIG_PATH = APP_DIR / "config.json"
HISTORY_PATH = APP_DIR / "history.db"
LOG_PATH = APP_DIR / "app.log"
USER_GLOSSARY_PATH = APP_DIR / "glossary.json"


def resource_path(rel: str) -> Path:
    """Ruta a un recurso empaquetado (funciona con PyInstaller y en desarrollo)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def system_lang() -> str:
    try:
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        name = locale.windows_locale.get(lcid, "en_US")
    except Exception:
        name = "en_US"
    return name.split("_")[0].lower()


_sys = system_lang()

DEFAULTS = {
    "ui_lang": "es" if _sys == "es" else "en",
    "incoming_target_lang": _sys if _sys in ("es", "en", "pt", "ru", "de", "fr", "it", "pl", "tr", "uk") else "en",
    "outgoing_lang": "auto",
    "outgoing_fallback_lang": "ru",
    "skip_if_source_is_target": True,
    "show_original": True,
    "save_history": True,
    "enable_outgoing": True,
    "overlay_enabled": True,
    "overlay": {
        "x_frac": 0.01,
        "y_frac": 0.52,
        "width_frac": 0.38,
        "max_lines": 8,
        "line_seconds": 12,
        "font_family": "Segoe UI",
        "font_size": 13,
    },
    "hotkeys": {
        "toggle_overlay": "alt+d",
        "translate_and_send": "ctrl+enter",
    },
    "ignore_messages": ["gg", "gg wp", "wp", "?", "??", "???", "ty", "np", "lol", "xd", "+", "-"],
    "gsi_port": 53123,
    "dota_dir": "",
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return _merge(DEFAULTS, saved)


def save(cfg: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
