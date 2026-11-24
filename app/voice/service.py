"""Servicio de voz: captura de dota2.exe → detector de voz (Silero VAD) → Whisper → texto.

Se transcribe todo lo que se habla en el audio del juego (chat de voz y también frases de héroes);
se descartan el locutor de Dota y las frases que Whisper inventa con ruido o silencio.
"""
import collections
import ctypes
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from . import engine
from .capture import SAMPLE_RATE, ProcessAudioCapture

log = logging.getLogger(__name__)

MAX_SEGMENT = 15.0  # s: las frases más largas se cortan

HOTWORDS = ("Dota, Roshan, Aegis, carry, support, mid, top, bot, offlane, BKB, Blink, smoke, ward, sentry, "
            "gank, push, TP, buyback, Рошан, керри, мид, варды, смок, ганк, пуш, 肉山, 辅助, 中路, 插眼")

# Frases que Whisper "inventa" con silencio o ruido (subtítulos de YouTube) y locutor de Dota
_HALLUCINATIONS = re.compile(
    r"(thanks? (you )?for watching|subtitles? by|amara\.org|like and subscribe|please subscribe|"
    r"субтитры|редактор субтитров|продолжение следует|спасибо за просмотр|подписывайтесь|"
    r"字幕|请不吝点赞|订阅|感谢观看|gracias por ver|suscr[ií]bete|sous-titres|untertitel)", re.I)
_ANNOUNCER = re.compile(
    r"^(first blood|double kill|triple kill|ultra kill|rampage|killing spree|dominating|mega kill|unstoppable|"
    r"wicked sick|monster kill|godlike|beyond godlike|holy shit|ownage|the battle begins|"
    r"(the )?(radiant|dire)( victory|'s .* (is|are) under attack)?|roshan has been (slain|killed)|"
    r"aegis (denied|stolen)|.*has (fallen|been destroyed))[.!]*$", re.I)


_SCRIPTS = {  # alfabeto esperado según el idioma que detecta Whisper
    "ru": r"[Ѐ-ӿ]", "uk": r"[Ѐ-ӿ]", "bg": r"[Ѐ-ӿ]", "kk": r"[Ѐ-ӿ]",
    "zh": r"[一-鿿]", "ja": r"[぀-ヿ一-鿿]", "ko": r"[가-힯]",
    "th": r"[฀-๿]", "ar": r"[؀-ۿ]", "fa": r"[؀-ۿ]", "el": r"[Ͱ-Ͽ]",
    "he": r"[֐-׿]",
}


