# FAFO Power Toolbox 3.0 — production pass

Frozen **2.0** (git-disconnected archive of `1.16.51`) first. Live tree is **3.0.6**.

## Media desks (3.0.6) — PID auto-link in matching

- `pair_id_from_name` lives in `media_ops` (`_PID_xxxxxxxx`, legacy `GT-` folder, `PID-xxxxxxxx`)
- Suggest / two-dir / guided candidates score PID as 0.99–1.0 and skip the “after must be larger” gate
- `GET /api/pairs/pid-matches` groups unpaired files; unique = exactly two files share the id
- `POST /api/pairs/trust-pids` locks unique groups (`source=pid-trust`). Pass `pids` to approve one; `include_ambiguous` stays off unless asked
- Guided Match: PID strip with Approve / Skip / Trust all unique. Keys **P** and **T**
- Pair Review: PID queue source + Trust all unique PIDs. **P** accepts the current PID item; **T** trusts unique
- Library Pairs menu: Trust all unique PIDs

## Media desks (3.0.5) — workspace tabs, durable scans, highlight-to-match

- Command-center media strip: Library / Duplicates / Organizer / Match / Review / Video / Image / Name match. Keys 1-8. Same-hub tab changes set hash instead of remounting the iframe.
- Media Hub + Compare Hub both mount `AIToolboxHub.mediaWorkspaceTabs()` (eight tabs). `hub-embedded` hides hub tabs when the command-center strip is showing.
- `aitoolbox-scan-cache.js` IndexedDB. Duplicate Manager persists full groups (no 1.5MB localStorage drop). Restore on load + pagehide save.
- Library `scanDir` skips folders with `last_scanned > 0`. Rescan is explicit (force). Age chip next to Rescan.
- `aitoolbox-catalog-pick.js` on Video + Image comparators: catalog search per slot, both filenames visible, highlight-on-before live-refines after search, restore last pair.
- `escapeHtml` in dom/hub actually escapes (amp/lt/gt/quot) — was identity-replaced.

## Media desks (3.0.4) — combine + remaining P0/P1

- Shared `aitoolbox-dom.js` (el / bind / withBusy / escapeHtml / recent folders) and `aitoolbox-hub.js` (one iframe controller)
- Media Hub + Compare Hub are thin configs over `AIToolboxHub.mount` — tab switch aborts the previous iframe
- Library catalog scan is a job (`POST /scan/{id}/start` + stream `?job_id=`). Cancel skips missing-file prune. SSE disconnect cancels the walk
- Library scan pill has Cancel. `queryMedia` cap 2000 (was a silent 200)
- `list_pairs` batch-enriches (no 2N `get_media`). Pair health reports occupancy overlap and self-pairs
- `delete_pair` strips UP-#### / role tags so Relink cannot resurrect. Unmarked names no longer default to “before”
- Video + Image comparators save by path first (`AIToolboxHub.saveComparatorPair`), then name+size
- Library: j/k selection, `/` focuses search, recent folders, XSS on `data-del`
- Dead inline Library dup scanner removed (deep-link only)

## Media desks (3.0.3)

- Library Find Dup and Companion Scan Duplicates open Media Hub → Duplicates
- `/api/vsr/apply-selected` wired
- Rename keeps rank/category/status/playlists. Scan prune cleans pairs + playlists
- `save_pair` refuses self-pairs and reuses an existing before/after row

## Media desks (3.0.2) — each app

- Duplicate File Manager: TDZ `const el = el(...)` in Start Server and ops tally (Start Server was a no-op crash)
- Pair Review Queue: `onOnline` autoload runs once, not on every health poll
- Guided Pair Match: candidate-load generation counter; reject/skip go through `withBusy`
- Library: remaining filename/tag XSS escaped; `toggleSelect` updates in place (no thumb rebuild)
- File Organizer: row `data-id` + in-place checkbox toggle
- Companion: probe-less `isOnline(false)`; preview surfaces `data.error`; apply-stage try/catch
- Media Hub + Compare Hub: cross-origin iframe timeout is a fail, not a fake load
- Batch convert: auto-queues remaining files when EventSource GET URL would exceed ~1800 chars
- VID TRIM: abortable browser encode (Pause / pagehide); browser path max-side clamped to 1920

## Media desks (3.0.1)

- New `shared/aitoolbox-media.js` on all media/AV HTML desks
- `watchServer` — pause health polls when the tab is hidden; 30s inside a hub iframe; ~12s on a visible top window (was 5s on Library / Organizer / Duplicates / Companion)
- Auto-pause `<video>`/`<audio>` when hidden; IntersectionObserver pauses off-screen clips (video wall)
- Library + Organizer: search debounce + generation counters so stale queries cannot paint
- Library verify-tags list HTML-escapes filenames
- Video comparator: reverse-play and timeline use rAF; fallback pill uses `isOnline(false)` (no heal storm)
- Image comparator: filter sliders rAF-batched; same probe-less pill
- Video wall: folder walk capped at 1,500 files / depth 12
- Guided Pair Match previews `preload=metadata`
- Duplicate auto-scan wait + batch convert EventSource close on `pagehide`
- Imagine Vault poll 20s via watchServer (was 12s always-on)

## P0 (3.0.0)

- Single version source `3.0.0` (`VERSION`, `aitoolbox-version.js`, HTML `?v=`, README)
- Debug `console.error` no longer recurses (`?debug=1` is usable again)
- Layout capture divides by UI scale so Look → 4K/125% no longer snowballs panel sizes
- `rebindAll()` no longer resets `_fafoBound` (listener multiplication)
- Layout `destroy()` removes resize/pagehide listeners
- Keep-alive skipped in iframes and when `aitoolbox.keepalive=off` (Stop no longer fights open tabs)
- GET coalescing + JSON Content-Type only when a body is present
- Scan EventSource JSON.parse is guarded; first SSE errors are not fatal
- Confirm-rename HTML is escaped (filename XSS)
- `postMessage` targets `location.origin`
- CORS allowlist (loopback + `null`) instead of `*`
- Re-adding a watch folder no longer CASCADE-wipes the catalog
- Unhandled 500s no longer leak exception strings
- `/toolbox` refuses `.py` / `.db` / `.env`
- Bind fallback to `127.0.0.1` if `127.0.0.87` is missing (Linux/VMs)
- Health `?probe=1` skips demand so the watchdog does not keep S1 “in use” forever
- Progress Map + Tech Quest un-hidden (`residualMissing` was a lie — files exist)
- Launcher search includes `path` (amortization / comparitor now match)

## P1

- `aitoolbox-runtime.js` — debounce/throttle/coalesce/timer registry/quota storage
- Config+version+runtime injected on hubs that skipped them
- Classic standalone cards restored (Library, Duplicates, Organizer, comparators)
- `apiFetch` times out at 30s
- Health includes `db_ok`

## What 3.0 does not rewrite

Typing Trainer and Commander Site Console are still large inline apps. Three.js for Empire/Solar still comes from jsDelivr unless you vendor it locally. System Health Dashboard / Desk / HUD remain three surfaces — Dashboard is the front door; Desk is ops KPIs; HUD is the interactive scan.
