"""
Commander (VAPS) site backup index — SMS/XML config exports.

Industry XML namespaces often still say "sapphire"; product branding is Commander.
Scans a user-chosen local backup root (never committed to git), builds tech dossiers,
and can pre-fill the Pre-Reload Punch List master.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from db import connect

# Marker files that identify a Commander SMS export folder
_MARKERS = ("poscfg.xml", "supportinfo.xml", "registercfg.xml", "paymentcfg.xml", "fuelcfg.xml")
_EXPORT_MIN_HITS = 2


def _local_paths_config() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FAFO" / "local-paths.json"


def get_sites_root(toolbox_root: Path | None = None) -> str | None:
    """Resolve machine-local Commander backup root (VerifoneSitesRoot)."""
    env = os.environ.get("FAFO_VERIFONE_SITES_ROOT", "").strip()
    if env and Path(env).is_dir():
        return str(Path(env).resolve())

    cfg = _local_paths_config()
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            root = str(data.get("VerifoneSitesRoot") or "").strip()
            if root and Path(root).is_dir():
                return str(Path(root).resolve())
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    if toolbox_root:
        link = toolbox_root / "VerifoneLibrary" / "Sites"
        if link.exists():
            try:
                return str(link.resolve())
            except OSError:
                return str(link)
        default = Path(os.environ.get("LOCALAPPDATA", "")) / "FAFO" / "VerifoneSites"
        if default.is_dir():
            return str(default.resolve())
    return None


def set_sites_root(path: str, toolbox_root: Path | None = None) -> dict[str, Any]:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    resolved = str(p.resolve())
    os.environ["FAFO_VERIFONE_SITES_ROOT"] = resolved

    cfg_path = _local_paths_config()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            existing = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing["Version"] = 1
    existing["VerifoneSitesRoot"] = resolved
    existing["UpdatedAt"] = datetime.now().isoformat()
    existing["Machine"] = os.environ.get("COMPUTERNAME", "")
    if toolbox_root:
        existing["ToolboxRoot"] = str(toolbox_root)
    cfg_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    link_ok = False
    link_path = None
    if toolbox_root:
        shell = toolbox_root / "VerifoneLibrary"
        shell.mkdir(parents=True, exist_ok=True)
        link_path = str(shell / "Sites")
        try:
            import subprocess

            lp = shell / "Sites"
            if lp.exists() or lp.is_symlink():
                # remove empty dir or junction
                if lp.is_dir() and not any(lp.iterdir()) and not lp.is_symlink():
                    lp.rmdir()
                else:
                    subprocess.run(["cmd", "/c", "rmdir", str(lp)], capture_output=True)
            r = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(lp), resolved],
                capture_output=True,
                text=True,
            )
            link_ok = lp.exists()
        except OSError:
            link_ok = False

    return {
        "VerifoneSitesRoot": resolved,
        "ConfigPath": str(cfg_path),
        "LinkPath": link_path,
        "LinkOk": link_ok,
    }


def ensure_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vf_exports (
                id TEXT PRIMARY KEY,
                customer TEXT,
                site_label TEXT,
                snapshot TEXT,
                display_name TEXT,
                site_id TEXT,
                service_id TEXT,
                store_phone TEXT,
                postal_code TEXT,
                help_desk TEXT,
                path TEXT UNIQUE NOT NULL,
                relative_path TEXT,
                root_path TEXT,
                xml_count INTEGER DEFAULT 0,
                has_mobile_mop INTEGER DEFAULT 0,
                dcr_rewards INTEGER DEFAULT 0,
                cloud_agent TEXT DEFAULT '',
                register_ids TEXT DEFAULT '',
                named_tanks TEXT DEFAULT '',
                tech_flags TEXT DEFAULT '[]',
                dossier_json TEXT DEFAULT '{}',
                last_scanned REAL DEFAULT 0,
                mtime REAL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_vf_customer ON vf_exports(customer);
            CREATE INDEX IF NOT EXISTS idx_vf_site_id ON vf_exports(site_id);
            CREATE INDEX IF NOT EXISTS idx_vf_root ON vf_exports(root_path);
            """
        )


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(root: ET.Element | None, name: str) -> str | None:
    if root is None:
        return None
    for el in root.iter():
        if _local(el.tag) == name and el.text and el.text.strip():
            return el.text.strip()
    return None


