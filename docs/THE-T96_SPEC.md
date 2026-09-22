# THE-T96 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T95 PASS `1235728` / `2bfd456c`  
**Cite:** Scout stretch remap (Balatro-style modifiers) · `Docs/THE-T95_SPEC.md` `629d46d2` · META brainstorm §7 hooks  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:45` → **Ω45** · CRE chip/card art optional `1:25` → **Ω25**  
**Constraints:** No HTML from THE. No CDN. No IP copy of Balatro art/names. ScaleSiege HOLD.  
**Remap:** Original brainstorm T96 mobile shell → **slips to T97+**. This KEEP = session/run **Glyph Charms** (joker-like stacking modifiers).

---

## T96 one-liner

**Session/run Glyph Charms — stacking catalog buffs (adapt Balatro joker *pattern*, original names); meta.v1 only; soft seed/thin-pool/is-locking juice if cheap.**

---

## 1. Concept (ours: Glyph Charms)

Like Balatro jokers: a small set of active modifiers that reshape a run.  
Unlike Balatro: no poker hands, no ante blind IP, no shop buy-joker loop mandatory — Charms are **earned/selected** via pick-3 hooks + optional Glyph spend unlock, then **equip** into limited slots for the session or next runs.

| Term | Meaning |
|------|---------|
| Charm | One modifier definition from catalog |
| Loadout | Up to **3** equipped charm ids (session) |
| Inventory | Unlocked charm ids (meta persistent) |

---

## 2. Data (meta.v1 only)

```json
"charms": {
  "inventory": ["charm_steady_hand"],
  "loadout": ["charm_steady_hand"],
  "slotMax": 3,
  "seed": null,
  "thinPoolHits": 0
}
```

- Do **not** mutate `campaign.v3`  
- Export/Import: union inventory; loadout = intersection with inventory (trim to slotMax)  
- Starter unlock: `charm_steady_hand` free in inventory on migrate  

---

## 3. Catalog (v1 — original names)

Each charm:

```json
{
  "id": "charm_steady_hand",
  "title": "Steady Hand",
  "blurb": "+1 forgive charge this run",
  "rarity": "C|B|A",
  "stackRule": "unique|rank",
  "effects": [{ "stat": "missForgiveChargesBonus", "op": "add", "value": 1, "scope": "run" }],
  "mutexGroup": null,
  "unlock": { "how": "starter|pick3|shards", "cost": 0 }
}
```

| id | rarity | effect (run scope unless noted) |
|----|--------|----------------------------------|
| `charm_steady_hand` | C | +1 forgive charge |
| `charm_long_fuse` | C | +20 streakGraceMs |
| `charm_iron_loop` | B | +10 streakRetainPct |
| `charm_glyph_magnet` | B | shardGainMult ×1.08 |
| `charm_scholar_ink` | B | +1 accFloor |
| `charm_sprinter_wind` | B | +2 wpmCushion |
| `charm_echo_pay` | A | On forgive spend: +2 shards (cap ignore daily? **No** — still daily cap) |
| `charm_double_sip` | A | First pick-3 instant shard option this session worth ×2 once |
| `charm_glass_tempo` | A | xpGainMult ×1.12; if accuracy <90% at run end, lose the XP mult (glass) |

**Caps:** still respect T93/T94 combat caps after summing lattice + charms + pick3 nextRun buffs.  
**Mutex:** optional later; T96 none required except unique ids in loadout.

Unlock:

- starter: Steady Hand  
- pick3: may offer `unlock_charm_*` as a pick-3 option (add 1–2 catalog entries to T95 pool **or** T96 injects into pick3 generator)  
- shards: War Room / Hub “Charm Case” spend 25/40/60 by rarity to unlock one random not-owned (anti-shop-creep: **single panel**, not full shop board)

---

## 4. Apply order

At run start:

1. Lattice runtimeBonuses  
2. Equipped charms (run scope)  
3. pick3 `nextRunBuffs`  
4. Clamp caps  

Mid-run: charms that react to events (`charm_echo_pay`) hook miss-forgive path from T94.

---

## 5. UI

- Hub or sphere-adjacent **Charm Case** panel: inventory grid, drag/click equip up to 3, grey empty slots  
- In-run: small charm icons near forgive pips  
- reducedMotion: static  
- Contrast ≥4.5  
- CRE: card chips optional  

---

## 6. Soft juice (if cheap)

| Issue | Fold |
|-------|------|
| **Seed** | `charms.seed = hash(dayKey)` for unlock RNG; show seed in Export debug optional |
| **Thin pool** | If unlocked/all owned ≥80% catalog, `thinPoolHits++` and tip “Charm pool thin — prestige later”; bias pick3 toward shards |
| **is-locking juice** | When equipping A-rarity, brief lock-in sheen (skip if reducedMotion); SIE one-liner OK |

Waive with KEEP note if any one blocks PASS.

---

## 7. Explicit non-goals

- Full Balatro ante/shop/blind structure  
- Mobile shell (T97+)  
- Char-select / portraits (T97+)  
- Global Bonus Shop wall  
- Stardew decoration  
- Lattice rings 3–4  

---

## 8. Acceptance A–D

### A. Inventory / loadout

- [ ] A1 Steady Hand present after migrate; equip ≤3  
- [ ] A2 Unequip works; loadout persists in meta.v1  
- [ ] A3 Export/Import preserves inventory union  

### B. Effects

- [ ] B1 Equipped charms modify next run combat/economy as catalog  
- [ ] B2 Caps still hold with lattice+charms  
- [ ] B3 glass_tempo strips XP mult when acc <90% at end  

### C. Soft

- [ ] C1 seed and/or thin-pool tip present **OR** waived in notes  
- [ ] C2 No campaign.v3 writes  

### D. Pipe

- [ ] D1 No mobile/char-select/full-shop creep  
- [ ] D2 One-file KEEP; ScaleSiege HOLD; soft→T97  

**PASS:** A–D green.

---

## 9. Handoff

| Role | Action |
|------|--------|
| **THE** | T96 LOCKED; standby T97 (mobile and/or portraits per COM) |
| **CRE** | Optional charm chip bank |
| **SIE** | Optional charm blurb pass |
| **PET** | On COM PET-T96 LIVE |
| **TST** | Score §8 |
| **COM** | Assign LIVE |

**Report line:** `THE-T96 LOCKED — Docs/THE-T96_SPEC.md`