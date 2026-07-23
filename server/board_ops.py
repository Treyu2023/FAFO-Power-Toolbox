"""
Hardware identity, board rear-I/O packs, component intel, and offline playbooks.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

IS_WINDOWS = platform.system() == "Windows"
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
_DATA = Path(__file__).resolve().parent / "data"
_BOARDS = _DATA / "boards"
_INTEL_PATH = _DATA / "component-intel.json"
_PLAYBOOKS_PATH = _DATA / "playbooks" / "index.json"

_ID_CACHE_LOCK = threading.Lock()
_ID_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_ID_CACHE_TTL = 60.0


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _run_ps(script: str, timeout: float = 30) -> tuple[str, str, int]:
    try:
        p = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_FLAGS,
            errors="replace",
        )
        return p.stdout or "", p.stderr or "", p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 124
    except OSError as e:
        return "", str(e), 1


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def detect_identity(force: bool = False) -> dict[str, Any]:
    """WMI/CIM snapshot of board, BIOS, CPU, GPU, disks, net, problem devices."""
    now = time.time()
    if not force:
        with _ID_CACHE_LOCK:
            if _ID_CACHE["payload"] and (now - _ID_CACHE["at"]) < _ID_CACHE_TTL:
                return _ID_CACHE["payload"]

    if not IS_WINDOWS:
        return {
            "timestamp": _utc_now(),
            "supported": False,
            "board": {},
            "bios": {},
            "cpu": {},
            "gpus": [],
            "disks": [],
            "net": [],
            "devices": [],
        }

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$bb = Get-CimInstance Win32_BaseBoard
$bios = Get-CimInstance Win32_BIOS
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  [pscustomobject]@{ name = $_.Name; driver = $_.DriverVersion; status = $_.Status }
})
$disks = @()
try {
  $disks = @(Get-PhysicalDisk | ForEach-Object {
    [pscustomobject]@{ name = $_.FriendlyName; media = [string]$_.MediaType; bus = [string]$_.BusType; health = [string]$_.HealthStatus; sizeGB = [math]::Round($_.Size/1GB,1) }
  })
} catch {}
$nets = @(Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -and $_.NetEnabled -ne $null } | Select-Object -First 12 | ForEach-Object {
  [pscustomobject]@{ name = $_.Name; mac = $_.MACAddress; netEnabled = [bool]$_.NetEnabled; manufacturer = $_.Manufacturer }
})
$devs = @()
try {
  $devs = @(Get-PnpDevice -PresentOnly -Status ERROR,DEGRADED,UNKNOWN -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object {
    [pscustomobject]@{ name = $_.FriendlyName; status = $_.Status; class = $_.Class; instanceId = $_.InstanceId }
  })
} catch {}
[pscustomobject]@{
  computer = $cs.Name
  manufacturer = $cs.Manufacturer
  model = $cs.Model
  board = [pscustomobject]@{ manufacturer = $bb.Manufacturer; product = $bb.Product; version = $bb.Version }
  bios = [pscustomobject]@{ manufacturer = $bios.Manufacturer; version = $bios.SMBIOSBIOSVersion; releaseDate = [string]$bios.ReleaseDate }
  cpu = [pscustomobject]@{ name = ($cpu.Name).Trim(); cores = $cpu.NumberOfCores; logical = $cpu.NumberOfLogicalProcessors }
  gpus = $gpus
  disks = $disks
  net = $nets
  devices = $devs
} | ConvertTo-Json -Compress -Depth 5
"""
    out, err, code = _run_ps(script, timeout=40)
    if not out.strip():
        return {
            "timestamp": _utc_now(),
            "supported": True,
            "error": err or "empty identity response",
            "board": {},
            "bios": {},
            "cpu": {},
            "gpus": [],
            "disks": [],
            "net": [],
            "devices": [],
        }
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {
            "timestamp": _utc_now(),
            "supported": True,
            "error": "json parse failed",
            "raw": out[:500],
            "board": {},
            "bios": {},
            "cpu": {},
            "gpus": [],
            "disks": [],
            "net": [],
            "devices": [],
        }

    def as_list(x: Any) -> list:
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    payload = {
        "timestamp": _utc_now(),
        "supported": True,
        "computer": data.get("computer"),
        "systemManufacturer": data.get("manufacturer"),
        "systemModel": data.get("model"),
        "board": data.get("board") or {},
        "bios": data.get("bios") or {},
        "cpu": data.get("cpu") or {},
        "gpus": as_list(data.get("gpus")),
        "disks": as_list(data.get("disks")),
        "net": as_list(data.get("net")),
        "devices": as_list(data.get("devices")),
    }
    with _ID_CACHE_LOCK:
        _ID_CACHE["at"] = time.time()
        _ID_CACHE["payload"] = payload
    return payload


