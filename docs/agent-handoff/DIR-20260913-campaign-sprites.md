# DIR: Campaign NPC + player sprites (Kenney + Imagine)

- **Status:** IN_PROGRESS  
- **Priority:** P1  
- **Owner (expert):** local Hands (assist grokbot)  
- **Executor:** grokbot / Hands  
- **Created:** 2026-09-13  
- **Goal:** Put real sprites on Keystroke Chronicles class picker, Glyph companion, map NPCs, and three bosses — sourced from Kenney CC0 packs and the owner’s Imagine library.

## Context

`TAT70_CLASSES[*].art.sprite` and T83 art slots were empty (emoji only). Packs are already downloaded and mapped:

`production/assets/typing-campaign-sprites/`  
Manifest: `assets/typing-campaign-sprites/MANIFEST.json`

Hands staged Kenney copies + two Imagine stills and began wiring faces. Grokbot finishes remaining territories, Imagine portrait option, and playtest.

## Constraints

- One file for trainer logic: `Typing Assistant Trainer.html` (plus files under `assets/typing-campaign-sprites/`)
- No CDN. Relative `assets/…` paths only
- `image-rendering: pixelated` for Kenney tiles
- Do not data-URL Imagine files over T83’s 1.5 MB cap
- Do not bump T-level unless COM names it (current stamp T83)
- Do not commit secrets; Kenney is CC0

## Tasks (ordered)

1. Confirm class picker six faces load from `players/*.png` (emoji remains fallback).
2. Glyph companion `#companionFace` uses `companion/glyph.png` after class pick.
3. Map nodes: apply `TAT_NPC_SPRITES` (or `t.sprite`) so Act I critters + three bosses show on `#territories`.
4. Optional Imagine portraits: Relay ← cyber-warrior pointer (downsample first); Glyph alt ← `imagine/glyph-cyber-squirrel.jpg`; Sovereign alt ← `imagine/sovereign-skull-axe.jpg`. Keep Kenney as default pixel set.
5. Fill leftover Act II/III nodes from `_source/tiny-dungeon` / `_source/new-platformer-pack` using the same naming (`npcs/<territoryId>.png`).
6. Smoke: open trainer from `production/`, pick each class, Attack Territory on meadow + warden. Sprites visible; no broken-image icons.
7. Result + LOG in this file / `LOG.md`.

## Acceptance checks

- [ ] Six class cards show Kenney (or Imagine) sprites
- [ ] Companion face shows Glyph sprite after pick
- [ ] Warden / Serpent / Sovereign map tiles show boss sprites
- [ ] Meadow (and any filled NPCs) show critter sprites
- [ ] Paths work when HTML is opened from `production/` (Toolbox launcher)
- [ ] MANIFEST.json matches files on disk

## Out of scope

- Full walk-cycle animation (idle/front stills are enough)
- Regenerating Imagine videos into sprite sheets
- T84 version stamp unless COM assigns it
- Rewriting campaign DAG / XP
