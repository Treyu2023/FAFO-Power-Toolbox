# Python setup (local venv)

The toolbox backend needs **Python 3.10–3.12** (recommended **3.12**).  
All packages install into a **local virtualenv** at:

```text
AI HTML TOOLBOX\.venv\
```

This does **not** pollute your global Python / site-packages.

## Quick start (Windows)

1. Double-click **`INSTALL-PYTHON.bat`**
2. Double-click **`START SERVER.bat`** (or use Launcher → Start Server)

Full first-time setup (venv + protocol + shortcut):

```text
SETUP (run once).bat
```

## What gets installed

| Item | Purpose |
|------|---------|
| `fastapi` + `uvicorn` | Local HTTP backend (`127.0.0.87:18765`) |
| `mutagen` | Media tags |
| `Pillow` | Images / thumbs |
| `pystray` | Tray launcher |
| `psutil` | System tools |
| `pywin32` | Windows Explorer metadata (Windows only) |

Source of truth: **`requirements.txt`** (repo root).  
`server/requirements.txt` mirrors it for older scripts.

## Layout

```text
AI HTML TOOLBOX/
  INSTALL-PYTHON.bat              ← double-click installer
  requirements.txt                ← pinned dependency list
  .python-version                 ← 3.12 hint
  .venv/                          ← local venv (gitignored)
  Scripts/
    Install-PythonEnvironment.ps1
    Resolve-FAFOPython.ps1
    use-fafo-python.bat           ← used by START SERVER*.bat
  server/
    requirements.txt
    aitoolbox_server.py
```

## Manual / PowerShell

```powershell
cd "C:\_Git\repos\html\ai-html-toolbox\production"

# Create .venv + install requirements (no global pip installs)
powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Install-PythonEnvironment.ps1

# Optional: activate for an interactive shell
.\.venv\Scripts\Activate.ps1
python -c "import fastapi; print('ok')"
```

Recreate from scratch:

```powershell
.\Scripts\Install-PythonEnvironment.ps1 -Force
```

## If Python is missing

Installer tries **winget** (`Python.Python.3.12`) when needed.

Or install manually:

- https://www.python.org/downloads/ (3.12.x)
- Enable **Add python.exe to PATH**
- Re-run `INSTALL-PYTHON.bat`

```text
winget install Python.Python.3.12
```

## How launch scripts pick Python

1. **`.venv\Scripts\python.exe`** (preferred)  
2. Else `py -3.12` / `py -3`  
3. Else `python` on PATH  

They **do not** run `pip install` into the global environment on every start.  
Install or update packages only via `INSTALL-PYTHON.bat` / `Install-PythonEnvironment.ps1`.

## Optional: ffmpeg

Not a Python package. Install separately for thumbnails / VSR metadata:

```text
winget install Gyan.FFmpeg
```

(or any build that puts `ffmpeg` on PATH)
