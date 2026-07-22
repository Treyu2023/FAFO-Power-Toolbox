"""
PC Report Library / system diagnostics helpers.
Packs device-local reports into catalog.js + logs-data.js for the offline viewer,
and can run Invoke-FAFOSystemDiagnostics.ps1 from the toolbox server.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _toolbox_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _device_id() -> str:
    name = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "LOCAL"
    return re.sub(r"[^\w.\-]+", "-", name).upper()


def _device_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FAFO" / "Devices" / _device_id()


def viewer_dir(toolbox_root: Path | None = None) -> Path:
    root = toolbox_root or _toolbox_root()
    return root / "System Tools" / "PC Reports and Log Viewer"


def pc_reports_dir() -> Path:
    return _device_root() / "Reports" / "PC"


def ensure_device_layout(toolbox_root: Path | None = None) -> dict[str, str]:
    """Create device folders + optional junction for file:// relative paths."""
    root = toolbox_root or _toolbox_root()
    dev = _device_root()
    pc = dev / "Reports" / "PC"
    md = dev / "Reports" / "Markdown"
    logs = dev / "Logs"
    for d in (pc, md, logs, dev / "Backups"):
        d.mkdir(parents=True, exist_ok=True)

    junction = viewer_dir(root) / "device-local"
    try:
        if junction.exists() or junction.is_symlink():
            # leave existing junction/folder
            pass
        else:
            # Create directory junction (Windows)
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(dev)],
                capture_output=True,
                text=True,
                check=False,
            )
    except OSError:
        pass

    return {
        "deviceId": _device_id(),
        "deviceRoot": str(dev),
        "pcReportsDir": str(pc),
        "logsDir": str(logs),
        "viewerDir": str(viewer_dir(root)),
        "junction": str(junction),
        "junctionOk": junction.exists(),
    }


def _kind(ext: str) -> str:
    e = ext.lower()
    if e == ".md":
        return "md"
    if e == ".json":
        return "json"
    if e == ".html":
        return "html"
    return "log"


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", Path(name).stem).strip("-").lower()
    return s or f"log-{uuid.uuid4().hex[:8]}"


def _read_text(path: Path, max_chars: int = 400_000) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        try:
            raw = path.read_text(encoding="cp1252", errors="replace")
        except OSError:
            return ""
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n\n... [truncated for offline pack] ...\n"
    return raw


