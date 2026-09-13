# Typing Trainer Roadmap
Living list. One file only: Typing Assistant Trainer.html.
Pipeline: COM assigns milestone → THE specs → PET implements → TST playtests → COM KEEP + local-promote → next item.
Do not touch launcher, TaxForge Hub, icons, ScaleSiege.
Baseline: T62 KEEP3 bdee8bb (I-model, mixable FX families, tiled bg knobs, contrast floor, wheel panes).

## Already shipped (do not redo)
- Mixable FX families: ice / fire / lightning / neon / void / hotspot
- I = clamp01(B+E)*gain ; hit +0.15 / miss +0.25 / chain n*0.08 cap 0.6 ; decay 400/700/200
- Tiled bg Photoshop knobs + parallax/noise/invert/cover
- Contrast floor 4.5:1, high-contrast caret, T61 wheel panes, prefs allowlist

## Open enhancements (36)
### Config for chosen types
1. Calm / Arcade / Chaos master profiles (one click, maps onto existing family+I knobs)
2. Five named preset slots (save/load/overwrite current FX+layout)
3. Per-family enable + 0-100 + hue already exists; add per-family **shape** (orb / shard / ribbon / spark)
4. Per-family **blend mode** (add / screen / multiply / overlay)
5. Reduced-motion master (kills burst/flash, keeps color)
6. Night-shift warmth slider on the plate only

### Gameplay
7. Combo multiplier meter (visible, ramps with chain)
8. Perfect-word burst (plate-only)
9. Session-finish fireworks / confetti (off glyph layer)
10. Ghost race: replay best-WPM caret
11. Daily challenge seed (date-based passage + score)
12. Timed sprint 15/30/60 with podium
13. Boss phrase waves (long sentence bursts)
14. Weak-key drill generator from miss log
15. Error heatmap on an on-screen keyboard
16. Word-pack themes: code / oilfield / sci-fi / quotes

### Visual / juice
17. Per-key ripple on correct
18. Letter-trail glyph sparks (behind text)
19. Ambient weather layer (rain / ember / snow) behind glyphs
20. Color-grade LUTs: sunset / arctic / toxic / midnight
21. Animated frame skins: chrome / rune / circuit
22. Caret skins: beam / orb / sword / ant
23. Scanline / CRT optional overlay
24. Typewell 3D tilt (subtle, toggle)
25. Custom accent color + glow radius
26. Miss shockwave (short, off-glyph)
27. Depth blur on completed words
28. Tile library + user-image tile

### Audio / recap / a11y
29. Sound pack (click / miss / combo / win) + volumes
30. Session recap card (shareable PNG)
31. Keystroke latency sparkline
32. Font picker + size + tracking
33. Layouts: classic / cinema / cockpit
34. Dyslexia-friendly font + extra spacing
35. Color-blind palettes (protan / deutan / tritan)
36. Music-reactive visualizer (optional local audio file)

## Milestone plan
- T63: items 7+8+9 juice pack 1 (combo meter, perfect-word burst, finish fireworks). Prefs + version stamp T63. Keep I-model and wheel.
- T64: items 1+2+5 profiles/presets/reduced-motion
- Later: one or two related items per milestone. THE specs, PET one file, TST playtest, COM promote.

## Hard wave (T70–T74) — TRAINER FOUNDATION
- **T70** Character + XP foundation: prefs.v3.character { classId, xp, level, unlockSlots[] }; Sprinter|Scholar|Streaker first-run pick (Keyseeker spirits, Glyph face); XP curve round(100*N^1.35) cap L30; sprint 15/30/60 awards XP + level-up toast; playMode enum shell; stubs streakAudio/bonusLetters/extraFxFamilies. (LIVE)
- **T71** Map / boss chrome shell (CRE plate-only) — no full campaign rewrite.
- **T72** Unlock slots + class passive hooks (read XP/level; still localStorage).
- **T73** Daily / seed challenge bridge into XP (no CDN).
- **T74** Juice pack hard-wave: streakAudio + bonusLetters + extra FX families (uses T70 stubs).
