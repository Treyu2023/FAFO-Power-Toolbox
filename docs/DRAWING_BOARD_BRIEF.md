# FAFO Drawing Board — RM-2 LOCK (2026-09-13)

**File:** `Drawing Board.html` (sandbox first)
**Data:** `shared/fafo-drawing-board.json` (+ localStorage mirror + Export/Import)
**Chrome:** `shared/fafo-chrome.css` + `fafo-chrome.js` + aitoolbox layout
**Launcher:** new tile (Management / Ops)
**Owner oversight:** Owner is final gate on promote Idea→Roadmap→Scaffolding

## Three stages (same app, tab flow)

### 1) Drawing Board
- Brainstorm cards/sticky ideas (title, notes, tags, links)
- Compare **outside sources** (URL + title + snippet/notes; paste-only, no phone-home scrape required in v1)
- Collaborate: Owner edits freely; COM updates seed JSON; import/export packs
- Statuses: Idea | WorthComparing | Parked | PromotedToRoadmap

### 2) Roadmap
- Practical plan pulled from promoted ideas
- Ordered milestones with status: Planned | LIVE | Blocked | Done
- Links back to source ideas + outside sources
- History of what shipped (seed HARD3 Trainer, chrome UI waves, etc.)

### 3) Scaffolding
- Exploded view: Milestone → Tasks
- Every task has **BTΩ** rating

## BTΩ (Bot × Time = Ω)
- Display format: `B:T` where B = bots, T = time in **minutes**
- Power: `Ω = B × T` shown as `Ω{N}` (example: `1:3` → Ω3)
- Fields: `bots`, `minutes`, `omega` (computed), optional `rolesIdeal[]`, `tokenBand` L/M/H
- On close: optional `actualBots`, `actualMinutes`, `actualOmega` for history
- Planning bar: sum Ω for selected slice vs daily Ω budget (default Ω60 = e.g. 2 bots × 30m)

## Safety / pipe
- Local only; no CDN; no credentials; no GitHub API in v1
- PET sole HTML KEEP; one LIVE KEEP; TST PASS then COM promote (+ launcher)
- ScaleSiege HOLD

## Seed
- History: Trainer HARD3 @ 618b14a; System Tools chrome UI-15..32
- Sample scaffolding milestone "Drawing Board v1" with tasks rated in BTΩ
- Empty Drawing Board ideas ready for Owner

## Done when
Owner can open from sandbox launcher, brainstorm + add outside source, promote to Roadmap, explode Scaffolding with BTΩ `B:T` / `ΩN`, export JSON, and see History.
