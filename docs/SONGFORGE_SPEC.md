# THE — Songforge Formal Spec (LOCKED)

**Status:** LOCKED 2026-09-22 — COM LOCK on brief `8fa05a52`  
**Cite:** `Docs/SONGFORGE_BRIEF.md` sha8 `8fa05a52`  
**File:** `Songforge.html` (sandbox first; FAFO toolbox tile — COM promote)  
**Data:** `shared/songforge-presets.json` + `localStorage` `aitoolbox.songforge.v1`  
**Chrome:** `fafo-chrome` + aitoolbox where practical  
**Constraints:** CDN0. No phone-home. No Suno API. ScaleSiege HOLD. THE docs-only (no HTML).  
**Studio hook:** soft-park stretch only — non-blocking.

---

## Product MVP

One offline toolbox HTML that produces a **Suno v6 pack**:

| Field | Paste target |
|-------|----------------|
| **Title** | Suno title |
| **Lyrics** | Suno lyrics |
| **Style** | Suno style / prompt tags |

Plus: rhyme autocomplete presets, browsable **instrument + soundboard** kit for Style (and lyric notes).

---

## Stages (same HTML)

| Stage | Duty |
|-------|------|
| Ideas | Sparks, theme/POV/emotion chips; local “remix” from presets |
| Lyrics | Sectioned editor (Intro / Verse / Pre / Chorus / Bridge / Outro); rhyme autocomplete from local banks |
| Style | Style string builder: genre, mood, vocal, BPM band, production tags; insert kit tags |
| Kit | Search/filter instruments + soundboard one-liners; click → insert into Style (or Lyrics note) |
| Export | Suno Pack panel: Title / Lyrics / Style — Copy each + Copy all + download `.txt` / `.json` |

---

## Data

```json
{
  "schema": "aitoolbox.songforge.v1",
  "title": "",
  "lyrics": { "sections": [] },
  "style": "",
  "ideaTags": [],
  "kitPins": [],
  "updatedAt": null
}
```

Presets file (seed): rhyme banks, structure templates, style chips, instrument taxonomy, soundboard lines — all local.

---

## KEEP plan SF-1 → SF-4

| KEEP | Scope | BTΩ |
|------|-------|-----|
| **SF-1** | Shell + Ideas + Title field + Export stub (copy title) | `1:30` Ω30 |
| **SF-2** | Lyrics editor + section templates + rhyme autocomplete presets | `1:45` Ω45 |
| **SF-3** | Style builder + instrument/soundboard Kit browser | `1:40` Ω40 |
| **SF-4** | Pack polish (Copy all / download) + empty states + studio-hook **flag stub only** | `1:25` Ω25 |

One LIVE KEEP at a time. CRE/SIE parallel docs OK; PET sole HTML.

---

## Studio hook (stretch — soft park)

- Feature flag `studioHook: false` by default  
- If a real Grok Build export/URL scheme appears later: enable behind flag  
- **Not** in SF-1–SF-3 acceptance; SF-4 only requires the stub flag + “parked” label  

---

## Non-goals

- In-app audio generation  
- Suno/HTTP APIs  
- CDN rhyme dictionaries  
- Cloud sync / accounts  
- Blocking on Grok Build studio  

---

## Acceptance A–D (wave / per-KEEP as noted)

### A. Core pack (SF-1 + SF-4)

- [ ] A1 User can set Title and see it in Export  
- [ ] A2 Export Copy Title works offline  
- [ ] A3 Final pack exposes Title + Lyrics + Style copy actions  
- [ ] A4 Download `.txt` or `.json` pack works without network  

### B. Lyrics + rhyme (SF-2)

- [ ] B1 Sections create/edit/reorder or clear templates  
- [ ] B2 Rhyme autocomplete from **local** presets (no CDN)  
- [ ] B3 Lyrics appear in Export pack  

### C. Style + Kit (SF-3)

- [ ] C1 Style builder composes a single style string  
- [ ] C2 Kit browser lists instruments + soundboard lines; search works  
- [ ] C3 Click kit item inserts into Style (or documented pin)  
- [ ] C4 Style appears in Export pack  

### D. Pipe / safety

- [ ] D1 CDN0 — no remote fonts/scripts/analytics  
- [ ] D2 `aitoolbox.songforge.v1` persists refresh  
- [ ] D3 Studio hook parked (flag stub OK); does not block MVP  
- [ ] D4 One-file KEEP; ScaleSiege untouched; soft nits → next SF  

**PASS (MVP):** A–D green after SF-4. TST scores each KEEP against relevant subset + D always.

---

## Handoff

| Role | Action |
|------|--------|
| **THE** | SPEC LOCKED; standby SF deltas |
| **TST** | PREP / score card = this § Acceptance |
| **CRE** | Visual bank when COM asks |
| **SIE** | Copy pack when COM asks |
| **PET** | Wait COM PET-SF-1 LIVE |
| **COM** | Assign LIVE |

**Report line:** `Songforge SPEC LOCKED — Docs/SONGFORGE_SPEC.md`