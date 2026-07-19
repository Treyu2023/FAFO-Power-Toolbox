"""
LAN & Task Manager — system monitoring, network diagnostics, and process control.
Windows-first; cross-platform where practical.
"""
from __future__ import annotations

import ipaddress
import platform
import re
import socket
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

import psutil

IS_WINDOWS = platform.system() == "Windows"
_NET_BASELINE: dict[str, tuple[int, int]] = {}
_NET_BASELINE_LOCK = threading.Lock()
_HOSTNAME_CACHE: dict[str, tuple[str, float]] = {}
_HOSTNAME_CACHE_TTL = 300.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, default=None):
    try:
        return fn()
    except (psutil.Error, OSError, PermissionError, ValueError):
        return default


def _bytes_human(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} PB"


def _resolve_hostname(ip: str, timeout: float = 1.5) -> str:
    if not ip or ip in ("*", "0.0.0.0", "::", "::1", "127.0.0.1"):
        return ""
    now = time.time()
    cached = _HOSTNAME_CACHE.get(ip)
    if cached and now - cached[1] < _HOSTNAME_CACHE_TTL:
        return cached[0]

    result: list[str] = []

    def worker():
        try:
            result.append(socket.gethostbyaddr(ip)[0])
        except (socket.herror, socket.gaierror, OSError):
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    name = result[0] if result else ""
    _HOSTNAME_CACHE[ip] = (name, now)
    return name


def _proc_name(pid: int | None) -> str:
    if not pid:
        return ""
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ""


def get_system_overview() -> dict[str, Any]:
    cpu = psutil.cpu_percent(interval=0.15)
    per_cpu = psutil.cpu_percent(interval=0, percpu=True)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/") if not IS_WINDOWS else psutil.disk_usage("C:\\")
    boot = datetime.fromtimestamp(psutil.boot_time()).isoformat()

    net_io = psutil.net_io_counters()
    rates = get_network_rates()

    return {
        "timestamp": _utc_now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu": {
            "percent": cpu,
            "cores_logical": psutil.cpu_count(logical=True),
            "cores_physical": psutil.cpu_count(logical=False),
            "per_core": per_cpu,
            "freq_mhz": _safe(lambda: psutil.cpu_freq().current),
        },
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
            "total_human": _bytes_human(mem.total),
            "used_human": _bytes_human(mem.used),
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "percent": swap.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "total_human": _bytes_human(disk.total),
            "used_human": _bytes_human(disk.used),
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout,
            "dropin": net_io.dropin,
            "dropout": net_io.dropout,
            "send_rate_bps": rates.get("send_bps", 0),
            "recv_rate_bps": rates.get("recv_bps", 0),
            "send_rate_human": _bytes_human(rates.get("send_bps", 0)) + "/s",
            "recv_rate_human": _bytes_human(rates.get("recv_bps", 0)) + "/s",
        },
        "boot_time": boot,
        "process_count": len(psutil.pids()),
    }


def get_network_rates() -> dict[str, float]:
    net = psutil.net_io_counters()
    now = time.time()
    with _NET_BASELINE_LOCK:
        prev = _NET_BASELINE.get("global")
        _NET_BASELINE["global"] = (net.bytes_sent, net.bytes_recv, now)
        if not prev:
            return {"send_bps": 0.0, "recv_bps": 0.0}
        sent0, recv0, t0 = prev
        dt = max(now - t0, 0.001)
        return {
            "send_bps": (net.bytes_sent - sent0) / dt,
            "recv_bps": (net.bytes_recv - recv0) / dt,
        }


