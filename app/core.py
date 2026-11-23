"""Motor de la app: conecta GSI, traducción, overlay, envío con Ctrl+Enter e historial."""
import logging
import queue
import threading
import time
from collections import Counter

import keyboard

from . import config as cfgmod
from . import dota
from .gsi import SLOT_COLORS, ChatMessage, GSIServer
from .history import History
from .i18n import t
from .outgoing import OutgoingTranslator
from .overlay import GRAY, Overlay
from .translator import translate, translate_chat

log = logging.getLogger(__name__)
ORANGE, CYAN = "#FFB74D", "#4FC3F7"


class Engine:
    def __init__(self, root, cfg: dict):
        self.cfg = cfg
        self.events: queue.Queue = queue.Queue()  # → GUI: ("record", dict)
        self.history = History(cfgmod.HISTORY_PATH)
        self.overlay = Overlay(root, cfg["overlay"], cfg["overlay_enabled"])
        self.gsi = GSIServer(int(cfg["gsi_port"]), self.on_message)
        self.outgoing = OutgoingTranslator(translate_chat, self.outgoing_lang, self.on_sent)
        self.lang_votes: Counter = Counter()
        self.recent: dict[str, float] = {}
        self.sent: dict[str, float] = {}
        self.stats = {"in": 0, "out": 0}
        self.lock = threading.Lock()
        self._hotkeys: list = []
        self.dota_dir = dota.normalize(cfg.get("dota_dir")) or dota.find_dota_dir()

    # ---------- ciclo de vida ----------
    def start(self):
        self.gsi.start()  # lanza OSError si el puerto está ocupado
        if self.dota_dir and self.cfg.get("auto_install_gsi", True) and not self.gsi_installed():
            try:
                dota.install(self.dota_dir, int(self.cfg["gsi_port"]))
                log.info("integración GSI instalada en %s", self.dota_dir)
            except OSError:
                log.exception("no se pudo instalar la integración GSI")
        self.outgoing.start()
        self.apply()

    def shutdown(self):
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.gsi.stop()

    # ---------- configuración ----------
    def set(self, path: str, value):
        """Cambia una opción ('overlay.font_size'), la guarda y la aplica."""
        node = self.cfg
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        cfgmod.save(self.cfg)
        self.apply()

    def apply(self):
        self.overlay.apply_cfg(self.cfg["overlay"])
        self.overlay.set_enabled(bool(self.cfg["overlay_enabled"]))
        self.outgoing.configure(self.cfg["hotkeys"]["translate_and_send"], bool(self.cfg["enable_outgoing"]))
        for h in self._hotkeys:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        self._hotkeys = []
        try:
            self._hotkeys.append(keyboard.add_hotkey(self.cfg["hotkeys"]["toggle_overlay"], self._toggle_overlay))
        except ValueError:
            log.warning("atajo inválido: %s", self.cfg["hotkeys"]["toggle_overlay"])

    def _toggle_overlay(self):
        self.cfg["overlay_enabled"] = not self.cfg["overlay_enabled"]
        cfgmod.save(self.cfg)
        self.overlay.set_enabled(self.cfg["overlay_enabled"])
        self.events.put(("cfg", None))

    # ---------- Dota / GSI ----------
    def gsi_installed(self) -> bool:
        return dota.is_installed(self.dota_dir, int(self.cfg["gsi_port"]))

    def set_dota_dir(self, folder: str) -> bool:
        d = dota.normalize(folder)
        if not d:
            return False
        self.dota_dir = d
        self.set("dota_dir", str(d))
        return True

    def install_gsi(self):
        dota.install(self.dota_dir, int(self.cfg["gsi_port"]))
        self.set("auto_install_gsi", True)

    def uninstall_gsi(self):
        dota.uninstall(self.dota_dir)
        self.set("auto_install_gsi", False)

    # ---------- idiomas ----------
    def outgoing_lang(self) -> str:
        lang = self.cfg.get("outgoing_lang", "auto")
        if lang != "auto":
            return lang
        with self.lock:
            if self.lang_votes:
                return self.lang_votes.most_common(1)[0][0]
        return self.cfg.get("outgoing_fallback_lang", "ru")

    # ---------- mensajes entrantes ----------
    def on_message(self, msg: ChatMessage):
        key = msg.text.lower()
        now = time.time()
        with self.lock:
            self.recent = {k: v for k, v in self.recent.items() if now - v < 8}
            if key in self.recent:
                return
            self.recent[key] = now
            if self.sent.pop(key, 0) > now - 30:  # eco de lo que enviaste con Ctrl+Enter
                return
        ignore = {s.strip().lower() for s in self.cfg.get("ignore_messages", [])}
        if key in ignore or not any(c.isalpha() for c in msg.text):
            return
        threading.Thread(target=self._process_incoming, args=(msg,), daemon=True).start()

    def _process_incoming(self, msg: ChatMessage):
        target = self.cfg["incoming_target_lang"]
        try:
            translated, detected = translate_chat(msg.text, target)
        except Exception:
            log.exception("error de traducción")
            translated, detected = msg.text, "?"
        same = detected.split("-")[0] == target.split("-")[0]
        if not same and detected not in ("?", "auto", "und"):
            with self.lock:
                self.lang_votes[detected] += 1
        if same and self.cfg.get("skip_if_source_is_target", True):
            return
        self.stats["in"] += 1
        rec = self._record("in", msg.match_id, msg.channel, msg.player_id, detected, target, msg.text, translated)
        self._show(rec)

    # ---------- mensajes salientes ----------
    def on_sent(self, original: str, translated: str, detected: str, lang: str):
        with self.lock:
            self.sent[translated.strip().lower()] = time.time()
        self.stats["out"] += 1
        rec = self._record("out", self.gsi.match_id, "", None, detected, lang, original, translated)
        self._show(rec)

    # ---------- pruebas ----------
    def test_translate(self, text: str):
        def run():
            target = self.cfg["incoming_target_lang"]
            try:
                translated, detected = translate_chat(text, target)
            except Exception:
                log.exception("error de traducción")
                translated, detected = text, "?"
            rec = self._record("test", "", "", None, detected, target, text, translated, save=False)
            self._show(rec)
        threading.Thread(target=run, daemon=True).start()

    def preview_overlay(self):
        self.overlay.push([(f"[{t('ch_team')}] {t('blue')}: ", SLOT_COLORS[0][1]),
                           ("ve mid, estoy en offlane" if self.cfg["ui_lang"] == "es" else "go mid, I'm offlane",
                            "#FFFFFF"), (f"ru: {t('preview_1')}", GRAY)])
        self.overlay.push([(f"[{t('ch_all')}] {t('orange')}: ", SLOT_COLORS[4][1]),
                           ("Empujemos la torre" if self.cfg["ui_lang"] == "es" else "Let's push the tower",
                            "#FFFFFF"), (f"zh-CN: {t('preview_2')}", GRAY)])

    # ---------- utilidades ----------
    def _record(self, direction, match_id, channel, player_id, src, tgt, original, translated, save=True) -> dict:
        kw = dict(match_id=match_id, direction=direction, channel=channel, player_id=player_id,
                  src_lang=src, tgt_lang=tgt, original=original, translated=translated)
        if save and self.cfg.get("save_history", True):
            try:
                return self.history.add(**kw)
            except Exception:
                log.exception("no se pudo guardar en el historial")
        return {**kw, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def _show(self, rec: dict):
        self.events.put(("record", rec))
        if rec["direction"] == "out":
            segs = [(f"{t('you')} → {rec['tgt_lang']}: ", ORANGE), (rec["translated"], "#FFFFFF")]
        else:
            pid = rec.get("player_id")
            color = SLOT_COLORS[pid][1] if isinstance(pid, int) and 0 <= pid < 10 else CYAN
            who = t(SLOT_COLORS[pid][0]) if isinstance(pid, int) and 0 <= pid < 10 else t("test")
            ch = {"all": f"[{t('ch_all')}] ", "team": f"[{t('ch_team')}] "}.get(rec.get("channel"), "")
            segs = [(f"{ch}{who}: ", color), (rec["translated"], "#FFFFFF")]
        if self.cfg.get("show_original", True) and rec["translated"].strip().lower() != rec["original"].lower():
            segs.append((f"{rec['src_lang']}: {rec['original']}", GRAY))
        self.overlay.push(segs)
