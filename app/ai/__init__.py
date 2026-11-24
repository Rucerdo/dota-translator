"""Traductores con IA (opcionales, cada usuario con su propia clave). Si fallan, se usa Google Translate.

Proveedores: ChatGPT con tu cuenta Plus/Pro (sin clave), Gemini, Claude, ChatGPT, Groq, DeepSeek, Mistral,
Grok, OpenRouter y servidor local.
"""
from .base import Provider
from .chatgpt_plan import ChatGPTPlan
from .claude import Claude
from .gemini import Gemini
from .openai_compat import PRESETS, OpenAICompat, openrouter_login
from .prompt import AIError
from .secrets import decrypt_key, encrypt_key

ORDER = ["chatgpt", "gemini", "claude", "openai", "groq", "deepseek", "mistral", "xai", "openrouter", "custom"]

PROVIDERS: dict[str, Provider] = {"chatgpt": ChatGPTPlan(), "gemini": Gemini(), "claude": Claude()}
for _pid in PRESETS:
    PROVIDERS[_pid] = OpenAICompat(_pid)


def new_provider(pid: str) -> Provider:
    """Instancia aparte (p. ej. para el botón 'Probar', sin tocar las pausas del cliente principal)."""
    if pid == "gemini":
        return Gemini()
    if pid == "claude":
        return Claude()
    if pid == "chatgpt":
        return PROVIDERS["chatgpt"]  # una sola instancia: el token de refresco rota y no se puede duplicar
    return OpenAICompat(pid)


__all__ = ["AIError", "ORDER", "PROVIDERS", "Provider", "decrypt_key", "encrypt_key", "new_provider",
           "openrouter_login"]