def _list_board_packs() -> list[dict[str, Any]]:
    packs = []
    if not _BOARDS.is_dir():
        return packs
    for d in sorted(_BOARDS.iterdir()):
        meta = d / "board.json"
        if meta.is_file():
            try:
                packs.append(_read_json(meta))
            except (OSError, json.JSONDecodeError):
                continue
    return packs


def _match_board(identity: dict[str, Any]) -> dict[str, Any] | None:
    product = str((identity.get("board") or {}).get("product") or "")
    mfr = str((identity.get("board") or {}).get("manufacturer") or "")
    prod_u = product.upper()
    mfr_u = mfr.upper()
    for pack in _list_board_packs():
        match = pack.get("match") or {}
        prod_ok = any(p.upper() in prod_u for p in (match.get("productIncludes") or []))
        mfr_need = match.get("manufacturerIncludes") or []
        mfr_ok = (not mfr_need) or any(m.upper() in mfr_u for m in mfr_need)
        if prod_ok and mfr_ok:
            return pack
    return None


def _load_ports(board_id: str) -> dict[str, Any]:
    path = _BOARDS / board_id / "ports.json"
    if path.is_file():
        try:
            return _read_json(path)
        except (OSError, json.JSONDecodeError):
            pass
    return {"boardId": board_id, "ports": []}


def _svg_url(board_id: str) -> str | None:
    path = _BOARDS / board_id / "rear-io.svg"
    if path.is_file():
        # Served via API so file:// pages can still fetch through server
        return f"/api/hardware/board/{board_id}/rear-io.svg"
    return None