def list_network_interfaces() -> list[dict[str, Any]]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    out = []
    for name, addr_list in addrs.items():
        st = stats.get(name)
        ipv4, ipv6, mac = [], [], ""
        for a in addr_list:
            if a.family == socket.AF_INET:
                ipv4.append({"addr": a.address, "netmask": a.netmask, "broadcast": a.broadcast})
            elif getattr(socket, "AF_INET6", None) and a.family == socket.AF_INET6:
                ipv6.append({"addr": a.address, "netmask": a.netmask})
            elif a.family == psutil.AF_LINK:
                mac = a.address
        io = _safe(lambda: psutil.net_io_counters(pernic=True).get(name))
        out.append({
            "name": name,
            "is_up": bool(st and st.isup),
            "speed_mbps": st.speed if st else 0,
            "duplex": str(st.duplex) if st else "",
            "mtu": st.mtu if st else 0,
            "mac": mac,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "bytes_sent": io.bytes_sent if io else 0,
            "bytes_recv": io.bytes_recv if io else 0,
        })
    return sorted(out, key=lambda x: (not x["is_up"], x["name"]))


def list_connections(
    kind: str = "all",
    search: str = "",
    limit: int = 500,
) -> dict[str, Any]:
    conns_raw = []
    try:
        conns_raw = psutil.net_connections(kind=kind)
    except (psutil.AccessDenied, PermissionError):
        pass

    rows = []
    proc_net: dict[int, dict[str, int]] = defaultdict(lambda: {"conns": 0, "send": 0, "recv": 0})

    for c in conns_raw:
        pid = c.pid or 0
        proc_net[pid]["conns"] += 1
        laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
        raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
        r_ip = c.raddr.ip if c.raddr else ""
        pname = _proc_name(c.pid)
        row = {
            "pid": pid,
            "process": pname,
            "family": "IPv6" if c.family == socket.AF_INET6 else "IPv4",
            "type": c.type.name if hasattr(c.type, "name") else str(c.type),
            "status": c.status,
            "local": laddr,
            "remote": raddr,
            "remote_ip": r_ip,
            "remote_host": _resolve_hostname(r_ip) if r_ip else "",
        }
        if search:
            q = search.lower()
            blob = " ".join(str(v) for v in row.values()).lower()
            if q not in blob:
                continue
        rows.append(row)

    rows.sort(key=lambda r: (r["status"] != "ESTABLISHED", -r["pid"]))
    total = len(rows)
    rows = rows[:limit]

    return {"connections": rows, "total": total, "limited": total > limit}


def list_processes(
    sort_by: str = "cpu",
    search: str = "",
    limit: int = 200,
    include_network: bool = True,
) -> dict[str, Any]:
    procs = []
    conn_by_pid: dict[int, int] = defaultdict(int)
    if include_network:
        try:
            for c in psutil.net_connections(kind="all"):
                if c.pid:
                    conn_by_pid[c.pid] += 1
        except (psutil.AccessDenied, PermissionError):
            pass

    for p in psutil.process_iter(["pid", "name", "username", "status", "create_time", "cpu_percent", "memory_info", "memory_percent", "num_threads", "exe", "cmdline"]):
        try:
            info = p.info
            mem = info.get("memory_info")
            mi = mem.rss if mem else 0
            cmdline = info.get("cmdline") or []
            row = {
                "pid": info["pid"],
                "name": info.get("name") or "",
                "username": info.get("username") or "",
                "status": info.get("status") or "",
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "memory_bytes": mi,
                "memory_human": _bytes_human(mi),
                "memory_percent": round(info.get("memory_percent") or 0, 2),
                "threads": info.get("num_threads") or 0,
                "connections": conn_by_pid.get(info["pid"], 0),
                "exe": info.get("exe") or "",
                "cmdline": " ".join(cmdline[:8]),
                "create_time": info.get("create_time"),
            }
            if search:
                q = search.lower()
                blob = f"{row['name']} {row['exe']} {row['cmdline']} {row['pid']}".lower()
                if q not in blob:
                    continue
            procs.append(row)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    key_map = {
        "cpu": lambda x: x["cpu_percent"],
        "memory": lambda x: x["memory_bytes"],
        "connections": lambda x: x["connections"],
        "name": lambda x: x["name"].lower(),
        "pid": lambda x: x["pid"],
    }
    procs.sort(key=key_map.get(sort_by, key_map["cpu"]), reverse=sort_by != "name")
    total = len(procs)
    procs = procs[:limit]
    return {"processes": procs, "total": total, "limited": total > limit}


