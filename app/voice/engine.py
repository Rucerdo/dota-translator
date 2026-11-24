"""Motor de voz: descarga, instalación y carga de Whisper (faster-whisper / CTranslate2).

Nada de esto va dentro del .exe. Se descarga la primera vez que se activa la voz, a
%APPDATA%/DotaChatTranslator/voice/:

  lib/      librerías de Python del motor (solo en el .exe; un .zip publicado en cada release)
  cuda/     DLLs de NVIDIA (cuBLAS, cuDNN, NVRTC) sacadas de los paquetes oficiales de PyPI,
            solo si hay una gráfica NVIDIA
  models/   el modelo de Whisper, descargado de Hugging Face

Cada paso deja un archivo '.complete' al terminar; las descargas se reanudan si se cortan.
"""
import ctypes
import hashlib
import json
import logging
import os
import shutil
import sys
import sysconfig
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from .. import GITHUB_REPO, __version__
from ..config import APP_DIR

log = logging.getLogger(__name__)

VOICE_DIR = APP_DIR / "voice"
LIB_DIR = VOICE_DIR / "lib"
CUDA_DIR = VOICE_DIR / "cuda"
MODELS_DIR = VOICE_DIR / "models"
DOWNLOADS = VOICE_DIR / "downloads"
HEADERS = {"User-Agent": "DotaChatTranslator-voice"}

