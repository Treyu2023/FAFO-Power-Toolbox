"""
Commander live status — network probes, HTTP service discovery, credential
profiles, and status gather for on-site / remote tech work.

Credentials are stored machine-local under %LOCALAPPDATA%\\FAFO (DPAPI on Windows).
Never commit profile secrets to git.

Commander web surfaces (field-confirmed):
  - http(s)://{host}/ConfigClient.html  — Petroleum C-Store Control Center (SmartClient)
  - http(s)://{host}/JournalBrowser     — System Journal Browser
  - /cgi-bin/CGILink?cmd=validate&user=&passwd=  — Sapphire session (cookie XML)
  - /cgi-bin/CGILink?cmd=ufunctionlist&cookie=
  - /cgi-bin/CGILink?cmd=vtlogpdlist&cookie=
  - /cgi-bin/CGILink?cmd=releaseCredential&cookie=
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import network_ops as net

IS_WINDOWS = platform.system() == "Windows"

# Common site-controller / POS / management surfaces techs hit in the field
DEFAULT_COMMANDER_PORTS: list[dict[str, Any]] = [
    {"port": 80, "label": "HTTP"},
    {"port": 443, "label": "HTTPS"},
    {"port": 8080, "label": "HTTP-alt"},
    {"port": 8443, "label": "HTTPS-alt"},
    {"port": 8000, "label": "App HTTP"},
    {"port": 8444, "label": "HTTPS-alt2"},
    {"port": 5000, "label": "Service"},
    {"port": 5001, "label": "Service+1"},
    {"port": 9001, "label": "Mgmt"},
    {"port": 3389, "label": "RDP"},
    {"port": 22, "label": "SSH"},
    {"port": 445, "label": "SMB"},
    {"port": 135, "label": "RPC"},
    {"port": 9100, "label": "Print/raw"},
]

# Paths often exposed on Commander / Sapphire web UIs (field + generic)
HTTP_PROBE_PATHS = [
    "/",
    "/ConfigClient.html",
    "/JournalBrowser",
    "/JournalBrowser/",
    "/cgi-bin/CGILink?cmd=validate",
    "/login",
    "/Login",
    "/index.html",
    "/api",
    "/api/status",
    "/status",
    "/health",
    "/console",
    "/admin",
    "/sapphire",
    "/commander",
]

# Commander-specific first-class surfaces
COMMANDER_UI_PATHS = [
    {"path": "/ConfigClient.html", "label": "Config Client (web)", "key": "configClient"},
    {"path": "/JournalBrowser", "label": "Journal Browser", "key": "journalBrowser"},
    {"path": "/JournalBrowser/", "label": "Journal Browser /", "key": "journalBrowserSlash"},
]

LOGIN_POST_PATHS = [
    "/login",
    "/Login",
    "/api/login",
    "/api/auth/login",
    "/api/session",
    "/Session/Login",
    "/auth/login",
    "/cgi-bin/login",
]

# CGILink cmds used by JournalBrowser credential.js / tviewerSession.js
SAPPHIRE_CMDS_AFTER_LOGIN = ("ufunctionlist", "vtlogpdlist")


def _fafo_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FAFO"


def _profiles_index_path() -> Path:
    return _fafo_dir() / "commander-profiles.json"


def _secrets_dir() -> Path:
    d = _fafo_dir() / "Secrets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- DPAPI (Windows) password vault -----------------------------------------

def _dpapi_protect(plain: bytes) -> bytes:
    if not IS_WINDOWS:
        # Non-Windows fallback: local obfuscation only (not strong crypto)
        return base64.b64encode(plain[::-1])
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    blob_in = DATA_BLOB(len(plain), ctypes.create_string_buffer(plain, len(plain)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), "FAFO Commander", None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(encrypted: bytes) -> bytes:
    if not IS_WINDOWS:
        return base64.b64decode(encrypted)[::-1]
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _password_path(profile_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", profile_id)[:80]
    return _secrets_dir() / f"commander_{safe}.bin"


def _write_password(profile_id: str, password: str) -> None:
    _password_path(profile_id).write_bytes(_dpapi_protect(password.encode("utf-8")))


def _read_password(profile_id: str) -> str:
    path = _password_path(profile_id)
    if not path.is_file():
        return ""
    try:
        return _dpapi_unprotect(path.read_bytes()).decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return ""


def _delete_password(profile_id: str) -> None:
    path = _password_path(profile_id)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


# --- Profile index (no plaintext passwords) ---------------------------------

def _load_index() -> dict[str, Any]:
    path = _profiles_index_path()
    if not path.is_file():
        return {"schema": "FAFO.Commander.Profiles/1", "profiles": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"schema": "FAFO.Commander.Profiles/1", "profiles": []}
        data.setdefault("profiles", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"schema": "FAFO.Commander.Profiles/1", "profiles": []}


def _save_index(data: dict[str, Any]) -> None:
    path = _profiles_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = _utc_now()
    data["schema"] = "FAFO.Commander.Profiles/1"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_profiles() -> list[dict[str, Any]]:
    data = _load_index()
    out = []
    for p in data.get("profiles") or []:
        if not isinstance(p, dict):
            continue
        pid = p.get("id") or ""
        out.append(
            {
                **{k: v for k, v in p.items() if k != "password"},
                "hasPassword": bool(_read_password(pid)) if pid else False,
            }
        )
    out.sort(key=lambda x: (x.get("name") or "").lower())
    return out


def get_profile(profile_id: str, *, include_password: bool = False) -> dict[str, Any] | None:
    for p in list_profiles():
        if p.get("id") == profile_id:
            if include_password:
                p = dict(p)
                p["password"] = _read_password(profile_id)
            return p
    return None


def save_profile(
    *,
    name: str,
    host: str,
    username: str = "",
    password: str | None = None,
    profile_id: str | None = None,
    export_id: str | None = None,
    ports: list[int] | None = None,
    notes: str = "",
    keep_password_if_empty: bool = True,
) -> dict[str, Any]:
    name = (name or "").strip() or host.strip()
    host = (host or "").strip()
    if not host:
        raise ValueError("host is required")
    username = (username or "").strip()

    data = _load_index()
    profiles: list[dict[str, Any]] = list(data.get("profiles") or [])
    now = _utc_now()

    if profile_id:
        existing = next((p for p in profiles if p.get("id") == profile_id), None)
    else:
        existing = None
        profile_id = hashlib.sha1(f"{host}|{name}|{time.time()}".encode()).hexdigest()[:12]

    if existing:
        existing.update(
            {
                "name": name,
                "host": host,
                "username": username,
                "exportId": export_id or existing.get("exportId") or "",
                "ports": ports if ports is not None else existing.get("ports"),
                "notes": notes if notes is not None else existing.get("notes") or "",
                "updatedAt": now,
            }
        )
        row = existing
    else:
        row = {
            "id": profile_id,
            "name": name,
            "host": host,
            "username": username,
            "exportId": export_id or "",
            "ports": ports,
            "notes": notes or "",
            "createdAt": now,
            "updatedAt": now,
            "lastProbeAt": None,
            "lastProbeOk": None,
        }
        profiles.append(row)

    if password is not None:
        if password == "" and keep_password_if_empty and existing:
            pass  # leave stored secret
        elif password == "" and not keep_password_if_empty:
            _delete_password(profile_id)
        else:
            _write_password(profile_id, password)

    data["profiles"] = profiles
    _save_index(data)
    return get_profile(profile_id) or row


def delete_profile(profile_id: str) -> dict[str, Any]:
    data = _load_index()
    before = len(data.get("profiles") or [])
    data["profiles"] = [p for p in (data.get("profiles") or []) if p.get("id") != profile_id]
    _delete_password(profile_id)
    _save_index(data)
    return {"ok": True, "removed": before - len(data["profiles"]), "id": profile_id}


def _touch_profile_probe(profile_id: str | None, ok: bool) -> None:
    if not profile_id:
        return
    data = _load_index()
    for p in data.get("profiles") or []:
        if p.get("id") == profile_id:
            p["lastProbeAt"] = _utc_now()
            p["lastProbeOk"] = bool(ok)
            break
    _save_index(data)


# --- Network / HTTP probes --------------------------------------------------

def resolve_host(host: str) -> dict[str, Any]:
    host = host.strip()
    ips: list[str] = []
    error = None
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        for info in infos:
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except socket.gaierror as e:
        error = str(e)
    rev = ""
    if ips:
        try:
            rev = socket.gethostbyaddr(ips[0])[0]
        except (socket.herror, socket.gaierror, OSError):
            rev = ""
    return {"host": host, "ips": ips, "reverseDns": rev, "ok": bool(ips), "error": error}


def tcp_probe(host: str, port: int, timeout: float = 1.2) -> dict[str, Any]:
    t0 = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {"port": port, "open": True, "ms": round((time.time() - t0) * 1000), "error": None}
    except OSError as e:
        return {"port": port, "open": False, "ms": round((time.time() - t0) * 1000), "error": str(e)}


def scan_commander_ports(
    host: str,
    ports: list[int] | None = None,
    timeout: float = 0.9,
) -> dict[str, Any]:
    import concurrent.futures

    label_map = {d["port"]: d["label"] for d in DEFAULT_COMMANDER_PORTS}
    if ports is None:
        ports = [d["port"] for d in DEFAULT_COMMANDER_PORTS]
    ports = sorted({int(p) for p in ports if 1 <= int(p) <= 65535})[:40]
    timeout = max(0.3, min(timeout, 3.0))

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(4, len(ports)))) as pool:
        futs = {pool.submit(tcp_probe, host, p, timeout): p for p in ports}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            r["label"] = label_map.get(r["port"], "")
            results.append(r)

    results.sort(key=lambda x: x["port"])
    open_list = [r for r in results if r["open"]]
    return {
        "host": host,
        "scanned": len(ports),
        "openCount": len(open_list),
        "open": open_list,
        "all": results,
    }


def _ssl_cert_info(host: str, port: int = 443, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                # getpeercert() may be empty with CERT_NONE — use binary form
                if not cert:
                    der = ssock.getpeercert(binary_form=True)
                    return {
                        "port": port,
                        "present": bool(der),
                        "subject": None,
                        "issuer": None,
                        "notAfter": None,
                        "note": "Certificate present (details unavailable without verification context)",
                        "tlsVersion": ssock.version(),
                    }
                subject = dict(x[0] for x in cert.get("subject", ()) if x)
                issuer = dict(x[0] for x in cert.get("issuer", ()) if x)
                return {
                    "port": port,
                    "present": True,
                    "subject": subject,
                    "issuer": issuer,
                    "notAfter": cert.get("notAfter"),
                    "san": cert.get("subjectAltName"),
                    "tlsVersion": ssock.version(),
                }
    except OSError as e:
        return {"port": port, "present": False, "error": str(e)}


def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 4.0,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    hdrs = {
        "User-Agent": "FAFO-Commander-Status-HUD/1.0",
        "Accept": "text/html,application/json,*/*",
    }
    if headers:
        hdrs.update(headers)
    if username is not None:
        token = base64.b64encode(f"{username}:{password or ''}".encode()).decode("ascii")
        hdrs["Authorization"] = f"Basic {token}"

    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    # Permissive SSL for site controllers with self-signed certs
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(65536)
            text = raw.decode("utf-8", errors="replace")
            return {
                "ok": True,
                "url": url,
                "status": getattr(resp, "status", None) or resp.getcode(),
                "headers": {k: v for k, v in resp.headers.items()},
                "bodyPreview": text[:4000],
                "ms": round((time.time() - t0) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(8192)
            text = raw.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        return {
            "ok": False,
            "url": url,
            "status": e.code,
            "headers": dict(e.headers.items()) if e.headers else {},
            "bodyPreview": text[:2000],
            "ms": round((time.time() - t0) * 1000),
            "error": str(e.reason or e),
            "authRequired": e.code in (401, 403),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "url": url,
            "status": None,
            "headers": {},
            "bodyPreview": "",
            "ms": round((time.time() - t0) * 1000),
            "error": str(e),
        }


def _title_from_html(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html or "", re.I)
    return (m.group(1).strip() if m else "")[:200]


def _local_xml(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_sapphire_xml(body: str) -> dict[str, Any]:
    """Parse VFI:Response from CGILink into cookie / fault / summary fields."""
    out: dict[str, Any] = {
        "isFault": False,
        "faultCode": None,
        "faultMessage": None,
        "cookie": None,
        "rawPreview": (body or "")[:2000],
        "tags": [],
        "textFields": {},
    }
    if not body or not body.strip():
        out["isFault"] = True
        out["faultMessage"] = "Empty response"
        return out
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        out["isFault"] = True
        out["faultMessage"] = f"XML parse error: {e}"
        return out

    # Fault detection — prefer detail message over generic faultString
    fault_string = None
    detail_message = None
    for el in root.iter():
        ln = _local_xml(el.tag)
        out["tags"].append(ln)
        if ln in ("faultCode", "Fault"):
            out["isFault"] = True
        if ln == "faultCode" and el.text:
            out["faultCode"] = el.text.strip()
        if ln == "faultString" and el.text:
            fault_string = el.text.strip()
        if ln == "message" and el.text:
            detail_message = el.text.strip()
        if ln == "cookie" and el.text:
            out["cookie"] = el.text.strip()
        # Capture a few useful text leaves
        if el.text and el.text.strip() and ln not in {"Response", "Fault", "detail", "vfiFault"}:
            if ln not in out["textFields"] and len(out["textFields"]) < 40:
                out["textFields"][ln] = el.text.strip()[:500]

    out["faultMessage"] = detail_message or fault_string
    msg = (out.get("faultMessage") or "").lower()
    code = (out.get("faultCode") or "").lower()
    if "invalid credential" in msg:
        out["isFault"] = True
        out["invalidCredentials"] = True
    # Config Client / CGILink: secure actions & some logins require on-site OTP
    if (
        "otprequired" in code
        or "otp_required" in code
        or "otp required" in msg
        or "cgi portal.otprequired" in code
        or code.endswith("otprequired")
        or "CGIPortal.OTPRequired" in (out.get("faultCode") or "")
    ):
        out["isFault"] = True
        out["otpRequired"] = True
    if "otp" in msg and "required" in msg:
        out["isFault"] = True
        out["otpRequired"] = True
    return out


def _cgi_base(host: str, scheme: str = "http", port: int | None = None) -> str:
    if port is None:
        port = 443 if scheme == "https" else 80
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def sapphire_cgi_link(
    host: str,
    cmd: str,
    *,
    params: dict[str, str] | None = None,
    scheme: str = "http",
    port: int | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """
    Call Commander/Sapphire CGILink portal.
    Example: cmd=validate&user=...&passwd=... → session cookie XML
    """
    q: dict[str, str] = {"cmd": cmd}
    if params:
        q.update(params)
    base = _cgi_base(host, scheme, port)
    url = f"{base}/cgi-bin/CGILink?{urllib.parse.urlencode(q)}"
    t0 = time.time()
    status = None
    full = ""
    err = None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "FAFO-Commander-Status-HUD/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            full = resp.read(512_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            full = e.read(65536).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            full = ""
        err = str(e.reason or e)
    except Exception as e:  # noqa: BLE001
        err = str(e)
    parsed = _parse_sapphire_xml(full)
    return {
        "url": url,
        "httpStatus": status,
        "ms": round((time.time() - t0) * 1000),
        "httpError": err,
        # Full response body for journal period lists / T-logs (rawPreview is truncated)
        "body": full,
        "bodyBytes": len(full or ""),
        **parsed,
    }


# Field-tech reference: OTPs + common Manager password hygiene
OTP_GUIDANCE = {
    "configOtp": {
        "title": "Generate Config OTP (on-site register / Commander)",
        "when": (
            "Required when Config Client / CGILink returns OTPRequired, or when performing "
            "secure actions (EPS global config, some reboots, pairing, etc.)."
        ),
        "steps": [
            "On the POS sales screen: CSR Functions",
            "Maintenance Menu",
            "Option 10 or 11 — Generate / Config OTP",
            "Select Yes",
            "Read the numeric 4-digit OTP from the register display and/or Commander front panel",
            "Enter that OTP in Config Client (or this HUD) promptly — codes expire",
        ],
        "notes": [
            "OTP is almost always a 4-digit numeric code generated at the site (register or Commander).",
            "Some sites also expose Generate OTP under Security → Site Security in Config Client after login.",
            "Write the code down before leaving the register; prompts time out.",
        ],
    },
    "cSiteOtp": {
        "title": "C-Site Management OTP (cloud link)",
        "when": (
            "Used to onboard / link Commander to Verifone C-Site Management (remote cloud), "
            "not the same as every Config Client login."
        ),
        "steps": [
            "In C-Site Management portal, generate OTP for the site / onboarding flow",
            "OTP is typically emailed to the C-Site account",
            "In Config Client: Initial Setup → Connect to C-Site Management",
            "Enter C-Site email/password and the emailed OTP when prompted",
        ],
        "notes": [
            "OTP_GENERATED cloudagent settings can forward OTPs to a server URL instead of reading the register.",
        ],
    },
    "managerPassword": {
        "title": "Manager password (90-day change)",
        "when": (
            "Many sites use Config Client user Manager. Controllers often force a password change "
            "about every 90 days when you sign in."
        ),
        "steps": [
            "When prompted to change password, advance the trailing letter: A → B → C → D → E",
            "After E, cycle back to A",
            "Update the saved HUD profile password on this PC after you change it on the site",
            "If login fails with Invalid Credentials, try the next letter in the cycle or confirm the last successful letter with the tech who rotated it",
        ],
        "notes": [
            "Base pattern is site-specific (e.g. root digits + letter). Document the current letter in the profile notes only on this machine — never in git.",
            "OTP is separate from the password: 4-digit code from register/Commander when CGIPortal.OTPRequired fires.",
        ],
    },
}


def sapphire_login(
    host: str,
    username: str,
    password: str,
    *,
    otp: str | None = None,
    open_ports: list[int] | None = None,
    timeout: float = 5.0,
    gather_functions: bool = True,
    release: bool = True,
) -> dict[str, Any]:
    """
    Authenticate via CGILink validate (same path Journal Browser / Sapphire web tools use).

    Query shape (from Config Client GWT): cmd=validate&user=&passwd=&otp=
    Fault CGIPortal.OTPRequired means generate Config OTP on the register and retry with otp=.
    """
    username = (username or "").strip()
    otp = (otp or "").strip()
    if not username:
        return {"ok": False, "authenticated": False, "message": "Username required", "method": "CGILink validate"}

    # Prefer http:80 then https:443 (only ports known open when scan provided)
    ports = open_ports or []
    ordered = [("http", 80), ("https", 443), ("http", 8080), ("https", 8443)]
    candidates: list[tuple[str, int]] = []
    for scheme, port in ordered:
        if ports and port not in ports:
            continue
        candidates.append((scheme, port))
    if not candidates:
        candidates = [("http", 80)]

    attempts: list[dict[str, Any]] = []
    success: dict[str, Any] | None = None
    otp_required = False
    last_fault = None

    for scheme, port in candidates:
        params: dict[str, str] = {"user": username, "passwd": password}
        if otp:
            params["otp"] = otp
        res = sapphire_cgi_link(
            host,
            "validate",
            params=params,
            scheme=scheme,
            port=port,
            timeout=timeout,
        )
        # Redact password from logged URL for UI attempts list
        safe_url = res.get("url") or ""
        safe_url = re.sub(r"(passwd=)[^&]*", r"\1***", safe_url)
        safe_url = re.sub(r"(otp=)[^&]*", r"\1***", safe_url)
        attempts.append(
            {
                "method": "CGILink validate" + (" + OTP" if otp else ""),
                "url": safe_url,
                "status": res.get("httpStatus"),
                "ok": bool(res.get("cookie")),
                "fault": res.get("faultMessage"),
                "faultCode": res.get("faultCode"),
                "otpRequired": bool(res.get("otpRequired")),
                "ms": res.get("ms"),
            }
        )
        last_fault = res.get("faultMessage") or res.get("faultCode")
        if res.get("cookie"):
            success = {
                "scheme": scheme,
                "port": port,
                "cookie": res["cookie"],
                "baseUrl": _cgi_base(host, scheme, port),
                "configClientUrl": f"{_cgi_base(host, scheme, port)}/ConfigClient.html",
                "journalBrowserUrl": f"{_cgi_base(host, scheme, port)}/JournalBrowser",
                "usedOtp": bool(otp),
                "validate": res,
            }
            break
        if res.get("otpRequired"):
            otp_required = True
            break
        # Invalid credentials — stop (same creds won't work on other schemes)
        if res.get("invalidCredentials") or (
            res.get("faultMessage") and "invalid credential" in (res.get("faultMessage") or "").lower()
        ):
            break
        # Got a real HTTP response with a fault other than transport error — don't thrash all ports
        if res.get("httpStatus") and res.get("isFault"):
            break

    if not success:
        msg = last_fault or "Invalid credentials or CGILink unavailable"
        if otp_required:
            msg = (
                "OTP required (CGIPortal.OTPRequired). "
                "Generate Config OTP on the register (CSR → Maintenance → Generate/Config OTP), "
                "then enter the code in the OTP field and probe again."
            )
        return {
            "ok": True,
            "authenticated": False,
            "otpRequired": otp_required,
            "method": "CGILink validate",
            "success": None,
            "attempts": attempts,
            "message": msg,
            "otpGuidance": OTP_GUIDANCE,
            "configClientNote": (
                "Open web Config Client at http://{host}/ConfigClient.html "
                "(Petroleum C-Store Control Center). If login asks for OTP, generate it on-site first."
            ).format(host=host),
        }

    gathered: dict[str, Any] = {}
    if gather_functions:
        for cmd in SAPPHIRE_CMDS_AFTER_LOGIN:
            g = sapphire_cgi_link(
                host,
                cmd,
                params={"cookie": success["cookie"]},
                scheme=success["scheme"],
                port=success["port"],
                timeout=timeout,
            )
            # strip cookie from stored payload for safety in logs — keep presence only
            gathered[cmd] = {
                "ok": not g.get("isFault") or bool(g.get("cookie")),
                "isFault": g.get("isFault"),
                "faultMessage": g.get("faultMessage"),
                "faultCode": g.get("faultCode"),
                "hasCookie": bool(g.get("cookie")),
                "textFields": g.get("textFields") or {},
                "tagSample": (g.get("tags") or [])[:30],
                "rawPreview": (g.get("rawPreview") or "")[:1500],
            }
            # refresh cookie if portal rotated it
            if g.get("cookie"):
                success["cookie"] = g["cookie"]

    if release and success.get("cookie"):
        try:
            sapphire_cgi_link(
                host,
                "releaseCredential",
                params={"cookie": success["cookie"]},
                scheme=success["scheme"],
                port=success["port"],
                timeout=min(timeout, 3.0),
            )
            success["released"] = True
        except Exception:  # noqa: BLE001
            success["released"] = False

    # Do not return raw long-lived cookie to browser after release — only session proof
    cookie_present = bool(success.get("cookie"))
    public_success = {
        "method": "CGILink validate" + (" + OTP" if success.get("usedOtp") else ""),
        "scheme": success["scheme"],
        "port": success["port"],
        "baseUrl": success["baseUrl"],
        "configClientUrl": success["configClientUrl"],
        "journalBrowserUrl": success["journalBrowserUrl"],
        "sessionEstablished": cookie_present,
        "released": success.get("released"),
        "usedOtp": bool(success.get("usedOtp")),
        "evidence": "CGILink validate returned session cookie"
        + (" (with OTP)" if success.get("usedOtp") else ""),
    }

    return {
        "ok": True,
        "authenticated": True,
        "otpRequired": False,
        "method": public_success["method"],
        "success": public_success,
        "attempts": attempts,
        "sapphire": {
            "authenticated": True,
            "usedOtp": bool(success.get("usedOtp")),
            "functionGather": gathered,
            "configClientUrl": success["configClientUrl"],
            "journalBrowserUrl": success["journalBrowserUrl"],
        },
        "otpGuidance": OTP_GUIDANCE,
        "message": "Logged in via Sapphire CGILink (validate) — session cookie issued"
        + (" with OTP" if success.get("usedOtp") else ""),
        "configClientNote": (
            f"Web Config Client: {success['configClientUrl']} · "
            f"Journal Browser: {success['journalBrowserUrl']}"
        ),
    }


def detect_commander_web_ui(
    host: str,
    open_ports: list[int],
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Detect ConfigClient.html / JournalBrowser — prefer :80 then :443 only."""
    found: list[dict[str, Any]] = []
    # Limit noise/time: primary web ports only
    preferred = []
    for port in (80, 443):
        if port in open_ports:
            preferred.append(port)
    if not preferred:
        preferred = [p for p in open_ports if p in {80, 443, 8080, 8443}][:2]

    ui_paths = [
        {"path": "/ConfigClient.html", "label": "Config Client (web)", "key": "configClient"},
        {"path": "/JournalBrowser", "label": "Journal Browser", "key": "journalBrowser"},
    ]
    for port in preferred:
        scheme = "https" if port in (443, 8443, 8444) else "http"
        base = _cgi_base(host, scheme, port)
        for ui in ui_paths:
            url = base + ui["path"]
            r = _http_request(url, timeout=timeout)
            if r.get("status") == 200:
                title = _title_from_html(r.get("bodyPreview") or "")
                found.append(
                    {
                        "key": ui["key"],
                        "label": ui["label"],
                        "url": url,
                        "title": title,
                        "port": port,
                        "scheme": scheme,
                        "server": (r.get("headers") or {}).get("Server"),
                        "ms": r.get("ms"),
                    }
                )
        # If Config Client is up, CGILink is the same host's auth portal (skip slow unauthenticated validate)
        if any(f.get("key") == "configClient" and f.get("port") == port for f in found):
            found.append(
                {
                    "key": "cgiLink",
                    "label": "Sapphire CGILink",
                    "url": f"{base}/cgi-bin/CGILink",
                    "title": "CGILink portal (validate / ufunctionlist)",
                    "port": port,
                    "scheme": scheme,
                    "inferred": True,
                }
            )
    # Dedupe by url
    seen: set[str] = set()
    uniq = []
    for f in found:
        if f["url"] in seen:
            continue
        seen.add(f["url"])
        uniq.append(f)
    primary = next((f for f in uniq if f.get("key") == "configClient"), uniq[0] if uniq else None)
    return {
        "found": bool(uniq),
        "surfaces": uniq,
        "primaryConfigClientUrl": primary["url"] if primary and primary.get("key") == "configClient" else (
            next((f["url"] for f in uniq if "ConfigClient" in f.get("url", "")), None)
        ),
    }


