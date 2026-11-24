import logging
import sys
from logging.handlers import RotatingFileHandler

from . import APP_NAME, __version__
from . import config as cfgmod


def setup_logging():
    cfgmod.APP_DIR.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(cfgmod.LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:  # en el .exe sin consola no hay stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: logging.getLogger("app").critical("error no controlado", exc_info=exc)


def voice_selftest(wav_path: str):
    """Sin ventana: carga el motor de voz y transcribe un .wav (16 kHz mono). Resultado en voice_selftest.json.
    Sirve para comprobar que el .exe empaquetado puede usar el motor descargado."""
    import json
    import time
    import traceback
    import wave

    out = {"version": __version__, "ok": False}
    try:
        from .voice import engine
        engine.activate()  # añade las librerías descargadas del motor a la ruta de importación
        import numpy as np

        from .voice import capture, service  # noqa: F401  (que todo se pueda importar)
        key = "turbo" if engine.model_ready("turbo") else "small"
        t = time.time()
        model, device = engine.load_model(key)
        out.update(model=key, device=device, load_s=round(time.time() - t, 1))
        with wave.open(wav_path) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        t = time.time()
        segs, info = model.transcribe(audio, beam_size=1, vad_filter=True, hotwords=service.HOTWORDS)
        out.update(text=" ".join(s.text.strip() for s in segs), language=info.language,
                   transcribe_s=round(time.time() - t, 1), ok=True)
    except Exception:
        out["error"] = traceback.format_exc()
    (cfgmod.APP_DIR / "voice_selftest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                        encoding="utf-8")


def ai_selftest():
    """Sin ventana: cada proveedor de IA con una clave inventada debe responder 'clave no válida'
    (comprueba que el .exe empaquetado puede usar sus librerías). Resultado en ai_selftest.json."""
    import json

    from . import ai
    out = {}
    for pid in ai.ORDER:
        if pid == "custom":
            continue
        p = ai.new_provider(pid)
        p.configure("clave-inventada-para-prueba-0000000000", "", "")
        try:
            p.translate("test", "es-ES")
            out[pid] = "¿funcionó?"
        except ai.AIError as e:
            out[pid] = f"ok: {e}"
        except Exception as e:
            out[pid] = f"FALLO: {type(e).__name__}: {e}"
    (cfgmod.APP_DIR / "ai_selftest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    setup_logging()
    logging.getLogger("app").info("%s v%s iniciando", APP_NAME, __version__)
    if "--ai-selftest" in sys.argv:
        ai_selftest()
        return
    if "--voice-selftest" in sys.argv:
        voice_selftest(sys.argv[sys.argv.index("--voice-selftest") + 1])
        return
    from .gui import App
    App(cfgmod.load()).mainloop()


if __name__ == "__main__":
    main()
