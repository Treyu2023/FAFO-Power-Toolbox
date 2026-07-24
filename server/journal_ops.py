"""
Commander / Sapphire Journal Browser integration.

Target fleet: Verifone Commander **Base 55.02.08** (Jan 2026) with:
  OS 6.01.00 · EPS 9.06.02 · RCI 6.00.01 · **WEB 5.05.00**
  (55.x uses shared SELinux OS; Config Client / JournalBrowser are WEB package.)

Collects transaction (T-log) data via the same CGILink portal Journal Browser uses,
then supports drill-down search/filter similar to the classic SMS Journal Browser:

  Period list → Get Data → Search/Filter by register, employee, time, amount,
  description, transaction #, MOP, department, fuel position / dispenser, barcode, etc.

Protocol (field-confirmed + Verifone Roles/Functions handout + SMS Journal Browser docs):
  CGILink?cmd=validate&user=&passwd=&otp=
  CGILink?cmd=ufunctionlist&cookie=          (discover allowed cmds for role)
  CGILink?cmd=vtlogpdlist&cookie=           (View T-Log period list)
  CGILink?cmd=vtransset&filename=&period=&cookie=   (Period reports / T-log body)
  CGILink?cmd=vtranssetz&…                  (gzip compressed variant)
  CGILink?cmd=vposjournal&…                 (NAXML POSJournal)
  CGILink?cmd=vAppInfo|vsapphireprop&cookie= (optional base/web version probe)
  CGILink?cmd=releaseCredential&cookie=

Official CGI function names (Commander User Administration roles handout):
  validate, releaseCredential, ufunctionlist, vtlogpdlist, vtransset,
  vtranssetz, vposjournal, vperiodlist, vreportpdlist, findfilename

Base 55.02.08 T-log notes:
  - Cash Rounding (new in 55.02.08): T-log may include a "Rounding Adjustment" payline.
  - Role still needs vtlogpdlist + vtransset (Period Reports, masked CHD).
  - Remote Config Client / CGILink may require 4-digit Config OTP (register / 7-seg).

Offline: parse previously saved period XML exports from disk.
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

# In-memory journal sessions (cookie stays server-side — never sent to browser)
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESS_LOCK = threading.Lock()
_SESSION_TTL_SEC = 45 * 60  # 45 minutes

# Field target for this toolbox build (sites may be slightly older/newer 55.02.x)
TARGET_BASE_VERSION = "55.02.08"
TARGET_WEB_VERSION = "5.05.00"
TARGET_OS_VERSION = "6.01.00"

# Official period-fetch cmds (preferred order). Avoid inventing cmds that can
# thrash the session cookie on some firmware builds.
# On Base 55.02.x / WEB 5.05 these are the documented period-report / POSJournal cmds.
_OFFICIAL_FETCH_CMDS = ("vtransset", "vtranssetz", "vposjournal")
_LEGACY_FETCH_CMDS = ("vtlog", "getvtlog", "tlog")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1] if ":" in tag else tag


def _text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts: list[str] = []
    if el.text and el.text.strip():
        parts.append(el.text.strip())
    for c in el:
        t = _text_of(c)
        if t:
            parts.append(t)
        if c.tail and c.tail.strip():
            parts.append(c.tail.strip())
    return " ".join(parts)


def _attr_map(el: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in el.attrib.items():
        out[_local(k)] = v
    return out


def _child_map(el: ET.Element, depth: int = 2) -> dict[str, str]:
    """Flatten immediate (and shallow) child local-name → text for search fields."""
    out: dict[str, str] = {}
    for c in el:
        ln = _local(c.tag)
        val = (c.text or "").strip() if (c.text and not list(c)) else _text_of(c)[:200]
        if val and ln not in out:
            out[ln] = val
        if depth > 1:
            for k, v in _child_map(c, depth - 1).items():
                key = f"{ln}.{k}" if k != ln else k
                if v and key not in out:
                    out[key] = v
    return out


# --- Sessions -----------------------------------------------------------------

def _purge_expired() -> None:
    now = time.time()
    dead = [k for k, v in _SESSIONS.items() if now - float(v.get("created", 0)) > _SESSION_TTL_SEC]
    for k in dead:
        try:
            _release_session_cookie(_SESSIONS[k])
        except Exception:  # noqa: BLE001
            pass
        _SESSIONS.pop(k, None)


def _release_session_cookie(sess: dict[str, Any]) -> None:
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


def journal_login(
    host: str,
    username: str,
    password: str,
    *,
    otp: str | None = None,
    profile_id: str | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Open a Journal Browser CGILink session (cookie kept server-side)."""
    host = (host or "").strip()
    username = (username or "").strip()
    if not host:
        raise ValueError("host required")
    if not username:
        raise ValueError("username required")

    # Load password from profile if omitted
    if profile_id and not password:
        prof = cl.get_profile(profile_id, include_password=True)
        if prof:
            password = prof.get("password") or ""
            if not username:
                username = prof.get("username") or username

    # Discover open ports lightly
    ports_open = []
    for p in (80, 443, 8080, 8443):
        if cl.tcp_probe(host, p, timeout=0.8).get("open"):
            ports_open.append(p)

    # Prefer http:80
    ordered = [("http", 80), ("https", 443), ("http", 8080), ("https", 8443)]
    candidates = [(s, p) for s, p in ordered if not ports_open or p in ports_open] or [("http", 80)]

    last_fault = None
    otp_required = False
    chosen = None
    for scheme, port in candidates:
        params: dict[str, str] = {"user": username, "passwd": password}
        if otp:
            params["otp"] = str(otp).strip()
        res = cl.sapphire_cgi_link(host, "validate", params=params, scheme=scheme, port=port, timeout=timeout)
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
        if res.get("invalidCredentials") or (res.get("httpStatus") and res.get("isFault")):
            break

    if not chosen:
        return {
            "ok": False,
            "authenticated": False,
            "otpRequired": otp_required,
            "message": (
                "OTP required — generate 4-digit Config OTP on the register, then retry."
                if otp_required
                else (last_fault or "Login failed")
            ),
            "otpGuidance": cl.OTP_GUIDANCE,
        }

    # Best-effort Base 55.02.x version probe (vAppInfo / vsapphireprop)
    site_version = _probe_site_version(
        host,
        chosen["cookie"],
        scheme=chosen["scheme"],
        port=chosen["port"],
        timeout=min(timeout, 8.0),
    )
    if site_version.get("cookie"):
        chosen["cookie"] = site_version["cookie"]

    # Discover which CGI functions this role may call (ufunctionlist).
    # Used later to prefer allowed T-log fetch cmds (vtransset / vposjournal / …).
    allowed_cmds: list[str] = []
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
    fl_xml = fl.get("body") or fl.get("rawPreview") or ""
    if fl_xml and not (fl.get("isFault") and "permission" in (fl.get("faultMessage") or "").lower()):
        allowed_cmds = _parse_function_list(fl_xml)

    # Confirm journal function available — View T-Log period list
    pd = cl.sapphire_cgi_link(
        host,
        "vtlogpdlist",
        params={"cookie": chosen["cookie"]},
        scheme=chosen["scheme"],
        port=chosen["port"],
        timeout=max(timeout, 15.0),
    )
    # cookie may rotate
    if pd.get("cookie"):
        chosen["cookie"] = pd["cookie"]

    periods = []
    pd_xml = pd.get("body") or pd.get("rawPreview") or ""
    if not pd.get("isFault") or (pd_xml and "period" in pd_xml.lower()):
        periods = parse_period_list(pd_xml)

    # Fallback period lists when vtlogpdlist is empty/faulted but role has report lists
    if not periods and allowed_cmds:
        for alt_cmd in ("vperiodlist", "vreportpdlist"):
            if allowed_cmds and alt_cmd not in allowed_cmds and allowed_cmds:
                # if we have a list and cmd is absent, still try once (some builds omit names)
                pass
            alt = cl.sapphire_cgi_link(
                host,
                alt_cmd,
                params={"cookie": chosen["cookie"]},
                scheme=chosen["scheme"],
                port=chosen["port"],
                timeout=max(timeout, 15.0),
            )
            if alt.get("cookie"):
                chosen["cookie"] = alt["cookie"]
            alt_xml = alt.get("body") or alt.get("rawPreview") or ""
            periods = parse_period_list(alt_xml)
            if periods:
                pd = alt
                pd_xml = alt_xml
                break

    sid = secrets.token_hex(16)
    with _SESS_LOCK:
        _purge_expired()
        _SESSIONS[sid] = {
            "id": sid,
            "host": host,
            "username": username,
            "scheme": chosen["scheme"],
            "port": chosen["port"],
            "cookie": chosen["cookie"],
            "baseUrl": chosen["baseUrl"],
            "created": time.time(),
            "profileId": profile_id,
            "cache": {},  # periodKey -> parsed payload
            "periods": periods,  # keep client period keys in sync
            "allowedCmds": allowed_cmds,
            "siteVersion": site_version,
        }

    period_fault = None
    if pd.get("isFault") and not periods:
        period_fault = pd.get("faultMessage") or "vtlogpdlist failed"
    elif not periods:
        period_fault = (
            "No T-log periods returned. On Base 55.02.x confirm the user role includes "
            "'View T-Log period list' (vtlogpdlist) and 'Period Reports' (vtransset). "
            "Remote sessions may need a 4-digit Config OTP from the register/Commander display."
        )

    ver_label = site_version.get("baseVersion") or f"target {TARGET_BASE_VERSION}"
    return {
        "ok": True,
        "authenticated": True,
        "sessionId": sid,
        "host": host,
        "username": username,
        "baseUrl": chosen["baseUrl"],
        "journalBrowserUrl": f"{chosen['baseUrl']}/JournalBrowser",
        "periodCount": len(periods),
        "periods": periods,
        "allowedCmds": allowed_cmds,
        "siteVersion": {
            "targetBase": TARGET_BASE_VERSION,
            "targetWeb": TARGET_WEB_VERSION,
            "baseVersion": site_version.get("baseVersion"),
            "webVersion": site_version.get("webVersion"),
            "looksLike55": site_version.get("looksLike55"),
            "notes": site_version.get("notes") or [],
        },
        "periodListFault": period_fault,
        "message": (
            f"Journal session open on base {ver_label} — {len(periods)} period(s) listed"
            if periods
            else f"Journal session open (base {ver_label}) but no periods listed ({period_fault or 'empty'})"
        ),
        "ttlSec": _SESSION_TTL_SEC,
    }


