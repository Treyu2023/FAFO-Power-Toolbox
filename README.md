# AI HTML Toolbox

Local browser-based tools for media cataloging, VSR pipeline renaming, and before/after comparison. No cloud — files stay on your machine.

**Current version:** `1.16.47`

**Deep dive (pairs, Explorer tags, moves, storage Q&A):** [`MEDIA_LIBRARY_AND_PAIRS.md`](MEDIA_LIBRARY_AND_PAIRS.md)

**Sharing / Chrome Web Store / GitHub:** [`docs/DISTRIBUTION.md`](docs/DISTRIBUTION.md) — full media+server stack is **not** a Chrome Web Store extension; GitHub (local install) is the right channel.

---

## Quick start (how to launch)

### First time on this PC (once)

1. Install **Google Chrome** if you do not have it.
2. Double-click **`Install FAFO Toolbox.bat`**
3. Follow the prompts (Python, shortcuts, optional “start with Windows”).
4. When finished, use the **Desktop** shortcuts — you should not need this folder again.

| File | Purpose |
|------|---------|
| **`Install FAFO Toolbox.bat`** | One-time installer (checks what is missing, installs only that) |
| `SETUP (run once).bat` | Same installer (compatibility alias) |

Installer creates:

- Desktop **AI HTML Toolbox** (app + servers)
- Desktop **AI HTML Toolbox - Start Servers** (recover if offline)
- Start Menu → **AI HTML Toolbox**
- `aitoolbox://` protocol so in-app **Start Server** works
- Local Python `.venv` (not global pip)

No admin / UAC required for normal install.

### Every day after that

| Action | How |
|--------|-----|
| Open the app | Desktop **AI HTML Toolbox** (or Start Menu) |
| Servers offline | Desktop **Start Servers**, tray → Recover, or in-app **▶ Start / Relaunch** |
| Servers while signed in | Launcher → *Launch with Windows*, or re-run installer and say Yes |

Backend: **`http://127.0.0.87:18765`** (toolbox + Verifone). FAFO Local Tab tags: **`127.0.0.1:8765`**. Both can run together. Servers stay **hidden** and **auto-restart** while the tray or a toolbox page is open.

**If the browser blocks Start:** use Desktop **Start Servers** or the tray icon — not the install folder.

### 3. First-time tour

- Launcher, Media Library, and Mismatched Source Companion each run a **🎓 Get Started** tour on first visit.
- Hover buttons and cards for **tooltips** — day-to-day use does not require reading this file.
- Media Library **❓ Q&A** has short answers (pairs, Explorer tags, ZIP vs USB, server start).

### 4. Typical workflow

1. **Media Library** — add watched folders, tag files, pair before/after  
   - Hover toolbar buttons for tips · **❓ Q&A** · **🎓 Get Started**  
2. **Mismatched Source Companion** (optional) — only if an upscaler scrambled names; match dumps back to originals and rename. Skip for Pinokio FlashVSR_plus.  
3. **Video / Image Comparator** — open saved pairs for side-by-side review  

Owner-only finance/investor/Xero modules (if present on your machine) are **not** part of the public repo — see `private/README.md`.

**Pairs survive folder moves** when `UP-####` tags are on the files: **Rescan** or **Relink Pairs from Tags**.  
**Do not ZIP the library for playback** — re-encode (HEVC/AV1) or cold-store on USB instead (see `MEDIA_LIBRARY_AND_PAIRS.md`).

---

## Per-app file snapshots (`snapshots/`)

Edit undo copies for each HTML tool live **in this folder**, not next to the apps and not under AppData.

| | |
|--|--|
| Where | `snapshots/<path-of-that-app>/` |
| How many | **Newest 5 per app** — each tool has its own stack |
| Why per app | Rolling back one tool must not throw away a backburner tool’s last good copies |

Agents: do not leave `*.bak*` beside live files. Copy into that app’s snapshots folder first. Details: [`snapshots/README.md`](snapshots/README.md). Sweep: `.\Scripts\Consolidate-HtmlEditBackups.ps1`.

This is separate from **version** snapshots (`1.00.00` tags) below.

---

## Version scheme (`MAJOR.FEATURES.FIXES`)

Three two-digit segments, shown as `vv.vv.vv` (e.g. `1.00.00`, `1.03.02`, `2.00.00`).

| Segment | Name | When it changes | Resets when |
|---------|------|-----------------|-------------|
| **1st** | **Major / snapshot** | You intentionally freeze a milestone and may branch or roll back | Never within a lineage — bump to `2`, `3`, … for a new snapshot era |
| **2nd** | **Features** | New capability added after the current snapshot | → `00` on every major snapshot bump |
| **3rd** | **Fixes** | Bug fix or small patch after a feature | → `00` on every major snapshot bump |

