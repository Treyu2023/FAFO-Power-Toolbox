# THE-T92 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T91 PASS `69ec781` / `5a368cde`
**SIE paste AMEND:** full toast/UX pack folded (§6c); prior LOCK sha8 `8b233caa`.
**Prior DRAFT sha8:** `f8b07c1e` (local commit `55ed58c`); interim file hash before this LOCK pass folded SIE §6c
**Folds on LOCK:** CRE grey-door/thumb/medallion tokens (§6b) + SIE toast/UX strings (§6c)
**LOCK gate:** CLEARED — T91 PASS 69ec781; COM LOCK GO
**Cite:** `Docs/THE-T91_SPEC.md` sha8 `c77b3aa5` · `Docs/TRAINER_META_BRAINSTORM.md` sha8 `9a3b92a5`
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)
**BTΩ:** PET `1:45` → **Ω45** · CRE visual bank optional `1:25` → **Ω25**
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.
**Do not touch:** `campaign.v3` writes, launcher, TaxForge, ScaleSiege, Drawing Board, Scout stretch

---

## Wave locks (inherited — do not reopen)

| Lock | Value |
|------|-------|
| Sync | Export/Import `trainer-meta-pack.v1` (Merge: max PB + union nodes + max shards) |
| Castle locked | **GREY** visible non-interactive (Ryan override — NOT hide/fog) |
| Respec | 1 free lifetime then 50 ScoreShards; copy may say **Glyphs**; fields stay `shards` |
| Order | T91→T100 |
| Scout stretch | Parked until after Lattice MVP |

### PET constraints (still bind)

- Bag: `aitoolbox.typingTrainer.meta.v1` only for META  
- Castle = **in-Trainer overlay/route** (`hub` \| `play` \| `sphere`) — not separate HTML  
- Mobile capability CSS = T96 (do not expand here)  
- Portraits = T97 (`shared/typing-trainer/portraits/`)

---

## T92 one-liner

**Castle hub shell (overlay route) + GREY locked rooms + Gatehouse/Barracks/Library gating of existing modes.**

---

## 1. Route / overlay shell

Add Trainer route enum (name flexible; behavior fixed):

| Route | Meaning |
|-------|---------|
| `play` | Existing HARD3 trainer play (default cold load unchanged) |
| `hub` | Castle overlay — room grid + upgrade CTAs |
| `sphere` | Stub entry only in T92 (disabled/grey “Glyph Lattice — T93”) — do not build Lattice UI |

**Chrome**

- Entry control from play chrome: **Castle** / **Hub** button → `hub`  
- Hub chrome: **Back to Play** → `play`  
- Do not break existing mode pills that remain unlocked  
- Overlay sits above play; closing returns to last play mode without wiping run state unnecessarily (if mid-run, confirm or block hub — PET: prefer **block hub during active timed run**, allow when idle/results)

---

## 2. Castle rooms (v1 set for T92)

| Room id | Start tier | tierMax | Locked look | Unlocks (cumulative by tier) |
|---------|------------|---------|-------------|------------------------------|
| `gatehouse` | 0 | 1 | Always available | T0: practice + Sprint 15 |
| `barracks` | 0 | 2 | Available | T0: Sprint 30 visible; T1: Sprint 60 + podium hooks; T2: shardGain cosmetic crumb optional |
| `library` | 0 | 2 | If gated unmet → **GREY** | T1: Daily + word packs; T2: Weak-key Academy if present |
| `observatory` | 0 | 1 | **GREY** until Barracks≥1 | T1: Ghost race / ghost replay (if HARD3 present) |
| `throne` | 0 | 1 | **GREY** until Library≥1 | T1: Campaign entry (existing campaign) |
| `arcade` | 0 | 1 | **GREY** until Observatory≥1 OR Library≥2 | T1: Munchers/Breaker/Endless if present |
| `war_room` | 0 | 1 | **GREY** until Castle any tier sum≥3 | T1: enables Shop stub label “T95” + sphere teaser |
| `gallery` | 0 | 1 | **GREY** until Gatehouse played once OR shards>0 | T1: Portraits teaser “T97” |

Persist under existing stub:

```json
"castle": {
  "rooms": {
    "gatehouse": { "tier": 0, "decor": {} },
    "barracks": { "tier": 0, "decor": {} },
    "library": { "tier": 0, "decor": {} },
    "observatory": { "tier": 0, "decor": {} },
    "throne": { "tier": 0, "decor": {} },
    "arcade": { "tier": 0, "decor": {} },
    "war_room": { "tier": 0, "decor": {} },
    "gallery": { "tier": 0, "decor": {} }
  }
}
```

T91 may only have gatehouse+barracks — **T92 migrates** missing rooms in on load (add defaults; never wipe shards/scores).

---

