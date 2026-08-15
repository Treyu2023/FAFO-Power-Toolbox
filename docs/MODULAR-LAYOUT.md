# Modular layout (resize · reorder · save)

Every toolbox app can ship **resizable, reorderable sections** with **per-app layout memory**.

## User controls

In apps that adopt the layout engine you get a small toolbar:

| Control | Action |
|---------|--------|
| **Reset layout** | Restore *this* app’s default panel order/sizes |
| **Reset all apps** | Clear every saved layout on this PC |

### Gestures

- **Drag panel header (⠿)** — reorder left/right (or top/bottom) columns  
- **Drag the thin edge between panels** — resize  
- **Drag section title (⠿)** — reorder sections *inside* a panel  
- **Drag section bottom edge** — resize height (when section is resizable)

Layouts **auto-save** to `localStorage` under `fafo_layout_v1_<appId>`.

## Adopting in a new app (required going forward)

1. CSS + JS:

```html
<link rel="stylesheet" href="../shared/aitoolbox-layout.css">
<script src="../shared/aitoolbox-layout.js"></script>
<!-- after aitoolbox-ui.js; before or with aitoolbox-pro.js -->
```

2. Mark the shell:

```html
<div class="main"
     data-fafo-layout-root
     data-fafo-layout-app="unique-app-id"
     data-fafo-layout-type="columns">
  <aside data-fafo-panel="sidebar"
         data-fafo-panel-title="Controls"
         data-fafo-panel-min="200"
         data-fafo-panel-default="280">
    <div data-fafo-section="scan" data-fafo-section-title="Scan">…</div>
    <div data-fafo-section="opts" data-fafo-section-title="Options"
         data-fafo-resizable="1"
         data-fafo-section-min="100"
         data-fafo-section-default="180">…</div>
  </aside>
  <section data-fafo-panel="center"
           data-fafo-panel-title="Results"
           data-fafo-flex="1">…</section>
  <aside data-fafo-panel="detail"
         data-fafo-panel-title="Detail"
         data-fafo-panel-min="260"
         data-fafo-panel-default="360">…</aside>
</div>
```

3. Optional toolbar host in the nav:

```html
<span data-fafo-layout-toolbar></span>
```

`data-fafo-layout-app` **must be unique** per tool (e.g. `duplicate-file-manager`, `pc-diagnostics-hud`).

### Attributes

| Attribute | Where | Meaning |
|-----------|--------|---------|
| `data-fafo-layout-root` | container | Enable engine |
| `data-fafo-layout-app` | container | Storage key |
| `data-fafo-layout-type` | container | `columns` (default) or `rows` |
| `data-fafo-panel` | panel | Stable id |
| `data-fafo-panel-title` | panel | Header label |
| `data-fafo-panel-min` | panel | Min px |
| `data-fafo-panel-default` | panel | Initial width/height |
| `data-fafo-panel-max` | panel | Optional max px |
| `data-fafo-flex="1"` | panel | Fills remaining space |
| `data-fafo-section` | section | Stable id inside panel |
| `data-fafo-section-title` | section | Drag handle label |
| `data-fafo-resizable="1"` | section | Height drag handle |
| `data-fafo-section-min` / `default` | section | Height limits |

## JS API

```js
AIToolboxLayout.init({ appId: 'my-app', root: '.main' });
AIToolboxLayout.reset('my-app');      // one app
AIToolboxLayout.resetAll();           // every app on this PC
AIToolboxLayout.listApps();           // keys with saved layouts
AIToolboxLayout.get('my-app');        // live instance
```

Auto-init runs on `DOMContentLoaded` for every `[data-fafo-layout-root]` (also triggered from `aitoolbox-pro.js`).

## Rolled out (all production tools)

**57 apps** have `data-fafo-layout-root` + layout CSS/JS + toolbar + **explicit** `data-fafo-panel` markers (audit: 0 scaffold-only, 0 issues). **Toolbox Launcher** is excluded (own chrome; assets only).

### Core multi-panel (critical)

| App | App id | Panels |
|-----|--------|--------|
| Duplicate File Manager | `duplicate-file-manager` | sidebar · results · detail |
| Media Library Manager | `media-library-manager` | multi-column |
| File Organizer | `file-organizer` | multi-column |
| Git Repository Manager | `git-repository-manager` | multi-column |
| PC Diagnostics HUD | `pc-diagnostics-hud` | multi-panel |
| LAN Task Manager | `lan-task-manager` | multi-panel |
| System Health Dashboard | `system-health-dashboard` | multi-panel |
| FAFO Task Manager Pro | `fafo-task-manager-pro` | sidebar · main |
| VSR Pipeline Manager | `vsr-pipeline-manager` | setup · rename · teach · dupes · tags |

