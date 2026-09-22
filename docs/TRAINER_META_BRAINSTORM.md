# THE — Typing Trainer META Brainstorm (docs only)

**Status:** BRAINSTORM LOCKED for COM review — 2026-09-22  
**Lane:** THE systems architecture. No HTML. ScaleSiege HOLD.  
**Cite baseline:** HARD3 complete @ `618b14a` (T90). Next KEEP ids start **T91+**.  
**Inspirations (adapt, do not copy IP):** FFX Sphere Grid · Path of Exile passive tree · Slay the Spire act map · Hades Mirror of Night · Vampire Survivors unlock board.

Ryan ask (7 pillars):
1. Mobile variant (auto-detect phone screen + soft keyboard)
2. Global progression desktop↔mobile → high scores → points → Global Bonus Shop
3. Sphere-grid–style path unlock nodes stacking small→big bonuses; sync with existing classes
4. Miss-forgiveness / streak-retain stats
5. Castle hub — decorate/upgrade rooms; modes unlock gradually
6. Character select from images on Ryan’s PC
7. Steal *hooks* (addiction/fun loops) from popular RPGs/indie — mechanics, not art/IP

---

## 0. Design north star

One **meta save** drives both shells (desktop Trainer + mobile Trainer). Session play earns **ScoreShards** (points). Shards buy **Grid Nodes**, **Castle Upgrades**, and **Shop Perks**. Classes remain the *identity* layer; the Grid is the *depth* layer. Castle is the *pacing* layer (what modes exist). Mobile is a *viewport + input* profile on the same save — not a second character.

**Non-goals v1 meta:** online accounts, cloud sync API, GitHub, CDN assets, multiplayer.

---

## 1. Sphere-grid data model

### 1.1 Metaphor (ours: **Glyph Lattice**)

Like FFX Sphere Grid: move along connected nodes; activate with a cost; early nodes are tiny, later clusters compound.  
Unlike FFX: no job-locked spheres as primary lock — **class affinity** soft-weights cost/effect instead.  
Like PoE: branching clusters with keystones (rare, powerful, mutually exclusive pairs).  
Like Hades mirrors: ranked ranks on a node (1→N) instead of only binary unlock.  
Like VS unlocks: some nodes are “content unlock” (mode/room) not pure stats.

### 1.2 Schema

