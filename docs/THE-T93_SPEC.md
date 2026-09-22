# THE-T93 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T92 PASS `17932f0` / `e3f06c81`  
**Cite:** `Docs/THE-T91_SPEC.md` `c77b3aa5` · `Docs/THE-T92_SPEC.md` `5368c82e` · `Docs/TRAINER_META_BRAINSTORM.md` `9a3b92a5`  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:55` → **Ω55** · CRE lattice ring art optional `1:30` → **Ω30**  
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.  
**Out of T93:** Scout stretch pick-3 / Balatro jokers / Stardew wall → **T95+** (not woven here)

---

## Wave locks (inherited)

| Lock | Value |
|------|-------|
| Currency | Fields `shards` / ScoreShards; player copy **Glyphs** |
| Respec | 1 free lifetime then 50 (UI still T98; lattice mutex prep only) |
| Castle | GREY rooms (T92); hub route exists |
| Sync | Export/Import Merge rules unchanged |
| Scout stretch | Parked until after Lattice MVP (this KEEP *is* Lattice MVP rings 0–2) |

### PET constraints

- Mutate only `aitoolbox.typingTrainer.meta.v1` (+ read prefs for classId / reducedMotion)  
- **Do not mutate** `campaign.v3`  
- Route: T92 `sphere` stub → **real Lattice UI** on `sphere` route  
- Entry: Hub War Room teaser / “Glyph Lattice” control → `sphere`; Back → `hub` or `play`

---

## T93 one-liner

**Glyph Lattice UI + seed rings 0–2; adjacent unlock for Glyphs; apply small stacking bonuses complementary to class.**

---

## 1. Data model (in meta.v1)

### 1.1 Static seed (ship in HTML or `shared/typing-trainer/glyph-lattice.v1.json` relative)

```json
{
  "schema": "aitoolbox.trainer.glyphLattice.v1",
  "startNodeId": "hub_core",
  "nodes": [ /* see §2 */ ]
}
```

### 1.2 Runtime in meta.v1.lattice

```json
"lattice": {
  "cursorNodeId": "hub_core",
  "owned": { "hub_core": { "rank": 1 } },
  "bonusesAppliedAt": null
}
```

On load: ensure `hub_core` owned rank 1; migrate if missing. Recompute derived `meta.runtimeBonuses` (in-memory OK; optional cache field).

### 1.3 Node fields

| Field | Notes |
|-------|-------|
| `id` | stable string |
| `kind` | `hub` \| `stat` \| `bridge` \| `keystone` \| `content` — T93 uses hub/stat/bridge only (keystone/content stubs OK disabled) |
| `title` | short label |
| `ring` | 0–2 for T93 seed |
| `pos` | `{x,y}` normalized for SVG/canvas layout |
| `edges` | adjacent ids (undirected; normalize on load) |
| `costShards` | Glyph cost for rank 1 (rank N = `costShards * N` if rankMax>1; T93 mostly rankMax 1–3) |
| `rankMax` | 1–3 for stats; hubs 1 |
| `effects[]` | `{ "op":"add\|mult", "stat":"...", "value":number, "perRank":true }` |
| `gates` | optional `{ minLevel?, requiresNodes?[] }` |
| `classAffinity` | optional map classId → mult (default 1) |
| `nearHint` | optional SIE near-toast id or custom string for ALMOST state |

---

## 2. Seed graph (rings 0–2) — MVP ~16–20 nodes

### Ring 0

| id | kind | cost | effects |
|----|------|------|---------|
| `hub_core` | hub | 0 | none (start; owned) |

### Ring 1 (fundamentals — adjacent to hub)

| id | title | cost | rankMax | effects (per rank) |
|----|-------|------|---------|---------------------|
| `wpm_1` | Pace Stone | 8 | 3 | add `wpmCushion` +1 |
| `acc_1` | True Strike | 8 | 3 | add `accFloor` +0.5 (percent points toward soft grade; clamp) |
| `forgive_1` | Soft Error | 10 | 3 | add `missForgiveChargesBonus` +1 |
| `retain_1` | Hold Chain | 10 | 2 | add `streakRetainPct` +10 |
| `grace_1` | Jitter Veil | 6 | 2 | add `streakGraceMs` +25 |
| `shard_1` | Glyph Well | 12 | 2 | mult `shardGain` ×1.05 |

Bridges (optional cheap connectors): `br_n`, `br_e`, `br_s`, `br_w` cost 3, no effects, kind `bridge`.

### Ring 2 (mode / class crumbs — adjacent from ring 1)

| id | title | cost | gates | effects |
|----|-------|------|-------|---------|
| `sprint_path` | Spur Link | 15 | requires `wpm_1` | mult `xpGain` ×1.03 |
| `daily_path` | Ledger Link | 15 | requires `acc_1` | add `shardGain` flat via mult ×1.04 on daily only if easy; else global ×1.03 |
| `forgive_2` | Second Chance | 18 | requires `forgive_1` | add `missForgiveChargesBonus` +1 |
| `class_sprinter` | Wind Favor | 14 | affinity Sprinter 1.15 cost 0.85 | add `wpmCushion` +2 |
| `class_scholar` | Ink Favor | 14 | affinity Scholar | add `accFloor` +1 |
| `class_streaker` | Flame Favor | 14 | affinity Streaker | add `streakRetainPct` +15 |
| `hub_ring2` | Outer Hub | 20 | requires any 3 ring1 owned | hub; free travel once owned |

**Complementary to class:** affinity discounts/boosts only; does not replace HARD3 class passives. Cap table (§4).

PET may tune numbers ±20% if playtest screams; keep ids stable.

---

## 3. Unlock rules

1. **Cursor:** player “stands on” `cursorNodeId` (default `hub_core`).  
2. **Move:** free move along edges onto **owned** nodes (hub/bridge/stat).  
3. **Buy:** if adjacent to cursor (or adjacent to any owned hub — pick one rule and stick; **THE call: adjacent to cursor OR adjacent to any owned node** for less frustration — PoE-lite). COM preference for Sphere feel: **adjacent to an owned node** (not only cursor).  
4. Cost = next rank cost; debit `shards`; `lifetimeSpent +=`; increment `owned[id].rank`; refuse if broke → SIE `SPEND_BROKE` / need toast.  
5. Confirm spend: SIE `SPEND_TITLE/BODY/YES/NO` then `SPEND_OK`.  
6. Gates fail → grey node + refuse toast (not purchasable).  
7. Export/Import: union owned ranks (max) already in T91 Merge.

---

## 4. Bonus application

Recompute after every buy/load:

```
runtimeBonuses = { wpmCushion, accFloor, missForgiveChargesBonus, streakRetainPct, streakGraceMs, xpGainMult, shardGainMult }
```

Stack: `(base + Σ add) * Π mult`.  

**Caps (anti-snowball T93):**

| stat | cap |
|------|-----|
| wpmCushion | +8 |
| accFloor | +5 |
| missForgiveChargesBonus | +5 |
| streakRetainPct | 50 |
| streakGraceMs | 120 |
| xpGainMult | 1.25 |
| shardGainMult | 1.30 |

Wire forgive/retain/grace into existing combo/streak code paths if present; if T94 owns full forgive UX, T93 still **stores and displays** bonuses and applies if hooks exist — minimum: HUD shows active lattice bonuses; apply shardGainMult + xpGainMult + wpmCushion at least.

Class affinity: when buying, effectiveCost = round(cost * affinityCostMult); effectValue *= affinityEffectMult for matching `prefs.v3.character.classId`.

---

## 5. UI (sphere route)

- Graph view: nodes as medallions (CRE tokens if present); owned vs affordable vs grey-gated  
- Selected node panel: title, rank, effects, cost, Buy  
- Wallet chip (T91)  
- Back to Castle / Play  
- reducedMotion: no path animations required  
- Contrast ≥4.5  

### Soft nit from T92 — NEAR toasts

If a node is **one buy away** (adjacent, gates met, not owned) and `shards >= cost * 0.75` OR player just finished a scored run: fire SIE near chip/toast when opening sphere or after run → prefer `GENERIC_NEAR` or node `nearHint`. Cheap; skip if noisy (once per session per node id).

---

## 6. Hub integration (T92)

- Replace disabled Lattice stub with working navigation to `sphere`  
- War Room tier 0 may still grey other features; Lattice entry available from Hub once T93 ships (THE: **Lattice reachable from Hub even if War Room grey** — avoid softlock; War Room upgrade remains cosmetic/shop teaser)

---

## 7. Explicit non-goals

- Rings 3–4 keystones/mutex (T98)  
- Scout pick-3 stretch (T95+)  
- Shop board (T95)  
- Mobile shell (T96)  
- Portraits (T97)  
- Full miss-forgive UX polish if unfinished (T94) — bonuses + partial wire OK  

---

## 8. Acceptance (PET / TST)

### A. Graph

- [ ] A1 `sphere` route shows seed rings 0–2; `hub_core` owned  
- [ ] A2 Can buy adjacent node when shards suffice; owned rank increments  
- [ ] A3 Cannot buy non-adjacent / gated; grey + toast  
- [ ] A4 Spend confirm uses SIE SPEND_* copy  

### B. Economy / bonuses

- [ ] B1 shards debit; daily cap rules from T91 still hold on earns  
- [ ] B2 runtime bonuses recompute; at least xp/shard/wpmCushion apply  
- [ ] B3 Caps respected  
- [ ] B4 class affinity changes cost or effect for matching class  

### C. Integration

- [ ] C1 Hub Lattice control opens `sphere` (stub gone)  
- [ ] C2 Export/Import preserves owned ranks (max merge)  
- [ ] C3 `campaign.v3` untouched  
- [ ] C4 NEAR toast/chip fires at least once in happy path (or documented skip if session-dedup)  

### D. Pipe

- [ ] D1 One-file KEEP; ScaleSiege HOLD  
- [ ] D2 Soft nits → T94  

**PASS:** A–D green.

---

## 9. Handoff

| Role | Action |
|------|--------|
| **THE** | T93 LOCKED; standby T94 after PASS |
| **CRE** | Optional ring/medallion bank |
| **PET** | On COM PET-T93 LIVE |
| **TST** | Score §8 |
| **COM** | Assign LIVE |

**Report line:** `THE-T93 LOCKED — Docs/THE-T93_SPEC.md`