def _prop_value(root: ET.Element | None, name: str) -> str | None:
    if root is None:
        return None
    for el in root.iter():
        if _local(el.tag) == name:
            if "value" in el.attrib:
                return el.attrib.get("value")
            if el.text and el.text.strip():
                return el.text.strip()
    return None


def _load_xml(path: Path) -> ET.Element | None:
    try:
        tree = ET.parse(path)
        return tree.getroot()
    except (ET.ParseError, OSError, ValueError):
        return None


def is_export_folder(path: Path) -> bool:
    if not path.is_dir():
        return False
    hits = sum(1 for m in _MARKERS if (path / m).is_file())
    return hits >= _EXPORT_MIN_HITS


def find_export_folders(root: Path, max_depth: int = 6) -> list[Path]:
    root = root.resolve()
    found: list[Path] = []
    # Walk limited depth
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if depth > max_depth:
            dirnames.clear()
            continue
        # skip junk
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        lower = {f.lower() for f in filenames}
        if "poscfg.xml" in lower or "supportinfo.xml" in lower:
            p = Path(dirpath)
            if is_export_folder(p):
                found.append(p)
                # don't recurse into children of an export root (xml files only typically)
                dirnames.clear()
    return sorted(found)


def _export_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8", errors="replace")).hexdigest()[:20]


