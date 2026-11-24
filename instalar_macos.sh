#!/bin/bash
set -euo pipefail

# Instalador de dependencias para BPT Converter en macOS.
# Uso:
#   chmod +x instalar_macos.sh
#   ./instalar_macos.sh

BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"

echo "== BPT Converter - instalación macOS =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: no se encontró python3. Instala Python 3 desde https://www.python.org/downloads/ o con Homebrew." >&2
  exit 1
fi

PYTHON_BIN="python3"
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
fi

echo "Usando Python: $($PYTHON_BIN --version)"

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual .venv..."
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# PyInstaller solo es necesario para compilar la app.
if [ "${1:-}" = "--build" ]; then
  python -m pip install pyinstaller
fi

echo
echo "Instalación completada."
echo "Para abrir la aplicación en modo desarrollo:"
echo "  ./Convertidor.command"
echo
echo "Para compilar la app .app/.dmg (solo en macOS):"
echo "  .venv/bin/python compilar_macos.py"
