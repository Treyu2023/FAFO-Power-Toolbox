"""Local defensive check: inbound shells, remote-admin listeners, and
published agent-intrusion indicators.

Reads this PC only. Does not change firewall rules, services, or files,
and does not contact command-and-control hosts. Indicators are names and
file hashes published by vendors in 2026, matched locally.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# Published setup.js hashes (Bitdefender, Nov 2026). Compare only.
_SETUP_JS_MD5 = {
    "b9a182b646c7fdff68f2ff9dfd822516",
    "2f54f6d41f41bb3c8e684b0f009cbcc3",
    "3794736979327349404171798328a38a",
    "ab7ff2f782c194953e5811d16b9e1817",
    "2191cbd04134839daeb6b8909725eae0",
    "31f1f5d9c59b950d91d05cecee20fce8",
    "908293cd1ed04cf50fbe72baf74967b6",
    "bbd5695c36e76538547c45fd17e6c7e4",
    "7ad1567180f6d5a5b317f697310a796c",
    "5c8db9bf78c6c2174ccf8a6299f9aafd",
    "82a8be193a41f5b17906f919a179d999",
    "5dc5473468ee2d8006ebdaab0c7e93fb",
    "a20a99e325226f56d7a25460a9d436ab",
}

# Defanged published ZQAgent names (NVISO, Nov 2026). Local match only.
_C2_IP = "37.122.150.15"
_C2_NAME = "bloonspace.com"

_SHELLS = {
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "bash.exe",
    "wsl.exe",
    "sh.exe",
}
_SCRIPT_HOSTS = {
    "python.exe",
    "pythonw.exe",
    "node.exe",
    "ruby.exe",
    "perl.exe",
    "php.exe",
    "java.exe",
    "javaw.exe",
}
_ADMIN_PORTS = {22: "SSH", 3389: "Remote Desktop", 5985: "WinRM", 5986: "WinRM", 47001: "WinRM"}
_SHARE_PORTS = {135: "RPC", 139: "NetBIOS", 445: "SMB"}

_SKIP_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "thumbnails",
    ".cache",
    "cache",
    "target",
    "bin",
    "obj",
    "site-packages",
    "sessions",
    "projects",
    ".next",
    "coverage",
    "quarantine",
    "videos",
    "music",
    "pictures",
}
_INSTRUCTION_NAMES = {
    "agents.md",
    "claude.md",
    ".cursorrules",
    ".windsurfrules",
    "copilot-instructions.md",
    "mcp.json",
    ".mcp.json",
    ".aider.conf.yml",
    "tasks.json",
}
_HOOK_NAMES = {"settings.json", "settings.local.json", "setup.mdc", "setup.mjs"}

_CAMPAIGN_BAD = (
    re.compile(r"sealed\s+binary\s+artifact", re.I),
    re.compile(r"do not read,\s*quote,\s*or display", re.I),
)
_SETUP_JS = re.compile(r"scripts[/\\]setup\.js", re.I)
_SILENT_RUN = re.compile(r"without (asking for )?confirmation", re.I)
_BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060]")
_SUSPICIOUS_CMD = re.compile(
    r"(?i)(-encodedcommand|-enc\s+[A-Za-z0-9+/=]{24,}|downloadstring|"
    r"invoke-expression|\biex\s*\(|frombase64string|"
    r"net\.sockets\.tcpclient|system\.net\.sockets\.tcpclient|"
    r"certutil(\.exe)?\s+[^\r\n]{0,40}-urlcache)"
)
_SECRET = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+"
    r"|sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{16}|Bearer\s+\S+"
)

_BAD_TOOLS = {
    "mimikatz.exe": "credential dump tool",
    "lazagne.exe": "credential harvest tool",
    "nc.exe": "netcat",
    "ncat.exe": "ncat",
}
_TUNNELS = {
    "ngrok.exe": "ngrok tunnel",
    "cloudflared.exe": "Cloudflare tunnel",
    "chisel.exe": "chisel tunnel",
    "frpc.exe": "frp tunnel",
    "socat.exe": "socat",
}
_REMOTE_APPS = {
    "anydesk.exe": "AnyDesk",
    "teamviewer.exe": "TeamViewer",
    "rustdesk.exe": "RustDesk",
    "parsec.exe": "Parsec",
}
# Normal Windows listeners. Other programs that bind a non-loopback port are listed, not treated as shells.
_WINDOWS_BASE = {
    "system.exe",
    "svchost.exe",
    "lsass.exe",
    "wininit.exe",
    "services.exe",
    "spoolsv.exe",
    "dashost.exe",
    "msmpeng.exe",
    "searchindexer.exe",
    "securityhealthservice.exe",
    "csrss.exe",
    "smss.exe",
    "dwm.exe",
    "registry",
}


def redact(text: str, limit: int = 220) -> str:
    """Shorten a command or snippet and mask token-shaped values."""
    raw = _SECRET.sub("<redacted>", text or "")
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) > limit:
        return raw[: limit - 1] + "…"
    return raw


def is_loopback(addr: str | None) -> bool:
    a = (addr or "").strip().lower().split("%", 1)[0]
    if a in {"::1", "0:0:0:0:0:0:0:1", "localhost"}:
        return True
    if a.startswith("127.") or a.startswith("::ffff:127."):
        return True
    return False


def _exe(name: str | None) -> str:
    n = (name or "").strip().lower()
    if n and "." not in n:
        n += ".exe"
    return n


def text_hits(text: str) -> list[dict[str, str]]:
    """Campaign phrases and hidden Unicode in one instruction file."""
    hits: list[dict[str, str]] = []
    if not text:
        return hits
    for cre in _CAMPAIGN_BAD:
        if cre.search(text):
            hits.append({"severity": "bad", "why": "instruction matches a published agent-malware phrase"})
            break
    else:
        mentions_setup = _SETUP_JS.search(text) is not None
        if mentions_setup and _SILENT_RUN.search(text):
            hits.append({"severity": "warn", "why": "instruction tells an agent to run setup without review"})
        elif mentions_setup:
            hits.append({"severity": "warn", "why": "instruction points an agent at scripts/setup.js"})
    if _BIDI.search(text):
        hits.append({"severity": "bad", "why": "hidden bidirectional Unicode in an agent instruction file"})
    zw = _ZERO_WIDTH.findall(text)
    body = text.lstrip("\ufeff")
    if len(_ZERO_WIDTH.findall(body)) >= 4 or (zw and len(zw) >= 4):
        hits.append({"severity": "warn", "why": "clusters of hidden zero-width characters"})
    return hits


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _item(severity: str, title: str, detail: str = "") -> dict[str, str]:
    return {"severity": severity, "title": title, "detail": redact(detail, 300)}


def default_scan_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".claude",
        home / ".cursor",
        home / ".codex",
        home / ".gemini",
        home / ".grok",
        home / ".windsurf",
        home / ".aider",
        Path(r"C:\_Git\repos"),
        home / "Documents",
        home / "Downloads",
    ]
    return [p for p in roots if p.is_dir()]


def _interesting_file(path: Path) -> bool:
    name = path.name.lower()
    if name in _INSTRUCTION_NAMES or name in _HOOK_NAMES or name == "setup.js":
        return True
    return False


def _should_read(path: Path) -> bool:
    name = path.name.lower()
    if name == "setup.js":
        return True
    parts = {p.lower() for p in path.parts}
    if name in _HOOK_NAMES:
        return bool(parts & {".claude", ".cursor", ".gemini", ".vscode", ".codex"})
    if name == "tasks.json":
        return ".vscode" in parts
    return name in _INSTRUCTION_NAMES


def scan_instruction_files(roots: list[Path], *, budget_s: float = 28.0) -> dict[str, Any]:
    """Walk a few dev roots for agent instruction files. Stops on a time budget."""
    started = time.time()
    hits: list[dict[str, str]] = []
    opened = 0
    stopped = False
    seen: set[str] = set()

    for root in roots:
        if time.time() - started > budget_s:
            stopped = True
            break
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if time.time() - started > budget_s or opened >= 280:
                stopped = True
                break
            dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS and not d.startswith(".git")]
            for fn in filenames:
                path = Path(dirpath) / fn
                if not _interesting_file(path) or not _should_read(path):
                    continue
                key = str(path).lower()
                if key in seen:
                    continue
                seen.add(key)
                opened += 1
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if path.name.lower() == "setup.js":
                    if size <= 20 * 1024 * 1024:
                        digest = _md5_file(path)
                        if digest in _SETUP_JS_MD5:
                            hits.append(
                                _item(
                                    "bad",
                                    "Known agent credential-stealer script",
                                    str(path),
                                )
                            )
                    continue
                if size > 500_000:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for hit in text_hits(text):
                    hits.append(_item(hit["severity"], hit["why"], str(path)))
                if path.name.lower() == "tasks.json" and re.search(r'"runOn"\s*:\s*"folderOpen"', text):
                    hits.append(_item("warn", "VS Code task runs when the folder opens", str(path)))
                if path.name.lower() in {"mcp.json", ".mcp.json", "settings.json", "settings.local.json"}:
                    hits.extend(_mcp_command_hits(path, text))
            if stopped:
                break
    return {"hits": hits[:40], "filesRead": opened, "stoppedEarly": stopped}


def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _mcp_command_hits(path: Path, text: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return hits

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            cmd = str(node.get("command") or "")
            args = node.get("args")
            arg_s = " ".join(str(a) for a in args) if isinstance(args, list) else str(args or "")
            line = f"{cmd} {arg_s}"
            if _SUSPICIOUS_CMD.search(line):
                hits.append(_item("bad", "MCP or hook command looks like a hidden shell", f"{path}: {line}"))
            elif re.search(r"(?i)setup\.js", line) and re.search(r"(?i)\b(node|bun)\b", line):
                hits.append(_item("warn", "Hook or MCP entry runs setup.js", f"{path}: {line}"))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return hits


def _known_file_hits() -> list[dict[str, str]]:
    hits = []
    temp = os.environ.get("TEMP") or ""
    paths = [
        (Path(r"C:\Windows\Temp\svchosts.exe"), "published beacon file name"),
        (Path(r"C:\Windows\Temp\svcmon32.exe"), "published beacon file name"),
        (Path(r"C:\Windows\svchosts.exe"), "published beacon file name"),
        (Path(r"C:\ProgramData\dsn_line.txt"), "published credential-dump file name"),
    ]
    if temp:
        paths.append((Path(temp) / "svchosts.exe", "published beacon file name in the user temp folder"))
    for path, why in paths:
        if path.is_file():
            hits.append(_item("bad", why, str(path)))
    hosts = Path(r"C:\Windows\System32\drivers\etc\hosts")
    try:
        body = hosts.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        body = ""
    if _C2_NAME in body:
        hits.append(_item("bad", "Hosts file names a published backdoor server", _C2_NAME.replace(".", "[.]")))
    return hits


def _run_keys() -> list[dict[str, str]]:
    hits = []
    try:
        import winreg
    except ImportError:
        return hits
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for hive, sub in keys:
        try:
            with winreg.OpenKey(hive, sub) as key:
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        continue
                    line = f"{name} {value}"
                    if re.search(r"(?i)^SystemUpdate$", str(name)) or _SUSPICIOUS_CMD.search(str(value)):
                        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                        hits.append(_item("bad", f"Startup Run value {hive_name}\\{name}", str(value)))
        except OSError:
            continue
    return hits


def _rdp_allowed() -> bool | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Terminal Server",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "fDenyTSConnections")
            return int(val) == 0
    except (OSError, ImportError, ValueError):
        return None


def _own_pids() -> set[int]:
    """This scanner and the PowerShell child it starts. Their command lines are not findings."""
    pids = {os.getpid()}
    try:
        import psutil

        me = psutil.Process()
        pids.add(me.pid)
        parent = me.parent()
        if parent:
            pids.add(parent.pid)
        for child in me.children(recursive=True):
            pids.add(child.pid)
    except Exception:
        pass
    return pids


def _ps_inventory() -> dict[str, Any]:
    """One Windows PowerShell call for listeners, services, tasks, and logons."""
    script = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
try {
$step = 'listen'
$listen = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess)
$step = 'shells'
$names = @('powershell','pwsh','cmd','wscript','cscript','mshta','bash','wsl')
$shells = New-Object System.Collections.Generic.List[uint32]
Get-Process -Name $names -ErrorAction SilentlyContinue | ForEach-Object {
  $shells.Add([uint32]$_.Id)
}
$step = 'established'
$established = @()
if ($shells.Count -gt 0) {
  $established = @(Get-NetTCPConnection -State Established -OwningProcess $shells.ToArray() -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess)
}
$step = 'services'
$svc = New-Object System.Collections.Generic.List[object]
foreach ($n in @('TermService','sshd','WinRM','RemoteRegistry','LanmanServer','RemoteAccess')) {
  $one = Get-Service -Name $n -ErrorAction SilentlyContinue
  if ($one) {
    $svc.Add([pscustomobject]@{ Name = $one.Name; Status = $one.Status.ToString(); StartType = $one.StartType.ToString() })
  }
}
$step = 'firewall'
$profiles = @(Get-NetFirewallProfile -ErrorAction SilentlyContinue | Select-Object Name, Enabled)
$step = 'tasks'
$tasks = New-Object System.Collections.Generic.List[object]
try { Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object {
  $tn = [string]$_.TaskName
  foreach ($a in @($_.Actions)) {
    $exe = [string]$a.Execute
    $arg = [string]$a.Arguments
    $line = "$exe $arg"
    $nameHit = $tn -match '^(?i)SystemUpdate$'
    $pat = $line -match '(?i)(-encodedcommand|-enc\s|downloadstring|invoke-expression|frombase64string|\\temp\\|\\appdata\\local\\temp\\)'
    if ($nameHit -or $pat) {
      if ($tasks.Count -lt 30) {
        $short = $arg
        if ($short.Length -gt 160) { $short = $short.Substring(0, 160) }
        $tasks.Add([pscustomobject]@{ Task = $tn; TaskPath = [string]$_.TaskPath; Execute = $exe; Arguments = $short })
      }
    }
  }
}
} catch {}
$step = 'defender'
$defender = $null
try { $defender = Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, IoavProtectionEnabled, AntivirusEnabled } catch {}
$step = 'logons'
$logons = New-Object System.Collections.Generic.List[string]
try {
  $q = "*[System[(EventID=4624) and TimeCreated[timediff(@SystemTime) <= 1209600000]] and EventData[Data[@Name='LogonType']='10']]"
  $raw = & wevtutil.exe qe Security /q:$q /c:15 /rd:true /f:text 2>&1 | Out-String
  if ($raw -match 'Access is denied') {
    $logons.Add('Security log not readable')
  } elseif ($raw) {
    $logons.Add($raw.Substring(0, [Math]::Min(4000, $raw.Length)))
  }
} catch {
  $logons.Add('Security log not readable')
}
$step = 'dns'
$dns = @()
try {
  $dns = @(Get-DnsClientCache | Where-Object { $_.Entry -match 'bloonspace' } | Select-Object -First 5 Entry, Data)
} catch {}
$listenOut = foreach ($r in @($listen)) {
  [pscustomobject]@{ LocalAddress = [string]$r.LocalAddress; LocalPort = [int]$r.LocalPort; OwningProcess = [int]$r.OwningProcess }
}
$estOut = foreach ($r in @($established)) {
  [pscustomobject]@{
    LocalAddress = [string]$r.LocalAddress
    LocalPort = [int]$r.LocalPort
    RemoteAddress = [string]$r.RemoteAddress
    RemotePort = [int]$r.RemotePort
    OwningProcess = [int]$r.OwningProcess
  }
}
[pscustomobject]@{
  listen = @($listenOut)
  established = @($estOut)
  services = @($svc.ToArray())
  firewall = @($profiles)
  tasks = @($tasks.ToArray())
  defender = $defender
  logons = @($logons.ToArray())
  dns = @($dns)
} | ConvertTo-Json -Depth 4 -Compress
} catch {
  [pscustomobject]@{ error = ($step + ' :: ' + $_.Exception.Message) } | ConvertTo-Json -Compress
}
"""
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    tmp = tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8")
    try:
        tmp.write(script)
        tmp.close()
        proc = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", tmp.name],
            capture_output=True,
            text=True,
            timeout=70,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    raw = (proc.stdout or "").strip()
    if not raw:
        err = (proc.stderr or "").strip()[:400]
        return {"error": err or f"powershell exit {proc.returncode}"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "powershell inventory was not JSON"}
    return data if isinstance(data, dict) else {"error": "unexpected powershell payload"}


