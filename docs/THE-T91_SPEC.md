# THE-T91 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 (COM LOCK META — Ryan override)  
**AMEND 2026-09-22:** Ryan late lock (widget t2240s3) — respec = 1 free lifetime then 50 ScoreShards; player-facing **Glyphs** label OK; bag stays ScoreShards. Prior sha8 `60e84eb4`.
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**Cite:** `Docs/TRAINER_META_BRAINSTORM.md` sha8 `9a3b92a5`  
**BTΩ:** `1:35` → **Ω35**  
**Constraints:** No HTML from THE. No CDN. No phone-home. ScaleSiege HOLD.  
**Do not touch:** `campaign.v3`, launcher, TaxForge, ScaleSiege, Drawing Board.html

---

## Ryan / COM locks (wave-wide — bind all T91–T100)

| # | Lock |
|---|------|
| 1 | Cross-device sync = **Export/Import** pack `trainer-meta-pack.v1` (Merge: max PB + union owned lattice nodes + max shards) |
| 2 | Castle locked rooms = **GREY** (visible, non-interactive) — **NOT** hide/fog (Ryan overrode THE hide default) |
| 3 | Respec = **1 free lifetime**, then **50 ScoreShards** each (T98+ UI; constants reserved now). Player-facing copy may say **Glyphs**; bag/fields stay `ScoreShards` / `shards` |
| 4 | KEEP order **T91→T100** exactly as brainstorm |
| 5 | Scout stretch (Hades pick-3 / Balatro-style jokers / Stardew wall) = **AFTER Lattice MVP** — not in T91–T100 |

### PET constraints (must appear in implementation notes)

| Constraint | Rule |
|------------|------|
| Storage | New bag only: `localStorage['aitoolbox.typingTrainer.meta.v1']` — **do not mutate** `campaign.v3` or other legacy bags except read-only score probes |
| Castle | In-Trainer **overlay/route** (`hub` \| `play` \| `sphere`) — **not** a separate HTML file |
| Mobile | Capability flags: coarse pointer / narrow viewport + `visualViewport`; **additive CSS only**; desktop HARD3 layout/FX untouched when not mobile |
| Portraits | Later path: `shared/typing-trainer/portraits/` (T97) — out of T91 |

---

## T91 one-liner

**Meta save stub `meta.v1` + ScoreShards from sprint/daily PB + wallet HUD.**

Out of T91: Castle UI, Glyph Lattice UI, Shop, miss-forgive, mobile shell, portraits, grey rooms UI (schema may reserve fields; no hub chrome yet).

---

## 1. Schema — `aitoolbox.typingTrainer.meta.v1`

```json
{
  "schema": "aitoolbox.typingTrainer.meta.v1",
  "version": 1,
  "shards": 0,
  "shardsEarnedToday": 0,
  "dayKey": "YYYY-MM-DD",
  "wallet": {
    "lifetimeEarned": 0,
    "lifetimeSpent": 0
  },
  "scores": {
    "sprint15": { "wpm": 0, "acc": 0, "at": null },
    "sprint30": { "wpm": 0, "acc": 0, "at": null },
    "sprint60": { "wpm": 0, "acc": 0, "at": null },
    "daily": { "dayKey": null, "wpm": 0, "acc": 0, "cleared": false, "at": null }
  },
  "lattice": {
    "cursorNodeId": "hub_core",
    "owned": { "hub_core": { "rank": 1 } }
  },
  "castle": {
    "rooms": {
      "gatehouse": { "tier": 0, "decor": {} },
      "barracks": { "tier": 0, "decor": {} }
    }
  },
  "shop": { "bought": [], "stockSeed": null },
  "stats": {
    "missForgiveChargesBonus": 0,
    "streakRetainPct": 0,
    "streakGraceMs": 0
  },
  "portraits": {},
  "history": [],
  "constants": {
    "dailyShardCap": 120,
    "repeatMult": 0.15,
    "respecCost": 50,
    "freeRespecLifetime": 1
  },
  "respec": {
    "freeUsed": 0
  },
  "updatedAt": null
}
```

### Load / save rules