def discover_http_services(host: str, open_ports: list[int], timeout: float = 2.0) -> list[dict[str, Any]]:
    """Probe HTTP(S) only on ports already known open (no blind 80/443 fallback)."""
    services: list[dict[str, Any]] = []
    web_set = {80, 443, 8000, 8080, 8443, 8444, 9001, 5000, 5001}
    web_ports = [p for p in open_ports if p in web_set]
    if not web_ports:
        return services

    # Prefer Commander paths first
    path_list = [
        "/",
        "/ConfigClient.html",
        "/JournalBrowser",
        "/cgi-bin/CGILink?cmd=validate",
        "/index.html",
        "/api/status",
        "/status",
        "/health",
    ]
    timeout = max(0.8, min(timeout, 3.0))

    for port in web_ports:
        if port in (443, 8443, 8444):
            schemes = ["https"]
        elif port in (80, 8080, 8000):
            schemes = ["http"]
        else:
            schemes = ["https", "http"]

        for scheme in schemes:
            base = f"{scheme}://{host}:{port}"
            root = _http_request(f"{base}/", timeout=timeout)
            if root.get("status") is None and not root.get("ok"):
                continue

            paths_hit = []
            for path in path_list:
                if path == "/":
                    r = root
                else:
                    r = _http_request(f"{base}{path}", timeout=timeout)
                if r.get("status") is not None:
                    paths_hit.append(
                        {
                            "path": path,
                            "status": r.get("status"),
                            "title": _title_from_html(r.get("bodyPreview") or ""),
                            "server": (r.get("headers") or {}).get("Server") or (r.get("headers") or {}).get("server"),
                            "authRequired": bool(r.get("authRequired")),
                            "ms": r.get("ms"),
                            "isCommanderUi": path.startswith("/ConfigClient") or path.startswith("/JournalBrowser"),
                        }
                    )

            services.append(
                {
                    "baseUrl": base,
                    "port": port,
                    "scheme": scheme,
                    "rootStatus": root.get("status"),
                    "rootTitle": _title_from_html(root.get("bodyPreview") or ""),
                    "server": (root.get("headers") or {}).get("Server") or (root.get("headers") or {}).get("server"),
                    "paths": paths_hit,
                    "configClientUrl": f"{base}/ConfigClient.html",
                    "cert": _ssl_cert_info(host, port, timeout=timeout) if scheme == "https" else None,
                }
            )
            break  # one working scheme per port
    return services


