"""Servicios con API compatible con OpenAI (/v1/chat/completions): ChatGPT, Groq, DeepSeek, Mistral,
Grok (xAI), OpenRouter y servidores locales (Ollama, LM Studio...). Un solo cliente HTTP para todos.

El modelo se elige solo entre los que permite la clave (o se escribe a mano en Ajustes).
Se pide esfuerzo de razonamiento bajo y salida JSON; si un servicio/modelo no admite alguno de esos
parámetros, se quita y se recuerda.
"""
import json
import logging
import re
import threading

import requests

from .base import Provider
from .prompt import AIError, parse_reply, system_prompt, user_prompt

log = logging.getLogger(__name__)

PRESETS = {
    "openai": dict(label="ChatGPT (OpenAI)", base="https://api.openai.com/v1",
                   key_page="https://platform.openai.com/api-keys", hint="gpt-…-mini",
                   prefer=[r"^gpt-\d+(\.\d+)?-mini$", r"^gpt-\d+(\.\d+)?-nano$", r"^gpt-\d+(\.\d+)?$"],
                   reasoning=r"^(gpt-[5-9]|o\d)"),
    "groq": dict(label="Groq (muy rápido · plan gratuito)", base="https://api.groq.com/openai/v1",
                 key_page="https://console.groq.com/keys", hint="openai/gpt-oss-120b",
                 prefer=[r"^openai/gpt-oss-120b$", r"^llama-3\.3-70b", r"gpt-oss", r"^llama"],
                 reasoning=r"gpt-oss|qwen3|deepseek-r1"),
    "deepseek": dict(label="DeepSeek", base="https://api.deepseek.com/v1",
                     key_page="https://platform.deepseek.com/api_keys", hint="deepseek-chat",
                     prefer=[r"^deepseek-chat$"], reasoning=None),
    "mistral": dict(label="Mistral", base="https://api.mistral.ai/v1",
                    key_page="https://console.mistral.ai/api-keys", hint="mistral-small-latest",
                    prefer=[r"^mistral-small-latest$", r"^mistral-medium-latest$", r"small"], reasoning=None),
    "xai": dict(label="Grok (xAI)", base="https://api.x.ai/v1", key_page="https://console.x.ai",
                hint="grok-…-fast", prefer=[r"^grok.*fast", r"^grok.*mini", r"^grok"], reasoning=r"mini"),
    "openrouter": dict(label="OpenRouter (cientos de modelos)", base="https://openrouter.ai/api/v1",
                       key_page="https://openrouter.ai/keys", hint="openrouter/auto · openai/gpt-…-mini",
                       prefer=[], default="openrouter/auto", reasoning=None),
    "custom": dict(label="Servidor propio / local (Ollama, LM Studio…)", base="http://127.0.0.1:11434/v1",
                   key_page="", hint="nombre del modelo (p. ej. qwen3:8b)", prefer=[], reasoning=None,
                   needs_key=False, has_base_url=True),
}

_SKIP = re.compile(r"audio|realtime|transcribe|tts|whisper|embed|image|dall-e|moderation|search|guard|vision|codex",
                   re.I)


def _version(model_id: str) -> tuple:
    return tuple(float(n) for n in re.findall(r"\d+(?:\.\d+)?", model_id)[:3]) or (0.0,)