MODELS = {
    "turbo": {"repo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo", "device": "cuda",
              "files": ["config.json", "model.bin", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"]},
    "small": {"repo": "Systran/faster-whisper-small", "device": "cpu",
              "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]},
}

# Paquetes oficiales de NVIDIA en PyPI (versiones con rueda para Windows, probadas con CTranslate2 4.9)
CUDA_WHEELS = [("nvidia-cublas-cu12", "12.9.2.10"), ("nvidia-cudnn-cu12", "9.28.1.4"),
               ("nvidia-cuda-nvrtc-cu12", "12.9.86")]


def engine_zip_name() -> str:
    return f"voice-engine-py{sys.version_info.major}{sys.version_info.minor}-win_amd64.zip"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def nvidia_available() -> bool:
    """¿Hay driver de NVIDIA? (nvcuda.dll lo instala el driver)."""
    try:
        ctypes.WinDLL("nvcuda.dll")
        return True
    except OSError:
        return False


def _dev_cuda_dirs() -> list[Path]:
    """En desarrollo: DLLs de los paquetes nvidia-* instalados con pip."""
    site = Path(sysconfig.get_paths()["purelib"])
    return [p for p in (site / "nvidia" / "cublas" / "bin", site / "nvidia" / "cudnn" / "bin",
                        site / "nvidia" / "cuda_nvrtc" / "bin") if p.is_dir()]


# ---------------- estado ----------------
def lib_ready() -> bool:
    if not is_frozen():
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False
    return (LIB_DIR / ".complete").exists()


def cuda_ready() -> bool:
    if not is_frozen() and len(_dev_cuda_dirs()) == 3:
        return True
    return (CUDA_DIR / ".complete").exists()


def model_ready(key: str) -> bool:
    return (MODELS_DIR / key / ".complete").exists()


def device_for(key: str) -> str:
    return "cuda" if MODELS[key]["device"] == "cuda" and nvidia_available() else "cpu"


def ready(key: str) -> bool:
    return lib_ready() and model_ready(key) and (device_for(key) == "cpu" or cuda_ready())


def installed_size_mb() -> int:
    if not VOICE_DIR.exists():
        return 0
    return int(sum(f.stat().st_size for f in VOICE_DIR.rglob("*") if f.is_file()) / 1e6)


def remove_all():
    shutil.rmtree(VOICE_DIR, ignore_errors=True)


# ---------------- descargas ----------------
class Cancelled(Exception):
    pass


@dataclass
class Item:
    label: str
    url: str
    dest: Path
    size: int = 0
    sha256: str | None = None


def _download(item: Item, progress: Callable[[int], None], cancel: threading.Event):
    """Descarga con reanudación (cabecera Range) y verificación SHA-256 opcional."""
    item.dest.parent.mkdir(parents=True, exist_ok=True)
    part = item.dest.with_suffix(item.dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = dict(HEADERS)
    if have:
        headers["Range"] = f"bytes={have}-"
    with requests.get(item.url, headers=headers, stream=True, timeout=30, allow_redirects=True) as r:
        if r.status_code == 416:  # ya estaba completo
            pass
        else:
            r.raise_for_status()
            if have and r.status_code != 206:  # el servidor no reanuda: empezar de cero
                have = 0
            progress(have)
            with open(part, "ab" if have else "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if cancel.is_set():
                        raise Cancelled()
                    f.write(chunk)
                    have += len(chunk)
                    progress(have)
    if item.sha256:
        h = hashlib.sha256()
        with open(part, "rb") as f:
            for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(block)
        if h.hexdigest() != item.sha256.lower():
            part.unlink(missing_ok=True)
            raise ValueError(f"{item.label}: el SHA-256 no coincide")
    part.replace(item.dest)


def _pypi_wheel(name: str, version: str) -> Item:
    r = requests.get(f"https://pypi.org/pypi/{name}/{version}/json", headers=HEADERS, timeout=15)
    r.raise_for_status()
    for u in r.json()["urls"]:
        if u["filename"].endswith("win_amd64.whl"):
            return Item(name, u["url"], DOWNLOADS / u["filename"], u["size"], u["digests"]["sha256"])
    raise ValueError(f"{name} {version} no tiene paquete para Windows")


def _model_items(key: str) -> list[Item]:
    repo = MODELS[key]["repo"]
    r = requests.get(f"https://huggingface.co/api/models/{repo}/tree/main", headers=HEADERS, timeout=15)
    r.raise_for_status()
    sizes = {f["path"]: f.get("size", 0) for f in r.json()}
    return [Item(f"{key}/{f}", f"https://huggingface.co/{repo}/resolve/main/{f}", MODELS_DIR / key / f,
                 sizes.get(f, 0)) for f in MODELS[key]["files"]]


def _engine_item() -> Item:
    override = os.environ.get("DCT_VOICE_ENGINE_URL")  # pruebas: URL o ruta a un .zip local
    if override:
        return Item("engine", override, DOWNLOADS / engine_zip_name())
    r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/v{__version__}",
                     headers=HEADERS, timeout=15)
    r.raise_for_status()
    for a in r.json().get("assets", []):
        if a["name"] == engine_zip_name():
            return Item("engine", a["browser_download_url"], DOWNLOADS / a["name"], a.get("size", 0))
    raise ValueError(f"la release v{__version__} no incluye {engine_zip_name()}")


def plan(key: str) -> list[tuple[str, list[Item]]]:
    """Pasos pendientes para dejar listo el modelo 'key': [(paso, [descargas])]."""
    steps = []
    if not lib_ready():
        steps.append(("engine", [_engine_item()]))
    if device_for(key) == "cuda" and not cuda_ready():
        steps.append(("cuda", [_pypi_wheel(n, v) for n, v in CUDA_WHEELS]))
    if not model_ready(key):
        steps.append(("model", _model_items(key)))
    return steps


def install(key: str, progress: Callable[[str, int, int], None], cancel: threading.Event):
    """Descarga e instala lo que falte. progress(paso, bytes_hechos, bytes_totales)."""
    steps = plan(key)
    total = sum(i.size for _s, items in steps for i in items) or 1
    done_before = 0
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for step, items in steps:
        for item in items:
            if item.url and not item.url.startswith("http"):  # .zip local (pruebas)
                if Path(item.url) != item.dest:
                    shutil.copyfile(item.url, item.dest)
            elif not item.dest.exists():
                _download(item, lambda n, b=done_before: progress(step, b + n, total), cancel)
            done_before += item.size or (item.dest.stat().st_size if item.dest.exists() else 0)
            progress(step, done_before, total)
        _finish_step(step, items, key)
    shutil.rmtree(DOWNLOADS, ignore_errors=True)


def _finish_step(step: str, items: list[Item], key: str):
    if step == "engine":
        shutil.rmtree(LIB_DIR, ignore_errors=True)
        with zipfile.ZipFile(items[0].dest) as z:
            z.extractall(LIB_DIR)
        (LIB_DIR / ".complete").write_text(__version__)
    elif step == "cuda":
        CUDA_DIR.mkdir(parents=True, exist_ok=True)
        for item in items:
            with zipfile.ZipFile(item.dest) as z:
                for name in z.namelist():
                    if name.lower().endswith(".dll") and "/bin/" in name.replace("\\", "/"):
                        with z.open(name) as src, open(CUDA_DIR / Path(name).name, "wb") as dst:
                            shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
            item.dest.unlink(missing_ok=True)
        (CUDA_DIR / ".complete").write_text(json.dumps(CUDA_WHEELS))
    elif step == "model":
        (MODELS_DIR / key / ".complete").write_text(MODELS[key]["repo"])


# ---------------- carga ----------------
_dll_handles: list = []


def _stub_av():
    """faster-whisper importa PyAV ('av') solo para leer archivos de audio, cosa que no hacemos (le pasamos
    el audio ya capturado). PyAV no va en el motor (64 MB de FFmpeg): si no está, un módulo vacío basta."""
    if "av" in sys.modules:
        return
    try:
        import av  # noqa: F401
    except ImportError:
        import types
        stub = types.ModuleType("av")
        stub.__doc__ = "sustituto: PyAV no se usa en Dota Chat Translator"
        sys.modules["av"] = stub


def activate():
    """Hace importable el motor: añade lib/ a sys.path y las DLLs de CUDA a la búsqueda de DLLs."""
    if is_frozen() and str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    _stub_av()
    dirs = _dev_cuda_dirs() if (not is_frozen() and len(_dev_cuda_dirs()) == 3) else [CUDA_DIR]
    for d in dirs:
        if d.is_dir() and str(d) not in os.environ.get("PATH", ""):
            _dll_handles.append(os.add_dll_directory(str(d)))
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def load_model(key: str, cpu_threads: int = 2):
    """Devuelve (WhisperModel, device)."""
    activate()
    from faster_whisper import WhisperModel
    device = device_for(key)
    if device == "cuda":
        import ctranslate2
        if ctranslate2.get_cuda_device_count() < 1:
            log.warning("CUDA no disponible; se usa la CPU")
            device = "cpu"
    compute = "int8_float16" if device == "cuda" else "int8"
    model = WhisperModel(str(MODELS_DIR / key), device=device, compute_type=compute, cpu_threads=cpu_threads)
    log.info("modelo de voz '%s' cargado en %s (%s)", key, device, compute)
    return model, device
