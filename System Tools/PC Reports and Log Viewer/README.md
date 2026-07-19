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

One shot — no need to name individual tests:

```powershell
cd "C:\_git\HTMLPROJECTS\AI HTML TOOLBOX"
powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Invoke-FAFOSystemDiagnostics.ps1 -OpenViewer
```

Or after loading modules:

```powershell
& .\Scripts\Initialize-FAFOSession.ps1
Invoke-FAFOSystemDiagnostics -OpenViewer
```

**Grok CLI:** say *“run system diagnostics”*, *“check PC health”*, or *“refresh report library”* — agents should run `Scripts\Invoke-FAFOSystemDiagnostics.ps1`.

What it does:

1. Reads identity, CPU/GPU, disks, volumes, network, problem devices, optional event-log summary  
2. Writes reports under this machine’s FAFO device folder  
3. Rebuilds `catalog.js` / `logs-data.js` for **this host only**  
4. Prints a plain-English status summary  

## Refresh packs only

If files already exist under the device store:

```powershell
powershell -ExecutionPolicy Bypass -File ".\_pack_logs.ps1"
```

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
