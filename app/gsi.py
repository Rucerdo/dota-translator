"""Servidor local de Game State Integration: recibe el chat de Dota 2.

Formato confirmado (Dota 2, 2026):
    {"event_type": "chat_message", "player_id": 0-9, "channel_type": 11|12, "message": "..."}
    channel_type 11 = todos, 12 = aliados
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

log = logging.getLogger(__name__)

# Colores de jugador de Dota por player_id 0-9 (clave i18n, color)
SLOT_COLORS = [
    ("blue", "#3375FF"), ("teal", "#66FFBF"), ("purple", "#BF00BF"), ("yellow", "#F3F00B"),
    ("orange", "#FF6B00"), ("pink", "#FE86C2"), ("olive", "#A1B447"), ("light_blue", "#65D9F7"),
    ("green", "#008321"), ("brown", "#A46900"),
]


@dataclass
class ChatMessage:
    text: str
    player_id: int | None = None
    channel: str = ""  # "all" | "team" | ""
    match_id: str = ""

    @property
    def color(self) -> str:
        if self.player_id is not None and 0 <= self.player_id < 10:
            return SLOT_COLORS[self.player_id][1]
        return "#FFFFFF"

    @property
    def color_key(self) -> str:
        if self.player_id is not None and 0 <= self.player_id < 10:
            return SLOT_COLORS[self.player_id][0]
        return ""


def _parse_event(e: dict, match_id: str) -> ChatMessage | None:
    if not isinstance(e, dict) or "chat" not in str(e.get("event_type", "")).lower():
        return None
    text = e.get("message") or e.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    pid = e.get("player_id")
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        pid = None
    channel = {11: "all", 12: "team"}.get(e.get("channel_type"), "")
    return ChatMessage(text=text.strip(), player_id=pid, channel=channel, match_id=match_id)


class GSIServer:
    def __init__(self, port: int, on_message: Callable[[ChatMessage], None]):
        self.port, self.on_message = port, on_message
        self.last_payload_time = 0.0
        self.match_id = ""
        self._seen: dict = {}
        self._lock = threading.Lock()
        self._srv: ThreadingHTTPServer | None = None

    @property
    def connected(self) -> bool:
        return time.time() - self.last_payload_time < 40  # heartbeat de Dota = 30 s

    def _fresh(self, key) -> bool:
        now = time.time()
        with self._lock:
            if len(self._seen) > 500:
                self._seen = {k: t for k, t in self._seen.items() if now - t < 120}
            if key in self._seen:
                return False
            self._seen[key] = now
            return True

    def handle(self, payload: dict):
        self.last_payload_time = time.time()
        m = payload.get("map") or {}
        if m.get("matchid") is not None:
            self.match_id = str(m.get("matchid"))
        for e in payload.get("events") or []:
            msg = _parse_event(e, self.match_id)
            if msg and self._fresh((e.get("game_time"), msg.player_id, msg.text)):
                self.on_message(msg)

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.end_headers()
                try:
                    outer.handle(json.loads(body.decode("utf-8", errors="replace")))
                except Exception:
                    log.exception("error procesando payload GSI")

            def log_message(self, *a):
                pass

        self._srv = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)  # OSError si el puerto está ocupado
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        log.info("GSI escuchando en 127.0.0.1:%s", self.port)

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None
