# THE-T95 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T94 PASS `1586041` / `0d86b2a7`  
**Cite:** META brainstorm Scout stretch (Hades pick-3) · `Docs/THE-T94_SPEC.md` `3dc1ce39` · `Docs/THE-T91_SPEC.md`  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:35` → **Ω35** · CRE card art optional `1:20` → **Ω20**  
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.  
**Remap note:** Scout stretch pick-3 lands **here** (was parked post-Lattice). Not Balatro jokers, not Stardew wall, not Global Bonus Shop board.

---

## T95 one-liner

**Post-run / milestone pick-3 offer — choose 1 of 3 bonuses; persist in meta.v1; soft retain floor→0 heat if cheap.**

---

## 1. Trigger

Offer pick-3 when **any** of:

| Trigger | When |
|---------|------|
| `runComplete` | Scored sprint/daily (or other scored mode) finishes successfully |
| `milestone` | First PB of day OR castle room tier-up OR lattice node buy of cost≥15 (pick one milestone type if spammy — **THE: runComplete always; plus castle tier-up**) |

**Anti-spam:** max **1 pick-3 per scored run**; castle tier-up may queue one extra if not same session-second as run offer. Skip if `shardsEarnedToday` already at cap **only if** offer would grant shards — stat offers still OK.

Dismiss / skip allowed (no force pick). Skip = no bonus.

---

## 2. Offer generation

Build pool of **3 distinct** options from catalog (§3). RNG seeded by `dayKey + runId + shards` (deterministic enough for export debug; not cryptographic).

Rules:

- No duplicate `optionId` in the same trio  
- Prefer at least one **safe** (shards/xp) and one **combat** (forgive/retain/grace/cushion) when pool allows  
- Respect caps from T93/T94 — if at cap, replace with alternate  

---

## 3. Catalog (v1)

Each option:

```json
{
  "id": "p3_shard_small",
  "title": "Glyph Sip",
  "blurb": "+8 Glyphs now",
  "kind": "instant|runBuff|metaAdd",
  "effect": { "stat": "shards|xpGainMult|...", "op": "add|mult", "value": 8, "duration": "instant|nextRun|session" }
}
```

| id | kind | effect |
|----|------|--------|
| `p3_shard_small` | instant | +8 shards (clamp daily cap) |
| `p3_shard_med` | instant | +15 shards (clamp) |
| `p3_xp_sip` | nextRun | xpGainMult ×1.10 next scored run only |
| `p3_forgive_pip` | nextRun | +1 forgive charge for next run only (not permanent lattice) |
| `p3_retain_pulse` | nextRun | +15 streakRetainPct next run (still capped 50) |
| `p3_grace_pulse` | nextRun | +40 streakGraceMs next run (cap 120) |
| `p3_cushion` | nextRun | +2 wpmCushion next run |
| `p3_lattice_discount` | session | next lattice buy costs 25% less (one buy) |
| `p3_heat_cool` | instant | soft nit (§5): clear retain-heat flag |

Player copy may say Glyphs; fields stay `shards`.

**Not in catalog:** shop SKUs, joker-style persistent weird relics, portrait unlocks, mobile flags.

---

## 4. Persistence (meta.v1 only)

```json
"pick3": {
  "lastOfferAt": null,
  "lastPickedId": null,
  "nextRunBuffs": [],
  "sessionFlags": { "latticeDiscount": false },
  "heat": { "retainFloorHits": 0 }
}
```

- Do **not** mutate `campaign.v3`  
- Export/Import: include `pick3`; Merge = keep max heat counters careful — prefer **union nextRunBuffs by id** then clear spent; simple rule: Import Replace for pick3 or take import’s `nextRunBuffs` if local empty  

Apply `nextRunBuffs` at run start then clear spent buffs.

---

## 5. Soft nit — retain floor → 0 heat

When retain% saves streak but result streak becomes **0** (floor of small streak), count `heat.retainFloorHits++`.  

If cheap: after 3 such hits in a day, auto-include `p3_heat_cool` or show one-time tip “Retain needs a longer chain to matter.” `p3_heat_cool` resets counter.  

If wiring painful: document skip + soft→T96 — but **try** counter + tip toast.

---

## 6. UI

- Modal / panel over results: 3 cards, one Choose, one Skip  
- CRE medallion/card tokens optional  
- reducedMotion: no card shuffle animation required  
- Contrast ≥4.5  
- Does not block Export/Import or Hub access after dismiss  

---

## 7. Explicit non-goals

- Balatro-style joker inventory  
- Stardew decoration wall  
- Global Bonus Shop board (still later / parked)  
- Mobile shell (T96)  
- Char-select / portraits (T97)  
- New lattice rings  

---

## 8. Acceptance A–D

### A. Offer

- [ ] A1 After scored run, pick-3 appears (or Skip path works)  
- [ ] A2 Three distinct options from catalog  
- [ ] A3 Choose applies effect; Skip applies nothing  

### B. Effects

- [ ] B1 Instant shards respect daily cap  
- [ ] B2 nextRun buff applies once then clears  
- [ ] B3 No campaign.v3 writes  

### C. Soft heat

- [ ] C1 retainFloorHits increments when retain leaves streak at 0 **OR** explicitly waived in KEEP notes  
- [ ] C2 Tip or `p3_heat_cool` available after threshold **OR** waived  

### D. Pipe

- [ ] D1 No shop/joker/mobile/char-select creep  
- [ ] D2 One-file KEEP; ScaleSiege HOLD; soft→T96  

**PASS:** A–D green (C may soft-waive with note).

---

## 9. Handoff

| Role | Action |
|------|--------|
| **THE** | T95 LOCKED; standby T96 after PASS |
| **CRE** | Optional pick-3 card bank |
| **PET** | On COM PET-T95 LIVE |
| **TST** | Score §8 |
| **COM** | Assign LIVE |

**Report line:** `THE-T95 LOCKED — Docs/THE-T95_SPEC.md`