# FAFO install & one-time scripts catalog

**Do not move originals.** This is an index so you never have to scrape every folder again.

- Machine catalog: [`setup/install-catalog.json`](../setup/install-catalog.json)
- Build a personal pack: [`Scripts/Build-UserSetupPack.ps1`](../Scripts/Build-UserSetupPack.ps1)
- UI: **Setup Configurator** (`Setup Configurator.html`) or `setup/Open-Setup-Configurator.bat`

Personal packs land in:

`%LOCALAPPDATA%\FAFO\user-setup-packs\<PackName>\`

---

## Workflows (presets)

| ID | Name | Typical modules |
|----|------|-----------------|
| `tech-full` | Field tech (recommended) | core, S1, Verifone, Phone Assist, system lite |
| `media-creator` | Media / VSR | core, S1, S2, media |
| `everything` | Everything | all modules |
| `minimal` | Minimal | core + S1 only |

---

## Modules (high level)

| Module | What it is |
|--------|------------|
| **core** | One-time install: Python, shortcuts, protocol |
| **server_s1** | HTML Toolbox API (Verifone, media, system) |
| **server_s2** | FAFO Local Media Tagger (Chrome extension) |
| **verifone** | Site Console, HUD, punch list, backups |
| **phone_assist** | Phone Assist Navigator |
| **media** | Media Library, VSR, comparators |
| **system_lite** | PC reports, IP profiles |
| **system_full** | LAN manager, malware UI, ghost devices |
| **reg_tweaks** | Optional Windows REG bats |
| **developer** | Git manager, pre-push |
| **investor** | Sumran investor portal |
| **icons** | Icon publish tools |

Full path list lives in JSON (including `looseScripts` not tied to a module).

---

## One-time vs every day

| When | What |
|------|------|
| **Once** | `Install FAFO Toolbox.bat` / pack `00-Install-Selected.bat` |
| **Daily** | Pack `01-Start-My-Servers.bat` + `03-Open-Launcher.bat` |
| **Stop** | `02-Stop-My-Servers.bat` |
| **Command board** | [Startup Command Board](../Startup%20Command%20Board.html) · `/startup` |

### Setup vs Startup

| Surface | Job |
|---------|-----|
| **Setup Configurator** | What to install → personal BAT pack |
| **Startup Command Board** | What is running · block auto-connect · force start/stop |

Prefs: `%LOCALAPPDATA%\FAFO\launch-prefs.json`  
- `startWithOneClick` — include in one-click  
- `blockAutoStart` — hard block auto paths (manual Force still works)

Users who pick only Verifone never get S2 start scripts forced on them.

---

## Root BAT cheat sheet (originals stay put)

| File | Role |
|------|------|
| `Install FAFO Toolbox.bat` | Primary installer |
| `SETUP (run once).bat` | Alias → installer |
| `INSTALL-PYTHON.bat` | venv only |
| `Start Servers.bat` | S1+S2 hidden + tray |
| `1-Start-HTML-Toolbox-Server.bat` | S1 only |
| `2-Start-FAFO-Local-Media-Tagger.bat` | S2 only |
| `Stop-ALL-Servers.bat` | Stop |
| `Launch-AI-HTML-Toolbox.bat` | Open app |

See catalog JSON for the complete inventory.
