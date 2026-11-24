"""Genera dist/voice-engine-pyXY-win_amd64.zip: las librerías de Python del motor de voz.

La app (el .exe) lo descarga de la release la primera vez que se activa la voz y lo descomprime en
%APPDATA%/DotaChatTranslator/voice/lib. Debe generarse con la MISMA versión de Python que el .exe.

Uso:  python tools/build_voice_engine.py
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "voice-engine"
NAME = f"voice-engine-py{sys.version_info.major}{sys.version_info.minor}-win_amd64.zip"
OUT = ROOT / "dist" / NAME

# Ya van dentro del .exe o no hacen falta en tiempo de ejecución
PRUNE = {"bin", "share", "include"}

shutil.rmtree(BUILD, ignore_errors=True)
BUILD.mkdir(parents=True)
subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-compile", "--only-binary=:all:",
                       "--target", str(BUILD), "-r", str(ROOT / "requirements-voice.txt")])
# faster-whisper sin dependencias: así no arrastra PyAV (ver requirements-voice.txt)
subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-compile", "--only-binary=:all:", "--no-deps",
                       "--target", str(BUILD), "faster-whisper==1.2.1"])
for p in list(BUILD.iterdir()):
    if p.name in PRUNE:
        shutil.rmtree(p, ignore_errors=True)
for p in BUILD.rglob("__pycache__"):
    shutil.rmtree(p, ignore_errors=True)
for p in BUILD.rglob("tests"):
    if p.is_dir() and p.parent.name in ("numpy", "onnxruntime", "av", "tokenizers"):
        shutil.rmtree(p, ignore_errors=True)

OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in sorted(BUILD.rglob("*")):
        if f.is_file():
            z.write(f, f.relative_to(BUILD).as_posix())
print(f"{OUT}  {OUT.stat().st_size / 1e6:.0f} MB")
