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


def _parse_version_token(text: str) -> tuple[int, ...]:
    """Extract dotted version like 3.12.40 for sorting; empty -> (0,)."""
    if not text:
        return (0,)
    m = re.search(r"(\d+\.\d+(?:\.\d+){0,3})", text)
    if not m:
        return (0,)
    try:
        return tuple(int(x) for x in m.group(1).split("."))
    except ValueError:
        return (0,)


def _brand_from_driver(driver: str) -> str:
    if not driver:
        return ""
    d = driver.lower()
    # Trailing letter codes on channel drivers (FuelChannel01G, dcrChannel01G)
    m = re.search(r"(?:channel\d*|fuelchannel\d*|dcrchannel\d*)([a-z])$", d, re.I)
    code = m.group(1).upper() if m else ""
    if "gilbarco" in d or code == "G":
        return "Gilbarco"
    if "wayne" in d or code == "W":
        return "Wayne"
    if "tokheim" in d or code == "T":
        return "Tokheim"
    if "bennett" in d or code == "B":
        return "Bennett"
    if "emulation" in d or code == "E":
        return "Emulation"
    if code == "P":
        return "Pump (P-family)"
    if code == "V":
        return "V-family"
    if "unitec" in d:
        return "Unitec"
    if "veeder" in d:
        return "Veeder-Root"
    if "emco" in d:
        return "Emco"
    if "autostik" in d or "auto-stik" in d:
        return "AutoStik"
    if "edim" in d:
        return "EDIM"
    return ""


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _is_none_device(val: str | None) -> bool:
    if not val:
        return True
    v = val.strip().lower()
    return v in {"", "none", "null"} or v.endswith("-none") or v.endswith("_none")


def _config_modules(mod_root: ET.Element | None) -> dict[str, dict[str, str]]:
    """Parse managedmodulecfg configModule blocks → {moduleName: {prop: value}}."""
    out: dict[str, dict[str, str]] = {}
    if mod_root is None:
        return out
    for cm in mod_root.iter():
        if _local(cm.tag) != "configModule":
            continue
        name = None
        props: dict[str, str] = {}
        for child in cm:
            ln = _local(child.tag)
            if ln == "moduleName" and child.text:
                name = child.text.strip()
            elif ln == "configProfile":
                for prop in child.iter():
                    if _local(prop.tag) != "configProp":
                        continue
                    pname = None
                    pval = ""
                    for pc in prop:
                        pl = _local(pc.tag)
                        if pl == "name" and pc.text:
                            pname = pc.text.strip()
                        elif pl == "value":
                            pval = (pc.text or "").strip()
                    if pname:
                        props[pname] = pval
        if name:
            out[name] = props
    return out