def _process_table() -> dict[int, dict[str, str]]:
    table: dict[int, dict[str, str]] = {}
    try:
        import psutil
    except ImportError:
        return table
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            pid = int(info.get("pid") or 0)
            cmd = info.get("cmdline") or []
            line = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd or "")
            table[pid] = {"name": str(info.get("name") or ""), "cmd": line}
        except (psutil.Error, OSError, ValueError):
            continue
    return table


def _toolbox_note(port: int, cmd: str) -> str | None:
    low = (cmd or "").lower()
    if port == 18780 and "phone_static" in low:
        return "FAFO phone file share (static pages on the LAN, not a shell)"
    if port == 18765 and ("aitoolbox" in low or "fafo" in low):
        return "FAFO toolbox API"
    if port == 18766 and ("fafo_diag" in low or "device" in low):
        return "FAFO device diagnostics"
    return None


def _psutil_listen() -> list[dict[str, Any]]:
    try:
        import psutil
    except ImportError:
        return []
    rows: list[dict[str, Any]] = []
    try:
        conns = psutil.net_connections(kind="tcp")
    except Exception:
        return rows
    for conn in conns:
        if conn.status != psutil.CONN_LISTEN or not conn.laddr:
            continue
        rows.append(
            {
                "LocalAddress": conn.laddr.ip,
                "LocalPort": conn.laddr.port,
                "OwningProcess": conn.pid or 0,
            }
        )
    return rows


