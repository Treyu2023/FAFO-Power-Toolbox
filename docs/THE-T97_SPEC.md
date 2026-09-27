# THE-T97 — Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK after T96 PASS `f2abc3c` / `7a59bd4c`  
**Scout AMEND:** sprite gaps folded §6b; prior sha8 `347f7b78`.
**Cite:** CRE portrait LOCK (starters sprinter→zen) · Scout art risks · `Docs/THE-T96_SPEC.md` `8462fb78` · HARD3 classes  
**File:** `Typing Assistant Trainer.html` only (one LIVE KEEP)  
**Art roots:** production `typing-campaign-sprites` (and/or `shared/typing-trainer/portraits/` for user adds) — **relative paths only**, no `D:\` absolute Imagine paths  
**BTΩ:** PET `1:40` → **Ω40** · CRE seal/portrait polish optional `1:25` → **Ω25**  
**Constraints:** No HTML from THE. No CDN. ScaleSiege HOLD.  
**Out of T97:** Mobile / PWA shell · full Global Bonus Shop · Scout Stardew wall

---

## T97 one-liner

**Char-select + seal wall — starters sprinter/scholar/streaker/guardian/ghost/zen from campaign sprites; grey visible locks; seal/portrait gates; MANIFEST 6≠10 fix; soft glass readAcc if cheap.**

---

## 1. Class / portrait model

HARD3 classes remain the kit. Portraits are faces.

| Slot | classId | Starter art | Start state |
|------|---------|-------------|-------------|
| 1 | `Sprinter` | production sprite | **Unlocked** |
| 2 | `Scholar` | production sprite | **Unlocked** |
| 3 | `Streaker` | production sprite | **Unlocked** |
| 4 | `Guardian` | production sprite | **Unlocked** |
| 5 | `Ghost` | production sprite | **Unlocked** |
| 6 | `Zen` | production sprite | **Unlocked** |
| 7 | `Raider` | unlock stub | **GREY locked** |
| 8 | `Oracle` | unlock stub | **GREY locked** |
| 9 | `Titan` | unlock stub | **GREY locked** |
| 10 | `Sovereign` | unlock stub | **GREY locked** |

**MANIFEST fix:** ship a Trainer-facing manifest of **10** entries (6 real src + 4 stub). Do not leave a 6-only MANIFEST that implies 10 classes without stubs. Stub = placeholder SVG/CSS medallion + grey lock (CRE), **not** broken image.

**glyph-compan pip:** optional companion pip on select card (CRE); cosmetic; no combat effect in T97.

**Imagine prestige:** parked — no absolute `D:` paths; no prestige portrait pack in T97.

---

## 2. Char-select UI

- Entry: Hub Gallery room (T92) and/or existing class picker — unify to one **Char Select** panel  
- Shows all 10; locked = **GREY visible** (Ryan rule), readable label, toast on click (SIE refuse tone OK)  
- Unlock gates (§3); selecting unlocked sets `prefs.v3.character.classId` + `portraitId`  
- User file portraits: optional “Add portrait” → store under meta `portraits` / IndexedDB; path note `shared/typing-trainer/portraits/` for packaged defaults only  
- Cold load: if classId missing, default Sprinter  

---

## 3. Seal / portrait gates

**Seals** = HARD3 permanent-ability / earn seals (already in Trainer). T97 wall:

| Gate | Unlocks |
|------|---------|
| Own seal count ≥1 OR lattice ring2 hub owned | Gallery cosmetic filter |
| Castle `gallery` tier ≥1 | User Add Portrait enabled |
| Class-specific seal or campaign beat (if hooks exist) | Raider / Oracle / Titan / Sovereign — else **Glyph cost stub**: 40/50/60/80 shards + confirmation (earn-only spend) |
| Prestige / Imagine | Parked |

Grey click without gate: refuse toast, no purchase bypass without meeting gate (same as castle GREY).

---

## 4. meta.v1 fields

```json
"portraits": {
  "activeId": "class:Sprinter",
  "custom": {},
  "unlockedClassIds": ["Sprinter","Scholar","Streaker","Guardian","Ghost","Zen"]
},
"sealsWall": {
  "seenIds": []
}
```

- Prefer binding portrait id `class:ClassId` for starters  
- **Do not mutate** `campaign.v3` except read-only seal/progress probes if needed  
- Export/Import: union `unlockedClassIds`; keep activeId if still unlocked  

---

## 5. Soft — glass readAcc (if cheap)

`charm_glass_tempo` (T96) uses accuracy at run end. Soft nit: ensure `readAcc` uses the **same** accuracy helper as HUD/grade (not a divergent counter). If already unified, note PASS. If split, one-line fix in T97.

---

## 6. Art path rules (Scout risks folded)

| Risk | Spec rule |
|------|-----------|
| MANIFEST 6 vs 10-class | Manifest length 10 with stubs |
| Unlock portraits stubby | GREY + placeholder until themed art exists |
| Imagine absolute D: paths | Forbidden — relative only |
| Sandbox missing sprites | Resolve from production copy path used by Trainer today; if sandbox lacks files, PET documents fallback placeholder + COM sync — **no broken img** |

---

## 6b. Scout re-verify (2026-09-22) — LOCK AMEND

| Finding | Spec duty |
|---------|-----------|
| MANIFEST 6 starters ≠ 10-class themes | Ship Trainer catalog/manifest **10** entries; do not pretend themes/*/players are auto-root |
| Root players missing raider/oracle/titan/sovereign (only under themes/*/players) | Char-select **must not** deep-link theme paths for v1 unlocks; use GREY CSS/SVG stubs until root copies exist |
| Rune unlock PNGs stub-sized (<250B) | Treat as **non-art**; never show as portrait (broken/blank risk) — placeholder medallion only |
| Root bg/ empty; sandbox sprites pack missing | Resolve starters from **production** typing-campaign-sprites path Trainer already loads; sandbox may placeholder; document in KEEP notes |
| Tiny bosses/sovereign + 4 npc stubs | Out of char-select scope; do not use as class portraits |
| Imagine `D:\OUTPUTS` abs paths; POINTERS gaps (Rig Hand, Syntax Serpent, Glyph spark) | **Forbidden** in Trainer URLs; no Imagine prestige pack this KEEP |
| No sha8 in MANIFEST | Optional: add `sha8` or `rev` field when rewriting manifest — nice-to-have, not PASS-blocking |

**Starters 6/6 OK** — Sprinter/Scholar/Streaker/Guardian/Ghost/Zen remain the only real portrait sources in T97.


## 7. Explicit non-goals

- Mobile / PWA / capability CSS wave  
- Full shop board  
- Stardew decoration wall  
- New lattice rings  
- Changing class combat kits (select only)  

---

## 8. Acceptance A–D

### A. Select

- [ ] A1 Six starters selectable with visible sprites (or approved placeholders)  
- [ ] A2 Four advanced classes grey visible, not hidden; click refuses without gate  
- [ ] A3 Selecting class updates character + portrait binding  

### B. Manifest / seals

- [ ] B1 Manifest/catalog exposes 10 slots (6 art + 4 stub); rune <250B PNGs not used as portraits  
- [ ] B2 Unlock path works for at least one grey class (seal **or** Glyph spend stub)  
- [ ] B3 No absolute `D:` image URLs  

### C. Soft

- [ ] C1 glass readAcc unified **OR** waived with note  
- [ ] C2 `campaign.v3` not written for portrait bag  

### D. Pipe

- [ ] D1 No mobile PWA / full shop creep  
- [ ] D2 One-file KEEP; ScaleSiege HOLD; soft→T98  

**PASS:** A–D green.

---

## 9. Handoff

| Role | Action |
|------|--------|
| **THE** | T97 LOCKED; standby T98 (keystones/mutex/respec UI) or mobile if COM remaps |
| **CRE** | Seal wall + stub medallions |
| **Scout** | Confirm sprite copy into sandbox if missing |
| **PET** | On COM PET-T97 LIVE |
| **TST** | Score §8 |
| **COM** | Assign LIVE |

**Report line:** `THE-T97 LOCKED — Docs/THE-T97_SPEC.md`