def _extract_equipment(mod_root: ET.Element | None, sap: ET.Element | None, dcr_cfg: ET.Element | None) -> dict[str, Any]:
    """
    Build equipment summary from managed modules + related files.
    Only include actively configured items (enabled channels / non-None device types).
    """
    modules = _config_modules(mod_root)
    fuel_channels: list[dict[str, Any]] = []
    dcr_channels: list[dict[str, Any]] = []
    configured_modules: list[dict[str, Any]] = []

    dispenser_brands: list[str] = []
    dcr_brands: list[str] = []

    for name, props in modules.items():
        # Active fuel channels
        if re.match(r"^FuelChannel\d+$", name, re.I):
            enabled = _truthy(props.get("enableChannel") or props.get("enable"))
            if not enabled:
                continue
            driver = props.get("DriverType") or props.get("driverType") or ""
            brand = _brand_from_driver(driver)
            if brand and brand not in dispenser_brands:
                dispenser_brands.append(brand)
            fuel_channels.append(
                {
                    "channel": name,
                    "enabled": True,
                    "driverType": driver,
                    "brand": brand,
                    "portName": props.get("portName") or "",
                    "positions": props.get("totalFuelingPositions") or "",
                    "baudRate": props.get("BaudRate") or props.get("baudRate") or "",
                }
            )
            continue

        # Active DCR channels
        if re.match(r"^dcrChannel\d+$", name, re.I):
            enabled = _truthy(props.get("enable"))
            if not enabled:
                continue
            driver = props.get("driverType") or props.get("DriverType") or ""
            brand = _brand_from_driver(driver)
            if brand and brand not in dcr_brands:
                dcr_brands.append(brand)
            dcr_channels.append(
                {
                    "channel": name,
                    "enabled": True,
                    "driverType": driver,
                    "brand": brand,
                    "portName": props.get("portName") or "",
                    "ipEnabled": _truthy(props.get("ipEnabled")),
                    "baudRate": props.get("baudRate") or props.get("BaudRate") or "",
                }
            )
            continue

        # Skip per-driver template blocks and unassigned defaults
        if re.match(r"^(FuelChannel|dcrChannel)\d+[A-Za-z]", name):
            continue
        if re.search(r"(Positions|Pcts|Port|DeviceOne|DeviceTwo|Channel\d+E)$", name):
            continue
        if name in {"DVR-JLogTypes", "dcrPositions"}:
            continue

        # Top-level logical modules
        device = props.get("deviceType") or props.get("tankModel") or props.get("DriverType") or props.get("driverType") or ""
        hostaddr = props.get("hostaddr") or props.get("hostAddress") or props.get("ipAddress") or ""
        interesting_props = {
            k: v
            for k, v in props.items()
            if v
            and not _is_none_device(v)
            and str(v).strip() not in {"0", "false", "no", "-1", "0.0.0.0", "NONE", "None"}
            and k.lower()
            not in {
                "restroot",
                "maximumdelay",
                "minimumdelay",
                "readtimeout",
                "iptimeout",
                "keepalive",
                "ttl",
            }
        }

        is_active = False
        if name in {"CW", "TLS", "TANK", "ESign", "DVR", "KitchenPrinter", "MoneyOrderPrinter", "FuelRfID", "Speedpass", "PamPOS", "GSM", "VFIPrinter", "MNSP-vpn", "ocs.app"}:
            if name == "MNSP-vpn" and hostaddr and hostaddr not in {"0.0.0.0", ""}:
                is_active = True
            elif name in {"TLS", "TANK", "CW", "ESign"}:
                is_active = not _is_none_device(device)
            elif name == "DVR":
                # Omit stock multicast defaults; only show if explicitly enabled or non-default host
                is_active = _truthy(props.get("enable")) or (
                    props.get("dvr.multicastHost") not in (None, "", "230.0.0.1")
                )
            elif name in {"FuelRfID"}:
                avi = props.get("fuelrfid.aviIPaddress") or ""
                oti = props.get("fuelrfid.otiIPaddress") or ""
                is_active = any(x and x not in {"0.0.0.0", ""} for x in (avi, oti))
            elif name == "Speedpass":
                # Template always references device stubs; require explicit enable
                is_active = _truthy(props.get("enable"))
            else:
                is_active = _truthy(props.get("enable")) or (bool(interesting_props) and not _is_none_device(device))

        if not is_active:
            continue

        configured_modules.append(
            {
                "name": name,
                "deviceType": device if not _is_none_device(device) else "",
                "brand": _brand_from_driver(device) or _brand_from_driver(name),
                "props": interesting_props,
            }
        )

    # TLS / TANK / CW explicit summary
    tls_type = (modules.get("TLS") or {}).get("deviceType") or ""
    tank_type = (modules.get("TANK") or {}).get("tankModel") or (modules.get("TANK") or {}).get("deviceType") or ""
    cw_type = (modules.get("CW") or {}).get("deviceType") or ""
    mnsp = modules.get("MNSP-vpn") or {}

    # Network / host clues from sapphire props + DCR EMV IP
    network: dict[str, str] = {}
    if sap is not None:
        for key in (
            "DailyMsg.server.IP",
            "remote.server.hostname",
            "remote.server.port",
            "remote.server.prefix",
            "sys.amber.alertCountUrl",
            "sys.amber.compareUrl",
            "sys.amber.enable",
            "kp.svc.POS.host",
            "kp.svc.POS.CommID",
        ):
            v = _prop_value(sap, key)
            if v and str(v).strip() not in {"", "NONE", "None", "0"}:
                network[key] = str(v).strip()

    emv_ip = _text(dcr_cfg, "emvIPAddress") if dcr_cfg is not None else None
    if emv_ip:
        network["dcr.emvIPAddress"] = emv_ip
    nfc = _text(dcr_cfg, "nfcMode") if dcr_cfg is not None else None
    graphic = _text(dcr_cfg, "graphicDisplay") if dcr_cfg is not None else None
    screen = _text(dcr_cfg, "graphicScreenSize") if dcr_cfg is not None else None

    payment_nic: dict[str, str] = {}
    # SMS exports rarely include full LAN/Payment NIC; surface what we can
    if emv_ip:
        payment_nic["emvIpOrHost"] = emv_ip
    if mnsp.get("hostaddr"):
        payment_nic["mnspRouter"] = mnsp.get("hostaddr") or ""
        payment_nic["mnspPort"] = mnsp.get("port") or ""
        payment_nic["mnspRestRoot"] = mnsp.get("restRoot") or ""

    routes: list[dict[str, str]] = []
    if mnsp.get("hostaddr"):
        routes.append(
            {
                "name": "MNSP VPN router",
                "host": mnsp.get("hostaddr") or "",
                "port": mnsp.get("port") or "",
                "notes": mnsp.get("restRoot") or "",
            }
        )
    if network.get("DailyMsg.server.IP"):
        routes.append({"name": "DailyMsg server", "host": network["DailyMsg.server.IP"], "port": "", "notes": ""})
    if network.get("remote.server.hostname"):
        routes.append(
            {
                "name": "Remote server",
                "host": network["remote.server.hostname"],
                "port": network.get("remote.server.port") or "",
                "notes": network.get("remote.server.prefix") or "",
            }
        )

    return {
        "dispenserBrands": dispenser_brands,
        "dispenserChannels": fuel_channels,
        "dcrBrands": dcr_brands,
        "dcrChannels": dcr_channels,
        "tankMonitorType": "" if _is_none_device(tank_type) else tank_type,
        "tlsDeviceType": "" if _is_none_device(tls_type) else tls_type,
        "carWashType": "" if _is_none_device(cw_type) else cw_type,
        "mnsp": {
            "hostaddr": mnsp.get("hostaddr") or "",
            "port": mnsp.get("port") or "",
            "restRoot": mnsp.get("restRoot") or "",
            "configured": bool(mnsp.get("hostaddr") and mnsp.get("hostaddr") not in {"0.0.0.0", ""}),
        },
        "configuredModules": configured_modules,
        "network": network,
        "paymentNic": payment_nic,
        "hostRoutes": routes,
        "dcrHardware": {
            "graphicDisplay": graphic or "",
            "screenSize": screen or "",
            "nfcMode": nfc or "",
            "emvIPAddress": emv_ip or "",
            "emvEnabled": _text(dcr_cfg, "isEMVEnabled") if dcr_cfg is not None else "",
            "debitEnabled": _text(dcr_cfg, "isDebitEnabled") if dcr_cfg is not None else "",
        },
        "firmwareVersions": {},  # rarely present in SMS XML; left for future sources
    }


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
    dcr_site = load("pscdcrcfg.xml")
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
    equipment = _extract_equipment(mod, sap, dcr_site)
    # only configured modules (not full template catalog)
    modules = [m["name"] for m in equipment.get("configuredModules") or []]

    mobile_feature = _prop_value(sap, "mobile.feature.enabled")
    xml_count = sum(1 for _ in export_path.glob("*.xml"))
    software_version = ""
    for token in (snapshot, rel, export_path.name):
        m = re.search(r"(\d+\.\d+(?:\.\d+){0,3})", token or "")
        if m:
            software_version = m.group(1)
            break

    # Brand cues from receipt / banners / DCR header
    brand_guess = ""
    brand_blob = " ".join(
        x
        for x in (
            receipt_name or "",
            site_label or "",
            customer or "",
        )
        if x
    ).upper()
    for label in (
        "EXXON",
        "MOBIL",
        "SHELL",
        "CITGO",
        "BP",
        "CHEVRON",
        "TEXACO",
        "MARATHON",
        "SUNOCO",
        "VALERO",
        "PHILLIPS",
        "76",
        "CIRCLE K",
    ):
        if label in brand_blob:
            brand_guess = label.title() if label != "BP" else "BP"
            break

    flags: list[str] = []
    if has_mobile:
        flags.append("Mobile MOP 28 present")
    if dcr_rewards:
        flags.append("DCR REWARDS soft key present")
    if (export_path / "cloudagentprop.xml").is_file():
        if str(cloud_en).lower() in {"1", "yes", "true"}:
            flags.append("Commander Central / C-Site agent enabled in backup")
        else:
            flags.append("cloudagentprop present - plan C-Site re-link after PSI reload")
    if pop_enabled == "1":
        flags.append("POP enabled")
    if re.search(r"pre", snapshot, re.I):
        flags.append("Pre-upgrade snapshot")
    if re.search(r"post", snapshot, re.I):
        flags.append("Post-upgrade snapshot")
    if equipment.get("dispenserBrands"):
        flags.append("Dispenser: " + ", ".join(equipment["dispenserBrands"]))
    if equipment.get("tankMonitorType"):
        flags.append("Tank monitor: " + str(equipment["tankMonitorType"]))
    if equipment.get("mnsp", {}).get("configured"):
        flags.append("MNSP router configured")

    display = receipt_name or site_label or export_path.name
    try:
        mtime = export_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    group_key = f"{customer}|{(site_id or site_label or display)}".lower()

    return {
        "id": _export_id(str(export_path)),
        "product": "Commander",
        "xmlFamily": "Sapphire-namespace SMS export",
        "customer": customer,
        "siteLabel": site_label,
        "snapshot": snapshot,
        "displayName": display,
        "brand": brand_guess,
        "softwareVersion": software_version,
        "groupKey": group_key,
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
        "equipment": equipment,
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
            "brand": brand_guess,
            "softwareVersion": software_version,
            "hasCSiteConfig": (export_path / "cloudagentprop.xml").is_file(),
            "hasMobileMop28": has_mobile,
            "dcrRewardsKey": dcr_rewards,
            "registerIds": ",".join(register_ids),
            "namedTanks": ", ".join(t["name"] for t in tanks),
            "dispenserBrands": ", ".join(equipment.get("dispenserBrands") or []),
            "tankMonitor": equipment.get("tankMonitorType") or "",
            "mnspHost": (equipment.get("mnsp") or {}).get("hostaddr") or "",
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
            "OR site_id LIKE ? OR service_id LIKE ? OR store_phone LIKE ? OR relative_path LIKE ? "
            "OR dossier_json LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like] * 8)
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
        d["softwareVersion"] = dossier.get("softwareVersion") or ""
        d["groupKey"] = dossier.get("groupKey") or f"{d.get('customer')}|{d.get('site_id') or d.get('site_label')}".lower()
        d["brand"] = dossier.get("brand") or ""
        d["equipment"] = dossier.get("equipment") or {}
        out.append(d)
    return out


def group_sites(
    q: str | None = None,
    customer: str | None = None,
    root: str | None = None,
) -> list[dict[str, Any]]:
    """
    Stack exports for the same physical site.
    Latest software version / newest mtime is primary; others nested as versions.
    """
    flat = list_sites(q=q, customer=customer, root=root)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for s in flat:
        key = s.get("groupKey") or f"{s.get('customer')}|{s.get('site_id') or s.get('site_label')}".lower()
        buckets.setdefault(key, []).append(s)

    groups: list[dict[str, Any]] = []
    for key, items in buckets.items():
        items_sorted = sorted(
            items,
            key=lambda x: (
                _parse_version_token(x.get("softwareVersion") or x.get("snapshot") or ""),
                float(x.get("mtime") or 0),
                str(x.get("snapshot") or ""),
            ),
            reverse=True,
        )
        primary = items_sorted[0]
        d = primary.get("dossier") or {}
        groups.append(
            {
                "groupKey": key,
                "customer": primary.get("customer"),
                "siteId": primary.get("site_id") or d.get("siteId"),
                "siteLabel": primary.get("site_label") or d.get("siteLabel"),
                "displayName": primary.get("display_name") or d.get("displayName"),
                "brand": primary.get("brand") or d.get("brand") or "",
                "storePhone": primary.get("store_phone") or d.get("storePhone"),
                "serviceId": primary.get("service_id") or d.get("serviceId"),
                "versionCount": len(items_sorted),
                "latestVersion": primary.get("softwareVersion") or d.get("softwareVersion") or primary.get("snapshot") or "",
                "latestId": primary.get("id"),
                "latestPath": primary.get("path"),
                "equipmentSummary": {
                    "dispenserBrands": (d.get("equipment") or {}).get("dispenserBrands") or [],
                    "tankMonitorType": (d.get("equipment") or {}).get("tankMonitorType") or "",
                    "mnspHost": ((d.get("equipment") or {}).get("mnsp") or {}).get("hostaddr") or "",
                    "dcrBrands": (d.get("equipment") or {}).get("dcrBrands") or [],
                },
                "versions": [
                    {
                        "id": v.get("id"),
                        "snapshot": v.get("snapshot") or v.get("relative_path"),
                        "softwareVersion": v.get("softwareVersion") or (v.get("dossier") or {}).get("softwareVersion") or "",
                        "relativePath": v.get("relative_path"),
                        "path": v.get("path"),
                        "mtime": v.get("mtime"),
                        "xmlCount": v.get("xml_count"),
                        "isLatest": i == 0,
                        "techFlags": v.get("techFlags") or [],
                        "hasMobileMop28": v.get("hasMobileMop28"),
                        "dcrRewardsSoftKey": v.get("dcrRewardsSoftKey"),
                    }
                    for i, v in enumerate(items_sorted)
                ],
            }
        )

    groups.sort(key=lambda g: (str(g.get("customer") or "").lower(), str(g.get("displayName") or "").lower()))
    return groups


def _safe_export_path(site_key: str) -> Path:
    row = get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    p = Path(row["path"]).resolve()
    root = Path(row.get("root_path") or "").resolve() if row.get("root_path") else None
    if root and root not in p.parents and p != root:
        # also allow path equal under root
        try:
            p.relative_to(root)
        except ValueError as e:
            raise PermissionError("Export path outside configured root") from e
    if not p.is_dir():
        raise FileNotFoundError(f"Export folder missing: {p}")
    return p


def list_export_files(site_key: str) -> list[dict[str, Any]]:
    export_dir = _safe_export_path(site_key)
    files = []
    for f in sorted(export_dir.iterdir(), key=lambda x: x.name.lower()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in {".xml", ".json", ".txt", ".csv", ".log", ".cfg", ".ini"}:
            continue
        try:
            st = f.stat()
            size = st.st_size
            mtime = st.st_mtime
        except OSError:
            size = 0
            mtime = 0
        files.append(
            {
                "name": f.name,
                "size": size,
                "mtime": mtime,
                "ext": f.suffix.lower(),
            }
        )
    return files


def read_export_file(site_key: str, filename: str, max_bytes: int = 2_000_000) -> dict[str, Any]:
    export_dir = _safe_export_path(site_key)
    # prevent path traversal
    name = Path(filename).name
    if name != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise PermissionError("Invalid filename")
    path = (export_dir / name).resolve()
    try:
        path.relative_to(export_dir)
    except ValueError as e:
        raise PermissionError("File outside export folder") from e
    if not path.is_file():
        raise FileNotFoundError(name)
    size = path.stat().st_size
    truncated = size > max_bytes
    data = path.read_bytes()[:max_bytes]
    # decode
    text: str
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return {
        "name": name,
        "path": str(path),
        "size": size,
        "truncated": truncated,
        "content": text,
    }


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
