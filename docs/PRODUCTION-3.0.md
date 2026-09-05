# FAFO Power Toolbox 3.0.0 — production pass

Live tree version is **3.0.0**. Frozen milestone 2.0 remains a git-disconnected archive of 1.16.51 (`9f90266932d68dbe00976955515734d6ef55b419`) and must not be edited.

What this pass actually changed:

## Version single source
- `/VERSION` and `shared/aitoolbox-version.js` are `3.0.0`.
- UI cache-bust fallback is `global.AITOOLBOX_VERSION || '3.0.0'` (was hardcoded `1.16.47`).
- Live HTML `?v=` stamps moved off 1.16.xx.

## P0 — debug infinite recursion
- `shared/aitoolbox-debug.js`: `console.error` wrapper has `_inConsole` re-entry guard.
- `log()` at error level writes through saved `origError`, not the wrapped `console.error`.

## API / keepalive
- Keep-alive skipped in iframes (`window.self !== window.top`) and when `localStorage['aitoolbox.keepalive']` or `aitoolbox_keepalive` is `'off'`.
- Stop companions writes `aitoolbox.keepalive=off`; start/success removes it so keep-alive resumes.
- GET coalescing via in-flight Map keyed by method+path+body.
- `Content-Type: application/json` only when a body is present.
- Directory scan EventSource: `JSON.parse` in try/catch; ignore two stream errors then reject; close on `pagehide`.
- `queryMedia` clamps `limit` to 1–200 (default 80).

## Layout
- `captureState` divides persisted width/height by `readUiScale()` so zoom does not snowball.
- `rebindAll()` no longer clears `_fafoBound` / `_fafoDrag` (duplicate listeners).
- `destroy()` removes `resize` / `pagehide` / `beforeunload` / `visibilitychange` listeners via named refs.

## UI
- `confirmAction` and tutorial steps HTML-escape title/body/from/to (and step title/body).
- `apiFetch` uses `AbortSignal.timeout(30000)` or `AIToolboxAPI.api` when present.
- `postMessage` target is `location.origin`; hub receivers drop foreign origins.

## Runtime
- New `shared/aitoolbox-runtime.js` (`window.AIToolboxRuntime`): debounce, throttle, rAF batch, pagehide-cleared timers, storage try/catch + quota fallback, `prefersReducedMotion`, `whenHidden`, in-flight `coalesce`.
- Load order: after config+version, before api.

## Server
- CORS origins only `http://127.0.0.87:18765`, `http://127.0.0.1:18765`, `null`. Credentials still false.
- Private-Network-Access header only echoed for those origins or a missing origin (file://).
- Unhandled exceptions return `{"detail":"Internal error","id":"..."}` (full traceback still logged).
- `/api/health?probe=1` skips `note_demand`; response always includes `db_ok`.
- Media query `limit` max 200.
- `GET /api/files/*` must resolve under toolbox `ROOT` or a registered media directory; `..`, `.db`, `.env` rejected.
- `GET /api/verifone/fleet-tech-defaults` `include_password` default **False**.
- Bind fallback: if `127.0.0.87` fails, retry `127.0.0.1` same port and print the actual bind.
- `/toolbox` static refuses `*.py`, `*.db`, `.env`, `*.ps1` (and existing secret/db suffixes).
- `media_ops.add_directory` uses `ON CONFLICT(path) DO UPDATE` (no `INSERT OR REPLACE` CASCADE wipe); old SQLite falls back to SELECT-by-path.

## Launcher / HTML
- Progress Map and Tech Quest no longer flagged `residualMissing` (those HTML files exist).
- Standalone originals added as nested-under-hub tiles (`*-classic`, VSR Pipeline Manager) while hub deep-links stay.
- Stamp script injects `aitoolbox-runtime.js` (and config/version on hubs that lacked them) before `aitoolbox-api.js`.

## Tool-specific
- Media Library search input debounced 280ms (`AIToolboxRuntime.debounce` when present).
- Duplicate File Manager: `renderGroups` throttled to 250ms during live scan; localStorage scan payload larger than 1.5MB stores a summary only (no full `JSON.stringify` of `scanResult`).
