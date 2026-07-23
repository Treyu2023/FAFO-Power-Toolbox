"""Generate plain-English health hub summary JSON + HTML (device-local)."""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import diagnostics_ops as diag


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label(level: str) -> str:
    return {"ok": "Fine", "info": "FYI", "warn": "Watch", "error": "Act", "bad": "Act"}.get(level or "info", level or "FYI")


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def build_summary_payload(dashboard: dict[str, Any]) -> dict[str, Any]:
    """Structured snapshot suitable for health-hub-summary.json."""
    overall = dashboard.get("overall") or {}
    alerts = dashboard.get("alerts") or []
    sections = dashboard.get("sections") or []
    system = dashboard.get("system") or {}
    hw = dashboard.get("hardwarePreview") or {}
    ev = dashboard.get("eventsPreview") or {}

    return {
        "schema": "FAFO.HealthHubSummary/1",
        "generatedAt": _utc_now(),
        "deviceId": diag._device_id(),
        "hostname": system.get("hostname"),
        "overall": overall,
        "system": system,
        "hardware": {
            "headline": hw.get("headline"),
            "matched": hw.get("matched"),
            "identity": hw.get("identity"),
            "problemDevices": hw.get("problemDevices"),
            "problemDeviceNames": hw.get("problemDeviceNames"),
        },
        "events": {
            "windowHours": ev.get("windowHours"),
            "errorCount": ev.get("errorCount"),
            "warningCount": ev.get("warningCount"),
            "level": ev.get("level"),
            "themes": [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "level": t.get("level"),
                    "count": t.get("count"),
                    "plainEnglish": t.get("plainEnglish"),
                    "care": t.get("care"),
                }
                for t in (ev.get("themes") or [])[:12]
            ],
        },
        "alerts": [
            {
                "id": a.get("id"),
                "level": a.get("level"),
                "title": a.get("title"),
                "plainEnglish": a.get("plainEnglish"),
                "whyItMatters": a.get("whyItMatters"),
                "sectionId": a.get("sectionId"),
                "source": a.get("source"),
            }
            for a in alerts
        ],
        "sections": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "level": s.get("level"),
                "headline": s.get("headline"),
                "detail": s.get("detail"),
                "live": s.get("live"),
            }
            for s in sections
        ],
        "hiddenAlerts": dashboard.get("hiddenAlerts") or [],
    }


