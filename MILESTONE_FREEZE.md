# Milestone freeze pointer

**Last freeze date:** 2026-07-10  
**Frozen archive version:** `1.04.00`  
**Live working tree (edit this):** currently **`1.06.00`** and beyond — do **not** treat this freeze as the live feature set.

## Snapshot location (read-only archive)

```
C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\
  AI_HTML_TOOLBOX_MILESTONE_v1.04.00_2026-07-10_2015\
  FAFO_Ultimate_Tab_MILESTONE_v5.2.1_2026-07-10_2015\
  MILESTONE_README_v1.04.00_2026-07-10_2015.md
```

## Live working trees (edit these)

| Project | Path |
|---------|------|
| Toolbox | `C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX\` |
| FAFO | `C:\Users\rkey2\FAFO_Ultimate_Tab\` |

## What was frozen (v1.04.00 archive only)

- Explorer Tags + Rating write (pywin32)
- Pair dual-tag + `UP-####` on disk
- Relink pairs after folder moves
- Media Library Q&A + tooltips
- Docs: `MEDIA_LIBRARY_AND_PAIRS.md`
- FAFO on-play tags + `explorer-meta` companion

## Shipped on live tree since freeze (do not re-implement from scratch)

| Version | Highlights |
|---------|------------|
| **1.05.00** | Pair Health, Verify Tags, Pair Map, Archive Pair, smart searches, `.fafo.json` sidecars |
| **1.05.01** | **▶ Start Server** in-app (Media Library / VSR / File Organizer / Launcher), offline banner, shared `AIToolboxAPI.startServer()` |
| **1.06.00** | Unique bind **`127.0.0.87:18765`**, tool parity (system tools + Git + Start Server), no FAFO port clash |

See **`README.md`** and **`MEDIA_LIBRARY_AND_PAIRS.md`** for the current user-facing guides and tooltips.

## Restore

See `MILESTONE_README_*.md` in **AI LOCAL Proj Bin**.  
Copy snapshot over live only if the live tree is broken and you accept losing post-freeze edits (including 1.05.x).
