@echo off
setlocal
cd /d "%~dp0"
title Instalando BPT Converter

set "PY=.venv\Scripts\python.exe"

if exist "%PY%" goto :instalar

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Descargalo desde https://www.python.org/downloads/
    echo IMPORTANTE: marca la casilla "Add python.exe to PATH" al instalar.
    echo.
    pause
    exit /b 1
)

echo Creando entorno virtual...
python -m venv .venv
if errorlevel 1 goto :error
if not exist "%PY%" goto :error

:instalar
echo Instalando dependencias (Pillow, pillow-heif, imageio-ffmpeg, tkinterdnd2, yt-dlp)...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Verificando la instalacion...
"%PY%" -c "import PIL, pillow_heif, imageio_ffmpeg, yt_dlp" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Las dependencias no se instalaron correctamente.
    echo Cierra esta ventana, borra la carpeta ".venv" y ejecuta de nuevo "instalar.bat".
    echo.
    pause
    exit /b 1
)

echo.
echo Todo listo. Abre "Convertidor.bat" para usar el programa.
echo.
if /i not "%~1"=="/silencioso" pause
exit /b 0

:error
echo.
echo [ERROR] No se pudieron instalar las dependencias.
echo Revisa tu conexion a internet e intentalo de nuevo.
echo.
pause
exit /b 1