def render_readable_html(summary: dict[str, Any]) -> str:
    overall = summary.get("overall") or {}
    system = summary.get("system") or {}
    hw = summary.get("hardware") or {}
    identity = hw.get("identity") or {}
    alerts = summary.get("alerts") or []
    sections = summary.get("sections") or []
    themes = (summary.get("events") or {}).get("themes") or []
    gen = summary.get("generatedAt") or _utc_now()
    try:
        gen_local = datetime.fromisoformat(gen.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        gen_local = gen

    def badge(level: str) -> str:
        lv = "error" if level == "bad" else (level or "info")
        return f'<span class="badge { _esc(lv) }">{_esc(_label(lv))}</span>'

    alert_rows = ""
    if alerts:
        for a in alerts:
            alert_rows += (
                f"<tr><td>{badge(a.get('level') or 'info')}</td>"
                f"<td><span class='dev'>{_esc(a.get('title'))}</span></td>"
                f"<td>{_esc(a.get('plainEnglish'))}</td>"
                f"<td>{_esc(a.get('whyItMatters') or '')}</td></tr>"
            )
    else:
        alert_rows = "<tr><td colspan='4'>No yellow or red issues in this snapshot.</td></tr>"

    section_rows = "".join(
        f"<tr><td><span class='dev'>{_esc(s.get('title'))}</span></td>"
        f"<td>{_esc(s.get('headline'))}</td>"
        f"<td>{badge(s.get('level') or 'info')}</td></tr>"
        for s in sections
    )

    theme_rows = "".join(
        f"<tr><td><span class='dev'>{_esc(t.get('title'))}</span></td>"
        f"<td>{_esc(t.get('plainEnglish'))}</td>"
        f"<td>{_esc(t.get('care') or '')}</td>"
        f"<td>{badge(t.get('level') or 'info')} ×{_esc(t.get('count'))}</td></tr>"
        for t in themes
    ) or "<tr><td colspan='4'>No event themes in sample.</td></tr>"

    problem = hw.get("problemDeviceNames") or []
    problem_html = (
        "<ul>" + "".join(f"<li>{_esc(n)}</li>" for n in problem[:12]) + "</ul>"
        if problem
        else "<p class='dim'>None flagged error/degraded at generation time.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PC Health — Auto Plain English</title>
  <link rel="stylesheet" href="../assets/report.css" />
  <style>
    /* Fallback if opened outside viewer assets path */
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #0b0f17; color: #e8eef8; }}
    .wrap {{ max-width: 920px; margin: 0 auto; padding: 28px 18px 56px; }}
    .badge {{ display: inline-block; padding: 2px 9px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; }}
    .badge.ok {{ background: rgba(52,211,153,.14); color: #34d399; }}
    .badge.info {{ background: rgba(96,165,250,.14); color: #60a5fa; }}
    .badge.warn {{ background: rgba(251,191,36,.14); color: #fbbf24; }}
    .badge.error {{ background: rgba(244,63,94,.14); color: #f43f5e; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.93rem; margin: 10px 0 18px; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #1e2a3d; vertical-align: top; }}
    th {{ color: #8b9bb4; font-size: 0.72rem; text-transform: uppercase; }}
    .dev {{ font-weight: 600; }}
    .dim, .meta, .footer-note {{ color: #8b9bb4; font-size: 0.92rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 16px 0; }}
    .stat {{ background: #121a27; border: 1px solid #1e2a3d; border-radius: 12px; padding: 12px; }}
    .stat b {{ display: block; font-size: 0.72rem; color: #8b9bb4; text-transform: uppercase; }}
    .stat span {{ font-weight: 700; font-size: 0.95rem; }}
    .callout {{ border-left: 4px solid #a78bfa; background: #121a27; padding: 12px 14px; border-radius: 0 12px 12px 0; margin: 16px 0; }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>PC Health Summary <small style="font-size:0.55em;color:#8b9bb4">(auto-generated)</small></h1>
  <p class="meta">
    Human-readable snapshot from Home Health Hub · Generated <strong>{_esc(gen_local)}</strong>
    · Host <strong>{_esc(system.get("hostname") or summary.get("deviceId"))}</strong>
  </p>

  <div class="callout">
    {badge(overall.get("level") or "info")}
    <strong style="margin-left:8px">{_esc(overall.get("headline") or "Status")}</strong>
    <p style="margin:8px 0 0">{_esc(overall.get("summary") or "")}</p>
  </div>

  <div class="grid">
    <div class="stat"><b>Board</b><span>{_esc(identity.get("product") or "—")}</span></div>
    <div class="stat"><b>CPU</b><span>{_esc(identity.get("cpu") or "—")}</span></div>
    <div class="stat"><b>GPU</b><span>{_esc((identity.get("gpus") or ["—"])[0] if identity.get("gpus") else "—")}</span></div>
    <div class="stat"><b>BIOS</b><span>{_esc(identity.get("bios") or "—")}</span></div>
    <div class="stat"><b>CPU load</b><span>{_esc(system.get("cpu_percent"))}%</span></div>
    <div class="stat"><b>Memory</b><span>{_esc(system.get("memory_percent"))}%</span></div>
  </div>

  <h2>What needs attention</h2>
  <table>
    <tr><th>Care</th><th>Issue</th><th>Plain English</th><th>Why it matters</th></tr>
    {alert_rows}
  </table>

  <h2>Sections at a glance</h2>
  <table>
    <tr><th>Section</th><th>Summary</th><th>Status</th></tr>
    {section_rows}
  </table>

  <h2>Event log — translated themes</h2>
  <p class="dim">Sampled System/Application errors &amp; warnings, grouped so DCOM clutter is not a panic.</p>
  <table>
    <tr><th>Theme</th><th>What it means</th><th>Care?</th><th>Level</th></tr>
    {theme_rows}
  </table>

  <h2>Problem devices (PnP)</h2>
  {problem_html}

  <div class="callout">
    <strong>Want live tools?</strong>
    Open <strong>Home Health Hub</strong>, <strong>Event Viewer</strong>, <strong>Hardware Board Map</strong>,
    or the full technical dumps in the PC Report Library.
  </div>

  <p class="footer-note">Color key:
    <span class="badge ok">Fine</span>
    <span class="badge info">FYI</span>
    <span class="badge warn">Watch</span>
    <span class="badge error">Act</span>
    · This file is device-local and auto-regenerated; edit curated notes in the toolbox data packs, not this HTML.
  </p>
</div>
</body>
</html>
"""


def write_summary(dashboard: dict[str, Any], toolbox_root: Path | None = None) -> dict[str, Any]:
    """Write JSON + HTML under device Reports\\PC and optionally mirror into viewer reports."""
    layout = diag.ensure_device_layout(toolbox_root)
    pc = Path(layout["pcReportsDir"])
    pc.mkdir(parents=True, exist_ok=True)

    summary = build_summary_payload(dashboard)
    json_path = pc / "health-hub-summary.json"
    html_path = pc / "pc-health-readable-auto.html"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    html_body = render_readable_html(summary)
    html_path.write_text(html_body, encoding="utf-8")

    # Mirror into bundled reports folder for easy file:// open from viewer tree
    viewer_reports = diag.viewer_dir(toolbox_root) / "reports"
    mirrored = []
    try:
        viewer_reports.mkdir(parents=True, exist_ok=True)
        mirror_html = viewer_reports / "pc-health-readable-auto.html"
        mirror_json = viewer_reports / "health-hub-summary.json"
        # Fix CSS path for viewer/reports (assets is ../assets)
        mirror_html.write_text(html_body, encoding="utf-8")
        mirror_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        mirrored = [str(mirror_html), str(mirror_json)]
    except OSError:
        pass

    # Refresh packs so library sees new files
    pack_info = None
    try:
        pack_info = diag.write_viewer_packs(toolbox_root)
        pack_info = {
            "reportCount": pack_info.get("reportCount"),
            "logCount": pack_info.get("logCount"),
        }
    except Exception as e:
        pack_info = {"error": str(e)}

    return {
        "ok": True,
        "generatedAt": summary["generatedAt"],
        "jsonPath": str(json_path),
        "htmlPath": str(html_path),
        "mirrored": mirrored,
        "deviceId": layout["deviceId"],
        "pack": pack_info,
        "overall": summary.get("overall"),
        "alertCount": len(summary.get("alerts") or []),
    }


def generate_now(toolbox_root: Path | None = None) -> dict[str, Any]:
    """Build dashboard and write plain-English reports."""
    import health_ops

    dash = health_ops.get_dashboard()
    return write_summary(dash, toolbox_root)
