# Typing campaign sprites

Staged for **Typing Assistant Trainer** (Keystroke Chronicles). Grokbot / Hands can wire remaining territories from `_source/` without re-downloading.

## Layout

| Folder | Use |
|--------|-----|
| `players/` | Six class picker faces (`TAT70_CLASSES.art.sprite`) |
| `companion/` | Glyph key-spirit (`#companionFace`) |
| `bosses/` | Home-Row Warden, Syntax Serpent, Keystone Sovereign |
| `npcs/` | Act I–II map critters + Master Home Row |
| `imagine/` | Owner Imagine stills (portraits, not pixel) |
| `_source/` | Full Kenney CC0 zips + extracted packs |

## How the trainer loads them

Relative to `production/Typing Assistant Trainer.html`:

```
assets/typing-campaign-sprites/players/sprinter.png
```

CSS should use `image-rendering: pixelated` (Kenney tiles are 16–96 px). Do **not** data-URL the Imagine portraits into `localStorage` (T83 cap is 1.5 MB; cyber-warrior still is ~5.8 MB).

## Imagine pointers

Full roster: `imagine/POINTERS.json` (Goth Ninja, Rogue Wizard, Cyborg Female, Futuristic 1, Ethereal Fairy, Zeus, etc.).

Already copied (small enough for git):

- Glyph alt: `imagine/glyph-cyber-squirrel.jpg`
- Sovereign alt: `imagine/sovereign-skull-axe.jpg`
- Streaker alt: `imagine/streaker-golden-cat.png`

Enhanced `__Unknown_Characters\*_enhanced.png` files are 16–24MB — downsample before using as T83 layers.

## License

Kenney packs are **CC0**. Credit `Kenney.nl` is appreciated, not required. Imagine files stay owner-local.