def get_board_bundle() -> dict[str, Any]:
    identity = detect_identity()
    pack = _match_board(identity)
    if not pack:
        return {
            "timestamp": _utc_now(),
            "matched": False,
            "identity": identity,
            "board": None,
            "ports": [],
            "svgUrl": None,
            "notices": [],
            "links": {},
            "note": "No curated rear-I/O pack for this motherboard yet. Identity still detected.",
        }

    bid = pack["id"]
    ports_doc = _load_ports(bid)
    return {
        "timestamp": _utc_now(),
        "matched": True,
        "identity": identity,
        "board": {
            "id": bid,
            "displayName": pack.get("displayName"),
            "manufacturer": pack.get("manufacturer"),
            "chipset": pack.get("chipset"),
            "formFactor": pack.get("formFactor"),
            "notes": pack.get("notes") or [],
        },
        "ports": ports_doc.get("ports") or [],
        "svgUrl": _svg_url(bid),
        "notices": pack.get("notices") or [],
        "links": pack.get("links") or {},
        "detectedProduct": (identity.get("board") or {}).get("product"),
        "detectedBios": (identity.get("bios") or {}).get("version"),
    }


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def match_component_intel(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or detect_identity()
    try:
        catalog = _read_json(_INTEL_PATH)
    except (OSError, json.JSONDecodeError):
        catalog = {"components": []}

    cpu = _blob((identity.get("cpu") or {}).get("name"))
    gpus = _blob(*[g.get("name") for g in (identity.get("gpus") or [])])
    disks = _blob(*[d.get("name") for d in (identity.get("disks") or [])])
    nets = _blob(*[n.get("name") for n in (identity.get("net") or [])])
    devs = _blob(*[d.get("name") for d in (identity.get("devices") or [])])
    # Also search all names loosely
    all_names = _blob(cpu, gpus, disks, nets, devs)

    hits = []
    for c in catalog.get("components") or []:
        m = c.get("match") or {}
        ok = False
        for key, field in (
            ("cpuIncludes", cpu),
            ("gpuIncludes", gpus),
            ("diskIncludes", disks),
            ("netIncludes", nets),
            ("deviceIncludes", devs + " " + all_names),
        ):
            needles = m.get(key) or []
            if any(n.lower() in field for n in needles):
                ok = True
                break
        if ok:
            hits.append({
                "id": c.get("id"),
                "level": c.get("level") or "info",
                "title": c.get("title"),
                "plainEnglish": c.get("plainEnglish"),
                "category": c.get("category"),
                "playbookId": c.get("playbookId"),
                "links": c.get("links") or [],
            })

    # Board notices as intel too
    pack = _match_board(identity)
    board_notices = []
    if pack:
        for n in pack.get("notices") or []:
            board_notices.append({
                "id": n.get("id"),
                "level": n.get("level") or "info",
                "title": n.get("title"),
                "plainEnglish": n.get("plainEnglish"),
                "category": "board",
                "playbookId": n.get("playbookId"),
                "links": [{"label": "Vendor link", "href": n["href"]}] if n.get("href") else [],
            })

    return {
        "timestamp": _utc_now(),
        "identity": {
            "board": (identity.get("board") or {}).get("product"),
            "cpu": (identity.get("cpu") or {}).get("name"),
            "gpus": [g.get("name") for g in (identity.get("gpus") or [])],
        },
        "items": hits + board_notices,
    }


def list_playbooks() -> dict[str, Any]:
    try:
        data = _read_json(_PLAYBOOKS_PATH)
    except (OSError, json.JSONDecodeError):
        data = {"playbooks": []}
    return {
        "timestamp": _utc_now(),
        "playbooks": [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "level": p.get("level"),
                "summary": p.get("summary"),
            }
            for p in (data.get("playbooks") or [])
        ],
    }


def get_playbook(playbook_id: str) -> dict[str, Any] | None:
    try:
        data = _read_json(_PLAYBOOKS_PATH)
    except (OSError, json.JSONDecodeError):
        return None
    for p in data.get("playbooks") or []:
        if p.get("id") == playbook_id:
            return p
    return None


def assist(
    *,
    playbook_id: str | None = None,
    theme_id: str | None = None,
    alert_id: str | None = None,
    process_name: str | None = None,
) -> dict[str, Any]:
    """
    Offline-first assist: playbook steps + guided web search query.
    Optional AI can be layered later without changing this contract.
    """
    identity = detect_identity()
    board_name = (identity.get("board") or {}).get("product") or "PC"
    cpu = (identity.get("cpu") or {}).get("name") or ""
    gpu = ""
    gpus = identity.get("gpus") or []
    if gpus:
        gpu = gpus[0].get("name") or ""
    disk = ""
    disks = identity.get("disks") or []
    if disks:
        # Prefer non-NVMe-looking portable names later; first disk for template
        disk = disks[0].get("name") or ""

    # Map event themes / alerts to playbooks
    theme_map = {
        "disk-retries": "disk-retries",
        "ethernet-link": "ethernet-link-flap",
        "usb-errors": "usb-bt-conflict",
        "gpu-watchdog": "gpu-watchdog",
        "event-theme-disk-retries": "disk-retries",
        "event-theme-ethernet-link": "ethernet-link-flap",
        "event-theme-usb-errors": "usb-bt-conflict",
        "event-theme-gpu-watchdog": "gpu-watchdog",
        "cpu-high": "high-cpu",
        "cpu-critical": "high-cpu",
        "mem-high": "high-cpu",
        "security-quarantine": None,
    }
    # disk low alerts
    if alert_id and str(alert_id).startswith("disk-"):
        playbook_id = playbook_id or "low-disk"

    if not playbook_id and theme_id:
        playbook_id = theme_map.get(theme_id)
    if not playbook_id and alert_id:
        playbook_id = theme_map.get(alert_id)
        if not playbook_id and str(alert_id).startswith("event-theme-"):
            playbook_id = theme_map.get(str(alert_id).replace("event-theme-", ""))

    pb = get_playbook(playbook_id) if playbook_id else None

    ctx = {
        "board": board_name,
        "cpu": cpu,
        "gpu": gpu,
        "disk": disk,
        "process": process_name or "",
    }

    search_q = ""
    if pb and pb.get("searchQueryTemplate"):
        try:
            search_q = pb["searchQueryTemplate"].format(**{k: v for k, v in ctx.items()})
        except (KeyError, ValueError):
            search_q = f"{board_name} {pb.get('title', '')} Windows 11"
    elif theme_id:
        search_q = f"{board_name} {theme_id} Windows 11"
    else:
        search_q = f"{board_name} troubleshooting Windows 11"

    search_url = "https://www.bing.com/search?q=" + quote_plus(search_q)

    # Intel hits for context cards
    intel = match_component_intel(identity)

    return {
        "timestamp": _utc_now(),
        "playbookId": playbook_id,
        "playbook": pb,
        "context": ctx,
        "searchQuery": search_q,
        "searchUrl": search_url,
        "componentIntel": intel.get("items") or [],
        "ai": {
            "available": False,
            "note": "Offline playbooks + guided search first. Optional free AI explain can plug in later without changing this API.",
        },
        "disclaimer": "Curated guidance for this toolbox — verify vendor notices and critical fixes on official manufacturer pages.",
    }