def get_process_detail(pid: int) -> dict[str, Any]:
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        raise FileNotFoundError(f"Process {pid} not found")

    with p.oneshot():
        mem = p.memory_info()
        io = _safe(p.io_counters)
        conns = []
        try:
            for c in p.connections(kind="all"):
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                conns.append({
                    "status": c.status,
                    "local": laddr,
                    "remote": raddr,
                    "family": "IPv6" if c.family == socket.AF_INET6 else "IPv4",
                })
        except (psutil.AccessDenied, psutil.Error):
            pass

        return {
            "pid": pid,
            "name": p.name(),
            "exe": _safe(p.exe, ""),
            "cwd": _safe(p.cwd, ""),
            "status": p.status(),
            "username": _safe(p.username, ""),
            "create_time": p.create_time(),
            "cpu_percent": p.cpu_percent(interval=0.1),
            "memory": {
                "rss": mem.rss,
                "vms": mem.vms,
                "rss_human": _bytes_human(mem.rss),
            },
            "threads": p.num_threads(),
            "cmdline": _safe(p.cmdline, []),
            "io": {
                "read_bytes": io.read_bytes if io else 0,
                "write_bytes": io.write_bytes if io else 0,
                "read_human": _bytes_human(io.read_bytes) if io else "0 B",
                "write_human": _bytes_human(io.write_bytes) if io else "0 B",
            } if io else None,
            "connections": conns,
            "connection_count": len(conns),
        }


def kill_process(pid: int, force: bool = False) -> dict[str, Any]:
    try:
        p = psutil.Process(pid)
        name = p.name()
        if force:
            p.kill()
        else:
            p.terminate()
        gone, alive = psutil.wait_procs([p], timeout=3)
        if alive:
            p.kill()
        return {"ok": True, "pid": pid, "name": name, "force": force}
    except psutil.NoSuchProcess:
        raise FileNotFoundError(f"Process {pid} not found")
    except psutil.AccessDenied:
        raise PermissionError(f"Access denied terminating PID {pid}")


def _run_command(cmd: list[str], timeout: float = 60) -> tuple[str, str, int]:
    creationflags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=creationflags,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout, proc.stderr, proc.returncode


