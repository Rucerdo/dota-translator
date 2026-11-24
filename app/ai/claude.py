"""Claude (Anthropic), con el SDK oficial 'anthropic'. Clave: https://console.anthropic.com/settings/keys

- Modelo por defecto: claude-opus-5-5. Para más velocidad y menos coste se puede elegir claude-haiku-5-5
  (o claude-sonnet-5-5) en Ajustes.
- Esfuerzo 'low' (lo recomendado para chat): en Opus 5.5 el razonamiento no se puede desactivar,
  el esfuerzo es lo que controla profundidad y latencia.
- Salida JSON garantizada con output_config.format (json_schema).
- Si un filtro de seguridad rechaza el mensaje (stop_reason 'refusal'), en Opus/Sonnet 5.5 se usa el
  respaldo del servidor ('fallbacks': 'default'); si aun así se rechaza, la app vuelve a Google.
"""
import logging
import threading

import anthropic

from .base import Provider
from .prompt import SCHEMA, AIError, parse_reply, system_prompt, user_prompt

log = logging.getLogger(__name__)

MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
DEFAULT_MODEL = "claude-opus-5-5"
_SERVER_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}  # Haiku 5.5 no tiene respaldo en el servidor
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Claude(Provider):
    id = "claude"
    label = "Claude (Anthropic)"
    key_page = "https://console.anthropic.com/settings/keys"
    model_hint = "claude-opus-5-5 · claude-haiku-5-5"

    def __init__(self):
        super().__init__()
        self._client: anthropic.Anthropic | None = None
        self._client_key = ""
        self._lock = threading.Lock()
        self._no_fallback_param = False  # si la cuenta no admite 'fallbacks', no volver a enviarlo

    def resolved_model(self) -> str:
        return self.model or DEFAULT_MODEL

    def _get_client(self) -> anthropic.Anthropic:
        with self._lock:
            if self._client is None or self._client_key != self.key:
                # sin reintentos del SDK: si falla, la app pasa a Google al momento en vez de esperar
                self._client = anthropic.Anthropic(api_key=self.key, max_retries=0, timeout=15.0)
                self._client_key = self.key
            return self._client

    def translate(self, text, target, context=None):
        client = self._get_client()
        model = self.resolved_model()
        output_config = {"format": {"type": "json_schema", "schema": SCHEMA}}
        if model in MODELS:
            output_config["effort"] = "low"
        params = dict(model=model, max_tokens=2048, system=system_prompt(target), output_config=output_config,
                      messages=[{"role": "user", "content": user_prompt(text, context)}])
        try:
            if model in _SERVER_FALLBACK and not self._no_fallback_param:
                try:
                    response = client.beta.messages.create(betas=[_FALLBACK_BETA], fallbacks="default", **params)
                except anthropic.BadRequestError as e:
                    if "fallback" not in str(e).lower():
                        raise
                    log.info("la cuenta no admite 'fallbacks'; se envía sin él")
                    self._no_fallback_param = True
                    response = client.messages.create(**params)
            else:
                response = client.messages.create(**params)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            self.pause(600)
            raise AIError("clave de Claude no válida o sin permiso") from e
        except anthropic.NotFoundError as e:
            raise AIError(f"modelo de Claude no encontrado: {model}") from e
        except anthropic.RateLimitError as e:
            self.pause(60)
            raise AIError("Claude: límite de uso alcanzado") from e
        except anthropic.BadRequestError as e:
            raise AIError(f"Claude rechazó la petición: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise AIError(f"error de Claude ({e.status_code})") from e
        except anthropic.APIConnectionError as e:
            self.pause(30)
            raise AIError("sin conexión con Claude") from e
        if response.stop_reason == "refusal":
            raise AIError("Claude rechazó traducir este mensaje")
        raw = next((b.text for b in response.content if b.type == "text"), "")
        return parse_reply(raw)
