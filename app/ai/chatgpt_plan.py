"""ChatGPT con tu cuenta ("Sign in with ChatGPT"): traduce gastando el uso de tu plan Plus/Pro, sin clave de API.

Flujo para apps de código abierto que funcionan en local (documentación: developers.openai.com/siwc):
- Login en el navegador con OAuth + PKCE y vuelta a http://127.0.0.1:<puerto>/auth/callback. La primera vez
  se registra la app con client_id=dynamic_agent_client y OpenAI devuelve el client_id propio de esta
  instalación, que se guarda y se reutiliza.
- Tokens: el de acceso dura 1 h, el de refresco 30 días y rota en cada refresco (se guarda el nuevo).
- Traducción: POST https://api.openai.com/v1/responses con store=false y stream=true.
- El uso cuenta para los límites de tu plan; puedes ponerle tope a la app en chatgpt.com/settings/usage.

Las credenciales se guardan como la "clave" de este proveedor, cifradas con DPAPI.
"""
import base64
import json
import logging
import re
import secrets as pysecrets
import threading
import time
import urllib.parse
import uuid

import requests

from .base import Provider
from .oauth import LoopbackLogin, pkce_pair
from .prompt import AIError, parse_reply, system_prompt, user_prompt

log = logging.getLogger(__name__)

AUTH_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
ISSUER = "https://auth.openai.com"
API = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
USE_SCOPE = "chatgpt.tokens.use.direct"
APP_NAME = "Dota Chat Translator"
USAGE_PAGE = "https://chatgpt.com/settings/usage"

# Cuando la credencial cambia (refresco), se avisa para guardarla: fn(creds_json: str)
SAVE_HOOK = None
_SAVE_LOCK = threading.Lock()

_REAUTH = {"invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired",
           "refresh_token_invalidated", "refresh_token_reused"}


class NeedsLogin(AIError):
    pass


def _jwt_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except Exception:
        return {}


