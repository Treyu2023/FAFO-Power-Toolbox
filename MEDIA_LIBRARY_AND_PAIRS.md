# Media Library, Tags, Pairs & Long-Term Storage

Guide for **AI HTML Toolbox** users (not the FAFO Chrome extension).  
Covers cataloging, Explorer-visible metadata, before/after pairing, moving files, and realistic storage options.

**Requires:** Toolbox server running on **`127.0.0.87:18765`** (green pill). FAFO’s optional companion still uses `127.0.0.1:8765` — they no longer share a port.  
**Start it in-app:** **▶ Start Server** on **Media Library**, **Mismatched Source Companion**, **File Organizer**, or **Launcher** — or click the offline pill. No need to hunt for a `.bat` first.

---

## Quick map

| Goal | Where |
|------|--------|
| Browse / search / preview | **Media Library Manager** |
| Rank ★, category, status, bulk table | **File Organizer** |
| Side-by-side before/after | Pair → **Video / Image Comparator** |
| Match scrambled upscale names | **Mismatched Source Companion** (not FlashVSR) |
| Start Python backend | Any of the above → **▶ Start Server** |

---

## Starting the server (in-app)

| Place | Control |
|-------|---------|
| **Media Library** | **▶ Start Server** button; click red pill; offline banner (Start / Open Folder / Setup Once / Console) |
| **Mismatched Source Companion** | **▶ Start Server**; click orange offline pill |
| **File Organizer** | **▶ Start Server**; click offline pill |
| **Launcher** | Banner **▶ Start Server**, Console, Open Folder, Setup Once |

Flow: click Start → app tries `aitoolbox://start` (after one-time setup) and `launch_server.hta` → waits up to ~90s → pill turns **green**.

**If Start fails (browser blocked the launch):**

1. **🖥 Console** or **📂 Open Folder** → double-click **`START SERVER.bat`**
2. Run **`SETUP (run once).bat`** once (registers protocol + desktop shortcut), then try **▶ Start Server** again
3. Advanced menu: `server\start_server.bat`

Hover the server pill and Start button in each tool for the same tips.

---

## Tags, ratings & Windows Explorer

When the server is on and **Write tags into file metadata** is enabled (default **ON**):

| UI field | Written to file (when possible) | Explorer |
|----------|----------------------------------|----------|
| Tags | `System.Keywords` (+ MP4 embedded extras) | **Tags** column / `tag:word` search |
| Rank ★1–5 | `System.Rating` | **Rating** stars |

**Formats:** MP4 / M4V / MOV and many images work best. MKV/WebM are weaker in Explorer — use **`.fafo.json` sidecars** + **Verify Tags**.

**Rescan** imports tags/rating *from* files into the catalog when the catalog entry was empty.

### Shared tags on pairs

- Creating a pair stamps **role tags** on each side and a shared code **`UP-####`**:
  - Before: `source`, `before`, `original-video` (or image)
  - After: `upscaled`, `after`, `vsr`, `upscaled-video` (or image)
  - Both: `UP-0042` (example)
- **Project tags** (`client-x`, `project-alpha`, …) can apply to **both** files:
  - Checkbox: *Also apply shared tags to paired file*
  - Button: **Push tags → pair partner**
  - Batch tags: *Also tag pair partners*
- Role tags are **not** copied across (so the original is never marked `upscaled`).

---

## Before / after pairs

### Create pairs

1. Select **exactly 2** files (first = Before / source, second = After / upscaled) → **Pair Selected**  
2. Or **Suggest Pairs** (name similarity)  
3. Or **Auto-Link Upscale Pairs** (filename markers like `_upscaled`, `_vsr`, …)

Each locked pair gets a permanent **`UP-####`** code, written into **both files’ tags** (on disk when server is green).

**Thumbnails:** paired items show green/red borders; **★** rank and **T#n** tag counts appear on library thumbs when available.

### Moving files to different folders

Catalog IDs are path-based (`folder::relative/path`). Moving a file **changes** its catalog ID, so a pair that only remembered old IDs would look broken.

**Durable link = tags on the files** (`UP-####` + role tags) and optional **Pair Map** JSON export.

After you move files (still under watched folders):

1. **Rescan** (automatic relink runs after each scan), **or**  
2. Click **🔗 Relink Pairs from Tags**

Use **🩺 Pair Health** to see complete / partial / broken pairs and orphans.

### Simple layout (recommended)

```text
D:\Media\Sources\     ← originals / before
D:\Media\Upscaled\    ← VSR / after
```

Pairs still work if you later nest project subfolders; relink uses tags, not folder names.

---

## Short Q&A

### How do I start the server?

**In the app:** open Media Library / VSR / File Organizer / Launcher → **▶ Start Server** (or click the offline pill). Wait for green. If the browser blocks it, use **Open Folder → START SERVER.bat** or run **SETUP (run once).bat** once.

### Do I need the server?

**For full features, yes.** Rename on disk, Explorer tag writes, pair relink, thumbnails, playlists, smart lists, and large libraries need the green server pill. Offline mode only browses cached catalog data.

### Are tags only in the toolbox?

**No** (when write-to-file is on). Tags/ratings go into the real files so Explorer and other apps can see them. The catalog is a fast index on top. Weak formats get **`.fafo.json`** sidecars next to the file.

