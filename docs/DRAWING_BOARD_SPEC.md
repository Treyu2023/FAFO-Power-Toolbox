# THE-DB-1 — Drawing Board Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-14  
**Cite brief:** `Docs/DRAWING_BOARD_BRIEF.md` (COM RM-2 LOCK)  
**Target file (PET later):** `Drawing Board.html` (sandbox first; one LIVE KEEP)  
**Data:** `shared/fafo-drawing-board.json` + `localStorage` mirror + Export/Import  
**Chrome:** `shared/fafo-chrome.css` + `shared/fafo-chrome.js` + aitoolbox layout  
**Launcher:** new tile under Management / Ops (COM promote after TST PASS)  
**Owner lanes:** THE = this spec only. PET = sole HTML KEEP. TST = score. COM = promote.  
**Constraints:** No CDN. No phone-home. No GitHub API v1. No credentials. ScaleSiege HOLD.  
**THE scope:** docs only — no HTML edits.

---

## 1. Product shape

One HTML app, three stages as a tab (or equivalent stage) flow in the same document:

| Stage | Purpose |
|-------|---------|
| **Drawing Board** | Brainstorm + outside sources; Owner oversight gate before promote |
| **Roadmap** | Practical ordered plan from promoted ideas |
| **Scaffolding** | Exploded milestones → tasks, each with **BTΩ** |

Owner is the final gate on **Idea → Roadmap → Scaffolding** promotion. COM may seed JSON; anyone can Import/Export packs; Owner edits freely in-app.

---

## 2. Stage specs

### 2.1 Drawing Board

**Entities**

- **Idea card:** `id`, `title`, `notes`, `tags[]`, `links[]` (optional URL strings), `status`, `createdAt`, `updatedAt`, `sourceIds[]` (outside sources)
- **Outside source:** `id`, `url`, `title`, `snippet` (paste-only notes), `createdAt`  
  v1 = paste-only. No scrape, no fetch, no phone-home.

**Statuses (Idea):** `Idea` | `WorthComparing` | `Parked` | `PromotedToRoadmap`

**UI must support**

- Create / edit / park idea cards (sticky-style cards OK)
- Attach outside sources by paste (URL + title + snippet/notes)
- Filter by status/tag
- Promote selected Idea → creates/links a Roadmap milestone (status becomes `PromotedToRoadmap`); **Owner confirms** before promote commits

### 2.2 Roadmap

**Entities**

- **Milestone:** `id`, `title`, `summary`, `status`, `order`, `ideaIds[]`, `sourceIds[]`, `createdAt`, `updatedAt`, `shippedAt?`, `historyNote?`

**Statuses:** `Planned` | `LIVE` | `Blocked` | `Done`

**UI must support**

- Ordered list (drag or up/down); status chips
- Link back to source ideas + outside sources
- **History** panel: shipped work (seedable; see §5)
- Promote milestone → Scaffolding explode (creates task shell list); Owner gate

### 2.3 Scaffolding

**Entities**

- **Task:** `id`, `milestoneId`, `title`, `notes?`, `status` (`Open` | `LIVE` | `Done` | `Cut`), **BTΩ fields** (see §3), `createdAt`, `updatedAt`, `closedAt?`

**UI must support**

- Milestone → task tree (exploded view)
- Every task shows `B:T` and `ΩN`
- Planning bar: sum Ω for selected slice vs daily Ω budget (default **Ω60**, e.g. 2 bots × 30m)
- On task close: optional actuals (`actualBots`, `actualMinutes`, `actualOmega`)

---

## 3. BTΩ (Bot × Time = Ω)

| Display | Meaning |
|---------|---------|
| `B:T` | B = bots (integer ≥1), T = minutes (integer ≥1) |
| `ΩN` | Ω = B × T (example: `1:3` → `Ω3`) |

**Fields (every task)**

| Field | Required | Notes |
|-------|----------|-------|
| `bots` | yes | integer ≥ 1 |
| `minutes` | yes | integer ≥ 1 |
| `omega` | yes | computed `bots * minutes`; store denormalized for export |
| `rolesIdeal` | optional | string[] (e.g. `PET`, `CRE`, `TST`) |
| `tokenBand` | optional | `L` \| `M` \| `H` |
| `actualBots` | optional | on close |
| `actualMinutes` | optional | on close |
| `actualOmega` | optional | on close; prefer `actualBots * actualMinutes` if both set |

**Planning bar**

- `sumOmega` = Σ `omega` for selected tasks/slice
- `dailyBudgetOmega` default `60` (prefs-editable)
- Show `sumOmega / dailyBudgetOmega` with clear over-budget state (contrast ≥4.5)

---

## 4. Data model & persistence

### 4.1 Files / keys

| Store | Path / key |
|-------|------------|
| Seed / pack file | `shared/fafo-drawing-board.json` |
| Runtime mirror | `localStorage` key `aitoolbox.drawingBoard.v1` |
| Export | download `.json` pack (same schema) |
| Import | merge or replace (prompt Owner: Merge \| Replace) |

### 4.2 Root JSON schema (v1)

