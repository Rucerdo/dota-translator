"""Traducción gratuita con el endpoint público de Google Translate (sin API key),
con corrección de idioma por alfabeto y glosario de jerga de Dota."""
import json
import logging
import re
import threading
import time

import requests

from .config import USER_GLOSSARY_PATH, resource_path

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"
_cache: dict[tuple[str, str, str], tuple[str, str]] = {}
_lock = threading.Lock()
_parallel = threading.Semaphore(3)  # ráfagas grandes provocan "429 Too Many Requests"
_cooldown: dict[str, float] = {}  # proveedor → hora hasta la que no se usa
COOLDOWN_S = 120


# ---- Proveedores gratuitos (sin API key). Cada uno devuelve (traducción, idioma_detectado) o lanza excepción.
def _google_gtx(text, target, source):
    r = _session.get("https://translate.googleapis.com/translate_a/single", timeout=6,
                     params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text})
    r.raise_for_status()
    data = r.json()
    out = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])
    detected = data[2] if len(data) > 2 and isinstance(data[2], str) else source
    return out, detected


def _google_dict(text, target, source):
    r = _session.get("https://clients5.google.com/translate_a/t", timeout=6,
                     params={"client": "dict-chrome-ex", "sl": source, "tl": target, "q": text})
    r.raise_for_status()
    data = r.json()
    first = data[0] if isinstance(data, list) and data else data
    if isinstance(first, list):  # [["traducción", "ru"]]
        return first[0], (first[1] if len(first) > 1 and isinstance(first[1], str) else source)
    if isinstance(first, str):  # ["traducción"] cuando se indica el idioma de origen
        return first, source
    raise ValueError(f"respuesta inesperada: {str(data)[:100]}")


def _mymemory(text, target, source):
    src = source if source != "auto" else "Autodetect"
    r = _session.get("https://api.mymemory.translated.net/get", timeout=8,
                     params={"q": text, "langpair": f"{src}|{target}"})
    r.raise_for_status()
    data = r.json()
    if data.get("responseStatus") not in (200, "200") or data.get("quotaFinished"):
        raise ValueError(data.get("responseDetails") or "MyMemory error")
    detected = source
    if source == "auto":
        detected = str((data.get("responseData") or {}).get("detectedLanguage") or "auto").split("-")[0]
    return data["responseData"]["translatedText"], detected


PROVIDERS = [("google", _google_gtx), ("google-dict", _google_dict), ("mymemory", _mymemory)]


def translate(text: str, target: str, source: str = "auto") -> tuple[str, str]:
    """Devuelve (texto_traducido, idioma_detectado). Prueba los proveedores en orden;
    si uno falla (p.ej. 429), lo aparta unos minutos y usa el siguiente."""
    key = (text, target, source)
    with _lock:
        if key in _cache:
            return _cache[key]
    last_err: Exception | None = None
    now = time.time()
    candidates = [p for p in PROVIDERS if _cooldown.get(p[0], 0) < now] or PROVIDERS
    with _parallel:
        for name, fn in candidates:
            try:
                out, detected = fn(text, target, source)
                if not out:
                    raise ValueError("traducción vacía")
                break
            except Exception as e:
                last_err = e
                _cooldown[name] = time.time() + COOLDOWN_S
                log.warning("proveedor %s falló (%s); probando el siguiente", name, e)
        else:
            raise RuntimeError(f"ningún traductor disponible: {last_err}")
    result = (out, detected or source)
    with _lock:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[key] = result
    return result


_SCRIPT_HINTS = [  # (rango unicode, idioma a forzar)
    ((0x0400, 0x04FF), "ru"),
    ((0x4E00, 0x9FFF), "zh-CN"),
    ((0xAC00, 0xD7AF), "ko"),
    ((0x0E00, 0x0E7F), "th"),
    ((0x0600, 0x06FF), "ar"),
    ((0x0370, 0x03FF), "el"),
]


_NO_SPACES = {"zh", "ja", "th"}  # idiomas sin espacios entre palabras: sin límites de palabra


def _compile(key: str, lang: str) -> re.Pattern:
    """'вард*' = cualquier palabra que empiece por 'вард'; si no, palabra/frase completa."""
    stem = key.endswith("*")
    body = re.escape(key[:-1] if stem else key) + (r"\w*" if stem else "")
    if lang in _NO_SPACES:
        return re.compile(body, re.I)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.I)


def _load_glossary() -> tuple[dict, dict]:
    """Tablas del glosario:
      "<lang>"         términos que se PROTEGEN (no se traducen, se dejan como término de Dota)
      "<lang>_expand"  abreviaturas que se EXPANDEN antes de traducir (xq → porque, щас → сейчас)
    <lang> es "ru", "zh", "latin" (cualquier idioma con alfabeto latino)…"""
    tables: dict[str, dict] = {}
    for path in (resource_path("app/glossary.json"), USER_GLOSSARY_PATH):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for name, table in data.items():
            if not name.startswith("_") and isinstance(table, dict):
                tables.setdefault(name, {}).update(table)
    protect, expand = {}, {}
    for name, table in tables.items():
        lang = name.removesuffix("_expand")
        # más largo primero (y a igual longitud, exacto antes que raíz) para que "мидас" gane a "мид*"
        items = sorted(table.items(), key=lambda kv: (-len(kv[0].rstrip("*")), kv[0].endswith("*")))
        compiled = [(_compile(k, lang), v) for k, v in items]
        (expand if name.endswith("_expand") else protect)[lang] = compiled
    return protect, expand


_GLOSSARY, _EXPAND = _load_glossary()


def _apply_glossary(text: str, lang: str) -> tuple[str, list[str]]:
    """Expande abreviaturas y sustituye la jerga por marcadores {n} que Google no traduce."""
    key = lang.split("-")[0]
    for rx, repl in _EXPAND.get(key, []):
        text = rx.sub(repl, text)
    terms: list[str] = []

    def sub(repl):
        def f(_m):
            terms.append(repl)
            return f" {{{len(terms) - 1}}} "
        return f

    for rx, repl in _GLOSSARY.get(key, []):
        text = rx.sub(sub(repl), text)
    return re.sub(r"\s+", " ", text).strip(), terms


def _restore(text: str, terms: list[str]) -> str:
    for i, t in enumerate(terms):
        text = re.sub(rf"\{{\s*{i}\s*\}}", t, text)
    return re.sub(r"\s+([,.!?])", r"\1", text)


_BROKEN = re.compile(r"\{\s*\d+\s*\}")


def translate_chat(text: str, target: str) -> tuple[str, str]:
    """Traducción pensada para chat de Dota: corrige la autodetección en mensajes
    cortos (p.ej. 'иди мид нуб' → ruso, no tayiko) y protege términos del juego."""
    lang = next((hint for (lo, hi), hint in _SCRIPT_HINTS if any(lo <= ord(c) <= hi for c in text)), None)
    if lang:
        prepared, terms = _apply_glossary(text, lang)
        out = _restore(translate(prepared, target, source=lang)[0], terms)
        if _BROKEN.search(out):
            out = translate(text, target, source=lang)[0]
        return out, lang
    prepared, terms = _apply_glossary(text, "latin")
    if not terms and prepared != text:  # solo hubo expansiones
        return translate(prepared, target)
    if terms:
        out, detected = translate(prepared, target)
        out = _restore(out, terms)
        if not _BROKEN.search(out):
            return out, detected
    return translate(text, target)
