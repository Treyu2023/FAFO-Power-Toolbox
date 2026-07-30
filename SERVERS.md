# FAFO / AI HTML Toolbox — Servers map

Two local servers. Clear names → which program needs which.

| Code | Name | Endpoint | Powers |
|------|------|----------|--------|
| **S1** | **HTML Toolbox Server** | `http://127.0.0.87:18765` | Toolbox Launcher, Media Library, VSR, File Organizer, Verifone Commander tools, System Tools, Git Manager |
| **S2** | **FAFO Local Media Tagger** | `http://127.0.0.1:8765` | FAFO Local Media Chrome extension (tags, ratings, pairs, Explorer metadata) |

S1 and S2 use different loopback addresses so they never fight each other.

## Auto-launch & tracking

- **Tray icon** keeps enabled servers alive (auto-restart if they die).
- **Launcher page** keep-alive while open.
- **Windows Startup** optional (Launcher → Launch with Windows → Save prefs).
- **Prefs** (this PC only): `%LOCALAPPDATA%\FAFO\launch-prefs.json`

## Manual Start / Stop

| Action | How |
|--------|-----|
| Start both | Launcher **▶ Start All Servers** · Desktop **Start Servers** · `0-Start-ALL-Servers.bat` |
| Start S1 only | Launcher **▶ Start S1** · `1-Start-HTML-Toolbox-Server.bat` |
| Start S2 only | Launcher **▶ Start S2** · `2-Start-FAFO-Local-Media-Tagger.bat` |
| Stop one / both | Launcher **⏹ Stop S1 / S2 / All** · tray **Stop all servers** · `Stop-ALL-Servers.bat` |

Checkboxes under each server control **auto-start** with one-click / Windows login.  
Manual Stop does **not** clear those prefs — it only stops the process.

## Paths (canonical)

| What | Path |
|------|------|
| HTML Toolbox (S1 code) | `C:\_Git\repos\html\HTML Toolbox AI tools\production` |
| FAFO Tagger (S2 code) | `C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta` |
| FAFO Chrome extensions | `C:\_Git\repos\html\fafo-chrome-extensions` |
| Per-PC Backups / Logs / Reports | `%LOCALAPPDATA%\FAFO\Devices\%COMPUTERNAME%\` |
| Exposed in toolbox folder | `Backups\` · `Logs\` · `Reports\` (junctions → device store) |

## Chrome extension load path

`chrome://extensions` → Load unpacked →

`C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS`