def try_http_login(
    host: str,
    username: str,
    password: str,
    open_ports: list[int] | None = None,
    timeout: float = 4.0,
    otp: str | None = None,
) -> dict[str, Any]:
    """
    Credential test: Sapphire CGILink validate (+ optional OTP) first, then generic HTTP.
    """
    username = (username or "").strip()
    if not username:
        return {
            "ok": False,
            "authenticated": False,
            "message": "Username required for login test",
            "attempts": [],
            "otpGuidance": OTP_GUIDANCE,
        }

    web_set = {80, 443, 8000, 8080, 8443, 8444, 9001}
    web_ports = [p for p in (open_ports or []) if p in web_set]

    # 1) Primary path: Sapphire CGILink (Config Client / Journal Browser auth)
    sapphire = sapphire_login(
        host,
        username,
        password,
        otp=otp,
        open_ports=web_ports or open_ports,
        timeout=timeout,
        gather_functions=True,
        release=True,
    )
    if sapphire.get("authenticated") or sapphire.get("otpRequired"):
        return sapphire

    if not web_ports:
        # Merge sapphire attempt info even when no ports classified as web
        return {
            "ok": True,
            "authenticated": False,
            "otpRequired": bool(sapphire.get("otpRequired")),
            "success": None,
            "attempts": sapphire.get("attempts") or [],
            "sapphire": sapphire.get("sapphire"),
            "otpGuidance": OTP_GUIDANCE,
            "message": sapphire.get("message")
            or (
                "No HTTP(S) ports open from this PC — cannot test web login. "
                "Try http://{host}/ConfigClient.html on-site."
            ).format(host=host),
            "configClientNote": (
                f"Web Config Client: http://{host}/ConfigClient.html "
                "(Petroleum C-Store Control Center)."
            ),
        }

    # 2) Fallback: generic HTTP basic / form posts (CGILink already failed)
    attempts: list[dict[str, Any]] = list(sapphire.get("attempts") or [])
    success: dict[str, Any] | None = None
    timeout = max(0.8, min(timeout, 3.5))

    for port in web_ports:
        schemes = ["https"] if port in (443, 8443, 8444) else ["http"]
        for scheme in schemes:
            base = f"{scheme}://{host}:{port}"

            bare = _http_request(f"{base}/", timeout=timeout)
            r = _http_request(f"{base}/", username=username, password=password, timeout=timeout)
            att = {
                "method": "HTTP Basic",
                "url": f"{base}/",
                "status": r.get("status"),
                "ok": False,
                "authRequired": r.get("authRequired"),
                "error": r.get("error"),
            }
            if (
                r.get("status") == 200
                and bare.get("status") in (401, 403)
            ) or (
                bare.get("authRequired") and r.get("ok") and r.get("status") and int(r["status"]) < 400
            ):
                att["ok"] = True
                success = {**att, "evidence": "Basic auth accepted where anonymous was rejected"}
            attempts.append(att)
            if success:
                break

            payloads = [
                (json.dumps({"username": username, "password": password}).encode(), "application/json"),
                (
                    f"username={urllib.parse.quote(username)}&password={urllib.parse.quote(password)}".encode(),
                    "application/x-www-form-urlencoded",
                ),
            ]
            for path in LOGIN_POST_PATHS[:4]:
                for body, ctype in payloads:
                    r = _http_request(
                        f"{base}{path}",
                        method="POST",
                        headers={"Content-Type": ctype},
                        body=body,
                        timeout=timeout,
                    )
                    st = r.get("status")
                    body_l = (r.get("bodyPreview") or "").lower()
                    looks_ok = bool(
                        st
                        and int(st) in (200, 201, 204, 302, 303)
                        and not any(x in body_l for x in ("invalid", "unauthorized", "failed", "denied"))
                    )
                    if st and int(st) < 400 and any(
                        k in body_l for k in ("token", "session", "success", "authenticated", "jwt")
                    ):
                        looks_ok = True
                    att = {
                        "method": f"POST {ctype.split('/')[-1]}",
                        "url": f"{base}{path}",
                        "status": st,
                        "ok": looks_ok,
                        "error": r.get("error"),
                    }
                    attempts.append(att)
                    if looks_ok:
                        success = {**att, "evidence": "Login POST returned success-like response"}
                        break
                if success:
                    break
            if success:
                break
        if success:
            break

    msg = (
        "Credentials accepted by an HTTP service"
        if success
        else (
            sapphire.get("message")
            or (
                "CGILink validate rejected credentials (or portal unavailable). "
                f"Open http://{host}/ConfigClient.html to sign in interactively."
            )
        )
    )
    return {
        "ok": True,
        "authenticated": bool(success),
        "otpRequired": bool(sapphire.get("otpRequired")),
        "success": success,
        "attempts": attempts[:40],
        "sapphire": sapphire.get("sapphire"),
        "otpGuidance": OTP_GUIDANCE,
        "message": msg,
        "configClientNote": (
            f"Web Config Client: http://{host}/ConfigClient.html "
            f"(Petroleum C-Store Control Center) · Journal Browser: http://{host}/JournalBrowser"
        ),
    }


