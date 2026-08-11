# Private owner-only modules (not published)

This folder and the gitignored paths below stay on **your machine only**.  
They are excluded from the public **FAFO-Power-Toolbox** GitHub repo.

## Local-only paths (see root `.gitignore`)

| Path | What |
|------|------|
| `Business Tax Preparedness/` | TaxForge suite + personal mileage imports |
| `Investor Portal.html` | Private investor ledger (owner + partner) |
| `server/investor_ops.py` | Investor portal backend |
| `server/xero_ops.py` | Xero token proxy / Accounting API |
| `server/_private_investor_routes.py` | Investor HTTP routes |
| `server/_private_xero_routes.py` | Xero HTTP routes |
| `private/launcher-private.js` | Extra launcher tiles + Tax section |
| Personal agent-handoff docs (`*xero*`, `*taxforge*`, `*investor*`, phase DIR notes) | Internal build notes |

## How public vs local works

1. **Public clone** — media tools, system tools, Verifone helpers, generic calculators. No TaxForge, Investor Portal, or Xero proxy modules.
2. **Your machine** — those files remain on disk; the server **optionally** loads private routes if the modules exist; the launcher loads `private/launcher-private.js` when present.

## Do not commit

- Real mileage CSVs, tax packs, investor sheets, Xero secrets, partner names in handoff docs.
- Anything under `%LOCALAPPDATA%\FAFO\` (already gitignored via secrets/device rules).

## Restore after re-clone

Copy this machine’s private files back from backup, or keep them only under this working tree (never force-add them).