```json
{
  "schema": "fafo-drawing-board.v1",
  "updatedAt": "ISO-8601",
  "prefs": {
    "dailyBudgetOmega": 60
  },
  "ideas": [],
  "sources": [],
  "milestones": [],
  "tasks": [],
  "history": []
}
```

**History entry:** `{ "id", "title", "note", "shippedAt", "ref" }`  
`ref` may cite git short sha or milestone id (string only; no API calls).

### 4.3 Sync rules

1. Cold load: if `localStorage` empty → load `shared/fafo-drawing-board.json` (fetch relative, same origin / file protocol safe). If both missing → empty scaffold + seed History (§5).
2. Every mutation → write `localStorage` immediately; optional "Save seed file" is PET/COM offline concern (export is the user path).
3. Export/Import never phones home.

---

## 5. Seed content (v1)

**History (shipped)**

1. Typing Trainer HARD3 complete — cite `618b14a`
2. System Tools chrome wave UI-15..32 (summary note; no need to list every file)

**Sample Scaffolding**

- Milestone: `Drawing Board v1` (`Planned`)
  - Tasks with BTΩ examples, e.g.:
    - Wire 3-stage tabs — `1:25` → `Ω25`
    - Idea + source paste CRUD — `1:20` → `Ω20`
    - Roadmap order + status — `1:15` → `Ω15`
    - Scaffolding + BTΩ bar — `1:20` → `Ω20`
    - Export/Import + History seed — `1:10` → `Ω10`

**Drawing Board ideas:** empty list ready for Owner (optional 1 placeholder Parked demo card OK if clearly marked sample).

---

## 6. Chrome / UX

- Use `fafo-chrome` tokens/components + existing aitoolbox shell patterns
- Theme-friendly (`--fafo-*`); contrast ≥4.5 for text/HUD
- `prefers-reduced-motion`: no mandatory motion; planning bar static OK
- No remote fonts/CDNs/audio
- Late-load safe
- Narrow: stacked panels; primary stage tabs reachable; touch targets ≥44×44 where chrome kit already requires
- Typewell-first N/A (not Trainer); keep primary CTAs visible without overlay traps

---

## 7. Safety / pipe

| Rule | Value |
|------|-------|
| Network | Local only; relative assets only |
| APIs | No GitHub / Origin / scrape in v1 |
| Secrets | None |
| KEEP | PET sole HTML; one LIVE KEEP |
| Gate | TST PASS → COM promote (+ launcher tile) |
| ScaleSiege | HOLD |

---

## 8. Acceptance checklist (PET / TST)

### A. Stages & gates

- [ ] A1 Three stages reachable in one HTML (Drawing Board / Roadmap / Scaffolding)
- [ ] A2 Create idea (title+notes+tags); edit; Park; filter works
- [ ] A3 Add outside source by paste (URL+title+snippet); no network fetch on add
- [ ] A4 Promote Idea → Roadmap requires Owner confirm; status becomes `PromotedToRoadmap`
- [ ] A5 Roadmap milestone statuses Planned|LIVE|Blocked|Done; reorder works
- [ ] A6 Milestone links back to ideas/sources
- [ ] A7 Explode to Scaffolding creates/shows tasks under milestone
- [ ] A8 History shows seeded HARD3 `618b14a` + chrome UI-15..32 notes

### B. BTΩ

- [ ] B1 Task shows `B:T` and `ΩN` with Ω = bots × minutes
- [ ] B2 Example `1:3` renders as `Ω3`
- [ ] B3 Optional `rolesIdeal`, `tokenBand` L/M/H persist
- [ ] B4 On close, optional actual* fields save; history usable
- [ ] B5 Planning bar sums selected Ω vs default budget Ω60; over-budget visible

### C. Data

- [ ] C1 `localStorage` key `aitoolbox.drawingBoard.v1` mirrors state
- [ ] C2 Export downloads schema `fafo-drawing-board.v1` JSON
- [ ] C3 Import Merge and Replace both work without throw
- [ ] C4 Cold load from `shared/fafo-drawing-board.json` when LS empty
- [ ] C5 Zero remote CDN / fonts / analytics / GitHub API

### D. Chrome / ship

- [ ] D1 Uses `fafo-chrome` + aitoolbox; contrast ≥4.5
- [ ] D2 Reduced-motion safe
- [ ] D3 Sandbox launcher tile path documented for COM (Management / Ops)
- [ ] D4 One-file KEEP only; no conflict files; ScaleSiege untouched

**PASS:** A1–A8, B1–B5, C1–C5, D1–D4 all green. Soft nits → next slice notes only.

---

## 9. Out of scope (v1)

- Live multiplayer / agent sockets
- Auto-scrape of pasted URLs
- GitHub/Origin API sync
- Phone install / sideload
- ScaleSiege / Unity work
- HTML authored by THE

---

## 10. Handoff

| Role | Action |
|------|--------|
| **THE** | This spec LOCKED; standby deltas only |
| **CRE** | Optional visual bank (stickies, stage chrome) — cite on PET LIVE |
| **PET** | Implement `Drawing Board.html` + seed JSON per this doc when COM assigns |
| **TST** | Score against §8 |
| **COM** | Assign LIVE KEEP; promote + launcher after PASS |

**Report line:** `THE-DB-1 LOCKED — Docs/DRAWING_BOARD_SPEC.md`