### Examples

| Version | Meaning |
|---------|---------|
| `1.00.00` | Snapshot 1 — baseline |
| `1.01.00` | First new feature after snapshot 1 |
| `1.01.03` | Same feature era, third bugfix |
| `1.05.00` | Fifth feature era since snapshot 1 |
| `1.05.01` | Patch on the 1.05 feature line (in-app server launch) |
| `2.00.00` | Snapshot 2 — features and fixes counters reset |

### Snapshot workflow (Git)

When you are satisfied with a milestone:

```bat
cd c:\_git\HTMLPROJECTS
git add -A
git commit -m "Snapshot 1.00.00 — baseline: library, VSR, UI kit, trust confirms"
git tag -a v1.00.00 -m "Snapshot 1: baseline toolbox"
```

To return to that point later: `git checkout v1.00.00`  
To branch: `git checkout -b experiment-vsr v1.00.00`

After tagging snapshot `N.00.00`, edit `VERSION` to the next feature line (e.g. `1.01.00`) before new work.

The canonical version string lives in **`VERSION`** (root of this folder). When bumping the version, update **both**:

1. `VERSION`
2. `shared/aitoolbox-version.js` (launcher reads this without a server)

The Python server reads `VERSION` on startup. The launcher subtitle shows the version at a glance (e.g. `v1.06.00`).

### Backend bind address (why not “standard” 127.0.0.1?)

| Setting | Value | Why |
|---------|--------|-----|
| Host | `127.0.0.87` | Still loopback-only (never leaves this PC), but a **dedicated** address so other local apps on `127.0.0.1` don’t collide with health checks / proxies |
| Port | `18765` | Unique high port — **frees `8765` for FAFO’s optional Explorer companion** |

Config lives in **`shared/aitoolbox-bind.json`** (Python) and **`shared/aitoolbox-config.js`** (browser). Override with env vars `AITOOLBOX_HOST` / `AITOOLBOX_PORT` if needed.

---

## Debug mode

Click **🐛 Debug** on the Launcher, Media Library, or Mismatched Source Companion (or add `?debug=1` to the URL).

- Captures errors, API calls, and user events in a floating panel
- Syncs with server log at `server/debug_runtime.log`
- **📋 Copy** the log and paste when reporting issues

---

## Changelog

### `1.06.00` — Unique bind + tool parity

- Backend moves to **`127.0.0.87:18765`** — no more fighting FAFO / other tools on `127.0.0.1:8765`
- Shared `aitoolbox-config.js` + `aitoolbox-bind.json` single source for host/port
- `AIToolboxUI.bindServerControls()` — same Start Server / status UX across tools
- System tools (Health, Converter, Disk, Hosts, Startup, Malware, LAN, Git) get config + in-page **▶ Start Server**
- Comparators + Duplicates use the new endpoint; launch bats no longer kill port 8765
- Health API returns `host`, `port`, `endpoint`

### `1.05.01` — In-app server launch

- **▶ Start Server** from Media Library, Mismatched Source Companion, File Organizer, and Launcher
- Shared `AIToolboxAPI.startServer()` — `aitoolbox://` protocol + `launch_server.hta`, wait for green
- Media Library offline banner (Setup Once / Open Folder / Console fallbacks)
- Docs + tooltips/FAQ updated for in-app start

### `1.05.00` — Pair health, smart searches, sidecars, archive

- **Pair Health** dashboard (complete / partial / broken / orphans)
- **Verify Tags** on disk + rewrite; **Pair Map** export/import JSON
- **Archive Pair** to folder/USB layout; **`.fafo.json` sidecars** (MKV-friendly)
- **Smart searches** (saved filters); pair-aware duplicate groups
- Optional auto-pair after rescan (Settings)

### `1.04.00` — Explorer metadata, pair dual-tag, relink after moves

- Write **Tags + Rating** into real files for Windows Explorer (pywin32; default ON)
- Tag autocomplete + all-tags picker; shared tags on **both** pair sides
- **Relink Pairs from Tags** (`UP-####`) after files move between folders (also auto on rescan)
- Media Library **❓ Q&A** panel + richer hover tooltips
- Doc: `MEDIA_LIBRARY_AND_PAIRS.md` (storage: re-encode vs ZIP vs USB)

### `1.03.00` — File Organizer, metadata, combined folders

