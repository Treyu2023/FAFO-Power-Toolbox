# CRE-DB-1 — Drawing Board Visual Brief (LOCKED)

**Status:** LOCKED 2026-09-14  
**Cite:** `Docs/DRAWING_BOARD_BRIEF.md` (COM RM-2) · `Docs/DRAWING_BOARD_SPEC.md` (THE-DB-1)  
**Target (PET later):** `Drawing Board.html` — CRE delivers look/feel only; **no HTML from CRE**  
**Chrome:** shared `fafo-chrome` + aitoolbox shell; dark FAFO default with theme tokens (`--fafo-*`)  
**ScaleSiege:** HOLD · No CDN · Contrast ≥4.5 · `prefers-reduced-motion` safe

---

## Goal

One Management/Ops app that feels like a **war-room notebook**: brainstorm stickies → ordered roadmap → exploded scaffolding with **BTΩ** (`B:T` + `ΩN`) planning weight. Owner stays the promote gate; chrome never traps primary CTAs.

---

## Global shell

### Mood
- Dark FAFO paper-on-slate: deep ink plate (`--fafo-bg`), soft card lifts, accent sheens on active stage only.
- Journal edges on cards (1px hairline + faint grain), not neon arcade (Trainer juice stays off this app).
- Header: app title **Drawing Board** + Export / Import ghost pair + discreet prefs (Ω budget).

### Stage chrome (sticky top)
Three-stage **stepper + tabs** (same control, dual affordance):

| Step | Label | Active look |
|------|-------|-------------|
| 1 | Drawing Board | filled accent pill + underline |
| 2 | Roadmap | same |
| 3 | Scaffolding | same |

- Inactive = muted ink on plate; ≥44×44 touch.
- Progress ticks 1→2→3 (filled dots); completed prior stages get check pip, not jump-ahead glow.
- Narrow (~≤720px): stepper stacks full-width; tabs become horizontal scroll chips (no wrap crush).

### Shared rules
- Theme-friendly: sheens use theme accent, not hardcoded cyan-only.
- `reducedMotion`: no card flutter, no bar pulse; state = color/opacity only.
- Overlays (promote confirm, Import Merge|Replace): modal card centered; Esc/Cancel ghost; never full-screen blackout that hides stage tabs.
- Empty states: paper hatch + one calm line (never broken-image / void).

---

## Stage 1 — Drawing Board

### Layout (wide)
```
[ Stage stepper ]
[ Filters: status · tag · search ]     [ + New idea ]
┌─────────────────────────┬──────────────────────────┐
│ Idea sticky wall        │ Outside-source compare   │
│ (masonry / wrap grid)   │ panel (sticky right)     │
└─────────────────────────┴──────────────────────────┘
```

### Idea sticky cards
- Size: compact journal sticky (~220–260px wide); soft rotate ≤2° optional (`reducedMotion` = 0°).
- Anatomy: title (strong) · status chip · tag pills · notes clamp 3 lines · link count pip · source-attach pip.
- Status chips (distinct hue, still ≥4.5 on plate):
  - `Idea` — quiet slate
  - `WorthComparing` — amber rim
  - `Parked` — mute / desat
  - `PromotedToRoadmap` — green check rim (read-only badge once promoted)
- Primary on card: Open · Park · **Promote…** (Promote opens Owner confirm card).
- Selected: accent rim + light sheen; multi-select optional later — v1 single focus OK.

### Outside-source compare panel
- Title: **Outside sources** · subtitle “Paste only — no fetch”.
- Rows: favicon-off generic link glyph · title · URL truncated · snippet 2-line clamp · Attach to focused idea.
- Add form: URL · Title · Snippet/notes · **Add** primary.
- Empty: “No sources yet — paste a URL + note to compare.”
- Never auto-scrape; no loading spinners that imply network.

### Mobile
- Stack: stepper → filters → idea wall → compare panel as accordion below (“Compare sources”).

---

## Stage 2 — Roadmap

### Layout
```
[ Stage stepper ]
┌──────────────────────────────┬─────────────────────┐
│ Ordered milestone list       │ History strip       │
│ (drag handle · status · Δ)   │ (shipped timeline)  │
└──────────────────────────────┴─────────────────────┘
```

