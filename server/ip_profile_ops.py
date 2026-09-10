"""
IP Profile Switcher — save and apply multi-setup IPv4 configs (Windows netsh).
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

IS_WINDOWS = platform.system() == "Windows"
ACTIVE_TOKEN = "__ACTIVE_ADAPTER__"
# Portable with the toolbox: <toolbox root>/data/ip_profiles.json
# (copy whole Toolbox folder to another PC and keep your IP setups)
TOOLBOX_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = TOOLBOX_ROOT / "data"
PROFILES_PATH = DATA_DIR / "ip_profiles.json"
# Legacy path (migrate once if present)
_LEGACY_PATH = Path(__file__).resolve().parent / "data" / "ip_profiles.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], timeout: float = 30) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": (p.stdout or "").strip(),
            "stderr": (p.stderr or "").strip(),
            "ok": p.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "returncode": -1, "stdout": "", "stderr": "timeout", "ok": False}
    except Exception as e:
        return {"cmd": cmd, "returncode": -1, "stdout": "", "stderr": str(e), "ok": False}


def _netmask_to_prefix(mask: str | None) -> int | None:
    if not mask:
        return None
    try:
        parts = [int(x) for x in mask.split(".")]
        if len(parts) != 4:
            return None
        bits = "".join(f"{p:08b}" for p in parts)
        if "01" in bits:
            return None
        return bits.count("1")
    except Exception:
        return None


def _prefix_to_netmask(prefix: int | str | None) -> str:
    try:
        p = int(prefix)
    except (TypeError, ValueError):
        p = 24
    p = max(0, min(32, p))
    bits = ("1" * p) + ("0" * (32 - p))
    octets = [int(bits[i : i + 8], 2) for i in range(0, 32, 8)]
    return ".".join(str(o) for o in octets)


def _load_store() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # One-time migrate from old server/data location
    if not PROFILES_PATH.exists() and _LEGACY_PATH.exists():
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            PROFILES_PATH.write_text(_LEGACY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    if not PROFILES_PATH.exists():
        store = {
            "version": 1,
            "profiles": [],
            "updated_at": _utc_now(),
            "portable_note": "Copy this file with the Toolbox folder to transfer IP setups to another PC.",
        }
        _save_store(store)
        return store
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "profiles": [], "updated_at": _utc_now()}


def _save_store(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = _utc_now()
    store["portable_note"] = (
        "Portable IP profiles for AI HTML Toolbox. "
        "Path: data/ip_profiles.json relative to the Toolbox root. "
        "Copy this file (or the whole Toolbox folder) to another PC to keep your setups."
    )
    store["toolbox_relative_path"] = "data/ip_profiles.json"
    PROFILES_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def export_profiles_blob() -> dict[str, Any]:
    """Full portable JSON (for download / transfer)."""
    store = _load_store()
    return {
        "format": "aitoolbox-ip-profiles",
        "version": 1,
        "exported_at": _utc_now(),
        "profiles": store.get("profiles", []),
        "toolbox_relative_path": "data/ip_profiles.json",
        "instructions": (
            "Place this file at <AI HTML TOOLBOX>/data/ip_profiles.json on the target PC, "
            "or use Import in IP Profile Switcher."
        ),
    }


def import_profiles_blob(blob: dict[str, Any], merge: bool = True) -> dict[str, Any]:
    """Import profiles from portable JSON. merge=True keeps existing ids unless overwritten."""
    incoming = blob.get("profiles")
    if not isinstance(incoming, list):
        raise ValueError("Invalid file: missing profiles array")
    store = _load_store()
    if not merge:
        store["profiles"] = []
    by_id = {p.get("id"): p for p in store.get("profiles", []) if p.get("id")}
    added = 0
    updated = 0
    for p in incoming:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        pid = p.get("id") or str(uuid.uuid4())
        p = dict(p)
        p["id"] = pid
        p["updated_at"] = _utc_now()
        if pid in by_id:
            updated += 1
        else:
            added += 1
            p.setdefault("created_at", _utc_now())
        by_id[pid] = p
    store["profiles"] = list(by_id.values())
    _save_store(store)
    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "total": len(store["profiles"]),
        "path": str(PROFILES_PATH),
    }


def list_adapters() -> list[dict[str, Any]]:
    """Physical/logical adapters with current IPv4 summary."""
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    out: list[dict[str, Any]] = []
    for name, addr_list in addrs.items():
        # Skip pure loopback / tunnel-ish noise for UI defaults
        lower = name.lower()
        if lower.startswith("loopback") or lower == "lo":
            continue
        st = stats.get(name)
        ipv4 = []
        mac = ""
        for a in addr_list:
            if a.family == getattr(psutil, "AF_LINK", object()):
                mac = a.address or mac
            elif a.family == 2:  # AF_INET
                ipv4.append(
                    {
                        "address": a.address,
                        "netmask": a.netmask,
                        "prefix": _netmask_to_prefix(a.netmask),
                        "broadcast": a.broadcast,
                    }
                )
        out.append(
            {
                "name": name,
                "is_up": bool(st and st.isup),
                "speed_mbps": st.speed if st else 0,
                "mac": mac,
                "ipv4": ipv4,
            }
        )
    # Prefer up adapters with IPv4 first
    out.sort(key=lambda x: (not x["is_up"], len(x["ipv4"]) == 0, x["name"].lower()))
    return out


def get_adapter_detail(name: str) -> dict[str, Any]:
    adapters = list_adapters()
    match = next((a for a in adapters if a["name"] == name), None)
    if not match:
        raise ValueError(f"Adapter not found: {name}")
    detail = dict(match)
    detail["gateway"] = None
    detail["dns"] = []
    detail["dhcp"] = None
    if IS_WINDOWS:
        r = _run(["netsh", "interface", "ip", "show", "config", f"name={name}"])
        detail["netsh_raw"] = r.get("stdout", "")
        text = r.get("stdout", "") or ""
        # DHCP enabled: Yes/No
        m = re.search(r"DHCP enabled:\s*(\w+)", text, re.I)
        if m:
            detail["dhcp"] = m.group(1).lower().startswith("y")
        m = re.search(r"Default Gateway:\s*([\d.]+)", text, re.I)
        if m and m.group(1) not in ("0.0.0.0",):
            detail["gateway"] = m.group(1)
        # DNS servers listed after "DNS servers configured through DHCP" or statically
        dns = re.findall(r"(?:DNS servers[^:]*:\s*|^\s{4,})([\d.]+)", text, re.I | re.M)
        # Cleaner parse: lines after "DNS servers"
        dns2 = []
        grab = False
        for line in text.splitlines():
            if re.search(r"DNS servers", line, re.I):
                grab = True
                m = re.search(r"([\d.]+)\s*$", line)
                if m:
                    dns2.append(m.group(1))
                continue
            if grab:
                m = re.match(r"\s+([\d.]+)\s*$", line)
                if m:
                    dns2.append(m.group(1))
                elif line.strip() and not line.startswith(" "):
                    grab = False
        detail["dns"] = dns2 or dns
    return detail


def list_profiles() -> dict[str, Any]:
    store = _load_store()
    return {
        "profiles": store.get("profiles", []),
        "updated_at": store.get("updated_at"),
        "path": str(PROFILES_PATH),
    }


def get_profile(profile_id: str) -> dict[str, Any]:
    store = _load_store()
    for p in store.get("profiles", []):
        if p.get("id") == profile_id:
            return p
    raise ValueError("Profile not found")


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Create or update a profile. Required: name, adapter, mode (dhcp|static)."""
    name = (profile.get("name") or "").strip()
    adapter = (profile.get("adapter") or "").strip()
    mode = (profile.get("mode") or "static").strip().lower()
    if not name:
        raise ValueError("Profile name is required")
    if not adapter:
        raise ValueError("Adapter name is required")
    if mode not in ("static", "dhcp"):
        raise ValueError("mode must be static or dhcp")

    if mode == "static":
        ip = (profile.get("ip") or "").strip()
        if not ip:
            raise ValueError("IP address is required for static mode")
        prefix = profile.get("prefix")
        if prefix is None or prefix == "":
            mask = (profile.get("netmask") or "255.255.255.0").strip()
            prefix = _netmask_to_prefix(mask) or 24
        else:
            prefix = int(prefix)
            mask = (profile.get("netmask") or _prefix_to_netmask(prefix)).strip()
        gateway = (profile.get("gateway") or "").strip() or None
        dns = profile.get("dns") or []
        if isinstance(dns, str):
            dns = [d.strip() for d in re.split(r"[,;\s]+", dns) if d.strip()]
        dns = [d for d in dns if d]
    else:
        ip = ""
        prefix = None
        mask = ""
        gateway = None
        dns = []

    store = _load_store()
    profiles = store.get("profiles", [])
    pid = (profile.get("id") or "").strip() or str(uuid.uuid4())
    now = _utc_now()
    existing = next((p for p in profiles if p.get("id") == pid), None)

    row = {
        "id": pid,
        "name": name,
        "color": (profile.get("color") or "#00f3ff").strip(),
        "adapter": adapter,
        "mode": mode,
        "ip": ip,
        "prefix": prefix,
        "netmask": mask if mode == "static" else "",
        "gateway": gateway,
        "dns": dns,
        "probe": (profile.get("probe") or gateway or "").strip() if isinstance(gateway, str) else (profile.get("probe") or ""),
        "hunt": bool(profile.get("hunt", True)),
        "useActiveOnApply": bool(profile.get("useActiveOnApply") or adapter == "__ACTIVE_ADAPTER__"),
        "notes": (profile.get("notes") or "").strip(),
        "updated_at": now,
        "created_at": existing.get("created_at") if existing else now,
    }

    if existing:
        profiles = [row if p.get("id") == pid else p for p in profiles]
    else:
        profiles.append(row)

    store["profiles"] = profiles
    _save_store(store)
    return row