def _classify_listeners(rows: list[dict], procs: dict[int, dict[str, str]]) -> dict[str, list]:
    shells: list[dict[str, str]] = []
    admin: list[dict[str, str]] = []
    scripts: list[dict[str, str]] = []
    known: list[dict[str, str]] = []
    others: list[dict[str, str]] = []
    shares: set[int] = set()
    seen: set[tuple] = set()
    seen_other: set[str] = set()
    for row in rows:
        addr = str(row.get("LocalAddress") or "")
        try:
            port = int(row.get("LocalPort") or 0)
        except (TypeError, ValueError):
            continue
        try:
            pid = int(row.get("OwningProcess") or 0)
        except (TypeError, ValueError):
            pid = 0
        key = (addr, port, pid)
        if key in seen:
            continue
        seen.add(key)
        meta = procs.get(pid) or {}
        name = _exe(meta.get("name"))
        cmd = meta.get("cmd") or ""
        loop = is_loopback(addr)
        label = f"{name or 'pid ' + str(pid)} on {addr}:{port}"
        if name in _SHELLS:
            if loop:
                shells.append(_item("info", "Shell listening on loopback only", label))
            else:
                shells.append(_item("bad", "Shell is accepting network connections", label + " " + cmd))
            continue
        if port in _ADMIN_PORTS and not loop:
            admin.append(_item("warn", f"{_ADMIN_PORTS[port]} is listening on the network", label))
        note = _toolbox_note(port, cmd)
        if note and not loop:
            known.append(_item("info", note, label))
            continue
        if note and loop:
            continue
        if port in _SHARE_PORTS and not loop:
            shares.add(port)
        if name in _SCRIPT_HOSTS and not loop:
            scripts.append(_item("warn", "A script host is accepting network connections", label + " " + cmd))
            continue
        if not loop and name not in _WINDOWS_BASE and port not in _SHARE_PORTS and port not in _ADMIN_PORTS:
            if name not in seen_other:
                seen_other.add(name)
                others.append(_item("info", "A program is listening beyond loopback", label))
    share_items = []
    if shares:
        names = ", ".join(f"{_SHARE_PORTS[p]} ({p})" for p in sorted(shares))
        share_items.append(_item("info", "Windows file sharing is listening on the LAN", names + ". This is not a shell."))
    return {
        "shells": shells,
        "admin": admin,
        "scripts": scripts,
        "known": known,
        "shares": share_items,
        "others": others[:12],
    }


