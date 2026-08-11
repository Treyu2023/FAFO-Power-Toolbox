"""Hosts file & DNS blocklist manager."""
from __future__ import annotations

import platform
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IS_WINDOWS = platform.system() == "Windows"
HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts") if IS_WINDOWS else Path("/etc/hosts")
MARKER_START = "# --- AI TOOLBOX BLOCKLIST START ---"
MARKER_END = "# --- AI TOOLBOX BLOCKLIST END ---"

BLOCKLIST_FEEDS = [
    {
        "id": "ads",
        "name": "Ads & Trackers",
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        "description": "Steven Black unified hosts (ads + malware)",
    },
    {
        "id": "fakenews",
        "name": "Fake News",
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews/hosts",
        "description": "Steven Black fakenews alternate",
    },
    {
        "id": "gambling",
        "name": "Gambling",
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts",
        "description": "Steven Black gambling alternate",
    },
]


def _download(url: str, timeout: float = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Toolbox-Hosts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _parse_hosts(text: str) -> list[dict[str, str]]:
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            entries.append({"ip": parts[0], "host": parts[1], "raw": line})
    return entries


def read_hosts() -> dict[str, Any]:
    if not HOSTS_PATH.exists():
        return {"path": str(HOSTS_PATH), "exists": False, "entries": [], "raw": ""}
    raw = HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
    custom = []
    blocklist = []
    in_block = False
    for line in raw.splitlines():
        if MARKER_START in line:
            in_block = True
            continue
        if MARKER_END in line:
            in_block = False
            continue
        if in_block:
            if line.strip() and not line.strip().startswith("#"):
                blocklist.append(line.strip())
        elif line.strip() and not line.strip().startswith("#"):
            custom.append(line.strip())
    return {
        "path": str(HOSTS_PATH),
        "exists": True,
        "entries": _parse_hosts(raw),
        "custom_lines": custom,
        "blocklist_lines": blocklist,
        "blocklist_count": len(blocklist),
        "raw": raw,
    }


def fetch_blocklist(feed_id: str = "ads") -> dict[str, Any]:
    feed = next((f for f in BLOCKLIST_FEEDS if f["id"] == feed_id), BLOCKLIST_FEEDS[0])
    text = _download(feed["url"])
    domains = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            host = parts[1]
            if host not in ("localhost", "localhost.localdomain"):
                domains.append(host)
    domains = sorted(set(domains))
    return {
        "feed": feed,
        "domain_count": len(domains),
        "domains": domains,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_blocklist(feed_id: str = "ads", enabled: bool = True) -> dict[str, Any]:
    data = read_hosts()
    raw_lines = []
    if HOSTS_PATH.exists():
        for line in HOSTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if MARKER_START in line:
                break
            if line.strip():
                raw_lines.append(line)

    if enabled:
        bl = fetch_blocklist(feed_id)
        block_section = [MARKER_START, f"# Feed: {bl['feed']['name']} — {bl['fetched_at']}", f"# Domains: {bl['domain_count']}"]
        block_section += [f"0.0.0.0 {d}" for d in bl["domains"]]
        block_section.append(MARKER_END)
        new_content = "\n".join(raw_lines) + "\n\n" + "\n".join(block_section) + "\n"
    else:
        new_content = "\n".join(raw_lines) + "\n"

    HOSTS_PATH.write_text(new_content, encoding="utf-8")
    return {"ok": True, "enabled": enabled, "feed_id": feed_id, "blocklist_count": len(_parse_hosts(new_content))}


def add_custom_block(host: str, ip: str = "0.0.0.0") -> dict[str, Any]:
    host = host.strip().lower()
    if not host or " " in host:
        raise ValueError("Invalid hostname")
    data = read_hosts()
    line = f"{ip} {host}"
    if line in data.get("custom_lines", []):
        return {"ok": True, "already_exists": True}
    raw = HOSTS_PATH.read_text(encoding="utf-8", errors="replace") if HOSTS_PATH.exists() else ""
    if MARKER_START in raw:
        raw = raw.split(MARKER_START)[0].rstrip() + "\n" + line + "\n\n" + MARKER_START + raw.split(MARKER_START, 1)[1]
    else:
        raw = raw.rstrip() + "\n" + line + "\n"
    HOSTS_PATH.write_text(raw, encoding="utf-8")
    return {"ok": True, "added": line}


def remove_custom_block(host: str) -> dict[str, Any]:
    host = host.strip().lower()
    raw = HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if host not in ln.lower() or ln.strip().startswith("#")]
    HOSTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "removed": host}


def _is_process_elevated() -> bool:
    """True when the toolbox server process is running elevated (can write hosts)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def get_status() -> dict[str, Any]:
    data = read_hosts()
    enabled = MARKER_START in (data.get("raw") or "")
    elevated = _is_process_elevated()
    return {
        "hosts_path": str(HOSTS_PATH),
        "blocklist_enabled": enabled,
        "blocklist_count": data.get("blocklist_count", 0),
        "custom_count": len(data.get("custom_lines", [])),
        "feeds": BLOCKLIST_FEEDS,
        "is_elevated": elevated,
        "can_write_hosts": elevated,
        "elevation_hint": (
            None
            if elevated
            else "Restart the toolbox server as Administrator to enable / disable blocklists or add custom hosts entries."
        ),
    }