"""Inicio de sesión en el navegador (OAuth con PKCE y vuelta a 127.0.0.1), sin claves secretas.

Se abre la página de login del servicio en el navegador; al aceptar, el servicio redirige a un
servidor HTTP mínimo que la app levanta un momento en tu propio PC (127.0.0.1) y que recibe el código.
"""
import base64
import hashlib
import http.server
import logging
import secrets
import threading
import urllib.parse
import webbrowser

log = logging.getLogger(__name__)

_PAGE = """<!doctype html><meta charset="utf-8"><title>Dota Chat Translator</title>
<body style="font-family:Segoe UI,sans-serif;background:#111;color:#eee;text-align:center;padding-top:15vh">
<h2>{title}</h2><p>{body}</p></body>"""


class LoginCancelled(Exception):
    pass


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    return verifier, challenge


class LoopbackLogin:
    """Servidor de un solo uso en 127.0.0.1 que espera la redirección del login.

    Uso: login = LoopbackLogin("/auth/callback", ports=(1455, 0)); login.redirect_uri → URL a pasar al
    servicio; login.open(url); params = login.wait(cancel_event)."""

    def __init__(self, path: str, ports=(0,), host_name: str = "127.0.0.1"):
        self.path = path
        self.result: dict | None = None
        self._done = threading.Event()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                if url.path != outer.path:
                    self.send_response(404)
                    self.end_headers()
                    return
                params = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
                ok = "code" in params and "error" not in params
                page = _PAGE.format(title="✔ Listo" if ok else "✖ No se completó",
                                    body="Ya puedes cerrar esta pestaña y volver a la app." if ok else
                                    "Vuelve a la app e inténtalo de nuevo.")
                data = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                if outer.result is None:
                    outer.result = params
                    outer._done.set()

            def log_message(self, *_a):
                pass

        last_err = None
        for port in ports:
            try:
                self._server = http.server.HTTPServer(("127.0.0.1", port), Handler)
                break
            except OSError as e:
                last_err = e
        else:
            raise OSError(f"no se pudo abrir un puerto local para el login: {last_err}")
        self.port = self._server.server_address[1]
        self.redirect_uri = f"http://{host_name}:{self.port}{path}"
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()

    def open(self, url: str):
        log.info("login: abriendo el navegador (vuelta a %s)", self.redirect_uri)
        webbrowser.open(url)

    def wait(self, cancel: threading.Event | None = None, timeout: float = 300) -> dict:
        try:
            waited = 0.0
            while not self._done.wait(0.25):
                waited += 0.25
                if (cancel and cancel.is_set()) or waited >= timeout:
                    raise LoginCancelled("inicio de sesión cancelado o caducado")
            return self.result or {}
        finally:
            def close():
                self._server.shutdown()
                self._server.server_close()
            threading.Thread(target=close, daemon=True).start()