def _shell_outbound(rows: list[dict], procs: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    hits = []
    for row in rows:
        remote = str(row.get("RemoteAddress") or "")
        if is_loopback(remote) or remote in {"", "*", "0.0.0.0"}:
            continue
        try:
            pid = int(row.get("OwningProcess") or 0)
            rport = int(row.get("RemotePort") or 0)
        except (TypeError, ValueError):
            continue
        name = _exe((procs.get(pid) or {}).get("name"))
        if remote == _C2_IP:
            hits.append(_item("bad", "A connection matches a published backdoor address", f"{name} -> {remote}:{rport}"))
        else:
            hits.append(_item("info", "A shell has an outbound connection", f"{name or pid} -> {remote}:{rport}"))
    return hits[:20]


def _process_hits(procs: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    hits = []
    own = _own_pids()
    for pid, meta in procs.items():
        if pid in own:
            continue
        name = _exe(meta.get("name"))
        cmd = meta.get("cmd") or ""
        if name in _BAD_TOOLS:
            hits.append(_item("bad", f"{_BAD_TOOLS[name]} is running", f"pid {pid}"))
        elif name in _TUNNELS:
            hits.append(_item("warn", f"{_TUNNELS[name]} is running", f"pid {pid}"))
        elif name in _REMOTE_APPS:
            hits.append(_item("info", f"{_REMOTE_APPS[name]} is running", f"pid {pid}"))
        if name in _SHELLS | _SCRIPT_HOSTS and _SUSPICIOUS_CMD.search(cmd):
            hits.append(_item("bad", "A running process has a hidden download or socket command", f"{name} pid {pid}: {cmd}"))
        if _C2_IP in cmd or _C2_NAME in cmd.lower():
            hits.append(_item("bad", "A running command names a published backdoor host", f"{name} pid {pid}"))
    return hits[:25]


def _parse_logons(chunks: list[str]) -> list[dict[str, str]]:
    hits = []
    blob = "\n".join(chunks)
    if "not readable" in blob.lower() or (
        re.search(r"(?i)access is denied", blob) and "Logon Type" not in blob
    ):
        return [_item("info", "Remote sign-in log was not readable", "Security log needs an elevated scan for RDP history")]
    blocks = re.split(r"\r?\nEvent\[\d+\]:", blob)
    for block in blocks:
        if "Logon Type" not in block and "LogonType" not in block:
            continue
        when = ""
        m = re.search(r"Date:\s*(.+)", block)
        if m:
            when = m.group(1).strip()
        ip = ""
        m = re.search(r"Source Network Address:\s*(\S+)", block)
        if m:
            ip = m.group(1).strip()
        account = ""
        m = re.search(r"Account Name:\s*(\S+)", block)
        if m:
            account = m.group(1).strip()
        if ip in {"", "-", "::1", "127.0.0.1"}:
            where = "local console"
        else:
            where = ip
        hits.append(_item("warn", "Remote interactive sign-in in the last 14 days", f"{when} account {account} from {where}"))
    return hits[:15]


def _services_and_firewall(inv: dict[str, Any], rdp_allowed: bool | None) -> tuple[list[dict], list[dict], list[dict]]:
    service_rows = []
    findings = []
    for row in _as_list(inv.get("services")):
        name = str(row.get("Name") or "")
        status = str(row.get("Status") or "")
        start = str(row.get("StartType") or "")
        service_rows.append({"name": name, "status": status, "start": start})
        running = status.lower() == "running"
        if name == "TermService" and running:
            findings.append(_item("warn", "Remote Desktop service is running", start))
        elif name == "sshd" and running:
            findings.append(_item("warn", "OpenSSH Server is running", start))
        elif name == "WinRM" and running:
            findings.append(_item("warn", "Windows Remote Management is running", start))
        elif name == "RemoteRegistry" and running:
            findings.append(_item("warn", "Remote Registry is running", start))
    if rdp_allowed is True:
        findings.append(_item("warn", "Remote Desktop is allowed by Windows policy", "fDenyTSConnections=0"))
    elif rdp_allowed is False:
        findings.append(_item("ok", "Remote Desktop connections are denied by policy", ""))

    fw = []
    for row in _as_list(inv.get("firewall")):
        name = str(row.get("Name") or "")
        enabled = row.get("Enabled")
        on = enabled in (True, "True", 1, "1")
        fw.append({"name": name, "enabled": bool(on)})
        if name and not on:
            findings.append(_item("warn", f"Firewall profile {name} is off", ""))
    defender = inv.get("defender") if isinstance(inv.get("defender"), dict) else {}
    if defender:
        rtp = defender.get("RealTimeProtectionEnabled")
        if rtp in (False, "False", 0, "0"):
            findings.append(_item("warn", "Microsoft Defender real-time protection is off", ""))
        elif rtp in (True, "True", 1, "1"):
            findings.append(_item("ok", "Microsoft Defender real-time protection is on", ""))
    return service_rows, fw, findings


def scan(
    roots: list[Path] | None = None,
    *,
    inventory: dict[str, Any] | None = None,
    processes: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the local exposure check. Tests may pass inventory and processes."""
    t0 = time.time()
    notes: list[str] = []
    if inventory is None or processes is None:
        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_ps = pool.submit(_ps_inventory) if inventory is None else None
            fut_proc = pool.submit(_process_table) if processes is None else None
            fut_files = pool.submit(scan_instruction_files, roots if roots is not None else default_scan_roots())
            if fut_ps:
                inventory = fut_ps.result()
            if fut_proc:
                processes = fut_proc.result()
            files = fut_files.result()
    else:
        files = scan_instruction_files(roots if roots is not None else [])

    inventory = inventory or {}
    processes = processes or {}
    if inventory.get("error"):
        notes.append("Windows inventory incomplete: " + redact(str(inventory.get("error")), 180))

    listen_rows = _as_list(inventory.get("listen"))
    if not listen_rows:
        listen_rows = _psutil_listen()
        if listen_rows:
            notes.append("Listener list came from the local process table.")
    listeners = _classify_listeners(listen_rows, processes)
    outbound = _shell_outbound(_as_list(inventory.get("established")), processes)
    proc_hits = _process_hits(processes)
    file_hits = _known_file_hits()
    run_hits = _run_keys()
    task_hits = []
    for row in _as_list(inventory.get("tasks")):
        task_hits.append(
            _item(
                "warn",
                f"Scheduled task {row.get('Task') or ''} has a script-like action",
                f"{row.get('Execute') or ''} {row.get('Arguments') or ''}",
            )
        )
    for row in _as_list(inventory.get("dns")):
        entry = str(row.get("Entry") or "")
        if "bloonspace" in entry.lower():
            file_hits.append(_item("bad", "DNS cache names a published backdoor server", entry))

    services, firewall, svc_findings = _services_and_firewall(inventory, _rdp_allowed())
    if not listeners["admin"]:
        for row in svc_findings:
            title = row.get("title") or ""
            if row.get("severity") == "warn" and (
                title.startswith("Remote Desktop service")
                or title.startswith("OpenSSH")
                or title.startswith("Windows Remote Management")
                or title.startswith("Remote Registry")
            ):
                row["severity"] = "info"
                row["detail"] = ((row.get("detail") or "") + " Nothing is listening on that port.").strip()
    logons = _parse_logons([str(x) for x in _as_list(inventory.get("logons"))])

    items: list[dict[str, str]] = []
    items.extend(listeners["shells"])
    items.extend(listeners["admin"])
    items.extend(listeners["scripts"])
    items.extend(listeners["shares"])
    items.extend(listeners["others"])
    items.extend(outbound)
    items.extend(proc_hits)
    items.extend(file_hits)
    items.extend(run_hits)
    items.extend(task_hits)
    items.extend(files.get("hits") or [])
    items.extend(svc_findings)
    items.extend(logons)

    # C2 address on any listener or outbound row already handled. Also scan listen addresses.
    for row in _as_list(inventory.get("listen")) + _as_list(inventory.get("established")):
        remote = str(row.get("RemoteAddress") or row.get("LocalAddress") or "")
        if remote == _C2_IP:
            items.append(_item("bad", "Traffic matches a published backdoor address", remote))

    rank = {"bad": 3, "warn": 2, "info": 1, "ok": 0}
    worst = max((rank.get(i.get("severity") or "", 0) for i in items), default=0)
    if any(i.get("severity") == "bad" for i in items):
        verdict = "alert"
        headline = "Something on this PC matches a shell listener or a published intrusion indicator."
    elif any(i.get("severity") == "warn" for i in items):
        verdict = "review"
        headline = "No inbound shell listener was found. Review the warnings before treating the PC as untouched."
    else:
        verdict = "clear"
        headline = "No shell is listening on the network, and no published agent-intrusion indicator was found."

    if files.get("stoppedEarly"):
        notes.append("Agent-file walk hit its time limit. Config folders were scanned first.")

    return {
        "verdict": verdict,
        "headline": headline,
        "worst": worst,
        "shellListeners": listeners["shells"],
        "remoteAdmin": listeners["admin"],
        "scriptListeners": listeners["scripts"],
        "knownLan": listeners["known"],
        "otherListeners": listeners["others"],
        "lanSharing": listeners["shares"],
        "shellOutbound": outbound,
        "processHits": proc_hits,
        "iocHits": file_hits,
        "persistence": run_hits + task_hits,
        "agentHits": files.get("hits") or [],
        "services": services,
        "firewall": firewall,
        "defenderNotes": [i for i in svc_findings if "Defender" in i.get("title", "") or "Firewall" in i.get("title", "") or "Remote Desktop" in i.get("title", "") or "OpenSSH" in i.get("title", "") or "WinRM" in i.get("title", "") or "Remote Registry" in i.get("title", "")],
        "remoteLogons": logons,
        "serviceFindings": svc_findings,
        "filesRead": files.get("filesRead") or 0,
        "notes": notes,
        "durationMs": int((time.time() - t0) * 1000),
        "items": items,
    }


def markdown_report(data: dict[str, Any]) -> str:
    lines = [
        "# Shell and agent exposure",
        "",
        f"**Verdict:** {data.get('verdict')}",
        "",
        data.get("headline") or "",
        "",
        "This check looks for inbound shells, remote-admin listeners, startup tricks, and published 2026 agent-malware indicators. It does not change settings.",
        "",
    ]

    def section(title: str, rows: list[dict] | None) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("- None")
            lines.append("")
            return
        for row in rows:
            sev = (row.get("severity") or "info").upper()
            detail = row.get("detail") or ""
            extra = f" — {detail}" if detail else ""
            lines.append(f"- **{sev}** {row.get('title')}{extra}")
        lines.append("")

    section("Inbound shells", data.get("shellListeners"))
    section("Remote admin listeners", data.get("remoteAdmin"))
    section("Script hosts on the network", data.get("scriptListeners"))
    section("Known toolbox LAN share", data.get("knownLan"))
    section("Other programs listening beyond loopback", data.get("otherListeners"))
    section("File sharing", data.get("lanSharing"))
    section("Shells with outbound connections", data.get("shellOutbound"))
    section("Processes", data.get("processHits"))
    section("Published file and host indicators", data.get("iocHits"))
    section("Startup and scheduled tasks", data.get("persistence"))
    section("Agent instruction files", data.get("agentHits"))
    section("Remote sign-ins (14 days)", data.get("remoteLogons"))
    section("Services, firewall, Defender", data.get("serviceFindings"))
    if data.get("notes"):
        lines.append("## Notes")
        lines.append("")
        for note in data["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    lines.append(f"Instruction files read: {data.get('filesRead')}. Duration: {data.get('durationMs')} ms.")
    return "\n".join(lines)


if __name__ == "__main__":
    report = scan()
    print(markdown_report(report))