def _backup_context(export_id: str | None) -> dict[str, Any] | None:
    if not export_id:
        return None
    try:
        import verifone_ops as vf

        row = vf.get_site(export_id)
        if not row:
            return None
        dossier = row.get("dossier") or {}
        survey = None
        try:
            survey = vf.get_survey(export_id)
        except Exception:  # noqa: BLE001
            survey = None
        eq = dossier.get("equipment") or {}
        return {
            "exportId": export_id,
            "customer": row.get("customer") or dossier.get("customer"),
            "displayName": row.get("display_name") or dossier.get("displayName"),
            "siteId": row.get("site_id") or dossier.get("siteId"),
            "serviceId": row.get("service_id") or dossier.get("serviceId"),
            "softwareVersion": dossier.get("softwareVersion") or row.get("softwareVersion"),
            "brand": dossier.get("brand") or row.get("brand"),
            "path": row.get("path"),
            "techFlags": row.get("techFlags") or dossier.get("techFlags") or [],
            "registerIds": dossier.get("registerIds") or [],
            "equipment": {
                "dispenserBrands": eq.get("dispenserBrands") or [],
                "dcrBrands": eq.get("dcrBrands") or [],
                "tankMonitorType": eq.get("tankMonitorType") or "",
                "mnsp": eq.get("mnsp") or {},
                "paymentNic": eq.get("paymentNic") or {},
            },
            "surveyNetwork": (survey or {}).get("network") if survey else None,
            "surveyCredentials": {
                "configClientUser": ((survey or {}).get("credentials") or {}).get("configClientUser"),
                "hasConfigClientPassword": bool(
                    ((survey or {}).get("credentials") or {}).get("configClientPassword")
                ),
                "accountCount": len(((survey or {}).get("credentials") or {}).get("accounts") or []),
            }
            if survey
            else None,
            "suggestedHost": (
                ((survey or {}).get("network") or {}).get("lanIp")
                or (eq.get("mnsp") or {}).get("hostaddr")
                or ""
            ),
        }
    except Exception as e:  # noqa: BLE001
        return {"exportId": export_id, "error": str(e)}


