# FAFO Power Toolbox / AI HTML Toolbox — Project Map

**Repo:** `Treyu2023/FAFO-Power-Toolbox` (local path: AI HTML Toolbox)  
**Updated:** 2026-08-02  

This is the “what is this whole project?” file for any agent or Grok.com expert starting cold.

---

## Mission

Local, secure **FAFO Power Toolbox** + **AI HTML Toolbox**: browser HTML tools + Python loopback server + PowerShell modules. Prefer small reversible changes. **Not** a cloud SaaS product.

Full rules: root `AGENTS.md`.

---

## Runtime

| Piece | Detail |
|-------|--------|
| Toolbox server bind | `127.0.0.87:18765` (`shared/aitoolbox-bind.json`) |
| Python | Project `.venv` only |
| Secrets | FAFO.Secrets / `%LOCALAPPDATA%\FAFO\Secrets\` — never commit |
| Device data | `%LOCALAPPDATA%\FAFO\Devices\<PC>\` — never commit other machines’ dumps |

---

## Major areas

| Path | Purpose |
|------|---------|
| `Toolbox Launcher.html` | App catalog / sections / icons |
| `shared/` | Bind config, UI CSS/JS, API helpers |
| `server/` | FastAPI-style loopback backend ops |
| `Scripts/` | PowerShell modules, session, pre-push |
| `Verifone Tools/` | Commander / field / site tooling |
| `System Tools/` | Health, diagnostics, security, disk, etc. |
| `Movie File Manager/` | Media library, VSR pipeline |
| `Business Tax Preparedness/` | **TaxForge** suite (tax readiness + Xero) |
| `Accounting Tools and calculators/` | Loan calc, converters |
| Games / science HTML | e.g. Empire Seed 3D, Typing Trainer, Bloodmoon |
| `docs/` | Guides, this map, multi-agent protocol, handoffs |

---

## Recent product work (this collaboration wave)

### TaxForge (`Business Tax Preparedness/`)

Local-first **business tax preparedness** suite, Xero-oriented:

- `TaxForge Hub.html` — suite home  
- `LedgerLink Console.html` — Xero bridge / CSV / demo  
- `Compliance Pulse.html` — readiness score  
- `Write-Off Workshop.html` — expense coding  
- `Year-End War Room.html` — close-out  
- `taxforge-shared.css` / `taxforge-shared.js`  
- Expert comms: `TAXFORGE-EXPERT-BRIEF.md`, `TAXFORGE-EMAIL-TO-EXPERTS.txt`, `TaxForge Expert Share Pack.html`  

Launcher: category **Tax**, section **TaxForge & Books**.

### Other HTML tools (same wave)

- `Typing Assistant Trainer.html` — WPM trainer, combos, campaign  
- `Empire Seed.html` — Civilization-style 4X, **Three.js 3D** (CDN)  

---

## How agents should navigate

1. `AGENTS.md` — security & layout non-negotiables  
2. `docs/MULTI-AGENT-PROTOCOL.md` — Expert ↔ Owner ↔ **Grok Build Hands** lanes  
3. `docs/agent-handoff/QUEUE.md` — what to do next  
4. Suite-specific briefs under product folders  
5. Hands = Grok Build (local); implement with tools; report in handoff LOG; Owner relays to Grok.com  

**Collaboration shape:** Grok.com Experts design → Owner relays → Grok Build executes on disk/git → Result in repo + paste-back to Experts.

---

## What must never land in git

See `.gitignore` and `AGENTS.md`: secrets, reports/logs/backups, device diagnostic packs, customer Verifone site XML, local DBs, venv, thumbnails, etc.