def _run_command_safe(cmd: list[str], timeout: float = 5) -> tuple[str, str, int]:
    try:
        return _run_command(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", "timed out", 124


def ping_host(host: str, count: int = 4, timeout_ms: int = 1000) -> dict[str, Any]:
    host = host.strip()
    if not host:
        raise ValueError("Host is required")
    count = max(1, min(count, 20))
    timeout_ms = max(200, min(timeout_ms, 10000))

    if IS_WINDOWS:
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    else:
        sec = max(1, timeout_ms // 1000)
        cmd = ["ping", "-c", str(count), "-W", str(sec), host]

    t0 = time.time()
    stdout, stderr, code = _run_command(cmd, timeout=count * (timeout_ms / 1000 + 2) + 5)
    elapsed = round(time.time() - t0, 2)

    replies = []
    if IS_WINDOWS:
        for line in stdout.splitlines():
            m = re.search(r"Reply from ([^:]+):.*time[=<](\d+)ms", line, re.I)
            if m:
                replies.append({"from": m.group(1).strip(), "time_ms": int(m.group(2)), "ok": True})
            m2 = re.search(r"Request timed out|Destination host unreachable|General failure", line, re.I)
            if m2:
                replies.append({"from": host, "time_ms": None, "ok": False, "error": m2.group(0)})
        stats_m = re.search(r"Minimum = (\d+)ms.*Maximum = (\d+)ms.*Average = (\d+)ms", stdout, re.I | re.S)
        stats = None
        if stats_m:
            stats = {"min_ms": int(stats_m.group(1)), "max_ms": int(stats_m.group(2)), "avg_ms": int(stats_m.group(3))}
    else:
        for line in stdout.splitlines():
            m = re.search(r"icmp_seq=\d+.*?time[=<]([\d.]+)\s*ms", line, re.I)
            if m:
                replies.append({"from": host, "time_ms": float(m.group(1)), "ok": True})
        stats_m = re.search(r"min/avg/max[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)", stdout)
        stats = None
        if stats_m:
            stats = {"min_ms": float(stats_m.group(1)), "max_ms": float(stats_m.group(3)), "avg_ms": float(stats_m.group(2))}

    return {
        "host": host,
        "success": code == 0 and any(r.get("ok") for r in replies),
        "elapsed_sec": elapsed,
        "replies": replies,
        "stats": stats,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "return_code": code,
    }


def traceroute(host: str, max_hops: int = 30, timeout_ms: int = 3000) -> dict[str, Any]:
    host = host.strip()
    if not host:
        raise ValueError("Host is required")
    max_hops = max(1, min(max_hops, 64))
    timeout_ms = max(500, min(timeout_ms, 10000))

    if IS_WINDOWS:
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", str(timeout_ms), host]
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", str(max(1, timeout_ms // 1000)), host]

    t0 = time.time()
    stdout, stderr, code = _run_command(cmd, timeout=max_hops * (timeout_ms / 1000 + 1) + 10)
    elapsed = round(time.time() - t0, 2)

    hops = []
    if IS_WINDOWS:
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Tracing") or line.startswith("over a maximum"):
                continue
            m = re.match(r"\s*(\d+)\s+(?:(<?\d+)\s+ms|\*)\s+(?:(<?\d+)\s+ms|\*)\s+(?:(<?\d+)\s+ms|\*)\s+(.+)$", line)
            if not m:
                m2 = re.match(r"\s*(\d+)\s+\*\s+\*\s+\*\s+Request timed out", line)
                if m2:
                    hops.append({"hop": int(m2.group(1)), "ip": "", "host": "", "times_ms": [], "timeout": True})
                continue
            hop_n = int(m.group(1))
            times = []
            for g in (m.group(2), m.group(3), m.group(4)):
                if g and g != "*":
                    times.append(int(g.replace("<", "")))
            target = m.group(5).strip()
            ip = target
            hostname = ""
            if " " in target:
                parts = target.split()
                ip = parts[0]
                hostname = " ".join(parts[1:])
            hops.append({
                "hop": hop_n,
                "ip": ip,
                "host": hostname or _resolve_hostname(ip),
                "times_ms": times,
                "timeout": len(times) == 0,
            })
    else:
        for line in stdout.splitlines():
            m = re.match(r"\s*(\d+)\s+(\S+)\s+([\d.]+)\s+ms", line)
            if m:
                ip = m.group(2)
                hops.append({
                    "hop": int(m.group(1)),
                    "ip": ip,
                    "host": _resolve_hostname(ip),
                    "times_ms": [float(m.group(3))],
                    "timeout": False,
                })

    return {
        "host": host,
        "success": len(hops) > 0,
        "elapsed_sec": elapsed,
        "hops": hops,
        "hop_count": len(hops),
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "return_code": code,
    }


def telnet_test(host: str, port: int, timeout_sec: float = 5.0) -> dict[str, Any]:
    host = host.strip()
    port = int(port)
    if not host:
        raise ValueError("Host is required")
    if not (1 <= port <= 65535):
        raise ValueError("Port must be 1–65535")

    t0 = time.time()
    result = {
        "host": host,
        "port": port,
        "open": False,
        "latency_ms": None,
        "resolved_ip": "",
        "error": "",
        "service_hint": _guess_service(port),
    }
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        result["resolved_ip"] = infos[0][4][0]
        sock = socket.socket(infos[0][0], socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        sock.connect((infos[0][4][0], port))
        result["open"] = True
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        sock.close()
    except socket.timeout:
        result["error"] = "Connection timed out"
    except ConnectionRefusedError:
        result["error"] = "Connection refused — host reachable, port closed"
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    except OSError as e:
        result["error"] = str(e)
    return result


def _guess_service(port: int) -> str:
    common = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
        110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB", 3306: "MySQL",
        3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Alt",
    }
    return common.get(port, "")


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip())
        return True
    except ValueError:
        return False


def _is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


_ARP_CACHE: tuple[float, list[dict[str, str]]] | None = None


def _cached_arp_table() -> list[dict[str, str]]:
    global _ARP_CACHE
    now = time.time()
    if _ARP_CACHE and now - _ARP_CACHE[0] < 30:
        return _ARP_CACHE[1]
    entries = get_arp_table()
    _ARP_CACHE = (now, entries)
    return entries


def _dedupe_records(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for r in results:
        key = (r["type"], r["value"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _parse_nslookup_ptr(stdout: str, ip: str) -> tuple[str, list[str]]:
    hostname = ""
    aliases: list[str] = []
    for line in stdout.splitlines():
        m = re.search(r"Name:\s+(.+)", line, re.I)
        if m:
            name = m.group(1).strip().rstrip(".")
            if name and name != ip:
                if not hostname:
                    hostname = name
                else:
                    aliases.append(name)
    return hostname, aliases


def _parse_ping_name(stdout: str) -> str:
    m = re.search(r"Pinging\s+(.+?)\s+\[", stdout, re.I)
    if m:
        name = m.group(1).strip()
        if name and not _is_ip_address(name):
            return name
    return ""


def _parse_nbtstat_name(stdout: str) -> str:
    for line in stdout.splitlines():
        m = re.match(r"\s+([A-Z0-9_-]+)\s+<00>\s+UNIQUE", line, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _valid_mac(mac: str) -> bool:
    return bool(mac) and mac not in (":::", "—") and ":" in mac and len(mac) >= 11


def _reverse_dns_fallbacks(ip: str) -> dict[str, Any]:
    """Collect hostname/MAC hints when PTR records are missing (common on LAN)."""
    import socket as sock

    hints: dict[str, Any] = {
        "ptr": "",
        "aliases": [],
        "ips": [ip],
        "mac": "",
        "sources": [],
    }

    for entry in _cached_arp_table():
        if entry["ip"] == ip:
            mac = entry.get("mac", "")
            if _valid_mac(mac):
                hints["mac"] = mac
                hints["sources"].append("arp")
            if entry.get("host"):
                hints["ptr"] = entry["host"]
            break

    if hints["ptr"] or _valid_mac(hints["mac"]):
        return hints

    if IS_WINDOWS:
        stdout, _, _ = _run_command_safe(["ping", "-a", "-n", "1", "-w", "500", ip], timeout=2)
        ping_name = _parse_ping_name(stdout)
        if ping_name:
            hints["ptr"] = ping_name
            hints["sources"].append("ping")
            return hints

    stdout, _, _ = _run_command_safe(["nslookup", ip], timeout=3)
    ns_name, ns_aliases = _parse_nslookup_ptr(stdout, ip)
    if ns_name:
        hints["ptr"] = ns_name
        hints["sources"].append("nslookup")
    for alias in ns_aliases:
        if alias not in hints["aliases"] and alias != hints["ptr"]:
            hints["aliases"].append(alias)

    return hints


def _build_reverse_response(ip: str, hints: dict[str, Any], ptr_source: str = "") -> dict[str, Any]:
    import socket as sock

    hostname = hints.get("ptr", "")
    aliases = list(hints.get("aliases") or [])
    ipaddrs = list(hints.get("ips") or [ip])
    mac = hints.get("mac", "")
    sources = list(hints.get("sources") or ([ptr_source] if ptr_source else []))

    results: list[dict[str, str]] = []
    if hostname:
        results.append({"type": "PTR", "value": hostname, "label": "Hostname"})
    for alias in aliases:
        if alias and alias != hostname:
            results.append({"type": "ALIAS", "value": alias, "label": "Alias"})
    if _valid_mac(mac):
        results.append({"type": "MAC", "value": mac, "label": "ARP"})
    for addr in ipaddrs:
        family = "AAAA" if ":" in addr else "A"
        results.append({"type": family, "value": addr, "label": "IP"})

    forward: list[dict[str, str]] = []
    forward_name = hostname or (aliases[0] if aliases else "")
    if forward_name and not _is_ip_address(forward_name):
        try:
            for info in sock.getaddrinfo(forward_name, None, family=sock.AF_INET, type=sock.SOCK_STREAM):
                forward.append({"type": "A", "value": info[4][0], "label": "Forward A"})
                if len(forward) >= 6:
                    break
        except OSError:
            pass

    note = ""
    error = ""
    if not hostname and not _valid_mac(mac):
        error = "No DNS PTR record found for this IP. Try running a LAN scan first to populate ARP."
    elif not hostname and _valid_mac(mac):
        note = "No PTR record — showing MAC address from local ARP table."
    elif ptr_source and ptr_source != "ptr" and "ptr" not in sources:
        note = f"Name resolved via {', '.join(sources)} (no public PTR record)."

    return {
        "host": ip,
        "record_type": "REVERSE",
        "query_mode": "reverse",
        "is_ip": True,
        "records": _dedupe_records(results),
        "reverse": {
            "ptr": hostname,
            "aliases": aliases,
            "ips": ipaddrs,
            "mac": mac,
            "sources": sources,
        },
        "forward_records": _dedupe_records(forward),
        "note": note,
        "error": error,
    }


def _socket_ptr_lookup(ip: str) -> dict[str, Any] | None:
    import socket as sock

    result: list[Any] = []
    err: list[Exception] = []

    def worker():
        try:
            result.append(sock.gethostbyaddr(ip))
        except OSError as e:
            err.append(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=2.0 if _is_private_ip(ip) else 5.0)
    if not result:
        return None
    hostname, aliases, ipaddrs = result[0]
    return {
        "ptr": hostname,
        "aliases": list(aliases),
        "ips": list(ipaddrs),
        "mac": next((e.get("mac", "") for e in _cached_arp_table() if e["ip"] == ip and _valid_mac(e.get("mac", ""))), "") if _is_private_ip(ip) else "",
        "sources": ["ptr"],
    }


def _reverse_dns_lookup(ip: str) -> dict[str, Any]:
    if _is_private_ip(ip):
        hints = _reverse_dns_fallbacks(ip)
        if hints.get("ptr") or _valid_mac(hints.get("mac", "")):
            return _build_reverse_response(ip, hints)

    ptr = _socket_ptr_lookup(ip)
    if ptr:
        return _build_reverse_response(ip, ptr, ptr_source="ptr")

    hints = _reverse_dns_fallbacks(ip)
    return _build_reverse_response(ip, hints)


def _forward_dns_lookup(host: str, record_type: str) -> dict[str, Any]:
    import socket as sock

    results: list[dict[str, str]] = []
    if record_type == "A":
        for info in sock.getaddrinfo(host, None, family=sock.AF_INET):
            results.append({"type": "A", "value": info[4][0], "label": "IPv4"})
    elif record_type == "AAAA":
        for info in sock.getaddrinfo(host, None, family=sock.AF_INET6):
            results.append({"type": "AAAA", "value": info[4][0], "label": "IPv6"})
    elif record_type == "CANONICAL":
        name = sock.getfqdn(host)
        results.append({"type": "FQDN", "value": name, "label": "Canonical name"})
    else:
        raise ValueError(f"Unsupported record type: {record_type}")

    return {
        "host": host,
        "record_type": record_type,
        "query_mode": "forward",
        "is_ip": False,
        "records": _dedupe_records(results),
        "reverse": None,
        "forward_records": [],
        "error": "",
    }


def dns_lookup(host: str, record_type: str = "AUTO") -> dict[str, Any]:
    host = host.strip()
    if not host:
        raise ValueError("Host is required")

    record_type = (record_type or "AUTO").upper()
    is_ip = _is_ip_address(host)

    if record_type == "AUTO":
        record_type = "REVERSE" if is_ip else "A"

    if is_ip or record_type == "REVERSE":
        if not is_ip:
            raise ValueError("Reverse lookup requires an IP address (e.g. 8.8.8.8)")
        return _reverse_dns_lookup(host)

    try:
        return _forward_dns_lookup(host, record_type)
    except OSError as e:
        return {
            "host": host,
            "record_type": record_type,
            "query_mode": "forward",
            "is_ip": is_ip,
            "records": [],
            "reverse": None,
            "forward_records": [],
            "note": "",
            "error": str(e),
        }


def port_scan(host: str, ports: list[int] | None = None, timeout_sec: float = 1.0) -> dict[str, Any]:
    host = host.strip()
    if not host:
        raise ValueError("Host is required")
    if ports is None:
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 3306, 3389, 5432, 5900, 8080]
    ports = sorted({int(p) for p in ports if 1 <= int(p) <= 65535})[:100]

    open_ports = []
    closed = []
    errors = []

    def probe(port: int):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            r = sock.connect_ex((host, port))
            sock.close()
            if r == 0:
                open_ports.append({"port": port, "service": _guess_service(port)})
            else:
                closed.append(port)
        except OSError as e:
            errors.append({"port": port, "error": str(e)})

    threads = [threading.Thread(target=probe, args=(p,), daemon=True) for p in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout_sec + 1)

    open_ports.sort(key=lambda x: x["port"])
    return {
        "host": host,
        "scanned": len(ports),
        "open": open_ports,
        "open_count": len(open_ports),
        "closed_count": len(closed),
        "errors": errors,
    }


def get_arp_table() -> list[dict[str, str]]:
    if IS_WINDOWS:
        stdout, _, _ = _run_command_safe(["arp", "-a"], timeout=5)
    else:
        stdout, _, _ = _run_command_safe(["arp", "-an"], timeout=5)

    entries = []
    for line in stdout.splitlines():
        if IS_WINDOWS:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f\-]+)\s+(\w+)", line, re.I)
            if m:
                entries.append({
                    "ip": m.group(1),
                    "mac": m.group(2).replace("-", ":").upper(),
                    "type": m.group(3),
                    "host": "",
                })
        else:
            m = re.search(r"\(([^)]+)\) at ([^\s]+)", line)
            if m:
                entries.append({
                    "ip": m.group(1),
                    "mac": m.group(2).upper(),
                    "type": "dynamic",
                    "host": "",
                })
    return entries


def get_default_gateway() -> str:
    gws = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    # Try route table via ipconfig/route on Windows
    if IS_WINDOWS:
        stdout, _, _ = _run_command(["ipconfig"])
        for line in stdout.splitlines():
            if "Default Gateway" in line:
                m = re.search(r":\s*(\d+\.\d+\.\d+\.\d+)", line)
                if m and m.group(1) != "0.0.0.0":
                    return m.group(1)
    return ""


def discover_lan(subnet: str = "", timeout_ms: int = 500) -> dict[str, Any]:
    """Ping-sweep local subnet + ARP table for LAN device discovery."""
    local_ips = []
    for iface in list_network_interfaces():
        for v4 in iface.get("ipv4", []):
            addr = v4.get("addr")
            if addr and not addr.startswith("127."):
                local_ips.append({"interface": iface["name"], "ip": addr, "netmask": v4.get("netmask")})

    targets: list[str] = []
    arp_entries = get_arp_table()

    if subnet:
        try:
            net = ipaddress.ip_network(subnet, strict=False)
            targets = [str(ip) for ip in net.hosts()][:254]
        except ValueError as e:
            raise ValueError(str(e))
    elif local_ips:
        ip = local_ips[0]["ip"]
        mask = local_ips[0].get("netmask") or "255.255.255.0"
        try:
            iface = ipaddress.ip_interface(f"{ip}/{mask}")
            net = iface.network
            targets = [str(h) for h in net.hosts() if str(h) != ip][:254]
        except ValueError:
            base = ".".join(ip.split(".")[:3])
            targets = [f"{base}.{i}" for i in range(1, 255)]
    else:
        targets = []

    found: dict[str, dict[str, Any]] = {}
    for e in arp_entries:
        found[e["ip"]] = {
            "ip": e["ip"],
            "mac": e["mac"],
            "host": e.get("host") or "",
            "source": "arp",
            "latency_ms": None,
            "status": "known",
        }

    lock = threading.Lock()
    timeout_sec = max(0.2, timeout_ms / 1000)

    def ping_one(target: str):
        if IS_WINDOWS:
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), target]
        else:
            cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_sec))), target]
        try:
            stdout, _, code = _run_command(cmd, timeout=timeout_sec + 2)
            if code == 0 or "Reply from" in stdout or "bytes from" in stdout:
                m = re.search(r"time[=<](\d+)", stdout, re.I)
                latency = int(m.group(1)) if m else None
                with lock:
                    prev = found.get(target, {})
                    found[target] = {
                        "ip": target,
                        "mac": prev.get("mac", ""),
                        "host": prev.get("host") or _resolve_hostname(target),
                        "source": "ping",
                        "latency_ms": latency,
                        "status": "online",
                    }
        except subprocess.TimeoutExpired:
            pass

    if targets:
        batch_size = 32
        for i in range(0, len(targets), batch_size):
            chunk = targets[i:i + batch_size]
            threads = [threading.Thread(target=ping_one, args=(t,), daemon=True) for t in chunk]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout_sec + 3)

    devices = sorted(found.values(), key=lambda d: tuple(int(x) for x in d["ip"].split(".")))
    return {
        "local_interfaces": local_ips,
        "gateway": get_default_gateway(),
        "subnet_scanned": subnet or (local_ips[0]["ip"] if local_ips else ""),
        "devices": devices,
        "device_count": len(devices),
        "online_count": sum(1 for d in devices if d.get("status") == "online"),
    }