def gather_status(
    host: str,
    *,
    username: str = "",
    password: str = "",
    otp: str | None = None,
    ports: list[int] | None = None,
    export_id: str | None = None,
    profile_id: str | None = None,
    ping_count: int = 2,
    do_login: bool = True,
    do_http: bool = True,
    timeout: float = 1.5,
) -> dict[str, Any]:
    """Full HUD gather: resolve → ping → ports → HTTP discovery → optional login (+ OTP) → backup context."""
    host = (host or "").strip()
    if not host:
        raise ValueError("host is required")

    t0 = time.time()
    dns = resolve_host(host)
    # Prefer first resolved IP for TCP if hostname fails inconsistently
    if dns.get("ips"):
        # keep hostname for TLS SNI / HTTP Host header when possible
        pass

    ping = net.ping_host(host, count=max(1, min(ping_count, 4)), timeout_ms=int(timeout * 1000))
    port_scan = scan_commander_ports(host, ports=ports, timeout=timeout)
    open_ports = [p["port"] for p in port_scan.get("open") or []]

    http_services: list[dict[str, Any]] = []
    commander_ui: dict[str, Any] = {"found": False, "surfaces": []}
    if do_http:
        http_services = discover_http_services(host, open_ports, timeout=max(timeout, 1.5))
        commander_ui = detect_commander_web_ui(host, open_ports, timeout=max(timeout, 1.5))

    login: dict[str, Any] | None = None
    if do_login and username:
        login = try_http_login(
            host,
            username,
            password,
            open_ports=open_ports or None,
            timeout=max(timeout, 2.5),
            otp=otp,
        )

    backup = _backup_context(export_id)

    # Prefer primary Config Client URL from detection
    config_client_url = commander_ui.get("primaryConfigClientUrl") or f"http://{host}/ConfigClient.html"
    journal_url = f"http://{host}/JournalBrowser"
    for s in commander_ui.get("surfaces") or []:
        if s.get("key") == "journalBrowser":
            journal_url = s.get("url") or journal_url

    # Overall health score
    score = 0
    reasons: list[str] = []
    if ping.get("success"):
        score += 30
        reasons.append("ICMP reachable")
    else:
        reasons.append("ICMP failed (may still be firewalled)")
    if open_ports:
        score += min(30, 8 * len(open_ports))
        reasons.append(f"{len(open_ports)} open port(s)")
    else:
        reasons.append("No common Commander ports open from this PC")
    if commander_ui.get("found"):
        score += 20
        reasons.append("Config Client / Journal Browser web UI found")
    elif http_services:
        score += 10
        reasons.append(f"{len(http_services)} HTTP(S) service(s)")
    if login and login.get("authenticated"):
        score += 20
        method = login.get("method") or "login"
        succ = login.get("success")
        if isinstance(succ, dict) and succ.get("method"):
            method = succ.get("method") or method
        reasons.append(f"Login OK ({method})")
    elif login and login.get("otpRequired"):
        score += 5
        reasons.append("OTP required — generate Config OTP on register, then retry")
    elif username and login and not login.get("authenticated"):
        reasons.append("Credentials not accepted by CGILink (check user/password/OTP)")

    score = min(100, score)
    if score >= 70:
        level = "online"
    elif score >= 35:
        level = "partial"
    elif open_ports or ping.get("success"):
        level = "degraded"
    else:
        level = "offline"

    overall_ok = level in ("online", "partial")
    _touch_profile_probe(profile_id, overall_ok)

    return {
        "ok": True,
        "product": "Commander",
        "gatheredAt": _utc_now(),
        "elapsedMs": round((time.time() - t0) * 1000),
        "host": host,
        "username": username,
        "profileId": profile_id,
        "exportId": export_id,
        "health": {
            "score": score,
            "level": level,
            "reasons": reasons,
        },
        "dns": dns,
        "ping": {
            "success": ping.get("success"),
            "stats": ping.get("stats"),
            "replies": ping.get("replies"),
            "elapsed_sec": ping.get("elapsed_sec"),
        },
        "ports": port_scan,
        "httpServices": http_services,
        "commanderUi": commander_ui,
        "configClientUrl": config_client_url,
        "journalBrowserUrl": journal_url,
        "login": login,
        "otpRequired": bool(login and login.get("otpRequired")),
        "otpGuidance": OTP_GUIDANCE,
        "backup": backup,
        "importExportUtility": detect_import_export_utility(),
        "hints": [
            f"Web Config Client: {config_client_url}",
            f"Journal Browser: {journal_url}",
            "Backups: use Import-Export Utility (ImportExportUtility.exe) — NOT unins000.exe",
            "Import-Export login = same site Manager credentials as Config Client (OTP 4-digit from register if required)",
            "Login: /cgi-bin/CGILink?cmd=validate&user=&passwd=&otp= (otp when CGIPortal.OTPRequired)",
            "Config OTP: CSR Functions → Maintenance → Generate/Config OTP (often 4 digits on register/Commander face)",
            "C-Site OTP: generated in C-Site portal / email for cloud onboarding — different from Config OTP",
            "Save profiles per site — passwords are DPAPI-protected on this Windows user account only.",
        ],
    }


