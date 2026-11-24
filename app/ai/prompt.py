"""Instrucciones comunes a todos los traductores con IA, y lectura de su respuesta."""
import json
import re

SYSTEM_PROMPT = """You translate Dota 2 in-game chat (text chat and voice transcriptions) between players.
Rules:
- Translate into {target_name} so it reads like a real {target_name}-speaking Dota player wrote it: short, casual, natural chat. Never word-for-word.
- Players use Dota 2 slang, abbreviations and hero/item nicknames in any language (e.g. мид, керри, сф, бкб, 肉山, ss, rax, bb). Understand them in context.
- Keep Dota 2 terms the way that player community actually says them. Hero, item and ability names stay in English (Shadow Fiend, Black King Bar/BKB, Blink Dagger, Roshan, Aegis). Common jargon follows community usage of the target language (in Spanish e.g. farmear, pushear, gankear, wardear, stackear, feedear, el carry, el support, mid, top, bot, high ground, buyback, smoke).
- Keep the tone and intensity, including insults and swearing; do not soften, censor or comment.
- Keep numbers, timings and abbreviations players understand (gg, wp, ez, ss, bkb, tp, rosh). Expand only what would be unclear.
- If the message is already in {target_name}, return it unchanged.
- Output only JSON: {{"source_language": "<ISO 639-1 code of the original>", "translation": "<text>"}}."""

LANG_NAMES = {"es": "Spanish",
              "es-ES": "Spanish from Spain (Castilian: use 'vosotros', Spain's vocabulary and gamer slang such as "
                       "'tío', 'chaval', 'flipar', 'currarse'; never Latin American forms like 'ustedes' for friends, "
                       "'agarrar', 'chévere', 'pana')",
              "es-419": "Latin American Spanish (use 'ustedes', neutral Latin American vocabulary and gamer slang; "
                        "never Spain-only forms like 'vosotros' or 'tío')",
              "en": "English", "ru": "Russian", "zh-CN": "Simplified Chinese",
              "zh-TW": "Traditional Chinese", "pt": "Portuguese (Brazilian)", "uk": "Ukrainian", "de": "German",
              "fr": "French", "it": "Italian", "pl": "Polish", "tr": "Turkish", "ko": "Korean", "ja": "Japanese",
              "th": "Thai", "vi": "Vietnamese", "id": "Indonesian", "tl": "Filipino", "ms": "Malay", "ar": "Arabic",
              "fa": "Persian", "he": "Hebrew", "el": "Greek", "ro": "Romanian", "cs": "Czech", "hu": "Hungarian",
              "sv": "Swedish", "fi": "Finnish", "bg": "Bulgarian", "sr": "Serbian", "kk": "Kazakh", "hi": "Hindi"}

# Esquema de la respuesta (para los servicios que admiten salida JSON con esquema)
SCHEMA = {"type": "object",
          "properties": {"source_language": {"type": "string"}, "translation": {"type": "string"}},
          "required": ["source_language", "translation"], "additionalProperties": False}


class AIError(Exception):
    """El servicio de IA no pudo traducir; translator.py vuelve a Google Translate."""


def system_prompt(target: str) -> str:
    return SYSTEM_PROMPT.format(target_name=LANG_NAMES.get(target, target))


def user_prompt(text: str, context: list[str] | None = None) -> str:
    parts = []
    if context:
        parts.append("Previous chat messages, for context only (do NOT translate them):\n"
                     + "\n".join(f"- {c}" for c in context[-4:]))
    parts.append(f"Message to translate:\n{text}")
    return "\n\n".join(parts)


def parse_reply(raw: str) -> tuple[str, str]:
    """Saca (traducción, idioma_origen) de la respuesta. Tolera texto alrededor del JSON."""
    raw = (raw or "").strip()
    candidates = [raw]
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            data = json.loads(c)
            translation = str(data["translation"]).strip()
            if translation:
                return translation, str(data.get("source_language") or "auto").strip().lower()
        except (ValueError, KeyError, TypeError):
            continue
    if raw and not raw.startswith("{"):  # el modelo ignoró el formato pero devolvió la traducción
        return raw, "auto"
    raise AIError("respuesta de la IA no utilizable")
