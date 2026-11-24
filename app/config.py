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


def system_locale() -> str:
    """'es_ES', 'es_MX', 'en_US'... según el idioma de Windows."""
    try:
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(lcid, "en_US")
    except Exception:
        return "en_US"


def system_lang() -> str:
    return system_locale().split("_")[0].lower()


def spanish_variant() -> str:
    """Español de España si Windows está en es_ES; si no, latinoamericano."""
    return "es-ES" if system_locale() in ("es_ES", "ca_ES", "gl_ES", "eu_ES") else "es-419"


_sys = system_lang()

DEFAULTS = {
    "ui_lang": "es" if _sys == "es" else "en",
    "incoming_target_lang": spanish_variant() if _sys == "es" else (
        _sys if _sys in ("en", "pt", "ru", "de", "fr", "it", "pl", "tr", "uk") else "en"),
    "outgoing_lang": "auto",
    "outgoing_fallback_lang": "ru",
    # "google" (gratis, sin cuenta) o un proveedor de IA con clave propia: gemini, claude, openai, groq,
    # deepseek, mistral, xai, openrouter, custom (ver app/ai). Google queda siempre de respaldo.
    "translator_engine": "google",
    "ai_keys_enc": {},    # {proveedor: clave cifrada con DPAPI (solo la descifra tu usuario de Windows)}
    "ai_models": {},      # {proveedor: modelo}; vacío = elegir automáticamente
    "ai_host_id": "",     # id estable de esta instalación (lo pide "Sign in with ChatGPT")
    "ai_base_urls": {},   # {proveedor: URL} (solo servidor propio/local)
    "skip_if_source_is_target": True,
    "show_original": True,
    "save_history": True,
    # Escribir desde el juego: atajos nativos de Windows (RegisterHotKey), sin gancho de teclado
    "compose_enabled": True,
    "compose_hotkey_team": "ctrl+enter",
    "compose_hotkey_all": "ctrl+shift+enter",
    "compose_autosend": True,        # False: abre el chat de Dota y pega, pero no pulsa Enter
    "overlay_enabled": True,
    "show_hero_icons": True,
    "topbar": {},  # ajustes finos de la posición de los retratos (ver app/portraits.py)
    "overlay": {
        "x_frac": 0.01,
        "y_frac": 0.52,
        "width_frac": 0.38,
        "max_lines": 8,
        "line_seconds": 12,
        "font_family": "Segoe UI",
        "font_size": 13,
    },
    "ignore_messages": ["gg", "gg wp", "wp", "?", "??", "???", "ty", "np", "lol", "xd", "+", "-"],
    "voice_enabled": False,       # transcripción del chat de voz (experimental, descarga aparte)
    "voice_model": "turbo",       # "turbo" (GPU NVIDIA) | "small" (CPU)
    "voice_process": "dota2.exe",
    "voice_skip_langs": [],       # idiomas (ISO 639-1: "es", "en"...) que NO se traducen en el chat de voz
    "voice_show_skipped": False,  # mostrar igualmente su transcripción, sin traducir
    "check_updates": True,
    "skip_version": "",
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
    # v1.2.0: el "español" genérico pasa a una variante concreta (España / Latinoamérica)
    for key in ("incoming_target_lang", "outgoing_lang", "outgoing_fallback_lang"):
        if saved.get(key) == "es":
            saved[key] = spanish_variant()
    # v1.2.0: clave/modelo de Gemini → formato multi-proveedor
    if saved.get("gemini_key_enc"):
        saved.setdefault("ai_keys_enc", {}).setdefault("gemini", saved["gemini_key_enc"])
    if saved.get("gemini_model"):
        saved.setdefault("ai_models", {}).setdefault("gemini", saved["gemini_model"])
    saved.pop("gemini_key_enc", None)
    saved.pop("gemini_model", None)
    return _merge(DEFAULTS, saved)


def save(cfg: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
