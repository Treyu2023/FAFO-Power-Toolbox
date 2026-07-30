"""
Per-site SITE-INFO.md in the SMS backup folder.

Combines:
  - Backup-derived dossier (POS users, dispensers/DCR, tanks, products, modules)
  - Survey fields (network IPs, host routes — usually NOT in backup / not pushable)
  - Liferaft Manager letter-cycle + days remaining (90-day rule)
  - Layout topography defaults for the aerial map (pumps/tanks/registers)

POS cashier passwords do NOT use the Manager A–E 90-day scheme.
Network / fuel / DCR programming is reference-only (manual in Config Client).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import site_profile_ops as sprof
import verifone_ops as vf

SITE_INFO_NAME = "SITE-INFO.md"
SITE_INFO_JSON = "survey" + "/site-info-snapshot.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_if_empty(pw: str | None) -> str:
    p = (pw or "").strip()
    return p if p else "*(not in backup / enter on site)*"


def _is_managed_user(name: str, level: str = "", is_cashier: str = "") -> bool:
    """
    Managed / elevated accounts (Manager letter-cycle applies only to Config Client Manager).
    POS cashiers are everyone else — they do NOT use the 90-day A–E rule.
    """
    n = (name or "").upper()
    if "CONFIG CLIENT" in n:
        return True
    if re.search(r"\b(STORE\s+)?MANAGER\b|\bASST\.?\s*MGR\b|\bASSISTANT\s+MANAGER\b", n):
        return True
    # Explicit non-cashier high level (Commander security levels vary by site)
    cash = str(is_cashier or "").strip().lower()
    if cash in {"1", "y", "yes", "true"}:
        return False
    try:
        if int(level or 0) >= 9 and "MANAGER" in n:
            return True
    except ValueError:
        pass
    return False


def _load_bundle(site_key: str) -> dict[str, Any]:
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    dossier = row.get("dossier") or {}
    if not dossier.get("employees") and not dossier.get("equipment"):
        try:
            root = Path(row.get("root_path") or export_path.parent)
            dossier = vf.build_dossier(export_path, root)
        except Exception:
            dossier = row.get("dossier") or {}

    survey = {}
    try:
        survey = vf.get_survey(site_key)
    except Exception:
        survey = {}

    # Liferaft by group / customer name
    group_key = (
        dossier.get("groupKey")
        or row.get("group_key")
        or f"{row.get('customer') or ''}|{row.get('site_id') or dossier.get('siteId') or ''}".lower()
    )
    # Prefer customer display for QNE-style keys
    cust = row.get("customer") or dossier.get("customer") or ""
    master = {}
    try:
        gk = sprof.resolve_group_key(cust or None, site_key)
        master = sprof.get_master_profile(group_key=gk, export_id=site_key, merge_sources=True)
    except Exception:
        try:
            master = sprof.get_master_profile(export_id=site_key, merge_sources=True)
        except Exception:
            master = {}

    return {
        "row": row,
        "exportPath": export_path,
        "dossier": dossier,
        "survey": survey or {},
        "master": master or {},
        "groupKey": (master or {}).get("groupKey") or group_key,
    }


def build_topography_defaults(dossier: dict[str, Any], survey: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Build layout palette items from backup equipment for the aerial map.
    User places/adjusts on the canvas; we seed sensible defaults.
    """
    eq = dossier.get("equipment") or {}
    positions = eq.get("fuelingPositions") or (survey or {}).get("forecourt", {}).get("positions") or []
    tanks = dossier.get("namedTanks") or []
    registers = dossier.get("registerIds") or []
    if isinstance(registers, str):
        registers = [r.strip() for r in registers.split(",") if r.strip()]

    # Prefer verifone default_layout then enrich
    layout = vf.default_layout(positions if isinstance(positions, list) else None)
    items = list(layout.get("items") or [])

    # Replace generic tanks with named tanks from fuelcfg
    items = [i for i in items if not str(i.get("id") or "").startswith("tank")]
    for i, t in enumerate(tanks[:12]):
        name = t.get("name") if isinstance(t, dict) else str(t)
        prod = (t.get("prodId") if isinstance(t, dict) else "") or ""
        items.append(
            {
                "id": f"tank{i+1}",
                "type": "tank",
                "x": 780 + (i % 3) * 80,
                "y": 80 + (i // 3) * 90,
                "w": 70,
                "h": 70,
                "label": name or f"Tank {i+1}",
                "color": "#f59e0b",
                "meta": {
                    "sysId": (t.get("sysId") if isinstance(t, dict) else "") or "",
                    "prodId": prod,
                    "source": "fuelcfg.xml",
                },
            }
        )

    # Card reader / DCR stubs per pump position that has a DCR brand
    for p in positions or []:
        if not isinstance(p, dict):
            continue
        n = p.get("position")
        brand = p.get("dcrBrand") or ""
        if not n:
            continue
        # attach meta onto existing pump if present
        for it in items:
            if it.get("type") == "pump" and str((it.get("meta") or {}).get("position")) == str(n):
                it.setdefault("meta", {})
                it["meta"]["dispenserBrand"] = p.get("dispenserBrand") or ""
                it["meta"]["dcrBrand"] = brand
                it["meta"]["dcrChannel"] = p.get("dcrChannel") or ""
                if brand:
                    it["label"] = f"Pump {n} · {brand}" if brand else it.get("label")
                break
        if brand:
            items.append(
                {
                    "id": f"crind{n}",
                    "type": "card_reader",
                    "x": 0,  # user places — stash off canvas until placed
                    "y": 0,
                    "w": 40,
                    "h": 28,
                    "label": f"CRIND {n} ({brand})",
                    "color": "#a78bfa",
                    "meta": {"position": n, "dcrBrand": brand, "unplaced": True, "source": "managedmodule/dcr"},
                    "paletteOnly": True,
                }
            )

    # Registers from registercfg
    items = [i for i in items if not str(i.get("id") or "").startswith("reg")]
    for i, rid in enumerate(list(registers)[:8]):
        items.append(
            {
                "id": f"reg{rid}",
                "type": "register",
                "x": 360 + (i % 4) * 50,
                "y": 120 + (i // 4) * 50,
                "w": 40,
                "h": 40,
                "label": f"Reg {rid}",
                "color": "#34d399",
                "meta": {"registerId": rid, "source": "registercfg.xml"},
            }
        )

    # Counts for MD / survey
    disp_brands = eq.get("dispenserBrands") or []
    dcr_brands = eq.get("dcrBrands") or []
    pump_count = len([i for i in items if i.get("type") == "pump"])
    crind_count = len([p for p in (positions or []) if isinstance(p, dict) and p.get("dcrBrand")])
    if not crind_count:
        crind_count = len(dcr_brands)  # brand list only

    layout["items"] = items
    layout["defaultsMeta"] = {
        "pumpCount": pump_count,
        "dispenserBrands": disp_brands,
        "cardReaderCount": crind_count,
        "cardReaderBrands": dcr_brands,
        "tankCount": len(tanks),
        "registerCount": len(registers),
        "source": "SMS backup (fuelcfg / managed modules / registercfg)",
        "note": (
            "Pumps/tanks/registers seeded from backup. "
            "Card readers listed for palette; place on map as needed. "
            "Network gear is survey/liferaft-only (not pushable)."
        ),
    }
    return layout


def apply_topography_to_survey(site_key: str, *, only_if_empty: bool = True) -> dict[str, Any]:
    """Merge topography defaults into survey.layout (optional empty-only)."""
    bundle = _load_bundle(site_key)
    dossier = bundle["dossier"]
    survey = bundle["survey"] or vf.get_survey(site_key)
    defaults = build_topography_defaults(dossier, survey)
    existing = (survey.get("layout") or {}).get("items") or []
    if only_if_empty and len(existing) > 5:
        # already customized
        return {
            "ok": True,
            "skipped": True,
            "message": "Layout already has items — not overwritten. Pass force to replace.",
            "defaultsMeta": defaults.get("defaultsMeta"),
        }
    survey["layout"] = defaults
    # also refresh forecourt positions from dossier if thin
    fc = survey.setdefault("forecourt", {})
    if not fc.get("positions") and (dossier.get("equipment") or {}).get("fuelingPositions"):
        fc["positions"] = (dossier.get("equipment") or {}).get("fuelingPositions")
    if not fc.get("dispenserBrands"):
        fc["dispenserBrands"] = (dossier.get("equipment") or {}).get("dispenserBrands") or []
    if not fc.get("dcrBrands"):
        fc["dcrBrands"] = (dossier.get("equipment") or {}).get("dcrBrands") or []
    if not fc.get("tankMonitorType"):
        fc["tankMonitorType"] = (dossier.get("equipment") or {}).get("tankMonitorType") or ""
    saved = vf.save_survey(site_key, survey)
    return {
        "ok": True,
        "skipped": False,
        "layout": defaults,
        "defaultsMeta": defaults.get("defaultsMeta"),
        "surveyPath": saved.get("path") if isinstance(saved, dict) else None,
        "message": "Topography defaults applied from backup equipment — drag items on Aerial layout tab.",
    }


def build_site_info_markdown(site_key: str) -> dict[str, Any]:
    """Build full SITE-INFO.md content (does not write)."""
    bundle = _load_bundle(site_key)
    row = bundle["row"]
    dossier = bundle["dossier"]
    survey = bundle["survey"] or {}
    master = bundle["master"] or {}
    export_path = bundle["exportPath"]

    eq = dossier.get("equipment") or {}
    positions = eq.get("fuelingPositions") or (survey.get("forecourt") or {}).get("positions") or []
    tanks = dossier.get("namedTanks") or []
    products = dossier.get("fuelProducts") or []
    employees = dossier.get("employees") or []
    # Prefer survey/liferaft accounts when richer
    surv_accts = (survey.get("credentials") or {}).get("accounts") or []
    master_cred = master.get("credentials") or {}
    master_pos = master_cred.get("posAccounts") or []
    master_roles = master_cred.get("roles") or []

    pwd_status = sprof.password_status_summary(master_cred)
    # also parse Manager password from liferaft
    mgr_pw = master_cred.get("configClientPassword") or ""
    if not mgr_pw:
        for a in surv_accts:
            if _is_managed_user(a.get("name") or "", a.get("securityLevel") or "", a.get("isCashier") or ""):
                if "MANAGER" in (a.get("name") or "").upper() or "CONFIG" in (a.get("name") or "").upper():
                    mgr_pw = a.get("password") or mgr_pw
                    break

    net_s = survey.get("network") or {}
    net_m = master.get("network") or {}
    cmd = master.get("commander") or {}
    site_info = survey.get("siteInfo") or {}
    ident = master.get("identity") or {}

    def net_get(key: str) -> str:
        return str(net_s.get(key) or net_m.get(key) or cmd.get(key) or "" or "")

    host_routes = net_m.get("hostRoutes") or []
    if not host_routes and net_s.get("staticRoutes"):
        # parse "name: host:port; ..." loosely
        host_routes = []

    # Classify users
    managed_rows: list[dict[str, Any]] = []
    pos_rows: list[dict[str, Any]] = []

    # Manager from liferaft first
    if mgr_pw or master_cred.get("configClientUser"):
        managed_rows.append(
            {
                "role": "Config Client / Manager",
                "username": master_cred.get("configClientUser") or "Manager",
                "password": mgr_pw,
                "source": "liferaft",
                "passwordRule": "letter_cycle_90d",
            }
        )
    for r in master_roles:
        managed_rows.append(
            {
                "role": r.get("role") or "role",
                "username": r.get("username") or "",
                "password": r.get("password") or "",
                "source": "liferaft-roles",
                "passwordRule": "managed",
                "notes": r.get("notes") or "",
            }
        )

    # POS from backup employees + survey accounts
    seen_nums: set[str] = set()
    for src_list, src_name in (
        (employees, "possecurity.xml"),
        (surv_accts, "survey"),
        (master_pos, "liferaft"),
    ):
        for e in src_list:
            name = e.get("name") or ""
            num = str(e.get("number") or e.get("sysId") or "")
            key = f"{name}|{num}".lower()
            if key in seen_nums:
                continue
            # skip blank name and pure numeric id-only rows without name
            if not name.strip():
                continue
            seen_nums.add(key)
            row_u = {
                "name": name,
                "number": num,
                "securityLevel": e.get("securityLevel") or "",
                "password": e.get("password") or "",
                "passwordDecoded": e.get("passwordDecoded"),
                "source": e.get("source") or src_name,
                "isCashier": e.get("isCashier") or "",
            }
            if _is_managed_user(name, row_u["securityLevel"], row_u["isCashier"]):
                if not any(
                    (m.get("username") or "").lower() == name.lower()
                    or (m.get("role") or "").lower() == name.lower()
                    for m in managed_rows
                ):
                    managed_rows.append(
                        {
                            "role": name,
                            "username": name,
                            "password": row_u["password"],
                            "source": row_u["source"],
                            "passwordRule": (
                                "letter_cycle_90d"
                                if re.search(r"MANAGER|CONFIG CLIENT", name.upper())
                                else "managed_no_90d"
                            ),
                            "notes": "Elevated POS role — not the Config Client letter cycle unless noted",
                        }
                    )
            else:
                pos_rows.append(row_u)

    topo = build_topography_defaults(dossier, survey)
    meta = topo.get("defaultsMeta") or {}

    title = (
        row.get("display_name")
        or dossier.get("displayName")
        or ident.get("displayName")
        or row.get("customer")
        or site_key
    )
    lines: list[str] = [
        f"# SITE INFO — {title}",
        "",
        f"_Generated: {_utc_now()[:19]} · FAFO Site Console_",
        "",
        "> **LOCAL TECH ONLY** — may contain live passwords. Stored in the SMS backup folder.  ",
        "> Do not commit to git or email unredacted. Network / fuel / DCR values are **reference only**  ",
        "> (Verifone: do not auto-push LAN or forecourt programming; apply manually in Config Client).",
        "",
        "## Snapshot",
        f"| Field | Value |",
        f"| --- | --- |",
        f"| Customer | {row.get('customer') or dossier.get('customer') or ident.get('customer') or ''} |",
        f"| Site ID | {dossier.get('siteId') or row.get('site_id') or ident.get('siteId') or ''} |",
        f"| Service ID | {dossier.get('serviceId') or site_info.get('serviceId') or ''} |",
        f"| Software | {dossier.get('softwareVersion') or row.get('softwareVersion') or ''} |",
        f"| Phone | {site_info.get('phone') or dossier.get('storePhone') or ident.get('phone') or ''} |",
        f"| Address | {site_info.get('address') or ident.get('address') or ''} {site_info.get('city') or ''} {site_info.get('state') or ''} {site_info.get('zip') or dossier.get('postalCode') or ''} |",
        f"| Backup path | `{export_path}` |",
        f"| Brand | {dossier.get('brand') or site_info.get('brand') or ''} |",
        "",
        "---",
        "",
        "## Managed users (Config Client / elevated)",
        "",
        "Manager uses the **fleet letter-cycle** (~90% of sites): leading `A–E` + site digit base,  ",
        "forced change ~every **90 days**. Prompt: current → re-enter current → new → confirm new.  ",
        "1 capital required; last 4 passwords blocked → cycle A→B→C→D→E→A.",
        "",
        f"| Role | User | Password | Letter | Days left | Last change | Next due | Next pwd |",
        f"| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    # Primary Manager row with days
    mgr_user = master_cred.get("configClientUser") or "Manager"
    lines.append(
        f"| Config Client / Manager | {mgr_user} | `{_mask_if_empty(mgr_pw)}` | "
        f"**{pwd_status.get('letter') or '—'}** | "
        f"**{pwd_status.get('passwordDaysLeft') if pwd_status.get('passwordDaysLeft') is not None else '—'}** "
        f"{'(OVERDUE)' if pwd_status.get('passwordOverdue') else ''} | "
        f"{(pwd_status.get('lastPasswordChangeAt') or '')[:10] or '*(enter date from site notes)*'} | "
        f"{(pwd_status.get('nextPasswordDueAt') or '')[:10] or '—'} | "
        f"`{pwd_status.get('nextPasswordPreview') or '—'}` |"
    )
    for m in managed_rows:
        if m.get("role") == "Config Client / Manager":
            continue
        lines.append(
            f"| {m.get('role')} | {m.get('username')} | `{_mask_if_empty(m.get('password'))}` | "
            f"— | n/a | — | — | — |"
        )

    lines.extend(
        [
            "",
            f"**Password status:** {pwd_status.get('statusText') or 'unknown'}  ",
            f"**Digit base:** `{pwd_status.get('base') or '—'}` · **Interval:** {pwd_status.get('intervalDays') or 90} days  ",
            "Update last-change date in **Liferaft → Credentials** (site notes often have the date).",
            "",
            "---",
            "",
            "## POS / cashier users",
            "",
            "These accounts **do not** use the Manager A–E 90-day birthday rule.  ",
            "Passwords from `possecurity.xml` (gemcomPasswd) when decoded; confirm live.",
            "",
            "| Name | # | Level | Cashier | Password | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not pos_rows:
        lines.append("| *(none in backup)* |  |  |  |  |  |")
    for p in pos_rows:
        lines.append(
            f"| {p.get('name') or ''} | {p.get('number') or ''} | {p.get('securityLevel') or ''} | "
            f"{p.get('isCashier') or ''} | `{_mask_if_empty(p.get('password'))}` | {p.get('source') or ''} |"
        )

    # SSH / shell recovery (fleet + site overrides)
    try:
        import fleet_tech_ops as fleet_tech

        shell = fleet_tech.shell_for_site(
            host=net_get("lanIp") or cmd.get("hostIp") or master_cred.get("sshHost") or None,
            site_password=master_cred.get("sshPassword") or None,
            site_user=master_cred.get("sshUser") or None,
            site_port=int(master_cred["sshPort"]) if master_cred.get("sshPort") else None,
        )
    except Exception:
        shell = {
            "username": master_cred.get("sshUser") or "maint",
            "password": master_cred.get("sshPassword") or "(see fleet-tech-defaults on this PC)",
            "port": master_cred.get("sshPort") or 22,
            "host": net_get("lanIp") or cmd.get("hostIp") or "192.168.x.x",
            "resetManagerCmd": "resetpw manager",
        }

    lines.extend(
        [
            "",
            "---",
            "",
            "## SSH / PuTTY shell (Manager lockout recovery)",
            "",
            "LAN cable on store switch (same as SMS load). Not the Manager letter-cycle password.",
            "",
            f"| Field | Value |",
            f"| --- | --- |",
            f"| Host | {shell.get('host') or master_cred.get('sshHost') or net_get('lanIp') or cmd.get('hostIp') or ''} |",
            f"| Port | {shell.get('port') or 22} |",
            f"| User | `{shell.get('username') or 'maint'}` |",
            f"| Password | `{shell.get('password') or '*(fleet defaults / liferaft)*'}` |",
            f"| Help desk | {master_cred.get('sshHelpDeskNotes') or 'Enable Help Desk login + token on Commander'} |",
            f"| Reset Manager | `{shell.get('resetManagerCmd') or 'resetpw manager'}` |",
            "",
            "1. PuTTY → SSH → host:port  ",
            "2. Login maint  ",
            "3. Host-key warning on known rebuild → Yes  ",
            "4. Enable Help Desk login + token on Commander if required  ",
            "5. `resetpw manager` → note temp password → Config Client Manager login → set next letter+base  ",
            "6. Liferaft: update letter + last changed date  ",
            "",
            f"_Notes: {master_cred.get('sshNotes') or shell.get('worksOnBase') or ''}_",
            "",
            "---",
            "",
            "## Network (survey / liferaft — usually NOT in SMS backup)",
            "",
            "Not pushable via Import-Export for site LAN / critical paths — copy into Config Client manually.",
            "",
            f"| Field | Value |",
            f"| --- | --- |",
            f"| Commander host IP | {net_get('hostIp') or cmd.get('hostIp') or net_get('lanIp') or ''} |",
            f"| LAN IP | {net_get('lanIp')} |",
            f"| Subnet | {net_get('subnet')} |",
            f"| Gateway | {net_get('gateway')} |",
            f"| DNS | {net_get('dns1')} / {net_get('dns2')} |",
            f"| Payment NIC IP | {net_get('paymentNicIp')} |",
            f"| Payment NIC gateway | {net_get('paymentNicGateway')} |",
            f"| Isolated payment NIC | {net_get('isolatedPaymentNic')} |",
            f"| EMV IP | {net_get('emvIp')} |",
            f"| MNSP router | {net_get('mnspRouter')}:{net_get('mnspPort')} |",
            f"| DailyMsg server | {net_get('dailyMsgServer')} |",
            f"| Remote server | {net_get('remoteServer')}:{net_get('remoteServerPort')} |",
            f"| Static routes (text) | {net_get('staticRoutes') or net_m.get('staticRoutesText') or ''} |",
            f"| Internet path notes | {net_get('internetPathNotes') or net_m.get('internetPathNotes') or ''} |",
            "",
            "### Host routes",
            "",
        ]
    )
    if host_routes:
        lines.append("| Name | Host | Port | Notes |")
        lines.append("| --- | --- | --- | --- |")
        for r in host_routes:
            lines.append(
                f"| {r.get('name') or ''} | {r.get('host') or ''} | {r.get('port') or ''} | {r.get('notes') or ''} |"
            )
    else:
        lines.append("*(none recorded — fill in Site survey → Network or Liferaft)*")
        if net_s.get("staticRoutes"):
            lines.append("")
            lines.append(f"Static routes string: `{net_s.get('staticRoutes')}`")

    # Equipment from backup
    disp_brands = eq.get("dispenserBrands") or (survey.get("forecourt") or {}).get("dispenserBrands") or []
    dcr_brands = eq.get("dcrBrands") or (survey.get("forecourt") or {}).get("dcrBrands") or []
    lines.extend(
        [
            "",
            "---",
            "",
            "## Forecourt / equipment (from SMS backup)",
            "",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| Dispenser brands | {', '.join(disp_brands) or '—'} |",
            f"| Dispenser / pump count | {meta.get('pumpCount') or len(positions) or '—'} |",
            f"| Card reader / DCR brands | {', '.join(dcr_brands) or '—'} |",
            f"| Card reader count (assigned) | {meta.get('cardReaderCount') or '—'} |",
            f"| Tank monitor | {eq.get('tankMonitorType') or (survey.get('forecourt') or {}).get('tankMonitorType') or '—'} |",
            f"| Car wash | {eq.get('carWashType') or (survey.get('forecourt') or {}).get('carWashType') or '—'} |",
            f"| Registers | {', '.join(str(x) for x in (dossier.get('registerIds') or []))} (count {dossier.get('registerCount') or len(dossier.get('registerIds') or [])}) |",
            f"| Tank count | {len(tanks)} |",
            "",
            "### Fueling positions",
            "",
            "| Pos | Dispenser | Driver | DCR / CRIND | Channel | Port |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not positions:
        lines.append("| — | *(not in backup)* |  |  |  |  |")
    for p in positions:
        if not isinstance(p, dict):
            continue
        lines.append(
            f"| {p.get('position')} | {p.get('dispenserBrand') or ''} | {p.get('dispenserDriver') or ''} | "
            f"{p.get('dcrBrand') or ''} | {p.get('dcrChannel') or p.get('fuelChannel') or ''} | {p.get('portName') or ''} |"
        )

    lines.extend(
        [
            "",
            "### Tanks",
            "",
            "| SysId | Name | Product ID |",
            "| --- | --- | --- |",
        ]
    )
    if not tanks:
        lines.append("| — | *(none named in fuelcfg)* |  |")
    for t in tanks:
        if isinstance(t, dict):
            lines.append(f"| {t.get('sysId') or ''} | {t.get('name') or ''} | {t.get('prodId') or ''} |")
        else:
            lines.append(f"|  | {t} |  |")

    lines.extend(
        [
            "",
            "### Fuel products",
            "",
            "| SysId | Name | Grade |",
            "| --- | --- | --- |",
        ]
    )
    if not products:
        lines.append("| — | *(none in fuelprices)* |  |")
    for p in products:
        if isinstance(p, dict):
            lines.append(f"| {p.get('sysId') or ''} | {p.get('name') or ''} | {p.get('grade') or ''} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Site topography (aerial map defaults)",
            "",
            "Auto-seeded from backup for the **Aerial layout** tab. Drag items onto the map;  ",
            "card readers may appear as palette items until placed.",
            "",
            f"- Pumps: **{meta.get('pumpCount')}** · Card readers: **{meta.get('cardReaderCount')}** · "
            f"Tanks: **{meta.get('tankCount')}** · Registers: **{meta.get('registerCount')}**",
            f"- Source: {meta.get('source')}",
            f"- Note: {meta.get('note')}",
            "",
            "In Site Console: **Aerial layout** → use **Seed from backup** if the canvas is empty.",
            "",
            "---",
            "",
            "## Survey & photo capture",
            "",
            "Fields that are **not** in the SMS export (fill under **Site survey** packs or photo OCR):",
            "",
            "- LAN / payment NIC / gateway / DNS (site switch reality)",
            "- Host routes and MNSP path notes",
            "- Pump / CRIND firmware versions per position",
            "- Physical topology photos (canopy, tank pad, network closet)",
            "",
            f"- Survey file: `survey/site-survey.json`  ",
            f"- Survey has saved data: **{bool(survey.get('hasSaved'))}**  ",
            f"- Photo captures: **{len(survey.get('photoCaptures') or [])}**",
            "",
            "---",
            "",
            "## Tech flags (from backup scan)",
            "",
        ]
    )
    for f in dossier.get("techFlags") or []:
        lines.append(f"- {f}")
    if not dossier.get("techFlags"):
        lines.append("- *(none)*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## How to refresh this file",
            "",
            "Site Console → Overview / Liferaft / Survey → **Write SITE-INFO.md**  ",
            "or API `POST /api/verifone/sites/{id}/site-info/write`",
            "",
            "_End of SITE-INFO.md_",
            "",
        ]
    )

    text = "\n".join(lines)
    return {
        "ok": True,
        "siteKey": site_key,
        "title": title,
        "markdown": text,
        "passwordStatus": pwd_status,
        "counts": {
            "managedUsers": len(managed_rows) + 1,
            "posUsers": len(pos_rows),
            "pumps": meta.get("pumpCount"),
            "cardReaders": meta.get("cardReaderCount"),
            "tanks": len(tanks),
            "products": len(products),
        },
        "topography": meta,
        "exportPath": str(export_path),
    }


def write_site_info_md(site_key: str, *, also_seed_layout: bool = False) -> dict[str, Any]:
    """Write SITE-INFO.md into the site backup export folder (+ optional layout seed)."""
    built = build_site_info_markdown(site_key)
    export_path = Path(built["exportPath"])
    if not export_path.is_dir():
        raise FileNotFoundError(f"Export path missing: {export_path}")
    md_path = export_path / SITE_INFO_NAME
    md_path.write_text(built["markdown"], encoding="utf-8", newline="\n")

    # Small JSON snapshot for tools (no need to re-parse MD)
    snap_dir = export_path / "survey"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "schema": "FAFO.Commander.SiteInfoSnapshot/1",
        "generatedAt": _utc_now(),
        "siteKey": site_key,
        "title": built.get("title"),
        "passwordStatus": built.get("passwordStatus"),
        "counts": built.get("counts"),
        "topography": built.get("topography"),
        "mdPath": str(md_path),
    }
    (snap_dir / "site-info-snapshot.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")

    layout_res = None
    if also_seed_layout:
        layout_res = apply_topography_to_survey(site_key, only_if_empty=True)

    return {
        "ok": True,
        "path": str(md_path),
        "snapshotPath": str(snap_dir / "site-info-snapshot.json"),
        "markdown": built["markdown"],
        "passwordStatus": built.get("passwordStatus"),
        "counts": built.get("counts"),
        "topography": built.get("topography"),
        "layoutSeed": layout_res,
        "message": (
            f"Wrote {SITE_INFO_NAME} under backup folder "
            f"({built.get('counts', {}).get('posUsers', 0)} POS users, "
            f"Manager letter {((built.get('passwordStatus') or {}).get('letter') or '—')}, "
            f"{((built.get('passwordStatus') or {}).get('passwordDaysLeft'))} days left)."
        ),
    }
