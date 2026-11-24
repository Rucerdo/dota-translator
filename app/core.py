"""Motor de la app: conecta GSI, traducción, overlay, voz e historial.

La app NO captura ni simula teclas: tus mensajes se escriben en la propia interfaz, se traducen y se
copian al portapapeles para pegarlos en el chat de Dota."""
import logging
import queue
import threading
import time
from collections import Counter

from . import config as cfgmod
from . import dota
from .gsi import SLOT_COLORS, ChatMessage, GSIServer
from .history import History
from .i18n import t
from .overlay import GRAY, Overlay
from .portraits import PortraitCache
from .translator import translate_chat

log = logging.getLogger(__name__)
ORANGE, CYAN = "#FFB74D", "#4FC3F7"


class Engine:
    def __init__(self, root, cfg: dict):
        self.cfg = cfg
        self.events: queue.Queue = queue.Queue()  # → GUI: ("record", dict)
        self.history = History(cfgmod.HISTORY_PATH)
        self.overlay = Overlay(root, cfg["overlay"], cfg["overlay_enabled"])
        self.gsi = GSIServer(int(cfg["gsi_port"]), self.on_message)
        self.lang_votes: Counter = Counter()
        self.recent: dict[str, float] = {}
        self.sent: dict[str, float] = {}
        self.stats = {"in": 0, "out": 0, "voice": 0}
        self.portraits = PortraitCache()
        self.voice = None          # VoiceService cuando la voz está activa
        self.voice_status = "stopped"
        self.lock = threading.Lock()
        self.dota_dir = dota.normalize(cfg.get("dota_dir")) or dota.find_dota_dir()
        from .ai import chatgpt_plan
        chatgpt_plan.SAVE_HOOK = self._save_chatgpt_session

    def _save_chatgpt_session(self, creds_json: str):
        """El token de ChatGPT rota al renovarse: guardar el nuevo (cifrado) sin reconfigurar el traductor."""
        from .ai import encrypt_key
        self.cfg.setdefault("ai_keys_enc", {})["chatgpt"] = encrypt_key(creds_json)
        cfgmod.save(self.cfg)

    # ---------- ciclo de vida ----------
    def start(self):
        self.gsi.start()  # lanza OSError si el puerto está ocupado
        if self.dota_dir and self.cfg.get("auto_install_gsi", True) and not self.gsi_installed():
            try:
                dota.install(self.dota_dir, int(self.cfg["gsi_port"]))
                log.info("integración GSI instalada en %s", self.dota_dir)
            except OSError:
                log.exception("no se pudo instalar la integración GSI")
        self.apply()
        self.sync_voice()

    def shutdown(self):
        self.gsi.stop()
        if self.voice:
            self.voice.stop()
            self.voice = None

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
        if keys[0] in ("voice_enabled", "voice_model", "voice_process"):
            self.sync_voice(restart=keys[0] != "voice_enabled")

    def apply(self):
        from . import translator
        from .ai import decrypt_key
        engine = self.cfg.get("translator_engine", "google")
        translator.configure(engine, decrypt_key((self.cfg.get("ai_keys_enc") or {}).get(engine, "")),
                             (self.cfg.get("ai_models") or {}).get(engine, ""),
                             (self.cfg.get("ai_base_urls") or {}).get(engine, ""))
        self.overlay.apply_cfg(self.cfg["overlay"])
        self.overlay.set_enabled(bool(self.cfg["overlay_enabled"]))

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
            if self.sent.pop(key, 0) > now - 120:  # eco de un mensaje tuyo traducido y pegado en Dota
                return
        ignore = {s.strip().lower() for s in self.cfg.get("ignore_messages", [])}
        if key in ignore or not any(c.isalpha() for c in msg.text):
            return
        threading.Thread(target=self._process_incoming, args=(msg,), daemon=True).start()

    def _process_incoming(self, msg: ChatMessage):
        icon = None
        if self.cfg.get("show_hero_icons", True):
            try:  # primero el retrato: cuanto antes, más fiel al momento del mensaje
                icon = self.portraits.get(msg.match_id, msg.player_id, self.cfg.get("topbar"))
            except Exception:
                log.exception("no se pudo obtener el retrato del héroe")
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
        rec = self._record("in", msg.match_id, msg.channel, msg.player_id, detected, target, msg.text, translated,
                           icon=icon)
        self._show(rec)

    # ---------- tus mensajes (escritos en la interfaz) ----------
    def compose(self, text: str, lang: str | None = None, mode: str = "copy"):
        """Traduce un mensaje tuyo. lang=None → idioma por defecto (el del equipo si es 'auto').
        mode: 'copy' (Chat en vivo: solo copiar) | 'team' / 'all' (caja del juego: enviar a ese chat).
        El resultado llega a la interfaz como ("composed", (registro, mode))."""
        def run():
            target = lang or self.outgoing_lang()
            try:
                translated, detected = translate_chat(text, target)
            except Exception:
                log.exception("error traduciendo tu mensaje")
                translated, detected = text, "?"
            with self.lock:  # cuando Dota lo devuelva por GSI, no se vuelve a traducir
                self.sent[translated.strip().lower()] = time.time()
            self.stats["out"] += 1
            channel = mode if mode in ("team", "all") else ""
            rec = self._record("out", self.gsi.match_id, channel, None, detected, target, text, translated)
            self.events.put(("composed", (rec, mode)))
            self._show(rec)
        threading.Thread(target=run, daemon=True).start()

    # ---------- voz ----------
    def voice_ready(self) -> bool:
        from .voice import engine
        return engine.ready(self.cfg.get("voice_model", "turbo"))

    def sync_voice(self, restart: bool = False):
        """Arranca o para el servicio de voz según la configuración (sin bloquear la interfaz)."""
        want = bool(self.cfg.get("voice_enabled")) and self.voice_ready()
        if self.voice and (restart or not want):
            old, self.voice = self.voice, None
            threading.Thread(target=old.stop, daemon=True).start()
            self._on_voice_status("stopped")
        if want and not self.voice:
            from .voice.service import VoiceService
            self.voice = VoiceService(lambda: self.cfg, self.on_voice_text, self._on_voice_status)
            self.voice.start()

    def _on_voice_status(self, status: str):
        self.voice_status = status
        self.events.put(("voice_status", status))

    def on_voice_text(self, text: str, lang: str, speakers: list[int]):
        """Una frase del chat de voz ya transcrita por Whisper."""
        base = (lang or "").split("-")[0].lower()
        skipped = base in {c.lower() for c in self.cfg.get("voice_skip_langs", [])}
        if skipped and not self.cfg.get("voice_show_skipped", False):
            log.info("voz en '%s' no se traduce (filtro de idiomas)", base)
            return
        pid = speakers[0] if speakers else None
        icon = None
        if pid is not None and self.cfg.get("show_hero_icons", True):
            try:
                icon = self.portraits.get(self.gsi.match_id, pid, self.cfg.get("topbar"))
            except Exception:
                log.exception("no se pudo obtener el retrato del héroe")
        target = self.cfg["incoming_target_lang"]
        same = (lang or "").split("-")[0] == target.split("-")[0]
        if skipped or (same and self.cfg.get("skip_if_source_is_target", True)):
            translated = text  # sin llamar al traductor
        else:
            try:
                translated, _ = translate_chat(text, target)
            except Exception:
                log.exception("error de traducción")
                translated = text
        self.stats["voice"] += 1
        rec = self._record("voice", self.gsi.match_id, "", pid, lang, target, text, translated, icon=icon)
        rec["speakers"] = list(speakers)
        self._show(rec)

    # ---------- vista previa ----------
    def preview_overlay(self):
        self.overlay.push([(f"[{t('ch_team')}] {t('blue')}: ", SLOT_COLORS[0][1]),
                           ("ve mid, estoy en offlane" if self.cfg["ui_lang"] == "es" else "go mid, I'm offlane",
                            "#FFFFFF"), (f"ru: {t('preview_1')}", GRAY)])
        self.overlay.push([(f"[{t('ch_all')}] {t('orange')}: ", SLOT_COLORS[4][1]),
                           ("Empujemos la torre" if self.cfg["ui_lang"] == "es" else "Let's push the tower",
                            "#FFFFFF"), (f"zh-CN: {t('preview_2')}", GRAY)])

    # ---------- utilidades ----------
    def _record(self, direction, match_id, channel, player_id, src, tgt, original, translated, save=True,
                icon: bytes | None = None) -> dict:
        kw = dict(match_id=match_id, direction=direction, channel=channel, player_id=player_id,
                  src_lang=src, tgt_lang=tgt, original=original, translated=translated, icon=icon)
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
        elif rec["direction"] == "voice":
            pid = rec.get("player_id")
            known = isinstance(pid, int) and 0 <= pid < 10
            who = t(SLOT_COLORS[pid][0]) if known else t("voice")
            extra = len(rec.get("speakers") or []) - 1
            if extra > 0:
                who += f" +{extra}"
            segs = [(f"🎤 {who}: ", SLOT_COLORS[pid][1] if known else CYAN), (rec["translated"], "#FFFFFF")]
        else:
            pid = rec.get("player_id")
            color = SLOT_COLORS[pid][1] if isinstance(pid, int) and 0 <= pid < 10 else CYAN
            who = t(SLOT_COLORS[pid][0]) if isinstance(pid, int) and 0 <= pid < 10 else t("test")
            ch = {"all": f"[{t('ch_all')}] ", "team": f"[{t('ch_team')}] "}.get(rec.get("channel"), "")
            segs = [(f"{ch}{who}: ", color), (rec["translated"], "#FFFFFF")]
        if self.cfg.get("show_original", True) and rec["translated"].strip().lower() != rec["original"].lower():
            segs.append((f"{rec['src_lang']}: {rec['original']}", GRAY))
        self.overlay.push(segs, icon=rec.get("icon"))
