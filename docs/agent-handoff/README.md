# Agent handoff folder

This directory is the **shared whiteboard** between:

- **Expert agents** (Grok.com team — design, domain, review)
- **Hands / Executor** (local Grok coding agent on the owner’s machine)

## Files

| File | Purpose |
|------|---------|
| `QUEUE.md` | Priority list of open/closed Direction Packages |
| `LOG.md` | Chronological work log (append-only style) |
| `COMMS-HANDS-TO-EXPERTS.md` | Standing message from Hands: how to use me |
| `DIR-*.md` | Individual Direction Packages |

## Rules

1. Experts create `DIR-*.md` and list them in `QUEUE.md`.  
2. Hands sets `IN_PROGRESS` → implements → `DONE` + Result + LOG line.  
3. No secrets in any handoff file.  
4. Protocol detail: `docs/MULTI-AGENT-PROTOCOL.md`.  
