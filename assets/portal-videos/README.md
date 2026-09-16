# FAFO Portal Pack

Launch videos and themes for **Holo-Portal** in the AI HTML Toolbox launcher.

## Priority (highest first)

1. **User video** — right-click a tool → *Set launch video* (stored in this browser’s IndexedDB)
2. **Per-tool file** — `assets/portal-videos/{toolId}.webm` (or `.mp4` / `.gif`)
3. **Pack theme** — from `pack.json` (`tools[id].theme` or category map)
4. **Theme file** — `assets/portal-videos/themes/{theme}.webm`
5. **Procedural synth** — if no file exists, the launcher generates a short themed loop and caches it

## Layout

```
portal-videos/
  pack.json              ← themes, category map, per-tool overrides
  README.md
  themes/
    default.webm         ← optional real clips (you add these)
    verifone.webm
    media.webm
    system.webm
    tax.webm
    files.webm
    utils.webm
  commander-site-console.webm   ← optional per-tool clips
  transfer-monitor.mp4
```

## Adding real videos

1. Keep clips **1–4 seconds**, ~720p or smaller, preferably **muted WebM**.
2. Name by **tool id** (see `Toolbox Launcher.html` → `id: '...'`) or drop under `themes/`.
3. Update `pack.json` if you add themes or tool→theme mappings.
4. Hard-refresh the launcher. User overrides still win until cleared.

## Settings

**🌀 Portal** in the launcher:

- Enable/disable portal, pack videos, mute, intensity
- Toggle **each effect** with descriptions
- Min/max random effects per launch
- Manage custom videos + regenerate synth pack cache
