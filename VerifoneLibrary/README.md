# VerifoneLibrary (repo shell)

This folder in **git** holds tools and templates only — **not** site XML backups.

## Local site data (Customer → Site → files)

Each site lives under a machine-local data root:

```text
{VerifoneSitesRoot}\
  {Customer}\
    {Site}\
      original\      sealed SMS / XML backup (never edit)
      working\       editable working tree
      scripts\       scripted edits + rollback log
      files\         extra drops, photos, misc
      punchlists\    pre-reload punch list working copies
      site.json      identity + paths for apps / prefill
```

### Why a separate folder + MKLINK?

- Backups are large and site-specific — **do not put them on GitHub**
- Desktop and laptop each pick their own data drive/folder
- Apps still get a stable path inside the repo: `VerifoneLibrary\Sites` → junction

### One-time setup (each PC)

1. Double-click **`Setup-SitesDataDirectory.bat`**
2. Pick a folder (e.g. `D:\FAFO\VerifoneSites` or accept the LocalAppData default)
3. Confirm the junction: `VerifoneLibrary\Sites` → your folder

Config is saved to:

`%LOCALAPPDATA%\FAFO\local-paths.json`

All FAFO apps should read **`VerifoneSitesRoot`** from that file (or env `FAFO_VERIFONE_SITES_ROOT`).

### PowerShell

```powershell
. .\Scripts\Initialize-FAFOSession.ps1

# Pick / set data root + create junction (each tech uses their own folder)
Set-FAFOVerifoneSitesRoot -Browse
# Example (this machine only — never hardcode others' paths in git):
# Set-FAFOVerifoneSitesRoot -Path 'C:\Users\you\OneDrive\WORK\Backups\Verifone Laptop storage\NC'

# Scan raw Sapphire SMS trees already on disk (Customer\Site\*.xml layouts)
Show-FAFOVerifoneSiteDossier
Update-FAFOVerifoneSapphireIndex
Export-FAFOVerifoneSiteDossier -Json

# Optional: formal ingest into original\working\scripts for scripted PLU edits
Add-FAFOVerifoneLibraryBackup -Path 'E:\FromSite\SMSExport' -Customer 'Acme Petro' -Location 'Main Street 12'

Show-FAFOVerifoneLibrary
Open-FAFOPath -Which VerifoneSites
```

### GUI

Open **Commander Site Console** from the Toolbox Launcher (category Verifone). With the local server running it will:

1. Sync your machine-local backup folder into a site index (SQLite)
2. Show visual cards + tech flags (MOP 28, DCR REWARDS, C-Site, pre/post snapshots)
3. Generate a **pre-filled Pre-Reload Punch List** per site (master stays untouched)
4. **Site survey** tab — network config + credentials (from `possecurity` when present) + fueling positions
5. **Aerial layout** — drag/resize pumps, tanks, manholes, building, parking, driveway; saved under `survey\site-survey.json` (local only)

Product name is **Commander**; XML namespaces may still say Sapphire historically.

### What we can pull from Commander SMS XML (tech dossiers)

| Source file | Useful fields |
|-------------|----------------|
| `supportinfo.xml` | Site ID, Service ID, help desk phone |
| `mainttelephone.xml` / `maintpostal.xml` | Store phone, postal code |
| `registercfg.xml` | Register IDs, receipt/banner name |
| `paymentcfg.xml` | MOP table — including **Mobile code 28** |
| `fuelcfg.xml` / `fuelprices.xml` | Named tanks, products, prices |
| `dcridlescreencfg.xml` | Idle soft keys — **REWARDS** |
| `cloudagentprop.xml` | C-Site / Commander Central agent flags + service override |
| `managedmodulecfg.xml` | Managed modules list |
| `popcfg.xml` | POP enabled / mode |
| `sapphireprop.xml` | Feature flags (e.g. mobile.feature.enabled) |
| `PLUs.xml` + Maintenance datasets | Items / combos / mix-match (health + pricing tools) |

### Tracked in git (this folder)

| Path | Purpose |
|------|---------|
| `Templates\Pre-Reload-Punch-List-MASTER.xml` | Punch list master |
| `Templates\Launch-PreReload-PunchList.bat` | Launcher next to master |
| `Launch-PreReload-PunchList.*` | Create working punch list copy |
| `Setup-SitesDataDirectory.*` | Choose local data root + mklink |
| `README.md` | This file |

### Not in git

| Path | Purpose |
|------|---------|
| `Sites\` | Junction to local data root |
| `{Customer}\{Site}\**` under the data root | Real backups |
| `%LOCALAPPDATA%\FAFO\local-paths.json` | Path registry |
| `Working-PunchLists\*.xml` | Orphan punch lists (prefer per-site `punchlists\`) |

### Pre-reload punch list

Run `Launch-PreReload-PunchList.bat`. Prefer saving under a site’s `punchlists\` folder once the site exists; generic copies can still land in `Working-PunchLists\` (gitignored).
