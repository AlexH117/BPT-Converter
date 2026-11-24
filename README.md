# BPT Converter

Aplicación de escritorio para **Windows y macOS** que convierte imágenes, vídeo y audio entre formatos, con soporte para descarga/conversión desde YouTube. Todo el procesamiento se realiza **localmente** en tu equipo.

## Características

- **Conversión por lotes** de imágenes, vídeo y audio.
- **Arrastrar y soltar** archivos en la interfaz (cuando `tkinterdnd2` está disponible).
- **Modo AUTO**: selecciona el formato recomendado según el tipo de archivo (imagen → JPG, vídeo → MP4, audio → MP3).
- **Descarga desde YouTube**: pega una URL, descarga y convierte a vídeo o extrae audio.
- **Control de resolución/calidad**: presets (4K, Full HD, HD, porcentaje, personalizado), calidad de imagen y CRF de vídeo.
- **Interfaz gráfica y CLI**: uso por ventana o por línea de comandos.
- **Empaquetado**: instalador/portable para Windows y `.app`/`.dmg` para macOS.

## Formatos compatibles

| Tipo | Entrada (ejemplos) | Salida |
|---|---|---|
| Imágenes | HEIC, HEIF, AVIF, JPG/JPEG, PNG, WEBP, BMP, TIFF, GIF, ICO, PPM | JPG, JPEG, PNG, WEBP, AVIF, TIFF, BMP, GIF |
| Vídeo | MOV, MP4, M4V, AVI, MKV, WEBM, WMV, FLV, MPEG, 3GP, TS/MTS, OGV, VOB | MP4, MOV, AVI, MKV, WEBM, WMV, FLV, MPEG, GIF |
| Audio | MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA, AIFF, ALAC | MP3, WAV, M4A, AAC, FLAC, OGG, OPUS |

> También puedes extraer audio desde vídeo (por ejemplo, `MOV → MP3`).

## Requisitos

### Uso en desarrollo

- Python 3.10+ recomendado.
- Dependencias Python: `Pillow`, `pillow-heif`, `imageio-ffmpeg`, `tkinterdnd2`, `yt-dlp`.
- FFmpeg: el proyecto usa `imageio-ffmpeg` en desarrollo; en paquetes empaquetados se incluye el binario.

### Uso empaquetado

- **Windows**: Windows 10/11 de 64 bits. No requiere Python ni FFmpeg instalados.
- **macOS**: app `.app`/`.dmg` generada en macOS. Para distribución pública se recomienda firma y notarización Apple.

## Inicio rápido

### Windows (desarrollo)

1. Haz doble clic en `Convertidor.bat`.
2. La primera ejecución instala dependencias en `.venv` si es necesario.
3. Arrastra archivos, elige formato/salida y pulsa **Convertir**.

Alternativa manual:

```bat
instalar.bat
.venv\Scripts\python.exe convertidor.py --gui
```

### macOS (desarrollo)

```bash
chmod +x instalar_macos.sh Convertidor.command consola_macos.command
./instalar_macos.sh
./Convertidor.command
```

## Uso por línea de comandos

```bash
# Abrir GUI
python convertidor.py --gui

# Ver formatos
python convertidor.py --formatos

# Convertir una imagen
python convertidor.py foto.heic -f jpg

# Convertir carpeta recursivamente
python convertidor.py ./entrada -f png -r -o ./salida

# Cambiar resolución manteniendo proporción
python convertidor.py video.mov -f mp4 --ancho 1280 --alto 720

# Escalar al 50%
python convertidor.py foto.jpg -f jpg --porcentaje 50

# Descargar YouTube y convertir
python convertidor.py "https://www.youtube.com/watch?v=XXXXXXXXXXX" -f mp4 -o ./Videos
python convertidor.py "https://youtu.be/XXXXXXXXXXX" -f mp3 -o ./Music
```

Opciones principales:

| Opción | Descripción |
|---|---|
| `-f, --formato` | Formato de salida o `auto` |
| `-o, --destino` | Carpeta de salida |
| `-r, --recursivo` | Procesa subcarpetas |
| `--calidad` | Calidad de imagen (1–100) |
| `--crf` | Calidad de vídeo (0–51, menor = mejor) |
| `--ancho` / `--alto` | Resolución de salida |
| `--porcentaje` | Escala por porcentaje |
| `--exacto` | Fuerza tamaño exacto |
| `--no-ampliar` | Evita ampliar archivos pequeños |
| `--sobrescribir` | Reemplaza archivos existentes |