def build_dossier(export_path: Path, root: Path) -> dict[str, Any]:
    export_path = export_path.resolve()
    root = root.resolve()
    try:
        rel = str(export_path.relative_to(root))
    except ValueError:
        rel = str(export_path)

    parts = [p for p in Path(rel).parts if p]
    customer = parts[0] if parts else export_path.name
    site_label = parts[1] if len(parts) >= 2 else customer
    snapshot = "\\".join(parts[2:]) if len(parts) >= 3 else ""

    def load(name: str) -> ET.Element | None:
        p = export_path / name
        return _load_xml(p) if p.is_file() else None

    si = load("supportinfo.xml")
    mt = load("mainttelephone.xml")
    mp = load("maintpostal.xml")
    ca = load("cloudagentprop.xml")
    pay = load("paymentcfg.xml")
    reg = load("registercfg.xml")
    fuel = load("fuelcfg.xml")
    prices = load("fuelprices.xml")
    dcr = load("dcridlescreencfg.xml")
    pop = load("popcfg.xml")
    mod = load("managedmodulecfg.xml")
    sap = load("sapphireprop.xml")

    site_id = _text(si, "site") or _text(reg, "site") or _text(pay, "site")
    service_id = _text(si, "storeServiceID")
    help_desk = _text(si, "helpDeskPhoneNumber") or _text(si, "helpDeskPhoneNumbers")
    phone = _text(mt, "maintStoreTelephoneNumber")
    zip_code = _text(mp, "maintStorePostalCode")

    cloud_en = _prop_value(ca, "cia.enableCloudAgent")
    cloud_site = _prop_value(ca, "cia.overrideSiteID")
    cloud_svc = _prop_value(ca, "cia.overrideServiceID")
    cloud_host = _prop_value(ca, "cia.overrideHostBaseURL")
    if not site_id and cloud_site:
        site_id = cloud_site
    if not service_id and cloud_svc:
        service_id = cloud_svc

    mops: list[dict[str, str]] = []
    has_mobile = False
    if pay is not None:
        for el in pay.iter():
            if _local(el.tag) == "mopCode":
                sid = el.attrib.get("sysid", "")
                name = el.attrib.get("name", "")
                mops.append({"sysId": sid, "name": name})
                if sid == "28" or "MOBILE" in name.upper():
                    has_mobile = True

    register_ids: list[str] = []
    receipt_name = None
    if reg is not None:
        seen = set()
        for el in reg.iter():
            if _local(el.tag) == "register" and el.attrib.get("sysid"):
                rid = el.attrib["sysid"]
                if rid not in seen:
                    seen.add(rid)
                    register_ids.append(rid)
            if _local(el.tag) == "logo" and el.attrib.get("sysid") == "2":
                receipt_name = el.attrib.get("message") or receipt_name
            if _local(el.tag) == "banner" and el.attrib.get("sysid") == "2" and not receipt_name:
                receipt_name = el.attrib.get("message")

    tanks: list[dict[str, str]] = []
    if fuel is not None:
        for el in fuel.iter():
            if _local(el.tag) == "fuelTank":
                nm = el.attrib.get("name") or ""
                if re.match(r"^tank\d+$", nm, re.I):
                    continue
                if nm:
                    tanks.append(
                        {
                            "sysId": el.attrib.get("sysid", ""),
                            "name": nm,
                            "prodId": el.attrib.get("NAXMLFuelProdID", ""),
                        }
                    )

    fuel_products: list[dict[str, str]] = []
    if prices is not None:
        for el in prices.iter():
            if _local(el.tag) == "fuelProduct":
                fuel_products.append(
                    {
                        "sysId": el.attrib.get("sysid", ""),
                        "name": el.attrib.get("name", ""),
                        "grade": el.attrib.get("NAXMLFuelGradeID", ""),
                    }
                )

    dcr_rewards = False
    dcr_keys: list[dict[str, str]] = []
    if dcr is not None:
        for el in dcr.iter():
            if _local(el.tag) == "softkey":
                kt = el.attrib.get("keyType") or ""
                tx = el.attrib.get("text") or ""
                if re.search(r"REWARD", kt + " " + tx, re.I):
                    dcr_rewards = True
                if kt and kt != "UNKNOWN":
                    dcr_keys.append({"keyType": kt, "text": tx})

    pop_enabled = _text(pop, "isPopEnable")
    modules: list[str] = []
    if mod is not None:
        for el in mod.iter():
            if _local(el.tag) == "name" and el.text:
                t = el.text.strip()
                if t and len(t) < 48 and t not in modules:
                    modules.append(t)

    mobile_feature = _prop_value(sap, "mobile.feature.enabled")
    xml_count = sum(1 for _ in export_path.glob("*.xml"))

    flags: list[str] = []
    if has_mobile:
        flags.append("Mobile MOP 28 present")
    if dcr_rewards:
        flags.append("DCR REWARDS soft key present")
    if (export_path / "cloudagentprop.xml").is_file():
        if str(cloud_en).lower() in {"1", "yes", "true"}:
            flags.append("Commander Central / C-Site agent enabled in backup")
        else:
            flags.append("cloudagentprop present — plan C-Site re-link after PSI reload")
    if pop_enabled == "1":
        flags.append("POP enabled")
    if re.search(r"pre", snapshot, re.I):
        flags.append("Pre-upgrade snapshot")
    if re.search(r"post", snapshot, re.I):
        flags.append("Post-upgrade snapshot")

    display = receipt_name or site_label or export_path.name
    try:
        mtime = export_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    return {
        "id": _export_id(str(export_path)),
        "product": "Commander",
        "xmlFamily": "Sapphire-namespace SMS export",
        "customer": customer,
        "siteLabel": site_label,
        "snapshot": snapshot,
        "displayName": display,
        "siteId": site_id or "",
        "serviceId": service_id or "",
        "storePhone": phone or "",
        "postalCode": zip_code or "",
        "helpDeskPhone": help_desk or "",
        "receiptBannerName": receipt_name or "",
        "cloudAgentEnabled": cloud_en or "",
        "cloudSiteOverride": cloud_site or "",
        "cloudServiceOverride": cloud_svc or "",
        "cloudHostUrl": cloud_host or "",
        "registerIds": register_ids,
        "registerCount": len(register_ids),
        "hasMobileMop28": has_mobile,
        "mops": mops[:40],
        "namedTanks": tanks,
        "fuelProducts": fuel_products[:30],
        "dcrRewardsSoftKey": dcr_rewards,
        "dcrSoftKeys": dcr_keys[:40],
        "popEnabled": pop_enabled or "",
        "mobileFeatureEnabled": mobile_feature or "",
        "managedModules": modules[:40],
        "techFlags": flags,
        "xmlFileCount": xml_count,
        "relativePath": rel,
        "path": str(export_path),
        "rootPath": str(root),
        "mtime": mtime,
        "prefill": {
            "siteName": display,
            "customer": customer,
            "storeNumber": site_id or "",
            "serviceId": service_id or "",
            "phone": phone or "",
            "postalCode": zip_code or "",
            "helpDesk": help_desk or "",
            "hasCSiteConfig": (export_path / "cloudagentprop.xml").is_file(),
            "hasMobileMop28": has_mobile,
            "dcrRewardsKey": dcr_rewards,
            "registerIds": ",".join(register_ids),
            "namedTanks": ", ".join(t["name"] for t in tanks),
        },
    }


