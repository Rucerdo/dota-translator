"""Gemini (Google AI Studio). Clave gratuita: https://aistudio.google.com/apikey

El modelo no va fijo: se pregunta a la API qué modelos permite la clave y se elige el Flash-Lite estable
más reciente (el más rápido y con el límite gratuito más holgado).
"""
import json
import logging
import re
import threading

import requests

from .base import Provider
from .prompt import SCHEMA, AIError, parse_reply, system_prompt, user_prompt

log = logging.getLogger(__name__)
API = "https://generativelanguage.googleapis.com/v1beta"

_SCHEMA = {"type": "OBJECT", "properties": {"source_language": {"type": "STRING"}, "translation": {"type": "STRING"}},
           "required": list(SCHEMA["required"])}
_SAFETY = [{"category": c, "threshold": "BLOCK_NONE"} for c in (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT")]
_VERSION_RX = re.compile(r"gemini-(\d+(?:\.\d+)?)")
_BAD = ("image", "tts", "audio", "live", "embedding", "vision", "thinking", "native", "computer", "robotics", "learnlm")


def _score(name: str) -> tuple:
    """Prefiere Flash-Lite estable más reciente; luego Flash estable; las 'preview' al final."""
    n = name.lower()
    m = _VERSION_RX.search(n)
    version = float(m.group(1)) if m else 0.0
    kind = 2 if "flash-lite" in n else (1 if "flash" in n else 0)
    stable = 0 if ("preview" in n or "exp" in n) else 1
    return (stable, kind, version)


class Gemini(Provider):
    id = "gemini"
    label = "Gemini (Google)"
    key_page = "https://aistudio.google.com/apikey"
    model_hint = "gemini-…-flash-lite"

    def __init__(self):
        super().__init__()
        self._chosen: dict[str, str] = {}
        self._session = requests.Session()
        self._lock = threading.Lock()

    def _headers(self):
        return {"x-goog-api-key": self.key, "Content-Type": "application/json"}

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        with self._lock:
            if self.key in self._chosen:
                return self._chosen[self.key]
        try:
            r = self._session.get(f"{API}/models", headers=self._headers(), params={"pageSize": 200}, timeout=(3, 10))
        except requests.RequestException as e:
            self.pause(30)
            raise AIError("sin conexión con Gemini") from e
        if r.status_code in (400, 401, 403):
            self.pause(600)  # no reintentar en cada mensaje con una clave mala
            raise AIError("clave de Gemini no válida")
        if r.status_code >= 400:
            raise AIError(f"Gemini no devolvió la lista de modelos ({r.status_code})")
        names = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        names = [n for n in names if n.startswith("gemini") and not any(b in n for b in _BAD)]
        if not names:
            raise AIError("la clave no tiene acceso a ningún modelo Gemini de texto")
        best = max(names, key=_score)
        log.info("Gemini: modelo elegido %s (de %d disponibles)", best, len(names))
        with self._lock:
            self._chosen[self.key] = best
        return best

    def translate(self, text, target, context=None):
        model = self.resolved_model()
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt(target)}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(text, context)}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400,
                                 "responseMimeType": "application/json", "responseSchema": _SCHEMA},
            "safetySettings": _SAFETY,
        }
        try:
            r = self._session.post(f"{API}/models/{model}:generateContent", headers=self._headers(),
                                   data=json.dumps(body), timeout=(3, 12))
        except requests.RequestException as e:
            self.pause(30)
            raise AIError("sin conexión con Gemini") from e
        if r.status_code == 429:
            self.pause(90)
            raise AIError("Gemini: límite de uso alcanzado")
        if r.status_code in (400, 401, 403):
            if not self.model and r.status_code == 400:  # el modelo elegido pudo desaparecer
                with self._lock:
                    self._chosen.pop(self.key, None)
            raise AIError(f"Gemini rechazó la petición ({r.status_code}): {r.text[:200]}")
        if r.status_code >= 400:
            raise AIError(f"error de Gemini ({r.status_code})")
        data = r.json()
        try:
            raw = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as e:
            reason = (data.get("promptFeedback") or {}).get("blockReason") or \
                (data.get("candidates") or [{}])[0].get("finishReason")
            raise AIError(f"respuesta de Gemini no utilizable ({reason or e})") from e
        return parse_reply(raw)
