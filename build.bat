@echo off
REM Genera dist\DotaChatTranslator.exe. La configuracion esta en tools\build_exe.py.
REM El motor de voz se empaqueta aparte:  py tools\build_voice_engine.py
cd /d "%~dp0"
py -m pip install -q -r requirements-dev.txt || goto :error
py tools\build_exe.py || goto :error
goto :eof
:error
echo Error en la compilacion.
exit /b 1