class OpenAICompat(Provider):
    def __init__(self, preset_id: str):
        super().__init__()
        p = PRESETS[preset_id]
        self.id, self.label, self.key_page, self.model_hint = preset_id, p["label"], p["key_page"], p["hint"]
        self.default_base_url = p["base"]
        self.needs_key = p.get("needs_key", True)
        self.has_base_url = p.get("has_base_url", False)
        self._prefer, self._default = p["prefer"], p.get("default", "")
        self._reasoning = re.compile(p["reasoning"]) if p.get("reasoning") else None
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._chosen: dict[tuple, str] = {}
        self._unsupported: dict[str, set] = {}  # modelo → parámetros que el servicio no admite

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        cache_key = (self.key, self.base_url)
        with self._lock:
            if cache_key in self._chosen:
                return self._chosen[cache_key]
        if self._default and not self._prefer:
            return self._default
        try:
            r = self._session.get(f"{self.base_url}/models", headers=self._headers(), timeout=(3, 10))
        except requests.RequestException as e:
            self.pause(30)  # sin conexión: no retrasar cada mensaje reintentando
            raise AIError(f"sin conexión con {self.label}") from e
        if r.status_code in (400, 401, 403):  # xAI responde 400 a una clave mala
            self.pause(600)
            raise AIError(f"clave de {self.label} no válida")
        if r.status_code >= 400:
            raise AIError(f"{self.label} no devolvió la lista de modelos ({r.status_code}); escribe uno en Ajustes")
        ids = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
        ids = [i for i in ids if not _SKIP.search(i)]
        best = ""
        for pattern in self._prefer:
            matches = [i for i in ids if re.search(pattern, i)]
            if matches:
                best = max(matches, key=_version)
                break
        best = best or self._default or (ids[0] if ids else "")
        if not best:
            raise AIError(f"{self.label}: no hay modelos disponibles; escribe uno en Ajustes")
        log.info("%s: modelo elegido %s", self.label, best)
        with self._lock:
            self._chosen[cache_key] = best
        return best

    def translate(self, text, target, context=None):
        model = self.resolved_model()
        unsupported = self._unsupported.setdefault(model, set())
        body = {"model": model, "messages": [{"role": "system", "content": system_prompt(target)},
                                             {"role": "user", "content": user_prompt(text, context)}]}
        if "response_format" not in unsupported:
            body["response_format"] = {"type": "json_object"}
        if self._reasoning and self._reasoning.search(model) and "reasoning_effort" not in unsupported:
            body["reasoning_effort"] = "low"
        for _attempt in range(3):  # quitar parámetros que el servicio no admita
            try:
                # un servidor local tarda en cargar el modelo la primera vez
                r = self._session.post(f"{self.base_url}/chat/completions", headers=self._headers(),
                                       data=json.dumps(body), timeout=(3, 60 if self.has_base_url else 15))
            except requests.RequestException as e:
                self.pause(30)
                raise AIError(f"sin conexión con {self.label}") from e
            if r.status_code == 400:
                msg = r.text.lower()
                dropped = next((p for p in ("reasoning_effort", "response_format") if p in body and p in msg), None)
                if dropped:
                    log.info("%s/%s no admite '%s'; se envía sin él", self.label, model, dropped)
                    unsupported.add(dropped)
                    body.pop(dropped)
                    continue
            break
        if r.status_code in (401, 403):
            self.pause(600)
            raise AIError(f"clave de {self.label} no válida o sin permiso")
        if r.status_code == 404:
            raise AIError(f"{self.label}: modelo no encontrado ({model})")
        if r.status_code == 429:
            self.pause(60)
            raise AIError(f"{self.label}: límite de uso alcanzado")
        if r.status_code >= 400:
            raise AIError(f"{self.label} rechazó la petición ({r.status_code}): {r.text[:200]}")
        try:
            raw = r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise AIError(f"respuesta de {self.label} no utilizable") from e
        return parse_reply(raw)


def openrouter_login(cancel=None) -> str:
    """'Conectar con OpenRouter': login en el navegador (OAuth PKCE oficial de OpenRouter) que devuelve una
    clave propia del usuario, revocable en openrouter.ai/keys."""
    from .oauth import LoopbackLogin, pkce_pair
    verifier, challenge = pkce_pair()
    srv = LoopbackLogin("/callback", ports=(3000, 0), host_name="localhost")
    srv.open("https://openrouter.ai/auth?" + requests.compat.urlencode(
        {"callback_url": srv.redirect_uri, "code_challenge": challenge, "code_challenge_method": "S256"}))
    got = srv.wait(cancel)
    if not got.get("code"):
        raise AIError("no se completó la conexión con OpenRouter")
    try:
        r = requests.post("https://openrouter.ai/api/v1/auth/keys", timeout=20,
                          json={"code": got["code"], "code_verifier": verifier, "code_challenge_method": "S256"})
    except requests.RequestException as e:
        raise AIError("sin conexión con OpenRouter") from e
    if r.status_code >= 400 or not r.json().get("key"):
        raise AIError(f"OpenRouter no entregó la clave ({r.status_code})")
    return r.json()["key"]