def hub_hardware_preview() -> dict[str, Any]:
    """Compact block for health dashboard firmware/board section."""
    try:
        bundle = get_board_bundle()
        intel = match_component_intel(bundle.get("identity") or detect_identity())
    except Exception as e:
        return {
            "matched": False,
            "level": "info",
            "headline": "Hardware map unavailable",
            "detail": str(e),
            "notices": [],
            "problemDevices": 0,
        }

    identity = bundle.get("identity") or {}
    board = bundle.get("board")
    product = (identity.get("board") or {}).get("product") or "Unknown board"
    bios = (identity.get("bios") or {}).get("version") or "?"
    problem = len(identity.get("devices") or [])

    notices = []
    for n in (bundle.get("notices") or []):
        if n.get("level") in ("warn", "error"):
            notices.append(n)
    for item in intel.get("items") or []:
        if item.get("level") in ("warn", "error"):
            notices.append(item)

    level = "ok"
    if problem:
        level = "warn"
    if any((n.get("level") == "error") for n in notices):
        level = "error"
    elif notices:
        level = "warn"
    elif not bundle.get("matched"):
        level = "info"

    if board:
        headline = f"{board.get('displayName')} · BIOS {bios}"
    else:
        headline = f"{product} · BIOS {bios} (no rear-I/O pack yet)"

    detail_bits = []
    if problem:
        detail_bits.append(f"{problem} device(s) in error/degraded state")
    if notices:
        detail_bits.append(f"{len(notices)} curated notice(s)")
    if not detail_bits:
        detail_bits.append("Open Hardware Map for rear I/O, vendor links, and playbooks.")

    return {
        "matched": bool(bundle.get("matched")),
        "level": level,
        "headline": headline,
        "detail": " · ".join(detail_bits),
        "boardId": (board or {}).get("id"),
        "svgUrl": bundle.get("svgUrl"),
        "links": bundle.get("links") or {},
        "notices": notices[:6],
        "problemDevices": problem,
        "problemDeviceNames": [
            d.get("name") for d in (identity.get("devices") or [])[:8] if d.get("name")
        ],
        "identity": {
            "product": product,
            "bios": bios,
            "cpu": (identity.get("cpu") or {}).get("name"),
            "gpus": [g.get("name") for g in (identity.get("gpus") or [])][:3],
        },
    }


def get_rear_io_svg(board_id: str) -> tuple[bytes, str] | None:
    """Return (bytes, content_type) for a board SVG."""
    # sanitize id
    if not re.match(r"^[a-z0-9\-]+$", board_id or ""):
        return None
    path = _BOARDS / board_id / "rear-io.svg"
    if not path.is_file():
        return None
    return path.read_bytes(), "image/svg+xml"