### Full app-id inventory

| App | App id |
|-----|--------|
| Amortization loan calculator | `accounting-tools-and-calculators-amoritization-loan-calculator2` |
| Universal Converter | `accounting-tools-and-calculators-universal-converter` |
| Bloodmoon Survivor | `bloodmoon-survivor` |
| Compliance Pulse | `business-tax-preparedness-compliance-pulse` |
| LedgerLink Console | `business-tax-preparedness-ledgerlink-console` |
| Mileage Log | `business-tax-preparedness-mileage-log` |
| Partner Period Desk | `business-tax-preparedness-partner-period-desk` |
| Quarterly Tracker | `business-tax-preparedness-quarterly-tracker` |
| TaxForge Expert Share Pack | `business-tax-preparedness-taxforge-expert-share-pack` |
| TaxForge Hub | `business-tax-preparedness-taxforge-hub` |
| Write-Off Workshop | `business-tax-preparedness-write-off-workshop` |
| Year-End War Room | `business-tax-preparedness-year-end-war-room` |
| Git Repository Manager | `git-repository-manager` |
| Empire Seed | `empire-seed` |
| Duplicate File Manager | `duplicate-file-manager` |
| Clear Ghost Devices | `ghostdevicecleaner-clear-ghostdevices` |
| Image Comparator | `image-tools-image-comparitor-with-slider` |
| Image Converter / Cropper | `image-tools-image-converter_cropper-for-chrome-store-resolution` |
| Investor Portal | `investor-portal` |
| Compare Hub | `movie-file-manager-compare-hub` |
| File Organizer | `file-organizer` |
| Guided Pair Match | `movie-file-manager-guided-pair-match` |
| Media Hub | `media-hub` |
| Media Library Manager | `media-library-manager` |
| Pair Review Queue | `movie-file-manager-pair-review-queue` |
| VSR Pipeline Manager | `vsr-pipeline-manager` |
| Progress Map | `progress-map-progress-map` |
| Windows REG QoL Tweaks | `reg-tweak-ai-bat-files-windows-reg-qol-tweaks` |
| Setup Configurator | `setup-configurator` |
| Solar System Debris Tracker | `solar-system-debris-tracker` |
| Startup Command Board | `startup-command-board` |
| Batch Media Converter | `system-tools-batch-media-converter` |
| Disk Space Analyzer | `disk-space-analyzer` |
| Event Deep Dive | `event-deep-dive` |
| Event Viewer | `event-viewer` |
| FAFO Task Manager Pro | `fafo-task-manager-pro` |
| Hardware Board Map | `hardware-board-map` |
| Hosts DNS Blocker | `system-tools-hosts-dns-blocker` |
| IP Profile Switcher | `system-tools-ip-profile-switcher` |
| LAN Task Manager | `lan-task-manager` |
| Malware Defender | `malware-defender` |
| PC Diagnostics HUD | `pc-diagnostics-hud` |
| PC Reports and Log Viewer | `system-tools-index` |
| Secrets Presence Console | `system-tools-secrets-presence-console` |
| Startup Service Manager | `startup-service-manager` |
| System Health Dashboard | `system-health-dashboard` |
| System Health Desk | `system-health-desk` |
| Transfer Monitor | `system-tools-transfer-monitor` |
| Tech Quest | `tech-quest-tech-quest` |
| Typing Assistant Trainer | `typing-assistant-trainer` |
| Commander Site Console | `commander-site-console` |
| Commander Status HUD | `verifone-tools-commander-status-hud` |
| Phone Assist Navigator | `verifone-tools-phone-assist-navigator` |
| Pre-Reload Punch List | `verifone-tools-pre-reload-punch-list` |
| FAFO VID TRIM | `fafo-vid-trim` |
| GEMPlay | `video-tools-gemplayhtml` |
| Video Comparison Slider | `video-tools-video-comparison-slider-tool` |

### Auto-scaffold (fallback for new tools)

If a page only has:

```html
data-fafo-layout-root data-fafo-layout-app="my-app"
```

…and **no** `data-fafo-panel` children, the engine invents panels from common markup:

1. `.sidebar` + `.main` + `.detail` → columns  
2. Stack of `.panel` / `.card` / `.section` → rows  
3. Otherwise one flex “Main” panel  

Prefer explicit `data-fafo-panel` markers for complex apps. Re-audit with `Scripts/_audit_layout_apps.py` and `Scripts/_reaudit_layout.py`.
