#!/bin/bash
# Abre Terminal en la carpeta del proyecto con el venv activado (macOS).
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "BPT Converter - consola"
echo "Ejemplos:"
echo "  python convertidor.py --gui"
echo "  python convertidor.py archivo.mov -f mp4"
echo "  python convertidor.py \"https://www.youtube.com/watch?v=XXXXXXXXXXX\" -f mp3"
exec "${SHELL:-/bin/zsh}"
