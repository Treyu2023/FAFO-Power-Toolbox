"""
FAFO SMS Import-Export Shell — drive Commander config export/import from the toolbox.

Two Verifone utilities exist on tech laptops:

  NEW (Base 55+ / modern WEB):
    C:\\Program Files\\Verifone\\Import-Export Utility\\ImportExportUtility.exe
    Catalog: importCfg.xml (large database list, CGIPLULink PLUs, etc.)

  LEGACY (older bases / x86 SMS pack):
    C:\\Program Files (x86)\\Verifone\\importExportUtil\\SMSImportExport.exe
    Catalog: importCfg.xml (smaller set)

Neither publishes a stable CLI. This shell:
  1) Detects both tools and picks the right catalog for the site base version
  2) Logs in with **site-specific Manager** credentials (same as Config Client)
  3) Exports / imports selected databases over CGILink / CGIPLULink
  4) Lets you choose save / import folders under FAFO watched backup roots

Does not replace the official GUI — you can still Launch either tool.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import commander_live as cl
import verifone_ops as vf

_SESSIONS: dict[str, dict[str, Any]] = {}
_SESS_LOCK = threading.Lock()
_SESSION_TTL_SEC = 45 * 60

# Preset database groups for store / tech workflows
PRESETS: dict[str, list[str]] = {
    "plu_core": ["PLUs", "poscfg", "taxratecfg", "mopcfg", "feecfg"],
    "merchandise": ["PLUs", "poscfg", "plupromocfg", "dealcfg", "menucfg", "feecfg", "taxratecfg"],
    "fuel": ["fuelcfg", "fuelsite", "fuelprices", "fueltaxex", "FPDcfg", "rcfcfg"],
    "payment": ["paymentcfg", "mopcfg", "pospaymentconfig", "epsprepaidcfg"],
    "security": ["possecurity", "roleadmin", "softkeytypesecuritycfg", "policycfg"],
    "site_info": ["supportinfo", "sapphireprop", "registercfg", "salescfg"],
}

# Friendly file names when saving exports
_CMD_FILENAME: dict[str, str] = {
    "PLUs": "PLUs.xml",
    "poscfg": "poscfg.xml",
    "paymentcfg": "paymentcfg.xml",
    "fuelcfg": "fuelcfg.xml",
    "fuelsite": "fuelsite.xml",
    "fuelprices": "fuelprices.xml",
    "supportinfo": "supportinfo.xml",
    "sapphireprop": "sapphireprop.xml",
    "registercfg": "registercfg.xml",
    "taxratecfg": "taxratecfg.xml",
    "mopcfg": "mopcfg.xml",
    "salescfg": "salescfg.xml",
    "restrictionscfg": "restrictionscfg.xml",
    "softkeycfg": "softkeycfg.xml",
    "menucfg": "menucfg.xml",
    "feecfg": "feecfg.xml",
    "dealcfg": "dealcfg.xml",
    "plupromocfg": "plupromocfg.xml",
    "Maintenance": "naxml_Maintenance.xml",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1] if ":" in tag else tag


def _fafo_dir() -> Path:
    import os

    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    d = base / "FAFO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _jobs_dir() -> Path:
    d = _fafo_dir() / "sms-ie-jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- Dual tool catalog -------------------------------------------------------

def _tool_meta() -> list[dict[str, Any]]:
    """Both utilities with generation / base-version guidance."""
    return [
        {
            "id": "import_export_utility",
            "generation": "new",
            "label": "Import-Export Utility (Base 55+)",
            "shortLabel": "New (55+)",
            "exe": r"C:\Program Files\Verifone\Import-Export Utility\ImportExportUtility.exe",
            "workdir": r"C:\Program Files\Verifone\Import-Export Utility",
            "cfg": r"C:\Program Files\Verifone\Import-Export Utility\importCfg.xml",
            "forBase": "55+",
            "notes": (
                "Current Verifone Site Management tool. Use for Commander Base 55.x / modern WEB. "
                "Larger importCfg database list (PLUs via CGIPLULink, SCO, Vista, etc.)."
            ),
        },
        {
            "id": "sms_import_export",
            "generation": "legacy",
            "label": "SMS Import Export (legacy x86)",
            "shortLabel": "Legacy",
            "exe": r"C:\Program Files (x86)\Verifone\importExportUtil\SMSImportExport.exe",
            "workdir": r"C:\Program Files (x86)\Verifone\importExportUtil",
            "cfg": r"C:\Program Files (x86)\Verifone\importExportUtil\importCfg.xml",
            "forBase": "pre-55 / older SMS packs",
            "notes": (
                "Older SMS Import Export package. Prefer only when the site is on an older base "
                "or when the new utility is not installed. Smaller database catalog."
            ),
        },
    ]


def _parse_base_version(text: str | None) -> tuple[int, int, int] | None:
    if not text:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(text))
    if not m:
        m = re.search(r"(\d+)\.(\d+)", str(text))
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), 0
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def recommend_tool_for_base(base_version: str | None) -> str:
    """Return tool id recommended for a Commander base version string."""
    ver = _parse_base_version(base_version)
    if ver and ver[0] >= 55:
        return "import_export_utility"
    if ver and ver[0] > 0 and ver[0] < 55:
        return "sms_import_export"
    # default: prefer new if installed
    for t in detect_tools().get("tools") or []:
        if t.get("id") == "import_export_utility" and t.get("installed"):
            return "import_export_utility"
    return "sms_import_export"


def detect_tools() -> dict[str, Any]:
    """Detect both Import-Export utilities and enrich with version metadata."""
    tools: list[dict[str, Any]] = []
    for meta in _tool_meta():
        exe = Path(meta["exe"])
        cfg = Path(meta["cfg"])
        row = {
            **meta,
            "installed": exe.is_file(),
            "exeExists": exe.is_file(),
            "cfgExists": cfg.is_file(),
            "workdirExists": Path(meta["workdir"]).is_dir(),
            "databaseCount": 0,
        }
        if exe.is_file():
            try:
                st = exe.stat()
                row["exeSize"] = st.st_size
                row["exeMtime"] = datetime.fromtimestamp(st.st_mtime).isoformat()
            except OSError:
                pass
        if cfg.is_file():
            try:
                cats = parse_import_cfg(str(cfg))
                row["databaseCount"] = len(cats.get("databases") or [])
            except Exception:  # noqa: BLE001
                pass
        tools.append(row)

    installed = [t for t in tools if t.get("installed")]
    new_t = next((t for t in installed if t.get("generation") == "new"), None)
    leg_t = next((t for t in installed if t.get("generation") == "legacy"), None)
    primary = new_t or (installed[0] if installed else None)

    watch: list[str] = []
    try:
        watch = vf.get_watch_folders()
    except Exception:  # noqa: BLE001
        watch = []

    ref_cfg = Path(__file__).resolve().parent / "data" / "importCfg.reference.xml"

    return {
        "ok": True,
        "installed": bool(installed),
        "bothInstalled": bool(new_t and leg_t),
        "primary": primary,
        "newTool": new_t,
        "legacyTool": leg_t,
        "tools": installed,
        "allCandidates": tools,
        "recommendedDefault": "import_export_utility" if new_t else (
            "sms_import_export" if leg_t else None
        ),
        "guidance": {
            "title": "Two Import-Export utilities",
            "dualTool": (
                "Tech laptops often have BOTH tools installed. "
                "Use the NEW Import-Export Utility for Commander Base 55+; "
                "use LEGACY SMS Import Export only for older bases / packs."
            ),
            "credentials": (
                "Login is always the **site-specific Manager** account (same as Config Client / Journal). "
                "Username is usually Manager. Password scheme (fleet default ~90%): "
                "leading A–E letter + that store's digit base (B6652990, A123456, …). "
                "Optional site label is only for folder naming — never put the password there."
            ),
            "passwordRotation": (
                "Every ~90 days Commander forces a Manager change: current → re-enter current → "
                "new → confirm new. Advance letter A→B→C→D→E→A; keep the same digit base. "
                "1 capital required; last 4 passwords blocked."
            ),
            "otp": (
                "When CGILink returns OTPRequired: CSR Functions → Maintenance → Generate/Config OTP "
                "(4-digit on register / Commander face), then login again with OTP."
            ),
            "shell": (
                "This FAFO shell exports/imports selected databases over CGILink using Manager session. "
                "You choose the save folder (under watched backup roots). "
                "You can still Launch the official GUI for either generation."
            ),
            "uninstallerWarning": "Never run unins000.exe — that uninstalls the tool.",
        },
        "suggestedBackupRoots": watch,
        "referenceCatalog": str(ref_cfg) if ref_cfg.is_file() else None,
        "presets": {k: v for k, v in PRESETS.items()},
    }


def parse_import_cfg(cfg_path: str | Path | None = None) -> dict[str, Any]:
    """Parse importCfg.xml into a list of selectable databases."""
    path = Path(cfg_path) if cfg_path else None
    if not path or not path.is_file():
        # prefer installed new tool, then legacy, then bundled reference
        for meta in _tool_meta():
            p = Path(meta["cfg"])
            if p.is_file():
                path = p
                break
        if not path or not path.is_file():
            ref = Path(__file__).resolve().parent / "data" / "importCfg.reference.xml"
            path = ref if ref.is_file() else None
    if not path or not path.is_file():
        raise FileNotFoundError("importCfg.xml not found (install Import-Export Utility or use bundled reference)")

    root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    databases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for icfg in root.iter():
        if _local(icfg.tag).lower() != "icfg":
            continue
        name = ""
        cmd = ""
        cmd_type = "CGI"
        params: dict[str, str] = {}
        for child in icfg:
            ln = _local(child.tag).lower()
            if ln == "name":
                name = (child.text or "").strip()
            elif ln == "cmd":
                cmd = (child.text or "").strip()
                cmd_type = (child.attrib.get("type") or "CGI").strip()
            elif ln == "param":
                ptype = child.attrib.get("type") or "param"
                params[ptype] = (child.text or "").strip()
        if not cmd:
            continue
        key = f"{cmd_type}:{cmd}:" + ",".join(f"{k}={v}" for k, v in sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        file_name = _CMD_FILENAME.get(cmd) or f"{cmd}.xml"
        if params.get("dataset"):
            file_name = f"naxml_{params['dataset']}.xml"
        databases.append(
            {
                "id": key,
                "name": name or cmd,
                "cmd": cmd,
                "type": cmd_type,  # CGI | CGIPLULink | NAXML
                "params": params,
                "fileName": file_name,
                "group": _guess_group(name or cmd, cmd),
            }
        )

    databases.sort(key=lambda d: (d.get("group") or "", d.get("name") or ""))
    return {
        "ok": True,
        "cfgPath": str(path),
        "count": len(databases),
        "databases": databases,
    }


def _guess_group(name: str, cmd: str) -> str:
    n = f"{name} {cmd}".lower()
    if "plu" in n:
        return "PLU / items"
    if "fuel" in n or "dcr" in n or "dispenser" in n:
        return "Fuel / DCR"
    if "payment" in n or "mop" in n or "eps" in n or "ebt" in n:
        return "Payment"
    if "tax" in n or "fee" in n or "currency" in n:
        return "Tax / fees"
    if "security" in n or "role" in n or "password" in n:
        return "Security"
    if "register" in n or "screen" in n or "softkey" in n or "banner" in n:
        return "Register / UI"
    if "naxml" in n or cmd == "Maintenance":
        return "NAXML"
    if "support" in n or "sapphire" in n or "site" in n:
        return "Site info"
    return "Other"


def databases_for_tool(tool_id: str | None = None, base_version: str | None = None) -> dict[str, Any]:
    tools = detect_tools()
    tid = tool_id or recommend_tool_for_base(base_version) or tools.get("recommendedDefault")
    meta = next((t for t in (tools.get("allCandidates") or []) if t.get("id") == tid), None)
    cfg = (meta or {}).get("cfg")
    cat = parse_import_cfg(cfg)
    cat["toolId"] = tid
    cat["tool"] = meta
    cat["recommendedToolId"] = recommend_tool_for_base(base_version)
    cat["baseVersion"] = base_version
    cat["presets"] = PRESETS
    return cat


# --- Sessions (site-specific Manager) ----------------------------------------

def _purge() -> None:
    now = time.time()
    dead = [k for k, v in _SESSIONS.items() if now - float(v.get("created", 0)) > _SESSION_TTL_SEC]
    for k in dead:
        try:
            _logout_cookie(_SESSIONS[k])
        except Exception:  # noqa: BLE001
            pass
        _SESSIONS.pop(k, None)


def _logout_cookie(sess: dict[str, Any]) -> None:
    cookie = sess.get("cookie")
    if not cookie:
        return
    try:
        cl.sapphire_cgi_link(
            sess["host"],
            "releaseCredential",
            params={"cookie": cookie},
            scheme=sess.get("scheme") or "http",
            port=sess.get("port"),
            timeout=4.0,
        )
    except Exception:  # noqa: BLE001
        pass


def _get_sess(session_id: str) -> dict[str, Any]:
    _purge()
    with _SESS_LOCK:
        sess = _SESSIONS.get(session_id)
        if not sess:
            raise KeyError("SMS IE session expired or unknown — log in with site Manager credentials again")
        return sess


def login(
    host: str,
    username: str = "Manager",
    password: str = "",
    *,
    otp: str | None = None,
    profile_id: str | None = None,
    site_number: str | None = None,
    export_id: str | None = None,
    tool_id: str | None = None,
    base_version: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Open CGILink session with **site-specific Manager** credentials.
    site_number / site label (e.g. \"Quick N Easy 1\") is for folder naming only — not the Manager password.
    """
    host = (host or "").strip()
    username = (username or "Manager").strip() or "Manager"
    if not host:
        raise ValueError("Commander host/IP required")

    if profile_id and not password:
        prof = cl.get_profile(profile_id, include_password=True)
        if prof:
            password = prof.get("password") or ""
            if prof.get("username"):
                username = prof["username"]
            if not host:
                host = prof.get("host") or host

    # Prefer http:80 like journal / Config Client
    ports_open = []
    for p in (80, 443, 8080, 8443):
        if cl.tcp_probe(host, p, timeout=0.8).get("open"):
            ports_open.append(p)
    ordered = [("http", 80), ("https", 443), ("http", 8080), ("https", 8443)]
    candidates = [(s, p) for s, p in ordered if not ports_open or p in ports_open] or [("http", 80)]

    last_fault = None
    otp_required = False
    chosen = None
    for scheme, port in candidates:
        params: dict[str, str] = {"user": username, "passwd": password or ""}
        if otp:
            params["otp"] = str(otp).strip()
        res = cl.sapphire_cgi_link(
            host, "validate", params=params, scheme=scheme, port=port, timeout=timeout
        )
        last_fault = res.get("faultMessage") or res.get("faultCode")
        if res.get("cookie"):
            chosen = {
                "scheme": scheme,
                "port": port,
                "cookie": res["cookie"],
                "baseUrl": cl._cgi_base(host, scheme, port),
            }
            break
        if res.get("otpRequired"):
            otp_required = True
            break
        if res.get("invalidCredentials"):
            break

    if not chosen:
        return {
            "ok": False,
            "authenticated": False,
            "otpRequired": otp_required,
            "message": (
                "OTP required — generate 4-digit Config OTP on register, then retry with site Manager + OTP."
                if otp_required
                else (last_fault or "Login failed — check site-specific Manager password for this store")
            ),
            "otpGuidance": cl.OTP_GUIDANCE,
            "siteNumber": site_number,
            "host": host,
        }

    # Discover allowed CGI functions (helps show what this Manager role can export)
    allowed: list[str] = []
    fl = cl.sapphire_cgi_link(
        host,
        "ufunctionlist",
        params={"cookie": chosen["cookie"]},
        scheme=chosen["scheme"],
        port=chosen["port"],
        timeout=max(timeout, 12.0),
    )
    if fl.get("cookie"):
        chosen["cookie"] = fl["cookie"]
    body = fl.get("body") or ""
    if body and not fl.get("isFault"):
        allowed = sorted(
            {
                m.group(1)
                for m in re.finditer(r">\s*([A-Za-z][A-Za-z0-9_]{1,40})\s*<", body)
                if len(m.group(1)) < 40
            }
        )

    tid = tool_id or recommend_tool_for_base(base_version)
    sid = secrets.token_hex(12)
    sess = {
        "sessionId": sid,
        "host": host,
        "username": username,
        "siteNumber": (site_number or "").strip() or None,
        "exportId": export_id,
        "toolId": tid,
        "baseVersion": base_version,
        "scheme": chosen["scheme"],
        "port": chosen["port"],
        "cookie": chosen["cookie"],
        "baseUrl": chosen["baseUrl"],
        "allowedCmds": allowed[:200],
        "created": time.time(),
        "createdAt": _utc_now(),
    }
    with _SESS_LOCK:
        _SESSIONS[sid] = sess

    cat = databases_for_tool(tid, base_version)
    return {
        "ok": True,
        "authenticated": True,
        "sessionId": sid,
        "host": host,
        "username": username,
        "siteNumber": sess["siteNumber"],
        "exportId": export_id,
        "toolId": tid,
        "tool": cat.get("tool"),
        "baseVersion": base_version,
        "databaseCount": cat.get("count"),
        "allowedCmdCount": len(allowed),
        "message": (
            f"Logged in as {username} @ {host}"
            + (f" · site {sess['siteNumber']}" if sess["siteNumber"] else "")
            + f" · using {(cat.get('tool') or {}).get('shortLabel') or tid} catalog"
            + " · credentials are site-specific Manager (same as Config Client)"
        ),
        "suggestedSavePath": suggest_save_path(site_number=sess["siteNumber"], host=host, export_id=export_id),
        "presets": PRESETS,
    }


