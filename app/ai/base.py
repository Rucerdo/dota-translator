"""Interfaz común de los traductores con IA."""
import time

from .prompt import AIError


class Provider:
    id = ""
    label = ""
    key_page = ""            # dónde conseguir la clave
    needs_key = True
    has_base_url = False     # solo 'custom' (servidor propio / local)
    default_base_url = ""
    model_hint = ""          # ejemplo para el campo de modelo
    oauth = False            # se conecta iniciando sesión en el navegador (sin clave)

    def __init__(self):
        self.key = ""
        self.model = ""      # vacío = elegir automáticamente
        self.base_url = ""
        self.cooldown_until = 0.0

    def configure(self, key: str = "", model: str = "", base_url: str = ""):
        self.key, self.model = key.strip(), model.strip()
        self.base_url = (base_url or self.default_base_url).strip().rstrip("/")

    @property
    def available(self) -> bool:
        return (bool(self.key) or not self.needs_key) and time.time() >= self.cooldown_until

    def pause(self, seconds: float):
        self.cooldown_until = time.time() + seconds

    def resolved_model(self) -> str:
        return self.model

    def translate(self, text: str, target: str, context: list[str] | None = None) -> tuple[str, str]:
        raise AIError("no implementado")
