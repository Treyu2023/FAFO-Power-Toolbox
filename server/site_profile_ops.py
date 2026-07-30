"""
Master Site Profile — tech liferaft for a physical site (not one backup version).

Stored under %LOCALAPPDATA%\\FAFO\\site-profiles\\ (never git).
Auto-fills from the latest SMS export dossier + per-export survey, while
preserving tech-entered fields. Sensitive passwords stay local-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import verifone_ops as vf

SCHEMA = "FAFO.Commander.MasterSiteProfile/1"
SENSITIVE_TOP = {
    "configClientPassword",
    "csrPassword",
    "maintenanceMenuPassword",
    "otpNotes",
    "registrationKey",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fafo_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    d = base / "FAFO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _profiles_dir() -> Path:
    d = _fafo_dir() / "site-profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_key(group_key: str) -> str:
    raw = (group_key or "unknown").strip().lower()
    h = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
    slug = re.sub(r"[^a-z0-9]+", "-", raw)[:48].strip("-") or "site"
    return f"{slug}_{h}"


def profile_path(group_key: str) -> Path:
    return _profiles_dir() / f"{_safe_key(group_key)}.json"


def empty_profile(group_key: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "groupKey": group_key,
        "updatedAt": None,
        "createdAt": None,
        "securityNotice": (
            "TECH LIFERAFT — may contain live site passwords. Stored only under "
            "%LOCALAPPDATA%\\FAFO\\site-profiles on this Windows user account. "
            "Do not commit to git or email."
        ),
        "identity": {
            "customer": "",
            "displayName": "",
            "siteId": "",
            "serviceId": "",
            "registrationKey": "",
            "brand": "",
            "storeNumber": "",
            "address": "",
            "city": "",
            "state": "",
            "zip": "",
            "phone": "",
            "helpDesk": "",
            "hours": "",
            "contactName": "",
            "contactPhone": "",
            "contactEmail": "",
            "latitude": "",
            "longitude": "",
            "directions": "",
            "afterHoursNotes": "",
        },
        "commander": {
            "hostIp": "",
            "hostAlt": "",
            "configClientUrl": "",
            "journalBrowserUrl": "",
            "baseVersion": "",
            "webVersion": "",
            "osVersion": "",
            "lastKnownSoftware": "",
            "cSiteEnabled": "",
            "cSiteAccount": "",
            "notes": "",
        },
        "credentials": {
            "configClientUser": "Manager",
            "configClientPassword": "",
            # Letter-cycle scheme (default ON): base digits + trailing A→B→C→D→E→A
            # Commander remembers last 4 passwords, so 5-letter cycle avoids reuse.
            # Fleet default (~90% of sites): leading A–E letter + site-specific digit base.
            # Base varies (6652990, 123456, …); cycle is the same everywhere.
            "passwordScheme": "letter_cycle",  # letter_cycle | manual (only if site differs)
            "passwordBase": "",  # digits only, e.g. 6652990 / 123456 — derived from full password if empty
            "passwordLetter": "",  # A-E current cycle letter
            "passwordLetterPosition": "leading",  # leading (B6652990) | trailing (6652990B) rare
            "passwordChangeIntervalDays": 90,
            "lastPasswordChangeAt": "",  # ISO date when letter was last advanced / set
            "nextPasswordDueAt": "",  # computed
            "passwordHistory": [],  # [{letter, changedAt, note}] last few rotations (no full pwd)
            "passwordRotationNotes": (
                "FLEET DEFAULT (~90% of sites) — only turn off if this store is different.\n"
                "Pattern: ONE capital letter (A–E) + site digit base, usually LEADING:\n"
                "  A{base} → B{base} → C{base} → D{base} → E{base} → A{base} …\n"
                "Examples: B6652990 → C6652990 · or A123456 → B123456 (base is per site).\n"
                "Interval: Commander forces a Manager password change ~every 90 days after last change.\n"
                "On-site prompt flow:\n"
                "  1) Login with CURRENT password\n"
                "  2) Forced change: re-enter CURRENT password\n"
                "  3) Enter NEW password (next letter + same base)\n"
                "  4) Re-enter NEW password to confirm\n"
                "Rules: must include 1 capital letter; cannot reuse last 4 passwords "
                "(5-letter A–E cycle clears the reuse window).\n"
                "After a successful live change, use Rotate letter in Liferaft so FAFO matches."
            ),
            "otpNotes": (
                "Config OTP: CSR → Maintenance → Generate/Config OTP (4-digit on register / 7-seg). "
                "C-Site OTP is separate (email/cloud)."
            ),
            "csrPassword": "",
            "maintenanceMenuPassword": "",
            # Linux shell (PuTTY/SSH) — fleet default user often "maint"; override per site if rotated
            "sshHost": "",  # usually Commander LAN IP
            "sshPort": 22,
            "sshUser": "maint",
            "sshPassword": "",  # leave empty to use fleet-tech-defaults.json on this PC
            "sshHelpDeskNotes": (
                "Enable Help Desk login on Commander and enter token before/with maint SSH. "
                "Then: resetpw manager → temp password → Config Client forces new Manager password."
            ),
            "sshNotes": "",
            "roles": [],  # {role, username, password, notes}
            "posAccounts": [],  # from possecurity / manual
            "notes": "",
        },
        "network": {
            "lanIp": "",
            "subnet": "",
            "gateway": "",
            "dns1": "",
            "dns2": "",
            "paymentNicIp": "",
            "paymentNicSubnet": "",
            "paymentNicGateway": "",
            "isolatedPaymentNic": "",
            "mnspVariant": "",
            "mnspRouter": "",
            "mnspPort": "",
            "hostRoutes": [],  # [{name, host, port, notes}]
            "staticRoutesText": "",
            "dailyMsgServer": "",
            "remoteServer": "",
            "remoteServerPort": "",
            "emvIp": "",
            "vpnNotes": "",
            "internetPathNotes": "",
            "notes": "",
        },
        "equipment": {
            "dispenserBrands": [],
            "dcrBrands": [],
            "tankMonitorType": "",
            "carWashType": "",
            "registerIds": "",
            "namedTanks": "",
            "positionsNotes": "",
            "notes": "",
        },
        "emergency": {
            "whatBreaksFirst": "",
            "knownGotchas": "",
            "lastTechOnSite": "",
            "lastVisitDate": "",
            "partsOnSite": "",
            "escalation": "",
            "liferaftNotes": "",
        },
        "customFields": [],  # [{key, value, notes}]
        "sources": {
            "lastBackupExportId": "",
            "lastBackupPath": "",
            "lastSurveyPath": "",
            "lastMergedAt": "",
            "fieldSources": {},  # path -> "backup"|"survey"|"manual"
        },
    }


def _load_raw(group_key: str) -> dict[str, Any] | None:
    p = profile_path(group_key)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _deep_merge_prefer_filled(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge overlay into base; non-empty overlay wins; nested dicts merge."""
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_prefer_filled(out[k], v)
        elif isinstance(v, list):
            # prefer non-empty list
            if v:
                out[k] = deepcopy(v)
            elif k not in out:
                out[k] = []
        else:
            if v not in (None, ""):
                out[k] = v
            elif k not in out:
                out[k] = v
    return out


