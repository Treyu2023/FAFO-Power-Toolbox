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
| `System Tools/` | Health, diagnostics, security, disk, **Admin: System Health Desk + Secrets Presence Console** |
| `Movie File Manager/` | Media library, Mismatched Source Companion (name-repair, not FlashVSR) |
| `private/` | Owner-only notes (`README.md` tracked; apps gitignored) |
| `Accounting Tools and calculators/` | Loan calc, converters |
| Games / science HTML | e.g. Empire Seed 3D, Typing Trainer, Bloodmoon |
| `docs/` | Guides, this map, multi-agent protocol, handoffs |
| `snapshots/` | Per-app HTML/JS/CSS undo copies — **newest 5 per app**, never a global pool |

---

## Recent product work (this collaboration wave)

### Owner-private finance modules (not in public git)

TaxForge, Investor Portal, and Xero proxy modules live **only on the owner machine**
(gitignored). See `private/README.md`. Do not re-add them to the public tree.

### Other HTML tools (same wave)

- `Typing Assistant Trainer.html` — WPM trainer, combos, campaign  
- `Empire Seed.html` — Civilization-style 4X, **Three.js 3D** (CDN)  

### Pro shell + QoL wave (2026-08-11)

- `shared/aitoolbox-pro.js` — every tool gets counterparts bar, `?` help, focus/density, copy report  
- Media · System · Verifone · Games · Calculators: **3 QoL upgrades each** + pair deep-links  
- Common keys in tools: `?` help · `C` first counterpart · `L` launcher · `R` report · `F` focus · `D` dense  

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
