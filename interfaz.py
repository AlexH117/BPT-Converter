#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaz gráfica del convertidor de formatos."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import convertidor as cv  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_OK = True
except Exception:
    DND_OK = False

# Paleta del prototipo de diseño (Open Design)
CANVAS = "#e9edf3"
SURFACE = "#ffffff"
SURFACE_ALT = "#f6f8fb"
SURFACE_SUNKEN = "#f1f4f9"
LINE = "#dbe2ec"
LINE_STRONG = "#b9c4d4"
INK = "#16202e"
INK_2 = "#435167"
INK_3 = "#5b6879"
ACCENT = "#1d4ed8"
ACCENT_HOVER = "#1a43b8"
ACCENT_SOFT = "#e8eefc"
ACCENT_LINE = "#b8c9f5"
OK = "#0f7547"
OK_BG = "#e7f5ed"
WARN = "#965300"
WARN_BG = "#fff3e2"
BAD = "#b42318"
BAD_BG = "#fdecea"
INFO = "#175cd3"
INFO_BG = "#eaf1fd"

COLOR_OK = OK
COLOR_ERROR = BAD
COLOR_PROC = INFO
COLOR_AVISO = WARN

NOMBRE_APP = "BPT Converter"

EXT_IMAGEN_PATRON = " ".join("*" + e for e in sorted(cv.EXTS_IMAGEN))
EXT_VIDEO_PATRON = " ".join("*" + e for e in sorted(cv.EXTS_VIDEO))
EXT_AUDIO_PATRON = " ".join("*" + e for e in sorted(cv.EXTS_AUDIO))

TIPOS_ARCHIVO = [
    (
        "Todos los soportados",
        f"{EXT_IMAGEN_PATRON} {EXT_VIDEO_PATRON} {EXT_AUDIO_PATRON}",
    ),
    ("Imágenes", EXT_IMAGEN_PATRON),
    ("Vídeos", EXT_VIDEO_PATRON),
    ("Audio", EXT_AUDIO_PATRON),
    ("Todos los archivos", "*.*"),
]

# Presets de resolución. Una tupla = caja máxima (sin ampliar); un número = porcentaje.
PRESETS_RESOLUCION = {
    "Original (sin cambios)": None,
    "4K (3840×2160)": (3840, 2160),
    "2K (2560×1440)": (2560, 1440),
    "Full HD (1920×1080)": (1920, 1080),
    "HD (1280×720)": (1280, 720),
    "480p (854×480)": (854, 480),
    "75 % del original": 75.0,
    "50 % del original": 50.0,
    "25 % del original": 25.0,
    "Personalizado…": "personalizado",
}


def _tamano_legible(ruta: Path) -> str:
    try:
        n = ruta.stat().st_size
    except OSError:
        return "?"
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidad == "TB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024
    return "?"


def _entero_de(texto: str, por_defecto: int) -> int:
    digitos = "".join(c for c in texto if c.isdigit())
    return int(digitos) if digitos else por_defecto


def _ruta_asset(nombre: str) -> Path | None:
    """Localiza un recurso tanto en desarrollo como dentro del .exe de PyInstaller."""
    base_ejecutable = Path(sys.executable).resolve().parent
    meipass = getattr(sys, "_MEIPASS", None)
    candidatos = []
    if meipass:
        candidatos.append(Path(meipass) / nombre)
    candidatos += [
        BASE / nombre,
        base_ejecutable / nombre,
        base_ejecutable / "_internal" / nombre,
    ]
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


