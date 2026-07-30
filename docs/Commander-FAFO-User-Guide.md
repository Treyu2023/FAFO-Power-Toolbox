# FAFO Commander Tools — Feature Guide & User Manual

**Product:** FAFO AI HTML Toolbox · Verifone / Commander suite  
**Audience:** Field techs, store support, reload specialists  
**Scope:** Commander Site Console, Phone Assist Navigator, Status HUD, PLU Editor, Import-Export shell, TLS phone trees, SSH Manager reset, tech desk  
**Last updated:** 2026-07-28  

> **Local / confidential:** These tools may store Manager passwords, POS passwords, and fleet `maint` SSH secrets on **this Windows PC only** under `%LOCALAPPDATA%\FAFO\`. Do not commit secrets to git or email unredacted `SITE-INFO.md` files.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Architecture & data locations](#2-architecture--data-locations)
3. [Commander Site Console](#3-commander-site-console)
4. [Tech desk (password dashboard, preflight, field pack)](#4-tech-desk)
5. [Liferaft & Manager letter-cycle passwords](#5-liferaft--manager-letter-cycle-passwords)
6. [Journal workflow](#6-journal-workflow)
7. [PLU Editor (bulk edits & safe originals)](#7-plu-editor)
8. [Import-Export shell](#8-import-export-shell)
9. [Manager reset via SSH (`resetpw manager`)](#9-manager-reset-via-ssh)
10. [SITE-INFO.md & field packs](#10-site-infomd--field-packs)
11. [Phone Assist Navigator](#11-phone-assist-navigator)
12. [Veeder-Root TLS (250/300/350/400/450)](#12-veeder-root-tls)
13. [Aerial layout / topography](#13-aerial-layout--topography)
14. [Site survey & photo OCR](#14-site-survey--photo-ocr)
15. [Commander Status HUD](#15-commander-status-hud)
16. [Security & secrets](#16-security--secrets)
17. [Troubleshooting](#17-troubleshooting)
18. [API reference (tech helpers)](#18-api-reference-tech-helpers)
19. [File map](#19-file-map)

---

## 1. Quick start

### 1.1 Launch

1. Run **`START SERVER.bat`** (or **▶ Start Server** inside the Console).  
2. Open **Commander Site Console** from:
   - Toolbox Launcher, or  
   - `http://127.0.0.87:18765/toolbox/Verifone%20Tools/Commander%20Site%20Console.html`
3. Click **📁 Watched folders…** and add your Commander SMS backup root  
   (e.g. `…\Verifone Laptop storage\NC`).
4. Click **↻ Sync folders** (or wait for auto-scan on load).
5. Select a site card → use tabs: Liferaft, Journal, PLU Editor, Import-Export, etc.

### 1.2 Companion apps

| App | Use when |
|-----|----------|
| **Commander Site Console** | Backups, Liferaft, PLU, IE, tech desk, SITE-INFO |
| **Phone Assist Navigator** | Talking a cashier/manager through CSR / TLS / SSH menus |
| **Commander Status HUD** | Live ping / ports / credential probe |
| **Pre-Reload Punch List** | CITGO-style reload checklist |

### 1.3 First-time checklist (new laptop)

- [ ] Python venv / FAFO setup complete (`SETUP (run once).bat` if needed)  
- [ ] Server starts and health pill is green  
- [ ] Watched folder points at your real backup tree  
- [ ] Fleet `maint` SSH secret seeded (or paste current fleet password into fleet-tech-defaults)  
- [ ] Open this guide from **📖 Help** in the Console  

---

## 2. Architecture & data locations

### 2.1 Local toolbox server

- **Bind:** `127.0.0.87:18765` (device-local, not the store Commander)  
- **Health:** `GET http://127.0.0.87:18765/api/health`  
- **Static tools:** `/toolbox/...` serves HTML from the toolbox root  

### 2.2 Where data lives