## 3. GREY locked behavior (Ryan)

| State | UI | Interaction |
|-------|-----|-------------|
| Unlocked / available | Full color, upgrade CTA if tier\<tierMax | Click selects room; Upgrade spends shards |
| Locked | **Greyed** (desaturate + reduced opacity), name still readable (contrast ≥4.5 on label), lock reason tooltip/subtitle | **No** upgrade, **no** navigate-to-mode; click may show toast “Unlock by upgrading {req}” |
| Maxed | Badge MAX | No upgrade CTA |

**Not allowed:** removing DOM of locked rooms; fog-of-war hide; separate HTML.

---

## 4. Mode gating (existing modes)

Maintain a single `modeAccess` map derived from castle tiers (recompute on load + after upgrade):

| Mode / feature | Requires |
|----------------|----------|
| Practice / free type | Gatehouse ≥0 (always) |
| Sprint 15 | Gatehouse ≥0 |
| Sprint 30 | Barracks ≥0 |
| Sprint 60 | Barracks ≥1 |
| Sprint podium | Barracks ≥1 |
| Daily | Library ≥1 |
| Word packs | Library ≥1 |
| Weak-key Academy | Library ≥2 |
| Ghost race / replay | Observatory ≥1 |
| Campaign | Throne ≥1 |
| Munchers / Breaker / Endless | Arcade ≥1 |

**Locked mode UX in play chrome:** mode pill stays **visible but GREY** + disabled (same Ryan rule as rooms — consistency). Tooltip = which room/tier unlocks it.

Cold start after T92: Library/Observatory/Throne/Arcade/War/Gallery grey; Gatehouse+Barracks active at tier 0 so Sprint 15/30 still reachable (HARD3 not bricked).

---

## 5. Upgrade economy

```
upgradeCost[room][nextTier]  // from table
```

| Room | Costs by next tier index (tier 0→1, 1→2, …) |
|------|-----------------------------------------------|
| gatehouse | [15] |
| barracks | [25, 60] |
| library | [30, 70] |
| observatory | [40] |
| throne | [50] |
| arcade | [55] |
| war_room | [45] |
| gallery | [20] |

On Upgrade click:

1. If locked → toast, abort  
2. If `shards < cost` → toast “Need N Glyphs” (copy) / still debit field `shards`  
3. Else: `shards -= cost`; `wallet.lifetimeSpent += cost`; `rooms[id].tier++`; recompute `modeAccess`; save meta.v1  
4. Pulse room tier badge (reducedMotion → static)

Decor props out of T92 except empty `decor:{}` persist.

---

## 6. Hub UI minimum

- Title: Castle / Hub  
- Grid or row of 8 room cards (GREY states)  
- Selected room panel: tier, unlocks list, Upgrade button + cost  
- Wallet chip reused from T91 (Glyphs label OK)  
- Link stub: “Glyph Lattice (T93)” disabled/grey  
- Export/Import remain available (from T91) — hub or settings; do not regress

CRE: optional stone/banner visual bank — cite on PET LIVE; PET may ship functional chrome first.

---


## 6b. CRE / SIE polish fold (COM — LOCK cite)

**CRE polish pack (required cite on PET-T92 LIVE):**
- Grey-door visual language: desaturate + lock glyph; still readable labels
- Thumb HUD tokens for wallet/Glyphs chip (mobile-ready sizing; desktop uses same tokens additively)
- Room medallions / tier pips for castle cards

**SIE flavor (door + respec copy — use exact tone, adapt to UI strings):**
- Locked door toast/subtitle pattern (requirement room/tier)
- Respec copy reserved: first free / then 50 Glyphs (fields stay ScoreShards) — no respec button in T92
- Upgrade confirm microcopy short, no CDN assets

PET ships functional GREY + hub first; CRE art is additive CSS/classes, not a second KEEP file.

Suggested token classes (CRE): .tt-room--grey, .tt-room__medallion, .tt-hud-glyph (thumb-friendly min 44px hit), .tt-door-lock glyph. No CDN images in T92 — CSS/SVG inline only.

## 6c. SIE toast / UX pack (LOCKED fold — SIE paste)

**Cite:** SIE T92 toast/UX → THE-T92_SPEC. Earn-only tone. Player copy **Glyphs**; fields `shards`. Align CRE grey-door / thumb / medallions.

### Room id map (systems id → SIE display name)

| meta room id | SIE name |
|--------------|----------|
| gatehouse | Foyer / Meadow Hall |
| barracks | Iron Annex |
| library | Scriptorium |
| arcade | Combat Yard |
| observatory | Starlane Balcony |
| gallery | Noir Alcove |
| throne | Throne Atrium |
| war_room | Hearth Crypt |

