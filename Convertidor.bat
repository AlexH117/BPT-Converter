@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "PYW=.venv\Scripts\pythonw.exe"

if not exist "%PYW%" (
    echo Primera ejecucion: preparando el entorno...
    call "%~dp0instalar.bat" /silencioso
)

if not exist "%PY%" goto :error_entorno
if not exist "%PYW%" goto :error_entorno

"%PY%" -c "import PIL, pillow_heif, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo Faltan librerias. Reparando el entorno...
    call "%~dp0instalar.bat" /silencioso
)

"%PY%" -c "import PIL, pillow_heif, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 goto :error_dependencias

start "" "%PYW%" "%~dp0convertidor.py" --gui
exit /b 0

:error_entorno
echo.
echo [ERROR] No se pudo preparar el entorno de Python.
echo Ejecuta "instalar.bat" y revisa los mensajes de error.
echo.
pause
exit /b 1

:error_dependencias
echo.
echo [ERROR] Faltan librerias en el entorno del programa.
echo Ejecuta "instalar.bat" para repararlo.
echo.
pause
exit /b 1
