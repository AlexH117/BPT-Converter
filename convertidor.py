#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BPT Converter (imagen, video y audio).

Uso con ventana:
    python convertidor.py --gui

Uso por consola:
    python convertidor.py foto.heic -f png
    python convertidor.py "C:\\fotos" -f jpg -r -o "C:\\salida"
    python convertidor.py video.mov -f mp4
    python convertidor.py cancion.m4a -f mp3
    python convertidor.py foto.jpg -f jpg --ancho 1600
    python convertidor.py video.mov -f mp4 --ancho 1280 --alto 720
    python convertidor.py --formatos
    python convertidor.py "https://www.youtube.com/watch?v=XXXXXXXXXXX" -f mp4 -o "C:\\Videos"
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

# --------------------------------------------------------------------------
# Dependencias (opcionales, se avisa si falta alguna)
# --------------------------------------------------------------------------

PIL_OK = False
try:
    from PIL import Image, ImageOps

    PIL_OK = True
except ImportError:
    Image = None  # type: ignore
    ImageOps = None  # type: ignore

HEIF_OK = False
if PIL_OK:
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        HEIF_OK = True
    except Exception:
        HEIF_OK = False

# Paquetes que necesita el programa (módulo de importación, nombre en pip)
REQUISITOS_APP = (
    ("PIL", "Pillow"),
    ("pillow_heif", "pillow-heif"),
    ("imageio_ffmpeg", "imageio-ffmpeg"),
)


def dependencias_faltantes() -> list[str]:
    """Devuelve los paquetes de pip que faltan en el intérprete actual."""
    if getattr(sys, "frozen", False):
        # En el .exe las librerías van empaquetadas dentro.
        return []
    faltan: list[str] = []
    for modulo, paquete in REQUISITOS_APP:
        try:
            encontrado = importlib.util.find_spec(modulo) is not None
        except (ImportError, ValueError):
            encontrado = False
        if not encontrado:
            faltan.append(paquete)
    return faltan


def _relanzar_desde_venv() -> None:
    """
    Si se abrió el .py con un Python sin las librerías, vuelve a lanzar el
    programa usando el Python del entorno .venv del proyecto.
    """
    if getattr(sys, "frozen", False):
        return
    if os.environ.get("CONVERTIDOR_RELANZADO") == "1":
        return
    if not dependencias_faltantes():
        return

    base = Path(__file__).resolve().parent
    es_windows = os.name == "nt"
    scripts = base / ".venv" / ("Scripts" if es_windows else "bin")
    if not scripts.is_dir():
        return

    argumentos = sys.argv[1:]
    quiere_gui = "--gui" in argumentos or not argumentos
    if es_windows:
        preferido = "pythonw.exe" if quiere_gui else "python.exe"
        candidatos = [scripts / preferido, scripts / "python.exe", scripts / "pythonw.exe"]
    else:
        # En macOS/Linux no existe pythonw; el intérprete del venv sirve para todo.
        preferido = "python3" if (scripts / "python3").exists() else "python"
        candidatos = [scripts / preferido, scripts / "python3", scripts / "python"]

    actual = Path(sys.executable)
    for candidato in candidatos:
        if not candidato.exists():
            continue
        try:
            if candidato.resolve() == actual.resolve():
                continue
        except OSError:
            pass
        entorno = os.environ.copy()
        entorno["CONVERTIDOR_RELANZADO"] = "1"
        try:
            subprocess.Popen(
                [str(candidato), str(Path(__file__).resolve()), *sys.argv[1:]],
                env=entorno,
                close_fds=True,
            )
        except OSError:
            continue
        raise SystemExit(0)

_FFMPEG: str | None = None


