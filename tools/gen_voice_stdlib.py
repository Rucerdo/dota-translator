"""Genera app/voice/_stdlib_refs.py: los módulos de la librería estándar que usa el motor de voz.

El .exe no lleva el motor de voz (se descarga aparte), pero sí debe llevar la parte de la librería
estándar de Python que el motor necesita, porque PyInstaller solo incluye lo que la app importa.
Este script ejecuta el motor de verdad y anota qué módulos estándar carga.

Uso (con el motor instalado y un modelo descargado):  python tools/gen_voice_stdlib.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
before = set(sys.modules)

import numpy as np  # noqa: E402

from app.voice import engine  # noqa: E402

model, _device = engine.load_model("turbo" if engine.model_ready("turbo") else "small")
audio = (np.sin(np.arange(32000) / 16000 * 2 * np.pi * 220) * 0.1).astype(np.float32)
list(model.transcribe(audio, beam_size=1, vad_filter=True, hotwords="Dota")[0])
from faster_whisper.vad import VadOptions, get_speech_timestamps  # noqa: E402

get_speech_timestamps(audio, VadOptions())
import app.voice.capture  # noqa: E402,F401
import app.voice.service  # noqa: E402,F401

stdlib = sys.stdlib_module_names
mods = sorted({m for m in sys.modules if m.split(".")[0] in stdlib and not m.startswith("_")
               and m.split(".")[0] not in ("tkinter", "idlelib", "test", "turtledemo", "lib2to3")})
out = ROOT / "app" / "voice" / "_stdlib_refs.py"
out.write_text('"""GENERADO por tools/gen_voice_stdlib.py. No editar.\n\nMódulos de la librería estándar que usa el '
               'motor de voz; se importan aquí solo\npara que PyInstaller los meta en el .exe."""\n'
               "# flake8: noqa\n" + "".join(f"import {m}\n" for m in mods), encoding="utf-8")
print(f"{len(mods)} módulos → {out}")