### Milestone rows
- Left drag / ↑↓ ghost controls.
- Title + summary one-liner.
- Status chips: `Planned` | `LIVE` (accent pulse once if motion OK) | `Blocked` (warn rim) | `Done` (check).
- Trailing: idea-link count · source-link count · **Explode to Scaffolding…** (Owner confirm).
- Linked ideas/sources open as chip drawers under the row (collapse by default).

### History strip
- Vertical or horizontal timeline rail on the side (bottom sheet on mobile).
- Seed entries as journal stamps:
  - Trainer HARD3 · ref `618b14a`
  - System Tools chrome UI-15..32
- Each stamp: title · short note · date · mono `ref` chip.
- Strip header: **History** · “Shipped” · no edit in v1 (seed + future Done promotions append).

### Empty
“Promote an idea from Drawing Board to start the roadmap.”

---

## Stage 3 — Scaffolding

### Layout
```
[ Stage stepper ]
[ Ω budget bar — sticky under stepper ]
┌────────────────────────────────────────────────────┐
│ Milestone tree                                     │
│  └─ Task rows with BTΩ chips                       │
└────────────────────────────────────────────────────┘
```

### Tree
- Milestone headers: fold chevron · title · status · task count · sum Ω for children.
- Task rows: checkbox/status · title · optional rolesIdeal pills (`PET` `CRE` `TST`…) · tokenBand L/M/H tiny chip · **BTΩ chip cluster**.

### BTΩ chips (every task)
- Cluster: `[ B:T ]` + `[ ΩN ]` (example `1:3` + `Ω3`).
- Chip style: mono digits on dark inset pill; Ω chip uses accent fill at low opacity.
- Edit: click opens compact popover (bots · minutes · roles · band); Ω updates live = B×T.
- Closed tasks: optional actuals row `actual B:T` / `Ω` muted under plan chips.
- Cut status: strikethrough title · chips desaturated.

### Ω budget bar (planning)
- Sticky under stage stepper while on Scaffolding.
- Show `sumΩ / dailyBudgetΩ` (default **Ω60**) as labeled meter.
- Under budget: accent fill; over budget: warn rim + “Over Ω budget” label (still ≥4.5).
- Selection: bar reflects **selected** tasks if any; else all visible under open milestones.
- Prefs: edit daily budget via header gear (number stepper).
- `reducedMotion`: meter is static width, no shimmer.

### Mobile
- Budget bar full width under tabs.
- Tree becomes stacked cards (milestone card → nested task cards); BTΩ chips wrap, never truncate ΩN.

---

## Promote / gate chrome (Owner)

Confirm cards (shared pattern):
- Title: “Promote to Roadmap?” / “Explode to Scaffolding?”
- Body: one-line consequence + linked title.
- Actions: **Confirm** primary · Cancel ghost.
- No silent promote.

---

## Import / Export

- Export: ghost download icon → toast “Pack downloaded”.
- Import: file pick → modal **Merge** | **Replace** (Replace = danger style).
- Toasts use existing FAFO plate queue; never block stage tabs.

---

## Density & responsive checklist

| Breakpoint | Behavior |
|------------|----------|
| Wide | 2-col Drawing Board; Roadmap list + History side; Scaffolding tree + sticky Ω bar |
| ~720px | Stack panels; History as bottom sheet; compare accordion |
| Touch | Filters/chips/stage tabs ≥44px; sticky cards tap-open |

---

## Do / Don't

**Do**
- Reuse fafo-chrome buttons, plates, toasts, focus rings.
- Keep BTΩ readable at a glance (`B:T` + `ΩN` always co-visible on task rows).
- Mark sample/demo cards clearly if seeded.

**Don't**
- No CDN fonts/icons; no Trainer FX families; no power meter metaphors.
- No Admin banner — this app is Owner-facing Management chrome.
- No HTML from CRE; PET sole KEEP when COM assigns.

---

## Out of scope (visual v1)

Live multiplayer cursors, URL scrape previews, GitHub/Origin sync chrome, phone install skin.

---

## Handoff

| Role | Action |
|------|--------|
| **CRE** | This visual LOCKED — cite on PET-DB-1 LIVE |
| **THE** | Formal SPEC owns data/gates |
| **PET** | Implement look per this doc + SPEC when COM assigns |
| **TST** | Score SPEC §8; soft visual nits OK |
| **COM** | Promote + launcher after PASS |

**Report line:** `CRE-DB-1 LOCKED — Docs/DRAWING_BOARD_VISUAL.md`