# Phone (Android Chrome) — FAFO Power Toolbox

Open the toolbox in the **phone browser**. No APK. No sideload of HTML from chat.

Static HTML + `shared/` assets only. Server-backed desks (Media Library, diagnostics, Verifone probes) still need the PC loopback server; the launcher and Drawing Board work as a catalog / notes UI without it.

## GitHub Pages URL

After Pages is live, open this on the phone:

**https://treyu2023.github.io/FAFO-Power-Toolbox/**

That root page sends you to the launcher:

**https://treyu2023.github.io/FAFO-Power-Toolbox/Toolbox%20Launcher.html**

Drawing Board (same origin, relative `shared/`):

**https://treyu2023.github.io/FAFO-Power-Toolbox/Drawing%20Board.html**

Repo: [Treyu2023/FAFO-Power-Toolbox](https://github.com/Treyu2023/FAFO-Power-Toolbox)

### Turn Pages on (one-time, repo Settings)

Pages is **not** on until someone flips it. Use **repo root**, not `/docs` — the launcher and `shared/` live at the root.

1. GitHub → this repo → **Settings** → **Pages**
2. **Build and deployment** → **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/ (root)` → Save
4. Wait a minute. The site URL shown on that page should match the links above.
5. If the repo is **private**, Pages for private repos needs a GitHub plan that includes it (or make this repo public).

`index.html` + `.nojekyll` are the Pages entry. Jekyll stays off so filenames with spaces (`Toolbox Launcher.html`) serve as-is.

## Add to Home screen (Chrome on Android)

1. Open the Pages URL above in **Chrome** (HTTPS is required).
2. Menu (**⋮**) → **Add to Home screen** / **Install app**.
3. Confirm. The icon uses `shared/pwa/` artwork.

The web manifest (`manifest.webmanifest`) and an optional shell-only service worker (`sw.js`) make that prompt available. The worker caches the home-screen shell (index, icons, manifest) only — it does not phone home or cache the whole toolbox.

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

| Works in the browser | Needs the PC toolbox server |
|----------------------|-----------------------------|
On phone-width, the Launcher skips the full-screen cinematic intro and hides the PC installer (“Install FAFO Toolbox.bat”) panel.

| Launcher catalog, search, sections | Media Library, VSR, most System Tools |
| Drawing Board (localStorage) | Verifone live probes, diagnostics HUD |
| Other offline-OK HTML tools | Anything that talks to `127.0.0.87:18765` |

Phone Chrome cannot reach `127.0.0.87` on the PC. Treat Pages as the **launcher + offline tools** path.
