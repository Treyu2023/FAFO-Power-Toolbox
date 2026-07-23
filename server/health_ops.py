"""Home Health Hub — aggregates toolbox system metrics into plain-English sections."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import board_ops as board
import disk_ops as disk
import event_ops as events
import health_prefs
import network_ops as net
import security_scan as sec
import startup_ops as startup

# UI maps: ok→Fine, info→FYI, warn→Watch, error→Act
LEVEL_RANK = {"ok": 0, "info": 1, "warn": 2, "error": 3}


def _rank(level: str) -> int:
    return LEVEL_RANK.get(level or "ok", 0)


def _worse(a: str, b: str) -> str:
    return a if _rank(a) >= _rank(b) else b


def _link(label: str, href: str, kind: str = "open") -> dict[str, str]:
    return {"type": kind, "label": label, "href": href}


def _alert(
    *,
    id: str,
    level: str,
    title: str,
    plain_english: str,
    why: str,
    source: str,
    section_id: str,
    actions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "level": level,
        "title": title,
        "plainEnglish": plain_english,
        "whyItMatters": why,
        "source": source,
        "sectionId": section_id,
        "actions": actions or [],
        "snoozedUntil": None,
    }


def _section(
    *,
    id: str,
    title: str,
    level: str,
    headline: str,
    detail: str = "",
    live: bool = True,
    links: list[dict[str, str]] | None = None,
    findings: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "level": level,
        "headline": headline,
        "detail": detail,
        "lastRun": None,
        "live": live,
        "links": links or [],
        "findings": findings or [],
    }


def _proc_preview(limit: int = 5) -> dict[str, Any]:
    """Top processes for hub mini strip (one scan, no per-process network)."""
    try:
        # High limit then slice — avoids two full process_iter passes
        data = net.list_processes(sort_by="cpu", limit=400, include_network=False)
    except Exception:
        return {"topCpu": [], "topMemory": [], "total": 0}

    rows = data.get("processes") or []
    # Idle/System noise is not useful on the hub strip
    skip = {"system idle process", "idle", "system"}
    rows = [p for p in rows if (p.get("name") or "").lower() not in skip]

    def slim(items: list[dict]) -> list[dict]:
        out = []
        for p in items[:limit]:
            out.append({
                "pid": p.get("pid"),
                "name": p.get("name") or "",
                "cpu": p.get("cpu_percent") or 0,
                "memory_human": p.get("memory_human") or "",
                "memory_percent": p.get("memory_percent") or 0,
            })
        return out

    by_cpu = sorted(rows, key=lambda x: x.get("cpu_percent") or 0, reverse=True)
    by_mem = sorted(rows, key=lambda x: x.get("memory_bytes") or 0, reverse=True)
    return {
        "topCpu": slim(by_cpu),
        "topMemory": slim(by_mem),
        "total": data.get("total") or len(rows),
    }


def get_dashboard() -> dict[str, Any]:
    overview = net.get_system_overview()
    intel = sec.get_intel_status()
    disks = disk.get_overview()
    boot = startup.get_overview()
    quarantine = sec.list_quarantine()
    procs = _proc_preview(5)
    try:
        events_preview = events.hub_events_preview(hours=24)
    except Exception as e:
        events_preview = {
            "windowHours": 24,
            "errorCount": None,
            "warningCount": None,
            "themes": [],
            "level": "info",
            "note": f"Event sample unavailable: {e}",
            "supported": False,
        }
    try:
        hardware_preview = board.hub_hardware_preview()
    except Exception as e:
        hardware_preview = {
            "matched": False,
            "level": "info",
            "headline": "Hardware map unavailable",
            "detail": str(e),
            "notices": [],
            "problemDevices": 0,
        }

    cpu_pct = float(overview["cpu"]["percent"] or 0)
    mem_pct = float(overview["memory"]["percent"] or 0)
    disk_pct = float(overview["disk"]["percent"] or 0)
    drives = disks.get("drives") or []
    auto_svc = int(boot.get("auto_services") or 0)
    startup_n = int(boot.get("startup_count") or 0)
    threat_hashes = int(intel.get("total_hashes") or 0)
    q_count = len(quarantine)
    proc_total = int(overview.get("process_count") or procs.get("total") or 0)

    alerts: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []  # backward-compatible flat list

    # ── CPU ──────────────────────────────────────────────────────────
    cpu_level = "ok"
    cpu_headline = f"CPU load is comfortable at {cpu_pct:.0f}%."
    cpu_detail = f"{overview['cpu'].get('cores_logical') or '?'} logical cores · live sample"
    if cpu_pct > 95:
        cpu_level = "error"
        cpu_headline = f"CPU is nearly maxed out ({cpu_pct:.0f}%)."
        cpu_detail = "Something may be stuck in a heavy loop. Check Task Manager for the top process."
        a = _alert(
            id="cpu-critical",
            level="error",
            title=f"CPU nearly maxed ({cpu_pct:.0f}%)",
            plain_english="Your processor is working as hard as it can right now. The PC may feel slow or hot.",
            why="Long stretches at 100% can mean a runaway app, mining malware, or a stuck update.",
            source="system",
            section_id="cpu",
            actions=[
                _link("Open Task Manager (by CPU)", "LAN Task Manager.html#processes?sort=cpu"),
                _link("Fix ideas", "Hardware Board Map.html?assist=1&playbook=high-cpu"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "error", "message": a["title"], "source": "system"})
    elif cpu_pct > 85:
        cpu_level = "warn"
        cpu_headline = f"CPU is working hard ({cpu_pct:.0f}%)."
        cpu_detail = "Fine during games or exports; watch if this stays high while idle."
        a = _alert(
            id="cpu-high",
            level="warn",
            title=f"High CPU usage ({cpu_pct:.0f}%)",
            plain_english="The processor is under heavy load. That is normal while gaming, rendering, or scanning — less so if you are just browsing.",
            why="Sustained high CPU can heat the system and make everything feel sluggish.",
            source="system",
            section_id="cpu",
            actions=[
                _link("Open Task Manager (by CPU)", "LAN Task Manager.html#processes?sort=cpu"),
                _link("Fix ideas", "Hardware Board Map.html?assist=1&playbook=high-cpu"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "warn", "message": a["title"], "source": "system"})

    # ── Memory ───────────────────────────────────────────────────────
    mem_level = "ok"
    mem_used = overview["memory"].get("used_human") or ""
    mem_total = overview["memory"].get("total_human") or ""
    mem_headline = f"Memory looks fine — {mem_used} of {mem_total} in use ({mem_pct:.0f}%)."
    mem_detail = "Live sample from this PC."
    if mem_pct > 95:
        mem_level = "error"
        mem_headline = f"Memory is almost full ({mem_pct:.0f}%)."
        mem_detail = "Windows may start thrashing to disk. Close heavy apps or reboot if it freezes."
        a = _alert(
            id="mem-critical",
            level="error",
            title=f"Memory almost full ({mem_pct:.0f}%)",
            plain_english="Almost all RAM is used. The PC can freeze, stutter, or crawl as Windows swaps to disk.",
            why="Running out of memory is a common cause of ‘everything is laggy’ complaints.",
            source="system",
            section_id="memory",
            actions=[
                _link("Open Task Manager (by memory)", "LAN Task Manager.html#processes?sort=memory"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "error", "message": a["title"], "source": "system"})
    elif mem_pct > 90:
        mem_level = "warn"
        mem_headline = f"Memory is getting tight ({mem_pct:.0f}%)."
        mem_detail = f"{mem_used} of {mem_total} used. Close a few heavy apps if the PC feels slow."
        a = _alert(
            id="mem-high",
            level="warn",
            title=f"High memory use ({mem_pct:.0f}%)",
            plain_english=f"Most of your RAM is in use ({mem_used} of {mem_total}). You may still be fine, but there is little headroom left.",
            why="When RAM fills up, Windows slows down to free space.",
            source="system",
            section_id="memory",
            actions=[
                _link("Open Task Manager (by memory)", "LAN Task Manager.html#processes?sort=memory"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "warn", "message": a["title"], "source": "system"})

    # ── Storage ──────────────────────────────────────────────────────
    storage_level = "ok"
    storage_findings: list[dict[str, str]] = []
    tight_drives = []
    critical_drives = []
    for d in drives:
        pct = float(d.get("percent") or 0)
        mount = d.get("mount") or d.get("device") or "?"
        free_h = d.get("free_human") or ""
        finding_level = "ok"
        if pct > 95:
            finding_level = "error"
            critical_drives.append(d)
        elif pct > 90:
            finding_level = "warn"
            tight_drives.append(d)
        storage_findings.append({
            "level": finding_level,
            "text": f"{mount} — {pct:.0f}% used · {free_h} free",
        })
        if finding_level == "error":
            a = _alert(
                id=f"disk-critical-{mount}",
                level="error",
                title=f"Drive {mount} is almost full ({pct:.0f}%)",
                plain_english=f"There is almost no free space left on {mount} ({free_h} free). Apps and Windows updates can fail.",
                why="Full disks cause failed saves, update errors, and general instability.",
                source="disk",
                section_id="storage",
                actions=[
                    _link("Open Disk Analyzer", "Disk Space Analyzer.html"),
                    _link("Fix ideas", "Hardware Board Map.html?assist=1&playbook=low-disk"),
                    _link("Report library", "PC Reports and Log Viewer/index.html"),
                ],
            )
            alerts.append(a)
            issues.append({"level": "error", "message": a["title"], "source": "disk"})
        elif finding_level == "warn":
            a = _alert(
                id=f"disk-low-{mount}",
                level="warn",
                title=f"Low free space on {mount} ({pct:.0f}% used)",
                plain_english=f"Drive {mount} is getting full — about {free_h} free. Time to clean downloads, old installers, or move media.",
                why="Windows and apps need free space for temp files and updates.",
                source="disk",
                section_id="storage",
                actions=[
                    _link("Open Disk Analyzer", "Disk Space Analyzer.html"),
                    _link("Fix ideas", "Hardware Board Map.html?assist=1&playbook=low-disk"),
                ],
            )
            alerts.append(a)
            issues.append({"level": "warn", "message": a["title"], "source": "disk"})

    if critical_drives:
        storage_level = "error"
        names = ", ".join(d.get("mount") or "?" for d in critical_drives)
        storage_headline = f"Critical: almost no free space on {names}."
    elif tight_drives:
        storage_level = "warn"
        names = ", ".join(d.get("mount") or "?" for d in tight_drives)
        storage_headline = f"Getting full on {names} — free up space soon."
    elif drives:
        storage_level = "ok"
        storage_headline = f"{len(drives)} drive(s) have healthy free space (C: {disk_pct:.0f}% used)."
    else:
        storage_headline = "Could not list drives."
        storage_level = "info"

    # ── Processes ────────────────────────────────────────────────────
    proc_level = "ok"
    top_cpu = (procs.get("topCpu") or [{}])[0]
    top_name = top_cpu.get("name") or "—"
    top_cpu_pct = float(top_cpu.get("cpu") or 0)
    proc_headline = f"{proc_total} processes running · top CPU: {top_name}"
    proc_detail = "Live list — open Task Manager for kill/detail controls."
    if cpu_level in ("warn", "error") and top_cpu_pct >= 20:
        proc_level = cpu_level
        proc_headline = f"Heavy load — {top_name} is a top CPU consumer ({top_cpu_pct:.0f}%)."
    elif mem_level in ("warn", "error"):
        proc_level = mem_level
        top_mem = (procs.get("topMemory") or [{}])[0]
        proc_headline = f"Memory pressure — check {top_mem.get('name') or 'top apps'} in Task Manager."

    # ── Network ──────────────────────────────────────────────────────
    net_send = overview["network"].get("send_rate_human") or "0"
    net_recv = overview["network"].get("recv_rate_human") or "0"
    net_level = "ok"
    net_headline = f"Network is active · ↑ {net_send}  ↓ {net_recv}"
    net_detail = "Live throughput sample. Use LAN Task Manager for connections and LAN scan."

    # ── Boot / startup ───────────────────────────────────────────────
    boot_level = "ok"
    boot_headline = (
        f"{startup_n} startup items · "
        f"{boot.get('running_services') or 0}/{boot.get('service_count') or 0} services running · "
        f"{boot.get('task_count') or 0} scheduled tasks"
    )
    boot_detail = f"{auto_svc} services set to auto-start."
    if auto_svc > 100:
        boot_level = "warn"
        boot_headline = f"Many auto-start services ({auto_svc}) — boot may feel heavy."
        a = _alert(
            id="startup-auto-heavy",
            level="warn",
            title=f"{auto_svc} auto-start services",
            plain_english="A large number of services are set to start with Windows. That can slow boot and background performance.",
            why="Each auto service adds work at login. Many are needed; some are leftover software.",
            source="startup",
            section_id="boot",
            actions=[
                _link("Open Startup Manager", "Startup Service Manager.html"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "warn", "message": a["title"], "source": "startup"})
    elif auto_svc > 80:
        boot_level = "info"
        boot_headline = f"{auto_svc} auto-start services — worth a quick review if boot is slow."
        issues.append({
            "level": "info",
            "message": f"{auto_svc} auto-start services — review Startup Manager",
            "source": "startup",
        })

    # ── Security ─────────────────────────────────────────────────────
    sec_level = "ok"
    sec_headline = f"Threat database has {threat_hashes:,} hashes · {q_count} quarantined"
    sec_detail = "Threat intel used by Malware Defender."
    if threat_hashes == 0:
        sec_level = "info"
        sec_headline = "Threat database not loaded yet — run Malware Defender to update."
        issues.append({
            "level": "info",
            "message": "Threat database not updated — run Malware Defender scan",
            "source": "security",
        })
    if q_count > 0:
        sec_level = _worse(sec_level, "warn")
        sec_headline = f"{q_count} item(s) in quarantine — review Malware Defender."
        a = _alert(
            id="security-quarantine",
            level="warn",
            title=f"{q_count} item(s) quarantined",
            plain_english="Malware Defender has isolated one or more files. They are not running, but you should review what was caught.",
            why="Quarantine means something looked suspicious enough to lock down.",
            source="security",
            section_id="security",
            actions=[
                _link("Open Malware Defender", "Malware Defender.html"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "warn", "message": a["title"], "source": "security"})

    # ── Events (live sample + themes) ────────────────────────────────
    ev_level = events_preview.get("level") or "ok"
    ev_err = events_preview.get("errorCount")
    ev_warn = events_preview.get("warningCount")
    ev_themes = events_preview.get("themes") or []
    if events_preview.get("supported") is False and ev_err is None:
        events_section = _section(
            id="events",
            title="Event log",
            level="info",
            headline="Event log sampling is not available on this platform.",
            detail=events_preview.get("note") or "",
            live=False,
            links=[
                _link("PC Reports & logs", "PC Reports and Log Viewer/index.html"),
            ],
        )
    else:
        top_theme = ev_themes[0] if ev_themes else None
        if top_theme and top_theme.get("level") in ("warn", "error"):
            ev_headline = f"{top_theme.get('title')} · {ev_err or 0} errors / {ev_warn or 0} warnings (24h sample)"
        elif ev_themes:
            ev_headline = f"{len(ev_themes)} theme(s) · {ev_err or 0} errors / {ev_warn or 0} warnings sampled"
        else:
            ev_headline = f"No error/warning events in the sample window ({ev_err or 0}/{ev_warn or 0})."
        ev_findings = [
            {
                "level": t.get("level") or "info",
                "text": f"{t.get('title')} ({t.get('count')}×) — {t.get('care') or t.get('plainEnglish', '')[:80]}",
            }
            for t in ev_themes[:6]
        ]
        events_section = _section(
            id="events",
            title="Event log",
            level=ev_level if ev_level != "ok" else ("info" if (ev_warn or 0) > 0 else "ok"),
            headline=ev_headline,
            detail=events_preview.get("note") or "Live sample of System + Application errors/warnings.",
            live=True,
            links=[
                _link("Open Event Viewer", "Event Viewer.html"),
                _link("Readable health summary", "PC Reports and Log Viewer/reports/pc-health-readable.html"),
                _link("PC Reports & logs", "PC Reports and Log Viewer/index.html"),
            ],
            findings=ev_findings,
        )
        # Raise hub alerts for actionable themes (not pure noise)
        for t in ev_themes:
            if t.get("level") not in ("warn", "error"):
                continue
            tid = t.get("id") or "theme"
            a = _alert(
                id=f"event-theme-{tid}",
                level=t.get("level") or "warn",
                title=t.get("title") or tid,
                plain_english=t.get("plainEnglish") or "",
                why=f"Care: {t.get('care') or 'Review'}. Seen about {t.get('count', 0)} time(s) in the last 24h sample.",
                source="events",
                section_id="events",
                actions=[
                    _link("View theme", f"Event Viewer.html?theme={tid}"),
                    _link("Fix ideas", f"Hardware Board Map.html?assist=1&theme={tid}"),
                    _link("Event Viewer", "Event Viewer.html"),
                    _link("Task Manager", "LAN Task Manager.html#processes"),
                ],
            )
            alerts.append(a)
            issues.append({
                "level": a["level"],
                "message": a["title"],
                "source": "events",
            })

    # USB / problem devices from hardware identity
    problem_n = int(hardware_preview.get("problemDevices") or 0)
    problem_names = hardware_preview.get("problemDeviceNames") or []
    if problem_n:
        usb_level = "warn"
        usb_headline = f"{problem_n} device(s) reporting error/degraded — check USB & Device Manager."
        usb_findings = [{"level": "warn", "text": n} for n in problem_names[:8]]
        a = _alert(
            id="pnp-problem-devices",
            level="warn",
            title=f"{problem_n} problem device(s)",
            plain_english="Windows lists one or more devices as error, degraded, or unknown. Often USB dongles, disabled RGB interfaces, or leftover drivers.",
            why="Broken devices can mean missing Bluetooth, audio, or storage until fixed or intentionally disabled.",
            source="devices",
            section_id="usb",
            actions=[
                _link("Hardware map", "Hardware Board Map.html"),
                _link("Fix ideas (BT conflict)", "Hardware Board Map.html?assist=1&playbook=usb-bt-conflict"),
                _link("Ghost cleaner", "../GhostDeviceCleaner/Clear-GhostDevices.html"),
                _link("Event Viewer", "Event Viewer.html?theme=usb-errors"),
            ],
        )
        alerts.append(a)
        issues.append({"level": "warn", "message": a["title"], "source": "devices"})
    else:
        usb_level = "ok"
        usb_headline = "No PnP devices currently flagged error/degraded."
        usb_findings = [{"level": "ok", "text": usb_headline}]
    usb_section = _section(
        id="usb",
        title="USB & peripherals",
        level=usb_level,
        headline=usb_headline,
        detail="Live PnP status + rear I/O map on the Hardware Board Map page.",
        live=True,
        links=[
            _link("Hardware Board Map", "Hardware Board Map.html"),
            _link("Ghost device cleaner", "../GhostDeviceCleaner/Clear-GhostDevices.html"),
            _link("Event Viewer (USB)", "Event Viewer.html?theme=usb-errors"),
        ],
        findings=usb_findings,
    )

    gpu_names = (hardware_preview.get("identity") or {}).get("gpus") or []
    gpu_label = gpu_names[0] if gpu_names else "Graphics"
    gpu_section = _section(
        id="gpu",
        title="Graphics",
        level="info",
        headline=f"{gpu_label} · watch Event Viewer GPU theme if you see black screens",
        detail="Driver stalls (nvlddmkm) are translated in Event Viewer; use the GPU playbook for steps.",
        live=True,
        links=[
            _link("GPU fix playbook", "Hardware Board Map.html?assist=1&playbook=gpu-watchdog"),
            _link("Event Viewer (GPU)", "Event Viewer.html?theme=gpu-watchdog"),
            _link("Component intel", "Hardware Board Map.html#intel"),
        ],
    )

    fw_level = hardware_preview.get("level") or "info"
    firmware_section = _section(
        id="firmware",
        title="BIOS & board",
        level=fw_level,
        headline=hardware_preview.get("headline") or "Board identity",
        detail=hardware_preview.get("detail") or "",
        live=True,
        links=[
            _link("Hardware Board Map", "Hardware Board Map.html"),
            _link("BIOS / firmware report", "PC Reports and Log Viewer/reports/bios-firmware-report.html"),
            _link("Report library", "PC Reports and Log Viewer/index.html"),
        ],
        findings=[
            {
                "level": n.get("level") or "info",
                "text": n.get("title") or n.get("plainEnglish") or "",
            }
            for n in (hardware_preview.get("notices") or [])[:5]
        ],
    )
    # Curated board/component warn notices → inbox
    for n in hardware_preview.get("notices") or []:
        if n.get("level") not in ("warn", "error"):
            continue
        nid = n.get("id") or "notice"
        pb = n.get("playbookId")
        actions = [_link("Hardware map", "Hardware Board Map.html#intel")]
        if pb:
            actions.insert(0, _link("Fix ideas", f"Hardware Board Map.html?assist=1&playbook={pb}"))
        a = _alert(
            id=f"intel-{nid}",
            level=n.get("level") or "warn",
            title=n.get("title") or nid,
            plain_english=n.get("plainEnglish") or "",
            why="Curated notice for hardware detected on this PC (not a live recall feed).",
            source="hardware",
            section_id="firmware",
            actions=actions,
        )
        # Avoid duplicate titles
        if not any(x.get("id") == a["id"] for x in alerts):
            alerts.append(a)
            issues.append({"level": a["level"], "message": a["title"], "source": "hardware"})

    sections = [
        _section(
            id="cpu",
            title="CPU & load",
            level=cpu_level,
            headline=cpu_headline,
            detail=cpu_detail,
            links=[
                _link("Task Manager", "LAN Task Manager.html#processes?sort=cpu"),
                _link("LAN dashboard", "LAN Task Manager.html#dashboard"),
            ],
            findings=[{"level": cpu_level, "text": cpu_headline}],
        ),
        _section(
            id="memory",
            title="Memory",
            level=mem_level,
            headline=mem_headline,
            detail=mem_detail,
            links=[
                _link("Task Manager (by memory)", "LAN Task Manager.html#processes?sort=memory"),
            ],
            findings=[{"level": mem_level, "text": mem_headline}],
        ),
        _section(
            id="storage",
            title="Storage",
            level=storage_level,
            headline=storage_headline if drives else "No drive data",
            detail=f"C: system volume at {disk_pct:.0f}% used." if drives else "",
            links=[
                _link("Disk Analyzer", "Disk Space Analyzer.html"),
                _link("Report library", "PC Reports and Log Viewer/index.html"),
            ],
            findings=storage_findings,
        ),
        gpu_section,
        usb_section,
        _section(
            id="network",
            title="Network",
            level=net_level,
            headline=net_headline,
            detail=net_detail,
            links=[
                _link("Connections", "LAN Task Manager.html#connections"),
                _link("LAN devices", "LAN Task Manager.html#lan"),
                _link("Network tools", "LAN Task Manager.html#tools"),
            ],
        ),
        events_section,
        _section(
            id="processes",
            title="Processes",
            level=proc_level,
            headline=proc_headline,
            detail=proc_detail,
            links=[
                _link("Full Task Manager", "LAN Task Manager.html#processes"),
            ],
            findings=[
                {"level": "info", "text": f"Top CPU: {p.get('name')} ({p.get('cpu'):.0f}%)"}
                for p in (procs.get("topCpu") or [])[:3]
                if p.get("name")
            ],
        ),
        _section(
            id="boot",
            title="Startup & services",
            level=boot_level,
            headline=boot_headline,
            detail=boot_detail,
            links=[
                _link("Startup Manager", "Startup Service Manager.html"),
            ],
        ),
        _section(
            id="security",
            title="Security",
            level=sec_level,
            headline=sec_headline,
            detail=sec_detail,
            links=[
                _link("Malware Defender", "Malware Defender.html"),
            ],
        ),
        firmware_section,
    ]

    # Overall headline from worst alert / section
    worst = "ok"
    for s in sections:
        worst = _worse(worst, s["level"])
    for a in alerts:
        worst = _worse(worst, a["level"])

    watch_n = sum(1 for a in alerts if a["level"] == "warn")
    act_n = sum(1 for a in alerts if a["level"] == "error")

    if worst == "ok":
        overall_level = "ok"
        headline = "System looks healthy"
        summary = "No yellow or red issues from live checks. Full diagnostics can still surface device or event-log themes."
    elif worst == "info":
        overall_level = "info"
        headline = "Healthy — a few FYIs"
        summary = "Nothing urgent. Optional cleanups or updates are listed in sections."
    elif act_n:
        overall_level = "error"
        headline = f"Attention needed — {act_n} issue(s) to act on" + (f", {watch_n} to watch" if watch_n else "")
        summary = alerts[0]["plainEnglish"] if alerts else "One or more serious conditions were detected."
    else:
        overall_level = "warn"
        headline = f"Mostly fine — {watch_n} thing(s) to watch"
        summary = alerts[0]["plainEnglish"] if alerts else "Something needs a look, but nothing is marked critical."

    # Sort alerts: error first, then warn
    alerts.sort(key=lambda a: -_rank(a["level"]))

    # Phase D — apply snooze / dismiss prefs (device-local)
    visible_alerts, hidden_alerts = health_prefs.filter_alerts(alerts)
    watch_n = sum(1 for a in visible_alerts if a["level"] == "warn")
    act_n = sum(1 for a in visible_alerts if a["level"] == "error")
    # Recompute overall from visible alerts only
    worst_vis = "ok"
    for a in visible_alerts:
        worst_vis = _worse(worst_vis, a["level"])
    for s in sections:
        worst_vis = _worse(worst_vis, s["level"])
    if worst_vis == "ok":
        overall_level = "ok"
        headline = "System looks healthy"
        summary = "No yellow or red issues from live checks (snoozed/dismissed alerts are hidden)."
        if hidden_alerts:
            summary += f" {len(hidden_alerts)} alert(s) hidden by you."
    elif worst_vis == "info":
        overall_level = "info"
        headline = "Healthy — a few FYIs"
        summary = "Nothing urgent. Optional cleanups or updates are listed in sections."
    elif act_n:
        overall_level = "error"
        headline = f"Attention needed — {act_n} issue(s) to act on" + (f", {watch_n} to watch" if watch_n else "")
        summary = visible_alerts[0]["plainEnglish"] if visible_alerts else "One or more serious conditions were detected."
    else:
        overall_level = "warn"
        headline = f"Mostly fine — {watch_n} thing(s) to watch"
        summary = visible_alerts[0]["plainEnglish"] if visible_alerts else "Something needs a look, but nothing is marked critical."

    healthy = overall_level in ("ok", "info") and act_n == 0

    # Section re-run capability flags
    for s in sections:
        s["canRerun"] = True
        s.setdefault("links", [])
        # Ensure re-run is available from UI via API, not only static links

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "healthy": healthy,
        "overall": {
            "level": overall_level,
            "headline": headline,
            "summary": summary,
            "watchCount": watch_n,
            "actCount": act_n,
            "hiddenAlertCount": len(hidden_alerts),
        },
        "issues": issues,  # legacy consumers
        "alerts": visible_alerts,
        "hiddenAlerts": [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "level": a.get("level"),
                "hiddenReason": a.get("hiddenReason"),
                "snoozedUntil": a.get("snoozedUntil"),
            }
            for a in hidden_alerts
        ],
        "alertPrefs": health_prefs.get_public_prefs(),
        "sections": sections,
        "processesPreview": procs,
        "eventsPreview": events_preview,
        "hardwarePreview": hardware_preview,
        "system": {
            "hostname": overview["hostname"],
            "cpu_percent": cpu_pct,
            "memory_percent": mem_pct,
            "memory_used_human": overview["memory"].get("used_human"),
            "memory_total_human": overview["memory"].get("total_human"),
            "disk_percent": disk_pct,
            "process_count": proc_total,
            "net_send_human": net_send,
            "net_recv_human": net_recv,
        },
        "security": {
            "threat_hashes": threat_hashes,
            "last_intel_update": intel.get("last_update"),
            "quarantine_count": q_count,
        },
        "disk": {
            "drives": drives,
            "top_user_folders": (disks.get("user_folders") or [])[:5],
        },
        "startup": {
            "startup_items": startup_n,
            "scheduled_tasks": boot.get("task_count") or 0,
            "services": boot.get("service_count") or 0,
            "running_services": boot.get("running_services") or 0,
            "auto_services": auto_svc,
        },
    }
