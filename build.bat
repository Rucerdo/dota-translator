@echo off
REM Genera dist\DotaChatTranslator.exe (un solo archivo, sin consola).
cd /d "%~dp0"
py -m pip install -q -r requirements-dev.txt || goto :error
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name DotaChatTranslator ^
  --icon assets\icon.ico ^
  --add-data "assets\icon.ico;assets" ^
  --add-data "app\glossary.json;app" ^
  --collect-data customtkinter ^
  run.py || goto :error
echo.
echo Listo: dist\DotaChatTranslator.exe
goto :eof
:error
echo Error en la compilacion.
exit /b 1
