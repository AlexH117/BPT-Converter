#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compila BPT Converter para macOS con PyInstaller.

Uso (en macOS):
    .venv/bin/python compilar_macos.py
    .venv/bin/python compilar_macos.py --target-arch universal2

Genera:
    dist_macos/BPT Converter.app
    dist_macos/BPTConverter_Portable
    dist_macos/BPTConverter-macOS-<arch>.dmg

Notas:
- PyInstaller no puede compilar para macOS desde Windows/Linux.
- `universal2` requiere un Python universal2 y dependencias/binaries compatibles.
  Si no es viable en un solo host, usa el workflow de GitHub Actions que construye
  arm64 + x86_64 y fusiona con lipo.
- Para distribución pública se recomienda firmar y notarizar en macOS.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DIST = BASE / "dist_macos"
BUILD = BASE / "build_macos"
NOMBRE_APP = "BPT Converter"
NOMBRE_PORTABLE = "BPTConverter_Portable"
VERSION = "1.2"
BUNDLE_ID = "com.bpt.converter"
ARQUITECTURAS_VALIDAS = {"auto", "arm64", "x86_64", "universal2"}


def _ejecutar(cmd: list[str]) -> None:
    print("\n>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=BASE, check=True)


def _ffmpeg() -> Path:
    try:
        import imageio_ffmpeg

        ruta = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as exc:  # pragma: no cover - solo compilación
        raise SystemExit(
            "No se encontró FFmpeg. Instala las dependencias con instalar_macos.sh."
        ) from exc
    if not ruta.exists():
        raise SystemExit(f"No existe el binario de FFmpeg: {ruta}")
    return ruta


def _icono() -> Path:
    # Preferimos .icns; si no existe, PyInstaller puede recibir .png en algunas versiones,
    # pero .icns es el formato correcto para .app.
    icns = BASE / "icono.icns"
    if icns.exists():
        return icns
    ico = BASE / "icono.ico"
    if ico.exists():
        return ico
    raise SystemExit("No se encontró icono.icns ni icono.ico.")


def _normalizar_arquitectura(valor: str) -> str:
    arch = (valor or "auto").strip().lower()
    if arch not in ARQUITECTURAS_VALIDAS:
        raise SystemExit(
            f"Arquitectura no válida: {valor}. Usa: {', '.join(sorted(ARQUITECTURAS_VALIDAS))}"
        )
    if arch == "auto":
        machine = platform.machine().lower()
        if machine in {"x86_64", "amd64"}:
            return "x86_64"
        if machine in {"arm64", "aarch64"}:
            return "arm64"
        return machine or "arm64"
    return arch


def _args_target_arch(arch: str) -> list[str]:
    # PyInstaller espera universal2 para binarios universales en macOS.
    if arch in {"arm64", "x86_64", "universal2"}:
        return ["--target-arch", arch]
    return []


def _argumentos_comunes(ffmpeg: Path, arch: str) -> list[str]:
    sep = ":"  # macOS/Linux PyInstaller usa ':' en --add-data/--add-binary
    icono = _icono()
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        NOMBRE_APP,
        "--icon",
        str(icono),
        "--osx-bundle-identifier",
        BUNDLE_ID,
        *_args_target_arch(arch),
        "--add-binary",
        f"{ffmpeg}{sep}.",
        "--add-data",
        f"{BASE / 'icono.ico'}{sep}.",
        "--add-data",
        f"{BASE / 'logo_bpt_40.png'}{sep}.",
        "--add-data",
        f"{BASE / 'logo_bpt.png'}{sep}.",
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
    return args


def compilar_app(ffmpeg: Path, arch: str) -> Path:
    args = _argumentos_comunes(ffmpeg, arch)
    args += ["--onedir", str(BASE / "convertidor.py")]
    _ejecutar(args)
    app = DIST / f"{NOMBRE_APP}.app"
    if not app.exists():
        # PyInstaller a veces deja la carpeta onedir con el nombre; normalizamos a .app
        onedir = DIST / NOMBRE_APP
        if onedir.exists():
            destino = DIST / f"{NOMBRE_APP}-onedir"
            if destino.exists():
                shutil.rmtree(destino)
            onedir.rename(destino)
            print(f"AVISO: no se generó .app, queda carpeta en {destino}")
            return destino
    return app


def compilar_portable(ffmpeg: Path, arch: str) -> Path:
    sep = ":"
    icono = _icono()
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        NOMBRE_PORTABLE,
        "--icon",
        str(icono),
        *_args_target_arch(arch),
        "--add-binary",
        f"{ffmpeg}{sep}.",
        "--add-data",
        f"{BASE / 'icono.ico'}{sep}.",
        "--add-data",
        f"{BASE / 'logo_bpt_40.png'}{sep}.",
        "--add-data",
        f"{BASE / 'logo_bpt.png'}{sep}.",
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
        str(BASE / "convertidor.py"),
    ]
    _ejecutar(args)
    return DIST / NOMBRE_PORTABLE


