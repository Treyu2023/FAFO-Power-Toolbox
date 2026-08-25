# Per-app file snapshots

In-repo undo copies for HTML / JS / CSS tools. **Each app has its own stack.**  
Rolling back Typing Trainer never deletes Event Viewer (or any other tool).

| Rule | Value |
|------|--------|
| Where | `snapshots/<relative-path-of-live-file>/` |
| How many | **Newest 5 per app** (not 5 total for the whole toolbox) |
| Live tools | Never leave `*.bak*` next to the real file |
| Restore | Copy a file from this folder over the live path (use the live filename) |

Examples:

```
snapshots/Typing Assistant Trainer.html/t62k3-20260824.html
snapshots/System Tools/Event Viewer.html/t37-20260824.html
snapshots/shared/aitoolbox-ui.js/before-sync.js
```

## Agents

Before editing a tool:

1. Copy the current live file into **that tool’s** folder under `snapshots/`.
2. Name it with a stamp, keep the original extension (`t63-20260825.html`).
3. If that folder already has 5 files, delete only the **oldest file in that folder**.
4. Do **not** write `Tool.html.bak-…` beside the live tool.

Sweep leftovers:

```powershell
& ".\Scripts\Consolidate-HtmlEditBackups.ps1"    # default -Keep 5 per app
```

Do not commit snapshots of gitignored private apps (`Investor Portal`, `Business Tax Preparedness`).
