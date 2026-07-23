# PC Reports and Log Viewer

Graphical library for **this PC’s** diagnostics, firmware snapshots, and log packs.

## Device-local by design

| What | Where |
|------|--------|
| **Source of truth** | `%LOCALAPPDATA%\FAFO\Devices\<COMPUTERNAME>\` |
| Reports (HTML/MD/TXT/JSON) | `...\Reports\PC\` |
| FAFO markdown/raw helpers | `...\Reports\Markdown` · `...\Reports\Raw` |
| Session logs | `...\Logs\` |
| Viewer code (shared) | this folder in the git repo |
| Generated packs (local only) | `catalog.js`, `logs-data.js` (**gitignored**) |

**Desktop dumps must not ship in git.** Cloning the repo onto a laptop must not show the desktop’s health reports. Each machine collects and stores its own data.

Optional multi-PC: you *can* copy folders between devices if you want both libraries on one machine, but the default is **one device → its own store**.

## Open the library

```text
Open_Report_Library.bat
```

or double-click `index.html` (Chrome / Edge).

## Collect diagnostics (recommended)

### In the viewer (preferred)

Open `index.html` (or Launcher → **PC Reports & Log Viewer**) and use the sidebar:

| Button | What it does |
|--------|----------------|
| **▶ Run diagnostics** | Full system collect for **this PC**, then rebuilds the library |
| **↻ Refresh library pack** | Rebuilds `catalog.js` / `logs-data.js` from device store + bundled `reports\` |
| **📂 Device folder** | Opens the toolbox folder (device data is under `device-local` junction) |

Needs the toolbox server (or one-time **Setup** so `aitoolbox://diagnostics` works). No need to paste PowerShell yourself.

**Interactive HUD:** open `System Tools\PC Diagnostics HUD.html` (server on) → choose scan modules → **Run diagnostics** → click tiles for components, bottlenecks, and suggested fixes. Includes a **Simple report** view for non-technical reading.

### CLI / agents (same work)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Invoke-FAFOSystemDiagnostics.ps1 -OpenViewer
# or open the HUD after collect:
powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Invoke-FAFOSystemDiagnostics.ps1 -OpenHud
```

**Grok CLI:** say *“run system diagnostics”*, *“check PC health”*, or *“refresh report library”*.

What it does:

1. Reads identity, CPU/GPU, disks, volumes, network, problem devices, optional event-log summary  
2. Writes reports under this machine’s FAFO device folder  
3. Rebuilds `catalog.js` / `logs-data.js` for **this host only**  
4. Prints a plain-English status summary  

## Refresh packs only

Viewer button **↻ Refresh library pack**, or:

```powershell
powershell -ExecutionPolicy Bypass -File ".\_pack_logs.ps1"
```

The pack includes **device** `Reports\PC` + `Logs` + `Reports\Markdown`, and also the in-repo **`reports\`** folder so existing HTML/logs still appear if device-local is empty.

## BIOS / firmware collect (legacy helper)

```powershell
powershell -ExecutionPolicy Bypass -File ".\_collect_bios_system.ps1"
```

Output now goes to the same device-local `Reports\PC` folder (not a hard-coded `D:\OUTPUTS` path).

## Layout

```text
PC Reports and Log Viewer/     ← git (shared UI)
  index.html
  catalog.default.js           ← empty stub in git
  logs-data.default.js
  catalog.js                   ← generated, gitignored
  logs-data.js                 ← generated, gitignored
  device-local/                ← junction → %LOCALAPPDATA%\FAFO\Devices\<PC>\
  _pack_logs.ps1
  _collect_bios_system.ps1
  README.md
```

## Notes

- Works offline via `file://` when packs are generated.  
- Reports open in-page (or new tab). HTML reports use `device-local/...` relative paths when the junction exists.  
- Full BIOS menus cannot be read from Windows; SMBIOS/WMI/registry/powercfg only.  