1. Cold load: if key missing → write default stub above (own `hub_core` rank 1; Gatehouse+Barracks tier 0).  
2. Every mutation → `JSON.stringify` to `aitoolbox.typingTrainer.meta.v1` immediately; set `updatedAt` ISO.  
3. **Never** write into `campaign.v3`, `prefs.v3` character/campaign trees for META wallet (read `prefs.v3` only if needed for display name/class label on HUD).  
4. Day rollover: if `dayKey !== todayLocal`, set `dayKey = today`, `shardsEarnedToday = 0` (do not wipe wallet shards).

### Reserved (stub only in T91 — no UI)

- `lattice`, `castle`, `shop`, `stats`, `portraits` exist so later KEEPs do not migrate schema.  
- T91 must not render Castle/Lattice/Shop screens.

---

## 2. ScoreShards — earn rules (T91)

### 2.1 Eligible events only

| Event | When it fires |
|-------|----------------|
| Sprint PB | Completed sprint 15 / 30 / 60 and **new personal best WPM** (tie WPM → require higher `acc` to count as PB) |
| Daily first clear | First successful daily clear for `dayKey` |
| Daily PB | Same day daily already cleared AND new PB WPM (or tie + higher acc) |

No shards from: practice free-type, incomplete runs, campaign (yet), munchers/breaker (yet), idle.

### 2.2 Formula

```
raw = floor( scorePoints * modeMult * durationWeight )
if isRepeat: raw = floor(raw * repeatMult)   // default 0.15
grant = min(raw, dailyShardCap - shardsEarnedToday)
if grant < 0: grant = 0
```

**scorePoints (v1 table):**

| Grade band (from existing sprint/daily grade if present; else derive) | scorePoints |
|------------------------------------------------------------------------|-------------|
| S | 40 |
| A | 28 |
| B | 18 |
| C | 10 |
| D/F / no grade | 6 |

If no grade helper exists, derive band from WPM+acc thresholds already used by Trainer podium (PET: reuse, do not invent parallel grade UI).

**modeMult:** sprint `1.0`, daily `1.25`  
**durationWeight:** sprint15 `0.7`, sprint30 `1.0`, sprint60 `1.35`, daily `1.0`

**firstClearBonus (daily only, once per dayKey):** `+15` flat shards after `raw`, still clamped by daily cap.

### 2.3 Anti-farm

| Rule | Value |
|------|-------|
| Daily soft cap | `constants.dailyShardCap` = **120** |
| Repeat grind | `repeatMult` = **0.15** after PB already held for that mode key |
| No idle | Must complete scored run |
| Cap shared | One wallet; mobile/desktop same bag when same origin; pack sync otherwise |
| Cap UX | When `shardsEarnedToday >= 120`, show “Daily shard cap reached” on grant attempt (toast or HUD hint); do not throw |

### 2.4 PB ledger write

On eligible completion, update `scores.sprint15|30|60` or `scores.daily` **before** computing grant. Persist meta bag once with both score + shard changes.

---

## 3. Wallet HUD (T91 UI)

**Placement:** Trainer chrome — compact, non-blocking (near existing XP/level or top bar).  

**Shows:**

- Icon/label **Shards** + integer `shards`  
- Optional tiny `today: shardsEarnedToday / 120`  
- On grant: brief +N pulse (honor `prefs.v3.reducedMotion` → static text update only)

**Does not show in T91:** shop, lattice, castle buttons (may add disabled placeholders only if zero risk — prefer omit).

**Reduced motion / contrast:** text contrast ≥4.5; no mandatory motion.

---

## 4. Export / Import (minimal T91)

T91 ships **pack helpers** so T96 does not redesign schema:

### Pack schema `trainer-meta-pack.v1`

```json
{
  "schema": "trainer-meta-pack.v1",
  "exportedAt": "ISO",
  "meta": { "...entire aitoolbox.typingTrainer.meta.v1 object..." }
}
```

