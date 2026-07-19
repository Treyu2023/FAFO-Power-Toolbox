# Shared tool icons

Icons in this folder are **defaults for every user** of the toolbox.

| File | Role |
|------|------|
| `manifest.json` / `manifest.js` | Maps tool ids → filename (`app` = main Desktop shortcut) |
| `icon-sources.json` | Your library roots, aliases, and **selections** (where each icon came from) |
| `{toolId}.png` / `.gif` / `.jpg` / `.webp` / `.ico` / `.svg` | Per-tool launcher icons |

## How icons are chosen (launcher)

1. **Personal override** (this browser only) — IndexedDB  
2. **Shared file** from this folder via `manifest.json`  
3. **Emoji fallback** built into the launcher  

## Publish icons you already picked (recommended)

If you already chose icons (launcher Edit Icons, library folder, or `HTML Code Tools Specific Icons`):

```powershell
# Copy selections + rebuild manifest from assets/tool-icons
.\Scripts\Set-FAFOToolIcon.ps1 -PublishShared

# Also auto-match any tool-named files in your Completed ICO library
.\Scripts\Set-FAFOToolIcon.ps1 -PublishShared -ScanLibrary
```

Or double-click **`Publish-Shared-Icons.bat`** in the toolbox root.

Then commit so others get the same icons on `git pull`:

```powershell
git add assets/tool-icons
git commit -m "Share selected tool icons"
git push
```

### Selections file

`icon-sources.json` remembers where each icon came from (relative to your library root). Example:

```json
"selections": {
  "image-compare": "HTML Code Tools Specific Icons/image-comparator.ico",
  "video-compare": "HTML Code Tools Specific Icons/Video-Comparator.ico"
}
```

When you set a single icon with `Set-FAFOToolIcon.ps1`, the selection is recorded automatically. Re-run `-PublishShared` later to re-copy from those sources.

## Set / change one icon

### In the app

1. Start the toolbox server (`▶ Start Server`)  
2. Launcher → **Edit Icons** → click a tool → pick PNG / GIF / JPG / WEBP / ICO / SVG  
3. The file is copied into this folder and `manifest.json` is updated  
4. Commit & push so other machines get the same icons  

### From PowerShell

```powershell
# One tool
.\Scripts\Set-FAFOToolIcon.ps1 -ToolId image-compare -SourcePath "C:\path\to\icon.png"

# Main app / Desktop shortcut icon
.\Scripts\Set-FAFOToolIcon.ps1 -ToolId app -SourcePath "C:\path\to\toolbox.ico" -RefreshShortcut

# List known tools + current manifest
.\Scripts\Set-FAFOToolIcon.ps1 -ListTools
```

Supported extensions: `.png` `.gif` `.jpg` `.jpeg` `.webp` `.ico` `.svg` `.bmp`

## Notes

- **Do** commit icons you want shared (`assets/tool-icons/`).  
- **Personal** browser overrides are never written to git by themselves.  
- Desktop `.lnk` shortcuts prefer `.ico` (Windows); the HTML launcher accepts images and animated GIFs.  
- Default icon library (this machine): `%USERPROFILE%\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO`  
