# Phone (Android Chrome) — FAFO Power Toolbox

Open the toolbox in the **phone browser**. No APK. No sideload of HTML from chat.

Static HTML + `shared/` assets only. Server-backed desks (Media Library, diagnostics, Verifone probes) still need the PC loopback server; the launcher and Drawing Board work as a catalog / notes UI without it. Typing Trainer is browser-local too.

Phone and desktop share one chrome kit (`shared/fafo-chrome.css` / `fafo-chrome.js`). Viewport checks for 390 / 430 / 1280 are in [CROSS-DEVICE.md](CROSS-DEVICE.md).

## GitHub Pages URL

**https://treyu2023.github.io/FAFO-Power-Toolbox/**

Checked **2026-09-22**: that URL still returns **404**. `gh` reports this repo **public**, so the 404 is Pages left off (no source branch), not a private-repo limitation. Enabling Pages below is the path to use. If the repo is private, or a plan/policy blocks Pages here, publish a **history-free** public mirror — [FORK-PAGES.md](FORK-PAGES.md). Do not use GitHub’s Fork button; old commits still contain Investor Portal and TaxForge even though `.gitignore` keeps them out of `HEAD`.

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

Pages is **not** on until someone flips it. Use **repo root**, not `/docs` — the launcher and `shared/` live at the root.

1. GitHub → this repo → **Settings** → **Pages**
2. **Build and deployment** → **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/ (root)` → Save
4. Wait a minute. The site URL shown on that page should match the links above.
5. If the repo is **private**, Pages for private repos needs a GitHub plan that includes it. Otherwise follow [FORK-PAGES.md](FORK-PAGES.md) (fresh public tree, not a fork).

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

## What works on the phone

On phone-width (≤640px), the Launcher skips the full-screen cinematic intro and hides the PC installer (“Install FAFO Toolbox.bat”) panel. At ≤430px, shared chrome also enforces 44px controls, 16px inputs, and stacked panels. Desktop widths keep the denser layout.

| Works in the browser | Needs the PC toolbox server |
|----------------------|-----------------------------|
| Launcher catalog, search, sections | Media Library, VSR, most System Tools |
| Drawing Board (localStorage) | Verifone live probes, diagnostics HUD |
| Typing Trainer (local drills) | Anything that talks to `127.0.0.87:18765` |
| Other offline-OK HTML tools | |

Phone Chrome cannot reach `127.0.0.87` on the PC. Treat Pages as the **launcher + offline tools** path.
