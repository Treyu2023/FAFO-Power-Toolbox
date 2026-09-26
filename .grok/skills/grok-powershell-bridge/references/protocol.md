---
description: "Wire format, paths, and HTTP routes for the Grok Build <-> Grok PowerShell bridge. Read before changing the protocol."
connections: []
---

# Protocol

## Endpoints

Base: `http://127.0.0.87:17321` (fallback `http://127.0.0.1:17321`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Sidecar alive. Returns bind, pid, mailbox paths. |
| POST | `/say` | Freeform message. Body: `{ "from", "to", "text" }`. |
| POST | `/exec` | Run PowerShell in the sidecar session. Body: `{ "from", "cmd", "cwd", "timeout_sec" }`. |
| GET | `/inbox` | Pending messages for the caller (`?role=grok-build` or `grok-ps`). |
| POST | `/reply` | Attach a result to an existing id. |

## Envelope

```json
{
  "v": 1,
  "id": "uuid",
  "ts": "2026-09-26T09:00:00Z",
  "from": "grok-build",
  "to": "grok-ps",
  "kind": "say",
  "text": "optional",
  "cmd": "optional",
  "cwd": "optional",
  "timeout_sec": 60,
  "ok": true,
  "stdout": "",
  "stderr": "",
  "exit_code": 0
}
```

`kind`: `say` | `exec` | `result` | `ping` | `pong`

## Mailbox paths

Primary (device-local, not git):

- `%LOCALAPPDATA%\FAFO\GrokPsBridge\inbox\` — Build → PS
- `%LOCALAPPDATA%\FAFO\GrokPsBridge\outbox\` — PS → Build
- `%LOCALAPPDATA%\FAFO\GrokPsBridge\archive\`
- `%LOCALAPPDATA%\FAFO\GrokPsBridge\bridge.json` — live bind + pid

Mirror (Grok home):

- `%USERPROFILE%\.grok\ps-bridge\` (same four names)

Write one JSON file per message. Name: `{utc-yyyyMMddTHHmmss}-{id}.json`.
