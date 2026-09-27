# THE-T94 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T93 PASS `1f60510` / `a7111a82`  
**Cite:** `Docs/THE-T93_SPEC.md` sha8 `bdaf267d` · `Docs/THE-T91_SPEC.md` · META brainstorm miss-forgive §4  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:40` → **Ω40**  
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.  
**Out of T94:** Shop / Scout pick-3 (T95+) · Mobile shell (T96) · Char-select/portraits (T97) · Lattice rings 3–4 (T98)

---

## T94 one-liner

**Miss-forgive charges + streakRetain% + grace ms — HUD pips; wire lattice `runtimeBonuses` into live typing.**

`meta.stats` / lattice-derived bonuses already store values from T93 — T94 makes them **combat-real**.

---

## 1. Runtime stats (source of truth)

On run start / after lattice recompute, build:

```
combat = {
  forgiveChargesMax: baseForgive + runtimeBonuses.missForgiveChargesBonus,  // baseForgive default 0
  forgiveCharges: forgiveChargesMax,  // refill each scored run start
  streakRetainPct: clamp(runtimeBonuses.streakRetainPct, 0, 50),
  streakGraceMs: clamp(runtimeBonuses.streakGraceMs, 0, 120)
}
```

| Stat | Behavior |
|------|----------|
| **Forgive charge** | On miss, if `forgiveCharges > 0`: consume 1; **do not** break combo/streak; flash FORGIVE; miss **still counts** against accuracy |
| **streakRetainPct** | If no forgive left and miss would zero streak: set `streak = floor(streak * retainPct/100)` instead of 0 (if retainPct=0 → streak 0) |
| **streakGraceMs** | After a **correct** key, for `graceMs` wall-clock: a miss is treated as forgive-without-charge (jitter shield). Does not convert miss→hit for accuracy |

**Priority on miss:** (1) grace window active → grace absorb (2) else if charges>0 → spend charge (3) else apply retain% (4) else full streak/combo break.

---

## 2. Accuracy / scoring fairness

- Forgive / grace / retain **never** rewrite the typed character to correct  
- Misses still increment miss count / accuracy denominator  
- Grades, PB, ScoreShards earn rules unchanged (T91)  
- Combo meter juice may stay up on forgive; document if combo uses separate counter — match streak protect

---

## 3. HUD pips

- Near combo / streak meter: **forgive pips** = current charges (empty slots for spent)  
- On spend: pip empties; optional “FORGIVE” chip (SIE tone OK: short, soft)  
- retain% / grace: tiny numeric or icon only if space; else lattice bonus panel already shows  
- `reducedMotion`: static pip update, no particle burst  
- Contrast ≥4.5  
- Mobile sizing later (T96); desktop HARD3 chrome additive only

---

## 4. Wire lattice bonuses

| Bonus from T93 | T94 duty |
|----------------|----------|
| `missForgiveChargesBonus` | Feeds `forgiveChargesMax` |
| `streakRetainPct` | Feeds retain on break |
| `streakGraceMs` | Feeds grace window |
| `wpmCushion` / `accFloor` / xp / shard mults | Keep T93 behavior; no regress |

If a bonus was display-only in T93, T94 must hook the typing miss path.

Cold start with zero lattice: 0 charges, 0 retain, 0 grace — vanilla miss breaks streak (HARD3 baseline).

---

## 5. Soft nits

- NEAR lattice toasts already T93 — no reopen  
- If combo HUD fights pips, prefer pips left of combo; soft nit → T95 only if blocked  

---

## 6. Explicit non-goals

- Buying forgive in a shop  
- Scout pick-3  
- Mobile capability CSS  
- Character select / portraits  
- Respec UI  
- New lattice nodes (use existing forgive_1 / retain_1 / grace_1 / forgive_2)

---

## 7. Acceptance (A–D)

### A. Forgive

- [ ] A1 With charges≥1, miss spends 1 charge and streak/combo survive  
- [ ] A2 Accuracy still records the miss  
- [ ] A3 At 0 charges, miss no longer forgive-absorbs  

### B. Retain + grace

- [ ] B1 With retainPct>0 and 0 charges, miss sets streak to floor(streak*pct/100) not necessarily 0  
- [ ] B2 Within graceMs after correct key, miss absorbed without spending a charge  
- [ ] B3 Outside grace + 0 charges + retain 0 → full break  

### C. HUD + lattice

- [ ] C1 Pips match charges at run start (includes lattice bonus)  
- [ ] C2 Buying Soft Error / Hold Chain / Jitter Veil nodes changes next-run combat stats  
- [ ] C3 reducedMotion-safe pip updates  

### D. Pipe

- [ ] D1 `campaign.v3` untouched; meta.v1 only  
- [ ] D2 No shop/mobile/char-select scope creep  
- [ ] D3 One-file KEEP; ScaleSiege HOLD; soft nits → T95  

**PASS:** A–D green.

---

## 8. Handoff

| Role | Action |
|------|--------|
| **THE** | T94 LOCKED; standby T95 after PASS |
| **PET** | On COM PET-T94 LIVE |
| **TST** | Score §7 |
| **COM** | Assign LIVE |

**BTΩ reminder:** `1:40` Ω40  

**Report line:** `THE-T94 LOCKED — Docs/THE-T94_SPEC.md`