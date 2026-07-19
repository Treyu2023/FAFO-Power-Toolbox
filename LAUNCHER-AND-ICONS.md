# Custom icon + launcher (AI HTML Toolbox)

## Best option for a custom icon on Windows

**Do not pin the `.html` file.** Windows always shows a browser/document icon for HTML.

| Method | Custom icon? | Look & feel | Recommendation |
|--------|--------------|-------------|----------------|
| `.html` shortcut | Poor | Generic browser | Avoid |
| **`.lnk` shortcut → launch `.bat` + custom `.ico`** | **Yes** | Normal desktop app icon | **Best** |
| Edge/Chrome `--app=` window | Yes (via `.lnk`) | Frameless “app” window | Best with shortcut |
| Real `.exe` wrapper | Yes | True EXE | Overkill unless you package later |

### What we installed

| File | Role |
|------|------|
| `Launch-AI-HTML-Toolbox.bat` | Opens Toolbox in Edge/Chrome **app mode** |
| `assets\AI-HTML-Toolbox.ico` | Default custom icon (from your Completed ICO library) |
| `Install-Desktop-Shortcut.bat` | Creates **Desktop + Start Menu** shortcuts with that icon |
| `Change-Toolbox-Icon.bat` | Pick any `.ico` from your library and rebuild the shortcut |

Your icon library:

`C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO`

### One-time setup

1. Double-click **`Install-Desktop-Shortcut.bat`**
2. On the Desktop, open **AI HTML Toolbox** (not the raw HTML file)
3. Optional: right-click → **Pin to taskbar**

### Change the icon later

- Run **`Change-Toolbox-Icon.bat`**, or  
-  
  ```powershell
  .\Install-Desktop-Shortcut.ps1 -IconPath "C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO\YourIcon.ico" -StartMenu
  ```

### Alternates already copied into `assets\`

- `AI-HTML-Toolbox.ico` — stack (default)
- `AI-HTML-Toolbox-alt-coding.ico` — web coding
- `AI-HTML-Toolbox-alt-wizard.ico` — tools wizard