```json
{
  "schema": "aitoolbox.trainer.glyphLattice.v1",
  "version": 1,
  "startNodeId": "hub_core",
  "nodes": [
    {
      "id": "hub_core",
      "kind": "hub|stat|keystone|content|bridge",
      "title": "Core Focus",
      "ring": 0,
      "pos": { "x": 0, "y": 0 },
      "edges": ["wpm_1", "acc_1", "forgive_1"],
      "costShards": 0,
      "rankMax": 1,
      "effects": [],
      "gates": {},
      "classAffinity": { "Sprinter": 1.0, "Scholar": 1.0 },
      "mutexGroup": null,
      "loreTag": "optional short flavor"
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `kind` | `hub` (free travel), `stat` (stackable small bonus), `keystone` (big unique), `content` (unlocks mode/room), `bridge` (empty connector, cheap) |
| `ring` | Distance band from core (0 hub → 6+ outer). UI can draw rings like Sphere Grid. |
| `edges` | Undirected adjacency list (store once; normalize on load) |
| `costShards` | Base cost to unlock rank 1 (rank N cost = `costShards * rankCostMult[N]`) |
| `rankMax` | Hades-style levels; default 1 for keystones, 3–5 for stats |
| `effects[]` | `{ "op": "add|mult|unlock", "stat": "...", "value": number, "perRank": bool }` |
| `gates` | Unlock requirements *before* you can buy (see 1.4) |
| `classAffinity` | Multiplier on effect strength and/or cost discount for matching `prefs.v3.character.classId` |
| `mutexGroup` | PoE-ish: only one node with same group active (e.g. `ks_aggression` vs `ks_precision`) |

### 1.3 Effect ops (stack into `meta.bonuses`)

| `stat` | Stacking | Example |
|--------|----------|---------|
| `xpGain` | mult | +2% XP / rank |
| `shardGain` | mult | +3% shards from scores |
| `wpmCushion` | add | treat WPM as +1 for grade bands |
| `accFloor` | add | soft floor toward accuracy grade |
| `missForgiveCharges` | add | charges of miss-forgiveness / run |
| `streakRetainPct` | add | % of streak kept on forgive |
| `streakGraceMs` | add | ms grace before combo break |
| `fxIntensityCap` | add | juice headroom (respect reducedMotion) |
| `unlockMode` | unlock | `modeId` string |
| `unlockRoom` | unlock | `roomId` string |
| `classSlot` | unlock | extra unlock slot for class passives |

**Compounding rule:** `final = (base + Σ add) * Π mult`. Cap table in prefs (anti-snowball). Keystones may set `exclusive: true`.

### 1.4 Gates (unlock before purchase)

```json
"gates": {
  "minLevel": 5,
  "requiresNodes": ["acc_1", "acc_2"],
  "requiresClass": null,
  "requiresRoomTier": { "library": 1 },
  "requiresHighScore": { "mode": "sprint30", "metric": "wpm", "min": 60 },
  "requiresCastleTier": 2
}
```

Must stand adjacent *or* have path from an **activated** node (Sphere Grid movement). v1 proposal: **activation cursor** — player “stands on” a node; can buy adjacent; free walk on owned hubs/bridges.

### 1.5 Class sync

Existing HARD3 classes stay. Lattice does **not** replace class pick.

- Each class gets a **favored arc** (highlighted path): e.g. Sprinter → WPM/cushion; Scholar → accuracy/weak-key; Streaker → streakRetain/grace; Guardian → forgive charges; Ghost → ghost-race bonuses; Zen → reduced-pressure / cushion; etc.
- Affinity: matching class → `costShards * 0.85` and `effect * 1.15` (tunable).
- Optional **class keystone** at ring 3 that requires that class (respec via existing global bonus / shard sink).

### 1.6 Seed layout (rings)

| Ring | Theme | ~Node count |
|------|-------|-------------|
| 0 | Hub Core | 1 |
| 1 | Fundamentals (WPM, Acc, Forgive) | 6–8 |
| 2 | Mode bridges (Sprint/Daily/Campaign crumbs) | 6 |
| 3 | Class-flavored clusters | 10–12 |
| 4 | Keystones (mutex pairs) | 4–6 |
| 5 | Castle content unlocks | 6–8 |
| 6 | Prestige / New Game+ crumbs | 4 |

Total v1 target: **~40–50 nodes**, not PoE-scale.

---

## 2. Point economy (ScoreShards)

### 2.1 Earn

From **verified high-score events** (mode + stage + difficulty), not raw keystrokes:

```
shards = floor( scorePoints * modeMult * diffMult * firstClearBonus * dailyMult )
```

| Source | `scorePoints` sketch |
|--------|----------------------|
| Sprint 15/30/60 | `gradeBand * durationWeight` (S/A/B/C table) |
| Daily | fixed clear + PB beat bonus |
| Campaign node/boss | clear + star rating |
| Munchers / Breaker | wave depth × accuracy |
| Ghost race win | flat + margin |

**PB ledger:** store best per key  
`scores.v1[ profileId ][ modeId ][ stageId ][ difficulty ] = { wpm, acc, stars, at }`  
Only **new PB** or **daily first clear** pays full shards; repeats pay `repeatMult` (e.g. 0.15) to allow grinding without infinite print.

### 2.2 Sink

| Sink | Typical cost | Notes |
|------|--------------|-------|
| Lattice node rank | 5–80 | Primary sink |
| Castle room upgrade | 20–120 | Pacing |
| Global Bonus Shop | 15–100 | Soft cosmetics + rare meta |
| Respec token | 50 | Clear mutex / move class keystone |
| Char portrait slot | 10 | After free first slots |

### 2.3 Global Bonus Shop (separate from Lattice)

Shop rows are **not** on the grid — impulse buys / cosmetics / QoL (VS-style unlock board feel):

- Juice packs, caret skins, title strings  
- One-shot: “+1 miss forgive tomorrow”  
- Permanent thin bonuses that *could* have been grid but are shop for clarity  

Shop stock gated by Castle tier + lattice hub progress so the board doesn’t dump everything day one.

### 2.4 Anti-exploit

- Cap shards/day soft (`dailyShardCap`, default 120) with overflow → cosmetic-only currency later  
- No shard from idle; must complete run  
- Mobile and desktop share cap (one wallet)

---

## 3. Mobile profile + one save with desktop

### 3.1 Detection

```
isMobileShell =
  (coarse pointer || maxTouchPoints > 0) &&
  (min(viewportW, viewportH) < 720 || visualViewport height shrinks > 20% on focus) &&
  (UA mobile token OR standalone PWA display-mode)
