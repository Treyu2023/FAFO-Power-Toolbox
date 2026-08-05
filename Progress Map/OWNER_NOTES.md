# Progress Map & Mythos — owner notes

## Open
Toolbox → **Progress Map & Mythos** · `Progress Map/Progress Map.html`

---

## Adventure unlock (not a padlock)

Paths **rotate by calendar day** (`dayIndex % 3`). Progress soft-resets each new day (vault stays).

### Shared steps (all paths)
1. **Dashboard lodge** — the **◈ mark**
   - **Click** → rotate **90°**
   - **Double-click** → moves to next of **3 places**
2. When mark is in the **correct place + rotation for today**, open **History**
3. **Bookshelf appears** (was not there before)
4. **Tilt the candle** on the mantle (Dashboard candle still works; shelf story is History)
5. Click the **green book** → **Garden** unlocks
6. In **Garden**, click the **tree trunk / heartwood** → if path extras OK, **Chamber** unlocks

### Daily path requirements

| Day path | Rune position | Rune rotation | Extra before tree yields |
|----------|---------------|---------------|---------------------------|
| **Lodge** (0) | pos **2** (near mantle right) | **180°** (upside-down — gold border) | none |
| **Cartographer** (1) | pos **0** (top-right) | **90°** | Map pins mode **cyan** (click pins on Coverage Map) |
| **Architect** (2) | pos **1** (mid-left) | **270°** | Skyline **landmark** (click towers) |

Candle must be **tilted** and green book opened on all paths.

Change logic in `mythos-engine.js` → `PATHS` array.

### Which path is today?
Chamber gate soft-hints the path **name**. Or console:
```js
FAFOMythos.activePath()
FAFOMythos.getAdventure()
```

---

## Audio (original, quiet)
`mythos-audio.js` — soft Web Audio cues (not Nintendo/Zelda IP).

- One-shots: rune / candle / book / garden / tree / wrong / chamber sting / dragon
- **Ambient** auto-starts after first click and **builds with path progress** (`pathProgressHint` steps) toward unlock; peak sparkle near complete; settles after chamber sting
- Master volume ~0.12; ambient bus stays quieter still
- Console: `FAFOMythosAudio.setVolume(0.08)`, `.setEnabled(false)`, `.getIntensity()`

**Prefer adventure comedy + louder game audio in TECH QUEST** (`../Tech Quest/Tech Quest.html`) so Progress Map pages stay professional.

---

## TECH QUEST (mini-game)
Standalone Shining Force-style TBS for field techs — **Warhammer of MASTER RESET**, Quick E Manager, Methen Kraken, Trixie, Gilbest, Veryfony.

- Launcher → Games → **TECH QUEST**
- **Hidden Treasure Room** is on the game title menu (open *before* deploy)
- Completing the finale sets `fafo.techquest.champion`

---

## Dragon
Click sleeping neon dragon → **5 minute ban**, garden path soft-reset, smoke on entrance.

---

## Vault
Local only: `fafo.mythos.vault`  
- Site logins · Verifone backdoor sheet · scraped passwords · PuTTY scroll  
- Export to encrypted USB · **never git commit**

### Sticky scan
`OneDrive\WORK\00_Field_Manuals_and_Notes\01_Sticky_Notes_Export\ALL_STICKY_NOTES.txt`

---

## Demo data
Map / skyline / rings / garden use `demoSites()` until real sites + Xero exist.
