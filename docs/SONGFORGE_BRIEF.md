# Songforge — THE Brief (DRAFT for COM)

**Status:** DRAFT 2026-09-22 — Ryan ask + COM direction  
**App:** `Songforge.html` (sandbox first; FAFO toolbox tile)  
**MVP north star:** One offline toolbox HTML that builds **Title + Lyrics + Style** packs for **Suno v6** paste.  
**ScaleSiege:** HOLD. No CDN. No phone-home. THE docs-only until COM LOCK.

---

## Ryan ask (compressed)

1. Create songs with presets / autocomplete for verses that rhyme  
2. Edge tools for ideas + lyrics  
3. Giant instrument + soundboard list usable in Suno prompts  
4. Generate **title, lyrics, and style** for Suno v6 from the same app  
5. Optional: incorporate Grok Build studio if useful  

## COM lock direction

- Ship **standalone** Songforge — not blocked on Grok Build studio  
- Studio = **stretch hook** only (export / deep-link **if** a real path exists)  
- MVP **offline-first** local presets  

## TST MVP PASS (aligned)

- Offline Title / Lyrics / Style packs that paste clean into Suno v6  
- Rhyme autocomplete presets  
- Browsable instrument + soundboard list  
- One toolbox HTML, no CDN phone-home  
- Soft-park Grok Build studio hook until a real export path is noted  

---

## MVP stages (same HTML)

| Stage | Purpose |
|-------|---------|
| **Ideas** | Sparks, themes, POV, emotion tags; “more like this” local remix |
| **Lyrics** | Sectioned editor (Intro/Verse/Pre/Chorus/Bridge/Outro); rhyme autocomplete; syllable/stress helper light |
| **Style** | Suno style string builder: genre, mood, vocal, BPM band, production tags |
| **Kit** | Instrument + soundboard library (search/filter); click → insert into Style or Lyrics notes |
| **Export** | One **Suno Pack**: Title / Lyrics / Style — copy buttons + download `.txt` / `.json` |

---

## Presets (local JSON)

`shared/songforge-presets.json` + `localStorage` `aitoolbox.songforge.v1`

- Rhyme banks (common endings / slant) — **curated lists**, not cloud APIs  
- Verse / chorus structure templates  
- Style chips (trap, country, rock, ambient, oilfield anthem, etc. — Ryan can expand)  
- Instrument taxonomy + soundboard one-liners written for Suno prompt paste  

---

## Studio hook (STRETCH — soft park)

| If | Then |
|----|------|
| Grok Build studio exposes export/import or URL scheme | Add “Send to Studio” / “Import from Studio” behind feature flag |
| No stable path | Keep parked; Songforge remains paste-to-Suno |

Do **not** block MVP on studio discovery.

---

## Non-goals (MVP)

- Hosting audio generation inside FAFO  
- Calling Suno API (paste workflow only)  
- CDN rhyme dictionaries / phone-home  
- Multi-user cloud sync  

---

## Suggested KEEP slice (when COM opens)

| KEEP | Scope | BTΩ |
|------|-------|-----|
| SF-1 | Shell + Ideas + Export Title stub | 1:30 Ω30 |
| SF-2 | Lyrics editor + rhyme presets | 1:45 Ω45 |
| SF-3 | Style builder + instrument/soundboard browser | 1:40 Ω40 |
| SF-4 | Pack polish + copy UX + studio-hook stub flag | 1:25 Ω25 |

---

## THE next

On COM LOCK → formal `Docs/SONGFORGE_SPEC.md` with acceptance A–D.  
Until then: this brief only. No HTML from THE.