def delete_profile(profile_id: str) -> dict[str, Any]:
    store = _load_store()
    before = len(store.get("profiles", []))
    store["profiles"] = [p for p in store.get("profiles", []) if p.get("id") != profile_id]
    if len(store["profiles"]) == before:
        raise ValueError("Profile not found")
    _save_store(store)
    return {"ok": True, "id": profile_id}


def capture_current(adapter: str, name: str | None = None, color: str | None = None) -> dict[str, Any]:
    """Snapshot current adapter config into a new (unsaved until save) profile dict and persist it."""
    detail = get_adapter_detail(adapter)
    ipv4 = (detail.get("ipv4") or [{}])[0]
    mode = "dhcp" if detail.get("dhcp") else "static"
    # If DHCP flag unknown but has IP, treat as static-capable snapshot
    if detail.get("dhcp") is None and ipv4.get("address"):
        mode = "static"
    label = name or f"{adapter} · {ipv4.get('address') or mode}"
    profile = {
        "name": label,
        "adapter": adapter,
        "mode": mode if mode == "dhcp" else "static",
        "ip": ipv4.get("address") or "",
        "prefix": ipv4.get("prefix") or 24,
        "netmask": ipv4.get("netmask") or _prefix_to_netmask(ipv4.get("prefix") or 24),
        "gateway": detail.get("gateway") or "",
        "dns": detail.get("dns") or [],
        "color": color or "#4ade80",
        "notes": f"Captured {_utc_now()}",
    }
    if detail.get("dhcp") is True:
        profile["mode"] = "dhcp"
        profile["ip"] = ""
        profile["gateway"] = ""
        profile["dns"] = []
        profile["netmask"] = ""
        profile["prefix"] = None
    return save_profile(profile)