def get_listening_ports() -> list[dict[str, Any]]:
    rows = []
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status != psutil.CONN_LISTEN:
                continue
            laddr = c.laddr
            if not laddr:
                continue
            rows.append({
                "pid": c.pid or 0,
                "process": _proc_name(c.pid),
                "port": laddr.port,
                "address": laddr.ip,
                "family": "IPv6" if c.family == socket.AF_INET6 else "IPv4",
            })
    except (psutil.AccessDenied, PermissionError):
        pass
    rows.sort(key=lambda r: r["port"])
    return rows


def run_diagnostics() -> dict[str, Any]:
    """Quick health check bundle."""
    overview = get_system_overview()
    issues = []
    if overview["cpu"]["percent"] > 90:
        issues.append({"level": "warn", "message": f"High CPU usage: {overview['cpu']['percent']}%"})
    if overview["memory"]["percent"] > 90:
        issues.append({"level": "warn", "message": f"High memory usage: {overview['memory']['percent']}%"})
    if overview["disk"]["percent"] > 90:
        issues.append({"level": "warn", "message": f"Low disk space: {overview['disk']['percent']}% used"})
    if overview["network"]["errin"] + overview["network"]["errout"] > 100:
        issues.append({"level": "info", "message": "Network errors detected on interface counters"})

    gateway = get_default_gateway()
    ping_gw = None
    if gateway:
        ping_gw = ping_host(gateway, count=2, timeout_ms=1000)

    dns = dns_lookup("google.com")
    if dns.get("error"):
        issues.append({"level": "error", "message": f"DNS resolution failed: {dns['error']}"})

    return {
        "timestamp": _utc_now(),
        "overview": overview,
        "gateway": gateway,
        "gateway_ping": ping_gw,
        "dns_test": dns,
        "issues": issues,
        "healthy": not any(i["level"] == "error" for i in issues),
    }