Spend/Fortify still uses §5 shard costs (COM economy). Grey refuse = cannot bypass gates by paying; must meet room requirements. Soft errors do not refund spends.

### Unlock (on room becomes available / tier unlock lands)

| id | Copy |
|----|------|
| `MEADOW` | Meadow Hall lit. Soft green. Walk in. |
| `IRON` | Iron Annex open. Kill sheet clear. Enter. |
| `SCRIPTORIUM` | Scriptorium open. Ledger listening. |
| `COMBAT` | Combat Yard open. Tray and board live. |
| `STARLANE` | Starlane Balcony open. Lights low. Sail. |
| `NOIR` | Noir Alcove open. Soft neon on. |
| `THRONE` | Throne Atrium open. Keystone warm. |
| `HEARTH` | Hearth Crypt open. Leyline warm. |
| `GENERIC_UNLOCK` | Door warm. Room unlocked. Soft shoulders. |

### Near-unlock

| id | Copy |
|----|------|
| `GENERIC_NEAR` | Almost lit. One clean clear left. |
| `MEADOW_NEAR` | Six stones down. One more for the Hall. |
| `IRON_NEAR` | Spur almost open. One calm clear. |
| `SCRIPTORIUM_NEAR` | One verse left. Then shelves light. |
| `COMBAT_NEAR` | One wave clear. Yard gate softens. |
| `STARLANE_NEAR` | Silent Running almost done. Balcony waits. |
| `NOIR_NEAR` | Bank B stamp close. Neon flickers. |
| `THRONE_NEAR` | Keystone near. Crown or dust — finish clean. |
| `HEARTH_NEAR` | Pact almost sealed. Hearth still grey. |

### Upgrade spend confirm

| id | Copy |
|----|------|
| `SPEND_TITLE` | Spend Glyphs? |
| `SPEND_BODY` | Earn-only. Soft errors won't refund them. |
| `SPEND_YES` | Spend Glyphs |
| `SPEND_NO` | Keep Glyphs |
| `SPEND_OK` | Spent. Upgrade locked in. Clean hands. |
| `SPEND_BROKE` | Need more Glyphs. Earn them clean — no shop door. |
| `RESPEC_PAID` | Respec for Glyphs? First free already used. |

### Grey-door refuse

| id | Copy |
|----|------|
| `REFUSE_1` | Grey lock. Earn the gate — never buy the door. |
| `REFUSE_2` | Still sealed. Clear clean; Glyphs don't open rooms. |
| `REFUSE_SHOP` | No shop here. Light stones. Stamp the ledger. |
| `REFUSE_FOYER` | Start in the Foyer. Mud on the boots first. |

### Chips

| id | Copy |
|----|------|
| `CHIP_UNLOCK` | ROOM LIT |
| `CHIP_NEAR` | ALMOST |
| `CHIP_REFUSE` | EARN ONLY |
| `CHIP_SPEND` | GLYPHS |


## 7. Explicit non-goals (T92)

- Lattice buy/UI (T93)  
- Miss-forgive (T94)  
- Shop purchases (T95) — war_room may label only  
- Mobile shell (T96)  
- Portrait file picker (T97)  
- Scout stretch  

---

## 8. Acceptance (PET / TST)

### A. Shell

- [ ] A1 Route `hub` ↔ `play` works; cold load still `play`  
- [ ] A2 Hub blocked or confirmed-safe during active timed sprint  
- [ ] A3 `sphere` not playable (stub only)

### B. GREY rooms

- [ ] B1 All 8 rooms visible; locked ones grey not hidden  
- [ ] B2 Locked click does not upgrade; shows requirement  
- [ ] B3 Labels readable contrast ≥4.5

### C. Gating

- [ ] C1 Daily/word packs unreachable until Library ≥1 (pills grey+disabled)  
- [ ] C2 Sprint 15/30 still available at cold start  
- [ ] C3 Upgrade Library 0→1 spends shards and enables Daily  

### D. Data

- [ ] D1 Missing castle rooms migrated into meta.v1 without wiping wallet/scores  
- [ ] D2 `campaign.v3` not mutated  
- [ ] D3 Export/Import still round-trip castle tiers  

### E. Pipe

- [ ] E1 One-file KEEP; ScaleSiege untouched  
- [ ] E2 Soft nits → T93  

**PASS:** all §8 checks green. Soft nits → T93.

---

## 9. Handoff

| Role | Action |
|------|--------|
| **THE** | T92 LOCKED; standby T93 draft after PET-T92 LIVE/PASS |
| **CRE** | Optional castle card visual bank |
| **PET** | Implement on COM PET-T92 LIVE — cite this sha8 |
| **TST** | Score §8 |
| **COM** | Assign PET-T92 LIVE |

**Report line:** `THE-T92 LOCKED — Docs/THE-T92_SPEC.md`