def login(host_id: str, saved: dict | None = None, cancel: threading.Event | None = None) -> dict:
    """Abre el navegador para iniciar sesión. Devuelve las credenciales (dict) o lanza AIError.
    saved: credenciales anteriores (para reutilizar el client_id registrado y la cuenta)."""
    saved = saved or {}
    client_id = saved.get("client_id", "")
    verifier, challenge = pkce_pair()
    state, nonce = pysecrets.token_urlsafe(24), pysecrets.token_urlsafe(24)
    srv = LoopbackLogin("/auth/callback", ports=(1455, 1456, 1457, 0))
    params = {"client_id": client_id or "dynamic_agent_client", "ext_agent_host_id": host_id,
              "response_type": "code", "redirect_uri": srv.redirect_uri, "scope": SCOPES, "resource": API,
              "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
    if not client_id:
        params["agent_name_hint"] = APP_NAME
    elif saved.get("id_token"):
        params["id_token_hint"] = saved["id_token"]
    srv.open(f"{AUTH_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}")
    got = srv.wait(cancel)
    if got.get("state") != state:
        raise AIError("respuesta de inicio de sesión no válida (state)")
    if got.get("error"):
        if got["error"] == "access_denied":
            raise AIError("no se dio permiso para usar tu plan de ChatGPT")
        raise AIError(f"OpenAI rechazó el inicio de sesión: {got.get('error_description') or got['error']}")
    issued = got.get("client_id", "")
    if client_id and issued and issued != client_id:
        raise AIError("respuesta de inicio de sesión no válida (client_id)")
    client_id = client_id or issued
    if not client_id:
        raise AIError("OpenAI no completó el registro de la app; inténtalo de nuevo")
    try:
        r = requests.post(TOKEN_URL, data={"grant_type": "authorization_code", "client_id": client_id,
                                           "code": got.get("code", ""), "code_verifier": verifier,
                                           "redirect_uri": srv.redirect_uri, "resource": API}, timeout=20)
    except requests.RequestException as e:
        raise AIError("sin conexión con OpenAI") from e
    if r.status_code >= 400:
        raise AIError(f"OpenAI no entregó los tokens ({r.status_code}): {r.text[:200]}")
    tok = r.json()
    claims = _jwt_claims(tok.get("id_token", ""))
    # Los tokens llegan directamente del servidor por HTTPS; se comprueban emisor, destinatario y nonce.
    if claims.get("iss") != ISSUER or claims.get("nonce") != nonce or \
            client_id not in (claims.get("aud") if isinstance(claims.get("aud"), list) else [claims.get("aud")]):
        raise AIError("token de identidad no válido")
    if USE_SCOPE not in (tok.get("scope") or "").split():
        raise AIError("la cuenta no permitió usar el plan de ChatGPT en esta app")
    creds = {"client_id": client_id, "access_token": tok["access_token"],
             "refresh_token": tok.get("refresh_token", ""), "id_token": tok.get("id_token", ""),
             "expires_at": time.time() + float(tok.get("expires_in", 3600)), "email": claims.get("email", ""),
             "sub": claims.get("sub", "")}
    log.info("ChatGPT: sesión iniciada")
    return creds


def revoke(creds: dict):
    """Cierra la sesión en OpenAI (revoca el token de refresco). Si falla, no pasa nada."""
    try:
        disc = requests.get(f"{ISSUER}/.well-known/openid-configuration", timeout=10).json()
        url = disc.get("revocation_endpoint")
        if url and creds.get("refresh_token"):
            requests.post(url, data={"token": creds["refresh_token"], "token_type_hint": "refresh_token",
                                     "client_id": creds.get("client_id", "")}, timeout=10)
    except Exception:
        log.info("ChatGPT: no se pudo revocar el token (se borra igualmente)")


def new_host_id() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


class ChatGPTPlan(Provider):
    id = "chatgpt"
    label = "ChatGPT · tu plan Plus/Pro (sin clave)"
    key_page = USAGE_PAGE
    model_hint = "se elige solo"
    oauth = True

    def __init__(self):
        super().__init__()
        self.creds: dict = {}
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._chosen = ""
        self._dropped: set[str] = set()

    def configure(self, key="", model="", base_url=""):
        super().configure(key, model, base_url)
        try:
            creds = json.loads(self.key) if self.key else {}
        except ValueError:
            creds = {}
        with self._lock:
            if creds.get("refresh_token") != self.creds.get("refresh_token"):
                self._chosen = ""
            self.creds = creds

    @property
    def account(self) -> str:
        return self.creds.get("email", "")

    def _save(self):
        if SAVE_HOOK:
            with _SAVE_LOCK:
                try:
                    SAVE_HOOK(json.dumps(self.creds))
                except Exception:
                    log.exception("ChatGPT: no se pudieron guardar las credenciales")

    def _access_token(self) -> str:
        try:
            return self._refresh_if_needed()
        except NeedsLogin:
            self._save()  # guardar que la sesión ya no vale (fuera del candado)
            raise

    def _refresh_if_needed(self) -> str:
        with self._lock:
            c = self.creds
            if not c.get("refresh_token") and not c.get("access_token"):
                raise NeedsLogin("inicia sesión con ChatGPT en Ajustes")
            if c.get("access_token") and time.time() < c.get("expires_at", 0) - 120:
                return c["access_token"]
            try:
                r = self._session.post(TOKEN_URL, data={"grant_type": "refresh_token",
                                                        "client_id": c.get("client_id", ""),
                                                        "refresh_token": c.get("refresh_token", ""),
                                                        "resource": API}, timeout=(5, 20))
            except requests.RequestException as e:
                self.pause(30)
                raise AIError("sin conexión con OpenAI") from e
            if r.status_code >= 400:
                try:
                    err = r.json().get("error", "")
                except ValueError:
                    err = ""
                if isinstance(err, dict):
                    err = err.get("code", "")
                if err in _REAUTH or r.status_code in (400, 401):
                    self.creds = {k: v for k, v in c.items() if k in ("client_id", "email", "id_token")}
                    self.pause(600)
                    raise NeedsLogin("la sesión de ChatGPT caducó; vuelve a iniciar sesión en Ajustes")
                self.pause(60)
                raise AIError(f"OpenAI no renovó la sesión ({r.status_code})")
            tok = r.json()
            c.update(access_token=tok["access_token"], refresh_token=tok.get("refresh_token") or c["refresh_token"],
                     expires_at=time.time() + float(tok.get("expires_in", 3600)))
            if tok.get("id_token"):
                c["id_token"] = tok["id_token"]
        self._save()
        return c["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        if self._chosen:
            return self._chosen
        try:
            r = self._session.get(f"{API}/models", headers=self._headers(), timeout=(5, 15))
        except requests.RequestException as e:
            self.pause(30)
            raise AIError("sin conexión con OpenAI") from e
        self._check_status(r)
        data = r.json()
        models = data.get("models") or data.get("data") or []
        slugs = [m.get("slug") or m.get("id") for m in models
                 if (m.get("visibility", "list") == "list") and (m.get("slug") or m.get("id"))]
        if not slugs:
            raise AIError("tu cuenta de ChatGPT no tiene modelos disponibles para apps")
        # para chat corto, mejor uno rápido si existe
        fast = [s for s in slugs if re.search(r"mini|nano|fast|instant", s, re.I)]
        self._chosen = (fast or slugs)[0]
        log.info("ChatGPT: modelo elegido %s (disponibles: %s)", self._chosen, ", ".join(slugs[:8]))
        return self._chosen

    def _check_status(self, r: requests.Response):
        if r.status_code < 400:
            return
        code, detail = "", r.text[:200]
        try:
            body = r.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                code, detail = err.get("code") or "", err.get("message") or detail
            elif isinstance(body.get("detail"), str):
                detail = body["detail"]
        self._raise_code(code, r.status_code, detail)

    def _raise_code(self, code: str, status: int, detail: str = ""):
        if code == "subscription_sharing_usage_limit_exceeded" or status == 429:
            self.pause(300)
            raise AIError(f"límite de tu plan de ChatGPT alcanzado (mira {USAGE_PAGE})")
        if code == "subscription_sharing_user_not_eligible":
            self.pause(3600)
            raise AIError("tu cuenta de ChatGPT no puede usar el plan en apps (hace falta Plus o Pro)")
        if code in ("subscription_sharing_usage_unavailable", "subscription_sharing_user_unavailable") or \
                status in (502, 503, 504):
            self.pause(30)
            raise AIError("el plan de ChatGPT no está disponible ahora mismo")
        if code == "subscription_sharing_invalid_user" or status == 401:
            self.pause(120)
            with self._lock:
                self.creds["expires_at"] = 0  # forzar refresco la próxima vez
            raise AIError("OpenAI no aceptó la sesión; si sigue, vuelve a iniciar sesión")
        if status == 403:
            self.pause(600)
            raise AIError(f"OpenAI denegó el acceso: {detail or code}")
        raise AIError(f"OpenAI rechazó la petición ({status or 'stream'}): {detail or code}")

    def translate(self, text, target, context=None):
        model = self.resolved_model()
        body = {"model": model, "instructions": system_prompt(target),
                "input": [{"role": "user", "content": user_prompt(text, context)}],
                "store": False, "stream": True}
        if "reasoning" not in self._dropped:
            body["reasoning"] = {"effort": "low"}
        for _attempt in range(2):
            try:
                r = self._session.post(f"{API}/responses", headers=self._headers(), data=json.dumps(body),
                                       stream=True, timeout=(5, 30))
            except requests.RequestException as e:
                self.pause(30)
                raise AIError("sin conexión con OpenAI") from e
            if r.status_code == 400 and "reasoning" in body and "reasoning" in r.text:
                log.info("ChatGPT/%s no admite 'reasoning'; se envía sin él", model)
                self._dropped.add("reasoning")
                body.pop("reasoning")
                continue
            break
        self._check_status(r)
        out, done = [], False
        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except ValueError:
                    continue
                kind = ev.get("type", "")
                if kind == "response.output_text.delta":
                    out.append(ev.get("delta", ""))
                elif kind == "response.completed":
                    done = True
                    break
                elif kind in ("response.failed", "error", "response.incomplete"):
                    err = (ev.get("response") or {}).get("error") or ev.get("error") or {}
                    code = err.get("code", "") if isinstance(err, dict) else ""
                    if code == "subscription_sharing_unsupported_capability" and err.get("param") == "reasoning":
                        self._dropped.add("reasoning")
                    self._raise_code(code, 0, err.get("message", kind) if isinstance(err, dict) else kind)
        except requests.RequestException as e:
            raise AIError("se cortó la conexión con OpenAI") from e
        finally:
            r.close()
        if not done:
            raise AIError("respuesta de ChatGPT incompleta")
        return parse_reply("".join(out))
