---
name: grok-crew-router
description: "Route a task to the best Grok Bot on the crew, or queue it for Commander when several could own it. Use when the user wants bots to work together, pick the best bot, open Grok Crew Router, or dispatch through the PowerShell bridge."
type: orchestrator
lifecycle: active
when-to-use: Grok Bots work together, pick the best bot, crew router, dispatch to Commander, rank bots for a task
user-invocable: true
argument-hint: "[rank <task>|queue <task>|status]"
metadata:
  author: FAFO Petro Services
  short-description: Pick the best Grok Bot and queue the rest
---

# Grok Crew Router — Best Bot For The Task

Do not create a second Commander. The live orchestrator is **Commander** (`fb2e38d1-0598-404d-846a-1025ce1ab222`). This skill + the toolbox app rank the roster and put work on the same loopback bridge as Grok PowerShell.

## Pick rules

1. Load roster from `assets/roster.json` or `%LOCALAPPDATA%\FAFO\GrokPsBridge\roster.json`.
2. Score each bot: keyword hits on name/title/role/keywords + idle preference.
3. **One clear winner** (score gap ≥ 2 and not a standing duty): dispatch that bot.
4. **Standing duty / "from now on" / two or more could own it**: do not assign. Name the candidates, say Commander is the default owner, ask the user.
5. Never hand the same task to a bot and also do it here.

## How to talk

```powershell
& ".\Scripts\Invoke-GrokCrew.ps1" -Action rank -Text "fix the Git UI zoom bug"
& ".\Scripts\Invoke-GrokCrew.ps1" -Action queue -Text "crew: sync milestone and check idle bots"
```

Toolbox app: `Developer Tools/Grok Crew Router.html` (needs the PS bridge running).

Bridge routes: `GET /bots/roster`, `POST /bots/route`, `POST /bots/jobs`, `GET /bots/jobs`.

Queued jobs land in the mailbox `outbox` as `kind: bot-job`. Grok Build or this chat then `bot_send_prompt` to the picked id with `mode: async`.

## Common Issues

| Symptom | Fix |
|---|---|
| Empty roster | Copy `assets/roster.json` to `%LOCALAPPDATA%\FAFO\GrokPsBridge\roster.json` |
| Bridge down | `.\Scripts\Start-GrokPsBridge.ps1` |
| Two owners | Stop and ask. Do not dual-send. |