def _abrir_con_visor(ruta: Path) -> None:
    """Abre una carpeta o archivo con el visor del sistema en Windows/macOS/Linux."""
    destino = str(ruta)
    if os.name == "nt":
        os.startfile(destino)  # type: ignore[attr-defined]
        return
    comando = ["open", destino] if sys.platform == "darwin" else ["xdg-open", destino]
    try:
        subprocess.run(comando, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise OSError(f"No se encontró el comando '{comando[0]}'.") from exc


class Aplicacion:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        self.archivos: dict[str, Path] = {}
        self.claves: set[str] = set()
        self.cola: queue.Queue = queue.Queue()
        self.cancelar = threading.Event()
        self.convertiendo = False
        self.hilo: threading.Thread | None = None
        self.carpeta_salida: Path | None = None

        self._configurar_ventana()
        self._crear_estilos()
        self._crear_widgets()
        self._actualizar_resumen()
        self._actualizar_formatos()
        self._configurar_dnd()

        self.raiz.after(100, self._procesar_cola)
        self.raiz.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ------------------------------------------------------------------ UI
    def _configurar_ventana(self) -> None:
        self.raiz.title(f"{NOMBRE_APP} — imágenes, vídeo y audio")
        ancho = min(1200, self.raiz.winfo_screenwidth() - 60)
        alto = min(860, self.raiz.winfo_screenheight() - 100)
        x = max(0, (self.raiz.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.raiz.winfo_screenheight() - alto) // 2 - 20)
        self.raiz.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.raiz.minsize(980, 640)

        icono = BASE / "icono.ico"
        if icono.exists() and os.name == "nt":
            try:
                self.raiz.iconbitmap(str(icono))
            except Exception:
                pass

        self.raiz.columnconfigure(0, weight=1)
        self.raiz.rowconfigure(2, weight=1)

    def _crear_estilos(self) -> None:
        estilo = ttk.Style(self.raiz)
        # "clam" respeta los colores personalizados; "vista" como respaldo.
        try:
            if "clam" in estilo.theme_names():
                estilo.theme_use("clam")
            elif "vista" in estilo.theme_names():
                estilo.theme_use("vista")
        except Exception:
            pass

        familia = "Segoe UI Variable Text" if os.name == "nt" else "Helvetica"
        display = "Segoe UI Variable Display" if os.name == "nt" else familia
        estilo.configure(".", font=(familia, 10), background=SURFACE, foreground=INK)

        def _conf(nombre: str, **opciones) -> None:
            try:
                estilo.configure(nombre, **opciones)
            except Exception:
                pass

        def _map(nombre: str, **secuencias) -> None:
            try:
                estilo.map(nombre, **secuencias)
            except Exception:
                pass

        _conf("Titulo.TLabel", font=(display, 15, "bold"), foreground=INK, background=SURFACE)
        _conf("Pane.TLabel", font=(display, 12, "bold"), foreground=INK, background=CANVAS)
        _conf("Sub.TLabel", font=(familia, 9), foreground=INK_3, background=SURFACE)
        _conf("Cmd.TLabel", font=(familia, 10, "bold"), foreground=INK_2, background=SURFACE_ALT)
        _conf("Estado.TLabel", font=(familia, 9), foreground=INK_2)

        _conf(
            "Card.TLabelframe",
            background=SURFACE, foreground=INK, bordercolor=LINE,
            lightcolor=LINE, darkcolor=LINE,
        )
        _conf(
            "Card.TLabelframe.Label",
            background=SURFACE, foreground=INK, font=(familia, 10, "bold"),
        )

        _conf("Principal.TButton", font=(familia, 10, "bold"), padding=(14, 8),
              background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
              borderwidth=1, relief="flat")
        _map("Principal.TButton", background=[("active", ACCENT_HOVER)],
             bordercolor=[("active", ACCENT_HOVER)])
        _conf("Convertir.TButton", font=(familia, 10, "bold"), padding=(14, 8),
              background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
              borderwidth=1, relief="flat")
        _map("Convertir.TButton", background=[("active", ACCENT_HOVER)])
        _conf("Secundario.TButton", font=(familia, 10, "bold"), padding=(11, 7),
              background=SURFACE, foreground=INK, bordercolor=LINE_STRONG,
              borderwidth=1, relief="flat")
        _map("Secundario.TButton", background=[("active", SURFACE_SUNKEN)],
             bordercolor=[("active", ACCENT_LINE)])
        _conf("Danger.TButton", font=(familia, 10, "bold"), padding=(10, 7),
              background=SURFACE, foreground=BAD, bordercolor=BAD_BG,
              borderwidth=1, relief="flat")
        _map("Danger.TButton", background=[("active", BAD_BG)])
        _conf("Quiet.TButton", font=(familia, 9, "bold"), padding=(7, 4),
              background=SURFACE_ALT, foreground=INK_2, borderwidth=0, relief="flat")
        _map("Quiet.TButton", background=[("active", SURFACE_SUNKEN)])

        _conf("TProgressbar", troughcolor=SURFACE_SUNKEN, background=ACCENT,
              bordercolor=LINE, darkcolor=ACCENT, lightcolor=ACCENT)
        _conf("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=INK,
              rowheight=28, font=(familia, 9), bordercolor=LINE)
        _conf("Treeview.Heading", background=SURFACE_ALT, foreground=INK_3,
              font=(familia, 9, "bold"), relief="flat", bordercolor=LINE)
        _map("Treeview.Heading", background=[("active", ACCENT_SOFT)])
        estilo.configure("ok.TCheckbutton", foreground=OK)

    def _crear_widgets(self) -> None:
        self.raiz.configure(bg=CANVAS)

        # ---------- Barra de título (estilo app de Windows) ----------
        titlebar = tk.Frame(self.raiz, bg=SURFACE, height=56)
        titlebar.grid(row=0, column=0, sticky="ew")
        titlebar.grid_propagate(False)
        titlebar.columnconfigure(2, weight=1)

        # Logo BPT (PNG transparente). Se mantiene una referencia para que no
        # sea recolectado por el garbage collector mientras viva la ventana.
        logo = None
        ruta_logo = _ruta_asset("logo_bpt_40.png")
        if ruta_logo is not None:
            try:
                self.logo_img = tk.PhotoImage(file=str(ruta_logo))
                logo = tk.Label(titlebar, image=self.logo_img, bg=SURFACE,
                                highlightthickness=0, bd=0)
                logo.grid(row=0, column=0, padx=(16, 10), pady=8)
            except Exception:
                logo = None
        if logo is None:
            # Respaldo por si el recurso no está disponible.
            logo = tk.Canvas(titlebar, width=32, height=32, bg=ACCENT, highlightthickness=0)
            logo.grid(row=0, column=0, padx=(16, 10), pady=12)
            logo.create_text(16, 16, text="B", fill="#ffffff",
                             font=("Segoe UI", 15, "bold"))

        textos = tk.Frame(titlebar, bg=SURFACE)
        textos.grid(row=0, column=1, sticky="w")
        ttk.Label(textos, text=NOMBRE_APP, style="Titulo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            textos,
            text="Conversión por lotes de imágenes, vídeo y audio",
            style="Sub.TLabel",
        ).grid(row=1, column=0, sticky="w")

        self.lbl_pill = tk.Label(
            titlebar, text="●  Listo", bg=SURFACE_ALT, fg=OK,
            font=("Segoe UI", 9, "bold"), padx=10, pady=3,
        )
        self.lbl_pill.grid(row=0, column=3, sticky="e", padx=(0, 18))

        # ---------- Barra de comandos ----------
        command = tk.Frame(self.raiz, bg=SURFACE_ALT, height=48)
        command.grid(row=1, column=0, sticky="ew")
        command.grid_propagate(False)
        command.columnconfigure(2, weight=1)
        ttk.Label(command, text="Espacio de trabajo / Conversión rápida", style="Cmd.TLabel").grid(
            row=0, column=0, sticky="w", padx=(24, 12)
        )
        ttk.Label(
            command, text="Arrastra archivos o pega un enlace para empezar", style="Sub.TLabel"
        ).grid(row=0, column=1, sticky="w")
        self.lbl_cola_pill = tk.Label(
            command, text="0 en cola", bg=ACCENT_SOFT, fg=INK,
            font=("Segoe UI", 9, "bold"), padx=10, pady=3,
        )
        self.lbl_cola_pill.grid(row=0, column=3, sticky="e", padx=(0, 24))

        # ---------- Área de trabajo (dos paneles) ----------
        workspace = tk.Frame(self.raiz, bg=CANVAS)
        workspace.grid(row=2, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=16)
        workspace.columnconfigure(1, weight=10)
        workspace.rowconfigure(0, weight=1)

        izquierda = tk.Frame(workspace, bg=CANVAS)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=12)
        izquierda.columnconfigure(0, weight=1)
        izquierda.rowconfigure(4, weight=1)

        derecha_contenedor = tk.Frame(workspace, bg=CANVAS)
        derecha_contenedor.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=12)
        derecha_contenedor.columnconfigure(0, weight=1)
        derecha_contenedor.rowconfigure(0, weight=1)

        canvas_derecha = tk.Canvas(derecha_contenedor, bg=CANVAS, highlightthickness=0, bd=0)
        scroll_derecha = ttk.Scrollbar(derecha_contenedor, orient="vertical", command=canvas_derecha.yview)
        canvas_derecha.configure(yscrollcommand=scroll_derecha.set)
        canvas_derecha.grid(row=0, column=0, sticky="nsew")
        scroll_derecha.grid(row=0, column=1, sticky="ns")

        derecha = tk.Frame(canvas_derecha, bg=CANVAS)
        derecha.columnconfigure(0, weight=1)
        ventana_derecha = canvas_derecha.create_window((0, 0), window=derecha, anchor="nw")

        def _ajustar_scroll_derecha(_evento=None):
            canvas_derecha.configure(scrollregion=canvas_derecha.bbox("all"))
            canvas_derecha.itemconfigure(ventana_derecha, width=canvas_derecha.winfo_width())

        derecha.bind("<Configure>", _ajustar_scroll_derecha)
        canvas_derecha.bind("<Configure>", _ajustar_scroll_derecha)

        def _wheel_derecha(event):
            if canvas_derecha.winfo_exists():
                delta = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
                canvas_derecha.yview_scroll(delta, "units")

        def _bind_wheel_derecha(_event=None):
            canvas_derecha.bind_all("<MouseWheel>", _wheel_derecha)
            canvas_derecha.bind_all("<Button-4>", _wheel_derecha)
            canvas_derecha.bind_all("<Button-5>", _wheel_derecha)

        def _unbind_wheel_derecha(_event=None):
            canvas_derecha.unbind_all("<MouseWheel>")
            canvas_derecha.unbind_all("<Button-4>")
            canvas_derecha.unbind_all("<Button-5>")

        canvas_derecha.bind("<Enter>", _bind_wheel_derecha)
        canvas_derecha.bind("<Leave>", _unbind_wheel_derecha)
        derecha.bind("<Enter>", _bind_wheel_derecha)
        derecha.bind("<Leave>", _unbind_wheel_derecha)

        # ---------- Panel izquierdo: archivos de origen ----------
        cab_origen = tk.Frame(izquierda, bg=CANVAS)
        cab_origen.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(cab_origen, text="Archivos de origen", style="Pane.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(cab_origen, text="Imágenes, vídeo, audio o YouTube", style="Sub.TLabel").grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        cab_origen.columnconfigure(2, weight=1)
        self.lbl_cuenta = ttk.Label(cab_origen, text="0 elementos", style="Sub.TLabel")
        self.lbl_cuenta.grid(row=0, column=2, sticky="e")

        dropzone = tk.Label(
            izquierda,
            text="Arrastra tus archivos aquí\no haz clic para seleccionar desde tu equipo",
            bg=SURFACE, fg=INK_2, font=("Segoe UI", 10),
            justify="center", bd=1, relief="groove", cursor="hand2", pady=12,
        )
        dropzone.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        dropzone.bind("<Button-1>", lambda _e: self._elegir_archivos())

        barra = ttk.Frame(izquierda)
        barra.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        barra.columnconfigure(1, weight=1)

        frame_agregar = ttk.Frame(barra)
        frame_agregar.grid(row=0, column=0, sticky="w")
        self.btn_agregar = ttk.Button(frame_agregar, text="Agregar archivos", command=self._elegir_archivos)
        self.btn_agregar.grid(row=0, column=0, padx=(0, 6))
        self.btn_carpeta = ttk.Button(frame_agregar, text="Agregar carpeta", command=self._elegir_carpeta)
        self.btn_carpeta.grid(row=0, column=1)
        self.var_recursivo = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_agregar, text="Incluir subcarpetas", variable=self.var_recursivo).grid(
            row=0, column=2, padx=(10, 0), sticky="w"
        )

        frame_lista = ttk.Frame(barra)
        frame_lista.grid(row=0, column=2, sticky="e")
        self.btn_quitar = ttk.Button(frame_lista, text="Quitar", style="Danger.TButton", command=self._quitar_seleccion)
        self.btn_quitar.grid(row=0, column=0, padx=(0, 6))
        self.btn_limpiar = ttk.Button(frame_lista, text="Vaciar cola", style="Quiet.TButton", command=self._limpiar)
        self.btn_limpiar.grid(row=0, column=1)

        self.lbl_pista = ttk.Label(barra, text="", style="Sub.TLabel")
        self.lbl_pista.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        youtube = ttk.LabelFrame(
            izquierda, text=" Descargar desde YouTube ", style="Card.TLabelframe", padding=12
        )
        youtube.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        youtube.columnconfigure(0, weight=1)
        fila_yt = ttk.Frame(youtube)
        fila_yt.grid(row=0, column=0, sticky="ew")
        fila_yt.columnconfigure(0, weight=1)
        self.var_url_youtube = tk.StringVar()
        self.entry_url_youtube = ttk.Entry(fila_yt, textvariable=self.var_url_youtube)
        self.entry_url_youtube.grid(row=0, column=0, sticky="ew")
        self.btn_agregar_url = ttk.Button(
            fila_yt, text="Agregar", style="Secundario.TButton", command=self._agregar_url_youtube
        )
        self.btn_agregar_url.grid(row=0, column=1, padx=(8, 0))
        self.lbl_url_youtube = ttk.Label(
            youtube,
            text="Pega una URL de YouTube (https://www.youtube.com/watch?v=…) y agrégala a la cola. "
                 "AUTO convierte a MP4; si eliges un formato de audio, se extrae solo el sonido.",
            style="Sub.TLabel", wraplength=560, justify="left",
        )
        self.lbl_url_youtube.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        archivos_card = ttk.LabelFrame(
            izquierda, text=" Cola de conversión ", style="Card.TLabelframe", padding=8
        )
        archivos_card.grid(row=4, column=0, sticky="nsew")
        archivos_card.columnconfigure(0, weight=1)
        archivos_card.rowconfigure(1, weight=1)

        self.lbl_vacio = ttk.Label(
            archivos_card,
            text="La cola está vacía.\nAñade archivos o un enlace de YouTube para empezar.",
            style="Sub.TLabel", justify="center",
        )
        self.lbl_vacio.grid(row=1, column=0, sticky="nsew")

        columnas = ("archivo", "tipo", "tamano", "estado")
        contenedor = ttk.Frame(archivos_card)
        self.contenedor_tree = contenedor
        contenedor.grid(row=1, column=0, sticky="nsew")
        contenedor.columnconfigure(0, weight=1)
        contenedor.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(contenedor, columns=columnas,
                                 show="headings", selectmode="extended")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("tamano", text="Tamaño")
        self.tree.heading("estado", text="Estado")
        self.tree.column("archivo", width=420, minwidth=200, stretch=True)
        self.tree.column("tipo", width=80, anchor="center", stretch=False)
        self.tree.column("tamano", width=90, anchor="e", stretch=False)
        self.tree.column("estado", width=130, anchor="w", stretch=False)

        self.barra_v = ttk.Scrollbar(contenedor, orient="vertical", command=self.tree.yview)
        self.barra_v.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self.barra_v.set)
        contenedor.grid_forget()

        self.tree.tag_configure("ok", foreground=OK, background=OK_BG)
        self.tree.tag_configure("error", foreground=BAD, background=BAD_BG)
        self.tree.tag_configure("proc", foreground=INFO, background=INFO_BG)
        self.tree.tag_configure("aviso", foreground=WARN, background=WARN_BG)

        self.tree.bind("<Double-1>", self._abrir_seleccionado)
        self.tree.bind("<Delete>", lambda _e: self._quitar_seleccion())

        self.lbl_resumen = ttk.Label(archivos_card, text="No hay archivos en la lista.", style="Sub.TLabel")
        self.lbl_resumen.grid(row=2, column=0, sticky="w", pady=(6, 0))

        # ---------- Panel derecho: ajustes de salida ----------
        cab_ajustes = tk.Frame(derecha, bg=CANVAS)
        cab_ajustes.grid(row=0, column=0, sticky="ew")
        ttk.Label(cab_ajustes, text="Ajustes de salida", style="Pane.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(cab_ajustes, text="Se aplican a toda la cola", style="Sub.TLabel").grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        cab_ajustes.columnconfigure(2, weight=1)

        formato_card = ttk.LabelFrame(
            derecha, text=" Formato de destino ", style="Card.TLabelframe", padding=12
        )
        formato_card.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        formato_card.columnconfigure(0, weight=1)
        ttk.Label(formato_card, text="Convertir a:", style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        self.combo_formato = ttk.Combobox(
            formato_card, state="readonly", width=18, values=["AUTO", *cv.FORMATOS_SALIDA]
        )
        self.combo_formato.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.combo_formato.set("JPG")
        self.formato_manual = False
        self.combo_formato.bind("<<ComboboxSelected>>", self._marcar_formato_manual)
        self.lbl_formatos = ttk.Label(
            formato_card,
            text="AUTO selecciona JPG / MP4 / MP3 según el tipo de archivo.",
            style="Sub.TLabel", wraplength=430, justify="left",
        )
        self.lbl_formatos.grid(row=2, column=0, sticky="w", pady=(8, 0))

        calidad_card = ttk.LabelFrame(
            derecha, text=" Calidad y resolución ", style="Card.TLabelframe", padding=12
        )
        calidad_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        calidad_card.columnconfigure(0, weight=1)

        ttk.Label(calidad_card, text="Resolución:", style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        self.var_resolucion = tk.StringVar(value="Original (sin cambios)")
        self.combo_resolucion = ttk.Combobox(
            calidad_card, state="readonly", width=24,
            values=list(PRESETS_RESOLUCION), textvariable=self.var_resolucion,
        )
        self.combo_resolucion.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.combo_resolucion.bind("<<ComboboxSelected>>", self._al_cambiar_resolucion)

        fila_px = ttk.Frame(calidad_card)
        fila_px.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(fila_px, text="Ancho:").grid(row=0, column=0, sticky="e")
        self.var_ancho_px = tk.StringVar()
        self.entry_ancho_px = ttk.Entry(fila_px, width=7, textvariable=self.var_ancho_px)
        self.entry_ancho_px.grid(row=0, column=1, padx=(4, 2))
        ttk.Label(fila_px, text="px").grid(row=0, column=2, sticky="w")
        ttk.Label(fila_px, text="Alto:").grid(row=0, column=3, sticky="e", padx=(12, 0))
        self.var_alto_px = tk.StringVar()
        self.entry_alto_px = ttk.Entry(fila_px, width=7, textvariable=self.var_alto_px)
        self.entry_alto_px.grid(row=0, column=4, padx=(4, 2))
        ttk.Label(fila_px, text="px").grid(row=0, column=5, sticky="w")
        self.var_proporcion = tk.BooleanVar(value=True)
        self.chk_proporcion = ttk.Checkbutton(
            fila_px, text="Mantener proporción", variable=self.var_proporcion
        )
        self.chk_proporcion.grid(row=0, column=6, padx=(12, 0))

        self.lbl_resolucion = ttk.Label(
            calidad_card,
            text="Ancho/Alto se usan con «Personalizado…» (vacío = automático). "
                 "Los presets nunca agrandan el archivo.",
            style="Sub.TLabel", wraplength=430, justify="left",
        )
        self.lbl_resolucion.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._al_cambiar_resolucion()

        fila_calidad = ttk.Frame(calidad_card)
        fila_calidad.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        fila_calidad.columnconfigure(1, weight=1)
        fila_calidad.columnconfigure(3, weight=1)
        ttk.Label(fila_calidad, text="Calidad imagen:").grid(row=0, column=0, sticky="w")
        self.combo_calidad_img = ttk.Combobox(
            fila_calidad, state="readonly", width=13,
            values=["Alta (95)", "Media (85)", "Baja (70)", "Máxima (100)"],
        )
        self.combo_calidad_img.grid(row=0, column=1, sticky="ew", padx=(4, 10))
        self.combo_calidad_img.set("Alta (95)")
        ttk.Label(fila_calidad, text="Calidad vídeo:").grid(row=0, column=2, sticky="w")
        self.combo_calidad_video = ttk.Combobox(
            fila_calidad, state="readonly", width=15,
            values=["Alta (CRF 20)", "Media (CRF 23)", "Baja (CRF 28)", "Máxima (CRF 18)"],
        )
        self.combo_calidad_video.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self.combo_calidad_video.set("Media (CRF 23)")

        self.var_sobrescribir = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            calidad_card, text="Sobrescribir archivos existentes", variable=self.var_sobrescribir
        ).grid(row=5, column=0, sticky="w", pady=(10, 0))

        destino_card = ttk.LabelFrame(
            derecha, text=" Carpeta de salida ", style="Card.TLabelframe", padding=12
        )
        destino_card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        destino_card.columnconfigure(1, weight=1)
        self.var_destino = tk.StringVar(value="subcarpeta")
        ttk.Radiobutton(
            destino_card, text="Junto al original (carpeta «Convertidos»)",
            variable=self.var_destino, value="subcarpeta",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(
            destino_card, text="Carpeta personalizada:",
            variable=self.var_destino, value="personalizada",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_carpeta = tk.StringVar(value="")
        self.entry_carpeta = ttk.Entry(destino_card, textvariable=self.var_carpeta)
        self.entry_carpeta.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(6, 0))
        self.btn_examinar = ttk.Button(
            destino_card, text="Examinar…", style="Secundario.TButton", command=self._elegir_destino
        )
        self.btn_examinar.grid(row=1, column=2, sticky="e", pady=(6, 0))

        progreso_card = ttk.LabelFrame(
            derecha, text=" Progreso de conversión ", style="Card.TLabelframe", padding=12
        )
        progreso_card.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        progreso_card.columnconfigure(0, weight=1)
        self.lbl_progreso_pct = ttk.Label(progreso_card, text="0%", style="Estado.TLabel")
        self.lbl_progreso_pct.grid(row=0, column=1, sticky="e")
        self.barra_progreso = ttk.Progressbar(
            progreso_card, orient="horizontal", mode="determinate", maximum=100
        )
        self.barra_progreso.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.lbl_estado = ttk.Label(progreso_card, text="Listo.", style="Estado.TLabel")
        self.lbl_estado.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.lbl_progreso_count = ttk.Label(progreso_card, text="0 de 0", style="Estado.TLabel")
        self.lbl_progreso_count.grid(row=2, column=1, sticky="e", pady=(6, 0))

        acciones = ttk.Frame(derecha)
        acciones.grid(row=5, column=0, sticky="ew")
        acciones.columnconfigure(1, weight=1)
        self.btn_cancelar = ttk.Button(
            acciones, text="Cancelar", style="Secundario.TButton", command=self._cancelar, state="disabled"
        )
        self.btn_cancelar.grid(row=0, column=0, padx=(0, 8))
        self.btn_convertir = ttk.Button(
            acciones, text="Convertir archivos", style="Principal.TButton", command=self._iniciar_conversion
        )
        self.btn_convertir.grid(row=0, column=1, sticky="ew")
        self.btn_abrir = ttk.Button(
            acciones, text="Abrir carpeta", style="Secundario.TButton", command=self._abrir_carpeta, state="disabled"
        )
        self.btn_abrir.grid(row=0, column=2, padx=(8, 0))

        # ---------- Registro ----------
        registro = ttk.LabelFrame(
            self.raiz, text=" Registro de actividad ", style="Card.TLabelframe", padding=(8, 4)
        )
        registro.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        registro.columnconfigure(0, weight=1)
        self.texto_log = ScrolledText(
            registro, height=6, wrap="word", state="disabled",
            bg=SURFACE, fg=INK, font=("Consolas" if os.name == "nt" else "Menlo", 9),
        )
        self.texto_log.grid(row=0, column=0, sticky="ew")

        # ---------- Barra de estado ----------
        statusbar = tk.Frame(self.raiz, bg=SURFACE, height=30)
        statusbar.grid(row=4, column=0, sticky="ew")
        statusbar.grid_propagate(False)
        statusbar.columnconfigure(3, weight=1)
        self.lbl_run_state = tk.Label(
            statusbar, text="●  Listo", bg=SURFACE, fg=OK,
            font=("Segoe UI", 9, "bold"), padx=24,
        )
        self.lbl_run_state.grid(row=0, column=0, sticky="w")
        self.lbl_status_summary = ttk.Label(statusbar, text="0 archivos en cola", style="Sub.TLabel")
        self.lbl_status_summary.grid(row=0, column=1, sticky="w")
        tk.Label(statusbar, text=f"{NOMBRE_APP} · v1.2", bg=SURFACE, fg=INK_3,
                 font=("Segoe UI", 9)).grid(row=0, column=3, sticky="e", padx=(0, 24))

    def _configurar_dnd(self) -> None:
        if DND_OK:
            try:
                self.raiz.drop_target_register(DND_FILES)
                self.raiz.dnd_bind("<<Drop>>", self._soltar)
                self.lbl_pista.configure(text="Arrastra archivos o carpetas aquí")
            except Exception:
                self.lbl_pista.configure(text="")
        else:
            self.lbl_pista.configure(text="")

    # -------------------------------------------------------------- Archivos
    def _elegir_archivos(self) -> None:
        rutas = filedialog.askopenfilenames(title="Selecciona archivos", filetypes=TIPOS_ARCHIVO)
        if rutas:
            self._agregar_rutas(rutas)

    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(title="Selecciona una carpeta")
        if carpeta:
            self._agregar_rutas([carpeta])

    def _agregar_url_youtube(self) -> None:
        url = self.var_url_youtube.get().strip()
        if not url:
            messagebox.showwarning("URL de YouTube", "Pega una URL de YouTube primero.")
            return
        if not cv.es_url_youtube(url):
            messagebox.showwarning("URL de YouTube", "Esa URL no parece ser una URL de YouTube válida.")
            return
        if url.lower() in self.claves:
            messagebox.showinfo("URL de YouTube", "Esa URL ya está en la lista.")
            return
        iid = self.tree.insert(
            "", "end",
            values=(f"YouTube: {url}", "Vídeo", "—", "Pendiente"),
        )
        self.archivos[iid] = url
        self.claves.add(url.lower())
        self.var_url_youtube.set("")
        self._registrar(f"URL de YouTube agregada: {url}")
        self._actualizar_resumen()
        self._actualizar_formatos()

    def _soltar(self, evento) -> None:
        if self.convertiendo:
            return
        try:
            rutas = self.raiz.tk.splitlist(evento.data)
        except Exception:
            rutas = [evento.data]
        self._agregar_rutas(rutas)

    def _agregar_rutas(self, rutas) -> None:
        nuevos = 0
        ignorados = 0
        for ruta in rutas:
            p = Path(ruta)
            if p.is_dir():
                patron = "**/*" if self.var_recursivo.get() else "*"
                for archivo in sorted(p.glob(patron)):
                    if archivo.is_file():
                        resultado = self._insertar(archivo)
                        if resultado is True:
                            nuevos += 1
                        elif resultado is None:
                            ignorados += 1
            elif p.is_file():
                resultado = self._insertar(p)
                if resultado is True:
                    nuevos += 1
                elif resultado is None:
                    ignorados += 1
            else:
                ignorados += 1

        if ignorados:
            self._registrar(f"{ignorados} archivo(s) ignorado(s): extensión no soportada.")
        if nuevos:
            self._registrar(f"{nuevos} archivo(s) agregado(s).")
        self._actualizar_resumen()
        self._actualizar_formatos()

    def _insertar(self, ruta: Path) -> bool | None:
        """True = agregado, False = duplicado, None = no soportado."""
        try:
            clave = str(ruta.resolve()).lower()
        except OSError:
            clave = str(ruta).lower()
        if clave in self.claves:
            return False
        cat = cv.categoria_archivo(ruta)
        if cat is None:
            return None

        iid = self.tree.insert(
            "", "end",
            values=(ruta.name, cat.capitalize(), _tamano_legible(ruta), "Pendiente"),
        )
        self.tree.item(iid, tags=())
        self.archivos[iid] = ruta
        self.claves.add(clave)
        return True

    def _quitar_seleccion(self) -> None:
        if self.convertiendo:
            return
        for iid in self.tree.selection():
            ruta = self.archivos.pop(iid, None)
            if ruta is not None:
                if isinstance(ruta, str):
                    # Las URLs de YouTube se guardan como string, sin Path.
                    self.claves.discard(ruta.strip().lower())
                else:
                    try:
                        self.claves.discard(str(ruta.resolve()).lower())
                    except OSError:
                        self.claves.discard(str(ruta).lower())
            self.tree.delete(iid)
        self._actualizar_resumen()
        self._actualizar_formatos()

    def _limpiar(self) -> None:
        if self.convertiendo:
            return
        self.tree.delete(*self.tree.get_children())
        self.archivos.clear()
        self.claves.clear()
        self._actualizar_resumen()
        self._actualizar_formatos()

    @staticmethod
    def _categoria_de(valor) -> str | None:
        """Categoría de un archivo o de una URL de YouTube."""
        if isinstance(valor, str) and cv.es_url_youtube(valor):
            return "video"
        return cv.categoria_archivo(valor)

    def _actualizar_resumen(self) -> None:
        total = len(self.archivos)
        if total == 0:
            self.lbl_resumen.configure(text="No hay archivos en la lista.")
            self.lbl_vacio.grid(row=1, column=0, sticky="nsew")
            self.tree.grid_forget()
            self.contenedor_tree.grid_forget()
        else:
            self.lbl_vacio.grid_forget()
            self.contenedor_tree.grid(row=1, column=0, sticky="nsew")
            self.tree.grid(row=0, column=0, sticky="nsew")
            tipos = {}
            for ruta in self.archivos.values():
                cat = self._categoria_de(ruta) or "otros"
                tipos[cat] = tipos.get(cat, 0) + 1
            detalle = ", ".join(f"{n} {c}" for c, n in sorted(tipos.items()))
            self.lbl_resumen.configure(text=f"{total} elemento(s) en la cola ({detalle}).")
        self._actualizar_indicadores()

    def _actualizar_indicadores(self) -> None:
        """Mantiene sincronizados los "pills" y contadores del diseño."""
        total = len(self.archivos)
        self.lbl_cuenta.configure(text=f"{total} elemento(s)")
        self.lbl_cola_pill.configure(text=f"{total} en cola")
        self.lbl_status_summary.configure(text=f"{total} archivo(s) en cola")

    def _estado_pill(self, texto: str, color: str, fondo: str) -> None:
        for etiqueta in (self.lbl_pill, self.lbl_run_state):
            etiqueta.configure(text=f"●  {texto}", fg=color, bg=fondo)

    def _actualizar_formatos(self) -> None:
        cats = {self._categoria_de(p) for p in self.archivos.values()}
        cats.discard(None)
        valores: list[str] = ["AUTO"]

        if not cats or "imagen" in cats:
            valores += list(cv.FORMATOS_IMAGEN)
        if not cats or "video" in cats:
            valores += list(cv.FORMATOS_VIDEO)
            valores += ["GIF"] if "GIF" not in valores else []
        if not cats or "audio" in cats or "video" in cats:
            valores += list(cv.FORMATOS_AUDIO)

        # Sin duplicados, conservando el orden
        vistos: set[str] = set()
        opciones = [v for v in valores if not (v in vistos or vistos.add(v))]

        actual = self.combo_formato.get()
        self.combo_formato.configure(values=opciones)
        if self.formato_manual and actual in opciones:
            return
        # El deseado por categoría: imágenes → imagen, audio → audio, vídeo (incl. YouTube) → vídeo.
        # Mezcla de categorías → AUTO.
        if not cats:
            self.combo_formato.set("JPG")
        elif len(cats) > 1:
            self.combo_formato.set("AUTO")
        elif "imagen" in cats:
            self.combo_formato.set("JPG")
        elif "audio" in cats:
            self.combo_formato.set("MP3")
        else:
            self.combo_formato.set("MP4")

    def _elegir_destino(self) -> None:
        carpeta = filedialog.askdirectory(title="Carpeta de salida")
        if carpeta:
            self.var_carpeta.set(carpeta)
            self.var_destino.set("personalizada")

    def _marcar_formato_manual(self, _evento=None) -> None:
        self.formato_manual = True

    def _al_cambiar_resolucion(self, _evento=None) -> None:
        personalizado = self.combo_resolucion.get() == "Personalizado…"
        activo = personalizado and not self.convertiendo
        estado = "normal" if activo else "disabled"
        self.entry_ancho_px.configure(state=estado)
        self.entry_alto_px.configure(state=estado)
        self.chk_proporcion.configure(state=estado)
        if activo:
            self.entry_ancho_px.focus_set()

    def _resolucion_seleccionada(self) -> dict | None:
        preset = self.combo_resolucion.get()
        valor = PRESETS_RESOLUCION.get(preset)

        if valor is None:
            return None
        if isinstance(valor, tuple):
            return {
                "ancho": valor[0], "alto": valor[1], "escala": None,
                "ajustar": True, "no_ampliar": True,
            }
        if isinstance(valor, (int, float)):
            return {
                "ancho": None, "alto": None, "escala": float(valor),
                "ajustar": True, "no_ampliar": False,
            }

        def leer(texto: str, nombre: str) -> int | None:
            limpio = texto.strip().replace("px", "").strip()
            if not limpio:
                return None
            try:
                numero = int(limpio)
            except ValueError as exc:
                raise ValueError(f"El {nombre} debe ser un número entero de píxeles.") from exc
            if numero < 1:
                raise ValueError(f"El {nombre} debe ser mayor que 0.")
            return numero

        ancho = leer(self.var_ancho_px.get(), "ancho")
        alto = leer(self.var_alto_px.get(), "alto")
        if not ancho and not alto:
            raise ValueError("Escribe un ancho o un alto para la resolución personalizada.")
        return {
            "ancho": ancho, "alto": alto, "escala": None,
            "ajustar": self.var_proporcion.get(), "no_ampliar": False,
        }

    @staticmethod
    def _descripcion_resolucion(resolucion: dict | None) -> str:
        if not resolucion:
            return ""
        if resolucion.get("escala"):
            return f" · {resolucion['escala']:.0f} %"
        ancho = resolucion.get("ancho")
        alto = resolucion.get("alto")
        if ancho and alto:
            return f" · {ancho}×{alto} px"
        if ancho:
            return f" · ancho {ancho} px"
        if alto:
            return f" · alto {alto} px"
        return ""

    # ------------------------------------------------------------ Conversión
    def _iniciar_conversion(self) -> None:
        if self.convertiendo:
            return
        if not self.archivos:
            messagebox.showinfo("Sin archivos", "Agrega al menos un archivo para convertir.")
            return

        formato = self.combo_formato.get().strip().upper()
        if formato != "AUTO" and formato not in cv.FORMATOS_SALIDA:
            messagebox.showwarning("Formato", "Selecciona un formato de salida válido.")
            return

        modo = self.var_destino.get()
        carpeta = self.var_carpeta.get().strip()
        if modo == "personalizada":
            if not carpeta:
                messagebox.showwarning("Carpeta", "Elige una carpeta de salida o usa «Junto al original».")
                return
            try:
                Path(carpeta).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                messagebox.showerror("Carpeta", f"No se pudo crear la carpeta:\n{exc}")
                return
            carpeta = str(Path(carpeta))

        calidad_img = _entero_de(self.combo_calidad_img.get(), 90)
        crf = _entero_de(self.combo_calidad_video.get(), 23)

        try:
            resolucion = self._resolucion_seleccionada()
        except ValueError as exc:
            messagebox.showwarning("Resolución", str(exc))
            return

        self.convertiendo = True
        self.cancelar.clear()
        self._bloquear(True)
        self.barra_progreso["value"] = 0
        self.lbl_estado.configure(text="Convirtiendo…")
        self.lbl_progreso_pct.configure(text="0%")
        self.lbl_progreso_count.configure(text=f"0 de {len(self.archivos)}")
        self._estado_pill("Procesando", INFO, INFO_BG)

        items = [(iid, ruta) for iid, ruta in self.archivos.items()]
        self._registrar(
            f"── Inicio: {len(items)} archivo(s) → {formato}"
            f"{self._descripcion_resolucion(resolucion)} ──"
        )

        hilo = threading.Thread(
            target=self._trabajo,
            args=(items, formato, modo, carpeta, calidad_img, crf,
                  self.var_sobrescribir.get(), resolucion),
            daemon=True,
        )
        self.hilo = hilo
        hilo.start()

    def _trabajo(self, items, formato, modo, carpeta, calidad_img, crf, sobrescribir,
                 resolucion=None) -> None:
        total = len(items)
        exitos = 0
        fallos = 0
        ultima_carpeta: Path | None = None

        for indice, (iid, ruta) in enumerate(items):
            if self.cancelar.is_set():
                for iid_pend, _ in items[indice:]:
                    self.cola.put(("estado", iid_pend, "Cancelado", "aviso"))
                break

            es_url = isinstance(ruta, str) and cv.es_url_youtube(ruta)
            if es_url:
                carpeta_destino = (
                    Path(carpeta) if (modo == "personalizada" and carpeta)
                    else Path.home()
                    / ("Videos" if os.name == "nt" else "Movies")
                    / "BPT Converter"
                )
            else:
                carpeta_destino = ruta.parent / "Convertidos" if modo == "subcarpeta" else Path(carpeta)

            self.cola.put(("estado", iid, "Convirtiendo…", "proc"))
            self.cola.put(("progreso", indice / total * 100))

            def progreso(pct, i=indice):
                self.cola.put(("progreso", (i + pct / 100.0) / total * 100))

            def log(msg):
                self.cola.put(("log", msg))

            try:
                if es_url:
                    fmt_a_usar = formato if formato != "AUTO" else "MP4"
                    destino_final = cv.convertir_url_youtube(
                        str(ruta), carpeta_destino, fmt_a_usar,
                        progreso=progreso, cancelado=self.cancelar, log=log,
                        calidad=calidad_img, crf=crf,
                        **(resolucion or {}),
                    )
                else:
                    fmt_archivo = cv.formato_automatico(ruta) if formato == "AUTO" else formato
                    destino = cv.ruta_destino(ruta, carpeta_destino, fmt_archivo, sobrescribir)
            except cv.ErrorConversion as exc:
                self.cola.put(("estado", iid, "✖ Error", "error"))
                self.cola.put(("log", f"✖ {ruta.name if not es_url else ruta}: {exc}"))
                fallos += 1
                continue

            try:
                if es_url:
                    exitos += 1
                    ultima_carpeta = destino_final.parent
                    self.cola.put(("estado", iid, "✔ Listo", "ok"))
                    self.cola.put(("log", f"✔ {ruta}  →  {destino_final.name}"))
                else:
                    cv.convertir_archivo(
                        ruta, destino, fmt_archivo,
                        calidad=calidad_img, crf=crf,
                        progreso=progreso, log=log, cancelado=self.cancelar,
                        **(resolucion or {}),
                    )
                    exitos += 1
                    ultima_carpeta = destino.parent
                    self.cola.put(("estado", iid, "✔ Listo", "ok"))
                    self.cola.put(("log", f"✔ {ruta.name}  →  {destino.name}"))
            except cv.ConversionCancelada:
                self.cola.put(("estado", iid, "Cancelado", "aviso"))
                self.cola.put(("log", f"⊗ Cancelado: {ruta.name if not es_url else ruta}"))
                for iid_pend, _ in items[indice + 1:]:
                    self.cola.put(("estado", iid_pend, "Cancelado", "aviso"))
                break
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                fallos += 1
                self.cola.put(("estado", iid, "✖ Error", "error"))
                self.cola.put(("log", f"✖ {ruta.name if not es_url else ruta}: {exc}"))

        self.cola.put(("fin", exitos, fallos, self.cancelar.is_set(), str(ultima_carpeta or "")))

    # --------------------------------------------------------------- Eventos
    def _procesar_cola(self) -> None:
        try:
            while True:
                evento = self.cola.get_nowait()
                tipo = evento[0]

                if tipo == "estado":
                    _, iid, texto, etiqueta = evento
                    if self.tree.exists(iid):
                        valores = list(self.tree.item(iid, "values"))
                        if len(valores) >= 4:
                            valores[3] = texto
                            self.tree.item(iid, values=valores, tags=(etiqueta,))
                elif tipo == "log":
                    self._registrar(evento[1])
                elif tipo == "progreso":
                    pct = max(0.0, min(100.0, evento[1]))
                    self.barra_progreso["value"] = pct
                    self.lbl_progreso_pct.configure(text=f"{pct:.0f}%")
                    total = max(1, len(self.archivos))
                    hechos = min(total, int(pct / 100 * total))
                    self.lbl_progreso_count.configure(text=f"{hechos} de {total}")
                elif tipo == "fin":
                    self._finalizar(*evento[1:])
        except queue.Empty:
            pass

        self.raiz.after(80, self._procesar_cola)

    def _finalizar(self, exitos: int, fallos: int, cancelado: bool, carpeta: str) -> None:
        self.convertiendo = False
        self._bloquear(False)
        if not cancelado:
            self.barra_progreso["value"] = 100

        resumen = f"{exitos} convertido(s), {fallos} error(es)."
        if cancelado:
            resumen = "Conversión cancelada. " + resumen
        self.lbl_estado.configure(text=resumen)
        self.lbl_progreso_pct.configure(
            text="100%" if not cancelado else f"{self.barra_progreso['value']:.0f}%"
        )
        self.lbl_progreso_count.configure(text=f"{exitos} de {len(self.archivos)}")
        if cancelado:
            self._estado_pill("Cancelado", WARN, WARN_BG)
        elif fallos:
            self._estado_pill("Con errores", BAD, BAD_BG)
        else:
            self._estado_pill("Listo", OK, OK_BG)
        self._registrar(f"── Fin: {resumen} ──")

        if carpeta:
            self.carpeta_salida = Path(carpeta)
            self.btn_abrir.configure(state="normal")

        if cancelado:
            messagebox.showwarning("Cancelado", resumen)
        elif fallos:
            messagebox.showwarning("Conversión terminada", resumen + "\n\nRevisa el registro para ver los detalles.")
        else:
            messagebox.showinfo("Conversión terminada", "¡Todo listo!\n\n" + resumen)

    def _bloquear(self, activo: bool) -> None:
        estado = "disabled" if activo else "normal"
        for boton in (self.btn_agregar, self.btn_carpeta, self.btn_quitar, self.btn_limpiar,
                      self.btn_convertir, self.btn_examinar, self.btn_agregar_url):
            boton.configure(state=estado)
        self.combo_formato.configure(state="disabled" if activo else "readonly")
        self.combo_resolucion.configure(state="disabled" if activo else "readonly")
        if activo:
            self.entry_ancho_px.configure(state="disabled")
            self.entry_alto_px.configure(state="disabled")
            self.chk_proporcion.configure(state="disabled")
        else:
            self._al_cambiar_resolucion()
        self.btn_cancelar.configure(state="normal" if activo else "disabled")

    def _cancelar(self) -> None:
        if self.convertiendo:
            self.cancelar.set()
            self.lbl_estado.configure(text="Cancelando…")
            self._estado_pill("Cancelando", WARN, WARN_BG)
            self._registrar("Solicitando cancelación…")

    def _abrir_carpeta(self) -> None:
        if self.carpeta_salida and self.carpeta_salida.exists():
            try:
                _abrir_con_visor(self.carpeta_salida)
            except Exception as exc:
                messagebox.showerror("Carpeta", f"No se pudo abrir la carpeta:\n{exc}")

    def _abrir_seleccionado(self, _evento=None) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            return
        ruta = self.archivos.get(seleccion[0])
        if isinstance(ruta, str):
            # Las URLs de YouTube se guardan como string; no se abren con el visor del sistema.
            return
        if ruta and ruta.exists():
            try:
                _abrir_con_visor(ruta)
            except Exception:
                pass

    def _cerrar(self) -> None:
        if self.convertiendo:
            if not messagebox.askyesno("Salir", "Hay una conversión en curso. ¿Cancelar y salir?"):
                return
            self.cancelar.set()
            if self.hilo is not None:
                self.hilo.join(timeout=8)
        self.raiz.destroy()

    # ------------------------------------------------------------------ Log
    def _registrar(self, mensaje: str) -> None:
        hora = datetime.now().strftime("%H:%M:%S")
        self.texto_log.configure(state="normal")
        self.texto_log.insert("end", f"[{hora}] {mensaje}\n")
        self.texto_log.see("end")
        self.texto_log.configure(state="disabled")


def _crear_raiz() -> tk.Tk:
    if DND_OK:
        try:
            return TkinterDnD.Tk()
        except Exception:
            pass
    return tk.Tk()


def _carpeta_datos() -> Path:
    """Carpeta escribible para registros (por plataforma cuando va empaquetada)."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "BPT Converter"
        elif os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ConvertidorFormatos"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "BPT Converter"
    else:
        base = BASE
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path.home()
    return base


def iniciar() -> None:
    # Si se abrió con un Python sin las librerías, relanza con el .venv.
    cv._relanzar_desde_venv()

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    raiz = _crear_raiz()
    raiz.withdraw()

    faltan = cv.dependencias_faltantes()
    if "Pillow" in faltan:
        try:
            messagebox.showerror(
                "Faltan dependencias",
                "No se encontró la librería Pillow en el Python que está "
                "ejecutando el programa.\n\n"
                f"Intérprete actual:\n{sys.executable}\n\n"
                f"Paquetes que faltan: {', '.join(faltan)}\n\n"
                "Cierra esta ventana y abre «Convertidor.bat» (Windows) o "
                "«Convertidor.command» (macOS).\n"
                "Si el problema continúa, ejecuta «instalar.bat» (Windows) o "
                "«instalar_macos.sh» (macOS) y vuelve a intentarlo.",
                parent=raiz,
            )
        except Exception:
            pass
        raiz.destroy()
        return

    raiz.deiconify()
    try:
        Aplicacion(raiz)
        if faltan:
            try:
                messagebox.showwarning(
                    "Dependencias incompletas",
                    "El programa puede abrirse, pero algunas conversiones "
                    "fallarán.\n\n"
                    f"Paquetes que faltan: {', '.join(faltan)}\n"
                    f"Intérprete: {sys.executable}\n\n"
                    "Ejecuta «instalar.bat» para completarlos.",
                    parent=raiz,
                )
            except Exception:
                pass
        raiz.mainloop()
    except Exception:
        detalle = traceback.format_exc()
        ruta_log = _carpeta_datos() / "errores.log"
        try:
            ruta_log.write_text(detalle, encoding="utf-8")
        except Exception:
            pass
        try:
            messagebox.showerror(
                "Error inesperado",
                "Ocurrió un error al iniciar la interfaz.\n\n"
                f"Se guardó el detalle en:\n{ruta_log}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    iniciar()
