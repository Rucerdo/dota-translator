"""Registro de conversaciones en SQLite (%APPDATA%/DotaChatTranslator/history.db)."""
import csv
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    match_id    TEXT,
    direction   TEXT NOT NULL,      -- 'in' recibido, 'out' enviado por ti, 'test' prueba
    channel     TEXT,               -- 'all' | 'team' | ''
    player_id   INTEGER,
    src_lang    TEXT,
    tgt_lang    TEXT,
    original    TEXT NOT NULL,
    translated  TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_match ON messages(match_id);
"""

COLUMNS = ["id", "ts", "match_id", "direction", "channel", "player_id", "src_lang", "tgt_lang",
           "original", "translated"]


class History:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(messages)")}
        if "icon" not in cols:  # migración v1.0.0 → retrato del héroe (PNG)
            self.db.execute("ALTER TABLE messages ADD COLUMN icon BLOB")
            self.db.commit()
        self.lock = threading.Lock()

    def add(self, *, match_id: str, direction: str, channel: str, player_id, src_lang: str, tgt_lang: str,
            original: str, translated: str, icon: bytes | None = None) -> dict:
        rec = dict(ts=datetime.now().isoformat(timespec="seconds"), match_id=match_id or "", direction=direction,
                   channel=channel or "", player_id=player_id, src_lang=src_lang or "", tgt_lang=tgt_lang or "",
                   original=original, translated=translated, icon=icon)
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO messages (ts, match_id, direction, channel, player_id, src_lang, tgt_lang, original,"
                " translated, icon) VALUES (:ts, :match_id, :direction, :channel, :player_id, :src_lang, :tgt_lang,"
                " :original, :translated, :icon)", rec)
            self.db.commit()
            rec["id"] = cur.lastrowid
        return rec

    def sessions(self) -> list[dict]:
        """Partidas registradas, la más reciente primero."""
        with self.lock:
            rows = self.db.execute(
                "SELECT match_id, MIN(ts) AS start, COUNT(*) AS n FROM messages "
                "GROUP BY match_id ORDER BY start DESC").fetchall()
        return [dict(r) for r in rows]

    def query(self, match_id: str | None = None, search: str = "", limit: int = 2000) -> list[dict]:
        sql, args = "SELECT * FROM messages WHERE 1=1", []
        if match_id is not None:
            sql += " AND match_id = ?"
            args.append(match_id)
        if search:
            sql += " AND (original LIKE ? OR translated LIKE ?)"
            args += [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def export_csv(self, path: str, rows: list[dict]):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel abre bien los acentos
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(reversed(rows))

    def clear(self):
        with self.lock:
            self.db.execute("DELETE FROM messages")
            self.db.commit()
