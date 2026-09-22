# Phone (Android Chrome) — FAFO Power Toolbox

Open the toolbox in the **phone browser**. No APK. No sideload of HTML from chat.

Static HTML + `shared/` assets only. Server-backed desks (Media Library, diagnostics, Verifone probes) still need the PC loopback server; the launcher and Drawing Board work as a catalog / notes UI without it. Typing Trainer is browser-local too.

Phone and desktop share one chrome kit (`shared/fafo-chrome.css` / `fafo-chrome.js`). Viewport checks for 390 / 430 / 1280 are in [CROSS-DEVICE.md](CROSS-DEVICE.md).

## GitHub Pages URL

**https://treyu2023.github.io/FAFO-Power-Toolbox/**

Checked **2026-09-22**: that URL still returns **HTTP 404**. The repo is **public** (owner `Treyu2023`, a user account, not an org). This is **not** a private-repo plan block.

An agent tried to enable Pages on this repo:

- `POST /repos/Treyu2023/FAFO-Power-Toolbox/pages` with `build_type: legacy`, `source.branch: main`, `source.path: /`
- `PUT` the same body

Both returned **403** `Resource not accessible by integration`. GitHub’s required permission header was `pages=write` and `administration=write`. The token’s repo permissions are `admin: false`. `GET .../pages` is **404** (no site configured). No public mirror repo was created: a GitHub Fork would republish Investor Portal / TaxForge history, and this token cannot create repos either.

Someone who can open **Settings → Pages** on the owner account still has to turn it on. Two equivalent choices:

1. **Deploy from a branch** — `main`, folder `/ (root)`. `index.html` and `.nojekyll` are already on `main`.
2. **GitHub Actions** — after `.github/workflows/pages.yml` is on `main`, set Source to **GitHub Actions**. That workflow uploads the repo root and does not add a second app.

If the repo is made private on a plan without private Pages, use [FORK-PAGES.md](FORK-PAGES.md) (fresh tree, not the Fork button).

After Pages is live, open this on the phone:

**https://treyu2023.github.io/FAFO-Power-Toolbox/**

That root page sends you to the launcher:

**https://treyu2023.github.io/FAFO-Power-Toolbox/Toolbox%20Launcher.html**

Drawing Board (same origin, relative `shared/`):

**https://treyu2023.github.io/FAFO-Power-Toolbox/Drawing%20Board.html**

Typing Trainer:

**https://treyu2023.github.io/FAFO-Power-Toolbox/Typing%20Assistant%20Trainer.html**

Repo: [Treyu2023/FAFO-Power-Toolbox](https://github.com/Treyu2023/FAFO-Power-Toolbox)

### Turn Pages on (one-time, repo Settings)

Pages stays off until an account with **admin** on this repo saves a source. Use **repo root**, not `/docs`.

Branch source:

1. GitHub → this repo → **Settings** → **Pages**
2. **Build and deployment** → **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/ (root)` → Save
4. Wait a minute. The site URL on that page should match the links above.

Actions source (after `.github/workflows/pages.yml` is on `main`):

1. **Source:** GitHub Actions
2. Run the “Deploy GitHub Pages” workflow, or push to `main` so it runs

If the repo is **private**, Pages needs a plan that includes private Pages. Otherwise follow [FORK-PAGES.md](FORK-PAGES.md) (fresh public tree, not a fork).

`index.html` + `.nojekyll` are the Pages entry. Jekyll stays off so filenames with spaces (`Toolbox Launcher.html`) serve as-is.

## Add to Home screen (Chrome on Android)

1. Open the Pages URL above in **Chrome** (HTTPS is required). A LAN `http://192.168.x.x:8080/` page can install only as a shortcut; the service worker registers on HTTPS, localhost, and private LAN.
2. Use the **Install** bar when it appears, or Menu (**⋮**) → **Add to Home screen** / **Install app**.
3. Confirm. The icon uses `shared/pwa/` artwork.

The web manifest (`manifest.webmanifest`, relative `id` so Pages and LAN both qualify) and shell-only service worker (`sw.js`) make that prompt available. The worker caches the home-screen shell (index, 404, icons, manifest, `shared/fafo-pwa.js`) only — it does not phone home or cache the whole toolbox. Desktop Chrome can install the same manifest.

## LAN fallback (no Pages)

From a checkout of this repo (the production HTML tree — repo root, not a nested `docs/` publish):

```bash
cd /path/to/FAFO-Power-Toolbox
python -m http.server 8080
```

On Windows PowerShell, from the toolbox folder:

```powershell
python -m http.server 8080
```

Then on the phone, same Wi-Fi:

`http://<PC-LAN-IP>:8080/`

Example: `http://192.168.1.40:8080/` → launcher.

`file://` open of HTML on the phone is out of scope. HTTP(S) keeps relative `shared/` paths working.

## Autosize (no scale slider on a phone)

The page matches the device. At **720px and under** there is no “scale everything” control. Saved UI scale on a laptop stays in preferences and comes back when the window is wide again. Ctrl+wheel does not change scale on a narrow window.

Narrow layout:

- Columns stack full width. Type uses the screen (viewport, `clamp`, fluid grids, safe-area).
- Panels, menus, and option lists grow with their content. The **page** scrolls.
- Nested max-height boxes (layout docks, companion chips, pro-bar chips, section bodies) unwrap. A collapsed accordion stays collapsed until you open it, then it grows.
- Touch targets stay at least 44px. The page does not scroll sideways.
- Desktop and laptop widths keep side-by-side panes, drag-resize, and the Look panel scale controls (UI scale, text scale, 4K TV presets).

A typing run (`body.run-active`) keeps its stage so the drill is not shoved off screen. Menus outside a run follow the page.

## What works on the phone

On phone-width (≤640px), the Launcher skips the full-screen cinematic intro and hides the PC installer (“Install FAFO Toolbox.bat”) panel. At ≤430px, shared chrome also enforces 44px controls, 16px inputs, and stacked panels. Desktop widths keep the denser layout.

| Works in the browser | Needs the PC toolbox server |
|----------------------|-----------------------------|
| Launcher catalog, search, sections | Media Library, VSR, most System Tools |
| Drawing Board (localStorage) | Verifone live probes, diagnostics HUD |
| Typing Trainer (local drills) | Anything that talks to `127.0.0.87:18765` |
| Other offline-OK HTML tools | |

Phone Chrome cannot reach `127.0.0.87` on the PC. Treat Pages as the **launcher + offline tools** path.
