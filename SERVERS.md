# FAFO servers — independent products & lifecycles

| Code | Product | Endpoint | **Starts when** | **Stops when** |
|------|---------|----------|-----------------|----------------|
| **S1** | **HTML Toolbox Server** | `http://127.0.0.87:18765` | You open **AI HTML Toolbox** | Tray → **Sleep S1** (or Stop) |
| **S2** | **Ultimate Tab / Local Media Tagger** | `http://127.0.0.1:8765` | **Google Chrome** is running | Chrome exits (auto) · or tray **Sleep S2** |

They share a tray/watchdog only for convenience. They are **not** the same app.

## Why this split

- Toolbox tools need **S1** only.
- Chrome Ultimate Tab needs **S2** only.
- Running both 24/7 wasted RAM/CPU when you were using neither product.

## Day-to-day use

| You want… | Do this |
|-----------|---------|
| Use HTML Toolbox | Launch **AI HTML Toolbox** (desktop / tray **Open HTML Toolbox**) → **S1 starts** |
| Done with Toolbox | Tray → **S1 · HTML Toolbox** → **💤 Sleep S1** |
| Use Ultimate Tab | Open **Google Chrome** → tray/watchdog starts **S2** automatically |
| Done with Chrome | Close Chrome → **S2 stops** automatically (frees resources) |
| Force S2 without waiting | Tray → **S2** → Start / wake · or `2-Start-FAFO-Local-Media-Tagger.bat` |

## Tray menu (taskbar)

- **Open HTML Toolbox (starts S1)**
- **S1 · HTML Toolbox (with Toolbox)** → Start / Sleep
- **S2 · Ultimate Tab (with Chrome)** → manual Start / Sleep block
- **Apply lifecycle now** — align S1/S2 with host apps
- **Lifecycle auto** — keep the binding on/off
- **Sleep both & quit tray**

## Prefs (this PC)

`%LOCALAPPDATA%\FAFO\launch-prefs.json`

| Key | Meaning |
|-----|---------|
| `sessions.toolboxActive` | Toolbox is “open” → auto-heal S1 |
| `serversSleeping.toolboxServer` | User slept S1 — never auto-start until Wake |
| `serversSleeping.fafoMetaServer` | User slept S2 — never auto-start with Chrome until Wake |
| `startWithOneClick.toolboxServer` | Allow S1 lifecycle at all |
| `startWithOneClick.fafoMetaServer` | Allow S2 lifecycle with Chrome |

## Manual bats

| Bat | Effect |
|-----|--------|
| `Launch-AI-HTML-Toolbox.bat` | S1 only + Chrome app window for Toolbox |
| `1-Start-HTML-Toolbox-Server.bat` | S1 only (manual) |
| `2-Start-FAFO-Local-Media-Tagger.bat` | S2 only (manual override) |
| `0-Start-ALL-Servers.bat` / `Start Servers.bat` | Respects lifecycle (S1 needs session / S2 needs Chrome) |
| `Stop-ALL-Servers.bat` | Sleep both (sticky) |

## Paths

| What | Path |
|------|------|
| HTML Toolbox (S1) | `C:\_Git\repos\html\HTML Toolbox AI tools\production` |
| Ultimate Tab tagger (S2) | `C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta` |
| Chrome extension load | `C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS` |

## Watchdog

Still optional. It **does not** force both servers always-on. It only:

1. Keeps **S1** up while toolbox session is active and not sleeping  
2. Keeps **S2** up while Chrome is running and not sleeping  
3. Stops **S2** when Chrome exits  
4. Leaves a tray icon so you can Sleep / Wake / Open Toolbox  
