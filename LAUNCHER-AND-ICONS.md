# Custom icons + launcher (AI HTML Toolbox)

## How icons work

| Layer | Where | Who sees it |
|-------|--------|-------------|
| **Personal** | Browser IndexedDB | Only this browser / profile |
| **Shared (repo)** | `assets/tool-icons/` + `manifest.json` | **All users** after pull |
| **Fallback** | Emoji on each tool card | Everyone |

**Priority:** personal override → shared file → emoji.

Supported file types: **PNG, GIF, JPG/JPEG, WEBP, ICO, SVG, BMP**.

When you set an icon with the **server running**, the app **copies the file into `assets/tool-icons/{toolId}.ext`** and updates `manifest.json`. Commit that folder to ship defaults to every machine. Users can still change icons locally without overwriting the repo until they publish.

## Best option for a Windows desktop icon

**Do not pin the `.html` file.** Windows shows a browser/document icon for HTML.

| Method | Custom icon? | Recommendation |
|--------|--------------|----------------|
| `.html` shortcut | Poor | Avoid |
| **`.lnk` → `Launch-AI-HTML-Toolbox.bat` + `.ico`** | **Yes** | **Best** |
| Edge/Chrome `--app=` | Yes (via `.lnk`) | Best with shortcut |

### One-time setup

1. Double-click **`Install-Desktop-Shortcut.bat`** (or `.ps1`)
2. Open **AI HTML Toolbox** from the Desktop shortcut
3. Optional: pin to taskbar

### Change the **main app** icon

- Run **`Change-Toolbox-Icon.bat`** and pick any image/GIF/ICO, or  
-  
  ```powershell
  .\Scripts\Set-FAFOToolIcon.ps1 -ToolId app -SourcePath "C:\path\to\icon.png"
  .\Install-Desktop-Shortcut.ps1 -StartMenu
  ```

Windows shortcuts prefer **`.ico`**. The HTML launcher still shows PNG/GIF/etc.

### Change a **tool** icon (all users)

**In the launcher**

1. `▶ Start Server`
2. **Edit Icons** → click a tool → pick PNG/GIF/ICO/…
3. Status should say it saved to `assets/tool-icons/…`
4. **Commit & push** `assets/tool-icons/`

**PowerShell**

```powershell
.\Scripts\Set-FAFOToolIcon.ps1 -ToolId image-compare -SourcePath "D:\icons\compare.png"
.\Scripts\Set-FAFOToolIcon.ps1 -ListTools

# Auto-grab icons you already selected (library + icon-sources.json) into assets/tool-icons
.\Scripts\Set-FAFOToolIcon.ps1 -PublishShared -ScanLibrary
# or double-click Publish-Shared-Icons.bat
```

**Publish personal → shared**

If you set icons while the server was offline, open **Edit Icons** → **Publish Shared** once the server is up — or run `-PublishShared` above. Selections are stored in `assets/tool-icons/icon-sources.json` so re-publish can re-copy from your library.

### Reset

- **Reset Personal** in the launcher clears only this browser’s overrides. Shared repo icons remain.

### Layout

```text
assets/
  AI-HTML-Toolbox.ico          ← legacy default for shortcuts
  tool-icons/
    manifest.json              ← toolId → filename (+ app)
    app.ico                    ← main launcher / optional shortcut
    image-compare.ico
    video-compare.ico
    media-library.png          ← example
    README.md
```

### Icon library on your Desktop

`C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO`