def _fill_empty_only(base: dict[str, Any], filler: dict[str, Any], prefix: str = "") -> tuple[dict[str, Any], dict[str, str]]:
    """Copy filler into empty base fields only. Returns (result, fieldSources for filled keys)."""
    out = deepcopy(base)
    sources: dict[str, str] = {}

    def walk(dst: dict[str, Any], src: dict[str, Any], path: str) -> None:
        for k, v in (src or {}).items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                walk(dst[k], v, p)
            elif isinstance(v, list):
                cur = dst.get(k)
                if (not cur) and v:
                    dst[k] = deepcopy(v)
                    sources[p] = "merge"
            else:
                cur = dst.get(k)
                if (cur in (None, "", [])) and v not in (None, ""):
                    dst[k] = v
                    sources[p] = "merge"

    walk(out, filler, prefix)
    return out, sources


def _dossier_to_filler(dossier: dict[str, Any], row: dict[str, Any] | None = None) -> dict[str, Any]:
    row = row or {}
    eq = dossier.get("equipment") or row.get("equipment") or {}
    net = eq.get("network") or {}
    nic = eq.get("paymentNic") or {}
    mnsp = eq.get("mnsp") or {}
    routes = eq.get("hostRoutes") or []
    employees = dossier.get("employees") or []
    pos_accounts = []
    for e in employees:
        pos_accounts.append(
            {
                "name": e.get("name") or "",
                "number": e.get("number") or "",
                "securityLevel": e.get("securityLevel") or "",
                "isCashier": e.get("isCashier") or "",
                "password": e.get("password") or "",
                "source": e.get("source") or "backup",
                "notes": "",
            }
        )
    host_routes = [
        {
            "name": r.get("name") or "",
            "host": r.get("host") or "",
            "port": str(r.get("port") or ""),
            "notes": r.get("notes") or "",
        }
        for r in routes
    ]
    site_id = dossier.get("siteId") or row.get("site_id") or ""
    phone = dossier.get("storePhone") or row.get("store_phone") or ""
    service = dossier.get("serviceId") or row.get("service_id") or ""
    return {
        "identity": {
            "customer": dossier.get("customer") or row.get("customer") or "",
            "displayName": dossier.get("displayName") or row.get("display_name") or "",
            "siteId": site_id,
            "serviceId": service,
            "brand": dossier.get("brand") or row.get("brand") or "",
            "storeNumber": site_id,
            "zip": dossier.get("postalCode") or row.get("postal_code") or "",
            "phone": phone,
            "helpDesk": dossier.get("helpDeskPhone") or row.get("help_desk") or "",
        },
        "commander": {
            "lastKnownSoftware": dossier.get("softwareVersion") or row.get("softwareVersion") or "",
            "cSiteEnabled": "yes" if (dossier.get("cloudAgentEnabled") or row.get("cloud_agent")) else "",
        },
        "credentials": {
            "posAccounts": pos_accounts,
            "roles": [
                {
                    "role": "Config Client / Manager",
                    "username": "Manager",
                    "password": "",
                    "notes": "Primary Config Client login — confirm letter cycle on site",
                }
            ],
        },
        "network": {
            "paymentNicIp": nic.get("emvIpOrHost") or "",
            "mnspRouter": mnsp.get("hostaddr") or nic.get("mnspRouter") or "",
            "mnspPort": str(mnsp.get("port") or ""),
            "hostRoutes": host_routes,
            "staticRoutesText": "; ".join(
                f"{r.get('name')}: {r.get('host')}" + (f":{r.get('port')}" if r.get("port") else "")
                for r in routes
            ),
            "dailyMsgServer": net.get("DailyMsg.server.IP") or "",
            "remoteServer": net.get("remote.server.hostname") or "",
            "remoteServerPort": str(net.get("remote.server.port") or ""),
            "emvIp": nic.get("emvIpOrHost") or "",
        },
        "equipment": {
            "dispenserBrands": eq.get("dispenserBrands") or [],
            "dcrBrands": eq.get("dcrBrands") or [],
            "tankMonitorType": eq.get("tankMonitorType") or "",
            "carWashType": eq.get("carWashType") or "",
            "registerIds": ", ".join(dossier.get("registerIds") or [])
            if isinstance(dossier.get("registerIds"), list)
            else str(dossier.get("registerIds") or row.get("register_ids") or ""),
            "namedTanks": ", ".join(
                t.get("name") if isinstance(t, dict) else str(t)
                for t in (dossier.get("namedTanks") or [])
            )
            if isinstance(dossier.get("namedTanks"), list)
            else str(dossier.get("namedTanks") or row.get("named_tanks") or ""),
        },
    }