def _get_session(session_id: str) -> dict[str, Any]:
    with _SESS_LOCK:
        _purge_expired()
        sess = _SESSIONS.get(session_id)
        if not sess:
            raise KeyError("Journal session expired or unknown — log in again")
        sess["created"] = time.time()  # sliding TTL
        return sess


def journal_logout(session_id: str) -> dict[str, Any]:
    with _SESS_LOCK:
        sess = _SESSIONS.pop(session_id, None)
    if sess:
        _release_session_cookie(sess)
    return {"ok": True, "closed": bool(sess)}


def journal_periods(session_id: str, *, refresh: bool = True) -> dict[str, Any]:
    sess = _get_session(session_id)
    if not refresh and sess.get("periods"):
        return {"ok": True, "periods": sess["periods"], "cached": True}

    res = cl.sapphire_cgi_link(
        sess["host"],
        "vtlogpdlist",
        params={"cookie": sess["cookie"]},
        scheme=sess["scheme"],
        port=sess["port"],
        timeout=20.0,
    )
    if res.get("cookie"):
        sess["cookie"] = res["cookie"]
    xml_body = res.get("body") or res.get("rawPreview") or ""
    periods = parse_period_list(xml_body)
    sess["periods"] = periods
    return {
        "ok": True,
        "periods": periods,
        "count": len(periods),
        "fault": res.get("faultMessage") if res.get("isFault") and not periods else None,
        "rawPreview": xml_body[:1500] if not periods else None,
        "bodyBytes": res.get("bodyBytes") or len(xml_body),
    }


# --- Period / T-log fetch -----------------------------------------------------

