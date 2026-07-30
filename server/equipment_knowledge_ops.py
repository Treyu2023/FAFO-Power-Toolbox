"""
Equipment field knowledge — site-specific pros/cons, compatibility, day-zero notes.

Technicians edit these (learned on site). Most notes are site-specific; cookie-cutter
chains can promote entries to a shared library after a short approval checklist.

Designed to attach later to 2D layout items and 3D/CAD-lite explode views
(Gilbarco-class service software is expensive — we close the gap with our own
low-poly kits + this knowledge layer, not a full CAD license).

Storage: %LOCALAPPDATA%\\FAFO\\equipment-knowledge\\
  site\\{siteKey}.json     — entries for one store
  library\\entries.json    — approved multi-site reusable knowledge
  pending\\{id}.json       — awaiting promote approval
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "FAFO.EquipmentKnowledge/1"
_LOCK = threading.RLock()

# Short questions before a site tip becomes multi-site library content
PROMOTE_CRITERIA = [
    {
        "id": "same_oem_family",
        "question": "Same equipment family / manufacturer class (e.g. Gilbarco CRIND class, Wayne Ovation-class)?",
        "requiredYes": True,
    },
    {
        "id": "not_site_wiring",
        "question": "This is NOT only about this store’s unique wiring, IP, or one-off cabling?",
        "requiredYes": True,
    },
    {
        "id": "not_one_customer_quirk",
        "question": "Useful beyond a single weird customer preference (or you marked it as chain cookie-cutter)?",
        "requiredYes": True,
    },
    {
        "id": "compat_checked",
        "question": "Compatibility notes list brands/models this applies to (or N/A with reason)?",
        "requiredYes": True,
    },
    {
        "id": "second_eyes",
        "question": "You or another tech would trust this on a second similar site without re-discovering day-zero pain?",
        "requiredYes": True,
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fafo() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "FAFO"
    base.mkdir(parents=True, exist_ok=True)
    return base


def root_dir() -> Path:
    d = _fafo() / "equipment-knowledge"
    d.mkdir(parents=True, exist_ok=True)
    (d / "site").mkdir(parents=True, exist_ok=True)
    (d / "library").mkdir(parents=True, exist_ok=True)
    (d / "pending").mkdir(parents=True, exist_ok=True)
    return d


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


def _safe_key(s: str) -> str:
    h = re.sub(r"[^a-z0-9]+", "-", (s or "site").lower())[:48].strip("-") or "site"
    return h


def site_file(site_key: str) -> Path:
    return root_dir() / "site" / f"{_safe_key(site_key)}.json"


def library_file() -> Path:
    return root_dir() / "library" / "entries.json"


def empty_entry(
    *,
    site_key: str = "",
    export_id: str = "",
    group_key: str = "",
    author: str = "tech",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "id": uuid.uuid4().hex[:12],
        "scope": "site",  # site | library | pending
        "siteKey": site_key,
        "exportId": export_id,
        "groupKey": group_key,
        "title": "",
        "equipment": {
            "type": "pump",  # pump | crind | tank | register | tls | network | other
            "manufacturer": "",
            "modelClass": "",
            "layoutItemId": "",  # optional link to aerial layout item
            "tags": [],
        },
        "pros": [],
        "cons": [],
        "compat": [],  # strings: "works with X", "breaks with Y"
        "dayZero": [],  # day-one gotchas
        "notes": "",
        # Future 3D / CAD-lite
        "view3d": {
            "modelKey": "",  # e.g. gilbarco-pump-generic
            "explodeSupported": False,
            "hotspots": [],  # [{id, label, note}]
        },
        "transfer": {
            "cookieCutter": False,
            "appliesToChain": "",
            "eligibleForLibrary": False,
            "promotedFrom": None,
            "promotedAt": None,
        },
        "author": author,
        "editors": [author] if author else [],
        "createdAt": _utc_now(),
        "updatedAt": _utc_now(),
    }


def _normalize_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        lines = [ln.strip() for ln in val.replace("\r", "").split("\n")]
        return [ln for ln in lines if ln]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return [str(val).strip()]


def _load_site_pack(site_key: str) -> dict[str, Any]:
    p = site_file(site_key)
    data = _read_json(p, None)
    if not isinstance(data, dict):
        data = {"schema": SCHEMA, "siteKey": site_key, "entries": []}
    data.setdefault("entries", [])
    return data


def _save_site_pack(site_key: str, pack: dict[str, Any]) -> None:
    pack["schema"] = SCHEMA
    pack["siteKey"] = site_key
    pack["updatedAt"] = _utc_now()
    _write_json(site_file(site_key), pack)


def _load_library() -> dict[str, Any]:
    data = _read_json(library_file(), None)
    if not isinstance(data, dict):
        data = {"schema": SCHEMA, "entries": []}
    data.setdefault("entries", [])
    return data


def _save_library(lib: dict[str, Any]) -> None:
    lib["schema"] = SCHEMA
    lib["updatedAt"] = _utc_now()
    _write_json(library_file(), lib)


def promote_criteria() -> list[dict[str, Any]]:
    return deepcopy(PROMOTE_CRITERIA)


def list_for_site(
    site_key: str,
    *,
    export_id: str = "",
    include_library: bool = True,
    equipment_type: str = "",
) -> dict[str, Any]:
    """Site entries + matching approved library tips."""
    pack = _load_site_pack(site_key)
    site_entries = list(pack.get("entries") or [])
    if export_id:
        # also merge packs that used export id as key historically
        alt = _load_site_pack(export_id)
        if alt.get("entries") and alt is not pack:
            ids = {e.get("id") for e in site_entries}
            for e in alt.get("entries") or []:
                if e.get("id") not in ids:
                    site_entries.append(e)

    lib_hits = []
    if include_library:
        lib = _load_library()
        for e in lib.get("entries") or []:
            if equipment_type and (e.get("equipment") or {}).get("type") != equipment_type:
                continue
            lib_hits.append(e)

    if equipment_type:
        site_entries = [
            e for e in site_entries if (e.get("equipment") or {}).get("type") == equipment_type
        ]

    def sort_key(e: dict[str, Any]) -> str:
        return str(e.get("updatedAt") or e.get("createdAt") or "")

    site_entries.sort(key=sort_key, reverse=True)
    lib_hits.sort(key=sort_key, reverse=True)

    return {
        "ok": True,
        "siteKey": site_key,
        "siteEntries": site_entries,
        "libraryEntries": lib_hits,
        "promoteCriteria": PROMOTE_CRITERIA,
        "view3dNote": (
            "3D explode views (CAD-lite) will bind to entry.view3d.modelKey + layout items. "
            "We are not bundling Gilbarco’s commercial CAD; low-poly kits + tech notes close the gap."
        ),
        "dataDir": str(root_dir()),
    }


def get_entry(entry_id: str, site_key: str = "") -> dict[str, Any] | None:
    if site_key:
        for e in _load_site_pack(site_key).get("entries") or []:
            if e.get("id") == entry_id:
                return e
    # scan site packs + library + pending
    for p in (root_dir() / "site").glob("*.json"):
        pack = _read_json(p, {})
        for e in pack.get("entries") or []:
            if e.get("id") == entry_id:
                return e
    for e in _load_library().get("entries") or []:
        if e.get("id") == entry_id:
            return e
    pend = root_dir() / "pending" / f"{entry_id}.json"
    if pend.is_file():
        return _read_json(pend, None)
    return None


def save_entry(payload: dict[str, Any], *, author: str = "tech") -> dict[str, Any]:
    """Create or update a site-scoped knowledge entry (techs edit freely)."""
    site_key = (payload.get("siteKey") or payload.get("site_key") or "").strip()
    if not site_key:
        raise ValueError("siteKey required")

    with _LOCK:
        pack = _load_site_pack(site_key)
        entries = list(pack.get("entries") or [])
        eid = (payload.get("id") or "").strip()
        existing = next((e for e in entries if e.get("id") == eid), None) if eid else None
        if existing:
            entry = deepcopy(existing)
        else:
            entry = empty_entry(
                site_key=site_key,
                export_id=str(payload.get("exportId") or payload.get("export_id") or ""),
                group_key=str(payload.get("groupKey") or payload.get("group_key") or ""),
                author=author or "tech",
            )

        entry["title"] = str(payload.get("title") or entry.get("title") or "Untitled tip")[:160]
        entry["notes"] = str(payload.get("notes") or "")[:4000]
        entry["pros"] = _normalize_list(payload.get("pros"))
        entry["cons"] = _normalize_list(payload.get("cons"))
        entry["compat"] = _normalize_list(payload.get("compat"))
        entry["dayZero"] = _normalize_list(payload.get("dayZero") or payload.get("day_zero"))
        eq_in = payload.get("equipment") if isinstance(payload.get("equipment"), dict) else {}
        eq = entry.setdefault("equipment", {})
        for k in ("type", "manufacturer", "modelClass", "layoutItemId"):
            if eq_in.get(k) is not None:
                eq[k] = str(eq_in.get(k) or "")[:80]
        if "tags" in eq_in:
            eq["tags"] = _normalize_list(eq_in.get("tags"))
        tr_in = payload.get("transfer") if isinstance(payload.get("transfer"), dict) else {}
        tr = entry.setdefault("transfer", {})
        if "cookieCutter" in tr_in:
            tr["cookieCutter"] = bool(tr_in["cookieCutter"])
        if "appliesToChain" in tr_in:
            tr["appliesToChain"] = str(tr_in.get("appliesToChain") or "")[:120]
        if "eligibleForLibrary" in tr_in:
            tr["eligibleForLibrary"] = bool(tr_in["eligibleForLibrary"])
        v3 = payload.get("view3d") if isinstance(payload.get("view3d"), dict) else {}
        if v3:
            entry.setdefault("view3d", {}).update(
                {
                    "modelKey": str(v3.get("modelKey") or entry.get("view3d", {}).get("modelKey") or "")[:80],
                    "explodeSupported": bool(v3.get("explodeSupported", False)),
                }
            )

        entry["exportId"] = str(payload.get("exportId") or payload.get("export_id") or entry.get("exportId") or "")
        entry["groupKey"] = str(payload.get("groupKey") or payload.get("group_key") or entry.get("groupKey") or "")
        entry["siteKey"] = site_key
        entry["scope"] = "site"
        entry["updatedAt"] = _utc_now()
        editors = list(entry.get("editors") or [])
        if author and author not in editors:
            editors.append(author)
        entry["editors"] = editors[-20:]

        if existing:
            entries = [entry if e.get("id") == entry["id"] else e for e in entries]
        else:
            entries.insert(0, entry)
        pack["entries"] = entries
        _save_site_pack(site_key, pack)
        return {"ok": True, "entry": entry, "message": "Knowledge saved (site-specific)"}


def delete_entry(site_key: str, entry_id: str) -> dict[str, Any]:
    with _LOCK:
        pack = _load_site_pack(site_key)
        before = len(pack.get("entries") or [])
        pack["entries"] = [e for e in (pack.get("entries") or []) if e.get("id") != entry_id]
        if len(pack["entries"]) == before:
            raise FileNotFoundError("Entry not found")
        _save_site_pack(site_key, pack)
        return {"ok": True, "message": "Deleted"}


def evaluate_promotion(answers: dict[str, Any] | None) -> dict[str, Any]:
    """Check yes/no answers against promote criteria."""
    answers = answers or {}
    missing = []
    failed = []
    for c in PROMOTE_CRITERIA:
        cid = c["id"]
        raw = answers.get(cid)
        # accept true/"yes"/"y"/1
        yes = raw in (True, "true", "yes", "y", "Y", "1", 1)
        if c.get("requiredYes") and not yes:
            if raw is None or raw == "":
                missing.append(cid)
            else:
                failed.append(cid)
    ok = not missing and not failed
    return {
        "ok": ok,
        "approved": ok,
        "missing": missing,
        "failed": failed,
        "criteria": PROMOTE_CRITERIA,
        "message": (
            "Ready to promote to multi-site library"
            if ok
            else "Answer all criteria with Yes to promote (site tips stay site-only until then)"
        ),
    }


def request_promote(
    site_key: str,
    entry_id: str,
    answers: dict[str, Any],
    *,
    author: str = "tech",
) -> dict[str, Any]:
    """
    If checklist passes, copy site entry into approved library (multi-site).
    Cookie-cutter chains: mark transfer.appliesToChain for faster recognition.
    """
    ev = evaluate_promotion(answers)
    if not ev["approved"]:
        return {**ev, "promoted": False}

    with _LOCK:
        pack = _load_site_pack(site_key)
        src = next((e for e in (pack.get("entries") or []) if e.get("id") == entry_id), None)
        if not src:
            raise FileNotFoundError("Site entry not found")

        lib_entry = deepcopy(src)
        lib_entry["id"] = uuid.uuid4().hex[:12]
        lib_entry["scope"] = "library"
        lib_entry["transfer"] = {
            **(src.get("transfer") or {}),
            "promotedFrom": {"siteKey": site_key, "entryId": entry_id},
            "promotedAt": _utc_now(),
            "approvalAnswers": {k: answers.get(k) for k in (c["id"] for c in PROMOTE_CRITERIA)},
            "approvedBy": author,
            "eligibleForLibrary": True,
        }
        lib_entry["updatedAt"] = _utc_now()
        lib = _load_library()
        lib["entries"] = [lib_entry] + [
            e for e in (lib.get("entries") or []) if e.get("id") != lib_entry["id"]
        ]
        _save_library(lib)

        # mark source as promoted
        for e in pack.get("entries") or []:
            if e.get("id") == entry_id:
                e.setdefault("transfer", {})["eligibleForLibrary"] = True
                e["transfer"]["lastPromotedLibraryId"] = lib_entry["id"]
                e["transfer"]["promotedAt"] = _utc_now()
                e["updatedAt"] = _utc_now()
        _save_site_pack(site_key, pack)

        return {
            "ok": True,
            "promoted": True,
            "libraryEntry": lib_entry,
            "message": "Promoted to multi-site library — other similar sites can see this tip",
        }


def apply_library_to_site(
    site_key: str,
    library_entry_id: str,
    *,
    author: str = "tech",
    export_id: str = "",
) -> dict[str, Any]:
    """Clone an approved library tip onto this site so techs can customize further."""
    lib = _load_library()
    src = next((e for e in (lib.get("entries") or []) if e.get("id") == library_entry_id), None)
    if not src:
        raise FileNotFoundError("Library entry not found")
    clone = deepcopy(src)
    clone["id"] = uuid.uuid4().hex[:12]
    clone["scope"] = "site"
    clone["siteKey"] = site_key
    clone["exportId"] = export_id or clone.get("exportId") or ""
    clone["transfer"] = {
        **(clone.get("transfer") or {}),
        "clonedFromLibrary": library_entry_id,
        "clonedAt": _utc_now(),
    }
    clone["author"] = author
    clone["createdAt"] = _utc_now()
    clone["updatedAt"] = _utc_now()
    with _LOCK:
        pack = _load_site_pack(site_key)
        pack.setdefault("entries", []).insert(0, clone)
        _save_site_pack(site_key, pack)
    return {"ok": True, "entry": clone, "message": "Library tip copied to this site (editable)"}


def seed_from_layout_item(
    site_key: str,
    item: dict[str, Any],
    *,
    export_id: str = "",
    author: str = "tech",
) -> dict[str, Any]:
    """Quick stub from aerial layout selection."""
    meta = item.get("meta") or {}
    etype = str(item.get("type") or "other")
    mfr = str(meta.get("dispenserBrand") or meta.get("dcrBrand") or meta.get("brand") or "")
    title = str(item.get("label") or f"{etype} tip")
    payload = {
        "siteKey": site_key,
        "exportId": export_id,
        "title": title,
        "equipment": {
            "type": etype if etype != "card_reader" else "crind",
            "manufacturer": mfr,
            "modelClass": "",
            "layoutItemId": str(item.get("id") or ""),
            "tags": [],
        },
        "pros": [],
        "cons": [],
        "compat": [],
        "dayZero": ["(add day-zero learnings here)"],
        "notes": "Created from aerial layout selection — edit freely.",
        "transfer": {"cookieCutter": False, "eligibleForLibrary": False},
    }
    return save_entry(payload, author=author)