## Descarga desde YouTube

- Pega la URL en el campo **Agregar URL** de la GUI.
- Formatos de vídeo: MP4, MKV, WEBM, AVI. Audio: MP3, WAV, FLAC, OGG, OPUS.
- Con **AUTO**, la descarga se convierte a **MP4**.
- Requiere conexión a internet. La descarga se realiza con `yt-dlp` y el procesamiento con FFmpeg.

## Compilación de paquetes

### Windows (`.exe` + instalador)

Requisitos: `.venv` con dependencias, PyInstaller e Inno Setup 6 para el instalador.

```bat
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe compilar_exe.py
```

Salida en `dist/`:

- `ConvertidorFormatos/` (aplicación instalable)
- `ConvertidorFormatos_Portable.exe`
- `Instalador_ConvertidorFormatos_1.2.exe` (si Inno Setup está disponible)

### macOS (`.app` + `.dmg`)

> PyInstaller **no** genera apps macOS desde Windows/Linux. Compila en macOS o usa GitHub Actions.

#### Opción A: GitHub Actions (recomendada para universal2)

1. Sube el repositorio a GitHub.
2. Abre **Actions → Build macOS → Run workflow**.
3. Selecciona `mode: universal`.
4. Descarga el artifact `BPTConverter-macOS-universal2`.

El workflow compila en `macos-13` (x86_64) y `macos-14` (arm64), fusiona binarios Mach-O con `lipo` y genera el DMG universal.

#### Opción B: Compilación local en macOS

```bash
./instalar_macos.sh --build
.venv/bin/python compilar_macos.py --target-arch universal2
```

Salida en `dist_macos/`. El modo `universal2` local requiere Python y dependencias/binarios compatibles con ambas arquitecturas; si falla, usa la opción A.

## Estructura del proyecto

```text
.
├── .github/workflows/build-macos.yml  # CI para build macOS
├── convertidor.py                     # Motor de conversión y CLI
├── interfaz.py                        # Interfaz gráfica Tkinter
├── compilar_exe.py                    # Build Windows
├── compilar_macos.py                  # Build macOS
├── instalador.iss                     # Script Inno Setup (Windows)
├── instalar.bat / instalar_macos.sh   # Instalación de dependencias
├── Convertidor.bat / Convertidor.command
├── consola.bat / consola_macos.command
├── requirements.txt
├── icono.ico / icono.icns
├── logo_bpt.png / logo_bpt_40.png
├── LEEME.txt / LEEME_PRIMERO.txt
└── README.md
```

## Archivos recomendados para GitHub

Para compilar en GitHub Actions (macOS) basta con incluir:

- `.github/workflows/build-macos.yml`
- `convertidor.py`, `interfaz.py`, `compilar_macos.py`
- `requirements.txt`
- `icono.icns`, `icono.ico`, `logo_bpt.png`, `logo_bpt_40.png`, `LEEME.txt`

No subas: `.venv/`, `__pycache__/`, `build/`, `build_macos/`, `dist/`, `dist_macos/`, `errores.log`.

## Solución de problemas

- **Faltan dependencias/Pillow**: ejecuta `instalar.bat` (Windows) o `./instalar_macos.sh` (macOS) y usa el lanzador del proyecto.
- **FFmpeg no encontrado**: en desarrollo reinstala dependencias; en paquete empaquetado vuelve a compilar/generar el artefacto.
- **No se lee HEIC/HEIF**: reinstala `pillow-heif` desde el script de instalación.
- **SmartScreen en Windows**: el ejecutable puede no estar firmado. Usa “Más información → Ejecutar de todas formas” solo si confías en el origen.
- **Gatekeeper en macOS**: para uso interno/pruebas, clic derecho → **Abrir**. Para distribución pública, firma y notariza.
- **Error en logs**: revisa `errores.log` (desarrollo) o la carpeta de datos de la app en modo empaquetado.

## Privacidad

BPT Converter procesa archivos localmente. La única conexión externa es la que realiza `yt-dlp` cuando el usuario solicita descargar/convertir una URL de YouTube.

## Contribuir

Las contribuciones son bienvenidas. Revisa [CONTRIBUTING.md](CONTRIBUTING.md) para el flujo de trabajo, comprobaciones básicas y guía para reportar bugs o proponer mejoras.

## Licencia

Este proyecto se distribuye bajo la licencia [MIT](LICENSE).