def logout(session_id: str) -> dict[str, Any]:
    with _SESS_LOCK:
        sess = _SESSIONS.pop(session_id, None)
    if sess:
        _logout_cookie(sess)
    return {"ok": True, "message": "SMS IE session closed"}


def session_status(session_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {"ok": False, "authenticated": False}
    try:
        sess = _get_sess(session_id)
    except KeyError:
        return {"ok": False, "authenticated": False, "message": "Session expired"}
    return {
        "ok": True,
        "authenticated": True,
        "sessionId": session_id,
        "host": sess.get("host"),
        "username": sess.get("username"),
        "siteNumber": sess.get("siteNumber"),
        "toolId": sess.get("toolId"),
        "exportId": sess.get("exportId"),
    }


# --- Paths -------------------------------------------------------------------

def suggest_save_path(
    *,
    site_number: str | None = None,
    host: str | None = None,
    export_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Propose a controlled export folder under FAFO watched roots."""
    roots = []
    try:
        roots = vf.get_watch_folders() or []
    except Exception:  # noqa: BLE001
        roots = []
    if not roots:
        roots = [str(_fafo_dir() / "SMS-Exports")]

    root = Path(roots[0])
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    site_bit = re.sub(r"[^A-Za-z0-9._-]+", "_", (site_number or label or host or "site").strip())[:48]
    # Prefer existing export folder if export_id maps to a known path
    existing = None
    if export_id:
        try:
            for s in vf.list_sites():
                if s.get("id") == export_id and s.get("path"):
                    existing = s["path"]
                    break
        except Exception:  # noqa: BLE001
            pass

    folder = root / site_bit / f"export_{stamp}"
    return {
        "ok": True,
        "watchRoots": roots,
        "suggestedPath": str(folder),
        "existingExportPath": existing,
        "siteNumber": site_number,
        "note": (
            "Exports land under a FAFO watched root so Site Console can Sync/index them. "
            "You can change the path before running export."
        ),
    }


def _safe_resolve_under_roots(path: str, *, must_exist: bool = False) -> Path:
    """Allow write/read only under watched roots or FAFO appdata (prevents arbitrary path abuse)."""
    p = Path(path).expanduser().resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"Path not found: {p}")

    allowed: list[Path] = []
    try:
        for r in vf.get_watch_folders() or []:
            allowed.append(Path(r).expanduser().resolve())
    except Exception:  # noqa: BLE001
        pass
    allowed.append((_fafo_dir()).resolve())
    # also allow site export paths already known
    try:
        for s in vf.list_sites()[:200]:
            if s.get("path"):
                allowed.append(Path(s["path"]).expanduser().resolve())
    except Exception:  # noqa: BLE001
        pass

    for a in allowed:
        try:
            p.relative_to(a)
            return p
        except ValueError:
            # if parent is allowed (creating new export subfolder)
            try:
                p.parent.relative_to(a)
                return p
            except ValueError:
                continue
    raise PermissionError(
        f"Path not under a FAFO watched backup root or %LOCALAPPDATA%\\FAFO: {p}. "
        f"Allowed roots: {[str(x) for x in allowed[:8]]}"
    )


# --- Export / Import ---------------------------------------------------------

def _cgi_for_db(db: dict[str, Any]) -> str:
    t = (db.get("type") or "CGI").upper()
    if t in {"CGIPLULINK", "CGIPLU"}:
        return "CGIPLULink"
    if t in {"CGIUplink".upper(), "CGIUPLINK"}:
        return "CGIUplink"
    return "CGILink"


def _export_one(sess: dict[str, Any], db: dict[str, Any], dest_dir: Path, timeout: float) -> dict[str, Any]:
    cmd = db.get("cmd") or ""
    params: dict[str, str] = {"cookie": sess["cookie"]}
    for k, v in (db.get("params") or {}).items():
        if v and "%~" not in str(v):  # skip unresolved register placeholders
            params[k] = str(v)

    # PLUs: try CGIPLULink cmd=PLUs, fall back to vPLUs
    attempts: list[tuple[str, str]] = []
    cgi = _cgi_for_db(db)
    attempts.append((cgi, cmd))
    if cgi == "CGIPLULink":
        attempts.append(("CGIPLULink", "vPLUs"))
        attempts.append(("CGILink", "PLUs"))
    if (db.get("type") or "").upper() == "NAXML":
        attempts = [("CGILink", cmd)]

    last_err = None
    body = ""
    used = None
    for cgi_name, ccmd in attempts:
        res = cl.sapphire_cgi_request(
            sess["host"],
            ccmd,
            params=params if ccmd == cmd else {**params, **({} if ccmd == cmd else {})},
            scheme=sess.get("scheme") or "http",
            port=sess.get("port"),
            timeout=timeout,
            method="GET",
            cgi_name=cgi_name,
        )
        if res.get("cookie"):
            sess["cookie"] = res["cookie"]
            params["cookie"] = res["cookie"]
        body = res.get("body") or ""
        if res.get("httpError") and not body:
            last_err = res.get("httpError")
            continue
        if res.get("isFault") and res.get("faultCode"):
            last_err = res.get("faultMessage") or res.get("faultCode")
            # try next attempt
            continue
        if body and len(body) > 40 and not (res.get("invalidCredentials") or res.get("otpRequired")):
            used = {"cgi": cgi_name, "cmd": ccmd, "ms": res.get("ms"), "bytes": len(body)}
            break
        last_err = res.get("faultMessage") or "Empty or fault response"

    if not used:
        return {
            "ok": False,
            "name": db.get("name"),
            "cmd": cmd,
            "error": last_err or "Export failed",
        }

    fname = db.get("fileName") or _CMD_FILENAME.get(cmd) or f"{cmd}.xml"
    # sanitize
    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", fname)
    out_path = dest_dir / fname
    # avoid clobber
    if out_path.exists():
        out_path = dest_dir / f"{out_path.stem}_{secrets.token_hex(3)}{out_path.suffix}"
    if not body.lstrip().startswith("<?xml") and not body.lstrip().startswith("<"):
        # still save raw
        pass
    out_path.write_text(body, encoding="utf-8")
    return {
        "ok": True,
        "name": db.get("name"),
        "cmd": used["cmd"],
        "cgi": used["cgi"],
        "file": str(out_path),
        "fileName": out_path.name,
        "bytes": out_path.stat().st_size,
        "ms": used.get("ms"),
    }


def export_databases(
    session_id: str,
    *,
    database_ids: list[str] | None = None,
    cmds: list[str] | None = None,
    preset: str | None = None,
    save_path: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    Export selected databases to save_path (controlled folder).
    Selection: database_ids (from catalog), or cmds list, or preset name.
    """
    sess = _get_sess(session_id)
    cat = databases_for_tool(sess.get("toolId"), sess.get("baseVersion"))
    dbs = list(cat.get("databases") or [])

    selected: list[dict[str, Any]] = []
    if preset:
        want = set(PRESETS.get(preset) or [])
        if not want:
            raise ValueError(f"Unknown preset: {preset}. Known: {list(PRESETS)}")
        selected = [d for d in dbs if d.get("cmd") in want]
    elif database_ids:
        idset = set(database_ids)
        selected = [d for d in dbs if d.get("id") in idset]
    elif cmds:
        cset = {c.lower() for c in cmds}
        selected = [d for d in dbs if (d.get("cmd") or "").lower() in cset]
    else:
        raise ValueError("Select databases, cmds, or a preset")

    if not selected:
        raise ValueError("No matching databases to export")

    if save_path:
        dest = _safe_resolve_under_roots(save_path, must_exist=False)
    else:
        sug = suggest_save_path(
            site_number=sess.get("siteNumber"),
            host=sess.get("host"),
            export_id=sess.get("exportId"),
        )
        dest = Path(sug["suggestedPath"])
    dest.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for db in selected:
        results.append(_export_one(sess, db, dest, timeout=timeout))

    ok_n = sum(1 for r in results if r.get("ok"))
    job = {
        "id": secrets.token_hex(8),
        "type": "export",
        "at": _utc_now(),
        "host": sess.get("host"),
        "siteNumber": sess.get("siteNumber"),
        "toolId": sess.get("toolId"),
        "savePath": str(dest),
        "okCount": ok_n,
        "failCount": len(results) - ok_n,
        "results": results,
    }
    (_jobs_dir() / f"{job['id']}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

    return {
        "ok": ok_n > 0,
        "jobId": job["id"],
        "savePath": str(dest),
        "exported": ok_n,
        "failed": len(results) - ok_n,
        "results": results,
        "message": (
            f"Exported {ok_n}/{len(results)} database(s) to {dest}. "
            "Sync folders in Site Console to index. "
            "Login used site-specific Manager credentials."
        ),
        "nextSteps": [
            "Open the save folder and verify PLUs.xml / poscfg.xml look right",
            "Site Console → Sync folders to index the new export",
            "Edit PLUs in PLU Editor if needed, then Import selected files back",
        ],
    }


def _import_one(sess: dict[str, Any], db: dict[str, Any], file_path: Path, timeout: float) -> dict[str, Any]:
    if not file_path.is_file():
        return {"ok": False, "file": str(file_path), "error": "File missing"}
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if len(text) < 20:
        return {"ok": False, "file": str(file_path), "error": "File too small"}

    cmd = db.get("cmd") or file_path.stem
    params: dict[str, str] = {"cookie": sess["cookie"]}
    for k, v in (db.get("params") or {}).items():
        if v and "%~" not in str(v):
            params[k] = str(v)

    cgi = _cgi_for_db(db) if db else "CGILink"
    attempts = [(cgi, cmd)]
    if cgi == "CGIPLULink":
        attempts.append(("CGIPLULink", "PLUs"))
        attempts.append(("CGILink", "PLUs"))

    last_err = None
    for cgi_name, ccmd in attempts:
        res = cl.sapphire_cgi_request(
            sess["host"],
            ccmd,
            params=params,
            scheme=sess.get("scheme") or "http",
            port=sess.get("port"),
            timeout=timeout,
            method="POST",
            body=text.encode("utf-8"),
            content_type="text/xml; charset=utf-8",
            cgi_name=cgi_name,
        )
        if res.get("cookie"):
            sess["cookie"] = res["cookie"]
            params["cookie"] = res["cookie"]
        if res.get("otpRequired"):
            return {
                "ok": False,
                "file": str(file_path),
                "name": db.get("name") if db else file_path.name,
                "error": "OTP required for this action — generate Config OTP and re-login",
            }
        if res.get("invalidCredentials"):
            return {
                "ok": False,
                "file": str(file_path),
                "error": "Credentials rejected — re-login with this site's Manager password",
            }
        if res.get("isFault") and res.get("faultCode"):
            last_err = res.get("faultMessage") or res.get("faultCode")
            continue
        if res.get("httpError") and res.get("httpStatus") not in (200, 201, None):
            last_err = res.get("httpError")
            continue
        # success heuristics: no fault, or body acknowledges
        return {
            "ok": True,
            "file": str(file_path),
            "fileName": file_path.name,
            "name": (db or {}).get("name") or file_path.stem,
            "cmd": ccmd,
            "cgi": cgi_name,
            "ms": res.get("ms"),
            "responseBytes": res.get("bodyBytes"),
        }

    return {
        "ok": False,
        "file": str(file_path),
        "name": (db or {}).get("name") if db else file_path.name,
        "error": last_err or "Import failed",
    }


def _match_db_for_file(
    path: Path,
    by_cmd: dict[str, dict[str, Any]],
    by_file: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Map an on-disk XML filename to an importCfg database entry."""
    name_l = path.name.lower()
    stem_l = path.stem.lower()
    if name_l in by_file:
        return by_file[name_l]
    if stem_l in by_cmd:
        return by_cmd[stem_l]
    # Common aliases
    if name_l == "plus.xml" or stem_l == "plus":
        return by_cmd.get("plus") or {
            "name": "PLUs",
            "cmd": "PLUs",
            "type": "CGIPLULink",
            "params": {},
            "fileName": "PLUs.xml",
        }
    if stem_l.startswith("naxml_"):
        ds = path.stem[6:]  # after naxml_
        for d in by_cmd.values():
            if (d.get("params") or {}).get("dataset", "").lower() == ds.lower():
                return d
        return {
            "name": f"NAXML {ds}",
            "cmd": "Maintenance",
            "type": "NAXML",
            "params": {"dataset": ds},
            "fileName": path.name,
        }
    return {
        "name": path.stem,
        "cmd": path.stem,
        "type": "CGI",
        "params": {},
        "fileName": path.name,
    }


def import_files(
    session_id: str,
    *,
    folder: str | None = None,
    files: list[str] | None = None,
    cmds: list[str] | None = None,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """
    Import XML config files into the live Commander for this Manager session.
    Match files to catalog cmds by filename (PLUs.xml → PLUs, poscfg.xml → poscfg).
    """
    sess = _get_sess(session_id)
    cat = databases_for_tool(sess.get("toolId"), sess.get("baseVersion"))
    by_cmd = {(d.get("cmd") or "").lower(): d for d in (cat.get("databases") or [])}
    by_file = {(d.get("fileName") or "").lower(): d for d in (cat.get("databases") or [])}

    paths: list[Path] = []
    if files:
        for f in files:
            paths.append(_safe_resolve_under_roots(f, must_exist=True))
    elif folder:
        folder_p = _safe_resolve_under_roots(folder, must_exist=True)
        if not folder_p.is_dir():
            raise NotADirectoryError(str(folder_p))
        paths = sorted(folder_p.glob("*.xml"))
    else:
        raise ValueError("folder or files required")

    if cmds:
        allow = {c.lower() for c in cmds}
        paths = [
            p
            for p in paths
            if p.stem.lower() in allow
            or p.name.lower().replace(".xml", "") in allow
            or any(c in p.stem.lower() for c in allow)
        ]

    if not paths:
        raise ValueError("No XML files to import")

    results: list[dict[str, Any]] = []
    for p in paths:
        db = _match_db_for_file(p, by_cmd, by_file)
        results.append(_import_one(sess, db, p, timeout))

    ok_n = sum(1 for r in results if r.get("ok"))
    job = {
        "id": secrets.token_hex(8),
        "type": "import",
        "at": _utc_now(),
        "host": sess.get("host"),
        "siteNumber": sess.get("siteNumber"),
        "toolId": sess.get("toolId"),
        "okCount": ok_n,
        "failCount": len(results) - ok_n,
        "results": results,
    }
    (_jobs_dir() / f"{job['id']}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

    return {
        "ok": ok_n > 0,
        "jobId": job["id"],
        "imported": ok_n,
        "failed": len(results) - ok_n,
        "results": results,
        "message": (
            f"Imported {ok_n}/{len(results)} file(s) to Commander @ {sess.get('host')}. "
            "Used site-specific Manager session. Verify on register / Config Client."
        ),
        "warning": (
            "Import writes live site config. Keep a protected original / safe copy before bulk PLU pushes."
        ),
    }


def list_folder_xml(folder: str) -> dict[str, Any]:
    """List importable XML files in a controlled folder."""
    p = _safe_resolve_under_roots(folder, must_exist=True)
    if not p.is_dir():
        raise NotADirectoryError(str(p))
    rows = []
    for f in sorted(p.glob("*.xml")):
        try:
            st = f.stat()
            rows.append(
                {
                    "name": f.name,
                    "path": str(f),
                    "bytes": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                }
            )
        except OSError:
            continue
    return {"ok": True, "folder": str(p), "files": rows, "count": len(rows)}


def recent_jobs(limit: int = 20) -> dict[str, Any]:
    rows = []
    for f in sorted(_jobs_dir().glob("*.json"), reverse=True)[:limit]:
        try:
            rows.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return {"ok": True, "jobs": rows, "count": len(rows)}
