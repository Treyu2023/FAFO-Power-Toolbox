/* Report Library catalog — plain-English editions first */
window.REPORT_CATALOG = {
  generatedAt: "2026-07-16T19:00:00-04:00",
  machine: "RWK-DESKTOP",
  toolboxPath: "AI HTML TOOLBOX\\\\System Tools\\\\PC Reports and Log Viewer",
  reports: [
    {
      id: "pc-anomaly",
      title: "Mouse & PC Anomalies",
      summary: "G502 SE freezes explained in plain English — power saving, SanDisk, G HUB, what we fixed.",
      category: "Diagnostics",
      severity: "warn",
      tags: ["G502 SE", "Mouse", "USB", "SanDisk", "Plain English"],
      date: "2026-07-16",
      icon: "radar",
      file: "reports/pc-anomaly-report.html",
      highlights: [
        { label: "Mouse", value: "G502 SE" },
        { label: "Cause", value: "USB power / bus" },
        { label: "Outages", value: "Explained" }
      ]
    },
    {
      id: "usb-power-fix",
      title: "USB Power Fix",
      summary: "Hubs + G502 SE protected from sleep. One step left: Intel USB host controller checkbox.",
      category: "Fixes",
      severity: "ok",
      tags: ["G502 SE", "USB", "Hubs", "Fix", "Plain English"],
      date: "2026-07-16",
      icon: "bolt",
      file: "reports/usb-power-fix-log.html",
      highlights: [
        { label: "G502 SE", value: "Protected" },
        { label: "Hubs", value: "Protected" },
        { label: "Host chip", value: "1 step left" }
      ]
    },
    {
      id: "pc-health-readable",
      title: "PC Health (Plain English)",
      summary: "Your gear by real names — Kraken, Lian Li, G935, drives, network — color-coded status.",
      category: "Diagnostics",
      severity: "info",
      tags: ["Health", "Plain English", "Devices"],
      date: "2026-07-16",
      icon: "heart",
      file: "reports/pc-health-readable.html",
      highlights: [
        { label: "Board", value: "Z790 Hero" },
        { label: "GPU", value: "RTX 4090" },
        { label: "Mouse", value: "G502 SE" }
      ]
    },
    {
      id: "bios-firmware",
      title: "BIOS & Firmware",
      summary: "UEFI, RAM 5600 on 4 sticks, Secure Boot off, USB checklist — what to confirm on next reboot.",
      category: "Firmware",
      severity: "warn",
      tags: ["BIOS", "UEFI", "RAM", "Z790", "Plain English"],
      date: "2026-07-16",
      icon: "cpu",
      file: "reports/bios-firmware-report.html",
      highlights: [
        { label: "BIOS", value: "3107" },
        { label: "RAM", value: "64GB @ 5600" },
        { label: "Secure Boot", value: "Off" }
      ]
    },
    {
      id: "pc-health",
      title: "PC Health — Technical Dump",
      summary: "Raw event log / device tree export for deep troubleshooting (not the friendly summary).",
      category: "Technical",
      severity: "info",
      tags: ["Technical", "Event Log", "Raw"],
      date: "2026-07-16",
      icon: "search",
      file: "reports/pc-health-report.html",
      highlights: [
        { label: "Style", value: "Raw log" },
        { label: "Use", value: "Deep debug" }
      ]
    },
    {
      id: "pc-health-p2",
      title: "PC Health Part 2 — Technical",
      summary: "Deep dump: disk retries, UASP, NVIDIA, registry power flags.",
      category: "Technical",
      severity: "info",
      tags: ["Technical", "Disk", "NVIDIA"],
      date: "2026-07-16",
      icon: "search",
      file: "reports/pc-health-report-part2.html",
      highlights: [
        { label: "Style", value: "Raw log" }
      ]
    }
  ]
};