def suggested_targets_from_library(limit: int = 40) -> list[dict[str, Any]]:
    """Sites from the local index that have a survey LAN IP or MNSP host for quick connect."""
    try:
        import verifone_ops as vf

        sites = vf.list_sites()
    except Exception:  # noqa: BLE001
        return []

    out: list[dict[str, Any]] = []
    for s in sites:
        dossier = s.get("dossier") or {}
        eq = dossier.get("equipment") or {}
        host_guess = ""
        try:
            survey = None
            # Avoid loading every survey file if expensive — try path
            path = s.get("path")
            if path:
                survey_path = Path(path) / "survey" / "site-survey.json"
                if survey_path.is_file():
                    survey = json.loads(survey_path.read_text(encoding="utf-8"))
            if survey:
                host_guess = ((survey.get("network") or {}).get("lanIp") or "").strip()
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        if not host_guess:
            host_guess = ((eq.get("mnsp") or {}).get("hostaddr") or "").strip()
        if host_guess in ("", "0.0.0.0"):
            host_guess = ""
        out.append(
            {
                "exportId": s.get("id"),
                "customer": s.get("customer"),
                "displayName": s.get("display_name") or dossier.get("displayName"),
                "siteId": s.get("site_id") or dossier.get("siteId"),
                "softwareVersion": dossier.get("softwareVersion") or s.get("softwareVersion"),
                "suggestedHost": host_guess,
                "path": s.get("path"),
            }
        )
    # Prefer ones with a host first
    out.sort(key=lambda x: (0 if x.get("suggestedHost") else 1, (x.get("customer") or "").lower()))
    return out[:limit]


