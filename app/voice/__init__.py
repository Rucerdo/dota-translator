"""Transcripción del chat de voz de Dota 2 (función opcional y experimental).

capture.py   audio de dota2.exe con 'process loopback' de Windows (sin tarjetas virtuales)
engine.py    descarga/instala el motor (librerías, CUDA, modelo Whisper) y lo carga
service.py   une todo: segmenta, transcribe con Whisper y entrega el texto
"""