def _probe_site_version(
    host: str,
    cookie: str,
    *,
    scheme: str,
    port: int | None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """
    Best-effort base/WEB version probe for Base 55.02.x sites.

    Tries vAppInfo then vsapphireprop (View App Info / Controller system properties).
    Returns dict with raw text fields + any version-like strings found.
    """
    info: dict[str, Any] = {
        "targetBase": TARGET_BASE_VERSION,
        "targetWeb": TARGET_WEB_VERSION,
        "detected": {},
        "baseVersion": None,
        "webVersion": None,
        "looksLike55": None,
        "notes": [],
    }
    text_blob = ""
    for cmd in ("vAppInfo", "vsapphireprop"):
        try:
            res = cl.sapphire_cgi_link(
                host,
                cmd,
                params={"cookie": cookie},
                scheme=scheme,
                port=port,
                timeout=timeout,
            )
        except Exception:  # noqa: BLE001
            continue
        if res.get("cookie"):
            cookie = res["cookie"]
            info["cookie"] = cookie
        body = res.get("body") or res.get("rawPreview") or ""
        if res.get("isFault") and not body:
            continue
        text_blob += "\n" + body
        # Capture useful leaves from sapphire parser
        for k, v in (res.get("textFields") or {}).items():
            if v and k not in info["detected"]:
                info["detected"][k] = v
        if body and not res.get("isFault"):
            info["sourceCmd"] = cmd
            break

    # Pull version-like tokens: 55.02.08, 055.02.08, WEB 5.05.00, etc.
    versions = re.findall(r"\b0?(\d{2}\.\d{2}\.\d{2})\b", text_blob)
    web_vers = re.findall(r"\b(?:WEB|Web|web)[\s:=_-]*(\d+\.\d+\.\d+)\b", text_blob)
    if versions:
        # Prefer 55.x if present
        pref = [v for v in versions if v.startswith("55.")]
        info["baseVersion"] = (pref or versions)[0]
    if web_vers:
        info["webVersion"] = web_vers[0]
    # Also scan detected field values
    for k, v in list(info["detected"].items()):
        kl = k.lower()
        vs = str(v)
        if not info["baseVersion"] and re.search(r"\b55\.\d{2}\.\d{2}\b", vs):
            m = re.search(r"\b(55\.\d{2}\.\d{2})\b", vs)
            if m:
                info["baseVersion"] = m.group(1)
        if "web" in kl and re.search(r"\d+\.\d+", vs) and not info["webVersion"]:
            info["webVersion"] = vs.strip()
    base = info.get("baseVersion") or ""
    if base.startswith("55."):
        info["looksLike55"] = True
        if base != TARGET_BASE_VERSION:
            info["notes"].append(
                f"Detected base {base}; toolbox tuned for {TARGET_BASE_VERSION} "
                f"(same 55.02 CGI family — usually OK)."
            )
        else:
            info["notes"].append(f"Detected base {base} (matches target).")
    elif base:
        info["looksLike55"] = False
        info["notes"].append(
            f"Detected base {base}; expected ~{TARGET_BASE_VERSION}. "
            "CGI names are usually stable, but period XML may differ."
        )
    else:
        info["notes"].append(
            f"Could not read base version (vAppInfo/vsapphireprop). "
            f"Assuming field target {TARGET_BASE_VERSION} / WEB {TARGET_WEB_VERSION}."
        )
    info["cookie"] = cookie
    return info


def _parse_function_list(xml_text: str) -> list[str]:
    """Parse ufunctionlist XML into lower-cased CGI cmd names available to the role."""
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # crude fallback: pull known cmd tokens from text
        found = re.findall(
            r"\b(vtranssetz?|vposjournal|vtlogpdlist|vperiodlist|vreportpdlist|"
            r"findfilename|validate|releaseCredential|ufunctionlist|vtlog)\b",
            xml_text,
            re.I,
        )
        return sorted({f.lower() for f in found})

    cmds: set[str] = set()
    for el in root.iter():
        ln = _local(el.tag).lower()
        # Common shapes: <function>vtransset</function>, <cmd name="vtransset"/>, text leaves
        if ln in {"function", "cmd", "name", "functionname", "cgi", "cginame", "id"}:
            val = (el.text or "").strip() or el.attrib.get("name") or el.attrib.get("cmd") or ""
            if val and re.match(r"^[A-Za-z][A-Za-z0-9_]{1,40}$", val):
                cmds.add(val.lower())
        for attr_key in ("name", "cmd", "id", "function"):
            av = el.attrib.get(attr_key) or ""
            if av and re.match(r"^[A-Za-z][A-Za-z0-9_]{1,40}$", av):
                cmds.add(av.lower())
        if el.text and re.match(r"^[A-Za-z][A-Za-z0-9_]{1,40}$", (el.text or "").strip()):
            # only keep if looks like a known CGI-ish token (starts with v/u/c or known)
            t = el.text.strip().lower()
            if t.startswith(("v", "u", "c", "diag", "allow", "get", "set", "find", "release", "notify", "send", "repeat")):
                cmds.add(t)
    return sorted(cmds)


def parse_period_list(xml_text: str) -> list[dict[str, Any]]:
    """
    Parse vtlogpdlist XML into period descriptors.

    Live Commander shape (field-confirmed):
      <periodList>
        <periodInfo>
          <vs:period sysid="1"/>
          <name>2026-07-22.416</name>
          <desc>2026-07-22 (SHIFT-416)</desc>
          <reportParameters>
            <reportParameter name="period">1</reportParameter>
            <reportParameter name="filename">2026-07-22.416</reportParameter>
          </reportParameters>
        </periodInfo>
      </periodList>
    """
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    def report_params(el: ET.Element) -> dict[str, str]:
        out: dict[str, str] = {}
        for rp in el.iter():
            if _local(rp.tag).lower() != "reportparameter":
                continue
            # name may be attribute or child
            pname = rp.attrib.get("name") or ""
            pval = (rp.text or "").strip()
            if not pname:
                # sometimes nested
                for k, v in rp.attrib.items():
                    if _local(k).lower() == "name":
                        pname = v
            if pname:
                out[pname] = pval
            # also map any child tags
            for c in rp:
                cn = _local(c.tag)
                if c.text and c.text.strip():
                    out[cn] = c.text.strip()
        return out

    def period_sysid(el: ET.Element) -> str:
        for child in el.iter():
            if _local(child.tag).lower() == "period":
                for k, v in child.attrib.items():
                    if _local(k).lower() in {"sysid", "id", "periodid"}:
                        return str(v).strip()
                if (child.text or "").strip():
                    return child.text.strip()
        return ""

    periods: list[dict[str, Any]] = []

    # Preferred: periodInfo blocks (Commander Journal Browser)
    for el in root.iter():
        if _local(el.tag).lower() != "periodinfo":
            continue
        children = _child_map(el, depth=3)
        rparams = report_params(el)
        sysid = period_sysid(el)
        name = children.get("name") or rparams.get("name") or ""
        desc = children.get("desc") or children.get("description") or ""
        filename = (
            rparams.get("filename")
            or rparams.get("file")
            or children.get("filename")
            or name
            or ""
        )
        period_num = rparams.get("period") or children.get("period") or sysid or ""
        # date/shift from name like 2026-07-22.416 or desc "2026-07-22 (SHIFT-416)"
        date = ""
        shift = ""
        m = re.match(r"(\d{4}-\d{2}-\d{2})(?:\.(\d+))?", name)
        if m:
            date = m.group(1)
            shift = m.group(2) or ""
        if not shift:
            m2 = re.search(r"SHIFT[-\s]?(\d+)", desc, re.I)
            if m2:
                shift = m2.group(1)
        if not date:
            m3 = re.search(r"(\d{4}-\d{2}-\d{2})", desc)
            if m3:
                date = m3.group(1)
        label = desc or name or filename
        if not filename and not name:
            continue
        key_src = f"{filename}|{name}|{period_num}|{sysid}|{label}"
        key = hashlib.sha1(key_src.encode("utf-8", errors="ignore")).hexdigest()[:16]
        periods.append(
            {
                "key": key,
                "label": label,
                "filename": filename,
                "name": name,
                "date": date,
                "shift": str(shift),
                "periodParam": period_num,
                "sysid": sysid,
                "reportParameters": dict(rparams),
                "raw": {**{k: v for k, v in children.items() if v}, **rparams, **({"sysid": sysid} if sysid else {})},
            }
        )

    # Fallback: older / simpler period elements
    if not periods:
        for el in root.iter():
            ln = _local(el.tag).lower()
            if ln not in {"period", "pd", "shiftperiod", "vtlogperiod", "tlogperiod"}:
                attrs = _attr_map(el)
                keys = {k.lower() for k in attrs}
                if not ({"filename", "file", "name", "period", "periodid"} & keys):
                    continue
            attrs = _attr_map(el)
            children = _child_map(el, depth=2)
            merged = {**children, **attrs}
            filename = (
                merged.get("filename")
                or merged.get("file")
                or merged.get("fileName")
                or merged.get("name")
                or merged.get("period")
                or ""
            )
            date = merged.get("date") or merged.get("beginDate") or merged.get("beginDateTime") or ""
            shift = merged.get("shift") or merged.get("shiftNumber") or merged.get("periodSeq") or merged.get("seq") or ""
            label = merged.get("label") or merged.get("display") or merged.get("desc") or ""
            if not label:
                parts = [p for p in (date, f"shift {shift}" if shift else "", filename) if p]
                label = " · ".join(parts) if parts else _local(el.tag)
            if not filename and not date:
                continue
            key_src = f"{filename}|{date}|{shift}|{label}"
            key = hashlib.sha1(key_src.encode("utf-8", errors="ignore")).hexdigest()[:16]
            periods.append(
                {
                    "key": key,
                    "label": label,
                    "filename": filename,
                    "date": date,
                    "shift": str(shift),
                    "raw": {k: v for k, v in merged.items() if v},
                }
            )

    # de-dupe by key
    seen: set[str] = set()
    uniq = []
    for p in periods:
        if p["key"] in seen:
            continue
        seen.add(p["key"])
        uniq.append(p)

    def sort_key(p: dict[str, Any]) -> str:
        # keep "current" first, then by date/name desc
        if str(p.get("filename") or "").lower() == "current" or str(p.get("name") or "").lower() == "current":
            return "9999-99-99"
        return str(p.get("date") or p.get("name") or p.get("label") or "")

    uniq.sort(key=sort_key, reverse=True)
    return uniq


def _period_fetch_attempts(
    period: dict[str, Any],
    cookie: str,
    *,
    allowed_cmds: list[str] | None = None,
) -> list[tuple[str, dict[str, str]]]:
    """Candidate CGILink cmd/param sets to retrieve a period T-log.

    Uses the same reportParameters Journal Browser / Config Client emit for the
    period (filename + period, plus any extras), and prefers official CGI cmds
    from the Verifone roles handout.
    """
    filename = (period.get("filename") or "").strip()
    date = (period.get("date") or "").strip()
    shift = (period.get("shift") or "").strip()
    raw = period.get("raw") or {}
    rparams = dict(period.get("reportParameters") or {})
    # merge raw report-ish keys
    for k in ("filename", "period", "file", "name", "shift", "date", "sysid"):
        if raw.get(k) and k not in rparams:
            rparams[k] = str(raw[k])
    attempts: list[tuple[str, dict[str, str]]] = []

    def add(cmd: str, **extra: str) -> None:
        params = {"cookie": cookie}
        params.update({k: str(v) for k, v in extra.items() if v not in (None, "")})
        attempts.append((cmd, params))

    period_param = str(
        period.get("periodParam") or rparams.get("period") or period.get("sysid") or raw.get("period") or "1"
    ).strip() or "1"
    name = str(period.get("name") or "").strip()
    fn = filename or name or rparams.get("filename") or "current"
    sysid = str(period.get("sysid") or raw.get("sysid") or "").strip()

    # Build param bundles Journal Browser typically POSTs/GETs for Get Data
    bundles: list[dict[str, str]] = []
    base = {"filename": fn, "period": period_param}
    if sysid and sysid != period_param:
        base["sysid"] = sysid
    bundles.append(dict(base))
    # Pass full reportParameters as CGI query args (native Journal Browser style)
    if rparams:
        full = {k: str(v) for k, v in rparams.items() if v not in (None, "")}
        if "filename" not in full and fn:
            full["filename"] = fn
        if "period" not in full:
            full["period"] = period_param
        bundles.append(full)
    bundles.append({"filename": fn})
    if name and name != fn:
        bundles.append({"filename": name, "period": period_param})
    if date:
        bundles.append({"period": date, **({"shift": shift} if shift else {})})
        bundles.append({"filename": fn, "date": date, **({"shift": shift} if shift else {})})

    # Prefer official cmds; optionally filter to role-allowed set when known
    official = list(_OFFICIAL_FETCH_CMDS)
    legacy = list(_LEGACY_FETCH_CMDS)
    if allowed_cmds:
        allow = {c.lower() for c in allowed_cmds}
        filtered = [c for c in official if c in allow]
        # If list is present but empty of our cmds, still try official — role lists
        # are not always complete on every build.
        if filtered:
            official = filtered + [c for c in official if c not in filtered]
        # only add legacy if explicitly present
        legacy = [c for c in legacy if c in allow]

    for cmd in official:
        for b in bundles:
            add(cmd, **b)
    for cmd in legacy:
        for b in bundles[:2]:
            add(cmd, **b)

    # de-dupe
    seen: set[str] = set()
    out = []
    for cmd, params in attempts:
        sig = cmd + "|" + "&".join(f"{k}={params[k]}" for k in sorted(params) if k != "cookie")
        if sig in seen:
            continue
        seen.add(sig)
        out.append((cmd, params))
    return out


def _looks_like_tlog_xml(preview: str) -> bool:
    if not preview or not preview.strip():
        return False
    low = preview.lower()
    markers = (
        "transaction",
        "transset",
        "<trans",
        "trheader",
        "tlog",
        "<sale",
        "saleevent",
        "begindatetime",
        "trlfuel",
        "postfuel",
        "naxml",
        "posjournal",
        "journalevent",
        "trseq",
        "trcurrtot",
    )
    if any(m in low for m in markers):
        return True
    # Empty but valid period container still counts as success (0 transactions)
    if ("transset" in low or "period" in low) and not re.search(
        r"fault|permission|invalid\s*credential", low
    ):
        if "<?xml" in low or "<transset" in low or "<period" in low:
            return True
    return False


def journal_load_period(session_id: str, period_key: str, *, force: bool = False) -> dict[str, Any]:
    """Fetch and parse one period's T-log into searchable transactions."""
    sess = _get_session(session_id)
    periods = sess.get("periods") or journal_periods(session_id).get("periods") or []
    period = next((p for p in periods if p.get("key") == period_key), None)
    if not period:
        raise FileNotFoundError(f"Period not found: {period_key}")

    if not force and period_key in (sess.get("cache") or {}):
        cached = sess["cache"][period_key]
        return {"ok": True, "cached": True, **cached}

    attempts_log: list[dict[str, Any]] = []
    raw_xml = ""
    used_cmd = None
    used_params: dict[str, str] = {}
    allowed = sess.get("allowedCmds") or []
    for cmd, params in _period_fetch_attempts(period, sess["cookie"], allowed_cmds=allowed):
        res = cl.sapphire_cgi_link(
            sess["host"],
            cmd,
            params=params,
            scheme=sess["scheme"],
            port=sess["port"],
            timeout=60.0,
        )
        if res.get("cookie"):
            sess["cookie"] = res["cookie"]
            params = dict(params)
            params["cookie"] = sess["cookie"]
        preview = res.get("body") or res.get("rawPreview") or ""
        attempts_log.append(
            {
                "cmd": cmd,
                "params": {k: v for k, v in params.items() if k != "cookie"},
                "status": res.get("httpStatus"),
                "fault": res.get("faultMessage"),
                "faultCode": res.get("faultCode"),
                "bytes": len(preview),
                "preview": (preview[:240] if preview and (res.get("isFault") or len(preview) < 400) else None),
            }
        )
        fault_l = (res.get("faultMessage") or "").lower()
        if res.get("isFault") and any(
            x in fault_l for x in ("permission", "not authorized", "not allowed", "access denied")
        ):
            continue
        if res.get("isFault") and any(
            x in fault_l for x in ("invalid", "unknown command", "unknown cmd", "not found", "no such")
        ):
            continue
        if res.get("isFault") and not _looks_like_tlog_xml(preview):
            continue
        if _looks_like_tlog_xml(preview):
            raw_xml = preview
            used_cmd = cmd
            used_params = {k: v for k, v in params.items() if k != "cookie"}
            break
        # Non-fault large XML without keyword still try parse
        if preview.strip().startswith("<?xml") and not res.get("isFault") and len(preview) > 500:
            raw_xml = preview
            used_cmd = cmd
            used_params = {k: v for k, v in params.items() if k != "cookie"}
            break

    if not raw_xml:
        # Summarize faults for the HUD
        fault_summary = []
        for a in attempts_log[:8]:
            if a.get("fault"):
                fault_summary.append(f"{a['cmd']}: {a['fault']}")
        return {
            "ok": False,
            "period": period,
            "message": (
                "Could not fetch T-log for this period. "
                "Need CGI functions vtlogpdlist + vtransset (Period Reports) on the user role. "
                "Or open http://{host}/JournalBrowser in a browser, export the period, "
                "and use offline XML load."
            ).format(host=sess.get("host") or "site"),
            "hint": (
                "Official CGI cmds: validate → vtlogpdlist → vtransset|vtranssetz|vposjournal. "
                "Manager role usually has these. OTP may be required for remote logins."
            ),
            "faults": fault_summary,
            "allowedCmds": allowed,
            "attempts": attempts_log[:20],
            "transactions": [],
            "count": 0,
        }

    parsed = parse_transactions(raw_xml)
    # Keep a small raw head for UI diagnostics (never multi-MB)
    raw_head = raw_xml[:1200] if raw_xml else ""
    n_markers = len(re.findall(r"<\s*(?:[\w.-]+:)?trans\b", raw_xml or "", flags=re.I))
    payload = {
        "period": period,
        "fetchCmd": used_cmd,
        "fetchParams": used_params,
        "transactions": parsed["transactions"],
        "count": len(parsed["transactions"]),
        "registers": parsed["registers"],
        "employees": parsed["employees"],
        "mops": parsed["mops"],
        "departments": parsed["departments"],
        "fuelPositions": parsed["fuelPositions"],
        "dispensers": parsed["dispensers"],
        "summary": parsed["summary"],
        "loadedAt": _utc_now(),
        "attempts": attempts_log[:12],
        "rawBytes": len(raw_xml),
        "transMarkers": n_markers,
        "parseNote": parsed.get("parseNote"),
        "rawHead": raw_head,
        "emptyPeriod": len(parsed["transactions"]) == 0 and _looks_like_tlog_xml(raw_xml),
    }
    sess.setdefault("cache", {})[period_key] = payload
    return {"ok": True, "cached": False, **payload}


def journal_load_xml_file(path: str) -> dict[str, Any]:
    """Offline: parse a saved T-log / period XML from disk."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    raw = p.read_text(encoding="utf-8", errors="replace")
    # period list file?
    periods = parse_period_list(raw)
    low_head = raw[:8000].lower()
    looks_like_tx = any(
        m in low_head
        for m in ("<trans", "trheader", "trseq", "saleevent", "trcurrtot", "trllinetot")
    )
    if periods and not looks_like_tx:
        return {"ok": True, "type": "periodList", "periods": periods, "path": str(p)}
    parsed = parse_transactions(raw)
    n_markers = len(re.findall(r"<\s*(?:[\w.-]+:)?trans\b", raw or "", flags=re.I))
    return {
        "ok": True,
        "type": "transactions",
        "path": str(p),
        "period": {"key": "file", "label": p.name, "filename": p.name},
        "transactions": parsed["transactions"],
        "count": len(parsed["transactions"]),
        "registers": parsed["registers"],
        "employees": parsed["employees"],
        "mops": parsed["mops"],
        "departments": parsed["departments"],
        "fuelPositions": parsed["fuelPositions"],
        "dispensers": parsed["dispensers"],
        "summary": parsed["summary"],
        "parseNote": parsed.get("parseNote"),
        "transMarkers": n_markers,
        "rawBytes": len(raw),
        "rawHead": raw[:1200],
        "loadedAt": _utc_now(),
    }


def scan_backup_journal_files(export_path: str | Path, *, max_files: int = 40) -> dict[str, Any]:
    """
    Look under a site SMS export / watched backup folder for offline T-log XML.

    Note: standard Import-Export SMS config dumps usually do NOT include journals.
    Techs sometimes drop Journal Browser / vtransset exports next to the site folder.
    """
    root = Path(export_path).expanduser()
    if not root.exists():
        return {
            "ok": False,
            "message": f"Path not found: {root}",
            "files": [],
            "smsNote": "SMS configuration backups rarely include T-log / journal XML.",
        }
    if root.is_file():
        roots = [root.parent]
        seed_files = [root]
    else:
        roots = [root]
        seed_files = []

    name_pat = re.compile(
        r"(tlog|transset|trans|journal|posjournal|pjr|period|vtlog|vtrans)",
        re.I,
    )
    content_markers = ("<trans", "trheader", "trseq", "trcurrtot", "saleevent", "trllinetot", "trline")
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def consider(p: Path, why: str) -> None:
        try:
            if not p.is_file():
                return
            key = str(p.resolve())
            if key in seen:
                return
            if p.suffix.lower() not in {".xml", ".txt", ".jnl", ".log"}:
                return
            size = p.stat().st_size
            if size < 200 or size > 80_000_000:
                return
            seen.add(key)
            head = ""
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                return
            low = head.lower()
            score = 0
            if name_pat.search(p.name):
                score += 2
            hits = [m for m in content_markers if m in low]
            score += len(hits)
            if score < 2 and why != "name":
                return
            if not hits and score < 3:
                return
            found.append(
                {
                    "path": str(p),
                    "name": p.name,
                    "bytes": size,
                    "score": score,
                    "markers": hits[:8],
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "why": why,
                }
            )
        except OSError:
            return

    for sf in seed_files:
        consider(sf, "seed")

    # shallow walk: site folder + one level of subfolders (avoid huge trees)
    for base in roots:
        try:
            for p in base.iterdir():
                if p.is_file():
                    consider(p, "name" if name_pat.search(p.name) else "scan")
                elif p.is_dir() and p.name.lower() not in {".git", "node_modules", "__pycache__"}:
                    try:
                        for p2 in p.iterdir():
                            if p2.is_file():
                                consider(p2, "name" if name_pat.search(p2.name) else "scan")
                    except OSError:
                        continue
        except OSError:
            continue

    # Prefer stronger journal signals
    found.sort(key=lambda r: (-int(r.get("score") or 0), -int(r.get("bytes") or 0)))
    found = found[: max(1, min(max_files, 80))]
    return {
        "ok": True,
        "exportPath": str(root if root.is_dir() else root.parent),
        "files": found,
        "count": len(found),
        "smsNote": (
            "SMS Import-Export config backups usually contain poscfg/PLUs/etc., not live T-logs. "
            "Use live Journal login → Get Data, or drop a Journal Browser / vtransset XML export "
            "into this site folder and click Scan backup."
        ),
    }


# --- Transaction parse / search ----------------------------------------------

# Verifone PJR / Journal Browser event roots (Petrosoft + SMS + NAXML docs)
_TX_LOCAL_NAMES = {
    "transaction",
    "trans",  # primary Verifone PJR root: <trans type="sale|void|network sale|...">
    "posTransaction",
    "posTrans",
    "trx",
    "tlogTransaction",
    "saleTransaction",
    "journalTransaction",
    # NAXML POSJournal (vposjournal) — event roots only (not nested TransactionDetail)
    "saleevent",
    "voidevent",
    "refundevent",
    "financialevent",
    "otherevent",
    "journalevent",
}

# Verifone line types (trLine @type) — used for fuel / PLU drill-down
# Base 55.02.08+ also journals cash "Rounding Adjustment" paylines when enabled.
_LINE_TYPES = {
    "plu",
    "void plu",
    "postfuel",
    "void postfuel",
    "prefuel",
    "void prefuel",
    "prefuelcompletion",
    "void prefuelcompletion",
    "dept",
    "void dept",
    "moneyorder",
    "void moneyorder",
    "rounding",
    "rounding adjustment",
    "cash rounding",
    "payline",
    "tender",
}


def _normalize_journal_xml(xml_text: str) -> str:
    """
    Make Commander / Journal Browser dumps parseable by ElementTree.

    Live CGI often returns *many* concatenated documents:
      <?xml ...?><trans>...</trans><?xml ...?><trans>...</trans>
    or bare multi-root <trans> fragments. ET rejects multi-root XML, which
    previously collapsed T-logs to 0–1 transactions with missing totals.
    """
    if not xml_text:
        return ""
    text = xml_text.lstrip("\ufeff").strip()
    if not text:
        return ""
    # Drop declarations / DOCTYPE so multi-doc streams can share one root
    text = re.sub(r"<\?xml[^?]*\?>", "", text, flags=re.I)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.I)
    text = text.strip()
    low_head = text[:800].lower()
    # Already a single-rooted container?
    if re.match(
        r"<\s*(?:[\w.-]+:)?(transset|period|periodlist|root|naxml-posjournal|journalreport|posjournal)\b",
        text,
        re.I,
    ):
        return text
    # Count event roots (Verifone PJR + NAXML)
    n_trans = len(re.findall(r"<\s*(?:[\w.-]+:)?trans\b", text, flags=re.I))
    n_events = len(
        re.findall(
            r"<\s*(?:[\w.-]+:)?(?:saleevent|voidevent|refundevent|financialevent|otherevent|journalevent)\b",
            text,
            flags=re.I,
        )
    )
    if n_trans >= 1 or n_events >= 1:
        # Always wrap multi / bare fragments so sibling <trans> are all kept
        if n_trans + n_events > 1 or not re.match(r"<\s*(?:[\w.-]+:)?trans\b", text, re.I):
            # If the stream is only events/trans (no outer wrapper), wrap
            if not re.match(
                r"<\s*(?:[\w.-]+:)?(transset|period|root|naxml|journal)",
                text,
                re.I,
            ):
                return f"<root>{text}</root>"
    # HTML / junk prefix before first tag
    m = re.search(r"<\s*(?:[\w.-]+:)?(?:trans|transset|saleevent|period)\b", text, re.I)
    if m and m.start() > 0:
        text = text[m.start() :]
        if not re.match(
            r"<\s*(?:[\w.-]+:)?(transset|period|root|naxml|journal)",
            text,
            re.I,
        ):
            n_trans = len(re.findall(r"<\s*(?:[\w.-]+:)?trans\b", text, flags=re.I))
            if n_trans >= 1:
                return f"<root>{text}</root>"
    return text


def _extract_trans_fragments(xml_text: str) -> list[str]:
    """Last-resort: pull each <trans>...</trans> (or SaleEvent) block via regex."""
    if not xml_text:
        return []
    patterns = [
        r"(<\s*(?:[\w.-]+:)?trans\b[^>]*>.*?</\s*(?:[\w.-]+:)?trans\s*>)",
        r"(<\s*(?:[\w.-]+:)?saleevent\b[^>]*>.*?</\s*(?:[\w.-]+:)?saleevent\s*>)",
        r"(<\s*(?:[\w.-]+:)?voidevent\b[^>]*>.*?</\s*(?:[\w.-]+:)?voidevent\s*>)",
        r"(<\s*(?:[\w.-]+:)?refundevent\b[^>]*>.*?</\s*(?:[\w.-]+:)?refundevent\s*>)",
    ]
    frags: list[str] = []
    for pat in patterns:
        frags.extend(re.findall(pat, xml_text, flags=re.I | re.S))
    return frags


def _parse_transactions_from_root(root: ET.Element) -> list[dict[str, Any]]:
    txs: list[dict[str, Any]] = []
    tx_names = {n.lower() for n in _TX_LOCAL_NAMES}
    for el in root.iter():
        ln = _local(el.tag)
        lnl = ln.lower()
        if lnl not in tx_names and not lnl.endswith("transaction"):
            continue
        if lnl in {"transactionlist", "transactions", "transset", "transactiondetail", "transactiondetailgroup"}:
            continue
        # Skip nested TransactionDetail-style containers inside NAXML events
        if lnl in {"transactionline", "transactionsummary"}:
            continue
        rec = _parse_one_transaction(el)
        if rec:
            txs.append(rec)
    if not txs:
        for el in root.iter():
            ln = _local(el.tag).lower()
            if ln in {"sale", "receipt", "ticket", "event"}:
                rec = _parse_one_transaction(el, force=True)
                if rec and (rec.get("amount") is not None or rec.get("transNum") or rec.get("description")):
                    txs.append(rec)
    return txs


def parse_transactions(xml_text: str) -> dict[str, Any]:
    """Parse T-log / PJR / transSet XML into flat searchable transaction records + line items."""
    empty = {
        "transactions": [],
        "registers": [],
        "employees": [],
        "mops": [],
        "departments": [],
        "fuelPositions": [],
        "dispensers": [],
        "summary": {"count": 0, "totalAmount": 0.0},
        "parseNote": None,
    }
    if not xml_text or not xml_text.strip():
        return empty

    text = _normalize_journal_xml(xml_text)
    root: ET.Element | None = None
    parse_note = None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Retry: strip decls again + force wrap
        stripped = re.sub(r"<\?xml[^?]*\?>", "", xml_text, flags=re.I)
        stripped = re.sub(r"<!DOCTYPE[^>]*>", "", stripped, flags=re.I).strip()
        try:
            root = ET.fromstring(f"<root>{stripped}</root>")
            parse_note = "wrapped-after-parse-error"
        except ET.ParseError:
            # Fragment extraction for severely broken multi-doc streams
            frags = _extract_trans_fragments(xml_text)
            if not frags:
                empty["parseNote"] = "parse-failed-no-fragments"
                return empty
            txs_fr: list[dict[str, Any]] = []
            for frag in frags:
                try:
                    el = ET.fromstring(frag)
                except ET.ParseError:
                    continue
                rec = _parse_one_transaction(el, force=True)
                if rec:
                    txs_fr.append(rec)
            if not txs_fr:
                empty["parseNote"] = "parse-failed-fragments-empty"
                return empty
            return _finalize_tx_payload(txs_fr, parse_note=f"fragment-extract:{len(frags)}")

    assert root is not None
    txs = _parse_transactions_from_root(root)

    # If single outer element absorbed everything poorly, try fragment path
    if len(txs) <= 1:
        n_markers = len(re.findall(r"<\s*(?:[\w.-]+:)?trans\b", xml_text, flags=re.I))
        if n_markers > max(1, len(txs)):
            frags = _extract_trans_fragments(xml_text)
            if len(frags) > len(txs):
                txs2: list[dict[str, Any]] = []
                for frag in frags:
                    try:
                        el = ET.fromstring(frag)
                    except ET.ParseError:
                        continue
                    rec = _parse_one_transaction(el, force=True)
                    if rec:
                        txs2.append(rec)
                if len(txs2) > len(txs):
                    txs = txs2
                    parse_note = f"fragment-recover:{len(frags)}-markers:{n_markers}"

    return _finalize_tx_payload(txs, parse_note=parse_note)


def _finalize_tx_payload(
    txs: list[dict[str, Any]], *, parse_note: str | None = None
) -> dict[str, Any]:
    registers = sorted({str(t.get("register") or "") for t in txs if t.get("register")})
    employees = sorted({str(t.get("employee") or "") for t in txs if t.get("employee")})
    mops = sorted({str(t.get("mop") or "") for t in txs if t.get("mop")})
    departments = sorted({str(t.get("department") or "") for t in txs if t.get("department")})
    fuel_pos = sorted({str(t.get("fuelPosition") or "") for t in txs if t.get("fuelPosition")})
    dispensers = sorted({str(t.get("dispenser") or "") for t in txs if t.get("dispenser")})

    total = 0.0
    sale_count = 0
    for t in txs:
        try:
            if t.get("amount") is not None:
                total += float(t.get("amount") or 0)
        except (TypeError, ValueError):
            pass
        if t.get("isSaleLike") or (t.get("amount") is not None and (t.get("eventType") or "").lower() != "journal"):
            sale_count += 1

    for i, t in enumerate(txs):
        t["rowId"] = i
        t["id"] = t.get("transNum") or f"row-{i}"

    return {
        "transactions": txs,
        "registers": [r for r in registers if r],
        "employees": [e for e in employees if e],
        "mops": [m for m in mops if m],
        "departments": [d for d in departments if d],
        "fuelPositions": [f for f in fuel_pos if f],
        "dispensers": [d for d in dispensers if d],
        "summary": {
            "count": len(txs),
            "totalAmount": round(total, 2),
            "saleLikeCount": sale_count,
            "journalEventCount": sum(1 for t in txs if (t.get("eventType") or "").lower() == "journal"),
        },
        "parseNote": parse_note,
    }


def _first(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _parse_amount(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
    return None


def _blob_get(blob: dict[str, Any], *names: str, allow_suffix: bool = False) -> str:
    """Exact-key field lookup. Short names like 'time' must NOT match beginDateTime."""
    for n in names:
        nl = n.lower()
        # 1) exact
        for k, v in blob.items():
            if k.lower() == nl and v not in (None, ""):
                return str(v).strip()
        # 2) dotted path ending with .name
        for k, v in blob.items():
            kl = k.lower()
            if kl.endswith("." + nl) and v not in (None, ""):
                return str(v).strip()
        # 3) optional loose suffix (only for longer names to avoid time⊂datetime)
        if allow_suffix and len(nl) >= 5:
            for k, v in blob.items():
                kl = k.lower()
                if kl.endswith(nl) and v not in (None, ""):
                    return str(v).strip()
    return ""


def _split_dt(date_raw: str) -> tuple[str, str]:
    """Split beginDateTime-style values into (YYYY-MM-DD, HH:MM:SS)."""
    if not date_raw:
        return "", ""
    s = date_raw.strip()
    date, time_s = "", ""
    if "T" in s:
        date, rest = s.split("T", 1)
        time_s = rest[:8]
    elif " " in s and re.match(r"\d{4}-\d{2}-\d{2}\s", s):
        date, rest = s.split(" ", 1)
        time_s = rest[:8]
    elif re.match(r"\d{4}-\d{2}-\d{2}", s):
        date = s[:10]
        if len(s) > 11:
            time_s = s[11:19]
    elif re.match(r"\d{1,2}:\d{2}", s):
        time_s = s[:8]
    return date[:10] if date else "", time_s


def _parse_one_transaction(el: ET.Element, force: bool = False) -> dict[str, Any] | None:
    attrs = _attr_map(el)
    kids = _child_map(el, depth=4)
    blob = {**kids, **attrs}
    event_type = (attrs.get("type") or attrs.get("eventType") or "").strip()  # sale, void, journal…
    if not event_type:
        # NAXML: local tag is the event type (SaleEvent → sale)
        ln = _local(el.tag)
        if ln.lower().endswith("event"):
            event_type = re.sub(r"event$", "", ln, flags=re.I).strip() or ln

    def g(*names: str, allow_suffix: bool = False) -> str:
        return _blob_get(blob, *names, allow_suffix=allow_suffix)

    # Verifone PJR: trSeq / trUniqueSN / posNum
    # termMsgSN text is often a journal sequence for type=journal — use as weak id
    term_msg = ""
    for c in el.iter():
        if _local(c.tag).lower() == "termmsgsn":
            term_msg = (c.text or "").strip()
            break
    trans_num = _first(
        g("trSeq", "transNum", "transactionNumber", "transactionNo", "ticketNumber", "trUniqueSN", "EventSequenceID", "TransactionID"),
        g("trans", "ticket"),
        attrs.get("trans"),
        attrs.get("id"),
        term_msg if (event_type or "").lower() == "journal" else "",
    )
    date_raw = _first(
        g("beginDateTime", "businessDate", "transactionDate", "EventStartDate", "EventStartDateTime", "beginDate"),
        g("date"),
    )
    date, time_from_dt = _split_dt(date_raw)
    time_s = _first(
        g("beginTime", "transactionTime", "EventStartTime", "time"),
        time_from_dt,
    )
    # If "time" accidentally still holds a datetime, re-split
    if time_s and ("T" in time_s or re.match(r"\d{4}-\d{2}-\d{2}", time_s)):
        d2, t2 = _split_dt(time_s)
        if t2:
            time_s = t2
        if d2 and not date:
            date = d2
    if not date and date_raw:
        date = date_raw[:10] if re.match(r"\d{4}-\d{2}-\d{2}", date_raw) else ""

    # Prefer numeric emp id (Journal Browser Emp ID column) over display name
    employee = ""
    cashier_pos = ""
    for c in el.iter():
        if _local(c.tag).lower() == "cashier":
            employee = _first(c.attrib.get("empNum"), c.attrib.get("sysid"), (c.text or "").strip())
            cashier_pos = _first(c.attrib.get("posNum"), c.attrib.get("register"), c.attrib.get("term"))
            break
    if not employee:
        employee = _first(
            g("empNum", "empId", "employeeId", "cashierId", "csrId", "EmployeeID", "CashierID"),
            g("employee", "cashier", "operator", "userId", "originalCashier"),
        )
    # PJR: posNum lives under trHeader/trTickNum/posNum (not cashier term attr alone)
    register = _first(
        g(
            "posNum",
            "registerId",
            "registerNumber",
            "posNumber",
            "workstation",
            "terminalId",
            "RegisterID",
            "POSCode",
            "register",
        ),
        cashier_pos,
    )
    if not register:
        for c in el.iter():
            if _local(c.tag).lower() == "termmsgsn":
                register = _first(c.attrib.get("term"), c.attrib.get("posNum"))
                if register:
                    break
    # Totals: prefer trValue/trCurrTot + trTotWTax (official PJR). Avoid bare "total"
    # which can collide with unrelated nested leaves.
    amount = _parse_amount(
        _first(
            g(
                "trCurrTot",
                "trTotWTax",
                "trSTotalizer",
                "trTotNoTax",
                "TransactionTotalGrandAmount",
                "TransactionTotalNetAmount",
                "TransactionTotalGrossAmount",
                "grandTotal",
                "transactionTotal",
                "netAmount",
                "totalAmount",
            )
        )
    )
    # Do not trust bare "amount"/"total"/"amt" at header level — too ambiguous.
    # Line totals fill in later if still missing.
    qty = ""  # filled after lines (sum of trlQty)
    mop = _first(
        g(
            "trpPaycode",
            "tenderType",
            "paymentMethod",
            "methodOfPayment",
            "TenderCode",
            "cardType",
            "fuelMOP",
            "mop",
            "tender",
        )
    )
    department = _first(g("trlDept", "departmentName", "deptName", "department", "dept"))
    barcode = _first(g("trlUPC", "itemCode", "barcode", "upc", "sku", "plu", "POSCode"))
    fuel_pos = _first(
        g(
            "fuelPosition",
            "fuelingPosition",
            "pumpNumber",
            "fuelPoint",
            "position",
            "pump",
            "fp",
            "hose",
        )
    )
    dispenser = _first(g("dispenserId", "dispenserNumber", "dispenser", "dcr", "crind", "fuelingPoint"))
    description = _first(
        g("trlDesc", "description", "transactionType", "summary", "desc", "event", "text", "name")
    )
    if not description:
        description = " ".join(x for x in (event_type, mop) if x)[:120]
    elif event_type and event_type.lower() not in description.lower():
        description = f"{event_type}: {description}"[:160]

    # line items — Verifone trLine + generic item nodes
    lines: list[dict[str, Any]] = []
    for c in el.iter():
        cln = _local(c.tag).lower()
        ca = _attr_map(c)
        line_type = (ca.get("type") or "").strip()
        is_line = (
            cln in {
                "trline",
                "item",
                "saleitem",
                "linesale",
                "linetransaction",
                "fuelline",
                "fuelsale",
                "merchandise",
                "trxline",
                "payline",
                "tenderline",
            }
            or cln.endswith("item")
            or line_type.lower().replace(" ", "") in {t.replace(" ", "") for t in _LINE_TYPES}
            # Base 55.02.08 cash rounding payline (description match)
            or "rounding" in (line_type or "").lower()
            or "rounding" in (cln or "")
        )
        if not is_line:
            continue
        if c is el:
            continue
        ck = _child_map(c, depth=3)
        cm = {**ck, **ca}

        def lg(*names: str) -> str:
            return _blob_get(cm, *names, allow_suffix=True)

        # fuel nested block (trlFuel/fuelPosition, etc.)
        fuel_pos_l = _first(lg("fuelPosition", "fuelingPosition", "position", "pump", "fp"))
        product = _first(lg("fuelProd", "product", "fuelProduct", "grade", "productName"))
        # CR #09 style in description often encodes position
        desc_l = _first(lg("trlDesc", "description", "desc", "name"))
        if not fuel_pos_l and desc_l:
            m = re.search(r"#\s*0*(\d+)", desc_l)
            if m:
                fuel_pos_l = m.group(1)
        line = {
            "type": line_type or cln,
            "description": desc_l,
            "qty": _first(lg("trlQty", "qty", "quantity", "units", "fuelVolume", "SalesQuantity")),
            "amount": _parse_amount(
                _first(lg("trlLineTot", "SalesAmount", "extendedAmount", "amount", "price", "total"))
            ),
            "unitPrice": _parse_amount(
                _first(lg("trlUnitPrice", "unitPrice", "RegularSellPrice", "sellPrice", "basePrice", "price"))
            ),
            "department": _first(lg("trlDept", "department", "dept")),
            "barcode": _first(lg("trlUPC", "barcode", "upc", "plu", "POSCode")),
            "fuelPosition": fuel_pos_l,
            "dispenser": _first(lg("dispenser", "dispenserId")),
            "product": product,
            "volume": _first(lg("fuelVolume", "volume")),
            "code": _first(lg("code", "status", "flag")),
        }
        # trlDept @number is the department code in official PJR
        if not line["department"]:
            for sub in c.iter():
                if _local(sub.tag).lower() == "trldept":
                    line["department"] = _first(sub.attrib.get("number"), (sub.text or "").strip())
                    break
        if any(v not in (None, "") for v in line.values()):
            lines.append(line)
            if not fuel_pos and fuel_pos_l:
                fuel_pos = fuel_pos_l
            if not dispenser and line.get("dispenser"):
                dispenser = str(line["dispenser"])
            if not barcode and line.get("barcode"):
                barcode = str(line["barcode"])
            if not department and line.get("department"):
                department = str(line["department"])

    if not force and not any([trans_num, amount is not None, register, employee, lines, date]):
        return None

    # pull amount from merchandise lines if header totals missing
    if amount is None and lines:
        s = 0.0
        any_a = False
        for ln in lines:
            lt = str(ln.get("type") or "").lower()
            # skip pure tender/change lines when summing
            if lt in {"payline", "tender", "trpayline"}:
                continue
            if ln.get("amount") is not None:
                s += float(ln["amount"])
                any_a = True
        if any_a:
            amount = round(s, 2)

    # transaction qty = sum of line quantities (Journal Browser style)
    qty_sum = 0.0
    qty_any = False
    for ln in lines:
        lt = str(ln.get("type") or "").lower()
        if lt in {"payline", "tender", "trpayline"}:
            continue
        qv = ln.get("qty")
        if qv in (None, ""):
            continue
        try:
            qty_sum += float(str(qv).replace(",", ""))
            qty_any = True
        except (TypeError, ValueError):
            pass
    if qty_any:
        # keep integers clean (3 not 3.0)
        qty = str(int(qty_sum)) if abs(qty_sum - int(qty_sum)) < 1e-9 else f"{qty_sum:.3f}".rstrip("0").rstrip(".")
    elif not qty:
        qty = _first(g("trlQty", "itemCount", "quantity", "units", "SalesQuantity"))

    # codes from description/lines
    codes = []
    for token in ("D", "PO", "TE", "VL"):
        if re.search(rf"\b{token}\b", description or ""):
            codes.append(token)
    for ln in lines:
        if ln.get("code") and ln["code"] not in codes:
            codes.append(str(ln["code"]))
        # Base 55.02.08 cash rounding
        desc_l = str(ln.get("description") or "").lower()
        type_l = str(ln.get("type") or "").lower()
        if "rounding" in desc_l or "rounding" in type_l:
            if "RND" not in codes:
                codes.append("RND")
            if not description or "sale" in (description or "").lower():
                description = (description + " · rounding adj" if description else "rounding adjustment")[:160]

    rounding_adj = None
    for ln in lines:
        desc_l = str(ln.get("description") or "").lower()
        type_l = str(ln.get("type") or "").lower()
        if "rounding" in desc_l or "rounding" in type_l:
            if ln.get("amount") is not None:
                try:
                    rounding_adj = (rounding_adj or 0.0) + float(ln["amount"])
                except (TypeError, ValueError):
                    pass

    return {
        "transNum": trans_num,
        "eventType": event_type or "",
        "date": date,
        "time": time_s,
        "dateTime": _first(g("beginDateTime"), f"{date} {time_s}".strip()),
        "employee": employee,
        "register": register,
        "description": description,
        "qty": qty,
        "amount": amount,
        "mop": mop,
        "department": department,
        "barcode": barcode,
        "fuelPosition": fuel_pos,
        "dispenser": dispenser,
        "codes": codes,
        "roundingAdjustment": round(rounding_adj, 2) if rounding_adj is not None else None,
        "lines": lines,
        "lineCount": len(lines),
        "isSaleLike": (event_type or "").lower() in {
            "sale", "network sale", "void", "refund sale", "refund network sale",
            "suspended sale", "suspended network sale", "nosale", "refund void",
        },
        "searchBlob": " ".join(
            str(x)
            for x in (
                trans_num,
                date,
                time_s,
                employee,
                register,
                description,
                qty,
                amount,
                mop,
                department,
                barcode,
                fuel_pos,
                dispenser,
                " ".join(codes),
                f"rounding {rounding_adj}" if rounding_adj is not None else "",
                " ".join(
                    f"{L.get('description')} {L.get('product')} {L.get('barcode')} {L.get('fuelPosition')}"
                    for L in lines
                ),
            )
            if x not in (None, "")
        ).lower(),
    }


def search_transactions(
    transactions: list[dict[str, Any]],
    criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Filter/search transactions (Journal Browser Search/Filter analogue).

    Criteria keys (all optional):
      register, employee, mop, department, fuelPosition, dispenser,
      transNum, barcode, text (free-text),
      amountMin, amountMax, timeFrom, timeTo, dateFrom, dateTo,
      hasFuel (bool), code (D/PO/TE/VL)
    """
    criteria = criteria or {}
    q = transactions
    out = []

    def match(t: dict[str, Any]) -> bool:
        if criteria.get("register") and str(t.get("register") or "") != str(criteria["register"]):
            # allow contains for multi-reg strings
            if str(criteria["register"]).lower() not in str(t.get("register") or "").lower():
                return False
        if criteria.get("employee") and str(criteria["employee"]).lower() not in str(t.get("employee") or "").lower():
            return False
        if criteria.get("mop") and str(criteria["mop"]).lower() not in str(t.get("mop") or "").lower():
            return False
        if criteria.get("department") and str(criteria["department"]).lower() not in str(t.get("department") or "").lower():
            return False
        if criteria.get("fuelPosition"):
            fp = str(criteria["fuelPosition"])
            if fp not in str(t.get("fuelPosition") or "") and not any(
                fp in str(L.get("fuelPosition") or "") for L in (t.get("lines") or [])
            ):
                return False
        if criteria.get("dispenser"):
            d = str(criteria["dispenser"]).lower()
            if d not in str(t.get("dispenser") or "").lower() and not any(
                d in str(L.get("dispenser") or "").lower() for L in (t.get("lines") or [])
            ):
                return False
        if criteria.get("transNum") and str(criteria["transNum"]) not in str(t.get("transNum") or ""):
            return False
        if criteria.get("barcode"):
            b = str(criteria["barcode"])
            if b not in str(t.get("barcode") or "") and not any(b in str(L.get("barcode") or "") for L in (t.get("lines") or [])):
                return False
        if criteria.get("code"):
            code = str(criteria["code"]).upper()
            if code not in [str(c).upper() for c in (t.get("codes") or [])]:
                return False
        if criteria.get("hasFuel") in (True, "true", "1", 1):
            if not (t.get("fuelPosition") or t.get("dispenser") or any(
                L.get("fuelPosition") or L.get("product") for L in (t.get("lines") or [])
            )):
                return False
        # amounts
        amt = t.get("amount")
        if criteria.get("amountMin") not in (None, ""):
            try:
                if amt is None or float(amt) < float(criteria["amountMin"]):
                    return False
            except (TypeError, ValueError):
                return False
        if criteria.get("amountMax") not in (None, ""):
            try:
                if amt is None or float(amt) > float(criteria["amountMax"]):
                    return False
            except (TypeError, ValueError):
                return False
        # time / date string compare (HH:MM or HH:MM:SS / YYYY-MM-DD)
        if criteria.get("timeFrom") and str(t.get("time") or "") and str(t.get("time")) < str(criteria["timeFrom"]):
            return False
        if criteria.get("timeTo") and str(t.get("time") or "") and str(t.get("time")) > str(criteria["timeTo"]):
            return False
        if criteria.get("dateFrom") and str(t.get("date") or "") and str(t.get("date")) < str(criteria["dateFrom"]):
            return False
        if criteria.get("dateTo") and str(t.get("date") or "") and str(t.get("date")) > str(criteria["dateTo"]):
            return False
        if criteria.get("text"):
            needle = str(criteria["text"]).lower().strip()
            if needle and needle not in (t.get("searchBlob") or ""):
                return False
        return True

    for t in q:
        if match(t):
            out.append(t)

    total = 0.0
    for t in out:
        try:
            total += float(t.get("amount") or 0)
        except (TypeError, ValueError):
            pass

    return {
        "ok": True,
        "count": len(out),
        "totalAmount": round(total, 2),
        "matched": out,
        "criteria": criteria,
    }


def journal_search(session_id: str, period_key: str, criteria: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ensure period loaded, then search/filter transactions."""
    loaded = journal_load_period(session_id, period_key)
    if not loaded.get("ok"):
        return loaded
    result = search_transactions(loaded.get("transactions") or [], criteria)
    return {
        "ok": True,
        "period": loaded.get("period"),
        "totalInPeriod": loaded.get("count"),
        "registers": loaded.get("registers"),
        "employees": loaded.get("employees"),
        "mops": loaded.get("mops"),
        "departments": loaded.get("departments"),
        "fuelPositions": loaded.get("fuelPositions"),
        "dispensers": loaded.get("dispensers"),
        **result,
    }


def session_status(session_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {"ok": True, "active": False}
    with _SESS_LOCK:
        _purge_expired()
        sess = _SESSIONS.get(session_id)
        if not sess:
            return {"ok": True, "active": False}
        return {
            "ok": True,
            "active": True,
            "sessionId": session_id,
            "host": sess.get("host"),
            "username": sess.get("username"),
            "baseUrl": sess.get("baseUrl"),
            "periodCount": len(sess.get("periods") or []),
            "cachedPeriods": list((sess.get("cache") or {}).keys()),
            "ageSec": int(time.time() - float(sess.get("created") or time.time())),
        }