def apply_profile(profile_id: str | None = None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply a saved profile or an inline profile body. Requires admin on Windows."""
    if not IS_WINDOWS:
        raise RuntimeError("IP apply is only implemented for Windows (netsh)")

    if profile_id and not profile:
        profile = get_profile(profile_id)
    if not profile:
        raise ValueError("No profile to apply")

    adapter = (profile.get("adapter") or "").strip()
    mode = (profile.get("mode") or "static").strip().lower()
    if profile.get("useActiveOnApply") or adapter in ("", ACTIVE_TOKEN, "__ACTIVE_ADAPTER__"):
        adapter = pick_active_adapter(True)
    if not adapter:
        raise ValueError("Adapter name required")

    # Validate adapter exists
    names = {a["name"] for a in list_adapters()}
    if adapter not in names:
        raise ValueError(f"Adapter not found: {adapter}. Available: {', '.join(sorted(names))}")

    steps: list[dict[str, Any]] = []

    if mode == "dhcp":
        steps.append(_run(["netsh", "interface", "ip", "set", "address", f"name={adapter}", "source=dhcp"]))
        steps.append(_run(["netsh", "interface", "ip", "set", "dns", f"name={adapter}", "source=dhcp"]))
    else:
        ip = (profile.get("ip") or "").strip()
        mask = (profile.get("netmask") or "").strip()
        if not mask:
            mask = _prefix_to_netmask(profile.get("prefix") or 24)
        gateway = (profile.get("gateway") or "").strip()
        if not ip:
            raise ValueError("Static profile missing IP")

        # netsh static: address [gateway gw metric]
        addr_cmd = [
            "netsh",
            "interface",
            "ip",
            "set",
            "address",
            f"name={adapter}",
            "source=static",
            f"addr={ip}",
            f"mask={mask}",
        ]
        if gateway:
            addr_cmd += [f"gateway={gateway}", "gwmetric=1"]
        steps.append(_run(addr_cmd))

        dns_list = profile.get("dns") or []
        if isinstance(dns_list, str):
            dns_list = [d.strip() for d in re.split(r"[,;\s]+", dns_list) if d.strip()]
        if dns_list:
            steps.append(
                _run(
                    [
                        "netsh",
                        "interface",
                        "ip",
                        "set",
                        "dns",
                        f"name={adapter}",
                        "source=static",
                        f"addr={dns_list[0]}",
                        "register=primary",
                        "validate=no",
                    ]
                )
            )
            for i, d in enumerate(dns_list[1:], start=2):
                steps.append(
                    _run(
                        [
                            "netsh",
                            "interface",
                            "ip",
                            "add",
                            "dns",
                            f"name={adapter}",
                            f"addr={d}",
                            f"index={i}",
                            "validate=no",
                        ]
                    )
                )
        else:
            # Leave DNS alone if empty? Safer to set DHCP DNS when none specified for static IP
            steps.append(_run(["netsh", "interface", "ip", "set", "dns", f"name={adapter}", "source=dhcp"]))

    failed = [s for s in steps if not s.get("ok")]
    # Permission hint
    admin_hint = False
    for s in failed:
        blob = (s.get("stderr") or "") + (s.get("stdout") or "")
        if re.search(r"access is denied|requires elevation|administrator", blob, re.I):
            admin_hint = True
            break

    # Refresh view
    try:
        after = get_adapter_detail(adapter)
    except Exception as e:
        after = {"error": str(e)}

    return {
        "ok": len(failed) == 0,
        "admin_required": admin_hint,
        "adapter": adapter,
        "mode": mode,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "steps": steps,
        "adapter_after": after,
        "message": (
            "Applied successfully"
            if not failed
            else (
                "Failed — run the toolbox server as Administrator to change IP settings"
                if admin_hint
                else "One or more netsh steps failed"
            )
        ),
    }


def pick_active_adapter(prefer_ethernet: bool = True) -> str:
    ads = list_adapters()
    up = [a for a in ads if a.get("is_up")]
    pool = up or ads
    if prefer_ethernet:
        eth = [
            a
            for a in pool
            if re.search(r"ether|eth|cable|local area|nic|lan", a.get("name") or "", re.I)
            and not re.search(r"wi-?fi|wireless|bluetooth|virtual|vmware|hyper-v|loop|vpn|tunnel", a.get("name") or "", re.I)
        ]
        if eth:
            return str(eth[0]["name"])
    if pool:
        return str(pool[0]["name"])
    raise ValueError("No network adapter found")


def resolve_adapter(profile: dict[str, Any]) -> str:
    adapter = (profile.get("adapter") or "").strip()
    if profile.get("useActiveOnApply") or adapter in ("", ACTIVE_TOKEN):
        return pick_active_adapter(True)
    return adapter


def probe_of(profile: dict[str, Any]) -> str:
    return str(profile.get("probe") or profile.get("gateway") or "").strip()


def ping_probe(host: str, timeout_ms: int = 400) -> dict[str, Any]:
    host = (host or "").strip()
    if not host:
        return {"ok": False, "host": host, "detail": "no probe", "ms": 0}
    timeout_ms = max(200, min(int(timeout_ms), 2000))
    t0 = time.time()
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        sec = max(1, timeout_ms // 1000)
        cmd = ["ping", "-c", "1", "-W", str(sec), host]
    r = _run(cmd, timeout=timeout_ms / 1000 + 1.5)
    ms = int((time.time() - t0) * 1000)
    blob = (r.get("stdout") or "") + "\n" + (r.get("stderr") or "")
    ok = bool(r.get("ok")) and bool(re.search(r"TTL=|ttl=", blob))
    if not ok and re.search(r"time[=<]\s*\d", blob, re.I):
        ok = True
    detail = "reply" if ok else "no reply"
    m = re.search(r"time[=<](\d+)\s*ms", blob, re.I)
    if m:
        detail = f"reply {m.group(1)}ms"
        try:
            ms = int(m.group(1))
        except ValueError:
            pass
    return {"ok": ok, "host": host, "detail": f"{detail} {host}", "ms": ms, "stdout": r.get("stdout")}


def ipv4_after(adapter: str) -> tuple[str, str]:
    try:
        d = get_adapter_detail(adapter)
    except Exception:
        return "", ""
    ip = ""
    ipv4 = d.get("ipv4") or []
    if ipv4:
        ip = str(ipv4[0].get("address") or "")
    return ip, str(d.get("gateway") or "")


def hunt(
    profile_ids: list[str] | None = None,
    timeout_ms: int = 400,
    settle_ms: int = 350,
) -> dict[str, Any]:
    """Apply each hunt-enabled profile and ping its probe until one answers."""
    store = _load_store()
    all_p = list(store.get("profiles") or [])
    if profile_ids:
        want = set(profile_ids)
        ordered = [p for p in all_p if p.get("id") in want]
        # keep requested order
        ordered.sort(key=lambda p: profile_ids.index(p.get("id")) if p.get("id") in want else 99)
    else:
        ordered = [p for p in all_p if p.get("hunt", True)]
    if not ordered:
        return {"ok": False, "hit": None, "attempts": [], "message": "No hunt-enabled setups"}

    attempts: list[dict[str, Any]] = []
    for p in ordered:
        probe = probe_of(p)
        name = p.get("name") or p.get("id")
        pid = p.get("id")
        try:
            adapter = resolve_adapter(p)
            payload = dict(p)
            payload["adapter"] = adapter
            payload["useActiveOnApply"] = False
            applied = apply_profile(profile=payload)
            settle = 900 if (p.get("mode") == "dhcp") else max(200, int(settle_ms))
            time.sleep(settle / 1000)
            ping = ping_probe(probe, timeout_ms=timeout_ms)
            ipv4, gw = ipv4_after(adapter)
            row = {
                "id": pid,
                "name": name,
                "probe": probe,
                "adapter": adapter,
                "ok": bool(ping.get("ok")),
                "detail": ping.get("detail"),
                "ms": ping.get("ms"),
                "apply_ok": bool(applied.get("ok")),
                "ipv4": ipv4,
                "gateway": gw or p.get("gateway") or "",
            }
            attempts.append(row)
            if ping.get("ok"):
                return {
                    "ok": True,
                    "hit": row,
                    "attempts": attempts,
                    "message": f"Hit {name} — {probe} answered",
                }
        except Exception as e:
            attempts.append(
                {
                    "id": pid,
                    "name": name,
                    "probe": probe,
                    "ok": False,
                    "detail": str(e),
                    "ms": 0,
                }
            )
    return {
        "ok": False,
        "hit": None,
        "attempts": attempts,
        "message": "No probe answered. Plug the cable and Hunt again.",
    }
