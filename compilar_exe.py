#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compila la aplicación de Windows y el instalador.

Uso:
    .venv\\Scripts\\python.exe compilar_exe.py

Genera:
    dist\\ConvertidorFormatos\\            aplicación instalable (onedir)
    dist\\ConvertidorFormatos_Portable.exe aplicación portable (un solo .exe)
    dist\\Instalador_ConvertidorFormatos_1.2.exe  instalador oficial
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DIST = BASE / "dist"
BUILD = BASE / "build"
NOMBRE_APP = "ConvertidorFormatos"
NOMBRE_PORTABLE = "ConvertidorFormatos_Portable"
VERSION = "1.2"


def _ejecutar(cmd: list[str]) -> None:
    print("\n>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=BASE, check=True)


def _ffmpeg() -> Path:
    try:
        import imageio_ffmpeg

        ruta = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as exc:  # pragma: no cover - solo compilación
        raise SystemExit(
            "No se encontró FFmpeg. Instala las dependencias con instalar.bat."
        ) from exc
    if not ruta.exists():
        raise SystemExit(f"No existe el binario de FFmpeg: {ruta}")
    return ruta


def _argumentos_comunes(ffmpeg: Path) -> list[str]:
    sep = os.pathsep  # ';' en Windows
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--icon",
        str(BASE / "icono.ico"),
        "--version-file",
        str(BASE / "version_info.txt"),
        "--add-binary",
        f"{ffmpeg}{sep}.",
        "--add-data",
        f"{BASE / 'icono.ico'}{sep}.",
        "--add-data",
        f"{BASE / 'logo_bpt_40.png'}{sep}.",
        "--add-data",
        f"{BASE / 'LEEME.txt'}{sep}.",
        "--collect-all",
        "pillow_heif",
        "--collect-all",
        "tkinterdnd2",
        "--collect-all",
        "yt_dlp",
        "--hidden-import",
        "interfaz",
        "--exclude-module",
        "imageio_ffmpeg",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--log-level",
        "WARN",
    ]


def compilar(ffmpeg: Path, *, portable: bool) -> None:
    nombre = NOMBRE_PORTABLE if portable else NOMBRE_APP
    args = _argumentos_comunes(ffmpeg)
    args += ["--name", nombre]
    if portable:
        args += ["--onefile"]
    else:
        args += ["--onedir"]
    args += [str(BASE / "convertidor.py")]
    _ejecutar(args)


def _buscar_iscc() -> Path | None:
    candidatos = [
        os.environ.get("ISCC"),
        shutil.which("ISCC"),
        shutil.which("iscc"),
        str(
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Antigravity IDE"
            / "resources"
            / "app"
            / "node_modules"
            / "innosetup"
            / "bin"
            / "ISCC.exe"
        ),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for candidato in candidatos:
        if candidato and Path(candidato).exists():
            return Path(candidato)
    return None


def compilar_instalador() -> Path | None:
    iscc = _buscar_iscc()
    if iscc is None:
        print(
            "\nAVISO: no se encontró Inno Setup (ISCC.exe). "
            "La aplicación se compiló, pero no se generó el instalador."
        )
        return None
    _ejecutar([str(iscc), str(BASE / "instalador.iss")])
    return DIST / f"Instalador_ConvertidorFormatos_{VERSION}.exe"


def _tamano_mb(ruta: Path) -> str:
    if ruta.is_file():
        total = ruta.stat().st_size
    else:
        total = sum(p.stat().st_size for p in ruta.rglob("*") if p.is_file())
    return f"{total / 1024 / 1024:.1f} MB"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "Falta PyInstaller. Instálalo con:\n"
            f'  "{sys.executable}" -m pip install pyinstaller',
            file=sys.stderr,
        )
        return 1

    ffmpeg = _ffmpeg()
    print(f"FFmpeg: {ffmpeg} ({_tamano_mb(ffmpeg)})")

    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    DIST.mkdir(parents=True)
    BUILD.mkdir(parents=True)

    # FFmpeg debe llamarse exactamente "ffmpeg.exe" dentro del paquete.
    assets = BUILD / "assets"
    assets.mkdir()
    ffmpeg_empaquetado = assets / "ffmpeg.exe"
    shutil.copy2(ffmpeg, ffmpeg_empaquetado)
    ffmpeg = ffmpeg_empaquetado

    print("\n=== 1/3 · Aplicación instalable (onedir) ===")
    compilar(ffmpeg, portable=False)
    shutil.copy2(BASE / "README.md", DIST / NOMBRE_APP / "README.md")
    shutil.copy2(BASE / "LEEME.txt", DIST / NOMBRE_APP / "LEEME.txt")

    print("\n=== 2/3 · Aplicación portable (onefile) ===")
    compilar(ffmpeg, portable=True)

    print("\n=== 3/3 · Instalador ===")
    instalador = compilar_instalador()

    shutil.rmtree(assets, ignore_errors=True)

    print("\n=== RESULTADO ===")
    print(f"  Carpeta instalable : {DIST / NOMBRE_APP} ({_tamano_mb(DIST / NOMBRE_APP)})")
    portable = DIST / f"{NOMBRE_PORTABLE}.exe"
    if portable.exists():
        print(f"  Portable           : {portable} ({_tamano_mb(portable)})")
    if instalador and instalador.exists():
        print(f"  Instalador         : {instalador} ({_tamano_mb(instalador)})")
    else:
        print("  Instalador         : no generado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
