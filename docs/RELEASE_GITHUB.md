# Publicar BPT Converter en GitHub

Esta guía resume los pasos para crear un repositorio limpio y profesional, y para generar el build de macOS con GitHub Actions.

## 1. Preparar el repositorio local

Desde la carpeta del proyecto:

```bash
git init
git add .
git commit -m "feat: initial release of BPT Converter"
git branch -M main
```

Antes de commitear, confirma que **no** se incluyan:

- `.venv/`
- `build/`, `build_macos/`
- `dist/`, `dist_macos/`
- `__pycache__/`
- `errores.log`

El `.gitignore` del proyecto ya cubre estos casos.

## 2. Crear el repositorio en GitHub

1. Entra a GitHub → **New repository**.
2. Nombre sugerido: `bpt-converter` o `convertidor-formatos`.
3. Descripción sugerida: `Conversor de imágenes, vídeo y audio para Windows y macOS, con GUI, CLI y descarga desde YouTube.`
4. Elige visibilidad (Public/Private).
5. **No** marques "Add README", "Add .gitignore" ni "Choose a license" si ya los tienes localmente.
6. Crea el repositorio.

## 3. Conectar y subir

Reemplaza `TU_USUARIO` y `TU_REPO`:

```bash
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

Si usas SSH:

```bash
git remote add origin git@github.com:TU_USUARIO/TU_REPO.git
git push -u origin main
```

## 4. Configurar la página del repo (para que se vea bonito)

En GitHub, en la página del repo:

- **About**: añade la descripción, topics y website si aplica.
- **Topics sugeridos**: `python`, `tkinter`, `ffmpeg`, `yt-dlp`, `file-converter`, `windows`, `macos`, `desktop-app`, `pyinstaller`.
- **Social preview**: sube una imagen (puedes usar una captura de la app).
- **Releases**: crea un release `v1.2.0` cuando tengas artefactos validados.

## 5. Compilar para macOS con GitHub Actions

1. Ve a **Actions**.
2. Selecciona **Build macOS**.
3. Haz clic en **Run workflow**.
4. Elige `mode: universal`.
5. Espera a que termine y descarga el artifact `BPTConverter-macOS-universal2`.

El artifact incluirá el `.app` y el `.dmg` universal (uso interno/pruebas, sin firma/notarización).

## 6. Crear un Release (opcional, recomendado)

1. Ve a **Releases → Draft a new release**.
2. Tag: `v1.2.0`.
3. Título: `BPT Converter 1.2.0`.
4. Describe cambios principales.
5. Adjunta artefactos validados (Windows installer/portable, macOS dmg/app si corresponde).
6. Publica el release.

## 7. Buenas prácticas

- No subas binarios grandes al código fuente salvo en Releases.
- Usa Pull Requests aunque trabajes solo; queda historial limpio.
- Etiqueta issues con `bug`, `enhancement`, `docs`, `macos`, `windows`.
- Antes de release, verifica hashes SHA-256 de los instaladores.