def script_matches(text: str, lang: str) -> bool:
    """Descarta salidas incoherentes (p. ej. 'español' escrito en cirílico)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    pattern = _SCRIPTS.get(lang)
    if pattern:
        ok = sum(1 for ch in letters if re.match(pattern, ch))
    else:  # idiomas con alfabeto latino
        ok = sum(1 for ch in letters if ch.isascii() or "À" <= ch <= "ɏ")
    return ok / len(letters) >= 0.6


@dataclass
class Segment:
    start: float
    end: float
    speakers: list[int] = field(default_factory=list)


class VoiceService:
    def __init__(self, get_cfg: Callable[[], dict], on_text: Callable[[str, str, list[int]], None],
                 on_status: Callable[[str], None]):
        self.get_cfg, self.on_text, self.on_status = get_cfg, on_text, on_status
        self._audio: collections.deque = collections.deque()  # (t_inicio, t_fin, bytes)
        self._audio_lock = threading.Lock()
        self._segments: queue.Queue = queue.Queue(maxsize=20)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._capture: ProcessAudioCapture | None = None
        self.model = None
        self.device = ""
        self.status = "stopped"

    # ---------- ciclo de vida ----------
    def start(self):
        self._stop.clear()
        t = threading.Thread(target=self._boot, name="voice-boot", daemon=True)
        t.start()
        self._threads = [t]

    def stop(self):
        self._stop.set()
        if self._capture:
            self._capture.stop()
        for t in self._threads:
            t.join(3)
        self.model = None  # libera la VRAM
        self._set_status("stopped")

    def _set_status(self, s: str):
        self.status = s
        try:
            self.on_status(s)
        except Exception:
            pass

    def _boot(self):
        cfg = self.get_cfg()
        key = cfg.get("voice_model", "turbo")
        self._set_status("loading")
        try:
            self.model, self.device = engine.load_model(key)
            import numpy as np  # calentamiento: la 1ª transcripción en GPU tarda más
            list(self.model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)[0])
        except Exception:
            log.exception("no se pudo cargar el modelo de voz")
            self._set_status("error")
            return
        if self._stop.is_set():
            return
        self._capture = ProcessAudioCapture(cfg.get("voice_process", "dota2.exe"), self._on_audio,
                                            self._on_capture_state)
        self._capture.start()
        for target, name in ((self._worker, "voice-whisper"), (self._vad_loop, "voice-segmenter")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def _on_capture_state(self, s: str):
        self._set_status({"capturing": "listening", "waiting": "waiting_dota"}.get(s, s))

    # ---------- audio ----------
    def _on_audio(self, chunk: bytes, t_end: float):
        dur = len(chunk) / 2 / SAMPLE_RATE
        with self._audio_lock:
            self._audio.append((t_end - dur, t_end, chunk))
            while self._audio and self._audio[0][1] < t_end - 40:  # se guardan 40 s
                self._audio.popleft()

    def _extract(self, start: float, end: float):
        import numpy as np
        with self._audio_lock:
            parts = [(s, e, b) for s, e, b in self._audio if e > start and s < end]
        if not parts:
            return None
        out = []
        for s, e, b in parts:
            a = np.frombuffer(b, dtype=np.int16)
            i0 = max(0, int((start - s) * SAMPLE_RATE))
            i1 = min(len(a), int((end - s) * SAMPLE_RATE))
            if i1 > i0:
                out.append(a[i0:i1])
        return (np.concatenate(out).astype(np.float32) / 32768.0) if out else None

    # ---------- segmentación por detector de voz ----------
    def _vad_loop(self):
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        opts = VadOptions(min_silence_duration_ms=600, speech_pad_ms=250, min_speech_duration_ms=300)
        consumed = time.monotonic()
        while not self._stop.wait(0.5):
            now = time.monotonic()
            start = max(consumed, now - MAX_SEGMENT - 2)
            audio = self._extract(start, now)
            if audio is None or len(audio) < SAMPLE_RATE:
                continue
            ts = get_speech_timestamps(audio, opts)
            for t in ts:
                s, e = start + t["start"] / SAMPLE_RATE, start + t["end"] / SAMPLE_RATE
                finished = e < now - 0.7
                too_long = (now - s) > MAX_SEGMENT
                if finished or too_long:
                    self._queue(Segment(s, e if finished else now))
                    consumed = e if finished else now
            if not ts:
                consumed = max(consumed, now - 1.0)

    def _queue(self, seg: Segment):
        if seg.end - seg.start < 0.4:
            return
        try:
            self._segments.put_nowait(seg)
        except queue.Full:
            log.warning("cola de voz llena; se descarta un fragmento")

    # ---------- transcripción ----------
    def _worker(self):
        try:  # prioridad baja: el juego va primero
            k32 = ctypes.windll.kernel32
            k32.SetThreadPriority(k32.GetCurrentThread(), -1)  # THREAD_PRIORITY_BELOW_NORMAL
        except Exception:
            pass
        while not self._stop.is_set():
            try:
                seg = self._segments.get(timeout=0.5)
            except queue.Empty:
                continue
            time.sleep(max(0.0, seg.end - time.monotonic() + 0.05))  # que el audio del final ya esté
            audio = self._extract(seg.start, seg.end)
            if audio is None or len(audio) < SAMPLE_RATE * 0.3:
                continue
            try:
                text, lang = self._transcribe(audio)
            except Exception:
                log.exception("error transcribiendo voz")
                continue
            if text:
                log.info("voz (%s, jugadores %s): %s", lang, seg.speakers, text)
                self.on_text(text, lang, seg.speakers)

    def _transcribe(self, audio) -> tuple[str, str]:
        if self.model is None:
            return "", ""
        segments, info = self.model.transcribe(
            audio, beam_size=1, vad_filter=True, condition_on_previous_text=False,
            hotwords=HOTWORDS, no_speech_threshold=0.6, log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4)
        parts = [s.text.strip() for s in segments if s.no_speech_prob < 0.6 and s.avg_logprob > -1.0]
        text = " ".join(p for p in parts if p).strip()
        if (len(re.sub(r"[\W_]+", "", text)) < 2 or _HALLUCINATIONS.search(text)
                or _ANNOUNCER.match(text) or info.language_probability < 0.5
                or not script_matches(text, info.language)):
            return "", info.language
        return text, info.language
