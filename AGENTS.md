# AGENTS.md — FAFO Power Toolbox

Rules for **Grok CLI**, other coding agents, and humans working in this tree.

## Mission

Local, secure FAFO Power Toolbox + AI HTML Toolbox. Prefer small, reversible PowerShell/Python changes. Do not turn this into a cloud SaaS project.

## Non-negotiable security

1. **Never commit secrets.** That includes API keys, tokens, passwords, and any decrypted secret material.
2. **Never commit** `server/security_config.json` with a real key. Prefer non-secret flags only (e.g. `has_abuse_ch_key`). Real keys live in DPAPI under `%LOCALAPPDATA%\FAFO\Secrets\`.
3. **Always use FAFO.Secrets** (`Scripts\Modules\FAFO.Secrets`) for secret store/load:
   - `Set-FAFOSecret` / `Set-FAFOSecretFromPlainText`
   - `Get-FAFOSecret` / `Test-FAFOSecret`
   - `Initialize-FAFOEnvironment`
4. **Never print secret values** in reports, logs, status output, commits, or chat. Presence checks only (`Test-FAFOSecret`, `has_*` flags).
5. **Secret load order** for abuse.ch / similar: process env → DPAPI store → empty. Do **not** fall back to JSON for the real key.
6. Before any private remote push: run `Scripts\Invoke-FAFOPrePushCheck.ps1`.

## Code layout

| Area | Prefer |
|------|--------|
| PowerShell modules | `Scripts\Modules\FAFO.*\` |
| Session bootstrap | `Scripts\Initialize-FAFOSession.ps1` |
| Shared paths/reports/logs | `FAFO.Toolbox` helpers |
| Python backend | `server\` (loopback only) |
| Browser tools | existing HTML + `shared\` |

- Prefer **extending modules** over one-off scripts when a helper will be reused.
- Keep modules focused; do not dump unrelated utilities into `FAFO.Toolbox`.

## What must stay out of git

Do not add, stage, or commit:

- `Reports\`, `Logs\`, `Backups\`, `terminals\`
- `%LOCALAPPDATA%\FAFO\Secrets\` (or any `Secrets\` folder)
- `server\security_config.json` with secrets
- `*.db`, `*.log`, thumbnails, quarantine, `__pycache__`
- `.env` and credential files

Use `.gitignore` as the source of truth. If something sensitive appears, fix ignore rules and scrub history before pushing.

## Runtime / bind conventions

- Toolbox server bind: **`127.0.0.87:18765`** (see `shared\aitoolbox-bind.json`).
- Do **not** move it back to `127.0.0.1:8765` — that conflicts with FAFO companion.
- Secrets and machine-local state belong under `%LOCALAPPDATA%\FAFO\`, not OneDrive if avoidable.

## Safety & destructive actions

**Confirm with the user before:**

- Deleting files/folders outside disposable report/log cleanup
- `git push --force`, history rewrite, or remote repo creation/deletion
- Registry/system changes, elevated cleaners, mass device removal
- Rotating or overwriting secrets without an explicit request
- Packaging/publishing a distributable that might include data dirs

Prefer:

- `Backup-FAFOItem` / `Move-FAFOItem` (backup + no overwrite without `-Force`)
- `Remove-FAFOReport` with `-WhatIf` first when cleaning reports
- Explicit paths; avoid broad `Remove-Item -Recurse` at toolbox root

## Daily workflow (agents)

```powershell
& ".\Scripts\Initialize-FAFOSession.ps1"
Test-FAFOHealth
# work...
& ".\Scripts\Invoke-FAFOPrePushCheck.ps1"
```

Reports: `Write-FAFOReport` / `Write-FAFOStatusReport` → `Reports\Markdown` + optional `Reports\Raw`.

## PR / commit hygiene

- Small commits with clear intent.
- Do not commit generated reports “for convenience.”
- Do not embed absolute machine paths in committed config unless required and already project convention.
- After secret-related work, double-check `git status` and the pre-push check.

## When unsure

Ask the user. Local toolbox > clever automation that risks data loss or secret leakage.
