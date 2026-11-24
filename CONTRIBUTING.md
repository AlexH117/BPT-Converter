# Contribuir a BPT Converter

Gracias por tu interés en contribuir. Este documento describe cómo reportar problemas, proponer mejoras y preparar cambios.

## Antes de empezar

- Revisa los issues existentes para evitar duplicados.
- Para cambios grandes, abre primero un issue describiendo la propuesta.
- Mantén los cambios enfocados: un PR por mejora o corrección.

## Entorno de desarrollo

### Windows

```bat
instalar.bat
.venv\Scripts\python.exe convertidor.py --gui
```

### macOS

```bash
chmod +x instalar_macos.sh Convertidor.command consola_macos.command
./instalar_macos.sh
./Convertidor.command
```

## Ejecutar comprobaciones básicas

Antes de abrir un PR, verifica al menos:

```bash
python -m py_compile convertidor.py interfaz.py compilar_exe.py compilar_macos.py
```

Si tocaste el empaquetado, indica en el PR qué plataforma probaste (Windows/macOS) y qué artefacto generaste.

## Estilo y buenas prácticas

- Escribe código claro y consistente con el estilo existente.
- Prefiere cambios pequeños y fáciles de revisar.
- No incluyas artefactos generados (`dist/`, `dist_macos/`, `build/`, `.venv/`, logs).
- Si agregas dependencias, actualiza `requirements.txt` y explica por qué.
- Actualiza `README.md` o `LEEME.txt` cuando cambie el comportamiento visible para el usuario.

## Reportar bugs

Incluye en el issue:

- Sistema operativo y versión (Windows 10/11, macOS Intel/Apple Silicon).
- Versión de Python si aplica.
- Pasos para reproducir.
- Resultado esperado vs. resultado actual.
- Mensaje de error, log o captura relevante.

## Pull Requests

1. Crea una rama desde `main`.
2. Haz commits claros y descriptivos.
3. Explica en el PR qué cambió, por qué y cómo se probó.
4. Si el cambio afecta UI, adjunta captura o video corto.

## Seguridad

No publiques credenciales, tokens ni archivos personales. Si encuentras un problema de seguridad, evita exponer detalles sensibles en un issue público antes de coordinar una corrección.
