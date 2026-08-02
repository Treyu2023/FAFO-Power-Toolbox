# Agent handoff folder

This directory is the **shared whiteboard** between:

- **Expert agents** (Grok.com team — design, domain, review)
- **Hands / Executor** (**Grok Build** local coding session on the owner’s machine)
- **Owner** (middle man — relays chat both ways; does not need to code)

## Workflow (short)

```
Grok.com Experts  ↔  Owner (relay)  ↔  Grok Build Hands
                         ↓
              docs/agent-handoff + git push/pull
```

Protocol: `docs/MULTI-AGENT-PROTOCOL.md` (lanes section).

## Files

| File | Purpose |
|------|---------|
| `QUEUE.md` | Priority list of open/closed Direction Packages |
| `LOG.md` | Chronological work log (append-only style) |
| `COMMS-HANDS-TO-EXPERTS.md` | Standing message from Hands: how to use me |
| `DIR-*.md` | Individual Direction Packages |

## Rules

1. Experts create `DIR-*.md` and list them in `QUEUE.md` (or Owner pastes DIR text for Hands to file).  
2. Hands (Grok Build) sets `IN_PROGRESS` → implements → `DONE` + Result + LOG line.  
3. Owner pastes Hands “report for Experts” back to Grok.com when needed.  
4. No secrets in any handoff file.  
5. Repo handoff beats chat history.
