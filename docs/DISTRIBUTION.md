# Distribution: GitHub vs Chrome Web Store

How this toolbox should be shared — and what **cannot** go through the Google Chrome Web Store as a full product.

## Short answer

| Package | Chrome Web Store? | GitHub? |
|---------|-------------------|---------|
| **AI HTML Toolbox** (HTML tools + optional local Python server) | **No** as one extension that replaces the desktop stack | **Yes** — preferred |
| **FAFO / local media stack** (Media Library, VSR, ffmpeg, renames, disk, diagnostics) | **No** as a pure CWS extension | **Yes** — desktop/local install |
| **Small pure-browser utilities** (converter, loan calc, image crop helper) | **Maybe** later as a thin MV3 extension | **Yes** |

**Do not** try to push the FAFO local media server + full library through the Chrome Web Store as the primary product. Ship it on **GitHub** (public or private) with clear install docs, same as this toolbox.

---

## Why the full stack is not a Chrome Web Store app

Chrome extensions (Manifest V3) are a **browser sandbox**, not a desktop media OS:

1. **No embedded Python/ffmpeg host**  
   CWS items cannot ship and run your `server/aitoolbox_server.py`, tray process, or batch launchers the way this repo does.

2. **Remotely hosted / external code rules**  
   MV3 requires executable logic to live in the extension package. A “thin UI that loads your full app from disk/network” fights store policy and review.

3. **Filesystem reality**  
   Media Library / VSR need bulk folder scan, rename, Explorer tags, pair maps, trash, etc. Extensions only get limited APIs (optional File System Access from a user gesture, not unrestricted disk like a local server).

4. **Native Messaging is not a free pass**  
   You *can* pair an extension with a separately installed **native host**, but:
   - Users must install the host **outside** the store  
   - Broad “control my whole media library / run ffmpeg” hosts are high-friction in review  
   - You still maintain two installers (extension + host) — worse UX than `START SERVER.bat` + HTML

5. **Single-purpose & permissions scrutiny**  
   A mega-extension that does diagnostics, hosts editing, malware scan, media rename, and Verifone tools will struggle on “narrow purpose” and permission justification.

There *are* CWS items that serve localhost files or talk to a local app — those are **helpers**, not a replacement for this architecture.

### What *could* be store-bound later (optional, separate product)

- Offline **Universal Converter** / calculators only  
- **Image crop** for store listing sizes (you already have a cropper oriented that way)  
- A **tiny “open toolbox protocol”** helper (low value vs desktop shortcut)

Treat those as **new small projects**, not a rebrand of FAFO media.

---

## Recommended branching / packaging

You do **not** need a hard git split on day one if secrets stay out of the repo (see `AGENTS.md` / `.gitignore`). Use **product layers**:

```
AI HTML TOOLBOX (this repo)
├── shareable on GitHub as-is (scrub secrets, device reports, DBs)
│   ├── Pure browser tools (converter, loan, games, science)
│   ├── Shared UI kit (shared/)
│   └── Optional server/ (documented local backend)
│
└── “FAFO Local Media” product story
    ├── Movie File Manager/*, VSR, pairs, batch convert
    └── server/* + START SERVER.bat + SETUP
```

### Practical options

**A. One public GitHub repo (simplest)**  
- Publish this tree with a clear README  
- Call out: “Local desktop toolbox; optional Python backend; not a Chrome Web Store extension”  
- Keep machine-local data out of git (already policy)

**B. Two repos later (if you want cleaner marketing)**  
| Repo | Contents |
|------|----------|
| `ai-html-toolbox` | Launcher, calculators, pure HTML, shared UI, docs |
| `fafo-local-media` | Media library, VSR, server, installers |

Shared code can be a submodule or copied `shared/` until you need a package registry.

**C. Git branches (light-weight)**  
- `main` — stable shareable snapshot  
- `media` / `fafo` — heavier local-media experiments  
Not required if one README + badges already separate “offline OK” vs “needs server”.

---

## What we mark in the launcher

- **Server** — full features need `127.0.0.87:18765`  
- **Offline OK** — pure browser (e.g. Universal Converter, loan calc)  
- **Local** — desktop/site-specific (e.g. Verifone site tooling); not for public store packaging

---

## Share checklist (before GitHub push)

1. Run `Scripts\Invoke-FAFOPrePushCheck.ps1`  
2. Confirm no secrets in `server/security_config.json`, `.env`, or reports  
3. No other machine’s `%LOCALAPPDATA%\FAFO\...` dumps committed  
4. README states: local-only, loopback bind, optional server  
5. Prefer MIT/your license + “use at your own risk” for system tools  

---

## Stability notes (engineering)

Cross-tool quality work lives mainly in:

- `shared/aitoolbox-api.js` — timeouts, offline errors, health  
- `shared/aitoolbox-ui.js` — global error toasts, back-link helpers, server bar  
- `Toolbox Launcher.html` — needsServer / offline badges, soft offline warn  

Deep per-tool refactors (every HTML file) stay incremental; prefer shared hardening over copy-paste IIFEs.