# --- Verifone Import-Export Utility (SMS/Commander config backup tool) --------

# unins000.exe is the Inno Setup uninstaller — never launch that for backups.
IMPORT_EXPORT_CANDIDATES: list[dict[str, str]] = [
    {
        "id": "import_export_utility",
        "label": "Import-Export Utility (current)",
        "exe": r"C:\Program Files\Verifone\Import-Export Utility\ImportExportUtility.exe",
        "workdir": r"C:\Program Files\Verifone\Import-Export Utility",
        "cfg": r"C:\Program Files\Verifone\Import-Export Utility\importCfg.xml",
    },
    {
        "id": "sms_import_export",
        "label": "SMS Import Export (legacy x86)",
        "exe": r"C:\Program Files (x86)\Verifone\importExportUtil\SMSImportExport.exe",
        "workdir": r"C:\Program Files (x86)\Verifone\importExportUtil",
        "cfg": r"C:\Program Files (x86)\Verifone\importExportUtil\importCfg.xml",
    },
]

IMPORT_EXPORT_GUIDANCE = {
    "title": "Verifone Import-Export Utility (site backups)",
    "uninstallerWarning": (
        "Do not run unins000.exe — that uninstalls the tool. "
        "Use ImportExportUtility.exe (or SMSImportExport.exe on older installs)."
    ),
    "login": (
        "Use the same Config Client credentials as the site (typically Manager + site password). "
        "If CGILink / Config Client needs a 4-digit OTP, generate it on the register first "
        "(CSR → Maintenance → Generate/Config OTP), then sign into Import-Export with user/password "
        "(and OTP if the utility prompts)."
    ),
    "passwordRotation": (
        "Manager password often forces a change ~every 90 days: cycle trailing letter A→B→C→D→E→A. "
        "Keep the HUD site profile password in sync after you rotate it."
    ),
    "backupWorkflow": [
        "Connect laptop to site LAN (same network as Commander).",
        "Confirm HUD can reach host (ping / Config Client URL).",
        "Launch Import-Export Utility from this HUD (or Start Menu).",
        "Log in with that site's Manager credentials (same as Config Client).",
        "Export / backup SMS config to a folder named for the site under your watched Verifone backup root.",
        "Click Sync folders in Commander Site Console so the new export is indexed.",
    ],
    "suggestedBackupRootNote": (
        "FAFO watches machine-local folders from local-paths.json (VerifoneWatchFolders). "
        "Drop new exports there (e.g. …\\Verifone Laptop storage\\NC\\{Site Name})."
    ),
}


