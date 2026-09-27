# Cross-device — one toolbox, phone and desktop

Same HTML. Android Chrome and desktop/laptop browsers share `shared/fafo-chrome.css`, `shared/fafo-chrome.js`, and `shared/fafo-pwa.js`. There is no phone-only app.

Checked **2026-09-22**: [https://treyu2023.github.io/FAFO-Power-Toolbox/](https://treyu2023.github.io/FAFO-Power-Toolbox/) returns **HTTP 404**. The repo is **public**. Enabling Pages from this agent failed with **403** (`pages=write` + `administration=write` not granted). Details and the Actions workflow are in [PHONE.md](PHONE.md). If the repo is private again, use [FORK-PAGES.md](FORK-PAGES.md) instead of the Fork button.

## Open it

| Path | URL |
|------|-----|
| Pages (after Settings → Pages → `main` / root) | https://treyu2023.github.io/FAFO-Power-Toolbox/ |
| Launcher | https://treyu2023.github.io/FAFO-Power-Toolbox/Toolbox%20Launcher.html |
| Drawing Board | https://treyu2023.github.io/FAFO-Power-Toolbox/Drawing%20Board.html |
| Typing Trainer | https://treyu2023.github.io/FAFO-Power-Toolbox/Typing%20Assistant%20Trainer.html |
| LAN | `python -m http.server 8080` from the repo root, then `http://<PC-LAN-IP>:8080/` |

`file://` is out of scope. Relative `shared/` paths need HTTP or HTTPS.

Server-backed desks still need the PC loopback server. The phone cannot open `127.0.0.87` on the PC. Launcher, Drawing Board, and Typing Trainer are the browser path.

## What the shared kit does

- **900px** — column layouts stack. Desktop fine-pointer chrome stays side by side above that.
- **640px** — tighter typewell-first spacing.
- **430px (360–430 phones)** — 44px targets on real buttons, 16px inputs (stops focus zoom), safe-area padding, no document horizontal scroll. Theme tokens (`--fafo-*`, which follow `--bg` / `--text` / `--accent`) stay in effect. This is not a dark-only skin.
- `html[data-fafo-phone="1"]` and `data-fafo-narrow` (`430` / `640` / `900`) come from `fafo-chrome.js`.
- If a page already has a viewport meta and omits `viewport-fit=cover`, the script appends it. It does not invent a viewport tag.

The on-screen typing keyboard (`.key`) is a visual guide, `aria-hidden`. Keycaps scale to the screen width. They are not 44×44 — a full row cannot be, on a 360px screen. Buttons, pills, and the Toolbox back link are.

## Add to Home screen / desktop install

`manifest.webmanifest` uses a relative `id` and `start_url` so the same file works on GitHub project Pages (`/FAFO-Power-Toolbox/`) and on a LAN server rooted at `/`.

`sw.js` precaches the **shell only** (index, 404, manifest, icons, `shared/fafo-pwa.js`). It does not call other origins and does not cache the whole toolbox. Offline navigation falls back to the cached index.

When Chrome fires `beforeinstallprompt`, `fafo-pwa.js` shows an Install / Not now bar (44px targets, safe-area, theme tokens). Menu → **Add to Home screen** / **Install app** still works if the bar was dismissed (`localStorage` key `fafo-a2hs-dismissed`). The bar hides while a typing run is active and when the app is already standalone.

HTTPS (Pages) or localhost / private LAN is required for the service worker. `file://` skips it.

## Viewport checklist

Resize the desktop window or use device mode. Confirm each row.

| Check | 390×844 | 430×932 | 1280×800 |
|-------|---------|---------|----------|
| No horizontal scroll on the page | Launcher, Drawing Board, Trainer | same | desktop chrome intact (side-by-side where the app uses it) |
| Buttons / pills / summaries ≥ 44px | yes | yes | compact buttons stay compact |
| Inputs 16px (no focus zoom) | yes | yes | unchanged |
| Panels stack | 1 column | 1 column | multi-column where the app is wide |
| Safe area | notch padding, no control under the gesture bar | same | n/a |
| Install | HTTPS: Install bar or browser menu | same | desktop install icon / bar when Chrome offers it |
| Trainer typewell | prompt readable, keyboard row fits, back link tappable | same | prompt stays the main surface |
| Drawing Board | filters stack, stepper scrolls inside itself | same | two-column idea wall |
| Launcher | installer `.bat` panel hidden, search full width | same | installer + kbd hints visible |

Pages publish steps and the private-repo fork warning live in [PHONE.md](PHONE.md) and [FORK-PAGES.md](FORK-PAGES.md).

## Headless check (2026-09-22)

Chrome headless, `python -m http.server` on localhost, cinematic intro skipped:

| Page | 390 | 430 | 1280 |
|------|-----|-----|------|
| Launcher | no page overflow, no control under 44px tall | same | compact server buttons (~31px), no overflow |
| Drawing Board | no page overflow, controls ≥ 44px | same | two-column board, layout buttons stay compact |
| Typing Trainer | no page overflow, keyboard row fits, controls ≥ 44px | same | desktop typewell + full keycaps |

`data-fafo-phone=1` at 390 and 430, absent at 1280. Service worker `sw.js` reached `activated` with scope `/` on that server. This was not a physical Android device.
