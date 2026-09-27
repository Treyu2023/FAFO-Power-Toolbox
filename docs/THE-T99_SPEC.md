# THE-T99 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T98 PASS `b4f0526` / `c80951c4`  
**Cite:** Ryan META lock Export/Import · THE-T91 pack `trainer-meta-pack.v1` · `Docs/THE-T98_SPEC.md` `5faafe5b`  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**BTΩ:** PET `1:40` → **Ω40**  
**Constraints:** No HTML from THE. No CDN. No phone-home. ScaleSiege HOLD.  
**Remap note:** Brainstorm T99 castle tiers → **slips**; this KEEP = cross-device **meta sync** polish.

---

## T99 one-liner

**Export/Import meta.v1 sync across devices — schema version + merge rules; safe import UI (no raw unsafe prompt); soft single Respec entry if cheap.**

---

## 1. Pack schema

```json
{
  "schema": "trainer-meta-pack.v1",
  "schemaVersion": 1,
  "exportedAt": "ISO-8601",
  "app": "Typing Assistant Trainer",
  "meta": { /* full aitoolbox.typingTrainer.meta.v1 object */ }
}
```

### Must round-trip inside `meta`

| Area | Fields |
|------|--------|
| Wallet | `shards`, `shardsEarnedToday`, `dayKey`, `wallet.*` |
| Scores | `scores.*` PB ledger |
| Lattice | `lattice.cursorNodeId`, `lattice.owned` |
| Charms | `charms.inventory`, `charms.loadout`, `charms.slotMax` |
| Portraits / unlocks | `portraits.*`, `unlockedClassIds` |
| Respec | `respec.freeUsed`, `respec.count?`, `constants.respecCost`, `freeRespecLifetime` |
| Castle | `castle.rooms` tiers |
| Pick3 / heat | `pick3.*` if present |
| Constants | `dailyShardCap`, `repeatMult`, etc. |

Reject import if `schema` ≠ `trainer-meta-pack.v1` OR `meta.schema` missing/wrong — show toast, **do not** partial-apply.

---

## 2. Actions

| Action | Behavior |
|--------|----------|
| **Export** | Download `.json` file (and optional copy-textarea). Filename `trainer-meta-YYYYMMDD.json` |
| **Import Replace** | Confirm modal → overwrite entire meta bag with `pack.meta` (migrate missing keys to defaults) |
| **Import Merge** | Confirm modal → apply merge rules (§3) |

### Safe import UI (required)

- **No** `window.prompt` / raw paste-only as the only path if that is current “unsafe prompt import”  
- Prefer: file `<input type="file" accept="application/json,.json">` + Confirm modal summarizing shard delta / class / lattice node count  
- Optional advanced: textarea paste behind “Paste JSON” disclosure — still Confirm before write  
- Invalid JSON → error toast; no throw to blank HUD  

---

## 3. Merge rules (Ryan lock)

| Field | Merge |
|-------|-------|
| `shards` | `max(local, import)` |
| `wallet.lifetimeEarned/Spent` | `max` each |
| `scores.*` | per-key best WPM; tie → higher acc |
| `lattice.owned` | union by nodeId; `rank = max` |
| `lattice.cursorNodeId` | prefer local if owned locally else import |
| `charms.inventory` | union ids |
| `charms.loadout` | intersection with merged inventory; trim to `slotMax`; prefer local order then fill from import |
| `portraits.unlockedClassIds` | union |
| `portraits.activeId` / class | keep local if still unlocked else import if unlocked else Sprinter |
| `respec.freeUsed` | `max(local, import)` (0/1) — **never** restore free if either side used |
| `respec.count` | `max` |
| `castle.rooms` | per-room `tier = max` |
| `pick3.nextRunBuffs` | prefer local if non-empty else import; or union by id then cap |
| `dayKey` / `shardsEarnedToday` | if same `dayKey`: `shardsEarnedToday = min(120, max(local, import))` soft — **THE: if same day use max then clamp cap; if different days keep local day counters** |
| `constants` | take max of numeric caps/costs where safe; never lower `respecCost` below 50 if either says 50 |

After merge: recompute lattice bonuses; save meta.v1; toast summary.

---

## 4. Soft — park lattice-vs-hub Respec entry

If cheap: ensure **one** Respec control (Hub primary; Lattice links to same modal or hides duplicate). Park/hide second entry to avoid double-fee confusion. Waive with note if already single.

---

## 5. Explicit non-goals

- Mobile / PWA / cloud sync API  
- Full shop  
- New classes  
- Auto LAN sync  
- Mutating `campaign.v3`  

---

## 6. Acceptance A–D

### A. Export

- [ ] A1 Export file has `trainer-meta-pack.v1` + `schemaVersion` + full meta  
- [ ] A2 Includes shards, lattice owned, charms inv/loadout, unlocks, `respec.freeUsed`  

### B. Import

- [ ] B1 Replace overwrites after Confirm; Cancel no-ops  
- [ ] B2 Merge applies max shards, union lattice ranks, union charm inventory, max freeUsed  
- [ ] B3 Invalid/wrong schema refused safely  
- [ ] B4 No sole dependency on unsafe `prompt()` for import  

### C. Soft

- [ ] C1 Single Respec entry (hub vs lattice) **OR** waived  
- [ ] C2 `campaign.v3` untouched  

### D. Pipe

- [ ] D1 No mobile PWA / shop / new-class creep  
- [ ] D2 One-file KEEP; ScaleSiege HOLD; soft→T100  

**PASS:** A–D green.

---

## 7. Handoff

| Role | Action |
|------|--------|
| **THE** | T99 LOCKED; standby T100 META polish |
| **PET** | On COM PET-T99 LIVE |
| **TST** | Score §6 |
| **COM** | Assign LIVE |

**Report line:** `THE-T99 LOCKED — Docs/THE-T99_SPEC.md`