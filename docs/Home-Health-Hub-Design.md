# Home Health Hub — Design Document

**Status:** Phases A–G implemented (2026-07-22)  
**Date:** 2026-07-22  
**Scope:** Unify System Health Dashboard, PC Reports (plain-English layer), live Task Manager, and a human-readable Event Viewer into one color-coded command center.

### Implementation notes

| Phase | Deliverable | Location |
|-------|-------------|----------|
| A | Extended dashboard API | `server/health_ops.py` → `overall`, `alerts`, `sections`, `processesPreview` |
| A | Home Health Hub UI | `System Tools/System Health Dashboard.html` |
| B | Task Manager deep links | `System Tools/LAN Task Manager.html` `#processes?sort=&q=` |
| C | Event themes dictionary | `server/data/event_themes.json` |
| C | Event APIs | `server/event_ops.py` · `GET /api/events/summary|themes|query` |
| C | Event Viewer UI | `System Tools/Event Viewer.html` |
| C | Hub events section + theme alerts | `health_ops` merges `hub_events_preview` |
| D | Alert snooze / dismiss prefs | `server/health_prefs.py` · device `%LOCALAPPDATA%\FAFO\Devices\<PC>\Prefs\` |
| D | Prefs APIs | `POST /api/health/alerts/snooze|dismiss|clear` |
| E | Per-section re-run | `diagnostics_ops.run_section` · `POST /api/diagnostics/run-section` |
| E | Full scan from hub | `POST /api/diagnostics/run` (also on main server) |
| F | Auto plain-English report | `server/health_report.py` → `health-hub-summary.json` + `pc-health-readable-auto.html` |
| F | Generate API | `POST /api/health/report/generate` |
| G | Board pack (Z790 Hero) | `server/data/boards/asus-rog-maximus-z790-hero/` |
| G | Component intel + playbooks | `server/data/component-intel.json`, `server/data/playbooks/index.json` |
| G | Hardware APIs | `server/board_ops.py` · `/api/hardware/*` |
| G | Hardware Board Map UI | `System Tools/Hardware Board Map.html` |
| G | Hub firmware/USB/assist links | `health_ops` + hub quick launch |
| + | Event Deep Dive (ranked issues + fix alternatives) | `server/event_deep_dive.py`, `server/data/event_advice.json`, `System Tools/Event Deep Dive.html`, `GET /api/events/deep-dive` |

---

## 1. Problem

Today system health is split across tools that each do part of the job well:

| Tool | Strength | Gap |
|------|----------|-----|
| **System Health Dashboard** | Live CPU/RAM/disk + thin alerts | No deep sections, no Event Viewer, shallow issue logic |
| **PC Reports & Log Viewer** | Full dumps + severity catalog | Static library; not a daily “what’s wrong?” surface |
| **pc-health-readable** | Best UX: plain English + Fine/Watch/Act | Hand-curated HTML; not auto-refreshed as hub home |
| **LAN & Task Manager** | Real Task Manager (processes, kill, LAN) | Separate app; not driven by health alerts |
| **Diagnostics script** | Event log sampling + findings | Summaries land in reports, not a live inbox |

Non-technical users (and future-you under stress) need **one home page** that answers:

1. Is my PC fine right now?  
2. What should I care about (yellow/red only)?  
3. What does this mean in English?  
4. Where do I dig in (events / processes / full report)?  
5. What can I re-run or open to fix it?

---

## 2. Product vision

### One-liner

**Home Health Hub** = mission control that speaks plain English, color-codes priority, and deep-links into live Task Manager, Event Viewer, section diagnostics, and the report library.

### Voice & severity (locked)

Reuse the readable-report language everywhere:

| Color | Label | Meaning | Inbox? |
|-------|--------|---------|--------|
| Green | **Fine** | No action | No |
| Blue | **FYI** | Expected / intentional / clutter | No (optional filter) |
| Yellow | **Watch** | Monitor or optional fix | Yes |
| Red | **Act** | Failing or risky | Yes |

**Rule:** If a non-tech person cannot decide from color + one sentence, the copy failed—not the user.

### Relationship of tools (not duplication)

```text
                    ┌─────────────────────────────┐
                    │     HOME HEALTH HUB         │
                    │  status · alerts · sections │
                    └──────────────┬──────────────┘
           ┌───────────────┬───────┴────────┬────────────────┐
           ▼               ▼                ▼                ▼
   Task Manager      Event Viewer     Section reports    Fix / assist
   (LAN TM APIs      (new live view    (PC Reports +      (playbooks,
    + deep link)      + translation)    per-section run)   later AI)
```

- **Hub owns:** summary, severity, navigation, re-run triggers, notification inbox.  
- **LAN Task Manager owns:** full process/network table UX (reuse via deep link + shared APIs).  
- **PC Reports owns:** historical dumps and offline catalog.  
- **Event Viewer (new pane or sub-tool):** live/filtered Windows events with plain-English translation—not a clone of `eventvwr.msc` raw tree.

---

## 3. Existing assets to reuse

### UI

| Path | Reuse as |
|------|----------|
| `System Tools/System Health Dashboard.html` | **Primary shell to evolve** into Home Health Hub (or rename/replace) |
| `System Tools/LAN Task Manager.html` | Canonical Task Manager + process APIs consumer |
| `System Tools/PC Reports and Log Viewer/` | Report library, packs, severity chips, device-local junction |
| `System Tools/PC Reports and Log Viewer/assets/report.css` | Shared Fine/Watch/Act styling |
| `System Tools/Startup Service Manager.html` | Deep link for boot/services section |
| `System Tools/Disk Space Analyzer.html` | Deep link for storage |
| `System Tools/Malware Defender.html` | Deep link for security |

### Backend / scripts

| Path | Reuse as |
|------|----------|
| `server/health_ops.py` → `GET /api/health/dashboard` | Extend: richer issues, section statuses, alert IDs |
| `server/network_ops.py` → processes, overview | Live Task Manager data |
| `server/diagnostics_ops.py` | Pack library; later section run hooks |
| `server/startup_ops.py`, `disk_ops.py`, `security_scan.py` | Section data sources |
| `Scripts/Invoke-FAFOSystemDiagnostics.ps1` | Full scan; event sampling; findings list |
| Device store `%LOCALAPPDATA%\FAFO\Devices\<PC>\` | Source of truth for reports (gitignored) |

### Confirmed: Task Manager “already has a home”

There is **no separate Task Manager folder**. The Task Manager lives **inside**:

- **File:** `System Tools/LAN Task Manager.html`  
- **Nav view:** `data-view="processes"` (“Task Manager”)  
- **APIs:**  
  - `GET /api/network/processes`  
  - `GET /api/network/processes/{pid}`  
  - `POST /api/network/processes/kill`  
  - system overview used by its Dashboard tab  

**Design choice:** Do **not** fork a second process UI. Hub embeds a **mini process strip** (top CPU/RAM offenders) and deep-links:

```text
LAN Task Manager.html#processes
LAN Task Manager.html#processes?q=chrome
```

(Optional later: extract shared process-table JS into `shared/` if both pages need the full table.)

### Event Viewer today

- **No dedicated Event Viewer HTML tool.**  
- Diagnostics samples System/Application Level 1–3 via `Get-WinEvent` (last N days, max 500 each) and writes top providers into the status report.  
- Readable report **translates** common piles (DCOM, BrLog, nvlddmkm, etc.) by hand.  
- PC Report Library can show packed log files offline.

**Design choice:** Add **Event Viewer as a first-class Hub section + optional full page**, with:

1. Live/recent query API (server)  
2. Aggregation by provider/theme  
3. Plain-English dictionary for known providers  
4. “Open full technical list” and “Include in next health report”

---

## 4. Information architecture

### 4.1 Home layout (wireframe)

```text
┌──────────────────────────────────────────────────────────────────┐
│ ← Toolbox    HOME HEALTH HUB          [Connected]  [Run full scan]│
├──────────────────────────────────────────────────────────────────┤
│  ● MOSTLY FINE — 2 things to watch                               │
│  Last full scan: 2h ago · Live vitals refresh: 15s               │
│  [CPU 12%] [RAM 61%] [Disk C: 74%] [Procs 312] [Net ↑↓]         │
├────────────────────────────┬─────────────────────────────────────┤
│  NOTIFICATIONS (Watch/Act) │  SECTIONS                           │
│  ┌──────────────────────┐  │  ┌────────┐ ┌────────┐ ┌────────┐ │
│  │ 🔴 BT dongle failed  │  │  │ CPU    │ │ Memory │ │ Storage│ │
│  │ Plain English…       │  │  │ Fine   │ │ Fine   │ │ Watch  │ │
│  │ [Details] [Events]   │  │  └────────┘ └────────┘ └────────┘ │
│  │ [Processes] [Fix]    │  │  ┌────────┐ ┌────────┐ ┌────────┐ │
│  └──────────────────────┘  │  │ GPU    │ │ USB    │ │ Network│ │
│  ┌──────────────────────┐  │  │ Fine   │ │ Watch  │ │ Watch  │ │
│  │ 🟡 External SSD      │  │  └────────┘ └────────┘ └────────┘ │
│  │ retries in event log │  │  ┌────────┐ ┌────────┐ ┌────────┐ │
│  └──────────────────────┘  │  │ Events │ │ Procs  │ │ Boot   │ │
│                            │  │ Watch  │ │ Live   │ │ Fine   │ │
│  (empty → green check)     │  └────────┘ └────────┘ └────────┘ │
│                            │  ┌────────┐ ┌────────┐            │
│                            │  │Security│ │Firmware│            │
│                            │  └────────┘ └────────┘            │
├────────────────────────────┴─────────────────────────────────────┤
│  QUICK LAUNCH: Task Manager · Event Viewer · Report Library · …  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Section expand (drawer or accordion)

On section click:

```text
┌─ Storage ──────────────────────────────── Watch ─┐
│ Two Crucial NVMe OK. SanDisk USB had disk retries. │
│ Last section run: today 10:12                      │
│                                                    │
│ Findings                                           │
│  · C: 74% free space Fine                          │
│  · SanDisk Extreme — Watch (event theme: disk)     │
│                                                    │
│ [Re-run this section] [Open Disk Analyzer]         │
│ [Related events] [Full report in library]          │
└────────────────────────────────────────────────────┘
```

### 4.3 Task Manager integration

| Hub surface | Behavior |
|-------------|----------|
| **Vitals strip** | Process count from existing dashboard payload |
| **Section: Processes** | Status from live sample: e.g. Fine / Watch if CPU or RAM sustained high; list top 5 by CPU and top 5 by memory |
| **Alert actions** | “Open in Task Manager” → `LAN Task Manager.html#processes` (+ search query when known) |
| **High CPU alert** | Card links to processes sorted by CPU |
| **Full Task Manager** | Always one click away; kill/detail stays in LAN Task Manager (don’t rebuild kill UX in Hub) |

**Deep-link contract (implement with hash):**

| Hash / query | Opens |
|--------------|--------|
| `#processes` | Task Manager view |
| `#processes?sort=cpu` | Sort by CPU |
| `#processes?q=nvcontainer` | Pre-filled search |
| `#dashboard` | LAN TM system dashboard |
| `#connections` | Network connections |

LAN Task Manager should read `location.hash` on load and select the matching `data-view`.

### 4.4 Event Viewer integration

| Hub surface | Behavior |
|-------------|----------|
| **Section: Events** | Count of errors/warnings in window; top 3 **themes** in plain English; severity of worst theme |
| **Notification cards** | “Related events” opens Event Viewer filtered to provider/theme |
| **Readable translation** | Dictionary maps provider names → human meaning + care level (seed from `pc-health-readable`) |
| **Full Event Viewer page** | Optional: `System Tools/Event Viewer.html` **or** a full-width Hub subview — filter by log (System/Application), level, time range, search; group by provider; expand raw message |

**Not in scope for v1:** full channel tree like `eventvwr.msc`, subscription management, or clearing logs.

**Open native Event Viewer (escape hatch):** button that shells `eventvwr.msc` via existing toolbox server/protocol helpers if available; otherwise document “Win+R → eventvwr”.

---

## 5. Data model

### 5.1 Extended dashboard payload

`GET /api/health/dashboard` (evolve `health_ops.get_dashboard`):

```json
{
  "timestamp": "ISO-8601",
  "healthy": false,
  "overall": {
    "level": "warn",
    "headline": "Mostly fine — 2 things to watch",
    "summary": "Bluetooth dongle failed; external SSD had disk retries recently."
  },
  "system": { "...existing vitals..." },
  "security": { "...existing..." },
  "startup": { "...existing..." },
  "sections": [
    {
      "id": "storage",
      "title": "Storage",
      "level": "warn",
      "headline": "Main SSDs healthy; portable drive needs watching",
      "lastRun": "ISO-8601|null",
      "live": true,
      "links": [
        { "label": "Disk Analyzer", "href": "Disk Space Analyzer.html" },
        { "label": "Related events", "href": "#section=events&theme=disk" }
      ]
    }
  ],
  "alerts": [
    {
      "id": "dev-bt500-start-fail",
      "level": "error",
      "title": "Bluetooth dongle failed to start",
      "plainEnglish": "Windows could not load the ASUS USB-BT500…",
      "whyItMatters": "Wireless devices may conflict or drop.",
      "source": "devices",
      "sectionId": "usb",
      "actions": [
        { "type": "open", "label": "Task Manager", "href": "LAN Task Manager.html#processes" },
        { "type": "open", "label": "Events", "href": "Event Viewer.html?q=Bluetooth" },
        { "type": "rerun", "label": "Re-check USB", "section": "usb" },
        { "type": "fix", "label": "Fix ideas", "playbookId": "usb-bt-conflict" }
      ],
      "snoozedUntil": null
    }
  ],
  "processesPreview": {
    "topCpu": [{ "pid": 1, "name": "…", "cpu": 12.3, "memory_human": "…" }],
    "topMemory": []
  },
  "eventsPreview": {
    "windowHours": 24,
    "errorCount": 12,
    "warningCount": 40,
    "themes": [
      {
        "id": "disk-retries",
        "level": "error",
        "title": "Disk retries on portable SSD",
        "plainEnglish": "External drive hiccuped mid-transfer.",
        "care": "Yes — watch that drive",
        "providers": ["disk", "ntfs"],
        "count": 8
      }
    ]
  }
}
```

**Severity mapping:** API may use `ok|info|warn|error`; UI maps to Fine / FYI / Watch / Act.

### 5.2 Event query API (new)

```text
GET /api/events/summary?hours=24&max=500
GET /api/events/query?log=System&level=error,warning&hours=24&provider=&q=&limit=100
GET /api/events/themes   # aggregated + translated
```

Implementation notes:

- Prefer **Python** on the toolbox server (PowerShell subprocess or `win32`/WMI) so HTML stays server-backed like Task Manager.  
- Cap sample size; never stream entire event DB into the browser.  
- Cache summary 30–60s to avoid hammering the event log.  
- Translation table: `server/data/event_themes.json` or `shared/event-themes.json` (provider patterns → plain English + care).

### 5.3 Process preview

Reuse `network_ops.list_processes` with `sort_by=cpu|memory` and `limit=5` inside `health_ops` so Hub does not invent a second process pipeline.

### 5.4 Device-local snapshot (offline / after full scan)

Written by diagnostics (extend current status report):

```text
%LOCALAPPDATA%\FAFO\Devices\<PC>\Reports\PC\health-hub-summary.json
```

Hub merges:

- **Live** (server online): vitals, process preview, recent events, threshold alerts  
- **Snapshot** (last full diagnostics): device errors, SMART-ish findings, firmware identity, richer English  

If server offline: show last snapshot + banner to start server (existing pattern).

### 5.5 Section registry

| id | Title | Live source | Scan source | Deep links |
|----|-------|-------------|-------------|------------|
| `cpu` | CPU & load | overview CPU | diagnostics | Task Manager `#processes?sort=cpu` |
| `memory` | Memory | overview RAM | diagnostics | Task Manager `#processes?sort=memory` |
| `storage` | Storage | disk_ops | diagnostics + events theme disk | Disk Analyzer, Events |
| `gpu` | Graphics | optional WMI/driver | diagnostics / nvlddmkm theme | Events |
| `usb` | USB & peripherals | problem devices (scan) | diagnostics | Ghost cleaner, Events |
| `network` | Network | net overview | diagnostics | LAN TM `#connections`, `#lan` |
| `events` | Event log | `/api/events/*` | diagnostics sample | Event Viewer full |
| `processes` | Processes | `/api/network/processes` | — | LAN TM `#processes` |
| `boot` | Startup & services | startup_ops | diagnostics | Startup Service Manager |
| `security` | Security | security_scan intel | — | Malware Defender |
| `firmware` | BIOS / board | snapshot BaseBoard/BIOS | collect scripts | Report library BIOS report |

---

## 6. Event Viewer UX (detail)

### Goals

- Feel like “Event Viewer for humans,” not a raw log dump.  
- Default view: **Themes** (grouped), not every row.  
- One click to **raw rows** for a theme.  
- Color chips match hub severity.  
- Always show: “This is normal clutter” for DCOM-style noise so users don’t panic.

### Views

1. **Themes** (default) — cards sorted by care level then count  
2. **Timeline** — recent errors/warnings list (paginated)  
3. **By provider** — table of provider → count → care  

### Seed translation entries (from existing readable report)

| Pattern / provider | Plain English | Care |
|--------------------|---------------|------|
| DCOM / DistributedCOM | Background Windows components talking slowly | Fine (usually) |
| Brother BrLog | Printer software missing IP for a feature | FYI unless printing broken |
| disk / retries / SanDisk | Drive hiccuped mid-transfer | Act / Watch |
| nvlddmkm / Display | GPU driver recovered from a stall | Watch if black screens |
| Tcpip / e1dexpress / link | Ethernet link down/up | Watch if internet drops |
| Kernel-Power 41 | Unexpected reboot / power loss | Context-dependent |
| ACPI / Embedded Controller | Board firmware/EC chatter (common on ASUS) | Fine (usually) |

Dictionary is data-driven so new machines get the same behavior without hand HTML.

---

## 7. Task Manager UX in the hub (detail)

### Mini strip (on Home)

- Top 5 CPU + top 5 memory  
- Click row → open LAN Task Manager with search = process name  
- “Open full Task Manager” button  

### When alerts mention a process

If assist/playbook or event mentions `chrome.exe` / `nvcontainer`, action button pre-fills `#processes?q=…`.

### What stays only in LAN Task Manager

- Kill process / force kill  
- Per-PID detail drawer  
- Connection list, LAN scan, network tools  

Hub **navigates**; LAN TM **operates**.

---

## 8. Motherboard / USB map & manufacturer intel (later phases)

Documented for roadmap completeness; not required for Hub v1.

- Board identity from `Win32_BaseBoard` (already in diagnostics).  
- Per-board pack: `boards/<slug>/rear-io.svg` + `ports.json` + support links.  
- USB tree from device manager APIs; physical port = best-effort + optional user labels.  
- Component notices: curated JSON keyed by model; optional AI only after playbooks.

---

## 9. Assist / fix resources (later)

Priority order:

1. **Playbooks** offline (`playbooks/*.json`: steps, when to stop, related section).  
2. **Deep links** into existing tools.  
3. **Guided search query** built from board + device + error.  
4. **Optional AI** (sanitized context, fixed output schema).  

Never show AI as the only authority on recalls/safety.

---

## 10. Phased delivery

### Phase A — Home shell + sections + severity (MVP)

- Evolve `System Health Dashboard.html` → Home Health Hub layout.  
- Color-coded overall status + section cards from extended `/api/health/dashboard`.  
- Alert list: yellow/red only; plain-English fields (even if initially thin).  
- Quick launch row (including Task Manager + Report Library).  
- Shared CSS tokens aligned with `report.css`.

### Phase B — Task Manager wiring

- Hash routing in `LAN Task Manager.html` (`#processes`, query `q`, `sort`).  
- Hub process preview (top CPU/RAM) + deep links.  
- Process section card on Hub.

### Phase C — Event Viewer

- `GET /api/events/summary` + `query` (+ themes).  
- Event themes dictionary.  
- Hub events section + preview on home.  
- Full Event Viewer UI (subview or `Event Viewer.html`).  
- Alert actions → filtered events.

### Phase D — Notification quality + snooze

- Stable alert IDs; snooze/dismiss in device-local prefs.  
- Merge live thresholds + last diagnostics findings (dedupe).  
- “Disabled on purpose” suppressions (Aura, unused RAID) as FYI not Act.

### Phase E — Per-section re-run

- `POST /api/diagnostics/run?section=…` (or PowerShell -Section).  
- Write/update `health-hub-summary.json` + refresh packs.  
- Button on each section card.

### Phase F — Auto plain-English report generation

- Generate readable HTML/JSON from structured findings (replace hand-only `pc-health-readable` as default).  
- Keep hand notes as optional overrides.

### Phase G — Board I/O map + component intel + assist

- Z790 Hero (or detected board) SVG map.  
- Curated notices; playbooks; optional search/AI panel.

---

## 11. API / file change summary (implementation checklist)

| Change | Purpose |
|--------|---------|
| `server/health_ops.py` | sections, alerts, overall headline, process/events previews |
| `server/event_ops.py` (new) | query + summarize + theme-match |
| `server/aitoolbox_server.py` | route registration for events APIs |
| `server/data/event_themes.json` (new) | translation dictionary |
| `System Tools/System Health Dashboard.html` | Hub UI |
| `System Tools/LAN Task Manager.html` | hash deep links |
| `System Tools/Event Viewer.html` (new, Phase C) | full human event UI |
| `Scripts/Invoke-FAFOSystemDiagnostics.ps1` | emit `health-hub-summary.json`; optional -Section |
| `docs/Home-Health-Hub-Design.md` | this document |

Device-local only for machine-specific output; no desktop dumps in git (existing FAFO rule).

---

## 12. UX copy guidelines

- Prefer **device friendly names** (“Graphics card”, “Portable drive”) over PnP IDs; show tech IDs secondary.  
- Event providers: always pair **Windows said** → **What it means** → **Care?**  
- Avoid alarm language for known-benign noise.  
- Empty inbox copy: “No yellow or red issues — you’re clear.”  
- Offline server: same pattern as today (Start Server + last snapshot if any).

---

## 13. Success criteria

1. A non-technical user can open Hub and know green vs “do something” in under 10 seconds.  
2. Every red/yellow alert has plain English + at least one useful action (Events, Task Manager, tool, or re-run).  
3. Task Manager is one click from Hub and opens the right view/filter.  
4. Event Viewer themes reduce “500 DCOM errors panic” to “Fine — background clutter.”  
5. Full raw reports remain available in PC Reports for power users.  
6. Still works device-local; no cross-machine report leakage via git.

---

## 14. Open decisions (resolve during Phase A)

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Rename dashboard file? | Keep name vs `Home Health Hub.html` | Keep path for bookmarks; change title in UI to **Home Health Hub** |
| Event Viewer location | Subview inside Hub vs separate HTML | Separate HTML + Hub embed/preview (matches Task Manager pattern) |
| Kill process from Hub? | Yes / No | **No** in v1 — deep link only |
| Admin elevation for some events | Prompt / degrade | Degrade gracefully; show what non-admin can see |

---

## 15. PR plan (suggested)

| PR | Title | Depends |
|----|-------|---------|
| PR1 | Extend `health_ops` dashboard schema + Hub shell UI (sections + alerts) | — |
| PR2 | LAN Task Manager hash deep links + Hub process preview | PR1 |
| PR3 | `event_ops` + themes dictionary + Hub events section | PR1 |
| PR4 | Event Viewer page + alert deep links | PR3 |
| PR5 | Diagnostics `health-hub-summary.json` + merge into dashboard | PR1 |
| PR6 | Snooze/prefs + section re-run | PR5 |

---

## 16. Summary

The Home Health Hub becomes the **plain-English front door** to system health. **LAN Task Manager** remains the real Task Manager (already under System Tools as one HTML app with a Processes view). **Event Viewer** becomes a new first-class human-readable surface, fed by server APIs and a translation dictionary seeded from the existing readable health report. Live vitals and process previews stay online; deep scans and library packs stay device-local. Color, language, and click paths stay consistent so anyone can understand their PC—and power users can still drill into events, processes, and raw reports.
