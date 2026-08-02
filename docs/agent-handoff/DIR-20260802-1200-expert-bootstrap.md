# DIR: Expert team bootstrap & first review pass

- **Status:** OPEN  
- **Priority:** P1  
- **Owner (expert):** Grok.com expert team (any role)  
- **Executor:** local Grok agent (hands) — *this package is mostly for Experts first; Hands waits for follow-on DIRs*  
- **Created:** 2026-08-02  
- **Goal:** Bring Expert agents online with full project context and produce concrete next Direction Packages for Hands.

## Context

Owner asked Hands to push latest apps + collaboration protocol so Grok.com experts and the local agent can work as a team: Experts direct, Hands executes.

Shipped in the same wave:

- TaxForge suite (`Business Tax Preparedness/`)  
- Typing Assistant Trainer, Empire Seed 3D  
- Multi-agent docs under `docs/` and `docs/agent-handoff/`  

## Constraints

- Do not put secrets, API keys, or customer data in DIR files  
- Do not treat TaxForge as certified tax advice  
- Prefer small, executable next DIRs over essay-only feedback  
- One primary product track per follow-on DIR when possible  

## Tasks (ordered) — **for Expert team**

1. Read `AGENTS.md`, `docs/PROJECT-MAP.md`, `docs/MULTI-AGENT-PROTOCOL.md`.  
2. Read `docs/agent-handoff/COMMS-HANDS-TO-EXPERTS.md` (how Hands works).  
3. Read TaxForge brief: `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md`.  
4. Optionally open live apps via Toolbox Launcher → TaxForge & Books (or HTML files).  
5. Produce **at least one** new `DIR-*.md` with ordered tasks for Hands, e.g.:  
   - Tax domain scoring/rules revision  
   - Live Xero token-proxy design  
   - Grok-assist panel over preparer pack  
   - UX polish on a named app  
6. Update this file’s Result section with links to new DIRs; mark this DIR **DONE**.  
7. Update `QUEUE.md` with the new packages.

## Tasks — **for Hands** (only if Experts produced no DIR within Owner request)

If Owner re-invokes Hands with “no expert DIRs yet,” Hands may:

1. Smoke-check TaxForge hub loads and shared JS has no syntax errors.  
2. Keep protocol docs current if paths break.  
3. Not invent major product features without a DIR.

## Acceptance checks

- [ ] Expert team has a clear path to file work for Hands  
- [ ] At least one follow-on DIR exists **or** Expert Result explains intentional pause  
- [ ] QUEUE.md reflects reality  

## Out of scope

- Implementing live Xero sync in this bootstrap DIR  
- Rewriting the entire toolbox  
- Publishing secrets or OAuth client secrets  

## Handoff notes for next expert

Hands is ready. Use DIR format. Repo is source of truth.

---

## Result

_Experts: fill this when bootstrap review is complete._

- **Status:**  
- **Completed:**  
- **Summary:**  
- **Follow-on DIRs created:**  
- **Blockers:**  