def crear_dmg(app: Path, arch: str) -> Path | None:
    if shutil.which("hdiutil") is None:
        print("AVISO: hdiutil no disponible; no se generó DMG.")
        return None
    if not app.exists() or not app.is_dir():
        print("AVISO: no hay .app para empaquetar en DMG.")
        return None

    sufijo = arch or platform.machine().lower()
    dmg_tmp = DIST / f"BPTConverter-{VERSION}-macOS-{sufijo}.tmp.dmg"
    dmg_final = DIST / f"BPTConverter-{VERSION}-macOS-{sufijo}.dmg"
    staging = BUILD / "dmg-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(app, staging / app.name)
    # Acceso directo a /Applications para arrastrar y soltar.
    aplicaciones = staging / "Applications"
    try:
        if not aplicaciones.exists():
            aplicaciones.symlink_to("/Applications")
    except OSError:
        pass

    for ruta in (dmg_tmp, dmg_final):
        if ruta.exists():
            ruta.unlink()

    _ejecutar([
        "hdiutil", "create",
        "-volname", NOMBRE_APP,
        "-srcfolder", str(staging),
        "-ov",
        "-format", "UDZO",
        str(dmg_final),
    ])
    shutil.rmtree(staging, ignore_errors=True)
    return dmg_final


def _tamano_mb(ruta: Path) -> str:
    if ruta.is_file():
        total = ruta.stat().st_size
    else:
        total = sum(p.stat().st_size for p in ruta.rglob("*") if p.is_file())
    return f"{total / 1024 / 1024:.1f} MB"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compila BPT Converter para macOS")
    parser.add_argument(
        "--target-arch",
        default=os.environ.get("BPT_TARGET_ARCH", "auto"),
        choices=sorted(ARQUITECTURAS_VALIDAS),
        help="Arquitectura destino de PyInstaller: auto, arm64, x86_64 o universal2.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    arch = _normalizar_arquitectura(args.target_arch)

    if sys.platform != "darwin":
        print(
            "AVISO: este script está pensado para ejecutarse en macOS. "
            "PyInstaller no genera apps de macOS desde Windows/Linux. "
            "Puedes usarlo en GitHub Actions con runner macOS.",
            file=sys.stderr,
        )
        # No salimos con error duro: permite validar sintaxis o preparar CI.
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
    print(f"Arquitectura Python: {platform.machine()}")
    print(f"Arquitectura destino: {arch}")

    if arch == "universal2":
        print(
            "AVISO: universal2 requiere Python/dependencias/binarios universal2. "
            "Si la compilación falla por dependencias single-arch, usa el workflow "
            "de GitHub Actions que fusiona arm64+x86_64 con lipo."
        )

    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    DIST.mkdir(parents=True)
    BUILD.mkdir(parents=True)

    # FFmpeg debe llamarse "ffmpeg" dentro del paquete en macOS.
    assets = BUILD / "assets"
    assets.mkdir()
    ffmpeg_empaquetado = assets / "ffmpeg"
    shutil.copy2(ffmpeg, ffmpeg_empaquetado)
    try:
        ffmpeg_empaquetado.chmod(0o755)
    except OSError:
        pass

    print("\n=== 1/3 · Aplicación .app ===")
    app = compilar_app(ffmpeg_empaquetado, arch)

    print("\n=== 2/3 · Binario portable ===")
    portable = compilar_portable(ffmpeg_empaquetado, arch)

    print("\n=== 3/3 · DMG ===")
    dmg = crear_dmg(app, arch)

    shutil.rmtree(assets, ignore_errors=True)

    print("\n=== RESULTADO ===")
    if app.exists():
        print(f"  App        : {app} ({_tamano_mb(app)})")
    if portable.exists():
        print(f"  Portable   : {portable} ({_tamano_mb(portable)})")
    if dmg and dmg.exists():
        print(f"  DMG        : {dmg} ({_tamano_mb(dmg)})")
    else:
        print("  DMG        : no generado")
    print("\nPara distribución fuera de pruebas, firma y notariza la app en macOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
