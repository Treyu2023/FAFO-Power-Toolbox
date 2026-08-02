# Multi-Agent Collaboration Protocol

**Audience:** Grok.com expert agents, coding agents (Grok CLI / Grok Build), humans  
**Role of this file:** How we work together efficiently without thrashing the repo or leaking secrets.

---

## Who is who

| Role | Who | Job |
|------|-----|-----|
| **Hands / Executor** | Local coding agent in this workspace (Grok Build / CLI on the owner’s machine) | Reads the repo, edits files, runs local commands, commits when asked, follows directions from Expert agents |
| **Expert team** | Grok.com specialists (product, tax/domain, architecture, security, UX) | Review, design, prioritize, write **Directions** packages the Executor must follow |
| **Owner / Human** | Repo owner | Goals, approvals for push/secrets/destructive work, final product calls |

**Core idea:** Experts think and direct. The local agent is their **hands** on the real filesystem and git remote. Experts should not assume they can edit this machine directly unless they are the same local session.

---

## Protocol in one paragraph (read this first)

Expert agents produce **Direction Packages** (goal, constraints, ordered tasks, acceptance checks, out-of-scope). The Executor agent implements those packages on disk, reports results (diff summary + verification), and asks only when blocked by secrets, ambiguity, or destructive risk. Experts then issue the next package or a revision. Communication lives **in the repo** under `docs/agent-handoff/` so any agent can resume without chat history.

---

## Efficiency rules (both sides)

### Expert team — how to direct the Hands

1. **One goal per Direction Package.** Not five unrelated epics.
2. **Write for an agent with tools, not for a chatbot.** Paths, file names, acceptance tests, “done when…”.
3. **Prefer ordered steps** the Hands can execute without re-planning the whole product.
4. **State constraints explicitly:** no secrets in git, loopback-only server, don’t delete user data, etc.
5. **Point at files** that already exist. Read `docs/PROJECT-MAP.md` and the relevant suite README first.
6. **Do not dump raw secrets** into directions or issues. Presence checks only.
7. **When reviewing:** return **Revision Packages** (what’s wrong, exact change, re-check).

### Hands / Executor — how to serve the Experts

1. **Read the latest open package** in `docs/agent-handoff/QUEUE.md` and the newest `DIR-*.md` with status `OPEN` or `IN_PROGRESS`.
2. **Implement only that package** unless the Owner overrides.
3. **Report in-repo:** update the package status, append to `docs/agent-handoff/LOG.md`.
4. **Verify** (open files, run tests/builds if applicable, smoke-check HTML).
5. **Stop and ask** for: force-push, secret rotation, mass delete, production credentials, unclear domain tax rules that could mislead users.
6. **Never commit** secrets, `.env`, `server/security_config.json` with keys, device reports, or customer Verifone site data (see `AGENTS.md` + `.gitignore`).

---

## Direction Package format (Experts → Hands)

Create a new file:

`docs/agent-handoff/DIR-YYYYMMDD-HHMM-short-slug.md`

```markdown
# DIR: <short title>

- **Status:** OPEN | IN_PROGRESS | BLOCKED | DONE | CANCELLED
- **Priority:** P0 | P1 | P2
- **Owner (expert):** <role or name>
- **Executor:** local Grok agent (hands)
- **Created:** YYYY-MM-DD
- **Goal:** one sentence

## Context
Why this matters; links to prior DIR or design notes.

## Constraints
- Must / must not (security, UX, scope)

## Tasks (ordered)
1. …
2. …

## Acceptance checks
- [ ] …
- [ ] …

## Out of scope
- …

## Handoff notes for next expert
- …
```

Then add a line to `docs/agent-handoff/QUEUE.md`.

---

## Result Package format (Hands → Experts)

Append to the same `DIR-*.md` under `## Result` (or set Status DONE and log):

```markdown
## Result
- **Status:** DONE | BLOCKED
- **Completed:** YYYY-MM-DD
- **Summary:** what changed
- **Files touched:** list
- **Verification:** what was checked
- **Blockers:** if any
- **Suggested next DIR:** optional
```

Also append a short line to `docs/agent-handoff/LOG.md`.

---

## Language contract (how Hands “talks” to Experts)

When writing handoffs, the Executor uses plain technical English:

- **What** was built or changed  
- **Where** (paths)  
- **How to verify**  
- **What’s next** if Experts should redesign  
- No roleplay fluff; no fake “I pushed secrets”; no hidden steps  

Experts should reply in the same style inside new DIR files so the next Hands session can start cold.

---

## Priority queue discipline

1. Only **one** `IN_PROGRESS` package at a time (unless Owner says parallel).  
2. `P0` = security, data loss, broken launcher/entry path.  
3. TaxForge domain questions stay in DIR notes — Hands does not invent tax advice.  
4. If chat and repo disagree, **repo handoff files win**.

---

## Git workflow for this collaboration

1. Hands implements on branch `main` or a feature branch as directed.  
2. Commits are small and intentional.  
3. Push only when Owner or DIR explicitly allows remote update.  
4. Before private remote push: prefer `Scripts\Invoke-FAFOPrePushCheck.ps1` when available.  
5. Never force-push `main` without Owner.

---

## Security shared understanding

- Secrets: FAFO.Secrets / DPAPI / env — **not** committed JSON with real keys.  
- Xero: browser may hold client id + auth code; **client secret + tokens** exchange on loopback server only.  
- Customer / site / device dumps: never commit.  
- Tools may say “not tax advice” where financial guidance appears.

---

## Quick start for a new Expert agent (Grok.com)

1. Read `AGENTS.md`  
2. Read `docs/PROJECT-MAP.md`  
3. Read this protocol  
4. Read `docs/agent-handoff/QUEUE.md`  
5. Open the relevant product brief (e.g. TaxForge `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md`)  
6. File a **DIR-*** package with tasks the Hands can execute  
7. Wait for Result section / LOG update; then revise or close  

## Quick start for Hands (local agent)

1. Read QUEUE → open highest-priority OPEN package  
2. Set Status IN_PROGRESS  
3. Implement → verify → Result + LOG  
4. Commit/push only if Owner/DIR requires  

---

*This protocol is the interface between expert reasoning and local execution. Keep it short; put product detail in suite briefs, not here.*
