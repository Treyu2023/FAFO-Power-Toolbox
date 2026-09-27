# THE-T98 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T97 PASS `cf3085f` / `d4f4d7cd`  
**Cite:** THE-T91 amend respec policy · SIE `RESPEC_PAID` / `REFUSE_*` / `CHIP_REFUSE` · `Docs/THE-T97_SPEC.md` `4ec0a3ff` · Lattice T93 · Charms T96  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:35` → **Ω35**  
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.  
**Out of T98:** Mobile / PWA · full shop board · new classes/portraits · lattice rings 3–4 keystone expansion (optional light mutex only if already stubbed)

---

## T98 one-liner

**Respec UX — 1 free lifetime then 50 ScoreShards; reset lattice + charms loadout + char-select bindings per rules; confirm modal; soft SIE refuse chips if cheap.**

---

## 1. Cost policy (META lock — unchanged)

| Step | Rule |
|------|------|
| First respec | Free if `meta.respec.freeUsed === 0` and `constants.freeRespecLifetime === 1` |
| Later | Cost `constants.respecCost` (**50**) `shards` |
| Broke | Block; SIE `SPEND_BROKE` / need-more Glyphs |
| Copy | Player-facing **Glyphs**; fields stay `shards` / ScoreShards |
| After free | Set `respec.freeUsed = 1`; never refund free |

SIE lines:

- Free available: short confirm “First respec is free.”  
- Paid: `RESPEC_PAID` — “Respec for Glyphs? First free already used.”  
- Chips: `CHIP_SPEND` / `CHIP_REFUSE` as fits  

---

## 2. What respec resets

### 2.1 Lattice (Glyph Lattice)

| Reset | Behavior |
|-------|----------|
| `owned` | Clear all except `hub_core: { rank: 1 }` |
| `cursorNodeId` | `hub_core` |
| Runtime bonuses | Recompute → baseline |

**No shard refund** for previously spent node costs (earn-only economy).

### 2.2 Charms (T96)

| Reset | Behavior |
|-------|----------|
| `loadout` | Clear to `[]` or starter-only optional — **THE: clear loadout** |
| `inventory` | **Keep** unlocked charm ids (respec ≠ wipe collection) |
| sessionFlags / nextRun from pick3 | Clear latticeDiscount-style session flags tied to loadout; do not wipe pick3 history counters unless cheap |

### 2.3 Char-select (T97)

| Reset | Behavior |
|-------|----------|
| `classId` / active portrait | Revert to **Sprinter** + `class:Sprinter` (or last-safe starter) |
| `unlockedClassIds` | **Keep** (do not re-lock Raider etc. if unlocked) |
| custom portraits | **Keep** files/ids |

### 2.4 Explicitly NOT reset

- `shards` wallet (except paying the 50)  
- `scores` PB ledger  
- Castle room tiers  
- pick3 catalog unlocks / heat (optional clear heat — soft)  
- `campaign.v3`  

---

## 3. UX

1. Control in Hub / Lattice / Charm Case / Char Select — one **Respec** button (not three conflicting). Prefer Hub + Lattice.  
2. Modal confirm:  
   - Title: Respec  
   - Body lists what clears (lattice path, charm loadout, class → Sprinter) and cost (Free / 50 Glyphs)  
   - Buttons: Confirm / Cancel  
3. On Confirm: apply cost → apply resets → save meta.v1 → toast OK  
4. During active timed run: **block** respec (same as hub block) + refuse toast  
5. reducedMotion: no dramatic wipe animation required  
6. Contrast ≥4.5  

### Soft — SIE.REFUSE / CHIP_REFUSE

If cheap: grey/disabled respec when mid-run or broke uses `REFUSE_1`/`CHIP_REFUSE` patterns (“Earn only” not required for paid respec — use broke/refuse appropriately). Waive if conflicts with SPEND_ copy.

---

## 4. meta.v1 touchpoints

Already present from T91:

```json
"constants": { "respecCost": 50, "freeRespecLifetime": 1 },
"respec": { "freeUsed": 0 }
```

Optional:

```json
"respec": { "freeUsed": 0, "lastAt": null, "count": 0 }
```

Increment `count` on each successful respec. **No** `campaign.v3` writes.

---

## 5. Explicit non-goals

- Mobile / PWA  
- Full shop  
- New class kits or MANIFEST art  
- Refunding Glyphs spent on lattice/charms  
- Mutex keystone rings 3–4 full design (unless already in code stubs — do not expand)

---

## 6. Acceptance A–D

### A. Cost

- [ ] A1 First respec free; sets `freeUsed=1`  
- [ ] A2 Second costs 50 shards; broke blocks  
- [ ] A3 Copy may say Glyphs; fields `shards`  

### B. Resets

- [ ] B1 Lattice owned → hub_core only; bonuses baseline  
- [ ] B2 Charm loadout cleared; inventory kept  
- [ ] B3 Class/portrait → Sprinter starter; unlockedClassIds kept  
- [ ] B4 Wallet scores castle not wiped (aside from fee)  

### C. UX

- [ ] C1 Confirm modal before apply; Cancel no-ops  
- [ ] C2 Blocked mid timed run  
- [ ] C3 REFUSE/CHIP_REFUSE soft fold **OR** waived  

### D. Pipe

- [ ] D1 meta.v1 only; campaign.v3 untouched  
- [ ] D2 No mobile/shop/new-class creep  
- [ ] D3 One-file KEEP; ScaleSiege HOLD; soft→T99  

**PASS:** A–D green.

---

## 7. Handoff

| Role | Action |
|------|--------|
| **THE** | T98 LOCKED; standby T99 (castle tiers / content nodes per brainstorm) or COM remap |
| **SIE** | Confirm strings already filed |
| **PET** | On COM PET-T98 LIVE |
| **TST** | Score §6 |
| **COM** | Assign LIVE |

**Report line:** `THE-T98 LOCKED — Docs/THE-T98_SPEC.md`