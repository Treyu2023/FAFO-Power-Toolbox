# HTML Tools Box — Report Library

**Path:** `D:\OUTPUTS\toolbox`

Graphical library for PC / BIOS / diagnostics reports.

**Reports are written in plain English** with friendly names (e.g. **Logitech G502 SE**, not “HID-compliant mouse”), color badges (green / yellow / red), and technical IDs kept in smaller secondary lines or “Technical appendix” sections.

Open with:

```text
Open_Report_Library.bat
```

or double-click `index.html`.

## Layout

```text
toolbox/
  index.html                 ← graphics UI (Reports + Log Viewer tabs)
  catalog.js                 ← report index (add new entries here)
  logs-data.js               ← packed raw logs for offline Log Viewer
  _pack_logs.ps1             ← refresh logs-data.js from reports\
  Open_Report_Library.bat
  README.md
  reports/
    bios-firmware-report.html
    pc-anomaly-report.html
    pc-health-report.html
    pc-health-report-part2.html
    usb-power-fix-log.html
    bios_system_raw.json     ← machine-readable snapshot
    *.md / *.txt             ← source originals
  _collect_bios_system.ps1   ← re-scan BIOS/OS-visible firmware data
```

## Log Viewer

On the dashboard, open the **Log Viewer** tab (or `index.html#logs`).

- Color-codes lines (errors / warnings / OK-ish)
- Search / filter lines, hits-only mode, copy, open raw file
- Works offline via `logs-data.js` (no web server)

After adding or changing `.txt` / `.md` / `.json` under `reports\`, refresh the pack:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\OUTPUTS\toolbox\_pack_logs.ps1"
```

Then reload the page.

## Add a new report

1. Put the file in `reports\` (prefer `.html`; `.md`/`.txt` OK if you wrap them).
2. Append an object to `reports: [...]` in `catalog.js`:

```js
{
  id: "unique-id",
  title: "Short title",
  summary: "One-line description",
  category: "Diagnostics" | "Firmware" | "Fixes",
  severity: "ok" | "warn" | "bad" | "info",
  tags: ["Tag1", "Tag2"],
  date: "YYYY-MM-DD",
  icon: "cpu" | "radar" | "heart" | "search" | "bolt",
  file: "reports/your-file.html",
  highlights: [{ label: "Key", value: "Value" }]
}
```

3. Refresh the Report Library page.

## Re-collect BIOS / system snapshot

```powershell
powershell -ExecutionPolicy Bypass -File "D:\OUTPUTS\toolbox\_collect_bios_system.ps1"
```

Then update or regenerate `reports/bios-firmware-report.html` if needed.

## Notes

- Reports open in an in-page viewer (or “Open in new tab”).
- Works offline via `file://` (no web server required).
- Full BIOS menus cannot be read from Windows; the BIOS report uses SMBIOS/WMI/registry/powercfg plus platform guidance.