| Data | Location |
|------|----------|
| Watched backup folders | `%LOCALAPPDATA%\FAFO\local-paths.json` |
| Commander login profiles (DPAPI passwords) | `%LOCALAPPDATA%\FAFO\commander-profiles.json` + `Secrets\commander_*.bin` |
| Master site Liferaft | `%LOCALAPPDATA%\FAFO\site-profiles\*.json` |
| Fleet SSH `maint` password | `%LOCALAPPDATA%\FAFO\fleet-tech-defaults.json` (**not git**) |
| Staged PLU edits / safe copies | `%LOCALAPPDATA%\FAFO\backup-safe\<siteId>\` |
| Per-export survey | `<export>\survey\site-survey.json` |
| SITE-INFO.md | `<export>\SITE-INFO.md` |
| Field packs | `<export>\survey\field-packs\field_*\` |
| This user guide | `docs\Commander-FAFO-User-Guide.md` |

### 2.3 What is *not* pushed automatically

Per Verifone practice and FAFO design:

- **Network / LAN / host routes** — reference only; apply in Config Client manually.  
- **Fuel / DCR / pump programming** — not auto-pushed.  
- **PLU edits** apply to **local SMS backup XML** first; live Commander needs **Import-Export** (or shell tools).  

---

## 3. Commander Site Console

### 3.1 Site list

- Groups the same physical store’s software snapshots (latest on top).  
- Search: customer, site id, phone, equipment cues.  
- Drag the splitter to widen the detail pane.  

### 3.2 Tabs (per site)

| Tab | Purpose |
|-----|---------|
| **🛟 Liferaft** | Master profile for the store (all versions): identity, Manager cycle, SSH, network, emergency |
| **Overview** | KPIs, tech desk (preflight, playbook, field pack, SSH reset, SITE-INFO) |
| **Equipment** | Dispensers, CRIND/DCR, positions, employees from backup |
| **Network** | From dossier/survey merge |
| **Journal** | Live T-log via CGILink + receipt → PLU stage |
| **PLU Editor** | Filter, multi-select, bulk price/%/EBT, protected original |
| **Import-Export** | CGILink export/import of selected databases; NEW vs LEGACY tool catalogs |
| **Site survey** | Packs: site / network / POS / forecourt + photo OCR |
| **Aerial layout** | Map topography; seed from backup |
| **XML files** | Browse export XMLs |

### 3.3 Help inside the app

- Toolbar **📖 Help / User Guide** opens this manual (in-app viewer + “open file” / “open folder”).  
- File is also readable at:  
  `C:\_git\HTMLPROJECTS\AI HTML TOOLBOX\docs\Commander-FAFO-User-Guide.md`

---

## 4. Tech desk

Always-visible **Manager passwords** strip under the header:

- Overdue / ≤7 days / ≤14 days / missing change date  
- Click a chip to filter the site list  

### 4.1 Overview → Tech desk tools

| Control | What it does |
|---------|----------------|
| **⚡ Preflight** | TCP 80/443/22/8080 (+ CGILink validate if Liferaft has Manager password) |
| **🆘 Playbook** | Dead-Manager recovery order for this site |
| **📦 Field pack** | Writes SITE-INFO + playbook + OTP card under `survey\field-packs\` |
| **📝 Log call** | Appends after-call note to Liferaft emergency notes |
| **OTP cheat card** | Config OTP vs C-Site vs Help Desk token |
| **🔑 resetpw manager** | SSH maint → temp Manager password (see §9) |
| **📄 Write SITE-INFO.md** | Full site markdown into backup root |

---

## 5. Liferaft & Manager letter-cycle passwords

### 5.1 Fleet default (~90% of sites)

| Piece | Rule |
|-------|------|
| Shape | **1 capital letter A–E** + **digit base** |
| Position | Usually **leading**: `B6652990`, `A123456` |
| Base | **Per site** (stays put) |
| Letter | Cycles **A → B → C → D → E → A** |
| Why 5 letters | Commander blocks **last 4** passwords |
| Interval | Forced change ~**every 90 days** after last change |

**On-site prompt flow**

1. Login with **current**  
2. Forced change → re-enter **current**  
3. Enter **new** (next letter + same base)  
4. Re-enter **new** to confirm  

Then in Liferaft: set **last changed** date (or **Changed today**) and/or **Rotate letter**.

### 5.2 POS / cashier passwords

- Come from `possecurity.xml` (gemcomPasswd decode when possible).  
- **Do not** use the Manager A–E 90-day rule.  
- Listed fully in **SITE-INFO.md** (local only).  

### 5.3 Last-change date

Techs often write the change date at the site. Liferaft supports:

- Date picker **Last changed (site date)**  
- **Save change date** → recalculates days remaining  
- **Changed today**  

---

## 6. Journal workflow

**Trunk:** Connect → Periods → Get Data → pick transaction → click line → stage backup PLU edits → review → apply local.

1. **Host** = store Commander LAN IP (not 127.0.0.87).  
2. **User** usually `Manager` + site password (Liferaft may prefill).  
3. **OTP** if required (register CSR → Maintenance → Config OTP).  
4. Prefer a **dated shift** period, not “Current” (Current is often journal noise without $).  
5. **Sales / money only** checkbox hides pure journal events.  
6. **Live filters** re-apply as you type (Register, Emp, UPC, text, amounts, etc.).  
7. Click a receipt line → **Backup PLU** panel → Stage → Review → **Apply to backup**.  

Edits are **local SMS backup only** until Import-Export (or push workflow).

---

## 7. PLU Editor

### 7.1 Browse & select

- Live filter: description / UPC / department / p-code / EBT  
- Checkboxes, Select page, Select all matches, Clear  

### 7.2 Bulk operations

| Operation | Example |
|-----------|---------|
| Price · % | Marlboro +10% |
| Price · $ amount | +1.00 |
| Set field | department, description, active, … |
| **EBT On / Off** | `foodStamp` Y/N on checked rows |

Uncheck rows to **exclude** before Stage.

### 7.3 Stage → Verify → Apply

1. **Stage bulk**  
2. **Verify all** (or review one-by-one in Journal review UI)  
3. **Apply to backup** → writes `PLUs.xml` in the export folder  

### 7.4 Protected original & last 3 finalized

- First Apply snapshots a **protected original** (not auto-overwritten).  
- **Restore original** anytime (fail-safe).  
- **Sign off / Finalize** archives that original into history (**keep last 3**), re-baselines from current working file.  
- Pre-apply safe copies also kept ~15 days under `backup-safe`.  

### 7.5 Live Commander

After Apply: use **Import-Export** tab (or official Verifone utility) to push SMS config.

---

## 8. Import-Export shell

### 8.1 Two official utilities

| Generation | Executable | Use when |
|------------|------------|----------|
| **NEW (Base 55+)** | `ImportExportUtility.exe` | Modern Commander |
| **LEGACY** | `SMSImportExport.exe` (x86) | Older bases / packs |

FAFO can **Launch** either GUI, or drive **CGILink** export/import of selected databases with path control under watched roots.

### 8.2 Login

Always **site-specific Manager** (same as Config Client).  
Site label field = store name for folders (e.g. Quick N Easy 1) — **never** put the password there.

### 8.3 Workflow

1. Login (Manager + OTP if needed)  
2. Choose tool catalog (NEW / LEGACY)  
3. Select databases or preset (PLU core, merchandise, fuel, payment, site info)  
4. Set **export/import folder** under a FAFO watched root  
5. **Export → folder** or **Import → Commander**  

---

## 9. Manager reset via SSH

### 9.1 Secrets

| Item | Default / note |
|------|----------------|
| User | `maint` |
| Password | Stored in `fleet-tech-defaults.json` on **this PC only** |
| Port | 22 |
| Reset command | `resetpw manager` |

### 9.2 Prerequisites

- Laptop on **store LAN** (same switch as when loading SMS)  
- **Help Desk login + token** enabled on Commander when the site requires it  
- Fleet `maint` password still valid for that software generation  

### 9.3 Automated tool (Site Console Overview)

1. Enter Commander host  
2. Set target letter (e.g. **A**) + base (e.g. **6652990**) → preview **A6652990**  
3. Click **resetpw manager**  
4. Copy **temporary** Manager password from the yellow box  
5. Config Client → Manager + temp → **forced change** to target (e.g. A6652990)  
6. **Confirm final password in Liferaft** (sets letter + days remaining)  

### 9.4 Manual PuTTY SOP

Also in **Phone Assist → SSH / resetpw** (copy full SOP).  
Host field editable (default hint often `192.168.31.11`).

---

## 10. SITE-INFO.md & field packs

### 10.1 SITE-INFO.md

Written next to SMS XMLs:

`<export>\SITE-INFO.md`

Includes:

- Snapshot identity  
- Managed users + Manager letter / days / next due  
- POS users + passwords (no 90-day rule)  
- SSH recovery section  
- Network (survey/liferaft — usually not in backup)  
- Forecourt equipment, tanks, products  
- Topography notes  

### 10.2 Field pack folder

`survey\field-packs\field_YYYYMMDD_HHMMSS\`

| File | Purpose |
|------|---------|
| `SITE-INFO.md` | Full site cheat sheet |
| `DEAD-MANAGER-PLAYBOOK.md` | Recovery order |
| `OTP-CHEAT-CARD.md` | OTP / token scripts |
| `PASSWORD-STATUS.json` | Letter / days snapshot |
| `README.md` | Pack usage |

Treat packs with passwords as **USB / local only**.

---

## 11. Phone Assist Navigator

**Path:** `Verifone Tools\Phone Assist Navigator.html`  
**Launcher:** Toolbox · Phone Assist · or Console toolbar **📞 Phone Assist**

### 11.1 Design goal

Walk a **non-technician** (cashier / manager) through menus **in the same order they see**, with:

- Mock screen  
- Path breadcrumb + tree  
- **Say to the person on the phone** (copy button)  
- Tech notes (you don’t read out loud)  

### 11.2 Modules

| Tab | Content |
|-----|---------|
| **Register / CSR** | Sales → CSR Functions → Maintenance → Config OTP, price check/override, no sale |
| **Commander / Config** | Login, OTP, users, network (view-only coaching), SSH bridge |
| **Veeder TLS** | Model picker 3xx vs 450 · line test re-enable · results · Favorites |
| **SSH / PuTTY** | Full recovery SOP + `resetpw manager` |

---

## 12. Veeder-Root TLS

Documentation also on **[veeder.com](https://www.veeder.com)** (operator tips, manuals) and often under your OneDrive `WORK\_Documentation\_Gilbarco\Veeder root\`.

### 12.1 Families

| Family | Models | UI |
|--------|--------|-----|
| **3xx** | TLS-250, 300, 350 | Keys: **MODE · FUNCTION · STEP · PRINT · ALARM/TEST** |
| **4xx** | TLS-400, 450, 450PLUS, TLS4 | **Touch**: Menu · Diagnostics · Favorites · Alarm bar |

### 12.2 Highest-value phone call: line re-enable

After **GROSS LINE FAIL / PLLD SHUTDOWN**, if the line is actually OK:

**3xx**

1. All nozzles hung up  
2. MODE → Operating or DIAG MODE  
3. FUNCTION → **PRESSURE LINE LEAK** (or WPLLD)  
4. STEP → **3.0** / start test · ENTER  
5. PASS → ALARM/TEST · try quiet pump  
6. FAIL → stop looping; dispatch  

**450 / 450PLUS**

1. All nozzles hung up  
2. Menu → Diagnostics → PLLD → **Manual Test** → Actions → **Start 3.0**  
3. Then **Menu → Diagnostics → PLLD → 3.0 gph Tests** to **watch results** (newest PASS/FAIL)  
4. Alarm bar **twice** · confirm no shutdown · try quiet pump  
5. Save **Favorites**: Manual Test + 3.0 gph Tests for next call  

**Favorites** (450) make the next non-tech call much faster: Home → Favorites → saved screens.

### 12.3 Safety on the phone

- No Setup programming over the phone  
- Don’t spam failed 3.0 tests  
- 3.0 = gross re-enable; 0.2 / 0.1 are different compliance paths  

---

## 13. Aerial layout / topography

**Aerial layout** tab:

- **🌱 Seed from backup** — pumps, tanks, registers, CRIND palette from SMS equipment  
- Drag / resize / colors · **Save layout** into survey  
- Force re-seed only if you confirm overwrite  

Used with SITE-INFO topography section for site maps.

---

## 14. Site survey & photo OCR

Packs: **Site · Network · POS · Forecourt**

- Fill what is **not** in SMS (true LAN IPs, routes, pump FW, photos).  
- Photo OCR (EZ Mode) can propose field fills when engine available.  
- Share packs: redacted (review before email) vs full (local/USB).  

---

## 15. Commander Status HUD

Live probe tool:

- Ping / ports / HTTP discovery  
- Credential test (CGILink)  
- Import-Export utility detect/launch  
- OTP guidance  

Use when validating reachability before Journal or IE.

---

## 16. Security & secrets

| Do | Don’t |
|----|--------|
| Store secrets under `%LOCALAPPDATA%\FAFO\` | Commit `fleet-tech-defaults.json` or filled SITE-INFO to public git |
| Use Liferaft per store | Share temp `resetpw` passwords in tickets/email |
| Redact share packs before email | Auto-push network/fuel programming |
| Treat field packs as sensitive | Guess Manager passwords in a spray pattern |

---

## 17. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Server pill red | ▶ Start Server · check 127.0.0.87:18765 · `START SERVER.bat` |
| No sites | Watched folders · Sync · confirm SMS markers (PLUs.xml, poscfg.xml, …) |
| Journal empty $ | Pick dated shift, not Current · Sales filter on |
| CGILink OTP | Phone Assist CSR → Config OTP · 4-digit from register |
| Import-Export auth fail | Site Manager password · OTP · correct host |
| SSH fails | Help Desk login + token · LAN cable · fleet maint password rotated? |
| PLU Apply but no live change | Apply is local backup only — IE Import to Commander |
| TLS line still down after PASS | Other alarms (FUEL OUT, sensor, etc.) · don’t spam tests |
| Password dashboard empty | Need Liferaft profiles with letter-cycle data |

---

## 18. API reference (tech helpers)

Base: `http://127.0.0.87:18765/api`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/verifone/tech/password-dashboard` | Rotation due list |
| GET | `/verifone/tech/dead-manager-playbook` | Recovery card |
| GET | `/verifone/tech/otp-card` | OTP scripts JSON |
| POST | `/verifone/tech/preflight` | Connectivity checks |
| POST | `/verifone/tech/field-pack` | One-click pack |
| POST | `/verifone/tech/log-call` | After-call Liferaft note |
| POST | `/verifone/ssh/reset-manager` | `resetpw manager` via maint |
| POST | `/verifone/ssh/confirm-manager-password` | Final A+base in Liferaft |
| GET | `/verifone/fleet-tech-defaults` | Local fleet SSH defaults |
| GET | `/verifone/docs/user-guide` | This manual as Markdown |
| GET | `/toolbox/docs/Commander-FAFO-User-Guide.md` | Static file serve |