| Action | Behavior |
|--------|----------|
| Export | Download JSON file (or copy textarea) of pack |
| Import Replace | Overwrite meta bag with `pack.meta` |
| Import Merge | `shards = max(a,b)`; `lifetime*` = max; `scores.*` = per-key best WPM (tie → best acc); `lattice.owned` = union by nodeId with `rank = max`; `castle.rooms` = per-room `tier = max`; `shop.bought` = union; `dayKey`/`shardsEarnedToday` = if same dayKey sum capped at 120 else take import’s day fields carefully (prefer: if dayKeys differ, keep local day counters; still merge wallet shards via max) |

T91 acceptance: Export + Import Replace required; Merge strongly preferred same KEEP if cheap — else T96 hard-require Merge. **COM preference:** include Merge in T91 if ≤+Ω10; else stub Merge function + TST note.

THE call: **implement Export + Import Replace + Import Merge in T91** (Merge rules above).

---


## 4b. Respec policy (reserved — UI at T98)

| Rule | Value |
|------|-------|
| Free | **One** lifetime free respec per `meta.v1` profile (`respec.freeUsed` 0→1) |
| Priced | Each later respec costs `constants.respecCost` (**50**) ScoreShards |
| Currency copy | Player-facing strings may say **Glyphs**; storage keys/fields remain `shards` / ScoreShards |
| T91 duty | Persist `constants.freeRespecLifetime`, `respec.freeUsed`, `respecCost` only — no respec button yet |
## 5. Explicit non-goals (T91)

- Castle overlay UI / grey rooms (T92)  
- Glyph Lattice UI (T93)  
- Miss-forgive (T94)  
- Shop board (T95)  
- Mobile capability CSS (T96) — flags may be detected and stored under `shell` later; not required  
- Portraits (T97)  
- Scout stretch content  

---

## 6. Acceptance checklist (PET / TST)

### A. Storage

- [ ] A1 Key `aitoolbox.typingTrainer.meta.v1` created on first run with schema stub  
- [ ] A2 `campaign.v3` byte-identical after T91 session that only plays sprint/daily (no META writes into it)  
- [ ] A3 Day rollover zeros `shardsEarnedToday`, keeps `shards`  
- [ ] A4 `constants.dailyShardCap === 120`, `respecCost === 50`, `freeRespecLifetime === 1`, `repeatMult === 0.15`; `respec.freeUsed` defaults 0

### B. Earn

- [ ] B1 New sprint PB grants shards > 0 (under cap)  
- [ ] B2 Repeat same sprint without new PB grants ~15% (floor) or 0 if raw floors to 0  
- [ ] B3 Daily first clear grants base +15 firstClear, clamped by cap  
- [ ] B4 After 120 earned today, further grants are 0 + cap messaging  
- [ ] B5 Incomplete run grants nothing  

### C. HUD

- [ ] C1 Wallet visible in play chrome showing shard count  
- [ ] C2 Grant updates HUD without reload  
- [ ] C3 reducedMotion: no flashy particle requirement  

### D. Pack

- [ ] D1 Export produces `trainer-meta-pack.v1`  
- [ ] D2 Import Replace restores shards + scores  
- [ ] D3 Import Merge: max shards, per-mode best PB, union lattice owned ranks  
- [ ] D4 No network / CDN / GitHub on export-import  

### E. Pipe

- [ ] E1 Single file KEEP; desktop HARD3 modes still playable  
- [ ] E2 ScaleSiege untouched  
- [ ] E3 Soft nits only → T92 notes  

**PASS:** A1–A4, B1–B5, C1–C3, D1–D4, E1–E3.

---

## 7. Handoff

| Role | Action |
|------|--------|
| **THE** | T91 LOCKED; standby T92 formal when COM assigns after KEEP |
| **CRE** | Optional wallet chip visual — cite if PET LIVE |
| **PET** | Implement when COM sets PET-T91 LIVE |
| **TST** | Score §6 |
| **COM** | Assign LIVE / promote |

**Wave reminder:** Grey rooms (not hide) bind at **T92**. Respec policy binds at first respec UI (T98): 1 free lifetime then 50 shards; HUD/copy may label currency **Glyphs** while fields remain ScoreShards. Scout stretch parked post-Lattice MVP.

**Report line:** `THE-T91 LOCKED — Docs/THE-T91_SPEC.md`