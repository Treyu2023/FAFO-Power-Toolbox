"""
Site Intelligence Registry — persistent, growing picture of every site we know.

Philosophy (sellable tech product):
  - ANY mention of a site creates a file, even if we only know a name or IP.
  - Knowledge accumulates over time (backup, survey, sticky notes, manual, web).
  - Backups seed layout/equipment; notes seed addresses/IPs/passwords.
  - Never delete a site shell just because data is thin.

Storage:
  %LOCALAPPDATA%\\FAFO\\site-registry\\
    index.json           — catalog of all site keys
    sites\\{key}.json     — full dossier shell + source log
    cache-policy.json    — local hot/cold memory allotment (for future OneDrive/etc.)

Also ensures Liferaft master profiles under site-profiles\\ so tech tools stay in sync.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import site_profile_ops as sprof
import verifone_ops as vf

SCHEMA = "FAFO.SiteRegistry/1"
_LOCK = threading.RLock()

# Rough local area seeds (tech can expand) — NC triad / nearby markets
DEFAULT_AREA_HINTS = [
    "Greensboro",
    "High Point",
    "Winston-Salem",
    "Burlington",
    "Asheboro",
    "Kernersville",
    "Thomasville",
    "Reidsville",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fafo() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "FAFO"
    base.mkdir(parents=True, exist_ok=True)
    return base


def registry_dir() -> Path:
    d = _fafo() / "site-registry"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sites").mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return registry_dir() / "index.json"


def _site_path(key: str) -> Path:
    return registry_dir() / "sites" / f"{key}.json"


def _policy_path() -> Path:
    return registry_dir() / "cache-policy.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def site_key_from_name(name: str, extra: str = "") -> str:
    raw = f"{(name or '').strip().lower()}|{(extra or '').strip().lower()}"
    h = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "site").lower())[:48].strip("-") or "site"
    return f"{slug}_{h}"


def empty_registry_site(
    *,
    display_name: str = "",
    source: str = "manual",
    note: str = "",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "key": "",
        "displayName": display_name or "Unknown site",
        "aliases": [],
        "status": "stub",  # stub | partial | rich
        "createdAt": _utc_now(),
        "updatedAt": _utc_now(),
        "lastTouchedAt": _utc_now(),
        "identity": {
            "customer": display_name or "",
            "siteId": "",
            "serviceId": "",
            "address": "",
            "city": "",
            "state": "NC",
            "zip": "",
            "phone": "",
            "brand": "",
            "storeNumber": "",
            "latitude": "",
            "longitude": "",
        },
        "commander": {
            "hostIp": "",
            "baseVersion": "",
            "notes": "",
        },
        "credentials": {
            "managerUser": "Manager",
            "managerPasswordHint": "",
            "notes": "",
        },
        "equipment": {
            "pumps": [],
            "tanks": [],
            "registers": [],
            "dispenserBrands": [],
            "dcrBrands": [],
            "tankMonitor": "",
            "notes": "",
        },
        "layout": {
            "hasLayout": False,
            "itemCount": 0,
            "lastSeededAt": None,
        },
        "sources": [],  # [{at, kind, detail}]
        "knowledgeLog": [],  # freeform append-only facts
        "links": {
            "exportId": "",
            "exportPath": "",
            "groupKey": "",
            "liferaftKey": "",
        },
        "completeness": 0,
        "areaTags": [],
        "rawNotes": note or "",
    }


def default_cache_policy() -> dict[str, Any]:
    """
    Local hot cache vs long-term cold store (OneDrive/Google later).
    Password for bulk zip is NEVER stored in plain form on the client app —
    only a server-issued unlock token for authorized seats (future).
    """
    return {
        "schema": SCHEMA,
        "localHotDays": 14,
        "maxLocalGb": 40,
        "preferExternalDrive": False,
        "externalDrivePath": "",
        "coldStore": "onedrive",  # onedrive | gdrive | custom | none
        "coldStorePath": "",
        "autoEvictUnused": True,
        "allowFullMirror": True,
        "fullMirrorRequiresServerUnlock": True,
        "fullMirrorNote": (
            "Full catalog ZIP is password-protected. The password is not stored in the "
            "download package; the app must obtain an unlock token from your FAFO license "
            "server so casual copy/theft of the ZIP is useless offline."
        ),
        "updatedAt": None,
    }


def get_cache_policy() -> dict[str, Any]:
    p = default_cache_policy()
    stored = _read_json(_policy_path(), None)
    if isinstance(stored, dict):
        p.update(stored)
    return p


def save_cache_policy(patch: dict[str, Any]) -> dict[str, Any]:
    p = get_cache_policy()
    for k, v in (patch or {}).items():
        if k in p and k != "schema":
            p[k] = v
    p["updatedAt"] = _utc_now()
    _write_json(_policy_path(), p)
    return p


def _load_index() -> dict[str, Any]:
    idx = _read_json(_index_path(), None)
    if not isinstance(idx, dict):
        idx = {"schema": SCHEMA, "sites": {}, "updatedAt": None}
    idx.setdefault("sites", {})
    return idx


def _save_index(idx: dict[str, Any]) -> None:
    idx["updatedAt"] = _utc_now()
    idx["schema"] = SCHEMA
    _write_json(_index_path(), idx)


def _score_completeness(site: dict[str, Any]) -> int:
    score = 0
    ident = site.get("identity") or {}
    cmd = site.get("commander") or {}
    eq = site.get("equipment") or {}
    if ident.get("customer") or site.get("displayName"):
        score += 10
    if ident.get("address") or ident.get("city"):
        score += 15
    if ident.get("phone"):
        score += 10
    if cmd.get("hostIp"):
        score += 20
    if (site.get("links") or {}).get("exportId"):
        score += 20
    if eq.get("pumps") or eq.get("registers"):
        score += 15
    if (site.get("layout") or {}).get("hasLayout"):
        score += 10
    return min(100, score)


def _status_for_score(score: int) -> str:
    if score >= 70:
        return "rich"
    if score >= 30:
        return "partial"
    return "stub"


def _append_source(site: dict[str, Any], kind: str, detail: str) -> None:
    site.setdefault("sources", []).append(
        {"at": _utc_now(), "kind": kind, "detail": (detail or "")[:400]}
    )
    # keep last 40
    site["sources"] = site["sources"][-40:]


def _append_fact(site: dict[str, Any], fact: str) -> None:
    fact = (fact or "").strip()
    if not fact:
        return
    log = site.setdefault("knowledgeLog", [])
    if any(x.get("text") == fact for x in log[-20:]):
        return
    log.append({"at": _utc_now(), "text": fact[:500]})
    site["knowledgeLog"] = log[-200:]


def load_site(key: str) -> dict[str, Any] | None:
    return _read_json(_site_path(key), None)


def list_sites(*, q: str = "", status: str = "") -> dict[str, Any]:
    idx = _load_index()
    rows = []
    ql = (q or "").lower().strip()
    for key, meta in (idx.get("sites") or {}).items():
        if status and meta.get("status") != status:
            continue
        blob = f"{meta.get('displayName','')} {meta.get('city','')} {meta.get('hostIp','')} {key}".lower()
        if ql and ql not in blob:
            continue
        rows.append({"key": key, **meta})
    rows.sort(key=lambda r: (r.get("displayName") or r["key"]).lower())
    return {
        "ok": True,
        "count": len(rows),
        "sites": rows,
        "registryDir": str(registry_dir()),
        "policy": get_cache_policy(),
    }


def ensure_site(
    *,
    display_name: str = "",
    host_ip: str = "",
    address: str = "",
    city: str = "",
    phone: str = "",
    site_id: str = "",
    export_id: str = "",
    export_path: str = "",
    group_key: str = "",
    source: str = "manual",
    note: str = "",
    facts: list[str] | None = None,
    area_tags: list[str] | None = None,
    equipment: dict[str, Any] | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """
    Create or enrich a site file. ALWAYS leaves a durable record.
    Thin data is fine — stubs grow into rich dossiers over time.
    """
    display_name = (display_name or "").strip() or (site_id and f"Site {site_id}") or (host_ip and f"IP {host_ip}") or "Unknown site"
    with _LOCK:
        idx = _load_index()
        # try match existing by export, IP, or name
        found_key = key
        if not found_key and export_id:
            for k, m in (idx.get("sites") or {}).items():
                if m.get("exportId") == export_id:
                    found_key = k
                    break
        if not found_key and host_ip:
            for k, m in (idx.get("sites") or {}).items():
                if m.get("hostIp") == host_ip:
                    found_key = k
                    break
        if not found_key:
            # name match
            dn = display_name.lower()
            for k, m in (idx.get("sites") or {}).items():
                if (m.get("displayName") or "").lower() == dn:
                    found_key = k
                    break
        if not found_key:
            found_key = site_key_from_name(display_name, host_ip or site_id or export_id)

        site = load_site(found_key) or empty_registry_site(display_name=display_name, source=source, note=note)
        site["key"] = found_key
        site["displayName"] = display_name or site.get("displayName")
        site["updatedAt"] = _utc_now()
        site["lastTouchedAt"] = _utc_now()

        ident = site.setdefault("identity", {})
        if display_name:
            ident["customer"] = ident.get("customer") or display_name
        for field, val in (
            ("siteId", site_id),
            ("address", address),
            ("city", city),
            ("phone", phone),
        ):
            if val and not ident.get(field):
                ident[field] = val

        cmd = site.setdefault("commander", {})
        if host_ip and not cmd.get("hostIp"):
            cmd["hostIp"] = host_ip

        links = site.setdefault("links", {})
        if export_id:
            links["exportId"] = export_id
        if export_path:
            links["exportPath"] = export_path
        if group_key:
            links["groupKey"] = group_key
            links["liferaftKey"] = group_key

        if equipment:
            eq = site.setdefault("equipment", {})
            for k, v in equipment.items():
                if v in (None, "", []):
                    continue
                if isinstance(v, list) and not eq.get(k):
                    eq[k] = v
                elif not isinstance(v, list) and not eq.get(k):
                    eq[k] = v

        if area_tags:
            tags = set(site.get("areaTags") or [])
            tags.update(t for t in area_tags if t)
            site["areaTags"] = sorted(tags)

        if note:
            site["rawNotes"] = ((site.get("rawNotes") or "") + "\n" + note).strip()[:8000]

        for f in facts or []:
            _append_fact(site, f)
        _append_source(site, source, note or display_name)

        site["completeness"] = _score_completeness(site)
        site["status"] = _status_for_score(site["completeness"])

        _write_json(_site_path(found_key), site)
        idx.setdefault("sites", {})[found_key] = {
            "displayName": site["displayName"],
            "status": site["status"],
            "completeness": site["completeness"],
            "city": (site.get("identity") or {}).get("city") or "",
            "hostIp": (site.get("commander") or {}).get("hostIp") or "",
            "exportId": (site.get("links") or {}).get("exportId") or "",
            "updatedAt": site["updatedAt"],
            "areaTags": site.get("areaTags") or [],
        }
        _save_index(idx)

        # Always ensure a Liferaft master profile shell exists (even thin)
        try:
            gk = group_key or display_name or found_key
            sprof.get_master_profile(group_key=gk, export_id=export_id or None, merge_sources=bool(export_id))
            # touch identity on liferaft if empty
            prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
            patch: dict[str, Any] = {}
            idp = prof.get("identity") or {}
            if display_name and not idp.get("customer"):
                patch.setdefault("identity", {})["customer"] = display_name
                patch.setdefault("identity", {})["displayName"] = display_name
            if site_id and not idp.get("siteId"):
                patch.setdefault("identity", {})["siteId"] = site_id
            if address and not idp.get("address"):
                patch.setdefault("identity", {})["address"] = address
            if city and not idp.get("city"):
                patch.setdefault("identity", {})["city"] = city
            if phone and not idp.get("phone"):
                patch.setdefault("identity", {})["phone"] = phone
            if host_ip:
                if not (prof.get("commander") or {}).get("hostIp"):
                    patch.setdefault("commander", {})["hostIp"] = host_ip
                if not (prof.get("network") or {}).get("lanIp"):
                    patch.setdefault("network", {})["lanIp"] = host_ip
            if patch:
                sprof.save_master_profile(gk, patch, export_id=export_id or None, merge_sources=False)
            site["links"]["liferaftKey"] = gk
            _write_json(_site_path(found_key), site)
        except Exception as e:  # noqa: BLE001
            _append_fact(site, f"Liferaft ensure note: {e}")
            _write_json(_site_path(found_key), site)

        return {"ok": True, "site": site, "created": True, "key": found_key}


def ingest_backups(*, sync_folders: bool = True) -> dict[str, Any]:
    """Pull every SMS export into the registry + ensure liferaft shells."""
    if sync_folders:
        try:
            vf.sync_sites()
        except Exception:
            pass
    sites = []
    try:
        sites = vf.list_sites() or []
    except Exception:
        sites = []

    created = 0
    updated = 0
    errors = []
    for row in sites:
        try:
            dossier = row.get("dossier") or {}
            name = (
                row.get("customer")
                or dossier.get("customer")
                or dossier.get("displayName")
                or row.get("display_name")
                or row.get("id")
                or "Backup site"
            )
            host = ""
            eq = dossier.get("equipment") or row.get("equipment") or {}
            net = eq.get("network") or {}
            host = net.get("lanIp") or net.get("ip") or row.get("host") or ""
            positions = eq.get("fuelingPositions") or []
            pumps = []
            for p in positions:
                if isinstance(p, dict) and p.get("position") is not None:
                    pumps.append(str(p.get("position")))
            registers = dossier.get("registerIds") or []
            if isinstance(registers, str):
                registers = [x.strip() for x in registers.split(",") if x.strip()]
            before = load_site(site_key_from_name(name, row.get("id") or ""))
            res = ensure_site(
                display_name=str(name),
                host_ip=str(host or ""),
                site_id=str(dossier.get("siteId") or row.get("site_id") or ""),
                phone=str(dossier.get("storePhone") or row.get("store_phone") or ""),
                export_id=str(row.get("id") or ""),
                export_path=str(row.get("path") or ""),
                group_key=str(dossier.get("groupKey") or row.get("group_key") or name),
                source="sms_backup",
                note=f"Ingested backup {row.get('id')}",
                equipment={
                    "pumps": pumps,
                    "registers": list(registers)[:16],
                    "dispenserBrands": eq.get("dispenserBrands") or [],
                    "dcrBrands": eq.get("dcrBrands") or [],
                    "tanks": dossier.get("namedTanks") or [],
                },
                area_tags=[t for t in DEFAULT_AREA_HINTS if t.lower() in str(name).lower()],
                facts=[
                    f"Backup path: {row.get('path')}",
                    f"Software: {dossier.get('softwareVersion') or row.get('software_version') or '?'}",
                ],
            )
            if before:
                updated += 1
            else:
                created += 1
            # touch layout flag from survey if present
            try:
                if row.get("id"):
                    survey = vf.get_survey(row["id"]) or {}
                    lay = survey.get("layout") or {}
                    items = lay.get("items") or []
                    if items:
                        sk = res["key"]
                        site = load_site(sk)
                        if site:
                            site.setdefault("layout", {})["hasLayout"] = True
                            site["layout"]["itemCount"] = len(items)
                            site["completeness"] = _score_completeness(site)
                            site["status"] = _status_for_score(site["completeness"])
                            _write_json(_site_path(sk), site)
            except Exception:
                pass
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:200])

    return {
        "ok": True,
        "backupRows": len(sites),
        "created": created,
        "updated": updated,
        "errors": errors[:10],
        "registry": list_sites(),
    }


def _strip_sticky_markup(text: str) -> str:
    # Sticky Notes stores RTF-like \id=... tokens
    t = re.sub(r"\\id=[^\s\\]+", " ", text or "")
    t = re.sub(r"\\[a-zA-Z]+\d*", " ", t)
    t = re.sub(r"[{}]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def import_sticky_notes() -> dict[str, Any]:
    """
    Read Windows Sticky Notes (plum.sqlite) and create/enrich site stubs
    from IPs, phone numbers, and store-ish lines.
    """
    p = Path(os.environ.get("LOCALAPPDATA") or "") / (
        "Packages/Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe/LocalState/plum.sqlite"
    )
    if not p.is_file():
        return {"ok": False, "message": "Sticky Notes database not found on this PC", "path": str(p)}

    notes: list[str] = []
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        cur = con.cursor()
        for (text, deleted) in cur.execute("SELECT Text, DeletedAt FROM Note"):
            if deleted:
                continue
            clean = _strip_sticky_markup(text or "")
            if clean and len(clean) > 3:
                notes.append(clean)
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"Could not read Sticky Notes: {e}"}

    ip_re = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")
    phone_re = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
    # Strong store brand / site signals only (avoid creating hundreds of junk stubs)
    brand_hints = re.compile(
        r"\b(quick\s*n\s*easy|qne\b|circle\s*k|shell\b|bp\b|exxon|mobil|citgo|marathon|valero|"
        r"kangaroo|raceway|gate\s*petroleum|weigel|mapco|spinx|liberty|flash\s*foods|"
        r"family\s*fare|pilot\b|loves\b|love'?s|speedway|wawa|sheetz|caseys|"
        r"verifone|commander|sapphire|c-store|fueling\s*position)\b",
        re.I,
    )
    private_ip = re.compile(
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
    )

    ensured = 0
    facts_added = 0
    skipped_weak = 0
    seen_names: set[str] = set()

    for note in notes:
        ips = private_ip.findall(note)  # only private LAN IPs (Commander-like)
        phones = phone_re.findall(note)
        has_brand = bool(brand_hints.search(note))
        # Require a strong signal: private IP, or brand + (phone or city-ish address digit)
        if not ips and not has_brand:
            skipped_weak += 1
            continue
        if has_brand and not ips and not phones and not re.search(r"\d{3,}", note):
            # brand mention alone in a random note — skip
            skipped_weak += 1
            continue

        # Prefer a brand-bearing chunk as display name
        chunks = [c.strip() for c in re.split(r"[\n;|]+", note) if c.strip()]
        cand = next((c[:100] for c in chunks if brand_hints.search(c)), None)
        if not cand and ips:
            cand = f"Commander {ips[0]}"
        if not cand:
            cand = note[:80]
        key_name = cand.lower()
        if key_name in seen_names:
            # still attach extra IPs as facts on existing if we can match
            skipped_weak += 1
            continue
        seen_names.add(key_name)

        host = ips[0] if ips else ""
        phone = phones[0] if phones else ""
        tags = [a for a in DEFAULT_AREA_HINTS if a.lower() in note.lower()]
        res = ensure_site(
            display_name=cand,
            host_ip=host,
            phone=phone,
            source="sticky_notes",
            note=note[:500],
            facts=[f"From sticky note: {cand}"]
            + ([f"IP {host}"] if host else [])
            + ([f"Phone {phone}"] if phone else []),
            area_tags=tags,
        )
        ensured += 1
        facts_added += 1
        site = res.get("site") or {}
        for extra_ip in ips[1:4]:
            _append_fact(site, f"Also saw IP {extra_ip} in sticky notes")
            facts_added += 1
        if site.get("key"):
            site["updatedAt"] = _utc_now()
            site["completeness"] = _score_completeness(site)
            site["status"] = _status_for_score(site["completeness"])
            _write_json(_site_path(site["key"]), site)

    return {
        "ok": True,
        "notesScanned": len(notes),
        "sitesTouched": ensured,
        "skippedWeak": skipped_weak,
        "factsAdded": facts_added,
        "message": (
            f"Scanned {len(notes)} sticky notes · "
            f"{ensured} site record(s) with strong signals · "
            f"{skipped_weak} weak notes ignored"
        ),
    }


def seed_area_stubs(cities: list[str] | None = None) -> dict[str, Any]:
    """
    Create placeholder area tags / research stubs for local markets.
    Does NOT invent fake store names — only city buckets for future scraping.
    """
    cities = cities or DEFAULT_AREA_HINTS
    out = []
    for city in cities:
        res = ensure_site(
            display_name=f"{city} area — research bucket",
            city=city,
            source="area_seed",
            note=f"Placeholder for {city} market sites to be filled from backups, notes, and web research.",
            area_tags=[city, "research-bucket"],
            facts=[f"Market research shell for {city}, NC area"],
        )
        out.append(res["key"])
    return {"ok": True, "buckets": out, "message": f"Ensured {len(out)} area research shells"}


def quick_start(*, seed_layouts: bool = True, import_notes: bool = True) -> dict[str, Any]:
    """
    One-button technician bootstrap:
      1) Sync SMS backup folders
      2) Ingest every export into registry + liferaft
      3) Import sticky notes (optional)
      4) Seed aerial layouts from backup when empty
    """
    steps: list[dict[str, Any]] = []
    # 1–2 backups
    ing = ingest_backups(sync_folders=True)
    steps.append({"step": "ingest_backups", **{k: ing[k] for k in ("backupRows", "created", "updated", "ok")}})

    # 3 sticky notes
    sticky = {"ok": False, "skipped": True}
    if import_notes:
        sticky = import_sticky_notes()
    steps.append({"step": "sticky_notes", **sticky})

    # 4 layout seeds
    layout_results = []
    if seed_layouts:
        try:
            import site_info_ops as site_info

            for row in (vf.list_sites() or [])[:80]:
                sid = row.get("id")
                if not sid:
                    continue
                try:
                    res = site_info.apply_topography_to_survey(sid, only_if_empty=True)
                    layout_results.append(
                        {
                            "exportId": sid,
                            "skipped": res.get("skipped"),
                            "ok": res.get("ok", True),
                            "message": res.get("message"),
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    layout_results.append({"exportId": sid, "ok": False, "error": str(e)[:120]})
        except Exception as e:  # noqa: BLE001
            layout_results.append({"ok": False, "error": str(e)})
    steps.append(
        {
            "step": "seed_layouts",
            "count": len(layout_results),
            "seeded": sum(1 for r in layout_results if r.get("ok") and not r.get("skipped")),
            "skipped": sum(1 for r in layout_results if r.get("skipped")),
        }
    )

    reg = list_sites()
    return {
        "ok": True,
        "message": (
            f"Quick Start complete · {reg['count']} sites in registry · "
            f"{ing.get('backupRows', 0)} backups · "
            f"layouts seeded where empty"
        ),
        "steps": steps,
        "registryCount": reg["count"],
        "registryDir": reg["registryDir"],
        "policy": get_cache_policy(),
        "next": [
            "Open a site → Aerial layout → refine placements",
            "Fill Liferaft Manager letter + network IPs",
            "Later: enable cold store (OneDrive) when catalog is large",
            "Public FAFO Petro inventory never includes cost (Investor Portal rule)",
        ],
    }


def product_roadmap() -> dict[str, Any]:
    """Machine-readable roadmap for Help / sales pitch."""
    return {
        "ok": True,
        "product": "FAFO Site Intelligence (Commander tech platform)",
        "valueProp": (
            "Every site you touch becomes a living dossier — layout, passwords scheme, "
            "equipment, sticky-note scraps — so the next tech arrives already sharp. "
            "That's what you sell: time saved on every call."
        ),
        "phases": [
            {
                "id": 1,
                "name": "Local gold (now)",
                "items": [
                    "Site registry always-create shells",
                    "Quick Start from backups + sticky notes",
                    "Layout seed from SMS equipment",
                    "Liferaft letter-cycle + journal + IE",
                ],
            },
            {
                "id": 2,
                "name": "Smarter gather",
                "items": [
                    "Paste/import call notes → auto fields",
                    "Optional web research for brand/address (manual confirm)",
                    "Greensboro / triad market buckets",
                    "Photo OCR survey packs → layout labels",
                ],
            },
            {
                "id": 3,
                "name": "Hot/cold storage",
                "items": [
                    "14-day hot local cache (configurable GB)",
                    "Cold archive on OneDrive/Google/external",
                    "Pull site pack on demand; evict after idle",
                    "Full mirror ZIP with server-side unlock password (anti-theft without encrypting whole app)",
                ],
            },
            {
                "id": 4,
                "name": "Sellable multi-tech",
                "items": [
                    "Per-tech seat + fleet of their work",
                    "Shared cold catalog, private credentials vault",
                    "License server issues unlock tokens for bulk export only",
                ],
            },
        ],
        "antiTheft": {
            "approach": "password-protected archive + remote unlock token",
            "not": "DRM on every local file (painful for techs)",
            "rule": "Daily work stays local & fast; bulk steal-the-catalog is locked",
        },
    }