def _survey_to_filler(survey: dict[str, Any]) -> dict[str, Any]:
    si = survey.get("siteInfo") or {}
    net = survey.get("network") or {}
    cred = survey.get("credentials") or {}
    fc = survey.get("forecourt") or {}
    accounts = cred.get("accounts") or []
    roles = []
    pos = []
    for a in accounts:
        name = (a.get("name") or "").upper()
        entry = {
            "name": a.get("name") or "",
            "number": a.get("number") or "",
            "securityLevel": a.get("securityLevel") or "",
            "isCashier": a.get("isCashier") or "",
            "password": a.get("password") or "",
            "source": a.get("source") or "survey",
            "notes": a.get("notes") or "",
        }
        if "MANAGER" in name or "CONFIG" in name or "CSR" in name:
            roles.append(
                {
                    "role": a.get("name") or "Role",
                    "username": a.get("name") or "",
                    "password": a.get("password") or "",
                    "notes": a.get("notes") or "",
                }
            )
        else:
            pos.append(entry)
    routes = []
    static = net.get("staticRoutes") or ""
    if static:
        for part in re.split(r"[;\n]+", static):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                name, rest = part.split(":", 1)
                host = rest.strip()
                port = ""
                if host.count(":") == 1 and re.search(r":\d+$", host):
                    host, port = host.rsplit(":", 1)
                routes.append({"name": name.strip(), "host": host, "port": port, "notes": ""})
            else:
                routes.append({"name": "", "host": part, "port": "", "notes": ""})
    return {
        "identity": {
            "address": si.get("address") or "",
            "city": si.get("city") or "",
            "state": si.get("state") or "",
            "zip": si.get("zip") or "",
            "phone": si.get("phone") or "",
            "hours": si.get("hours") or "",
            "contactName": si.get("contactName") or "",
            "contactPhone": si.get("contactPhone") or "",
            "brand": si.get("brand") or "",
            "serviceId": si.get("serviceId") or "",
            "helpDesk": si.get("helpDesk") or "",
            "afterHoursNotes": si.get("techNotes") or "",
        },
        "credentials": {
            "configClientUser": cred.get("configClientUser") or "Manager",
            "configClientPassword": cred.get("configClientPassword") or "",
            "csrPassword": cred.get("csrPassword") or "",
            "maintenanceMenuPassword": cred.get("maintenanceMenuPassword") or "",
            "roles": roles,
            "posAccounts": pos if pos else accounts,
            "notes": cred.get("notes") or "",
        },
        "network": {
            "lanIp": net.get("lanIp") or "",
            "subnet": net.get("subnet") or "",
            "gateway": net.get("gateway") or "",
            "dns1": net.get("dns1") or "",
            "dns2": net.get("dns2") or "",
            "paymentNicIp": net.get("paymentNicIp") or "",
            "paymentNicSubnet": net.get("paymentNicSubnet") or "",
            "paymentNicGateway": net.get("paymentNicGateway") or "",
            "isolatedPaymentNic": net.get("isolatedPaymentNic") or "",
            "mnspVariant": net.get("mnspVariant") or "",
            "mnspRouter": net.get("mnspRouter") or "",
            "mnspPort": str(net.get("mnspPort") or ""),
            "hostRoutes": routes,
            "staticRoutesText": static,
            "dailyMsgServer": net.get("dailyMsgServer") or "",
            "remoteServer": net.get("remoteServer") or "",
            "remoteServerPort": str(net.get("remoteServerPort") or ""),
            "emvIp": net.get("emvIp") or "",
            "internetPathNotes": net.get("internetPathNotes") or "",
            "notes": net.get("notes") or "",
        },
        "equipment": {
            "dispenserBrands": fc.get("dispenserBrands") or [],
            "dcrBrands": fc.get("dcrBrands") or [],
            "tankMonitorType": fc.get("tankMonitorType") or "",
            "carWashType": fc.get("carWashType") or "",
            "notes": fc.get("notes") or "",
        },
        "commander": {
            "hostIp": net.get("lanIp") or net.get("remoteServer") or "",
        },
    }


def resolve_group_key(group_key: str | None = None, export_id: str | None = None) -> str:
    if group_key and group_key.strip():
        return group_key.strip().lower()
    if export_id:
        row = vf.get_site(export_id)
        if row:
            d = row.get("dossier") or {}
            return (
                d.get("groupKey")
                or f"{row.get('customer')}|{row.get('site_id') or row.get('site_label')}".lower()
            )
    raise ValueError("group_key or export_id required")


def get_master_profile(
    *,
    group_key: str | None = None,
    export_id: str | None = None,
    merge_sources: bool = True,
) -> dict[str, Any]:
    """
    Return master profile for a physical site.
    If merge_sources, fill empty fields from latest backup dossier + survey.
    """
    gk = resolve_group_key(group_key, export_id)
    base = empty_profile(gk)
    saved = _load_raw(gk)
    if saved:
        base = _deep_merge_prefer_filled(base, saved)
        base["hasSaved"] = True
    else:
        base["hasSaved"] = False
    base["groupKey"] = gk
    base["path"] = str(profile_path(gk))

    # Resolve latest export for this group
    latest_id = export_id
    latest_path = ""
    if not latest_id:
        groups = vf.group_sites()
        g = next((x for x in groups if (x.get("groupKey") or "").lower() == gk), None)
        if g:
            latest_id = g.get("latestId")
            latest_path = g.get("latestPath") or ""
            base["identity"] = _deep_merge_prefer_filled(
                base.get("identity") or {},
                {
                    "customer": g.get("customer") or "",
                    "displayName": g.get("displayName") or "",
                    "siteId": g.get("siteId") or "",
                    "serviceId": g.get("serviceId") or "",
                    "brand": g.get("brand") or "",
                    "phone": g.get("storePhone") or "",
                },
            )
            base["versions"] = g.get("versions") or []
            base["versionCount"] = g.get("versionCount") or 0
            base["latestVersion"] = g.get("latestVersion") or ""

    base["sources"] = base.get("sources") or {}
    base["sources"]["lastBackupExportId"] = latest_id or base["sources"].get("lastBackupExportId") or ""
    base["sources"]["lastBackupPath"] = latest_path or base["sources"].get("lastBackupPath") or ""

    if merge_sources and latest_id:
        try:
            row = vf.get_site(latest_id)
            if row:
                dossier = row.get("dossier") or {}
                if not dossier.get("equipment"):
                    try:
                        root = Path(row.get("root_path") or Path(row["path"]).parent)
                        dossier = vf.build_dossier(Path(row["path"]), root)
                    except Exception:
                        pass
                filler = _dossier_to_filler(dossier, row)
                base, srcs = _fill_empty_only(base, filler)
                for p, s in srcs.items():
                    base.setdefault("sources", {}).setdefault("fieldSources", {})[p] = "backup"
                base["sources"]["lastBackupPath"] = row.get("path") or latest_path
                # survey
                try:
                    survey = vf.get_survey(latest_id)
                    base["sources"]["lastSurveyPath"] = survey.get("path") or ""
                    sf = _survey_to_filler(survey)
                    base, srcs2 = _fill_empty_only(base, sf)
                    for p, s in srcs2.items():
                        base.setdefault("sources", {}).setdefault("fieldSources", {})[p] = "survey"
                except Exception:
                    pass
        except Exception:
            pass

    # Derived URLs from host
    host = (base.get("commander") or {}).get("hostIp") or ""
    if host:
        cmd = base.setdefault("commander", {})
        if not cmd.get("configClientUrl"):
            cmd["configClientUrl"] = f"http://{host}/ConfigClient.html"
        if not cmd.get("journalBrowserUrl"):
            cmd["journalBrowserUrl"] = f"http://{host}/JournalBrowser"

    # Normalize Manager letter-cycle fields + due dates
    base["credentials"] = enrich_password_fields(base.get("credentials") or {})

    base["programmingHints"] = _programming_hints(base)
    return base