### If I pair two files and move them apart, is the pair gone?

**The UI link can break until rescan/relink.** The pair is **not** gone if both files still have the same `UP-####` tag. Rescan or **Relink Pairs from Tags**. Export a **Pair Map** for extra safety.

### Can I put everything in one big folder?

**Yes.** One watched folder (with subfolders) is fine. Two roots (source vs upscaled) is optional organization, not a requirement.

### Can I ZIP my library and still play in the toolbox / FAFO?

**Not practically.** Zip/7z/RAR are archives, not video containers. Players need seekable streams; you’d decompress first (slow, needs free space). See **Long-term storage** below.

### Should I use NTFS “compress this folder”?

**Almost never for video.** MP4/MKV are already compressed; disk compression rarely saves space and can hurt performance.

### USB for cold storage?

**Yes — good idea.** Keep hot working set on the internal drive; archive finished projects with **📦 Archive Pair to Folder…** or copy to USB/external. Re-add the USB path as a watched folder when you plug it in, then rescan/relink.

### What’s the difference vs FAFO?

| | **Toolbox Media Library** | **FAFO Ultimate Tab** |
|--|---------------------------|------------------------|
| Role | Organize, pair, rename, bulk tag | New-tab player + on-play rate/tag |
| Explorer write | Built-in server @ `127.0.0.87:18765` | Optional FAFO companion @ `127.0.0.1:8765` |
| Pairs / comparator | Yes | No |

Run the **toolbox** on `127.0.0.87:18765` and (optionally) FAFO companion on `127.0.0.1:8765` — both can run at once now.

---

## Long-term storage & “compression” (realistic)

### What works while still playing in the library / players

| Approach | Saves space? | Play in toolbox / FAFO / Explorer? | Notes |
|----------|--------------|--------------------------------------|--------|
| **Re-encode** to H.265/HEVC or AV1 in **MP4/MKV** | Often **yes** (big) | **Yes** | Best “compress but still play” path. Re-tag after encode if tags stripped. |
| Lower resolution / bitrate masters | Yes | Yes | Keep one “hero” quality; archive rest colder |
| Leave as efficient MP4 already | Maybe little | Yes | Many AI exports are already compact |
| **ZIP / RAR whole libraries** | Yes on disk count | **No** (not without extract) | Archive-only, not for day-to-day playback |
| Store on **USB / external** | Frees internal SSD | Yes when plugged in + watched | Best simple cold storage |
| Cloud (Drive, etc.) | Offloads PC | Depends on local sync | Not required by toolbox |

### Feasible strategy (recommended)

1. **Working set** — current projects on internal disk, two folders or one tree, pairs + tags.  
2. **Archive set** — finished work: optional re-encode to HEVC/AV1 *or* **Archive Pair** / copy to USB.  
3. When you need them again — plug USB / restore folder → **Add Folder** / Rescan → **Relink Pairs from Tags**.  
4. Do **not** depend on zip-inside-player for random access.

### If you re-encode

- Prefer **stream copy** only when changing containers without re-encoding.  
- After a full re-encode, **re-apply pair tags** (open pair → push tags, or re-pair) so `UP-####` stays on disk.  
- Verify with **✔ Verify Tags** if needed.

---

## Hover help in the app

| Surface | What you get |
|---------|----------------|
| **Toolbar / pills** | Almost every control has a **hover tooltip** (`data-tip`) |
| **🎓 Get Started** | Interactive tour (Launcher, Media Library, VSR) |
| **❓ Q&A** | In-app FAQ (same answers as above, condensed), including how to start the server |
| **Offline banner** (Media Library) | Start Server + Open Folder + Setup Once while red |

---

## Library extras (v1.05+)

| Feature | Where |
|---------|--------|
| **▶ Start Server** | Toolbar / offline pill / banner (v1.05.01) |
| **Pair Health** | Toolbar 🩺 — complete / partial / broken / orphans |
| **Verify Tags** | Catalog vs disk + sidecars; rewrite option |
| **Pair Map** | Export/import JSON of all UP-#### pairs |
| **Archive Pair** | Paired file detail → `dest/UP-####/before|after` + manifest |
| **Smart searches** | Chips under search bar; Build… / save current filter |
| **Playlists** | Sidebar — create, load, copy paths, export |
| **Sidecars** | `.fafo.json` next to MKV/weak types |
| **Thumb badges** | Pair green/red borders, ★ rank, T#n tag count |
| **Dedup** | Flags likely before/after twins (not true duplicates) |

## Changelog (library / pairs / metadata)

### `1.05.01` — In-app server launch + docs/tooltips

- Start server from Media Library, VSR, File Organizer, Launcher  
- Offline banner + shared API launch helpers  
- Guides, FAQ, and hover tips updated  

### `1.05.00` — Health, smart searches, sidecars, archive, pair map

### `1.04.00` — Explorer write, dual-tag, relink, Q&A

### `1.03.00` — File Organizer, rank, combined folders  
### `1.02.00` — Grid/playlists/copy paths  
### Earlier — pairs, VSR, launcher, server

---

*Keep this file next to the toolbox root for users and for yourself when documenting the product.*
