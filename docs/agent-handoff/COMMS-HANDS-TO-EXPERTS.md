# COMMS — Hands (local Executor) → Grok.com Expert Team

**From:** Local coding agent on the owner’s FAFO / AI HTML Toolbox workspace  
**To:** Expert agents collaborating via Grok.com (and any coding agent joining this repo)  
**Date:** 2026-08-02  
**Language:** Direct. Operational. No theater.

---

## Who I am

I am the **Hands**, running as **Grok Build** on the owner’s machine (local coding agent / worktree on FAFO-Power-Toolbox). Tools: read/write the repo, shell, git (with safety rules), local smoke checks. I do **not** magically share a live session with Grok.com unless you are the same process.

You are the **brains and specialists** on **Grok.com**. You review, design, and **direct**. I execute.

The **Owner** is the **middle man**: they paste your DIR asks into Grok Build and paste my Result / report blocks back to you. They should not have to re-implement code themselves.

That split only works if you write directions I can act on **without** re-deriving the whole product every turn — ideally as `DIR-*.md` in this repo.

---

## How to use me efficiently (protocol summary)

1. Read `docs/MULTI-AGENT-PROTOCOL.md` and `docs/PROJECT-MAP.md`.  
2. Open `docs/agent-handoff/QUEUE.md`.  
3. Create a **Direction Package**: `docs/agent-handoff/DIR-YYYYMMDD-HHMM-slug.md` using the template in the protocol.  
4. Put **one goal**, **ordered tasks**, **acceptance checks**, **constraints**, **out of scope**.  
5. Add it to the QUEUE as `OPEN` / priority.  
6. I will (when the owner runs me) pick it up, set `IN_PROGRESS`, implement, verify, write **Result**, append **LOG**, commit/push if directed.  
7. You reply with a **Revision Package** or a new DIR — not vague “make it better.”

**If you only chat:** I may never see it. **If you write it in the repo:** any future Hands session can execute it cold.

---

## What I need in every Direction Package

| Field | Why |
|-------|-----|
| Goal (one sentence) | Stops scope creep |
| Ordered tasks | I execute sequentially; parallel only if you mark it |
| Paths / file names | I won’t guess “the tax thing” |
| Acceptance checks | Binary done/not done |
| Constraints | Security, UX, “don’t invent tax law” |
| Out of scope | Prevents freelancing |

**Bad direction:** “Improve TaxForge and Xero.”  
**Good direction:** “In LedgerLink Console, add a last-sync relative time and surface pending OAuth code age; acceptance: UI shows both; no secrets logged.”

---

## What I will do without being asked (defaults)

- Follow `AGENTS.md` security  
- Prefer small diffs  
- Match existing HTML/CSS patterns in-suite  
- Refuse to commit secrets or customer dumps  
- Ask before: force-push, mass delete, real secret rotation, destructive system changes  

---

## What I will **not** do

- Invent tax/legal advice as if certified  
- Put Xero client secrets or tokens in the frontend/repo  
- Expand a DIR into a multi-month rewrite without Owner  
- Pretend remote push succeeded if it didn’t  

---

## Current state I just landed for you (2026-08-02)

### TaxForge suite (new)

Path: `Business Tax Preparedness/`

| App | Role |
|-----|------|
| TaxForge Hub | Suite entry, flow, animation |
| LedgerLink Console | Xero/demo/CSV/OAuth scaffold |
| Compliance Pulse | Readiness score |
| Write-Off Workshop | Coding / deductibility triage |
| Year-End War Room | Deadlines, vault, kanban, preparer pack |

Shared: `taxforge-shared.js/css`  
Comms pack for humans: `TAXFORGE-EXPERT-BRIEF.md`, email txt, `TaxForge Expert Share Pack.html`  
Launcher: category **Tax**, section **TaxForge & Books**

### Other recent apps

- `Typing Assistant Trainer.html` — typing trainer with combos/campaign  
- `Empire Seed.html` — Civ-like 4X, Three.js 3D (CDN)  

### Docs for collaboration (this drop)

- `docs/MULTI-AGENT-PROTOCOL.md`  
- `docs/PROJECT-MAP.md`  
- `docs/agent-handoff/*`  

---

## How you should talk to me (examples)

### Domain expert (tax)

> DIR: Adjust Compliance Pulse weights so bank reconciliation checklist items cannot score above 70% readiness until coded txn coverage ≥ 80%. List exact weight changes. Acceptance: document the formula in a short comment in Compliance Pulse.html and update TAXFORGE-EXPERT-BRIEF scoring section.

### Product expert

> DIR: Rename launcher section subtitle; add Share Pack as a non-featured launcher card under Tax. Acceptance: card opens Expert Share Pack; hub nav unchanged.

### Eng / security

> DIR: Design-only note in `docs/` for Xero token proxy on 127.0.0.87 using FAFO.Secrets; no code yet. Acceptance: sequence diagram in markdown + endpoint list.

### After I finish

You open the DIR Result section, then either:

- Status stays DONE and you open a new DIR, or  
- Status → OPEN with revision tasks  

---

## Feedback loop

```
Expert DIR (OPEN)
    → Hands IN_PROGRESS
    → Hands DONE + Result + LOG
    → Expert review
    → Next DIR or revision
```

Owner can always interrupt. Repo handoff files beat forgotten chat.

---

## My ask of the Expert team

1. **Use DIR files**, not only chat.  
2. **Prioritize** in QUEUE (one IN_PROGRESS).  
3. **Be specific** enough that a fresh agent can execute tomorrow.  
4. **Keep secrets out** of directions.  
5. When you want live Xero or Grok-chat-over-books, file separate DIRs: architecture first, then implementation.

I am ready to be your hands. Point me with DIR packages.

— Local Executor (Hands)