def detect_import_export_utility() -> dict[str, Any]:
    """Locate installed Verifone Import-Export / SMS Import Export tools on this PC."""
    found: list[dict[str, Any]] = []
    for c in IMPORT_EXPORT_CANDIDATES:
        exe = Path(c["exe"])
        row = {
            **c,
            "installed": exe.is_file(),
            "exeExists": exe.is_file(),
            "cfgExists": Path(c["cfg"]).is_file() if c.get("cfg") else False,
            "workdirExists": Path(c["workdir"]).is_dir() if c.get("workdir") else False,
        }
        if row["installed"]:
            try:
                st = exe.stat()
                row["exeSize"] = st.st_size
                row["exeMtime"] = datetime.fromtimestamp(st.st_mtime).isoformat()
            except OSError:
                pass
            found.append(row)

    primary = found[0] if found else None
    # Preferred save location from FAFO watch list
    watch: list[str] = []
    try:
        import verifone_ops as vf

        watch = vf.get_watch_folders()
    except Exception:  # noqa: BLE001
        watch = []

    return {
        "ok": True,
        "installed": bool(found),
        "primary": primary,
        "tools": found,
        "allCandidates": [
            {**c, "installed": Path(c["exe"]).is_file()} for c in IMPORT_EXPORT_CANDIDATES
        ],
        "guidance": IMPORT_EXPORT_GUIDANCE,
        "suggestedBackupRoots": watch,
        "uninstallerPaths": [
            p
            for p in (
                r"C:\Program Files\Verifone\Import-Export Utility\unins000.exe",
            )
            if Path(p).is_file()
        ],
        "desktopShortcut": r"C:\Users\Public\Desktop\Import-Export Utility.lnk",
    }


def launch_import_export_utility(tool_id: str | None = None) -> dict[str, Any]:
    """
    Start ImportExportUtility.exe (or legacy SMSImportExport.exe).
    Credentials are entered in the app UI — same Manager login as the site.
    """
    info = detect_import_export_utility()
    tools = info.get("tools") or []
    if not tools:
        raise FileNotFoundError(
            "Verifone Import-Export Utility not found. Expected "
            r"C:\Program Files\Verifone\Import-Export Utility\ImportExportUtility.exe"
        )

    target = None
    if tool_id:
        target = next((t for t in tools if t.get("id") == tool_id), None)
    if not target:
        target = tools[0]

    exe = Path(target["exe"])
    if not exe.is_file():
        raise FileNotFoundError(f"Executable missing: {exe}")

    workdir = target.get("workdir") or str(exe.parent)
    # Launch detached so server is not blocked
    import subprocess

    subprocess.Popen(
        [str(exe)],
        cwd=workdir,
        shell=False,
        close_fds=True,
    )
    return {
        "ok": True,
        "launched": str(exe),
        "workdir": workdir,
        "toolId": target.get("id"),
        "label": target.get("label"),
        "loginHint": IMPORT_EXPORT_GUIDANCE["login"],
        "suggestedBackupRoots": info.get("suggestedBackupRoots") or [],
        "note": (
            "Log into Import-Export with the same site Manager credentials used for Config Client. "
            "Export into a site folder under your FAFO watched backup root, then Sync."
        ),
    }
