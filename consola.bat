@echo off
setlocal
cd /d "%~dp0"
title BPT Converter - consola
echo.
echo  Consola del convertidor. Ejemplos:
echo.
echo    python convertidor.py --formatos
echo    python convertidor.py "C:\ruta\fotos" -f jpg -r
echo    python convertidor.py video.mov -f mp4
echo    python convertidor.py audio.m4a -f mp3
echo.
echo  Escribe "exit" para cerrar.
echo.
cmd /k ".venv\Scripts\python.exe" convertidor.py --formatos
