"""
Local Commander SMS backup item lookup + staged edits with safe copies.

Scope:
  - Look up / browse PLU fields from a site's export folder (PLUs.xml, etc.)
  - Stage single or bulk field edits against the LOCAL backup only (never live Commander)
  - Bulk ops: absolute set, price % / $ delta, mass EBT (foodStamp) by selection or department filter
  - Before first apply: lock a protected "original" snapshot until the user signs off
  - On sign-off: archive original into per-site finalized history (keep last 3)
  - Safe-copy each pre-apply file under %LOCALAPPDATA%\\FAFO\\backup-safe
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
FINALIZED_KEEP = 3  # last N signed-off original snapshots per site
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
    "foodStamp",  # EBT / Food Stamps eligible (Commander "Food Stamp" on PLU)
    "active",
    "taxable",
    "discountable",
    "returnable",
}

# XML child / attribute name aliases → canonical field
_FIELD_ALIASES: dict[str, str] = {
    "description": "description",
    "desc": "description",
    "price": "price",
    "Price": "price",
    "department": "department",
    "dept": "department",
    "DepartmentId": "department",
    "departmentId": "department",
    "pcode": "pcode",
    "productCode": "pcode",
    "ProductCode": "pcode",
    "SellUnit": "SellUnit",
    "sellUnit": "SellUnit",
    "maxQtyPerTrans": "maxQtyPerTrans",
    "foodStamp": "foodStamp",
    "FoodStamp": "foodStamp",
    "foodStamps": "foodStamp",
    "FoodStamps": "foodStamp",
    "allowFoodStamps": "foodStamp",
    "AllowFoodStamps": "foodStamp",
    "ebt": "foodStamp",
    "ebtAllowed": "foodStamp",
    "fsEligible": "foodStamp",
    "active": "active",
    "Active": "active",
    "taxable": "taxable",
    "Taxable": "taxable",
    "discountable": "discountable",
    "Discountable": "discountable",
    "returnable": "returnable",
    "Returnable": "returnable",
}

# Preferred XML tag/attr name when writing each canonical field
_FIELD_WRITE_NAME: dict[str, str] = {
    "description": "description",
    "price": "price",
    "department": "department",
    "pcode": "pcode",
    "SellUnit": "SellUnit",
    "maxQtyPerTrans": "maxQtyPerTrans",
    "foodStamp": "foodStamp",
    "active": "active",
    "taxable": "taxable",
    "discountable": "discountable",
    "returnable": "returnable",
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


def _scalar(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("value") or val.get("number") or "")
    return str(val).strip()


def _yn_normalize(val: str) -> str:
    """Normalize Y/N / true/false / 1/0 to Y or N for foodStamp-style flags."""
    s = str(val or "").strip().lower()
    if s in {"y", "yes", "true", "1", "on", "enabled"}:
        return "Y"
    if s in {"n", "no", "false", "0", "off", "disabled", ""}:
        return "N" if s != "" else ""
    return str(val).strip()


def _plu_element_to_dict(el: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {}
    # Attribute-style exports (demo / some SMS packs use <Item UPC=...>)
    for ak, av in el.attrib.items():
        ln = _local(ak)
        out[ln] = av
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

    def pick(*keys: str) -> str:
        for k in keys:
            if k in out and out[k] not in (None, ""):
                return _scalar(out[k])
        return ""

    upc = pick("upc", "UPC", "plu", "PLU")
    desc = pick("description", "desc", "Description")
    price = pick("price", "Price")
    dept = pick("department", "dept", "DepartmentId", "departmentId")
    pcode = pick("pcode", "productCode", "ProductCode")
    sell = pick("SellUnit", "sellUnit")
    max_qty = pick("maxQtyPerTrans")
    food = pick(
        "foodStamp",
        "FoodStamp",
        "foodStamps",
        "FoodStamps",
        "allowFoodStamps",
        "AllowFoodStamps",
        "ebt",
        "ebtAllowed",
        "fsEligible",
    )
    active = pick("active", "Active")
    taxable = pick("taxable", "Taxable")
    discountable = pick("discountable", "Discountable")
    returnable = pick("returnable", "Returnable")
    return {
        "upc": str(upc),
        "upcNormalized": _norm_upc(str(upc)),
        "upcModifier": pick("upcModifier", "modifier") or "000",
        "description": str(desc),
        "price": str(price),
        "department": str(dept),
        "pcode": str(pcode),
        "SellUnit": str(sell),
        "maxQtyPerTrans": str(max_qty),
        "foodStamp": _yn_normalize(food) if food else "",
        "active": str(active),
        "taxable": str(taxable),
        "discountable": str(discountable),
        "returnable": str(returnable),
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
    items: list[dict[str, Any]] = []
    departments: set[str] = set()
    count = 0

    def _ingest(el: ET.Element) -> None:
        nonlocal count
        tag = _local(el.tag).lower()
        if tag not in {"plu", "item"}:
            return
        rec = _plu_element_to_dict(el)
        key = rec["upcNormalized"]
        # Prefer UPC; fall back to description-only key so fuel/open items still list
        if not key or key == "0":
            key = "d:" + hashlib.sha1(
                (rec.get("description") or str(count)).encode("utf-8", errors="replace")
            ).hexdigest()[:10]
            rec["upcNormalized"] = key
        slim = {k: rec[k] for k in (
            "upc", "upcNormalized", "upcModifier", "description", "price",
            "department", "pcode", "SellUnit", "maxQtyPerTrans", "foodStamp",
            "active", "taxable", "discountable", "returnable",
        )}
        by_upc[key] = slim
        if rec.get("upc"):
            digits = re.sub(r"\D", "", rec["upc"])
            if digits:
                by_upc[digits] = slim
        dkey = (rec.get("description") or "").strip().lower()
        if dkey:
            by_desc.setdefault(dkey, []).append(key)
        if rec.get("department"):
            departments.add(str(rec["department"]))
        items.append(slim)
        count += 1

    if plu_path and plu_path.is_file():
        # iterparse for large PLUs.xml
        try:
            for _event, el in ET.iterparse(plu_path, events=("end",)):
                if _local(el.tag).lower() in {"plu", "item"}:
                    _ingest(el)
                el.clear()
        except ET.ParseError:
            # fallback full parse
            try:
                root = ET.fromstring(plu_path.read_text(encoding="utf-8", errors="replace"))
                for el in root.iter():
                    if _local(el.tag).lower() in {"plu", "item"}:
                        _ingest(el)
            except ET.ParseError:
                pass

    # Stable list ordered by description then upc
    items.sort(key=lambda r: (
        (r.get("description") or "").lower(),
        r.get("upc") or "",
    ))

    payload = {
        "siteId": site_id,
        "exportPath": str(export_dir),
        "pluFile": str(plu_path) if plu_path else None,
        "count": count,
        "byUpc": by_upc,
        "byDesc": by_desc,
        "items": items,
        "departments": sorted(departments, key=lambda x: (len(x), x)),
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


def _resolve_plu(idx: dict[str, Any], upc: str) -> dict[str, Any] | None:
    if not upc:
        return None
    full = re.sub(r"\D", "", str(upc))
    n = _norm_upc(upc)
    return idx["byUpc"].get(full) or idx["byUpc"].get(n) or idx["byUpc"].get(str(upc))


def _format_price(val: float) -> str:
    # Keep cents; drop trailing zeros only for whole dollars still as 2 decimals
    return f"{val:.2f}"


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
    # accept aliases
    field = _FIELD_ALIASES.get(field, field)
    if field not in EDITABLE_PLU_FIELDS:
        raise ValueError(f"Field not editable: {field}. Allowed: {sorted(EDITABLE_PLU_FIELDS)}")
    upc = str(upc or "").strip()
    if not upc:
        raise ValueError("upc required")

    idx = _build_plu_index(site_id)
    rec = _resolve_plu(idx, upc)
    if not rec:
        raise FileNotFoundError(f"PLU not found in backup for UPC {upc}")

    before = str(old_value if old_value is not None else rec.get(field) or "")
    after = str(new_value if new_value is not None else "")
    if field == "foodStamp":
        after = _yn_normalize(after) or after
        before = _yn_normalize(before) or before
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
        "upc": rec.get("upc") or upc,
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


def list_plus(
    site_id: str,
    *,
    q: str | None = None,
    department: str | None = None,
    pcode: str | None = None,
    food_stamp: str | None = None,
    upc: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Browse/filter PLUs in the local SMS backup (for the bulk editor)."""
    idx = _build_plu_index(site_id)
    items: list[dict[str, Any]] = list(idx.get("items") or [])
    qn = (q or "").strip().lower()
    dept = (department or "").strip()
    pc = (pcode or "").strip().lower()
    fs = _yn_normalize(food_stamp) if food_stamp not in (None, "") else ""
    upc_q = re.sub(r"\D", "", upc or "")

    def match(rec: dict[str, Any]) -> bool:
        if dept and str(rec.get("department") or "") != dept:
            return False
        if pc and pc not in str(rec.get("pcode") or "").lower():
            return False
        if fs:
            cur_fs = _yn_normalize(str(rec.get("foodStamp") or "")) or "N"
            if cur_fs != fs:
                return False
        if upc_q:
            digits = re.sub(r"\D", "", str(rec.get("upc") or ""))
            if upc_q not in digits and upc_q != rec.get("upcNormalized"):
                return False
        if qn:
            hay = " ".join(
                [
                    str(rec.get("description") or ""),
                    str(rec.get("upc") or ""),
                    str(rec.get("pcode") or ""),
                    str(rec.get("department") or ""),
                ]
            ).lower()
            if qn not in hay:
                return False
        return True

    filtered = [r for r in items if match(r)]
    try:
        limit = max(1, min(int(limit), 1000))
    except (TypeError, ValueError):
        limit = 200
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0
    page = filtered[offset : offset + limit]
    return {
        "ok": True,
        "siteId": site_id,
        "pluFile": idx.get("pluFile"),
        "exportPath": idx.get("exportPath"),
        "totalInFile": idx.get("count") or 0,
        "matchCount": len(filtered),
        "offset": offset,
        "limit": limit,
        "items": page,
        "departments": idx.get("departments") or [],
        "editableFields": sorted(EDITABLE_PLU_FIELDS),
        "original": get_original_status(site_id),
        "note": (
            "Edits apply to the LOCAL SMS backup only. "
            "Pushing to Commander still uses Import-Export Utility after you apply & review."
        ),
    }