def obtener_ffmpeg() -> str:
    """Devuelve la ruta del ejecutable de FFmpeg (empaquetado, del PATH o del paquete pip)."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG

    # 1) En el .exe empaquetado, FFmpeg viaja junto al programa.
    if getattr(sys, "frozen", False):
        carpetas = []
        if hasattr(sys, "_MEIPASS"):
            carpetas.append(Path(sys._MEIPASS))
        carpetas.append(Path(sys.executable).resolve().parent)
        for carpeta in carpetas:
            for nombre in ("ffmpeg.exe", "ffmpeg"):
                ruta = carpeta / nombre
                if ruta.exists():
                    _FFMPEG = str(ruta)
                    return _FFMPEG

    # 2) FFmpeg instalado en el sistema (PATH).
    candidato = shutil.which("ffmpeg")

    # 3) Binario incluido por imageio-ffmpeg (modo desarrollo).
    if not candidato:
        try:
            import imageio_ffmpeg

            candidato = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            candidato = None
    if not candidato or not Path(candidato).exists():
        raise ErrorConversion(
            "No se encontró FFmpeg dentro del programa. Vuelve a instalar la "
            "aplicación o ejecuta 'instalar.bat' (Windows) / 'instalar_macos.sh' (macOS)."
        )
    _FFMPEG = candidato
    return candidato


# --------------------------------------------------------------------------
# Formatos y categorías
# --------------------------------------------------------------------------

FORMATOS_IMAGEN = {
    "JPG": ".jpg",
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "AVIF": ".avif",
    "TIFF": ".tiff",
    "BMP": ".bmp",
    "GIF": ".gif",
}

FORMATOS_VIDEO = {
    "MP4": ".mp4",
    "MOV": ".mov",
    "AVI": ".avi",
    "MKV": ".mkv",
    "WEBM": ".webm",
    "WMV": ".wmv",
    "FLV": ".flv",
    "MPEG": ".mpg",
}

FORMATOS_AUDIO = {
    "MP3": ".mp3",
    "WAV": ".wav",
    "M4A": ".m4a",
    "AAC": ".aac",
    "FLAC": ".flac",
    "OGG": ".ogg",
    "OPUS": ".opus",
}

FORMATOS_SALIDA: dict[str, str] = {}
FORMATOS_SALIDA.update(FORMATOS_IMAGEN)
FORMATOS_SALIDA.update(FORMATOS_VIDEO)
FORMATOS_SALIDA.update(FORMATOS_AUDIO)

EXTS_IMAGEN = {
    ".heic", ".heif", ".avif", ".jpg", ".jpeg", ".jpe", ".jfif", ".png",
    ".webp", ".bmp", ".dib", ".tif", ".tiff", ".gif", ".ico", ".ppm", ".pgm",
}
EXTS_VIDEO = {
    ".mov", ".qt", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".wmv", ".flv",
    ".mpg", ".mpeg", ".mpe", ".3gp", ".3g2", ".ts", ".mts", ".m2ts", ".ogv",
    ".vob", ".divx", ".asf",
}
EXTS_AUDIO = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wma",
    ".aiff", ".aif", ".alac", ".ape",
}

# Qué se puede convertir a qué
PERMITIDAS = {
    "imagen": {"imagen"},
    "video": {"video", "audio"},
    "audio": {"audio"},
}

PIL_FORMATO = {
    "JPG": "JPEG",
    "JPEG": "JPEG",
    "PNG": "PNG",
    "WEBP": "WEBP",
    "AVIF": "AVIF",
    "TIFF": "TIFF",
    "BMP": "BMP",
    "GIF": "GIF",
}


class ErrorConversion(Exception):
    """Error controlado durante una conversión."""


class ConversionCancelada(Exception):
    """El usuario canceló la conversión."""


def _log_consola(mensaje: str) -> None:
    if sys.stdout is not None:
        try:
            print(mensaje, flush=True)
        except Exception:
            pass


# --------------------------------------------------------------------------
# YouTube (descarga y conversión)
# --------------------------------------------------------------------------

_RE_URL_YOUTUBE = re.compile(
    r"^https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/",
    re.IGNORECASE,
)


def es_url_youtube(valor) -> bool:
    """Devuelve True si `valor` es una URL de YouTube (youtube.com o youtu.be)."""
    if isinstance(valor, Path):
        valor = str(valor)
    if not isinstance(valor, str):
        return False
    return bool(_RE_URL_YOUTUBE.match(valor.strip()))


def _nombre_seguro(titulo: str) -> str:
    """Limpia un título para usarlo como nombre de archivo."""
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(titulo or "")).strip()
    return nombre[:120]


def _hook_ytdlp(
    progreso: Callable[[float], None] | None,
    cancelado,
) -> Callable[[dict], None]:
    """Hook de progreso para yt-dlp (descarga del video)."""

    def hook(datos: dict) -> None:
        if cancelado is not None and cancelado.is_set():
            raise ConversionCancelada()
        estado = datos.get("status")
        if estado == "downloading":
            progreso_datos = datos.get("progress") or {}
            total = progreso_datos.get("total_bytes") or datos.get("total_bytes") or 0
            hecho = progreso_datos.get("downloaded_bytes") or datos.get("downloaded_bytes") or 0
            if progreso is not None and total > 0:
                progreso(min(99.0, hecho / total * 100.0))
        elif estado == "finished":
            if progreso is not None:
                progreso(99.0)

    return hook


def descargar_youtube(
    url: str,
    directorio_tmp: str | Path,
    *,
    audio_only: bool = False,
    progreso: Callable[[float], None] | None = None,
    cancelado=None,
    log: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    """
    Descarga un video (o audio) desde YouTube usando yt-dlp.

    Devuelve (ruta_local_del_descarga, titulo).
    """
    import yt_dlp  # import lazy: yt-dlp es una dependencia opcional

    log = log or _log_consola
    directorio = Path(directorio_tmp)
    directorio.mkdir(parents=True, exist_ok=True)

    # Misma resolución que en el resto de la app: empaquetado, PATH o imageio-ffmpeg.
    # En macOS el binario se llama "ffmpeg" (no "ffmpeg.exe").
    try:
        ffmpeg_path = obtener_ffmpeg()
    except Exception:
        ffmpeg_path = None

    error_descarga: Exception | None = None
    ruta_descarga: Path | None = None
    titulo = "youtube"
    formatos_a_probar = (
        ["bestaudio/best"]
        if audio_only
        else ["bestvideo*+bestaudio/best", "bestvideo/best"]
    )
    for fmt_seleccion in formatos_a_probar:
        ydl_opts: dict = {
            "outtmpl": str(directorio / "%(id)s.%(ext)s"),
            "format": fmt_seleccion,
            "progress_hooks": [_hook_ytdlp(progreso, cancelado)],
        }
        if ffmpeg_path and Path(ffmpeg_path).exists():
            ydl_opts["ffmpeg_location"] = ffmpeg_path
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                titulo = str(info.get("title") or "youtube")
            descargas = sorted(p for p in directorio.rglob("*") if p.is_file())
            if descargas:
                ruta_descarga = descargas[-1]
                break
        except ConversionCancelada:
            raise
        except Exception as exc:
            error_descarga = exc

    if ruta_descarga is None:
        detalle = f": {error_descarga}" if error_descarga is not None else ""
        raise ErrorConversion(f"No se pudo descargar el video de YouTube{detalle}.")
    return ruta_descarga, titulo


def convertir_url_youtube(
    url: str,
    destino_carpeta: str | Path,
    formato: str,
    *,
    progreso: Callable[[float], None] | None = None,
    cancelado=None,
    log: Callable[[str], None] | None = None,
    calidad: int = 90,
    crf: int = 23,
    ancho: int | None = None,
    alto: int | None = None,
    escala: float | None = None,
    ajustar: bool = True,
    no_ampliar: bool = False,
) -> Path:
    """
    Descarga un video desde YouTube (yt-dlp) y lo convierte al formato pedido.

    destino_carpeta : carpeta donde se guarda el archivo final (el nombre sale del título).
    """
    log = log or _log_consola
    fmt = "MP4" if normalizar_formato(formato) == "AUTO" else normalizar_formato(formato)
    if fmt not in FORMATOS_SALIDA:
        raise ErrorConversion(
            f"Formato de salida no soportado: {formato}. "
            f"Usa uno de: {', '.join(FORMATOS_SALIDA)}"
        )
    es_audio = categoria_formato(fmt) == "audio"

    carpeta = Path(destino_carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="convertidor_yt_") as td:
        ruta_descarga, titulo = descargar_youtube(
            url, td, audio_only=es_audio, progreso=progreso, cancelado=cancelado, log=log,
        )
        base = _nombre_seguro(titulo) or f"youtube_{Path(ruta_descarga).stem}"
        destino_final = carpeta / f"{base}{extension_de(fmt)}"
        if destino_final.exists():
            n = 1
            while True:
                candidato = carpeta / f"{base} ({n}){extension_de(fmt)}"
                if not candidato.exists():
                    destino_final = candidato
                    break
                n += 1
        _convertir_con_ffmpeg(
            ruta_descarga, destino_final, fmt,
            crf=crf, es_audio=es_audio,
            progreso=progreso, log=log, cancelado=cancelado,
            ancho=ancho, alto=alto, escala=escala, ajustar=ajustar, no_ampliar=no_ampliar,
        )
    return destino_final


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def normalizar_formato(formato: str) -> str:
    fmt = (formato or "").strip().upper().lstrip(".")
    if fmt == "JPE":
        fmt = "JPG"
    if fmt == "TIF":
        fmt = "TIFF"
    return fmt


def extension_de(formato: str) -> str:
    fmt = normalizar_formato(formato)
    if fmt not in FORMATOS_SALIDA:
        raise ErrorConversion(
            f"Formato de salida no soportado: {formato}. "
            f"Usa uno de: {', '.join(FORMATOS_SALIDA)}"
        )
    return FORMATOS_SALIDA[fmt]


def categoria_archivo(ruta: str | Path) -> str | None:
    ext = Path(ruta).suffix.lower()
    if ext in EXTS_IMAGEN:
        return "imagen"
    if ext in EXTS_VIDEO:
        return "video"
    if ext in EXTS_AUDIO:
        return "audio"
    return None


def categoria_formato(formato: str) -> str:
    fmt = normalizar_formato(formato)
    if fmt in FORMATOS_IMAGEN:
        return "imagen"
    if fmt in FORMATOS_VIDEO:
        return "video"
    if fmt in FORMATOS_AUDIO:
        return "audio"
    raise ErrorConversion(f"Formato desconocido: {formato}")


def formato_automatico(origen: str | Path) -> str:
    """Formato recomendado según el tipo de archivo (para -f auto)."""
    cat = categoria_archivo(origen)
    if cat == "imagen":
        return "JPG"
    if cat == "video":
        return "MP4"
    if cat == "audio":
        return "MP3"
    raise ErrorConversion(
        f"Extensión no soportada: '{Path(origen).suffix or '(sin extensión)'}'"
    )


def validar_conversion(origen: str | Path, formato: str) -> tuple[str, str]:
    """Comprueba que la conversión tenga sentido. Devuelve (formato, categoría_origen)."""
    origen = Path(origen)
    fmt = normalizar_formato(formato)
    if fmt == "AUTO":
        fmt = formato_automatico(origen)
    if fmt not in FORMATOS_SALIDA:
        raise ErrorConversion(f"Formato de salida no soportado: {formato}")

    cat = categoria_archivo(origen)
    if cat is None:
        raise ErrorConversion(
            f"Extensión no soportada: '{origen.suffix or '(sin extensión)'}'"
        )

    if cat == "imagen" and not PIL_OK:
        raise ErrorConversion("Falta Pillow. Ejecuta instalar.bat")
    if cat == "imagen" and origen.suffix.lower() in {".heic", ".heif", ".avif"} and not HEIF_OK:
        raise ErrorConversion(
            "Para leer HEIC/HEIF/AVIF hace falta 'pillow-heif'. Ejecuta instalar.bat"
        )

    # GIF se puede crear tanto desde imagen como desde vídeo
    if fmt == "GIF" and cat in {"imagen", "video"}:
        return fmt, cat

    cat_salida = categoria_formato(fmt)
    if cat_salida not in PERMITIDAS[cat]:
        validos = [
            f for f in FORMATOS_SALIDA
            if categoria_formato(f) in PERMITIDAS[cat] or (f == "GIF" and cat in {"imagen", "video"})
        ]
        raise ErrorConversion(
            f"No se puede convertir un archivo de {cat} a {fmt}. "
            f"Formatos válidos: {', '.join(sorted(validos))}"
        )
    return fmt, cat


def ruta_destino(
    origen: str | Path,
    carpeta: str | Path,
    formato: str,
    sobrescribir: bool = False,
) -> Path:
    """Calcula una ruta de salida libre (o la misma si se sobrescribe)."""
    origen = Path(origen)
    carpeta = Path(carpeta)
    ext = extension_de(formato)
    base = origen.stem
    candidato = carpeta / f"{base}{ext}"

    try:
        mismo = candidato.resolve() == origen.resolve()
    except OSError:
        mismo = False

    if mismo:
        candidato = carpeta / f"{base}_convertido{ext}"

    if not sobrescribir:
        n = 1
        while candidato.exists():
            candidato = carpeta / f"{base} ({n}){ext}"
            n += 1
    return candidato


def _a_segundos(partes) -> float:
    h, m, s = partes
    return int(h) * 3600 + int(m) * 60 + float(s)


_RE_DURACION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_RE_TIEMPO = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _mensaje_ffmpeg(detalle: str) -> str:
    bajo = detalle.lower()
    if "matches no streams" in bajo or "does not contain any stream" in bajo:
        return "El archivo no contiene una pista de audio que extraer."
    if "invalid data found" in bajo or "moov atom not found" in bajo:
        return "El archivo parece estar dañado o no es un vídeo válido."
    if "unknown encoder" in bajo:
        return "El códec necesario no está disponible en este FFmpeg."
    if "no space left" in bajo:
        return "No hay espacio suficiente en el disco de destino."
    return "FFmpeg falló al convertir el archivo.\n" + detalle


def _ejecutar_ffmpeg(
    cmd: list[str],
    *,
    progreso: Callable[[float], None] | None = None,
    cancelado=None,
) -> None:
    opciones: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    if os.name == "nt":
        # CREATE_NO_WINDOW solo existe en Windows.
        opciones["creationflags"] = 0x08000000

    try:
        proceso = subprocess.Popen(cmd, **opciones)
    except FileNotFoundError as exc:
        raise ErrorConversion("No se encontró FFmpeg en el sistema.") from exc

    duracion: float | None = None
    cola: collections.deque[str] = collections.deque(maxlen=60)

    assert proceso.stderr is not None
    try:
        for linea in proceso.stderr:
            cola.append(linea.rstrip())
            if duracion is None:
                m = _RE_DURACION.search(linea)
                if m:
                    try:
                        duracion = _a_segundos(m.groups())
                    except ValueError:
                        pass
            if progreso and duracion:
                m = _RE_TIEMPO.search(linea)
                if m:
                    try:
                        t = _a_segundos(m.groups())
                        if 0 <= t <= duracion * 1.05:
                            progreso(max(0.0, min(99.0, t / duracion * 100)))
                    except ValueError:
                        pass
            if cancelado is not None and cancelado.is_set():
                proceso.terminate()
                try:
                    proceso.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proceso.kill()
                raise ConversionCancelada()
    finally:
        try:
            proceso.stderr.close()
        except Exception:
            pass

    proceso.wait()
    if proceso.returncode != 0:
        detalle = "\n".join(list(cola)[-14:])
        raise ErrorConversion(_mensaje_ffmpeg(detalle))
    if progreso:
        progreso(100.0)


# --------------------------------------------------------------------------
# Imágenes
# --------------------------------------------------------------------------

def _preparar_imagen(im, fmt: str):
    """Adapta el modo de color al formato de destino."""
    if fmt in {"JPG", "JPEG", "BMP"}:
        tiene_alfa = im.mode in {"RGBA", "LA", "PA"} or (
            im.mode == "P" and "transparency" in im.info
        )
        if tiene_alfa:
            fondo = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            fondo.paste(rgba, mask=rgba.split()[-1])
            return fondo
        if im.mode != "RGB":
            return im.convert("RGB")

    if fmt == "GIF" and im.mode != "P":
        return im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=256)

    if fmt == "WEBP" and im.mode == "P":
        return im.convert("RGBA")

    if fmt in {"PNG", "WEBP", "AVIF", "TIFF", "GIF"}:
        if im.mode in {"CMYK", "YCbCr", "LAB", "HSV", "I", "F", "I;16", "I;16B", "I;16L"}:
            return im.convert("RGB")

    return im


def _guardar_imagen(im, destino: Path, fmt: str, calidad: int, exif, icc) -> None:
    destino = Path(destino)
    params: dict = {}

    if fmt in {"JPG", "JPEG"}:
        params = {
            "quality": max(1, min(100, calidad)),
            "optimize": True,
            "progressive": True,
            "subsampling": 0 if calidad >= 90 else 2,
        }
    elif fmt == "PNG":
        params = {"optimize": True, "compress_level": 7}
    elif fmt == "WEBP":
        params = {"quality": max(1, min(100, calidad)), "method": 6}
    elif fmt == "AVIF":
        params = {"quality": max(1, min(100, calidad))}
    elif fmt == "TIFF":
        params = {"compression": "tiff_lzw"}
    elif fmt == "GIF":
        params = {"optimize": True}

    if exif and fmt in {"JPG", "JPEG", "PNG", "WEBP", "TIFF"}:
        params["exif"] = exif
    if icc and fmt in {"JPG", "JPEG", "PNG", "WEBP", "TIFF"}:
        params["icc_profile"] = icc

    try:
        im.save(destino, format=PIL_FORMATO[fmt], **params)
    except (OSError, TypeError, ValueError):
        # Algunos metadatos no encajan en ciertos formatos: reintenta sin ellos
        params.pop("exif", None)
        params.pop("icc_profile", None)
        im.save(destino, format=PIL_FORMATO[fmt], **params)


def _tamano_redimensionado(
    tamano: tuple[int, int],
    ancho: int | None,
    alto: int | None,
    escala: float | None,
    ajustar: bool,
    no_ampliar: bool,
) -> tuple[int, int]:
    """Calcula el tamaño final de una imagen conservando la proporción si hace falta."""
    w0, h0 = tamano
    if w0 < 1 or h0 < 1:
        return w0, h0

    if escala is not None:
        factor = float(escala) / 100.0
        nuevo_w, nuevo_h = w0 * factor, h0 * factor
    elif ajustar:
        if ancho and alto:
            factor = min(ancho / w0, alto / h0)
        elif ancho:
            factor = ancho / w0
        elif alto:
            factor = alto / h0
        else:
            return w0, h0
        if no_ampliar:
            factor = min(factor, 1.0)
        nuevo_w, nuevo_h = w0 * factor, h0 * factor
    else:
        nuevo_w = ancho or w0
        nuevo_h = alto or h0
        if no_ampliar:
            nuevo_w = min(nuevo_w, w0)
            nuevo_h = min(nuevo_h, h0)

    return max(1, round(nuevo_w)), max(1, round(nuevo_h))


def _convertir_imagen(
    origen: Path,
    destino: Path,
    fmt: str,
    calidad: int,
    progreso: Callable[[float], None] | None,
    log: Callable[[str], None],
    ancho: int | None = None,
    alto: int | None = None,
    escala: float | None = None,
    ajustar: bool = True,
    no_ampliar: bool = False,
) -> None:
    if not PIL_OK:
        raise ErrorConversion(
            "Falta la librería Pillow en el Python que está ejecutando el programa.\n"
            f"  Intérprete: {sys.executable}\n"
            "Abre «Convertidor.bat» o ejecuta «instalar.bat»."
        )
    if fmt == "AVIF" and not HEIF_OK:
        raise ErrorConversion(
            "Para crear AVIF hace falta 'pillow-heif'. Ejecuta «instalar.bat»."
        )

    try:
        with Image.open(origen) as abierta:
            abierta.load()
            try:
                im = ImageOps.exif_transpose(abierta)
            except Exception:
                im = abierta.copy()

            exif = None
            try:
                datos = im.getexif()
                if len(datos):
                    exif = datos.tobytes()
            except Exception:
                exif = None
            icc = None
            try:
                icc = im.info.get("icc_profile")
            except Exception:
                pass

            if ancho or alto or escala:
                nuevo_tamano = _tamano_redimensionado(
                    im.size, ancho, alto, escala, ajustar, no_ampliar
                )
                if nuevo_tamano != im.size:
                    redimensionada = im.resize(nuevo_tamano, Image.Resampling.LANCZOS)
                    if im is not abierta:
                        im.close()
                    im = redimensionada

            preparada = _preparar_imagen(im, fmt)
            try:
                _guardar_imagen(preparada, destino, fmt, calidad, exif, icc)
            finally:
                if preparada is not im and preparada is not abierta:
                    preparada.close()
                if im is not abierta:
                    im.close()
    except ErrorConversion:
        raise
    except Image.UnidentifiedImageError as exc:
        raise ErrorConversion("No se pudo leer la imagen: formato no reconocido o dañado.") from exc
    except OSError as exc:
        raise ErrorConversion(f"Error al leer o escribir la imagen: {exc}") from exc

    if progreso:
        progreso(100.0)


# --------------------------------------------------------------------------
# Vídeo y audio
# --------------------------------------------------------------------------

def _filtro_escala(
    ancho: int | None,
    alto: int | None,
    escala: float | None,
    ajustar: bool,
    no_ampliar: bool,
) -> str | None:
    """Devuelve el filtro 'scale' de FFmpeg o None si no hay que redimensionar."""
    if escala is not None:
        # Porcentaje manteniendo proporción; ancho par para yuv420p
        return f"scale=trunc(iw*{escala}/100/2)*2:-2:flags=lanczos"

    if not ancho and not alto:
        return None

    if ajustar:
        if ancho and alto:
            if no_ampliar:
                return (
                    f"scale=w='min({ancho},iw)':h='min({alto},ih)':"
                    "force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos"
                )
            return (
                f"scale={ancho}:{alto}:force_original_aspect_ratio=decrease:"
                "force_divisible_by=2:flags=lanczos"
            )
        if ancho:
            return f"scale={ancho}:-2:flags=lanczos"
        return f"scale=-2:{alto}:flags=lanczos"

    # Dimensiones exactas (puede deformar si la proporción no coincide)
    w = max(2, int(ancho) // 2 * 2) if ancho else -2
    h = max(2, int(alto) // 2 * 2) if alto else -2
    return f"scale={w}:{h}:flags=lanczos"


def _comando_video(
    origen: Path,
    destino: Path,
    fmt: str,
    crf: int,
    ancho: int | None = None,
    alto: int | None = None,
    escala: float | None = None,
    ajustar: bool = True,
    no_ampliar: bool = False,
) -> list[str]:
    ff = obtener_ffmpeg()
    cmd = [ff, "-hide_banner", "-nostdin", "-y", "-i", str(origen)]
    fmt = normalizar_formato(fmt)
    filtro_escala = _filtro_escala(ancho, alto, escala, ajustar, no_ampliar)

    if fmt == "GIF":
        escalado = filtro_escala or "scale='min(960,iw)':-2:flags=lanczos"
        filtro = (
            f"fps=12,{escalado},"
            "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];"
            "[s1][p]paletteuse=dither=bayer:bayer_scale=3"
        )
        cmd += ["-vf", filtro, "-loop", "0", "-an"]
    elif fmt in {"MP4", "MOV"}:
        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
        ]
    elif fmt == "MKV":
        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        ]
    elif fmt == "AVI":
        cmd += [
            "-c:v", "mpeg4", "-qscale:v", "4", "-pix_fmt", "yuv420p",
            "-c:a", "libmp3lame", "-b:a", "192k",
        ]
    elif fmt == "WEBM":
        cmd += [
            "-c:v", "libvpx-vp9", "-crf", str(min(63, crf + 9)), "-b:v", "0",
            "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k",
        ]
    elif fmt == "WMV":
        cmd += ["-c:v", "wmv2", "-b:v", "5M", "-c:a", "wmav2", "-b:a", "192k"]
    elif fmt == "FLV":
        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        ]
    elif fmt == "MPEG":
        cmd += ["-c:v", "mpeg2video", "-qscale:v", "5", "-c:a", "mp2", "-b:a", "192k"]
    else:
        raise ErrorConversion(f"Formato de vídeo no soportado: {fmt}")

    if fmt != "GIF" and filtro_escala:
        cmd += ["-vf", filtro_escala]

    cmd += ["-map_metadata", "0", str(destino)]
    return cmd


CODIFICADORES_AUDIO = {
    "MP3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "WAV": ["-c:a", "pcm_s16le"],
    "M4A": ["-c:a", "aac", "-b:a", "192k"],
    "AAC": ["-c:a", "aac", "-b:a", "192k"],
    "FLAC": ["-c:a", "flac"],
    "OGG": ["-c:a", "libvorbis", "-q:a", "5"],
    "OPUS": ["-c:a", "libopus", "-b:a", "128k"],
}


def _comando_audio(origen: Path, destino: Path, fmt: str) -> list[str]:
    ff = obtener_ffmpeg()
    fmt = normalizar_formato(fmt)
    if fmt not in CODIFICADORES_AUDIO:
        raise ErrorConversion(f"Formato de audio no soportado: {fmt}")
    cmd = [
        ff, "-hide_banner", "-nostdin", "-y", "-i", str(origen),
        "-vn", "-map", "0:a:0",
    ]
    cmd += CODIFICADORES_AUDIO[fmt]
    cmd += ["-map_metadata", "0", str(destino)]
    return cmd


def _convertir_con_ffmpeg(
    origen: Path,
    destino: Path,
    fmt: str,
    *,
    crf: int,
    es_audio: bool,
    progreso: Callable[[float], None] | None,
    log: Callable[[str], None],
    cancelado,
    ancho: int | None = None,
    alto: int | None = None,
    escala: float | None = None,
    ajustar: bool = True,
    no_ampliar: bool = False,
) -> None:
    cmd = (
        _comando_audio(origen, destino, fmt)
        if es_audio
        else _comando_video(
            origen, destino, fmt, crf,
            ancho=ancho, alto=alto, escala=escala,
            ajustar=ajustar, no_ampliar=no_ampliar,
        )
    )
    log(f"FFmpeg: {origen.name} -> {destino.name}")
    _ejecutar_ffmpeg(cmd, progreso=progreso, cancelado=cancelado)

    if not destino.exists() or destino.stat().st_size == 0:
        raise ErrorConversion("La conversión terminó pero el archivo de salida está vacío.")


# --------------------------------------------------------------------------
# API principal
# --------------------------------------------------------------------------

def convertir_archivo(
    origen: str | Path,
    destino: str | Path,
    formato: str,
    *,
    calidad: int = 90,
    crf: int = 23,
    ancho: int | None = None,
    alto: int | None = None,
    escala: float | None = None,
    ajustar: bool = True,
    no_ampliar: bool = False,
    progreso: Callable[[float], None] | None = None,
    log: Callable[[str], None] | None = None,
    cancelado=None,
) -> Path:
    """
    Convierte un archivo.

    origen    : ruta del archivo original
    destino   : ruta final (incluye nombre y extensión)
    formato   : JPG, PNG, MP4, AVI, MP3...
    calidad   : 1-100 para imágenes
    crf       : 0-51 para vídeo (menor = mejor calidad)
    ancho     : ancho de salida en píxeles (opcional)
    alto      : alto de salida en píxeles (opcional)
    escala    : porcentaje de escala, p. ej. 50 (opcional)
    ajustar   : True conserva la proporción; False fuerza ancho×alto exactos
    no_ampliar: True evita agrandar archivos que ya son más pequeños
    progreso  : callback con porcentaje 0-100
    cancelado : threading.Event opcional
    """
    log = log or _log_consola
    if isinstance(origen, str) and es_url_youtube(origen):
        # Flujo especial: descargar desde YouTube y convertir.
        return convertir_url_youtube(
            origen, destino, formato,
            progreso=progreso, cancelado=cancelado, log=log,
            calidad=calidad, crf=crf, ancho=ancho, alto=alto,
            escala=escala, ajustar=ajustar, no_ampliar=no_ampliar,
        )
    origen = Path(origen)
    destino = Path(destino)
    fmt, cat = validar_conversion(origen, formato)

    if not origen.exists() or not origen.is_file():
        raise ErrorConversion("El archivo de origen no existe.")
    if escala is not None and escala <= 0:
        raise ErrorConversion("El porcentaje de escala debe ser mayor que 0.")
    if (ancho is not None and ancho < 1) or (alto is not None and alto < 1):
        raise ErrorConversion("El ancho y el alto deben ser mayores que 0.")

    try:
        if destino.resolve() == origen.resolve():
            raise ErrorConversion("El archivo de destino no puede ser el mismo que el de origen.")
    except OSError:
        pass

    destino.parent.mkdir(parents=True, exist_ok=True)
    if cancelado is not None and cancelado.is_set():
        raise ConversionCancelada()

    try:
        if cat == "imagen":
            _convertir_imagen(
                origen, destino, fmt, calidad, progreso, log,
                ancho=ancho, alto=alto, escala=escala,
                ajustar=ajustar, no_ampliar=no_ampliar,
            )
        elif fmt in FORMATOS_AUDIO:
            _convertir_con_ffmpeg(
                origen, destino, fmt,
                crf=crf, es_audio=True,
                progreso=progreso, log=log, cancelado=cancelado,
            )
        else:
            _convertir_con_ffmpeg(
                origen, destino, fmt,
                crf=crf, es_audio=False,
                progreso=progreso, log=log, cancelado=cancelado,
                ancho=ancho, alto=alto, escala=escala,
                ajustar=ajustar, no_ampliar=no_ampliar,
            )
    except BaseException:
        # No dejar archivos a medio escribir
        try:
            if destino.exists() and destino != origen:
                destino.unlink()
        except OSError:
            pass
        raise

    return destino


def _recolectar(rutas: list[str], recursivo: bool) -> list[Path]:
    archivos: list[Path] = []
    for ruta in rutas:
        p = Path(ruta).expanduser()
        if p.is_dir():
            patron = "**/*" if recursivo else "*"
            archivos.extend(sorted(x for x in p.glob(patron) if x.is_file()))
        elif p.is_file():
            archivos.append(p)
        else:
            _log_consola(f"! No encontrado: {p}")
    # Quitar duplicados conservando el orden
    vistos: set[str] = set()
    unicos: list[Path] = []
    for a in archivos:
        clave = str(a.resolve()).lower()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(a)
    return unicos


def imprimir_formatos() -> None:
    print("Formatos de salida disponibles\n")
    print("  Imagen : " + " | ".join(FORMATOS_IMAGEN))
    print("  Vídeo  : " + " | ".join(FORMATOS_VIDEO))
    print("  Audio  : " + " | ".join(FORMATOS_AUDIO))
    print("\n  AUTO   : JPG para imágenes, MP4 para vídeos, MP3 para audio")
    print("\nEntradas de imagen: " + ", ".join(sorted(EXTS_IMAGEN)))
    print("Entradas de vídeo : " + ", ".join(sorted(EXTS_VIDEO)))
    print("Entradas de audio : " + ", ".join(sorted(EXTS_AUDIO)))


# --------------------------------------------------------------------------
# Consola
# --------------------------------------------------------------------------

def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="convertidor",
        description="Convierte imágenes (HEIC, JPG, PNG...), vídeo (MOV, MP4, AVI...) y audio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python convertidor.py --gui\n"
            "  python convertidor.py foto.heic -f png\n"
            '  python convertidor.py "C:\\fotos" -f jpg -r -o "C:\\salida"\n'
            "  python convertidor.py video.mov -f mp4\n"
            "  python convertidor.py foto.jpg -f jpg --ancho 1600\n"
            "  python convertidor.py video.mov -f mp4 --ancho 1280 --alto 720\n"
            "  python convertidor.py fotos/ -f jpg --porcentaje 50 -r\n"
            "  python convertidor.py \"https://www.youtube.com/watch?v=XXXXXXXXXXX\" -f mp4 -o salida\n"
        ),
    )
    p.add_argument("rutas", nargs="*", help="Archivos o carpetas de entrada")
    p.add_argument("-f", "--formato", help="Formato de salida (JPG, PNG, MP4, MP3... o AUTO)")
    p.add_argument("-o", "--destino", help="Carpeta de salida (por defecto, junto al original)")
    p.add_argument("-r", "--recursivo", action="store_true", help="Incluir subcarpetas")
    p.add_argument("--calidad", type=int, default=90, help="Calidad de imagen 1-100 (por defecto 90)")
    p.add_argument("--crf", type=int, default=23, help="Calidad de vídeo 0-51, menor = mejor (por defecto 23)")
    p.add_argument("--ancho", type=int, help="Ancho de salida en píxeles")
    p.add_argument("--alto", type=int, help="Alto de salida en píxeles")
    p.add_argument("--porcentaje", type=float, help="Escalar al porcentaje indicado (ej. 50)")
    p.add_argument("--exacto", action="store_true", help="Forzar ancho×alto exactos (puede deformar)")
    p.add_argument("--no-ampliar", action="store_true", help="No agrandar archivos que ya son pequeños")
    p.add_argument("--sobrescribir", action="store_true", help="Sobrescribir archivos existentes")
    p.add_argument("--gui", action="store_true", help="Abrir la interfaz gráfica")
    p.add_argument("--formatos", action="store_true", help="Mostrar formatos soportados")
    p.add_argument("--version", action="store_true", help="Mostrar la versión")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)

    if args.version:
        print("BPT Converter 1.2")
        return 0

    if args.formatos:
        imprimir_formatos()
        return 0

    if args.gui or not args.rutas:
        from interfaz import iniciar

        iniciar()
        return 0

    if not args.formato:
        print("ERROR: falta el formato de salida. Usa -f JPG, -f MP4, ...", file=sys.stderr)
        return 2

    fmt = normalizar_formato(args.formato)
    if fmt != "AUTO" and fmt not in FORMATOS_SALIDA:
        print(f"ERROR: formato no soportado: {args.formato}", file=sys.stderr)
        imprimir_formatos()
        return 2

    urls = [r for r in args.rutas if es_url_youtube(r)]
    if urls:
        if len(urls) > 1:
            print("ERROR: solo se admite una URL de YouTube por ejecución.", file=sys.stderr)
            return 2
        url = urls[0]
        carpeta = Path(args.destino) if args.destino else Path.cwd()
        print(f"Descargando {url} y convirtiendo a {args.formato} ...")
        try:
            final = convertir_url_youtube(
                url, carpeta, args.formato,
                progreso=None, cancelado=None, log=lambda m: print(m),
            )
        except ErrorConversion as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"\nListo: {final}")
        return 0

    archivos = _recolectar(args.rutas, args.recursivo)
    if not archivos:
        print("No se encontraron archivos para convertir.", file=sys.stderr)
        return 1

    if args.porcentaje is not None and args.porcentaje <= 0:
        print("ERROR: --porcentaje debe ser mayor que 0.", file=sys.stderr)
        return 2
    if (args.ancho is not None and args.ancho < 1) or (args.alto is not None and args.alto < 1):
        print("ERROR: --ancho y --alto deben ser mayores que 0.", file=sys.stderr)
        return 2
    if args.porcentaje is not None and (args.ancho is not None or args.alto is not None):
        print("ERROR: usa --porcentaje o --ancho/--alto, no ambos a la vez.", file=sys.stderr)
        return 2

    total = len(archivos)
    exitos = 0
    fallos = 0

    for i, origen in enumerate(archivos, 1):
        try:
            fmt_archivo, _cat = validar_conversion(origen, fmt)
        except ErrorConversion as exc:
            print(f"[{i}/{total}] OMITIDO {origen.name}: {exc}", file=sys.stderr)
            fallos += 1
            continue

        carpeta = Path(args.destino) if args.destino else origen.parent
        destino = ruta_destino(origen, carpeta, fmt_archivo, args.sobrescribir)

        print(f"[{i}/{total}] {origen.name} -> {destino.name}")
        try:
            convertir_archivo(
                origen,
                destino,
                fmt_archivo,
                calidad=args.calidad,
                crf=args.crf,
                ancho=args.ancho,
                alto=args.alto,
                escala=args.porcentaje,
                ajustar=not args.exacto,
                no_ampliar=args.no_ampliar,
                log=lambda m: None,
            )
            exitos += 1
        except ErrorConversion as exc:
            print(f"    ERROR: {exc}", file=sys.stderr)
            fallos += 1
        except KeyboardInterrupt:
            print("\nCancelado por el usuario.", file=sys.stderr)
            return 130

    print(f"\nListo: {exitos} convertido(s), {fallos} con error.")
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    _relanzar_desde_venv()
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