def _programming_hints(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Checklist for programming Config Client from this liferaft.
    Live push of IPs into Commander is intentionally NOT automated —
    a wrong IP can brick remote access; tech confirms each value.
    """
    net = profile.get("network") or {}
    cmd = profile.get("commander") or {}
    ident = profile.get("identity") or {}
    steps = [
        {
            "area": "Identity",
            "action": "Confirm site ID / service ID on Controller properties",
            "values": {
                "siteId": ident.get("siteId"),
                "serviceId": ident.get("serviceId"),
                "registrationKey": ident.get("registrationKey"),
            },
        },
        {
            "area": "LAN",
            "action": "Program payment / controller LAN only after confirming with site switch/router",
            "values": {
                "lanIp": net.get("lanIp") or cmd.get("hostIp"),
                "subnet": net.get("subnet"),
                "gateway": net.get("gateway"),
                "dns1": net.get("dns1"),
                "dns2": net.get("dns2"),
            },
            "warning": "Never auto-push IP changes — verify on site switch before applying in Config Client.",
        },
        {
            "area": "Payment NIC",
            "action": "Isolated payment NIC / EMV path",
            "values": {
                "paymentNicIp": net.get("paymentNicIp"),
                "paymentNicSubnet": net.get("paymentNicSubnet"),
                "paymentNicGateway": net.get("paymentNicGateway"),
                "emvIp": net.get("emvIp"),
            },
        },
        {
            "area": "MNSP / host routes",
            "action": "Enter host routes and MNSP router exactly as listed (copy/paste from this profile)",
            "values": {
                "mnspRouter": net.get("mnspRouter"),
                "mnspPort": net.get("mnspPort"),
                "hostRoutes": net.get("hostRoutes"),
                "staticRoutesText": net.get("staticRoutesText"),
            },
        },
        {
            "area": "Credentials",
            "action": "Config Client Manager password + OTP process",
            "values": {
                "user": (profile.get("credentials") or {}).get("configClientUser"),
                "passwordSet": bool((profile.get("credentials") or {}).get("configClientPassword")),
            },
        },
    ]
    return {
        "canAutoPushToConfigClient": False,
        "reason": (
            "Commander Config Client network programming is site-critical. "
            "This liferaft gives copy/paste-ready values and a checklist so you "
            "do not retype IPs at 3AM — apply manually in Config Client / Import-Export."
        ),
        "steps": steps,
        "copyPasteBlock": _copy_paste_block(profile),
    }


def _copy_paste_block(profile: dict[str, Any]) -> str:
    ident = profile.get("identity") or {}
    net = profile.get("network") or {}
    cmd = profile.get("commander") or {}
    cred = profile.get("credentials") or {}
    lines = [
        f"SITE: {ident.get('displayName') or ''} ({ident.get('customer') or ''})",
        f"Site ID: {ident.get('siteId') or ''}",
        f"Service ID: {ident.get('serviceId') or ''}",
        f"Reg key: {ident.get('registrationKey') or ''}",
        f"Phone: {ident.get('phone') or ''}",
        f"Address: {ident.get('address') or ''} {ident.get('city') or ''} {ident.get('state') or ''} {ident.get('zip') or ''}",
        f"Commander host: {cmd.get('hostIp') or net.get('lanIp') or ''}",
        f"LAN: {net.get('lanIp') or ''} / {net.get('subnet') or ''} gw {net.get('gateway') or ''}",
        f"DNS: {net.get('dns1') or ''} {net.get('dns2') or ''}",
        f"Payment NIC: {net.get('paymentNicIp') or ''} gw {net.get('paymentNicGateway') or ''}",
        f"MNSP: {net.get('mnspRouter') or ''}:{net.get('mnspPort') or ''}",
        f"Config Client user: {cred.get('configClientUser') or 'Manager'}",
        f"Routes: {net.get('staticRoutesText') or ''}",
    ]
    for r in net.get("hostRoutes") or []:
        lines.append(f"  route {r.get('name')}: {r.get('host')}:{r.get('port')}")
    return "\n".join(lines)


def save_master_profile(group_key: str, profile: dict[str, Any]) -> dict[str, Any]:
    gk = resolve_group_key(group_key, None)
    existing = _load_raw(gk) or {}
    data = deepcopy(profile) if profile else empty_profile(gk)
    data["schema"] = SCHEMA
    data["groupKey"] = gk
    if not existing.get("createdAt") and not data.get("createdAt"):
        data["createdAt"] = _utc_now()
    else:
        data["createdAt"] = existing.get("createdAt") or data.get("createdAt") or _utc_now()
    data["updatedAt"] = _utc_now()
    data["path"] = str(profile_path(gk))
    # strip large runtime-only
    data.pop("programmingHints", None)
    data.pop("versions", None)
    data.pop("hasSaved", None)
    p = profile_path(gk)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "path": str(p),
        "groupKey": gk,
        "updatedAt": data["updatedAt"],
        "message": "Master site profile saved on this PC (liferaft).",
    }


def refresh_master_from_backup(
    *,
    group_key: str | None = None,
    export_id: str | None = None,
    overwrite_empty_only: bool = True,
) -> dict[str, Any]:
    """
    Re-merge from backup/survey into master profile and save.
    By default only fills empty fields so tech notes are preserved.
    """
    gk = resolve_group_key(group_key, export_id)
    current = get_master_profile(group_key=gk, export_id=export_id, merge_sources=True)
    if not overwrite_empty_only:
        # force: take dossier values over master for identity/equipment/network from backup
        row = vf.get_site(export_id or current.get("sources", {}).get("lastBackupExportId") or "")
        if row:
            dossier = row.get("dossier") or {}
            filler = _dossier_to_filler(dossier, row)
            if not overwrite_empty_only:
                current = _deep_merge_prefer_filled(current, filler)
    current["sources"] = current.get("sources") or {}
    current["sources"]["lastMergedAt"] = _utc_now()
    save_master_profile(gk, current)
    return get_master_profile(group_key=gk, export_id=export_id, merge_sources=False)


def list_master_profiles() -> dict[str, Any]:
    rows = []
    for p in sorted(_profiles_dir().glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ident = data.get("identity") or {}
            rows.append(
                {
                    "groupKey": data.get("groupKey"),
                    "displayName": ident.get("displayName"),
                    "customer": ident.get("customer"),
                    "siteId": ident.get("siteId"),
                    "serviceId": ident.get("serviceId"),
                    "hostIp": (data.get("commander") or {}).get("hostIp"),
                    "updatedAt": data.get("updatedAt"),
                    "path": str(p),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return {"ok": True, "profiles": rows, "count": len(rows), "root": str(_profiles_dir())}


# --- Manager password letter-cycle (per site) ---------------------------------

_LETTER_ORDER = ("A", "B", "C", "D", "E")


def parse_manager_password(password: str) -> dict[str, str]:
    """
    Split Manager password into base + cycle letter.

    Fleet default (~90% of sites): leading letter A–E + digit base,
    e.g. B6652990, C123456. Base digits are per site; letter cycle is shared.
    Also accepts trailing letter (6652990B) if that is what the site uses.
    """
    pw = (password or "").strip()
    if not pw:
        return {"base": "", "letter": "", "password": "", "position": "leading"}
    # Leading letter (preferred fleet pattern): C6652990
    if len(pw) >= 2 and pw[0].upper() in _LETTER_ORDER and re.search(r"\d", pw[1:]):
        return {
            "base": pw[1:],
            "letter": pw[0].upper(),
            "password": pw[0].upper() + pw[1:],
            "position": "leading",
        }
    # Trailing letter fallback: 6652990C
    if len(pw) >= 2 and pw[-1].upper() in _LETTER_ORDER and re.search(r"\d", pw[:-1]):
        return {
            "base": pw[:-1],
            "letter": pw[-1].upper(),
            "password": pw[:-1] + pw[-1].upper(),
            "position": "trailing",
        }
    return {"base": pw, "letter": "", "password": pw, "position": "leading"}


def next_letter(letter: str) -> str:
    L = (letter or "E").upper()
    if L not in _LETTER_ORDER:
        return "A"
    i = _LETTER_ORDER.index(L)
    return _LETTER_ORDER[(i + 1) % len(_LETTER_ORDER)]


def build_manager_password(base: str, letter: str, position: str = "leading") -> str:
    b = (base or "").strip()
    L = (letter or "").strip().upper()
    if not b:
        return ""
    if L not in _LETTER_ORDER:
        return b
    pos = (position or "leading").lower()
    if pos == "trailing":
        return b + L
    return L + b


def _add_days_iso(iso: str | None, days: int) -> str:
    try:
        if iso:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt + timedelta(days=int(days))).isoformat()
    except Exception:
        return (datetime.now(timezone.utc) + timedelta(days=int(days or 90))).isoformat()


def enrich_password_fields(cred: dict[str, Any]) -> dict[str, Any]:
    """Normalize scheme fields and due dates on a credentials dict (in place + return)."""
    c = cred if isinstance(cred, dict) else {}
    scheme = (c.get("passwordScheme") or "letter_cycle").strip().lower()
    if scheme not in {"letter_cycle", "manual"}:
        scheme = "letter_cycle"
    c["passwordScheme"] = scheme
    interval = int(c.get("passwordChangeIntervalDays") or 90)
    if interval < 1:
        interval = 90
    c["passwordChangeIntervalDays"] = interval

    pw = c.get("configClientPassword") or ""
    parsed = parse_manager_password(pw)
    pos = (c.get("passwordLetterPosition") or parsed.get("position") or "leading").lower()
    if pos not in {"leading", "trailing"}:
        pos = "leading"
    c["passwordLetterPosition"] = pos
    if scheme == "letter_cycle":
        if not c.get("passwordBase") and parsed["base"]:
            c["passwordBase"] = parsed["base"]
        if not c.get("passwordLetter") and parsed["letter"]:
            c["passwordLetter"] = parsed["letter"]
        if parsed.get("position"):
            c["passwordLetterPosition"] = parsed["position"]
            pos = parsed["position"]
        # Rebuild password from base+letter when both known
        base = c.get("passwordBase") or parsed["base"]
        letter = c.get("passwordLetter") or parsed["letter"]
        if base and letter:
            c["passwordBase"] = base
            c["passwordLetter"] = letter.upper()
            c["configClientPassword"] = build_manager_password(base, letter, pos)
        c["nextLetter"] = next_letter(c.get("passwordLetter") or "A")
        c["nextPasswordPreview"] = (
            build_manager_password(c.get("passwordBase") or "", c["nextLetter"], pos)
            if c.get("passwordBase")
            else ""
        )
    else:
        c["nextLetter"] = ""
        c["nextPasswordPreview"] = ""

    last = c.get("lastPasswordChangeAt") or ""
    if last and not c.get("nextPasswordDueAt"):
        c["nextPasswordDueAt"] = _add_days_iso(last, interval)
    # overdue flag
    due = c.get("nextPasswordDueAt") or ""
    overdue = False
    days_left = None
    if due:
        try:
            dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = dt - datetime.now(timezone.utc)
            days_left = int(delta.total_seconds() // 86400)
            overdue = days_left < 0
        except Exception:
            pass
    c["passwordOverdue"] = overdue
    c["passwordDaysLeft"] = days_left
    return c


def rotate_manager_password(
    group_key: str,
    *,
    direction: str = "next",
    set_letter: str | None = None,
    mark_changed: bool = True,
    note: str = "",
    sync_live_profile: bool = True,
) -> dict[str, Any]:
    """
    Advance (or set) the Manager password letter for a site liferaft and save.

    direction: "next" | "prev" | "set"
    Does not change the password on the live Commander — only the local liferaft
    (and optional DPAPI live profile). Tech still accepts the prompt on site /
    Config Client; this records what letter is current and when it was changed.
    """
    gk = resolve_group_key(group_key, None)
    prof = get_master_profile(group_key=gk, merge_sources=False)
    if not prof.get("hasSaved"):
        # still allow rotate on merged profile then save
        pass
    cred = enrich_password_fields(prof.get("credentials") or {})
    if (cred.get("passwordScheme") or "letter_cycle") != "letter_cycle":
        raise ValueError("Password scheme is manual for this site — enable letter_cycle to rotate")

    base = (cred.get("passwordBase") or parse_manager_password(cred.get("configClientPassword") or "")["base"] or "").strip()
    if not base:
        raise ValueError("Set Manager password (or password base) first so the letter can cycle")

    cur_letter = (cred.get("passwordLetter") or parse_manager_password(cred.get("configClientPassword") or "")["letter"] or "A").upper()
    if direction == "set" and set_letter:
        new_letter = set_letter.strip().upper()
        if new_letter not in _LETTER_ORDER:
            raise ValueError("Letter must be A–E")
    elif direction == "prev":
        i = _LETTER_ORDER.index(cur_letter) if cur_letter in _LETTER_ORDER else 0
        new_letter = _LETTER_ORDER[(i - 1) % len(_LETTER_ORDER)]
    else:
        new_letter = next_letter(cur_letter)

    pos = (cred.get("passwordLetterPosition") or "leading").lower()
    old_pw = cred.get("configClientPassword") or build_manager_password(base, cur_letter, pos)
    new_pw = build_manager_password(base, new_letter, pos)
    now = _utc_now()
    interval = int(cred.get("passwordChangeIntervalDays") or 90)

    history = list(cred.get("passwordHistory") or [])
    history.append(
        {
            "fromLetter": cur_letter,
            "toLetter": new_letter,
            "changedAt": now if mark_changed else "",
            "note": note or ("rotated on 90-day prompt" if mark_changed else "updated"),
        }
    )
    # keep last 12 events
    history = history[-12:]

    cred["passwordBase"] = base
    cred["passwordLetter"] = new_letter
    cred["configClientPassword"] = new_pw
    cred["passwordHistory"] = history
    if mark_changed:
        cred["lastPasswordChangeAt"] = now
        cred["nextPasswordDueAt"] = _add_days_iso(now, interval)
    cred = enrich_password_fields(cred)
    prof["credentials"] = cred

    # Keep Manager role row in sync
    roles = list(cred.get("roles") or [])
    found = False
    for r in roles:
        if "MANAGER" in (r.get("role") or "").upper() or (r.get("username") or "").lower() == "manager":
            r["password"] = new_pw
            r["username"] = r.get("username") or "Manager"
            found = True
    if not found:
        roles.insert(
            0,
            {
                "role": "Config Client / Manager",
                "username": "Manager",
                "password": new_pw,
                "notes": f"Letter {new_letter} · cycle A–E",
            },
        )
    cred["roles"] = roles
    prof["credentials"] = cred

    save_res = save_master_profile(gk, prof)

    live_sync = None
    if sync_live_profile:
        live_sync = _sync_password_to_live_profile(prof, new_pw)

    return {
        "ok": True,
        "groupKey": gk,
        "previousPasswordMasked": (old_pw[:2] + "…" + old_pw[-1:]) if len(old_pw) > 3 else "***",
        "letter": new_letter,
        "previousLetter": cur_letter,
        "password": new_pw,  # local API only — used by UI to fill fields; not logged to git
        "base": base,
        "lastPasswordChangeAt": cred.get("lastPasswordChangeAt"),
        "nextPasswordDueAt": cred.get("nextPasswordDueAt"),
        "passwordDaysLeft": cred.get("passwordDaysLeft"),
        "passwordOverdue": cred.get("passwordOverdue"),
        "history": history[-5:],
        "liveProfileSync": live_sync,
        "path": save_res.get("path"),
        "message": (
            f"Manager password letter {cur_letter}→{new_letter} saved for this site. "
            f"Next due ~{str(cred.get('nextPasswordDueAt') or '')[:10]}. "
            "Change it in Config Client when prompted, then this liferaft already matches."
        ),
        "profile": get_master_profile(group_key=gk, merge_sources=False),
    }


def _parse_change_date(date_str: str | None) -> str:
    """
    Accept YYYY-MM-DD or full ISO; return UTC noon ISO for stable day math.
    Empty → now.
    """
    s = (date_str or "").strip()
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            # date only from site notes / tech clipboard
            dt = datetime.fromisoformat(s).replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            return dt.isoformat()
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception as e:
        raise ValueError(f"Invalid change date (use YYYY-MM-DD): {date_str}") from e


def set_password_change_date(
    group_key: str,
    *,
    changed_at: str | None = None,
    interval_days: int | None = None,
    note: str = "",
) -> dict[str, Any]:
    """
    Record when Manager password was last changed on site (tech often writes the date at the store).
    Recalculates next due and days remaining from that date + interval (default 90).
    Does not change the password string itself.
    """
    gk = resolve_group_key(group_key, None)
    prof = get_master_profile(group_key=gk, merge_sources=False)
    cred = enrich_password_fields(prof.get("credentials") or {})
    when = _parse_change_date(changed_at)
    if interval_days is not None:
        try:
            interval = max(1, int(interval_days))
        except (TypeError, ValueError):
            interval = int(cred.get("passwordChangeIntervalDays") or 90)
        cred["passwordChangeIntervalDays"] = interval
    else:
        interval = int(cred.get("passwordChangeIntervalDays") or 90)

    cred["lastPasswordChangeAt"] = when
    cred["nextPasswordDueAt"] = _add_days_iso(when, interval)
    hist = list(cred.get("passwordHistory") or [])
    hist.append(
        {
            "fromLetter": cred.get("passwordLetter") or "",
            "toLetter": cred.get("passwordLetter") or "",
            "changedAt": when,
            "note": note or "last-change date recorded (site notes)",
        }
    )
    cred["passwordHistory"] = hist[-12:]
    cred = enrich_password_fields(cred)
    # enrich may not recompute due if last already set — force from our when
    cred["lastPasswordChangeAt"] = when
    cred["nextPasswordDueAt"] = _add_days_iso(when, interval)
    cred = enrich_password_fields(cred)
    prof["credentials"] = cred
    save_master_profile(gk, prof)
    return {
        "ok": True,
        "groupKey": gk,
        "passwordLetter": cred.get("passwordLetter"),
        "passwordBase": cred.get("passwordBase"),
        "currentPasswordPreview": cred.get("configClientPassword") or "",
        "nextLetter": cred.get("nextLetter"),
        "nextPasswordPreview": cred.get("nextPasswordPreview"),
        "lastPasswordChangeAt": cred.get("lastPasswordChangeAt"),
        "nextPasswordDueAt": cred.get("nextPasswordDueAt"),
        "passwordDaysLeft": cred.get("passwordDaysLeft"),
        "passwordOverdue": cred.get("passwordOverdue"),
        "passwordChangeIntervalDays": cred.get("passwordChangeIntervalDays"),
        "message": (
            f"Last change set to {str(when)[:10]}. "
            f"Letter {cred.get('passwordLetter') or '—'} · "
            + (
                f"OVERDUE by {abs(int(cred.get('passwordDaysLeft') or 0))} day(s)"
                if cred.get("passwordOverdue")
                else f"{cred.get('passwordDaysLeft')} day(s) remaining"
                if cred.get("passwordDaysLeft") is not None
                else "due date set"
            )
            + f" · next due {str(cred.get('nextPasswordDueAt') or '')[:10]}."
        ),
        "profile": get_master_profile(group_key=gk, merge_sources=False),
    }


def password_status_summary(cred: dict[str, Any] | None) -> dict[str, Any]:
    """Compact letter + days remaining for UI cards (Import-Export, overview, etc.)."""
    c = enrich_password_fields(dict(cred or {}))
    days = c.get("passwordDaysLeft")
    overdue = bool(c.get("passwordOverdue"))
    if c.get("nextPasswordDueAt") is None and not c.get("lastPasswordChangeAt"):
        status = "unknown"
        statusText = "No last-change date — enter the date from site notes"
    elif overdue:
        status = "overdue"
        statusText = f"OVERDUE by {abs(int(days or 0))} day(s)"
    elif days is not None and days <= 14:
        status = "soon"
        statusText = f"{days} day(s) left — change soon"
    elif days is not None:
        status = "ok"
        statusText = f"{days} day(s) remaining"
    else:
        status = "unknown"
        statusText = "Due date unknown"
    return {
        "letter": c.get("passwordLetter") or "",
        "base": c.get("passwordBase") or "",
        "nextLetter": c.get("nextLetter") or "",
        "nextPasswordPreview": c.get("nextPasswordPreview") or "",
        "lastPasswordChangeAt": c.get("lastPasswordChangeAt") or "",
        "nextPasswordDueAt": c.get("nextPasswordDueAt") or "",
        "passwordDaysLeft": days,
        "passwordOverdue": overdue,
        "intervalDays": c.get("passwordChangeIntervalDays") or 90,
        "status": status,
        "statusText": statusText,
        "scheme": c.get("passwordScheme") or "letter_cycle",
    }


def set_manager_password(
    group_key: str,
    password: str,
    *,
    mark_changed: bool = True,
    scheme: str | None = None,
    note: str = "",
    sync_live_profile: bool = True,
    changed_at: str | None = None,
) -> dict[str, Any]:
    """Set full Manager password on site liferaft (parses letter if scheme is letter_cycle)."""
    gk = resolve_group_key(group_key, None)
    prof = get_master_profile(group_key=gk, merge_sources=False)
    cred = enrich_password_fields(prof.get("credentials") or {})
    if scheme:
        cred["passwordScheme"] = scheme if scheme in {"letter_cycle", "manual"} else cred.get("passwordScheme")
    pw = (password or "").strip()
    if not pw:
        raise ValueError("password required")
    parsed = parse_manager_password(pw)
    if (cred.get("passwordScheme") or "letter_cycle") == "letter_cycle" and parsed["letter"]:
        cred["passwordBase"] = parsed["base"]
        cred["passwordLetter"] = parsed["letter"]
        cred["passwordLetterPosition"] = parsed.get("position") or "leading"
        cred["configClientPassword"] = build_manager_password(
            parsed["base"], parsed["letter"], cred["passwordLetterPosition"]
        )
    else:
        cred["configClientPassword"] = pw
        if (cred.get("passwordScheme") or "") == "letter_cycle" and not parsed["letter"]:
            # still store as base only
            cred["passwordBase"] = pw
    interval = int(cred.get("passwordChangeIntervalDays") or 90)
    if mark_changed:
        when = _parse_change_date(changed_at) if changed_at else _utc_now()
        cred["lastPasswordChangeAt"] = when
        cred["nextPasswordDueAt"] = _add_days_iso(when, interval)
        hist = list(cred.get("passwordHistory") or [])
        hist.append(
            {
                "fromLetter": "",
                "toLetter": cred.get("passwordLetter") or "",
                "changedAt": when,
                "note": note or ("password set" + (f" · change date {str(when)[:10]}" if changed_at else "")),
            }
        )
        cred["passwordHistory"] = hist[-12:]
    cred = enrich_password_fields(cred)
    if mark_changed and cred.get("lastPasswordChangeAt"):
        # keep explicit date after enrich
        when = cred["lastPasswordChangeAt"]
        cred["nextPasswordDueAt"] = _add_days_iso(when, interval)
        cred = enrich_password_fields(cred)
    prof["credentials"] = cred
    save_master_profile(gk, prof)
    live_sync = _sync_password_to_live_profile(prof, cred.get("configClientPassword") or pw) if sync_live_profile else None
    return {
        "ok": True,
        "groupKey": gk,
        "letter": cred.get("passwordLetter"),
        "base": cred.get("passwordBase"),
        "lastPasswordChangeAt": cred.get("lastPasswordChangeAt"),
        "nextPasswordDueAt": cred.get("nextPasswordDueAt"),
        "passwordDaysLeft": cred.get("passwordDaysLeft"),
        "passwordOverdue": cred.get("passwordOverdue"),
        "status": password_status_summary(cred),
        "liveProfileSync": live_sync,
        "profile": get_master_profile(group_key=gk, merge_sources=False),
        "message": "Manager password saved for this site",
    }


def _sync_password_to_live_profile(prof: dict[str, Any], password: str) -> dict[str, Any] | None:
    """Best-effort: update/create commander_live DPAPI profile for this host."""
    try:
        import commander_live as cl
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    host = ((prof.get("commander") or {}).get("hostIp") or "").strip()
    user = ((prof.get("credentials") or {}).get("configClientUser") or "Manager").strip() or "Manager"
    if not host or not password:
        return {"ok": False, "error": "host or password missing"}
    try:
        # find existing profile by host
        profiles = cl.list_profiles() if hasattr(cl, "list_profiles") else []
        match = None
        for p in profiles or []:
            if (p.get("host") or "").strip() == host and (p.get("username") or "Manager") == user:
                match = p
                break
        name = (prof.get("identity") or {}).get("displayName") or host
        row = cl.save_profile(
            name=f"{host} {user}" if not match else (match.get("name") or f"{host} {user}"),
            host=host,
            username=user,
            password=password,
            profile_id=(match or {}).get("id"),
            notes=(
                f"Synced from site liferaft {(prof.get('identity') or {}).get('displayName') or ''}. "
                f"Letter cycle: {(prof.get('credentials') or {}).get('passwordLetter') or '?'}"
            ),
            keep_password_if_empty=False,
        )
        return {"ok": True, "profileId": (row or {}).get("id"), "host": host, "username": user}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def export_liferaft_markdown(group_key: str) -> dict[str, Any]:
    prof = get_master_profile(group_key=group_key, merge_sources=True)
    ident = prof.get("identity") or {}
    cmd = prof.get("commander") or {}
    net = prof.get("network") or {}
    cred = prof.get("credentials") or {}
    em = prof.get("emergency") or {}
    eq = prof.get("equipment") or {}
    lines = [
        f"# TECH LIFERAFT — {ident.get('displayName') or group_key}",
        "",
        f"_Updated: {prof.get('updatedAt') or '(unsaved)'} · Local only — may contain passwords_",
        "",
        "## Identity",
        f"- Customer: {ident.get('customer')}",
        f"- Site ID: {ident.get('siteId')}",
        f"- Service ID: {ident.get('serviceId')}",
        f"- Registration key: {ident.get('registrationKey')}",
        f"- Phone: {ident.get('phone')}",
        f"- Address: {ident.get('address')}, {ident.get('city')} {ident.get('state')} {ident.get('zip')}",
        f"- Help desk: {ident.get('helpDesk')}",
        f"- Contact: {ident.get('contactName')} {ident.get('contactPhone')}",
        "",
        "## Commander",
        f"- Host IP: {cmd.get('hostIp')}",
        f"- Config Client: {cmd.get('configClientUrl')}",
        f"- Journal Browser: {cmd.get('journalBrowserUrl')}",
        f"- Software: {cmd.get('lastKnownSoftware')}",
        f"- Notes: {cmd.get('notes')}",
        "",
        "## Credentials",
        f"- Config Client: {cred.get('configClientUser')} / {'(set)' if cred.get('configClientPassword') else '(empty)'}",
        f"- CSR: {'(set)' if cred.get('csrPassword') else '(empty)'}",
        f"- Maintenance: {'(set)' if cred.get('maintenanceMenuPassword') else '(empty)'}",
        f"- Rotation: {cred.get('passwordRotationNotes')}",
        f"- OTP: {cred.get('otpNotes')}",
        "",
        "### Roles",
    ]
    for r in cred.get("roles") or []:
        lines.append(
            f"- {r.get('role')}: {r.get('username')} / {'•••' if r.get('password') else '(empty)'} — {r.get('notes') or ''}"
        )
    lines.append("")
    lines.append("### POS / cashier accounts")
    for a in (cred.get("posAccounts") or [])[:40]:
        lines.append(
            f"- {a.get('name')} #{a.get('number')} lvl {a.get('securityLevel')} "
            f"{'pwd set' if a.get('password') else 'no pwd'} ({a.get('source') or ''})"
        )
    lines.extend(
        [
            "",
            "## Network",
            f"- LAN: {net.get('lanIp')} / {net.get('subnet')} gw {net.get('gateway')}",
            f"- DNS: {net.get('dns1')} , {net.get('dns2')}",
            f"- Payment NIC: {net.get('paymentNicIp')} / {net.get('paymentNicSubnet')} gw {net.get('paymentNicGateway')}",
            f"- MNSP: {net.get('mnspRouter')}:{net.get('mnspPort')} ({net.get('mnspVariant')})",
            f"- EMV: {net.get('emvIp')}",
            f"- Routes text: {net.get('staticRoutesText')}",
            "",
        ]
    )
    for r in net.get("hostRoutes") or []:
        lines.append(f"- Route {r.get('name')}: {r.get('host')}:{r.get('port')} {r.get('notes') or ''}")
    lines.extend(
        [
            "",
            "## Equipment",
            f"- Dispensers: {', '.join(eq.get('dispenserBrands') or [])}",
            f"- DCR: {', '.join(eq.get('dcrBrands') or [])}",
            f"- Tank monitor: {eq.get('tankMonitorType')}",
            f"- Registers: {eq.get('registerIds')}",
            f"- Tanks: {eq.get('namedTanks')}",
            "",
            "## 3AM emergency",
            f"- What breaks first: {em.get('whatBreaksFirst')}",
            f"- Gotchas: {em.get('knownGotchas')}",
            f"- Last tech: {em.get('lastTechOnSite')} on {em.get('lastVisitDate')}",
            f"- Parts on site: {em.get('partsOnSite')}",
            f"- Escalation: {em.get('escalation')}",
            f"- Notes: {em.get('liferaftNotes')}",
            "",
            "## Copy/paste block",
            "```",
            (prof.get("programmingHints") or {}).get("copyPasteBlock") or "",
            "```",
            "",
            "## Config Client programming",
            (prof.get("programmingHints") or {}).get("reason") or "",
            "",
        ]
    )
    text = "\n".join(lines)
    out = profile_path(group_key).with_suffix(".md")
    out.write_text(text, encoding="utf-8")
    return {"ok": True, "path": str(out), "markdown": text}