PLU / backup / journal / IE endpoints are under `/verifone/backup/*`, `/verifone/journal/*`, `/verifone/sms-ie/*`, `/verifone/live/*`.

---

## 19. File map

```
AI HTML TOOLBOX/
  docs/
    Commander-FAFO-User-Guide.md     ← this manual
  Verifone Tools/
    Commander Site Console.html
    Phone Assist Navigator.html
    phone-assist-tls-trees.js
    Commander Status HUD.html
    Pre-Reload Punch List.html
  server/
    tech_ops.py                      ← dashboard, playbook, preflight, field pack
    commander_ssh_ops.py             ← resetpw manager
    fleet_tech_ops.py                ← local maint secret
    site_info_ops.py                 ← SITE-INFO.md
    backup_edit_ops.py               ← PLU stage/apply/originals
    sms_ie_ops.py                    ← Import-Export shell
    site_profile_ops.py              ← Liferaft + letter cycle
    journal_ops.py
    commander_live.py
    aitoolbox_server.py
  START SERVER.bat
  Launch-AI-HTML-Toolbox.bat
```

---

## Appendix A — Suggested daily tech workflow

1. Start server · open Console · glance **password desk** for overdue sites.  
2. On site: **Preflight** host · Journal if needed · PLU Editor if merch fixes.  
3. Phone call: **Phone Assist** (CSR OTP or TLS line re-enable + results + Favorites).  
4. Manager locked: **Playbook** → **resetpw manager** → force-change to letter+base → Confirm Liferaft.  
5. Before leaving: **Write SITE-INFO** or **Field pack** · **Log call**.  

---

## Appendix B — Glossary

| Term | Meaning |
|------|---------|
| CGILink | Sapphire/Commander HTTP CGI portal (validate, config cmds, journal) |
| SMS backup | XML export set (PLUs, poscfg, fuelcfg, …) from Import-Export |
| Liferaft | FAFO master per-store profile (all software versions) |
| PLLD | Pressurized Line Leak Detection (Veeder) |
| Gross 3.0 | 3.0 gph line test — common phone re-enable after fail |
| Config OTP | 4-digit register-generated code for Config Client / CGILink |
| maint | Linux shell user for advanced Commander recovery |

---

*End of FAFO Commander Tools User Guide. For product docs beyond FAFO, see Verifone Commander Help and [veeder.com](https://www.veeder.com) TLS operator materials.*
