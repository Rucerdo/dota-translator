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


def main():
    setup_logging()
    logging.getLogger("app").info("%s v%s iniciando", APP_NAME, __version__)
    from .gui import App
    App(cfgmod.load()).mainloop()


if __name__ == "__main__":
    main()
