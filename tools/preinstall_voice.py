"""Instala el motor de voz en una carpeta de datos SIN descargar nada (para pruebas locales del .exe):
  - lib/   desde dist/voice-engine-pyXY-win_amd64.zip
  - cuda/  copiando las DLLs de los paquetes nvidia-* instalados con pip
  - models/ enlace (junction) a los modelos ya descargados en %APPDATA%, si el destino es otro

Uso: python tools/preinstall_voice.py <carpeta DotaChatTranslator destino>
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
dest = Path(sys.argv[1]) / "voice"
real_models = Path(os.environ["APPDATA"]) / "DotaChatTranslator" / "voice" / "models"
zip_path = ROOT / "dist" / f"voice-engine-py{sys.version_info.major}{sys.version_info.minor}-win_amd64.zip"

lib = dest / "lib"
shutil.rmtree(lib, ignore_errors=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(lib)
(lib / ".complete").write_text("local")
print("lib:", lib)

cuda = dest / "cuda"
cuda.mkdir(parents=True, exist_ok=True)
site = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
n = 0
for sub in ("cublas", "cudnn", "cuda_nvrtc"):
    for dll in (site / sub / "bin").glob("*.dll"):
        if not (cuda / dll.name).exists():
            shutil.copy2(dll, cuda / dll.name)
        n += 1
(cuda / ".complete").write_text(json.dumps("local"))
print(f"cuda: {n} DLLs en {cuda}")

models = dest / "models"
if models.resolve() != real_models.resolve() and not models.exists():
    subprocess.check_call(["cmd", "/c", "mklink", "/J", str(models), str(real_models)], stdout=subprocess.DEVNULL)
print("models:", models, "->", sorted(p.name for p in models.iterdir()))