def _collect_files() -> list[tuple[Path, str, str]]:
    """
    Return list of (path, relative_viewer_file, source_label).
    Priority: device Reports\\PC, device Logs, device Markdown, legacy viewer reports\\.
    """
    out: list[tuple[Path, str, str]] = []
    seen: set[str] = set()

    def add(path: Path, rel: str, label: str) -> None:
        key = path.resolve().as_posix().lower() if path.exists() else rel.lower()
        if key in seen:
            return
        if not path.is_file():
            return
        if path.suffix.lower() not in {".txt", ".md", ".json", ".html", ".log"}:
            return
        seen.add(key)
        out.append((path, rel.replace("\\", "/"), label))

    dev = _device_root()
    pc = dev / "Reports" / "PC"
    logs = dev / "Logs"
    md = dev / "Reports" / "Markdown"

    prefer = [
        "system-status-latest.html",
        "system_status_latest.md",
        "system_status_latest.txt",
        "system_snapshot_latest.json",
        "bios_system_raw.json",
        "bios-firmware-report.html",
        "pc-health-report.html",
        "pc-anomaly-report.html",
    ]

    if pc.is_dir():
        files = list(pc.iterdir())
        ordered: list[Path] = []
        for n in prefer:
            for f in files:
                if f.name.lower() == n.lower():
                    ordered.append(f)
        rest = sorted(
            [f for f in files if f not in ordered],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:40]
        for f in ordered + rest:
            add(f, f"device-local/Reports/PC/{f.name}", "device-pc")

    if logs.is_dir():
        for f in sorted(logs.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            add(f, f"device-local/Logs/{f.name}", "device-logs")

    if md.is_dir():
        for f in sorted(md.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:15]:
            add(f, f"device-local/Reports/Markdown/{f.name}", "device-md")

    # Legacy / repo sample reports so the library is never blank if files exist in-tree
    legacy = viewer_dir() / "reports"
    if legacy.is_dir():
        for f in sorted(legacy.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            add(f, f"reports/{f.name}", "repo-reports")

    return out


def _title_for(path: Path, device_id: str, source: str) -> str:
    n = path.name.lower()
    base = path.stem
    if "system-status" in n or "system_status" in n:
        return f"System Status — {device_id}"
    if "bios" in n:
        return f"BIOS / firmware — {device_id}"
    if "anomaly" in n:
        return f"PC Anomaly Report — {device_id}"
    if "health" in n:
        return f"PC Health — {path.stem}"
    if "usb" in n:
        return f"USB / Power log — {base}"
    if source == "repo-reports":
        return f"{base} (bundled)"
    return f"{base} — {device_id}"


def build_catalog_and_logs(toolbox_root: Path | None = None) -> dict[str, Any]:
    """Build catalog + log pack structures (does not write files)."""
    root = toolbox_root or _toolbox_root()
    ensure_device_layout(root)
    device_id = _device_id()
    device_root = str(_device_root())
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    reports: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []

    for path, rel, source in _collect_files():
        raw = _read_text(path)
        sid = _slug(path.name)
        # disambiguate repo vs device
        if source == "repo-reports":
            sid = f"repo-{sid}"
        kind = _kind(path.suffix)
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        title = _title_for(path, device_id, source)
        desc = f"{source} · {mtime.strftime('%Y-%m-%d %H:%M')}"

        logs.append({
            "id": sid,
            "title": title,
            "file": rel,
            "kind": kind,
            "desc": desc,
            "bytes": path.stat().st_size,
            "content": raw,
            "device": device_id,
            "source": source,
        })

        # Report cards: prefer HTML; also surface important non-html as cards that open as text via log view
        if path.suffix.lower() == ".html" or source in ("device-pc", "repo-reports"):
            sev = "info"
            low = raw.lower()
            if "banner bad" in low or "attention needed" in low or "kernel-power" in low:
                sev = "warn"
            if 'class="banner ok"' in low or "system healthy" in low:
                sev = "ok"
            cat = "Diagnostics"
            if "usb" in path.name.lower() or "fix" in path.name.lower():
                cat = "Fixes"
            if "bios" in path.name.lower():
                cat = "Firmware"
            if source == "repo-reports":
                cat = "Bundled"
            reports.append({
                "id": f"rpt-{sid}",
                "title": title,
                "summary": (
                    f"Local to {device_id}."
                    if source != "repo-reports"
                    else "Report file in the toolbox reports folder (may predate device-local packs)."
                ),
                "category": cat,
                "severity": sev,
                "tags": [device_id if source != "repo-reports" else "Bundled", cat, path.suffix.lstrip(".")],
                "date": mtime.strftime("%Y-%m-%d"),
                "icon": "heart" if "health" in path.name.lower() else ("bolt" if cat == "Fixes" else "search"),
                "file": rel,
                "highlights": [
                    {"label": "Source", "value": source},
                    {"label": "Updated", "value": mtime.strftime("%H:%M")},
                ],
            })

    if not reports:
        reports.append({
            "id": "no-local-reports",
            "title": f"No reports yet on {device_id}",
            "summary": "Click “Run diagnostics” to collect system status for this PC.",
            "category": "Diagnostics",
            "severity": "info",
            "tags": [device_id, "Empty"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "icon": "search",
            "file": "",
            "highlights": [
                {"label": "Device", "value": device_id},
                {"label": "Action", "value": "Run diagnostics"},
            ],
        })

    catalog = {
        "generatedAt": generated_at,
        "machine": device_id,
        "deviceId": device_id,
        "deviceRoot": device_root,
        "toolboxPath": "System Tools\\PC Reports and Log Viewer",
        "scope": "device-local",
        "note": "Reports are for this PC. Use Run diagnostics / Refresh pack — do not commit catalog.js.",
        "reports": reports,
        "logCount": len(logs),
    }
    return {"catalog": catalog, "logs": logs}


def write_viewer_packs(toolbox_root: Path | None = None) -> dict[str, Any]:
    """Write catalog.js + logs-data.js next to the viewer."""
    root = toolbox_root or _toolbox_root()
    built = build_catalog_and_logs(root)
    vdir = viewer_dir(root)
    catalog = built["catalog"]
    logs = built["logs"]
    device_id = catalog["deviceId"]

    catalog_js = (
        f"/* Auto-generated for THIS PC only ({device_id}). Do not commit.\\n"
        f"   Refresh: viewer buttons or POST /api/diagnostics/pack\\n*/\\n"
        f"window.REPORT_CATALOG = {json.dumps(catalog, indent=2)};\\n"
    )
    # Fix the accidental double-escape - use real newlines
    catalog_js = (
        f"/* Auto-generated for THIS PC only ({device_id}). Do not commit.\n"
        f"   Refresh: viewer buttons or POST /api/diagnostics/pack\n*/\n"
        f"window.REPORT_CATALOG = {json.dumps(catalog, indent=2)};\n"
    )
    logs_js = (
        f"/* Auto-generated offline Log Viewer pack for {device_id} only. Do not commit.\n*/\n"
        f"window.LOG_DATA = {json.dumps(logs, indent=2)};\n"
    )

    cat_path = vdir / "catalog.js"
    log_path = vdir / "logs-data.js"
    cat_path.write_text(catalog_js, encoding="utf-8")
    log_path.write_text(logs_js, encoding="utf-8")

    return {
        "ok": True,
        "deviceId": device_id,
        "deviceRoot": catalog["deviceRoot"],
        "catalogPath": str(cat_path),
        "logsPath": str(log_path),
        "reportCount": len(catalog.get("reports") or []),
        "logCount": len(logs),
        "catalog": catalog,
        # omit full log bodies from API response size — frontend reloads scripts
    }


def status(toolbox_root: Path | None = None) -> dict[str, Any]:
    root = toolbox_root or _toolbox_root()
    layout = ensure_device_layout(root)
    vdir = viewer_dir(root)
    cat = vdir / "catalog.js"
    logs = vdir / "logs-data.js"
    pc = Path(layout["pcReportsDir"])
    pc_files = list(pc.glob("*")) if pc.is_dir() else []
    legacy = vdir / "reports"
    legacy_files = list(legacy.glob("*")) if legacy.is_dir() else []
    return {
        **layout,
        "hasCatalogJs": cat.is_file(),
        "hasLogsJs": logs.is_file(),
        "catalogBytes": cat.stat().st_size if cat.is_file() else 0,
        "logsBytes": logs.stat().st_size if logs.is_file() else 0,
        "pcReportFileCount": len([f for f in pc_files if f.is_file()]),
        "legacyReportFileCount": len([f for f in legacy_files if f.is_file()]),
        "catalogMtime": datetime.fromtimestamp(cat.stat().st_mtime).isoformat(timespec="seconds") if cat.is_file() else None,
    }


def run_system_diagnostics(
    toolbox_root: Path | None = None,
    open_viewer: bool = False,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    """Run Scripts\\Invoke-FAFOSystemDiagnostics.ps1 then pack viewer."""
    root = toolbox_root or _toolbox_root()
    script = root / "Scripts" / "Invoke-FAFOSystemDiagnostics.ps1"
    if not script.is_file():
        raise FileNotFoundError(f"Missing {script}")

    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script),
        "-ToolboxRoot", str(root),
    ]
    if open_viewer:
        args.append("-OpenViewer")

    try:
        proc = subprocess.run(
            args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Diagnostics timed out after {timeout_sec}s") from e

    pack = write_viewer_packs(root)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-8000:],
        "stderr": (proc.stderr or "")[-4000:],
        "pack": {
            "reportCount": pack["reportCount"],
            "logCount": pack["logCount"],
            "deviceId": pack["deviceId"],
            "deviceRoot": pack["deviceRoot"],
        },
    }
