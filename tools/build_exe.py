"""Compila dist/DotaChatTranslator.exe con PyInstaller (un solo archivo, sin consola).

El motor de voz NO va dentro (se empaqueta aparte con tools/build_voice_engine.py), pero el .exe sí
lleva lo que ese motor necesita del propio Python:
  - app/voice/_stdlib_refs.py: módulos de la librería estándar que usa (generado por gen_voice_stdlib.py)
  - python3.dll (API estable, la piden p. ej. tokenizers) y vcruntime140_1.dll

Uso:  python tools/build_exe.py
"""
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(sys.base_prefix)
EXCLUDE = ["numpy", "faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers", "huggingface_hub", "torch"]

args = [
    str(ROOT / "run.py"),
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "DotaChatTranslator",
    "--icon", str(ROOT / "assets" / "icon.ico"),
    "--add-data", f"{ROOT / 'assets' / 'icon.ico'};assets",
    "--add-data", f"{ROOT / 'app' / 'glossary.json'};app",
    "--collect-data", "customtkinter",
    "--hidden-import", "app.voice._stdlib_refs",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
]
for dll in ("python3.dll", "vcruntime140_1.dll"):
    if (BASE / dll).exists():
        args += ["--add-binary", f"{BASE / dll};."]
for mod in EXCLUDE:
    args += ["--exclude-module", mod]

PyInstaller.__main__.run(args)
print(f"Listo: {ROOT / 'dist' / 'DotaChatTranslator.exe'}")