def stage_bulk(
    site_id: str,
    *,
    upcs: list[str] | None = None,
    exclude_upcs: list[str] | None = None,
    operation: str = "set",
    field: str = "price",
    value: str | None = None,
    department: str | None = None,
    q: str | None = None,
    source: str | None = None,
    select_all_matches: bool = False,
) -> dict[str, Any]:
    """
    Stage the same partial update across many PLUs.

    operation:
      - set            → field = value (absolute)
      - price_percent  → price *= (1 + value/100)   e.g. value=10 → +10%
      - price_amount   → price += value             e.g. value=1.00 → +$1
    """
    op = (operation or "set").strip().lower()
    if op not in {"set", "price_percent", "price_amount"}:
        raise ValueError("operation must be set|price_percent|price_amount")
    field = _FIELD_ALIASES.get((field or "").strip(), (field or "").strip())
    if op in {"price_percent", "price_amount"}:
        field = "price"
    if field not in EDITABLE_PLU_FIELDS:
        raise ValueError(f"Field not editable: {field}")

    idx = _build_plu_index(site_id)
    exclude = {_norm_upc(u) for u in (exclude_upcs or []) if u}
    exclude |= {re.sub(r"\D", "", str(u)) for u in (exclude_upcs or []) if u}

    targets: list[dict[str, Any]] = []
    if select_all_matches or (not upcs and (department or q)):
        browse = list_plus(site_id, q=q, department=department, limit=10000, offset=0)
        targets = list(browse.get("items") or [])
    else:
        for u in upcs or []:
            rec = _resolve_plu(idx, str(u))
            if rec:
                targets.append(rec)

    # de-dupe + exclude
    seen: set[str] = set()
    final: list[dict[str, Any]] = []
    for rec in targets:
        key = rec.get("upcNormalized") or ""
        if not key or key in seen:
            continue
        if key in exclude or re.sub(r"\D", "", str(rec.get("upc") or "")) in exclude:
            continue
        seen.add(key)
        final.append(rec)

    if not final:
        raise ValueError("No PLUs selected to stage (after excludes)")

    staged: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[str] = []

    for rec in final:
        try:
            before = str(rec.get(field) or "")
            if op == "set":
                after = str(value if value is not None else "")
                if field == "foodStamp":
                    after = _yn_normalize(after) or after
            elif op == "price_percent":
                try:
                    pct = float(value)
                    base = float(before or 0)
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Bad price/percent for {rec.get('upc')}: {before!r} / {value!r}") from e
                after = _format_price(base * (1.0 + pct / 100.0))
            else:  # price_amount
                try:
                    delta = float(value)
                    base = float(before or 0)
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Bad price/amount for {rec.get('upc')}: {before!r} / {value!r}") from e
                after = _format_price(base + delta)

            if before == after:
                skipped.append({"upc": rec.get("upc"), "reason": "unchanged"})
                continue
            res = stage_plu_edit(
                site_id,
                upc=str(rec.get("upc") or rec.get("upcNormalized")),
                field=field,
                new_value=after,
                old_value=before,
                source=source or f"bulk:{op}",
            )
            staged.append(res["change"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{rec.get('upc')}: {e}")

    return {
        "ok": len(staged) > 0,
        "stagedCount": len(staged),
        "skippedCount": len(skipped),
        "errorCount": len(errors),
        "staged": staged[:50],  # sample
        "skipped": skipped[:30],
        "errors": errors[:30],
        "operation": op,
        "field": field,
        "value": value,
        "pendingCount": _pending_count(_load_pending(site_id)),
        "message": (
            f"Staged {len(staged)} change(s)"
            + (f", skipped {len(skipped)}" if skipped else "")
            + (f", {len(errors)} error(s)" if errors else "")
            + ". Review then Apply to write local backup."
        ),
    }


# --- Protected original + finalized history (last N) ---

def _original_dir(site_id: str) -> Path:
    d = _site_safe_dir(site_id) / "original"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _finalized_dir(site_id: str) -> Path:
    d = _site_safe_dir(site_id) / "finalized-history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _original_meta_path(site_id: str) -> Path:
    return _original_dir(site_id) / "original.meta.json"


def get_original_status(site_id: str) -> dict[str, Any]:
    meta_path = _original_meta_path(site_id)
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    orig_file = Path(meta.get("safePath") or (_original_dir(site_id) / "PLUs.xml"))
    history = list_finalized_history(site_id)
    return {
        "protected": bool(meta.get("protected") and orig_file.is_file()),
        "exists": orig_file.is_file(),
        "meta": meta,
        "safePath": str(orig_file) if orig_file.is_file() else None,
        "finalizedCount": history.get("count") or 0,
        "finalizedKeep": FINALIZED_KEEP,
        "history": history.get("entries") or [],
        "message": (
            "Protected original is locked until you Sign off / Finalize. "
            "Restore anytime as a fail-safe. On finalize the old original moves to history (last 3 kept)."
            if orig_file.is_file()
            else "No protected original yet — first Apply will snapshot the current PLUs.xml."
        ),
    }


def ensure_protected_original(site_id: str, *, force: bool = False) -> dict[str, Any]:
    """
    Snapshot the working PLUs.xml into original/ if none exists (or force=True after sign-off).
    Never overwrites an existing protected original unless force is set (finalize path).
    """
    export_dir = _export_dir(site_id)
    plu = _plu_file(export_dir)
    if not plu or not plu.is_file():
        raise FileNotFoundError("No PLUs.xml in site export to protect")

    dest = _original_dir(site_id) / plu.name
    meta_path = _original_meta_path(site_id)
    if dest.is_file() and meta_path.is_file() and not force:
        return get_original_status(site_id)

    shutil.copy2(plu, dest)
    meta = {
        "protected": True,
        "siteId": site_id,
        "originalName": plu.name,
        "sourcePath": str(plu),
        "safePath": str(dest),
        "bytes": dest.stat().st_size,
        "createdAt": _utc_now(),
        "sha1": hashlib.sha1(dest.read_bytes()).hexdigest(),
        "note": "Protected baseline — not replaced until Sign off / Finalize",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return get_original_status(site_id)


def list_finalized_history(site_id: str) -> dict[str, Any]:
    root = _finalized_dir(site_id)
    entries: list[dict[str, Any]] = []
    if root.is_dir():
        for d in sorted(root.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            meta_file = d / "meta.json"
            try:
                if meta_file.is_file():
                    entries.append(json.loads(meta_file.read_text(encoding="utf-8")))
                else:
                    entries.append({"id": d.name, "path": str(d)})
            except (OSError, json.JSONDecodeError):
                continue
    return {"ok": True, "siteId": site_id, "entries": entries, "count": len(entries), "keep": FINALIZED_KEEP}


def _prune_finalized(site_id: str) -> None:
    root = _finalized_dir(site_id)
    dirs = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    for old in dirs[FINALIZED_KEEP:]:
        try:
            shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass


def finalize_original(site_id: str, *, note: str | None = None, signed_by: str | None = None) -> dict[str, Any]:
    """
    User sign-off: archive the protected original into finalized-history (keep last 3),
    then re-snapshot current working PLUs.xml as the new protected original.
    """
    status = get_original_status(site_id)
    if not status.get("exists"):
        # Nothing protected yet — just snapshot current as original
        ensure_protected_original(site_id, force=True)
        st = get_original_status(site_id)
        return {
            "ok": True,
            **st,
            "archived": None,
            "message": "No prior original — current PLUs.xml is now the protected baseline.",
        }

    meta = status.get("meta") or {}
    src = Path(meta.get("safePath") or (_original_dir(site_id) / "PLUs.xml"))
    if not src.is_file():
        raise FileNotFoundError("Protected original file missing on disk")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = _finalized_dir(site_id) / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / src.name
    shutil.copy2(src, dest_file)
    hist_meta = {
        "id": stamp,
        "siteId": site_id,
        "finalizedAt": _utc_now(),
        "note": note or "",
        "signedBy": signed_by or "",
        "originalName": src.name,
        "path": str(dest_file),
        "bytes": dest_file.stat().st_size,
        "sha1": hashlib.sha1(dest_file.read_bytes()).hexdigest(),
        "priorMeta": meta,
    }
    (dest_dir / "meta.json").write_text(json.dumps(hist_meta, indent=2), encoding="utf-8")
    _prune_finalized(site_id)

    # Replace protected original with current working export
    ensure_protected_original(site_id, force=True)
    status = get_original_status(site_id)
    return {
        "ok": True,
        **status,
        "archived": hist_meta,
        "message": (
            f"Signed off. Prior original archived as {stamp}. "
            f"Keeping last {FINALIZED_KEEP} finalized snapshots. "
            "Current PLUs.xml is the new protected baseline."
        ),
    }


def restore_from_original(site_id: str) -> dict[str, Any]:
    """Fail-safe: restore protected original over the working export PLUs.xml."""
    status = get_original_status(site_id)
    if not status.get("exists"):
        raise FileNotFoundError("No protected original to restore — apply once to create it, or finalize first.")
    src = Path((status.get("meta") or {}).get("safePath") or "")
    if not src.is_file():
        raise FileNotFoundError(f"Original file missing: {src}")

    export_dir = _export_dir(site_id)
    plu = _plu_file(export_dir)
    dest = plu if plu else (export_dir / src.name)
    pre = None
    if dest.is_file():
        pre = _safe_copy_file(site_id, dest, reason="pre-restore-original")
    shutil.copy2(src, dest)
    invalidate_plu_cache(site_id)
    return {
        "ok": True,
        "restoredFrom": str(src),
        "restoredTo": str(dest),
        "preRestoreCopy": pre,
        "message": f"Restored {dest.name} from protected original. Pre-restore safe copy kept.",
        "original": get_original_status(site_id),
    }


def restore_finalized(site_id: str, history_id: str) -> dict[str, Any]:
    """Restore a finalized-history snapshot over the working export (safe-copy current first)."""
    hist = list_finalized_history(site_id)
    entry = next((e for e in hist["entries"] if e.get("id") == history_id), None)
    if not entry:
        raise FileNotFoundError(f"Finalized snapshot not found: {history_id}")
    src = Path(entry.get("path") or "")
    if not src.is_file():
        raise FileNotFoundError(f"Finalized file missing: {src}")
    export_dir = _export_dir(site_id)
    plu = _plu_file(export_dir)
    dest = plu if plu else (export_dir / src.name)
    pre = None
    if dest.is_file():
        pre = _safe_copy_file(site_id, dest, reason=f"pre-restore-finalized:{history_id}")
    shutil.copy2(src, dest)
    invalidate_plu_cache(site_id)
    return {
        "ok": True,
        "restored": entry,
        "preRestoreCopy": pre,
        "message": f"Restored {dest.name} from finalized snapshot {history_id}",
    }


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


def _field_match_names(field: str) -> set[str]:
    """All XML names that map to this canonical field (case-insensitive compare via lower)."""
    names = {field, _FIELD_WRITE_NAME.get(field, field)}
    for alias, canon in _FIELD_ALIASES.items():
        if canon == field:
            names.add(alias)
    # attribute-style demo names
    if field == "department":
        names.update({"DepartmentId", "departmentId", "dept"})
    if field == "description":
        names.update({"Description", "desc"})
    if field == "price":
        names.update({"Price"})
    if field == "pcode":
        names.update({"ProductCode", "productCode"})
    if field == "foodStamp":
        names.update({
            "FoodStamp", "foodStamps", "FoodStamps",
            "allowFoodStamps", "AllowFoodStamps", "ebt", "ebtAllowed",
        })
    if field == "active":
        names.update({"Active"})
    return names


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

    field = _FIELD_ALIASES.get(field, field)
    write_name = _FIELD_WRITE_NAME.get(field, field)
    match_names = {n.lower() for n in _field_match_names(field)}

    root = ET.fromstring(xml_text)
    target_n = _norm_upc(upc)
    target_digits = re.sub(r"\D", "", upc or "")
    old_value = ""
    found = False
    for el in root.iter():
        tag = _local(el.tag).lower()
        if tag not in {"plu", "item"}:
            continue
        rec = _plu_element_to_dict(el)
        rec_digits = re.sub(r"\D", "", rec.get("upc") or "")
        if rec["upcNormalized"] != target_n and rec_digits != target_digits and rec_digits != target_n:
            # also match raw upc string
            if str(rec.get("upc") or "") != str(upc):
                continue
        # 1) child element
        for child in list(el):
            if _local(child.tag).lower() in match_names:
                old_value = (child.text or "").strip()
                child.text = str(new_value)
                found = True
                break
        # 2) attribute on Item/plu
        if not found:
            for ak in list(el.attrib.keys()):
                if _local(ak).lower() in match_names:
                    old_value = str(el.attrib.get(ak) or "")
                    el.set(ak, str(new_value))
                    found = True
                    break
        if not found:
            # Prefer attribute write if the element already uses attributes (Item style)
            if el.attrib and not list(el):
                # map write name to demo-style attr when possible
                attr_name = {
                    "description": "Description",
                    "price": "Price",
                    "department": "DepartmentId",
                    "pcode": "ProductCode",
                    "foodStamp": "FoodStamp",
                    "active": "Active",
                    "taxable": "Taxable",
                    "discountable": "Discountable",
                    "returnable": "Returnable",
                }.get(field, write_name)
                el.set(attr_name, str(new_value))
                old_value = ""
                found = True
            else:
                ns = ""
                for child in el:
                    if "}" in child.tag:
                        ns = child.tag.split("}")[0] + "}"
                        break
                new_el = ET.SubElement(el, f"{ns}{write_name}" if ns else write_name)
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
    Ensures a protected original snapshot exists first, then safe-copies each touched file.
    """
    prune_safe_copies(site_id)
    try:
        ensure_protected_original(site_id, force=False)
    except FileNotFoundError:
        pass
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
    orig = get_original_status(site_id)
    return {
        "ok": len(applied) > 0 and not errors,
        "applied": applied,
        "appliedCount": len(applied),
        "errors": errors,
        "safeCopies": list(safe_copies.values()),
        "original": orig,
        "message": (
            f"Applied {len(applied)} change(s) to local backup. "
            f"Safe copies kept {SAFE_RETENTION_DAYS} days under {_site_safe_dir(site_id)}. "
            + (
                "Protected original baseline retained until you Sign off / Finalize. "
                if orig.get("protected")
                else ""
            )
            + "Use Import-Export Utility to push SMS config back to Commander when ready."
        ),
        **list_changes(site_id),
    }