- **File Organizer** — standalone rename/tag interface (table view, no thumbnail grid)
- **Rank** (★1–5), **category**, **status** metadata on every file
- **Combined Folders** — merge same-named root folders across different watched locations
- Thumbnail capture: **button on player**; keyboard shortcut disabled by default (`none`)

### `1.02.00` — Grid view, playlists, copy paths

- Media Library **List / Grid / Group** views (Windows-style thumbnail grid)
- Group by tag, folder, type, or date for batch matching
- **Copy Paths** and **Export .txt** — full disk paths for CapCut, Explorer, etc.
- Saved **playlists** — create, load, copy all paths, export

### `1.01.04` — Video preview & polish

- Video playback fix — `/api/media/file?mid=` (route ordering)
- Resizable sidebar, detail panel, and preview player
- Scan skips `$RECYCLE.BIN`; tag-rules re-apply fix
- Launcher waits for green dot; `aitoolbox://` protocol helpers

### `1.01.01` — One-click server start (Launcher)

- Launcher **▶ Start Server** — no menu, auto-waits for green dot
- `launch_tray.hta` / `launch_console.hta` — reliable Windows launchers
- Console + Server Folder fallback buttons

### `1.01.00` — Workflow UI, folder index, debug echo

- Color workflow progress bar (watch → browse → select → act)
- Folder index browser; selection colors for pairing
- Debug mode — client + server runtime echo with copy-to-clipboard

### `1.00.00` — Snapshot 1 (baseline)

- Toolbox Launcher with custom PNG icons and server status
- Media Library Manager — folders, tags, search, pairs, batch rename with confirm/trust
- Mismatched Source Companion — match/rename dumps whose names no longer match originals (not FlashVSR)
- Video & image comparators with pair loading via server
- Python backend (`127.0.0.87:18765`) — scan, rename, ffmpeg thumbs, native folder picker
- Shared UI kit — tooltips, animations, first-run tutorials, confirm + trust dialogs
- System tray launcher and optional Windows autostart
- One-click / Start Server can also start the FAFO Local Tab tagging companion (`127.0.0.1:8765`) alongside the toolbox backend (`127.0.0.87:18765`, Verifone + media)
- Servers launch **hidden** (no console windows users can close by mistake)
- **Auto-keep**: tray watchdog + in-page keepalive restart companions if they die while the toolbox is open
- Relaunch without browsing install folders: Desktop **Start Servers**, Start Menu **AI HTML Toolbox**, system **tray**, or in-app **Relaunch** — local loopback, **no UAC**
- Launcher panel: companion status, which servers start with one-click, and **Launch with Windows** toggles for servers and/or Chrome app (Startup folder shortcuts; prefs in `%LOCALAPPDATA%\FAFO\launch-prefs.json`)

---

## Project layout

```
AI HTML TOOLBOX/
├── VERSION                 ← single source of truth (vv.vv.vv)
├── shared/aitoolbox-bind.json   ← host/port for Python server
├── shared/aitoolbox-config.js   ← same host/port for browser tools
├── README.md
├── MEDIA_LIBRARY_AND_PAIRS.md
├── SETUP (run once).bat    ← protocol + desktop shortcut
├── START SERVER.bat        ← double-click fallback
├── launch_server.hta       ← used by in-app ▶ Start Server
├── Toolbox Launcher.html   ← start here
├── shared/                 ← API (incl. startServer), UI kit, IndexedDB core
├── Movie File Manager/     ← Media Library, File Organizer, Mismatched Source Companion
├── Video Tools/
├── Image tools/
└── server/                 ← Python backend
    ├── start_server.bat
    ├── protocol_start.bat
    └── aitoolbox_server.py
```

---

## Requirements

- **Browser:** Chrome or Edge (File System Access API for browser-only mode)
- **Python 3.10–3.12** (recommended **3.12**) for full backend features  
  - Use a **local venv** — do not install toolbox packages globally  
  - One-time: double-click **`INSTALL-PYTHON.bat`** (creates `.venv\`, installs `requirements.txt`)  
  - Details: [`docs/PYTHON-SETUP.md`](docs/PYTHON-SETUP.md)
- **ffmpeg** on PATH (optional but recommended for thumbnails and VSR metadata)

### Python install (first time on a PC)

```bat
INSTALL-PYTHON.bat
START SERVER.bat
```

Or full setup (venv + `aitoolbox://` protocol + desktop shortcut):

```bat
SETUP (run once).bat
```

---

## Trust & renames

Renames always show a preview first. Optionally check **Trust** to skip future prompts for that specific scope (single video, single image, batch video, batch image — separate). Mixed video+image selections always confirm. Reset trust in Media Library → **Settings**.
