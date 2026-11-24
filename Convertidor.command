#!/bin/bash
# Lanza BPT Converter en macOS (modo desarrollo).
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"

if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python convertidor.py --gui
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 convertidor.py --gui
fi

echo "No se encontró Python. Ejecuta ./instalar_macos.sh primero."
read -r -p "Pulsa Enter para cerrar..."
exit 1
