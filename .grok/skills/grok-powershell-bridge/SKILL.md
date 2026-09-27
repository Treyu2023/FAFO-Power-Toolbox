---
name: grok-powershell-bridge
description: "Bidirectional bridge so Grok Build and Grok PowerShell talk directly over loopback HTTP plus a file mailbox. Use when the user wants Grok Build to talk to PowerShell, send host commands through a persistent PS session, start the Grok PS bridge, install the skill into the toolbox, or run /grok-powershell-bridge."
type: tool
lifecycle: active
when-to-use: Grok Build talk to PowerShell, Grok PowerShell, start the PS bridge, send a host command from Grok Build, mailbox between grok and pwsh
user-invocable: true
argument-hint: "[start|status|say <text>|exec <command>|install]"
metadata:
  author: FAFO Petro Services
  short-description: Direct Grok Build <-> Grok PowerShell channel
---

# Grok PowerShell Bridge — Direct Build <-> Host PS

Grok Build (TUI / `grok -p`) and Grok PowerShell (persistent host `pwsh`) share one local channel. Do not spawn a fresh `pwsh -c` for every ask once the bridge is up. Do not print secrets. Bind loopback only.

## Roles

| Side | Who | How it talks |
|---|---|---|
| Grok Build | coding agent in this repo | `scripts/grok_ps.py` or `Scripts/Invoke-GrokPs.ps1` |
| Grok PowerShell | host `pwsh` sidecar | `Scripts/Start-GrokPsBridge.ps1` |

Default bind: `http://127.0.0.87:17321/` (toolbox loopback family). Fallback: `http://127.0.0.1:17321/`. File mailbox: `%LOCALAPPDATA%\FAFO\GrokPsBridge\` and `%USERPROFILE%\.grok\ps-bridge\`.

## Workflow

1. **Install once** (copies this skill into `%USERPROFILE%\.grok\skills\` so every Grok Build session finds it):
   ```powershell
   & ".\Scripts\Install-GrokPsBridge.ps1"
   ```
2. **Start the PowerShell sidecar** (leave the window open):
   ```powershell
   & ".\Scripts\Start-GrokPsBridge.ps1"
   ```
3. **From Grok Build**, check then talk:
   ```powershell
   & ".\Scripts\Invoke-GrokPs.ps1" -Action status
   & ".\Scripts\Invoke-GrokPs.ps1" -Action say -Text "Bridge check from Grok Build"
   & ".\Scripts\Invoke-GrokPs.ps1" -Action exec -Command "Get-Date; $PSVersionTable.PSVersion"
   ```
   Python equivalent (same repo):
   ```bash
   python .grok/skills/grok-powershell-bridge/scripts/grok_ps.py status
   python .grok/skills/grok-powershell-bridge/scripts/grok_ps.py say "hello from build"
   python .grok/skills/grok-powershell-bridge/scripts/grok_ps.py exec "Get-Location"
   python .grok/skills/grok-powershell-bridge/scripts/grok_ps.py inbox
   ```
4. **From Grok PowerShell back to Build**, write a `say`/`result` into the outbox (the sidecar does this on `/say` and `/exec`). Grok Build must poll `inbox` / `outbox` until the turn is complete.

If HTTP is down, still use the mailbox. Write a JSON file into `inbox\` (to PS) or `outbox\` (to Build). See `references/protocol.md`.

## Rules

1. Confirm with the user before `exec` that deletes, force-pushes, changes the registry, rotates secrets, or runs elevated.
2. Never put API keys, tokens, or DPAPI secret values on the wire. Presence checks only.
3. Prefer this bridge for host work (PATH, Windows services, toolbox scripts, `Initialize-FAFOSession.ps1`). Use Grok Build's own tools for repo file edits.
4. If `status` is unreachable, start the sidecar. Do not invent a second bind address.
5. After install, tell the user to restart Grok Build or run `grok inspect` so the skill appears as `/grok-powershell-bridge`.

## Common Issues

| Symptom | Fix |
|---|---|
| Connection refused on 17321 | Start `Scripts/Start-GrokPsBridge.ps1`. Confirm nothing else owns the port. |
| 127.0.0.87 fails | Sidecar already falls back to 127.0.0.1. Re-run `status` and use the printed base URL. |
| Skill missing in TUI | Run install, then `grok inspect`. Skill must live under `.grok/skills/` or `~/.grok/skills/`. |
| Exec hangs | Default timeout 60s. Re-run with `-TimeoutSec`. Check `last-error.json` in the mailbox root. |
| Messages vanish | Poll both `inbox` and `outbox`. Consumed files move to `archive\`. |
