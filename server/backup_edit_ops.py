"""
Local Commander SMS backup item lookup + staged edits with safe copies.

Scope:
  - Look up PLU/item fields from a site's export folder (PLUs.xml, etc.)
  - Stage field edits against the LOCAL backup only (never live Commander)
  - Before applying: safe-copy originals under %LOCALAPPDATA%\\FAFO\\backup-safe
  - Keep safe copies for SAFE_RETENTION_DAYS (default 15), then prune
  - Review queue with before/after values for sequential verification

Does NOT push config back to the controller — that remains Import-Export Utility.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import verifone_ops as vf

SAFE_RETENTION_DAYS = 15
_PLU_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()
_PLU_CACHE_TTL_SEC = 10 * 60

# Fields techs may stage-edit on a PLU row (local backup only)
EDITABLE_PLU_FIELDS = {
    "description",
    "price",
    "department",
    "pcode",
    "SellUnit",
    "maxQtyPerTrans",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fafo_dir() -> Path:
    import os

    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    d = base / "FAFO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_root() -> Path:
    d = _fafo_dir() / "backup-safe"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _site_safe_dir(site_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", site_id)[:64] or "site"
    d = _safe_root() / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pending_path(site_id: str) -> Path:
    return _site_safe_dir(site_id) / "pending_changes.json"


def _load_pending(site_id: str) -> dict[str, Any]:
    p = _pending_path(site_id)
    if not p.is_file():
        return {"schema": "FAFO.BackupEdits/1", "siteId": site_id, "changes": [], "updatedAt": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"schema": "FAFO.BackupEdits/1", "siteId": site_id, "changes": [], "updatedAt": None}
    data.setdefault("changes", [])
    return data


def _save_pending(site_id: str, data: dict[str, Any]) -> None:
    data["updatedAt"] = _utc_now()
    data["siteId"] = site_id
    p = _pending_path(site_id)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1] if ":" in tag else tag


def _norm_upc(val: str | None) -> str:
    s = re.sub(r"\D", "", str(val or ""))
    return s.lstrip("0") or "0"


def _export_dir(site_id: str) -> Path:
    return vf._safe_export_path(site_id)


def _plu_file(export_dir: Path) -> Path | None:
    for name in ("PLUs.xml", "plus.xml", "Plus.xml"):
        p = export_dir / name
        if p.is_file():
            return p
    # case-insensitive scan
    try:
        for f in export_dir.iterdir():
            if f.is_file() and f.name.lower() == "plus.xml":
                return f
    except OSError:
        pass
    return None


def _plu_element_to_dict(el: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for child in el:
        ln = _local(child.tag)
        if list(child):
            # shallow nested: fees/fee, taxRates, etc.
            texts = []
            for g in child.iter():
                if g is child:
                    continue
                if (g.text or "").strip() and not list(g):
                    texts.append((_local(g.tag), g.text.strip(), dict(g.attrib)))
            if texts:
                out[ln] = texts
            else:
                out[ln] = (child.text or "").strip()
        else:
            txt = (child.text or "").strip()
            attrs = {_local(k): v for k, v in child.attrib.items()}
            if attrs and txt:
                out[ln] = {"value": txt, **attrs}
            elif attrs:
                out[ln] = attrs
            else:
                out[ln] = txt
    # Flatten common fields for UI
    upc = str(out.get("upc") or out.get("UPC") or "")
    if isinstance(upc, dict):
        upc = str(upc.get("value") or "")
    desc = out.get("description") or out.get("desc") or ""
    if isinstance(desc, dict):
        desc = desc.get("value") or ""
    price = out.get("price") or out.get("Price") or ""
    if isinstance(price, dict):
        price = price.get("value") or ""
    dept = out.get("department") or out.get("dept") or ""
    if isinstance(dept, dict):
        dept = dept.get("value") or dept.get("number") or ""
    pcode = out.get("pcode") or ""
    if isinstance(pcode, dict):
        pcode = pcode.get("value") or ""
    sell = out.get("SellUnit") or out.get("sellUnit") or ""
    if isinstance(sell, dict):
        sell = sell.get("value") or ""
    return {
        "upc": str(upc),
        "upcNormalized": _norm_upc(str(upc)),
        "upcModifier": str(out.get("upcModifier") or out.get("modifier") or "000"),
        "description": str(desc),
        "price": str(price),
        "department": str(dept),
        "pcode": str(pcode),
        "SellUnit": str(sell),
        "maxQtyPerTrans": str(
            (out.get("maxQtyPerTrans") or {}).get("value")
            if isinstance(out.get("maxQtyPerTrans"), dict)
            else (out.get("maxQtyPerTrans") or "")
        ),
        "raw": out,
    }


def _build_plu_index(site_id: str, *, force: bool = False) -> dict[str, Any]:
    with _CACHE_LOCK:
        cached = _PLU_CACHE.get(site_id)
        if cached and not force and (time.time() - cached.get("builtAt", 0)) < _PLU_CACHE_TTL_SEC:
            return cached

    export_dir = _export_dir(site_id)
    plu_path = _plu_file(export_dir)
    by_upc: dict[str, dict[str, Any]] = {}
    by_desc: dict[str, list[str]] = {}
    count = 0
    if plu_path and plu_path.is_file():
        # iterparse for large PLUs.xml
        try:
            for _event, el in ET.iterparse(plu_path, events=("end",)):
                if _local(el.tag).lower() != "plu":
                    continue
                rec = _plu_element_to_dict(el)
                key = rec["upcNormalized"]
                if key and key != "0":
                    by_upc[key] = rec
                    # also store full padded form
                    if rec.get("upc"):
                        by_upc[re.sub(r"\D", "", rec["upc"])] = rec
                dkey = (rec.get("description") or "").strip().lower()
                if dkey:
                    by_desc.setdefault(dkey, []).append(key)
                count += 1
                el.clear()
        except ET.ParseError:
            # fallback full parse
            try:
                root = ET.fromstring(plu_path.read_text(encoding="utf-8", errors="replace"))
                for el in root.iter():
                    if _local(el.tag).lower() != "plu":
                        continue
                    rec = _plu_element_to_dict(el)
                    key = rec["upcNormalized"]
                    if key and key != "0":
                        by_upc[key] = rec
                    count += 1
            except ET.ParseError:
                pass

    payload = {
        "siteId": site_id,
        "exportPath": str(export_dir),
        "pluFile": str(plu_path) if plu_path else None,
        "count": count,
        "byUpc": by_upc,
        "byDesc": by_desc,
        "builtAt": time.time(),
    }
    with _CACHE_LOCK:
        _PLU_CACHE[site_id] = payload
    return payload


def invalidate_plu_cache(site_id: str) -> None:
    with _CACHE_LOCK:
        _PLU_CACHE.pop(site_id, None)


def lookup_item(
    site_id: str,
    *,
    barcode: str | None = None,
    description: str | None = None,
    department: str | None = None,
    product: str | None = None,
) -> dict[str, Any]:
    """Resolve a journal line item against the site SMS backup PLUs.xml."""
    idx = _build_plu_index(site_id)
    matches: list[dict[str, Any]] = []
    reasons: list[str] = []

    if barcode:
        n = _norm_upc(barcode)
        full = re.sub(r"\D", "", barcode)
        rec = idx["byUpc"].get(full) or idx["byUpc"].get(n)
        # Short numeric tokens (e.g. "55") are ambiguous — only accept if full padded UPC matched
        # or the barcode was reasonably long (8+ digits).
        if rec and (len(full) >= 8 or full == re.sub(r"\D", "", rec.get("upc") or "")):
            matches.append({**rec, "matchReason": "upc", "matchScore": 100})
        elif rec and len(full) < 8:
            reasons.append(f"Short barcode {barcode!r} is ambiguous in PLU file — also trying description")
            # keep as weak candidate
            matches.append({**rec, "matchReason": "upc-weak", "matchScore": 20})
        else:
            reasons.append(f"No PLU for UPC/barcode {barcode!r}")

    if description:
        dkey = description.strip().lower()
        # exact
        keys = list(idx["byDesc"].get(dkey) or [])
        exact = bool(keys)
        if not keys and len(dkey) >= 3:
            # partial — prefer longer overlapping descriptions
            # Skip empty/very-short catalog descriptions ("" in haystack is always true in Python)
            partial: list[tuple[int, str]] = []
            for desc, ks in idx["byDesc"].items():
                if not desc or len(desc) < 3:
                    continue
                if dkey in desc or (len(desc) >= 4 and desc in dkey):
                    # score by overlap quality: exact substring length
                    partial.append((min(len(desc), len(dkey)), ks[0] if ks else ""))
            partial.sort(reverse=True)
            keys = [k for _n, k in partial[:20] if k]
        seen: set[str] = set()
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            rec = idx["byUpc"].get(k)
            if rec:
                score = 90 if exact else 50
                matches.append({**rec, "matchReason": "description" if exact else "description-partial", "matchScore": score})
        if not any(m.get("matchReason", "").startswith("description") for m in matches):
            reasons.append(f"No PLU description match for {description!r}")

    if department and matches:
        for m in matches:
            if str(m.get("department")) == str(department):
                m["matchScore"] = int(m.get("matchScore") or 0) + 15

    # Deduplicate by upcNormalized, keep highest score
    best: dict[str, dict[str, Any]] = {}
    for m in matches:
        key = m.get("upcNormalized") or m.get("upc") or ""
        prev = best.get(key)
        if not prev or int(m.get("matchScore") or 0) > int(prev.get("matchScore") or 0):
            best[key] = m
    matches = sorted(best.values(), key=lambda x: -int(x.get("matchScore") or 0))
    primary = matches[0] if matches else None
    return {
        "ok": True,
        "siteId": site_id,
        "query": {
            "barcode": barcode,
            "description": description,
            "department": department,
            "product": product,
        },
        "pluFile": idx.get("pluFile"),
        "pluCount": idx.get("count"),
        "exportPath": idx.get("exportPath"),
        "match": primary,
        "matches": matches[:15],
        "matchCount": len(matches),
        "reasons": reasons,
        "editableFields": sorted(EDITABLE_PLU_FIELDS),
        "note": (
            "Edits apply to the LOCAL SMS backup only. "
            "Pushing to Commander still uses Import-Export Utility after you apply & review."
        ),
    }


def stage_plu_edit(
    site_id: str,
    *,
    upc: str,
    field: str,
    new_value: str,
    old_value: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    field = (field or "").strip()
    if field not in EDITABLE_PLU_FIELDS:
        raise ValueError(f"Field not editable: {field}. Allowed: {sorted(EDITABLE_PLU_FIELDS)}")
    upc = str(upc or "").strip()
    if not upc:
        raise ValueError("upc required")

    idx = _build_plu_index(site_id)
    rec = idx["byUpc"].get(_norm_upc(upc)) or idx["byUpc"].get(re.sub(r"\D", "", upc))
    if not rec:
        raise FileNotFoundError(f"PLU not found in backup for UPC {upc}")

    before = str(old_value if old_value is not None else rec.get(field) or "")
    after = str(new_value if new_value is not None else "")
    if before == after:
        raise ValueError("No change — before and after are the same")

    data = _load_pending(site_id)
    # replace existing pending edit for same upc+field
    changes = [
        c
        for c in data["changes"]
        if not (
            c.get("status") in {"pending", "verified"}
            and c.get("upcNormalized") == rec["upcNormalized"]
            and c.get("field") == field
        )
    ]
    change = {
        "id": uuid.uuid4().hex[:12],
        "type": "plu_field",
        "status": "pending",  # pending | verified | rejected | applied
        "file": Path(idx["pluFile"]).name if idx.get("pluFile") else "PLUs.xml",
        "filePath": idx.get("pluFile"),
        "upc": rec.get("upc"),
        "upcNormalized": rec["upcNormalized"],
        "description": rec.get("description"),
        "field": field,
        "before": before,
        "after": after,
        "source": source or "journal-line",
        "createdAt": _utc_now(),
        "verifiedAt": None,
        "appliedAt": None,
    }
    changes.append(change)
    data["changes"] = changes
    _save_pending(site_id, data)
    return {"ok": True, "change": change, "pendingCount": _pending_count(data)}


def _pending_count(data: dict[str, Any]) -> int:
    return sum(1 for c in data.get("changes") or [] if c.get("status") in {"pending", "verified"})


def list_changes(site_id: str, *, include_applied: bool = True) -> dict[str, Any]:
    data = _load_pending(site_id)
    changes = data.get("changes") or []
    if not include_applied:
        changes = [c for c in changes if c.get("status") != "applied"]
    # order: pending first, then verified, then others
    order = {"pending": 0, "verified": 1, "rejected": 2, "applied": 3}
    changes = sorted(changes, key=lambda c: (order.get(c.get("status") or "", 9), c.get("createdAt") or ""))
    pending = [c for c in changes if c.get("status") == "pending"]
    verified = [c for c in changes if c.get("status") == "verified"]
    return {
        "ok": True,
        "siteId": site_id,
        "changes": changes,
        "pendingCount": len(pending),
        "verifiedCount": len(verified),
        "nextToReview": pending[0] if pending else None,
        "readyToApply": len(pending) == 0 and len(verified) > 0,
        "retentionDays": SAFE_RETENTION_DAYS,
        "safeRoot": str(_site_safe_dir(site_id)),
    }


def set_change_status(site_id: str, change_id: str, status: str) -> dict[str, Any]:
    status = (status or "").strip().lower()
    if status not in {"pending", "verified", "rejected"}:
        raise ValueError("status must be pending|verified|rejected")
    data = _load_pending(site_id)
    found = None
    for c in data["changes"]:
        if c.get("id") == change_id:
            if c.get("status") == "applied":
                raise ValueError("Change already applied")
            c["status"] = status
            c["verifiedAt"] = _utc_now() if status == "verified" else c.get("verifiedAt")
            if status == "rejected":
                c["verifiedAt"] = _utc_now()
            found = c
            break
    if not found:
        raise FileNotFoundError(f"Change not found: {change_id}")
    _save_pending(site_id, data)
    nxt = next((c for c in data["changes"] if c.get("status") == "pending"), None)
    return {"ok": True, "change": found, "nextToReview": nxt, **list_changes(site_id)}


def verify_all_pending(site_id: str) -> dict[str, Any]:
    data = _load_pending(site_id)
    n = 0
    for c in data["changes"]:
        if c.get("status") == "pending":
            c["status"] = "verified"
            c["verifiedAt"] = _utc_now()
            n += 1
    _save_pending(site_id, data)
    return {"ok": True, "verified": n, **list_changes(site_id)}


def _safe_copy_file(site_id: str, src: Path, reason: str) -> dict[str, Any]:
    if not src.is_file():
        raise FileNotFoundError(str(src))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = _site_safe_dir(site_id) / "copies"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stamp}_{src.name}"
    # avoid clobber
    if dest.exists():
        dest = dest_dir / f"{stamp}_{uuid.uuid4().hex[:6]}_{src.name}"
    shutil.copy2(src, dest)
    meta = {
        "id": hashlib.sha1(str(dest).encode()).hexdigest()[:12],
        "originalPath": str(src),
        "originalName": src.name,
        "safePath": str(dest),
        "bytes": dest.stat().st_size,
        "createdAt": _utc_now(),
        "reason": reason,
        "siteId": site_id,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(days=SAFE_RETENTION_DAYS)).isoformat(),
    }
    meta_path = dest.with_suffix(dest.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def list_safe_copies(site_id: str) -> dict[str, Any]:
    prune_safe_copies(site_id)
    copies_dir = _site_safe_dir(site_id) / "copies"
    rows: list[dict[str, Any]] = []
    if copies_dir.is_dir():
        for meta_file in sorted(copies_dir.glob("*.meta.json"), reverse=True):
            try:
                rows.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {
        "ok": True,
        "siteId": site_id,
        "copies": rows,
        "count": len(rows),
        "retentionDays": SAFE_RETENTION_DAYS,
        "safeRoot": str(_site_safe_dir(site_id)),
    }


def prune_safe_copies(site_id: str | None = None) -> dict[str, Any]:
    """Remove safe copies older than SAFE_RETENTION_DAYS."""
    roots = [_site_safe_dir(site_id)] if site_id else [p for p in _safe_root().iterdir() if p.is_dir()]
    removed = 0
    kept = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=SAFE_RETENTION_DAYS)
    for root in roots:
        copies = root / "copies"
        if not copies.is_dir():
            continue
        for meta_file in list(copies.glob("*.meta.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                created = meta.get("createdAt") or ""
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                safe_path = Path(meta.get("safePath") or "")
                if dt < cutoff:
                    if safe_path.is_file():
                        safe_path.unlink(missing_ok=True)
                    meta_file.unlink(missing_ok=True)
                    removed += 1
                else:
                    kept += 1
            except Exception:
                continue
    return {"ok": True, "removed": removed, "kept": kept, "retentionDays": SAFE_RETENTION_DAYS}


def restore_safe_copy(site_id: str, copy_id: str) -> dict[str, Any]:
    """Restore a safe copy over the live backup file (with a new safe copy of current first)."""
    info = list_safe_copies(site_id)
    meta = next((c for c in info["copies"] if c.get("id") == copy_id), None)
    if not meta:
        raise FileNotFoundError(f"Safe copy not found: {copy_id}")
    src = Path(meta["safePath"])
    dest = Path(meta["originalPath"])
    if not src.is_file():
        raise FileNotFoundError(f"Safe file missing: {src}")
    # protect current
    pre = None
    if dest.is_file():
        pre = _safe_copy_file(site_id, dest, reason=f"pre-restore:{copy_id}")
    shutil.copy2(src, dest)
    invalidate_plu_cache(site_id)
    return {
        "ok": True,
        "restored": meta,
        "preRestoreCopy": pre,
        "message": f"Restored {dest.name} from safe copy {copy_id}",
    }


def _update_plu_field_in_xml(xml_text: str, upc: str, field: str, new_value: str) -> tuple[str, str]:
    """Return (new_xml, old_value). Preserves namespaces as much as ElementTree allows."""
    # Register common sapphire namespaces so serialization keeps prefixes when possible
    ns_map = {
        "domain": "urn:vfi-sapphire:np.domain.2001-07-01",
        "vs": "urn:vfi-sapphire:vs.2001-10-01",
        "base": "urn:vfi-sapphire:base.2001-10-01",
    }
    for prefix, uri in ns_map.items():
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass

    root = ET.fromstring(xml_text)
    target_n = _norm_upc(upc)
    old_value = ""
    found = False
    for el in root.iter():
        if _local(el.tag).lower() != "plu":
            continue
        rec = _plu_element_to_dict(el)
        if rec["upcNormalized"] != target_n and re.sub(r"\D", "", rec.get("upc") or "") != re.sub(
            r"\D", "", upc
        ):
            continue
        # find field child
        for child in list(el):
            if _local(child.tag) == field or _local(child.tag).lower() == field.lower():
                old_value = (child.text or "").strip()
                child.text = str(new_value)
                found = True
                break
        if not found:
            # create field
            # use same namespace as upc child if present
            ns = ""
            for child in el:
                if "}" in child.tag:
                    ns = child.tag.split("}")[0] + "}"
                    break
            new_el = ET.SubElement(el, f"{ns}{field}" if ns else field)
            new_el.text = str(new_value)
            old_value = ""
            found = True
        break
    if not found:
        raise FileNotFoundError(f"PLU UPC {upc} not found in XML")
    # Serialize
    try:
        ET.indent(root, space="  ")
    except Exception:
        pass
    out = ET.tostring(root, encoding="unicode")
    if not out.lstrip().startswith("<?xml"):
        out = '<?xml version="1.0" encoding="UTF-8"?>\n' + out
    return out, old_value


def apply_verified_changes(site_id: str, *, only_verified: bool = True) -> dict[str, Any]:
    """
    Apply verified (or all pending if only_verified=False) staged edits to LOCAL backup files.
    Creates a safe copy of each touched file before first write in this batch.
    """
    prune_safe_copies(site_id)
    data = _load_pending(site_id)
    if only_verified:
        targets = [c for c in data["changes"] if c.get("status") == "verified"]
    else:
        targets = [c for c in data["changes"] if c.get("status") in {"pending", "verified"}]

    if not targets:
        return {"ok": False, "message": "No verified changes to apply", "applied": []}

    export_dir = _export_dir(site_id)
    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    safe_copies: dict[str, dict[str, Any]] = {}

    # Group by file
    by_file: dict[str, list[dict[str, Any]]] = {}
    for c in targets:
        fname = c.get("file") or "PLUs.xml"
        by_file.setdefault(fname, []).append(c)

    for fname, group in by_file.items():
        path = (export_dir / Path(fname).name).resolve()
        try:
            path.relative_to(export_dir.resolve())
        except ValueError:
            errors.append(f"Refusing path outside export: {fname}")
            continue
        if not path.is_file():
            errors.append(f"Missing file: {fname}")
            continue
        # safe copy once per file
        try:
            safe_copies[fname] = _safe_copy_file(site_id, path, reason="pre-apply-batch")
        except OSError as e:
            errors.append(f"Safe copy failed for {fname}: {e}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for c in group:
            try:
                text, old = _update_plu_field_in_xml(text, c.get("upc") or "", c.get("field") or "", c.get("after") or "")
                c["status"] = "applied"
                c["appliedAt"] = _utc_now()
                c["appliedBefore"] = old
                c["safeCopyId"] = safe_copies[fname].get("id")
                applied.append(c)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{c.get('id')} {c.get('upc')} {c.get('field')}: {e}")
        path.write_text(text, encoding="utf-8")

    _save_pending(site_id, data)
    invalidate_plu_cache(site_id)
    return {
        "ok": len(applied) > 0 and not errors,
        "applied": applied,
        "appliedCount": len(applied),
        "errors": errors,
        "safeCopies": list(safe_copies.values()),
        "message": (
            f"Applied {len(applied)} change(s) to local backup. "
            f"Safe copies kept {SAFE_RETENTION_DAYS} days under {_site_safe_dir(site_id)}. "
            "Use Import-Export Utility to push SMS config back to Commander when ready."
        ),
        **list_changes(site_id),
    }