def upsert_dossier(d: dict[str, Any]) -> None:
    ensure_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO vf_exports (
                id, customer, site_label, snapshot, display_name, site_id, service_id,
                store_phone, postal_code, help_desk, path, relative_path, root_path,
                xml_count, has_mobile_mop, dcr_rewards, cloud_agent, register_ids,
                named_tanks, tech_flags, dossier_json, last_scanned, mtime
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                customer=excluded.customer,
                site_label=excluded.site_label,
                snapshot=excluded.snapshot,
                display_name=excluded.display_name,
                site_id=excluded.site_id,
                service_id=excluded.service_id,
                store_phone=excluded.store_phone,
                postal_code=excluded.postal_code,
                help_desk=excluded.help_desk,
                relative_path=excluded.relative_path,
                root_path=excluded.root_path,
                xml_count=excluded.xml_count,
                has_mobile_mop=excluded.has_mobile_mop,
                dcr_rewards=excluded.dcr_rewards,
                cloud_agent=excluded.cloud_agent,
                register_ids=excluded.register_ids,
                named_tanks=excluded.named_tanks,
                tech_flags=excluded.tech_flags,
                dossier_json=excluded.dossier_json,
                last_scanned=excluded.last_scanned,
                mtime=excluded.mtime,
                id=excluded.id
            """,
            (
                d["id"],
                d["customer"],
                d["siteLabel"],
                d["snapshot"],
                d["displayName"],
                d["siteId"],
                d["serviceId"],
                d["storePhone"],
                d["postalCode"],
                d["helpDeskPhone"],
                d["path"],
                d["relativePath"],
                d["rootPath"],
                d["xmlFileCount"],
                1 if d["hasMobileMop28"] else 0,
                1 if d["dcrRewardsSoftKey"] else 0,
                d.get("cloudAgentEnabled") or "",
                ",".join(d.get("registerIds") or []),
                ", ".join(t["name"] for t in (d.get("namedTanks") or [])),
                json.dumps(d.get("techFlags") or []),
                json.dumps(d),
                time.time(),
                float(d.get("mtime") or 0),
            ),
        )


def sync_root(root: str | Path, remove_missing: bool = True) -> dict[str, Any]:
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise FileNotFoundError(f"Backup root not found: {root_p}")

    ensure_tables()
    folders = find_export_folders(root_p)
    dossiers: list[dict[str, Any]] = []
    errors: list[str] = []
    for folder in folders:
        try:
            d = build_dossier(folder, root_p)
            upsert_dossier(d)
            dossiers.append(d)
        except Exception as ex:  # noqa: BLE001 — keep sync resilient
            errors.append(f"{folder}: {ex}")

    removed = 0
    if remove_missing:
        with connect() as conn:
            rows = conn.execute(
                "SELECT path FROM vf_exports WHERE root_path = ?",
                (str(root_p),),
            ).fetchall()
            live = {d["path"] for d in dossiers}
            for (path,) in rows:
                if path not in live:
                    conn.execute("DELETE FROM vf_exports WHERE path = ?", (path,))
                    removed += 1

    # Optional JSON index beside backups (best effort)
    index_path = root_p / "_commander_index.json"
    try:
        index_path.write_text(
            json.dumps(
                {
                    "Schema": "FAFO.Commander.Index/1",
                    "UpdatedAt": datetime.now().isoformat(),
                    "Root": str(root_p),
                    "Count": len(dossiers),
                    "Sites": [
                        {
                            "Customer": d["customer"],
                            "SiteLabel": d["siteLabel"],
                            "Snapshot": d["snapshot"],
                            "DisplayName": d["displayName"],
                            "SiteId": d["siteId"],
                            "ServiceId": d["serviceId"],
                            "StorePhone": d["storePhone"],
                            "Path": d["path"],
                            "RelativePath": d["relativePath"],
                            "TechFlags": d["techFlags"],
                            "Prefill": d["prefill"],
                        }
                        for d in dossiers
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        index_path = None  # type: ignore

    return {
        "ok": True,
        "root": str(root_p),
        "count": len(dossiers),
        "removed": removed,
        "errors": errors,
        "indexPath": str(index_path) if index_path else None,
        "sites": dossiers,
    }


def list_sites(
    q: str | None = None,
    customer: str | None = None,
    root: str | None = None,
) -> list[dict[str, Any]]:
    ensure_tables()
    sql = "SELECT * FROM vf_exports WHERE 1=1"
    params: list[Any] = []
    if root:
        sql += " AND root_path = ?"
        params.append(str(Path(root).resolve()))
    if customer:
        sql += " AND customer LIKE ?"
        params.append(customer.replace("*", "%"))
    if q:
        sql += (
            " AND (customer LIKE ? OR site_label LIKE ? OR display_name LIKE ? "
            "OR site_id LIKE ? OR service_id LIKE ? OR store_phone LIKE ? OR relative_path LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like] * 7)
    sql += " ORDER BY customer COLLATE NOCASE, site_label COLLATE NOCASE, snapshot COLLATE NOCASE"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            dossier = json.loads(d.get("dossier_json") or "{}")
        except json.JSONDecodeError:
            dossier = {}
        d["dossier"] = dossier
        d["techFlags"] = json.loads(d.get("tech_flags") or "[]")
        d["hasMobileMop28"] = bool(d.get("has_mobile_mop"))
        d["dcrRewardsSoftKey"] = bool(d.get("dcr_rewards"))
        out.append(d)
    return out


def get_site(site_key: str) -> dict[str, Any] | None:
    ensure_tables()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM vf_exports WHERE id = ? OR path = ?",
            (site_key, site_key),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["dossier"] = json.loads(d.get("dossier_json") or "{}")
    except json.JSONDecodeError:
        d["dossier"] = {}
    d["techFlags"] = json.loads(d.get("tech_flags") or "[]")
    return d


def _fill_input_after_label(xml: str, label: str, value: str) -> str:
    """Fill the first yellow sInput cell after a given sLabel string."""
    if not value:
        return xml
    # Escape XML special chars in value
    esc = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    # Match label cell then next empty sInput Data cell
    pattern = (
        rf'(<Cell ss:StyleID="sLabel"><Data ss:Type="String">{re.escape(label)}</Data></Cell>'
        rf'[\s\S]*?<Cell[^>]*ss:StyleID="sInput"[^>]*><Data ss:Type="String">)'
        rf'([^<]*)'
        rf'(</Data></Cell>)'
    )

    def repl(m: re.Match[str]) -> str:
        # only fill if empty or whitespace
        if m.group(2).strip():
            return m.group(0)
        return m.group(1) + esc + m.group(3)

    return re.sub(pattern, repl, xml, count=1)


def prefill_punch_list(
    toolbox_root: Path,
    dossier: dict[str, Any],
    destination: str | Path | None = None,
) -> dict[str, Any]:
    master = toolbox_root / "VerifoneLibrary" / "Templates" / "Pre-Reload-Punch-List-MASTER.xml"
    if not master.is_file():
        raise FileNotFoundError(f"Punch list master not found: {master}")

    pre = dossier.get("prefill") or dossier.get("dossier", {}).get("prefill") or {}
    # normalize keys from DB row vs dossier
    site_name = pre.get("siteName") or dossier.get("displayName") or dossier.get("display_name") or ""
    customer = pre.get("customer") or dossier.get("customer") or ""
    store = pre.get("storeNumber") or dossier.get("siteId") or dossier.get("site_id") or ""
    phone = pre.get("phone") or dossier.get("storePhone") or dossier.get("store_phone") or ""
    service = pre.get("serviceId") or dossier.get("serviceId") or dossier.get("service_id") or ""
    postal = pre.get("postalCode") or dossier.get("postalCode") or dossier.get("postal_code") or ""
    path = dossier.get("path") or ""

    if destination is None:
        # Prefer site punchlists folder next to export
        if path and Path(path).is_dir():
            dest_dir = Path(path) / "punchlists"
        else:
            dest_dir = toolbox_root / "VerifoneLibrary" / "Working-PunchLists"
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_c = re.sub(r'[<>:"/\\|?*]+', "-", customer).strip("- ")[:40] or "Site"
        safe_s = re.sub(r'[<>:"/\\|?*]+', "-", store or site_name).strip("- ")[:40] or "Export"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = dest_dir / f"Pre-Reload-PunchList_{safe_c}_{safe_s}_{stamp}.xml"
    else:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

    text = master.read_text(encoding="utf-8")
    banner_old = (
        "MASTER TEMPLATE — open via Launch-PreReload-PunchList so a dated working copy is created. "
        "Do not type site data into the master file."
    )
    # tolerate dash variants
    text = re.sub(
        r"MASTER TEMPLATE.{0,20}open via Launch-PreReload-PunchList so a dated working copy is created\. Do not type site data into the master file\.",
        f"WORKING COPY — prefilled for {customer} / {site_name} (site {store}). Master stays under Templates\\.",
        text,
        count=1,
    )

    text = _fill_input_after_label(text, "Site Name", site_name)
    text = _fill_input_after_label(text, "Site / Store #", store)
    text = _fill_input_after_label(text, "Date", datetime.now().strftime("%Y-%m-%d"))
    text = _fill_input_after_label(text, "Brand / MOC", "Commander / CITGO VAPS")
    # Address-ish: phone + postal as note if no address
    addr_bits = ", ".join(x for x in [phone, postal] if x)
    if addr_bits:
        text = _fill_input_after_label(text, "Address", addr_bits)

    # Detail sheet prefill for maintenance phone / service id labels if present
    text = _fill_input_after_label(text, "Maintenance phone", phone)
    text = _fill_input_after_label(text, "Registration / Service ID", service)
    text = _fill_input_after_label(text, "Site uses C-Site / Commander Central? (Y/N)", "Y" if pre.get("hasCSiteConfig") else "")
    text = _fill_input_after_label(text, "C-Site portal email / account label", "")  # never invent credentials

    # Inject tech summary into first notes block for item 4 if empty pattern exists
    notes_blob = (
        f"Service ID: {service}\\n"
        f"Phone: {phone}\\n"
        f"ZIP: {postal}\\n"
        f"Mobile MOP 28: {pre.get('hasMobileMop28')}\\n"
        f"DCR REWARDS: {pre.get('dcrRewardsKey')}\\n"
        f"Registers: {pre.get('registerIds')}\\n"
        f"Tanks: {pre.get('namedTanks')}\\n"
        f"Backup: {dossier.get('relativePath') or dossier.get('relative_path') or ''}"
    )
    # Soft inject into Network detail Service ID already done

    destination.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "path": str(destination),
        "siteName": site_name,
        "customer": customer,
        "storeNumber": store,
        "serviceId": service,
        "notes": notes_blob.replace("\\n", "\n"),
    }


def status(toolbox_root: Path) -> dict[str, Any]:
    ensure_tables()
    root = get_sites_root(toolbox_root)
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM vf_exports").fetchone()[0]
        last = conn.execute("SELECT MAX(last_scanned) FROM vf_exports").fetchone()[0]
    return {
        "productLabel": "Commander",
        "xmlFamilyNote": "Config XML uses Sapphire namespaces historically; product is Commander.",
        "sitesRoot": root,
        "exportCount": count,
        "lastScanned": last,
        "localPathsConfig": str(_local_paths_config()),
        "masterPunchList": str(
            toolbox_root / "VerifoneLibrary" / "Templates" / "Pre-Reload-Punch-List-MASTER.xml"
        ),
        "punchListMasterExists": (
            toolbox_root / "VerifoneLibrary" / "Templates" / "Pre-Reload-Punch-List-MASTER.xml"
        ).is_file(),
    }