```

Also: `prefs.v3.forceShell = auto|desktop|mobile` override.

**Mobile UX deltas (same HTML file, CSS/JS branches):**

- Typewell-first, stacked chrome, 44×44 targets  
- Soft-keyboard: pin input focus strategy; compact HUD; hide non-essential FX (`mobileFxProfile: calm`)  
- Virtual key assist optional (not a second game)

### 3.2 Single save model

| Layer | Key | Scope |
|-------|-----|-------|
| Meta wallet + lattice + castle + scores | `aitoolbox.typingTrainer.meta.v1` | Shared |
| Legacy prefs / character / FX | `prefs.v3` (existing) | Shared |
| Shell chrome only | `aitoolbox.typingTrainer.shell.v1` | Per-device OK to diverge |

**Sync without cloud (v1):**

1. **Same browser profile / same machine** — automatic via `localStorage` (desktop + mobile browser on same origin if ever hosted; file:// is per-path — see below).  
2. **Export/Import pack** (primary cross-device): one JSON `trainer-meta-pack.v1` = meta + prefs slice + scores + lattice state + castle + portraits refs. QR or file share.  
3. Optional later: LAN sync via existing toolbox patterns — **out of T91–T95**.

**file:// caveat:** desktop file path vs phone copy are different origins. v1 acceptance = Export on desktop → Import on phone (and reverse). Document in UI.

**Conflict:** last-write-wins on Import Replace; Merge prefers max(PB), union(owned nodes), max(shards) with audit log entry.

### 3.3 Identity

`profileId` default `local-ryan`; character class + portrait bind to profile. Multiple profiles optional T9x later.

---

## 4. Miss-forgiveness / streak-retain

New combat stats (Lattice + class passives feed these):

| Stat | Behavior |
|------|----------|
| `missForgiveCharges` | On miss, if charges > 0: consume 1, **do not** break combo/streak; flash “FORGIVE”; still count miss for accuracy |
| `streakRetainPct` | If forgive unavailable and miss would break streak: set streak to `floor(streak * retainPct/100)` instead of 0 |
| `streakGraceMs` | After correct key, window where a miss is auto-forgiven without charge (tiny, e.g. 30–80ms) — anti-jitter, not godmode |

**UI:** charges as pips near combo meter; reducedMotion → static pip update.  
**Fairness:** forgive does not convert miss→hit for scoring grades; only protects streak/combo juice.

---

## 5. Castle hub (pacing + unlocks)

### 5.1 Metaphor

Hub screen (StS act map energy, VS collection board pacing): a **castle** with rooms. Decorating/upgrading rooms spends shards and **unlocks modes gradually**.

| Room | Unlocks when upgraded | Modes / features |
|------|----------------------|------------------|
| Gatehouse (start) | Tier 0 free | Sprint 15, basic practice |
| Barracks | T1 | Sprint 30/60, podium |
| Library | T1–2 | Word packs, Daily, Weak-key Academy |
| Observatory | T2 | Ghost race / ghost replay |
| Throne | T2–3 | Campaign acts, bosses |
| Arcade | T3 | Munchers, Breaker, Endless |
| War Room | T3 | Lattice deep rings + Shop tier 2 |
| Gallery | any | Character portraits / cosmetics |

### 5.2 Room schema

```json
{
  "id": "library",
  "tier": 0,
  "tierMax": 3,
  "upgradeCost": [0, 25, 60, 100],
  "unlocksAtTier": {
    "1": ["mode:daily", "mode:wordPack"],
    "2": ["mode:weakKey"],
    "3": ["shopStock:library"]
  },
  "decor": { "wallpaperId": null, "propIds": [] }
}
```

Decor is cosmetic sink + mild shardGain or juice; upgrades are gated content.

**Cold start:** only Gatehouse + Barracks T0 visible. Other rooms fogged (StS-like unknown) until prior tier or adjacent room opens.

---

## 6. Character select from PC images

### 6.1 Flow

- Gallery room / Character Select: “Add portrait” → file input (`accept="image/*"`)  
- Store as **data URL or IndexedDB blob** keyed `portraits.v1[id]` (prefer IndexedDB if size; fallback compressed dataURL with max edge 512px)  
- Bind `prefs.v3.character.portraitId`  
- Class pick still separate (HARD3 classes); portrait is face, class is kit

### 6.2 Safety

- Local only; no upload  
- Strip EXIF on canvas rewrite  
- Quota warn if pack export > N MB  
- Default pack ships 0 user images; placeholders OK

---

## 7. Addiction / fun hooks (stolen patterns, original skin)

| Hook | From (pattern) | Our use |
|------|----------------|---------|
| Short run → small permanent | VS unlocks | Every session can afford *something* on Lattice/Castle |
| Build identity | PoE / FFX | Class + Lattice path screenshot-worthy |
| One more node | Sphere Grid | Adjacent cheap bridges tease next cluster |
| Daily login / daily seed | live-ops lite | Daily room chest: shards + stock refresh |
| Ranked mirrors | Hades | Rerank Lattice nodes 1→N for juice |
| Act map curiosity | StS | Fogged castle rooms |
| Near-miss protect | platformer forgiving | Miss-forgive charges (skill expression, not RNG loot) |
| Collection | VS / roguelikes | Portrait gallery + titles + history seals (HARD3 seals stay) |
| Prestige crumb | many RPGs | Ring-6 nodes after Castle T3; optional meta reset keeps cosmetics |

**Avoid:** dark-pattern timers that punish absence; pay-to-win; loot boxes.

---

## 8. Save blob (target)

```json
{
  "schema": "aitoolbox.typingTrainer.meta.v1",
  "shards": 0,
  "shardsEarnedToday": 0,
  "dayKey": "2026-09-22",
  "lattice": {
    "cursorNodeId": "hub_core",
    "owned": { "hub_core": { "rank": 1 } }
  },
  "castle": { "rooms": { "gatehouse": { "tier": 0, "decor": {} } } },
  "shop": { "bought": [], "stockSeed": "..." },
  "scores": {},
  "stats": {
    "missForgiveChargesBonus": 0,
    "streakRetainPct": 0,
    "streakGraceMs": 0
  },
  "portraits": {},
  "history": []
}
```

Derived bonuses recomputed from lattice+shop+class on load → merge into runtime `meta.bonuses` (do not dual-write conflicting prefs).

---

## 9. Phased KEEP plan T91+ (BTΩ)

Ω = bots × minutes. Estimates assume PET primary (+ CRE visual bank where noted). One LIVE KEEP at a time.

| KEEP | Scope | BTΩ | Ω |
|------|-------|-----|---|
| **T91** | Meta save stub `meta.v1` + ScoreShards earn from existing sprint/daily PB only + wallet HUD | `1:35` | Ω35 |
| **T92** | Castle hub shell (rooms fog/unlock) + Gatehouse/Barracks/Library gating of *existing* modes (hide modes behind rooms) | `1:45` + CRE `1:25` | Ω45 / CRE Ω25 |
| **T93** | Glyph Lattice UI + data seed rings 0–2; buy adjacent; apply add/mult bonuses to XP/shards/cushion | `1:55` + CRE `1:30` | Ω55 / CRE Ω30 |
| **T94** | Miss-forgive charges + streakRetain + grace; pips on combo HUD; Lattice ring-1 forgive nodes | `1:40` | Ω40 |
| **T95** | Global Bonus Shop v1 + daily shard cap + firstClear/PB rules polish | `1:35` | Ω35 |
| **T96** | Mobile shell detect + compact HUD + forceShell prefs; typewell-first; export/import pack round-trip | `1:50` | Ω50 |
| **T97** | Character portraits from local files + Gallery room + bind to class select | `1:30` + CRE `1:20` | Ω30 / CRE Ω20 |
| **T98** | Lattice rings 3–4 (class clusters + keystones/mutex) + class affinity | `1:45` | Ω45 |
| **T99** | Castle tiers 2–3 (Observatory/Throne/Arcade) + content nodes on Lattice | `1:40` | Ω40 |
| **T100** | META polish: caps, reducedMotion, empty states, pack schema freeze, TST full matrix | `1:40` + TST heavy | Ω40 |

**Suggested COM order:** T91 → T92 → T93 → T94 → T95 → T96 → T97 → T98 → T99 → T100.  
**Parallel docs:** CRE visual banks one KEEP ahead; TST PREP each slice; THE deltas only on COM request.  
**Sum PET-ish:** ~Ω415 across T91–T100 (~7×Ω60 days if single bot) — plan as multi-week wave, not one weekend.

### 9.1 Acceptance themes (per wave)

- T91: shards change only on PB/daily rules; HUD shows wallet  
- T92: modes not in unlocked rooms are unreachable; Ryan can upgrade Library  
- T93: can buy path from hub; bonuses apply; refresh-safe  
- T94: forgive pips work; accuracy still counts misses  
- T96: phone-width layout; export desktop → import “mobile” profile works  
- T100: no CDN; local only; ScaleSiege untouched

---

## 10. Risks / open questions for COM + Ryan

1. **file:// multi-device** — confirm Export/Import is acceptable v1 “sync.”  
2. **Shard inflation** — start stingy; T100 retune.  
3. **Mode hide vs grey** — recommend hide until room unlock (stronger Castle fantasy).  
4. **Respec** — shard sink vs free weekly; recommend paid respec.  
5. **Portrait storage** — IndexedDB vs dataURL; PET picks with quota warn.  
6. **Drawing Board app** — separate; META stays inside Trainer.html one-file KEEP rule.

---

## 11. Handoff

| Role | Action |
|------|--------|
| **THE** | This brainstorm delivered; standby for formal THE-T91+ specs when COM locks order |
| **CRE** | Visual banks: Castle map, Lattice rings, forgive pips, Shop board, mobile chrome |
| **PET** | Wait COM LIVE assignment; one HTML KEEP |
| **TST** | PREP matrices from §9 when COM schedules |
| **COM** | Prioritize / cut / assign; ScaleSiege HOLD |

**Report line:** `THE META BRAINSTORM — Docs/TRAINER_META_BRAINSTORM.md`