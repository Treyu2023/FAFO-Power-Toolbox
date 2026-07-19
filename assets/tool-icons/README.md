# Shared tool icons

Icons in this folder are **defaults for every user** of the toolbox.

| File | Role |
|------|------|
| `manifest.json` | Maps tool ids → filename (also `app` for the main Desktop shortcut) |
| `{toolId}.png` / `.gif` / `.jpg` / `.webp` / `.ico` / `.svg` | Per-tool launcher icons |

## How icons are chosen (launcher)

1. **Personal override** (this browser only) — IndexedDB  
2. **Shared file** from this folder via `manifest.json`  
3. **Emoji fallback** built into the launcher  

## Set / change an icon

### In the app (recommended)

1. Start the toolbox server (`▶ Start Server`)  
2. Launcher → **Edit Icons** → click a tool → pick PNG / GIF / JPG / WEBP / ICO / SVG  
3. The file is copied into this folder and `manifest.json` is updated  
4. Commit & push so other machines get the same icons  

If the server is offline, the icon still saves **personally** in the browser. Use **Publish Shared Icons** after the server is up.

### From PowerShell

```powershell
# One tool
.\Scripts\Set-FAFOToolIcon.ps1 -ToolId image-compare -SourcePath "C:\path\to\icon.png"

# Main app / Desktop shortcut icon
.\Scripts\Set-FAFOToolIcon.ps1 -ToolId app -SourcePath "C:\path\to\toolbox.ico"

# Interactive pick + list known tools
.\Scripts\Set-FAFOToolIcon.ps1 -ListTools
```

Supported extensions: `.png` `.gif` `.jpg` `.jpeg` `.webp` `.ico` `.svg` `.bmp`

## Notes

- **Do** commit icons you want shared.  
- **Personal** browser overrides are never written to git by themselves.  
- Desktop `.lnk` shortcuts prefer `.ico` (Windows); the HTML launcher accepts images and animated GIFs.  
