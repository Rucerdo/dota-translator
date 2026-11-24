"""Traducción gratuita con el endpoint público de Google Translate (sin API key),
con corrección de idioma por alfabeto y glosario de jerga de Dota."""
import collections
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


def _service_code(lang: str) -> str:
    """Google y MyMemory solo tienen un español: las variantes (es-ES, es-419) solo las distingue Gemini."""
    return "es" if lang.startswith("es-") else lang


def translate(text: str, target: str, source: str = "auto") -> tuple[str, str]:
    target, source = _service_code(target), _service_code(source)
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
    # El nombre completo en inglés también es una entrada ('blink dagger' → 'Blink Dagger'), para que se
    # reconozca entero antes que sus partes ('blink', 'dagger') y no salga duplicado.
    latin = tables.setdefault("latin", {})
    for table_name, table in list(tables.items()):
        if table_name.endswith("_expand"):
            continue
        for value in list(table.values()):  # solo nombres propios ('Blink Dagger'), no frases ('are feeding')
            if " " in value and value[0].isupper() and value.lower() not in latin:
                latin[value.lower()] = value
    protect, expand = {}, {}
    for name, table in tables.items():
        lang = name.removesuffix("_expand")
        # más largo primero (y a igual longitud, exacto antes que raíz) para que "мидас" gane a "мид*"
        items = sorted(table.items(), key=lambda kv: (-len(kv[0].rstrip("*")), kv[0].endswith("*")))
        compiled = [(_compile(k, lang), v) for k, v in items]
        (expand if name.endswith("_expand") else protect)[lang] = compiled
    return protect, expand


_GLOSSARY, _EXPAND = _load_glossary()


def _inline_ok(term: str) -> bool:
    """Siglas ('BKB', 'TP', 'HP'): Google las respeta dentro de la frase, así que van tal cual (sin marcador
    opaco) y Google puede construir la frase con naturalidad. Los nombres de varias palabras NO son fiables
    ('Void Spirit' acababa como 'Espíritu del Vacío'), así que esos siguen protegidos con marcador."""
    return term.isupper() and len(term) <= 5


def _apply_glossary(text: str, lang: str) -> tuple[str, list[str]]:
    """Expande abreviaturas; los nombres y siglas se ponen en la frase tal cual y el resto de la jerga
    se sustituye por marcadores {n} que Google no traduce."""
    key = lang.split("-")[0]
    for rx, repl in _EXPAND.get(key, []):
        text = rx.sub(repl, text)
    terms: list[str] = []
    inline: list[str] = []

    def sub(repl):
        def f(_m):
            if _inline_ok(repl):  # marcador interno (no lo toca ninguna otra regla); se pone el nombre al final
                inline.append(repl)
                return f" {len(inline) - 1} "
            terms.append(repl)
            return f" {{{len(terms) - 1}}} "
        return f

    for rx, repl in _GLOSSARY.get(key, []):
        text = rx.sub(sub(repl), text)
    text = re.sub("(\\d+)", lambda m: inline[int(m.group(1))], text)
    return re.sub(r"\s+", " ", text).strip(), terms


def _restore(text: str, terms: list[str]) -> str:
    for i, t in enumerate(terms):
        text = re.sub(rf"\{{\s*{i}\s*\}}", t, text)
    return re.sub(r"\s+([,.!?])", r"\1", text)


_BROKEN = re.compile(r"\{\s*\d+\s*\}")


_ENGINE = {"name": "google"}
_CONTEXT: collections.deque = collections.deque(maxlen=6)  # últimos mensajes (contexto para la IA)
_AI_CACHE: dict[tuple[str, str, str], tuple[str, str]] = {}


def configure(engine: str = "google", key: str = "", model: str = "", base_url: str = ""):
    """engine: 'google' (gratis, sin cuenta) o un proveedor de IA de app/ai (gemini, claude, openai, groq...)
    con la clave del usuario. Google queda siempre como respaldo."""
    from .ai import PROVIDERS
    _ENGINE["name"] = engine if engine in PROVIDERS else "google"
    for pid, provider in PROVIDERS.items():
        if pid == _ENGINE["name"]:
            provider.configure(key, model, base_url)
        else:
            provider.configure("", "", "")


_INVISIBLE = re.compile("[​‌‍⁠﻿]")


def translate_chat(text: str, target: str) -> tuple[str, str]:
    """Traduce un mensaje del chat de Dota. Con un proveedor de IA activo, la IA (natural, entiende la jerga
    de Dota y el contexto); si no hay o falla, Google Translate con el glosario.
    Sin caracteres invisibles (Google los mete a veces)."""
    out, lang = _translate_chat(text, target)
    return re.sub(r" {2,}", " ", _INVISIBLE.sub("", out)).strip(), lang


def _translate_chat(text: str, target: str) -> tuple[str, str]:
    engine = _ENGINE["name"]
    if engine != "google":
        from .ai import PROVIDERS, AIError
        provider = PROVIDERS[engine]
        key = (engine, text, target)
        if key in _AI_CACHE:
            return _AI_CACHE[key]
        if provider.available:
            try:
                # Sin glosario: la IA ya conoce la jerga de Dota y las pistas pueden despistarla.
                # El glosario queda solo para Google (sin clave, fallo o sin cuota).
                t0 = time.time()
                out = provider.translate(text, target, list(_CONTEXT))
                log.info("%s tradujo en %.2fs", provider.label, time.time() - t0)
                _CONTEXT.append(text)
                if len(_AI_CACHE) > 2000:
                    _AI_CACHE.clear()
                _AI_CACHE[key] = out
                return out
            except AIError as e:
                log.warning("%s; se usa Google Translate", e)
            except Exception:
                log.exception("error inesperado con %s; se usa Google Translate", provider.label)
    _CONTEXT.append(text)
    return _translate_chat_google(text, target)


def _translate_chat_google(text: str, target: str) -> tuple[str, str]:
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
