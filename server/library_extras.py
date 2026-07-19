"""
High-leverage library utilities: pair health, tag verify, sidecars,
pair map export/import, archive packs, smart saved searches.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from db import connect
from file_metadata import read_file_metadata, write_file_metadata, normalize_tags

# Lazy ops access avoids circular import with media_ops
def _ops():
    import media_ops as ops
    return ops

SIDECAR_SUFFIX = ".fafo.json"
SMART_SEARCHES_KEY = "smart_searches"


def sidecar_path_for(file_path: Path) -> Path:
    return Path(str(file_path) + SIDECAR_SUFFIX)


def read_sidecar(file_path: Path) -> dict[str, Any] | None:
    p = sidecar_path_for(file_path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_sidecar(
    file_path: Path,
    *,
    tags: list[str] | None = None,
    rating: int | None = None,
    pair_code: str | None = None,
    pair_role: str | None = None,
    notes: str | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Write/update a durable sidecar next to the media file (great for MKV)."""
    existing = read_sidecar(file_path) or {}
    if tags is not None:
        existing["tags"] = normalize_tags(tags)
    if rating is not None:
        existing["rating"] = max(0, min(5, int(rating)))
    if pair_code is not None:
        existing["pair_code"] = pair_code
    if pair_role is not None:
        existing["pair_role"] = pair_role
    if notes is not None:
        existing["notes"] = notes
    if extra:
        existing.update(extra)
    existing["name"] = file_path.name
    existing["updated"] = time.time()
    existing["version"] = 1
    sp = sidecar_path_for(file_path)
    sp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(sp), "data": existing}


def merge_sidecar_into_meta(file_path: Path, catalog_tags: list[str] | None = None) -> dict[str, Any]:
    """Combine shell metadata + sidecar for the richest read."""
    shell = read_file_metadata(file_path)
    side = read_sidecar(file_path) or {}
    tags = list(shell.get("tags") or [])
    for t in side.get("tags") or []:
        if t not in tags:
            tags.append(t)
    for t in catalog_tags or []:
        if t not in tags:
            tags.append(t)
    rating = shell.get("rating") or side.get("rating") or 0
    code = _ops().extract_pair_code_from_tags(tags) or side.get("pair_code")
    role = side.get("pair_role") or _ops().infer_pair_role_from_tags(tags, file_path.name)
    return {
        "tags": tags,
        "rating": int(rating or 0),
        "pair_code": code,
        "pair_role": role,
        "sidecar": bool(side),
        "shell_methods": shell.get("methods") or [],
    }


def write_meta_with_sidecar(
    file_path: Path,
    tags: list[str] | None = None,
    rating: int | None = None,
    pair_code: str | None = None,
    pair_role: str | None = None,
    force_sidecar: bool = False,
) -> dict[str, Any]:
    """Write Explorer props when possible; always keep sidecar for MKV/weak types or when forced."""
    result = write_file_metadata(file_path, tags=tags, rating=rating)
    ext = file_path.suffix.lower()
    weak = ext in {".mkv", ".webm", ".avi", ".ts", ".m2ts"} or not result.get("ok")
    if force_sidecar or weak or pair_code:
        code = pair_code or (_ops().extract_pair_code_from_tags(tags or []) if tags else None)
        role = pair_role
        if not role and tags:
            role = _ops().infer_pair_role_from_tags(tags, file_path.name)
        sc = write_sidecar(
            file_path,
            tags=tags if tags is not None else None,
            rating=rating,
            pair_code=code,
            pair_role=role,
        )
        result["sidecar"] = sc
        result["methods"] = list(result.get("methods") or []) + ["sidecar"]
        if sc.get("ok"):
            result["ok"] = True
    return result


# ---------- Pair health ----------

def pair_health_report(*, relink: bool = False) -> dict[str, Any]:
    """Classify pairs and orphan UP-#### tags for a health dashboard."""
    if relink:
        _ops().relink_pairs_from_metadata()
    pairs = _ops().list_pairs()
    complete = []
    partial = []
    broken = []

    for p in pairs:
        bid = p.get("before_media_id")
        aid = p.get("after_media_id")
        before = _ops().get_media(bid) if bid else None
        after = _ops().get_media(aid) if aid else None
        before_ok = False
        after_ok = False
        before_path = p.get("before_path") or ""
        after_path = p.get("after_path") or ""
        try:
            if before:
                before_path = str(_ops().resolve_path(before))
                before_ok = Path(before_path).is_file()
            elif before_path:
                before_ok = Path(before_path).is_file()
        except Exception:
            before_ok = False
        try:
            if after:
                after_path = str(_ops().resolve_path(after))
                after_ok = Path(after_path).is_file()
            elif after_path:
                after_ok = Path(after_path).is_file()
        except Exception:
            after_ok = False

        entry = {
            "id": p.get("id"),
            "pair_code": p.get("pair_code") or p.get("pairCode"),
            "name": p.get("name"),
            "before_id": bid,
            "after_id": aid,
            "before_name": p.get("before_name"),
            "after_name": p.get("after_name"),
            "before_path": before_path,
            "after_path": after_path,
            "before_ok": before_ok,
            "after_ok": after_ok,
        }
        if before_ok and after_ok:
            complete.append(entry)
        elif before_ok or after_ok:
            partial.append(entry)
        else:
            broken.append(entry)

    # Orphan media with UP-#### but no pair_id
    orphans = []
    looks_upscaled = []
    for m in _ops().get_all_media():
        tags = m.get("tags") or []
        code = _ops().extract_pair_code_from_tags(tags)
        if code and not m.get("pair_id"):
            orphans.append({
                "id": m["id"],
                "name": m["name"],
                "pair_code": code,
                "role": _ops().infer_pair_role_from_tags(tags, m["name"]),
            })
        if not m.get("pair_id") and _ops()._is_upscaled_name(m.get("name") or ""):
            looks_upscaled.append({"id": m["id"], "name": m["name"]})

    return {
        "ok": True,
        "summary": {
            "complete": len(complete),
            "partial": len(partial),
            "broken": len(broken),
            "orphan_tagged": len(orphans),
            "unpaired_upscale_named": len(looks_upscaled),
            "total_pairs": len(pairs),
        },
        "complete": complete,
        "partial": partial,
        "broken": broken,
        "orphan_tagged": orphans,
        "unpaired_upscale_named": looks_upscaled[:100],
    }


# ---------- Tag verify / rewrite ----------

def verify_tags_on_disk(
    media_ids: list[str] | None = None,
    *,
    limit: int = 500,
    fix: bool = False,
) -> dict[str, Any]:
    """Compare catalog tags/rank vs file shell+sidecar; optionally rewrite disk."""
    if media_ids:
        items = [_ops().get_media(mid) for mid in media_ids]
        items = [m for m in items if m]
    else:
        items = _ops().get_all_media()[:limit]

    matches = []
    mismatches = []
    missing = []
    fixed = []

    for m in items:
        try:
            path = _ops().resolve_path(m)
        except Exception:
            missing.append({"id": m["id"], "name": m["name"], "error": "unresolvable"})
            continue
        if not path.is_file():
            missing.append({"id": m["id"], "name": m["name"], "path": str(path)})
            continue

        disk = merge_sidecar_into_meta(path, m.get("tags"))
        cat_tags = sorted({t.lower() for t in (m.get("tags") or [])})
        disk_tags = sorted({t.lower() for t in (disk.get("tags") or [])})
        cat_rank = int(m.get("rank") or 0)
        disk_rank = int(disk.get("rating") or 0)
        ok = cat_tags == disk_tags and cat_rank == disk_rank
        row = {
            "id": m["id"],
            "name": m["name"],
            "path": str(path),
            "catalog_tags": m.get("tags") or [],
            "disk_tags": disk.get("tags") or [],
            "catalog_rank": cat_rank,
            "disk_rank": disk_rank,
            "has_sidecar": disk.get("sidecar"),
        }
        if ok:
            matches.append(row)
        else:
            mismatches.append(row)
            if fix:
                wr = write_meta_with_sidecar(
                    path,
                    tags=m.get("tags") or [],
                    rating=cat_rank,
                    pair_code=_ops().extract_pair_code_from_tags(m.get("tags") or []),
                    pair_role=m.get("pair_role"),
                    force_sidecar=path.suffix.lower() in {".mkv", ".webm", ".avi"},
                )
                # refresh catalog file_tags
                with connect() as conn:
                    conn.execute(
                        "UPDATE media SET file_tags=? WHERE id=?",
                        (json.dumps(m.get("tags") or []), m["id"]),
                    )
                fixed.append({**row, "write": wr})

    return {
        "ok": True,
        "checked": len(items),
        "match_count": len(matches),
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "fixed_count": len(fixed),
        "mismatches": mismatches[:200],
        "missing": missing[:100],
        "fixed": fixed[:100],
    }


# ---------- Pair map export / import ----------

def export_pair_map() -> dict[str, Any]:
    pairs = _ops().list_pairs()
    out = []
    for p in pairs:
        before = _ops().get_media(p.get("before_media_id") or "")
        after = _ops().get_media(p.get("after_media_id") or "")
        bp = ap = ""
        try:
            if before:
                bp = str(_ops().resolve_path(before))
        except Exception:
            bp = p.get("before_path") or ""
        try:
            if after:
                ap = str(_ops().resolve_path(after))
        except Exception:
            ap = p.get("after_path") or ""

        def snap(m: dict | None, path: str) -> dict:
            if not m:
                return {"name": Path(path).name if path else "", "path": path, "size": 0, "tags": []}
            st = Path(path).stat() if path and Path(path).is_file() else None
            return {
                "name": m.get("name"),
                "path": path,
                "size": st.st_size if st else m.get("size") or 0,
                "tags": m.get("tags") or [],
                "rank": m.get("rank") or 0,
                "role": m.get("pair_role"),
            }

        out.append({
            "pair_code": p.get("pair_code"),
            "name": p.get("name"),
            "kind": p.get("kind"),
            "pinned": bool(p.get("pinned")),
            "notes": p.get("notes") or "",
            "before": snap(before, bp),
            "after": snap(after, ap),
        })
    return {
        "version": 1,
        "exported_at": time.time(),
        "pairs": out,
    }


def import_pair_map(data: dict[str, Any], *, write_files: bool = True) -> dict[str, Any]:
    """Re-create/update pairs from an exported map using name+size (+path) matching."""
    pairs = data.get("pairs") or []
    created = updated = skipped = 0
    errors = []

    for entry in pairs:
        try:
            code = entry.get("pair_code") or _ops()._next_pair_code()
            b = entry.get("before") or {}
            a = entry.get("after") or {}
            before = None
            after = None
            if b.get("path") and Path(b["path"]).is_file():
                before = _ops().find_media_by_name(Path(b["path"]).name, Path(b["path"]).stat().st_size)
            if not before and b.get("name"):
                before = _ops().find_media_by_identity(b["name"], b.get("size"))
            if a.get("path") and Path(a["path"]).is_file():
                after = _ops().find_media_by_name(Path(a["path"]).name, Path(a["path"]).stat().st_size)
            if not after and a.get("name"):
                after = _ops().find_media_by_identity(a["name"], a.get("size"))

            if not before or not after:
                skipped += 1
                errors.append(f"{code}: missing media (before={bool(before)}, after={bool(after)})")
                continue

            # Merge tags from map
            if b.get("tags"):
                _ops().batch_add_tags([before["id"]], b["tags"], write_file_tags=write_files)
            if a.get("tags"):
                _ops().batch_add_tags([after["id"]], a["tags"], write_file_tags=write_files)

            existing = _ops().get_pair_by_code(code)
            if existing:
                with connect() as conn:
                    conn.execute(
                        """UPDATE pairs SET before_media_id=?, after_media_id=?, name=?, notes=?, pinned=?
                           WHERE id=?""",
                        (
                            before["id"], after["id"],
                            entry.get("name") or existing.get("name"),
                            entry.get("notes") or "",
                            1 if entry.get("pinned") else 0,
                            existing["id"],
                        ),
                    )
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='before' WHERE id=?",
                        (existing["id"], before["id"]),
                    )
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='after' WHERE id=?",
                        (existing["id"], after["id"]),
                    )
                updated += 1
                pid = existing["id"]
            else:
                pair = _ops().save_pair(
                    entry.get("name") or f"{before['name']} ↔ {after['name']}",
                    before["id"],
                    after["id"],
                    entry.get("kind") or "video",
                    pinned=bool(entry.get("pinned", True)),
                    notes=entry.get("notes") or "imported-pair-map",
                    source="import",
                    pair_code=code,
                )
                created += 1
                pid = pair.get("id")

            if write_files:
                for mid, role, tags in (
                    (before["id"], "before", b.get("tags") or []),
                    (after["id"], "after", a.get("tags") or []),
                ):
                    m = _ops().get_media(mid)
                    if not m:
                        continue
                    try:
                        path = _ops().resolve_path(m)
                        write_meta_with_sidecar(
                            path,
                            tags=list(set((m.get("tags") or []) + (tags or []) + [code])),
                            rating=m.get("rank") or 0,
                            pair_code=code,
                            pair_role=role,
                        )
                    except Exception:
                        pass
        except Exception as e:
            errors.append(str(e))
            skipped += 1

    _ops().relink_pairs_from_metadata()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:50],
    }


# ---------- Archive pair ----------

def archive_pair(pair_id: str, dest_root: str, *, copy_sidecars: bool = True) -> dict[str, Any]:
    """
    Copy both files of a pair into dest_root/UP-XXXX/{before,after}/ plus manifest.
    """
    pair = _ops().get_pair(pair_id) or _ops().get_pair_by_code(pair_id)
    if not pair:
        raise FileNotFoundError("Pair not found")
    code = pair.get("pair_code") or pair.get("id") or "PAIR"
    dest = Path(dest_root).expanduser().resolve() / str(code)
    before_dir = dest / "before"
    after_dir = dest / "after"
    before_dir.mkdir(parents=True, exist_ok=True)
    after_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for role, mid, folder in (
        ("before", pair.get("before_media_id"), before_dir),
        ("after", pair.get("after_media_id"), after_dir),
    ):
        m = _ops().get_media(mid) if mid else None
        src = None
        if m:
            try:
                src = _ops().resolve_path(m)
            except Exception:
                src = None
        if (not src or not src.is_file()) and pair.get(f"{role}_path"):
            src = Path(pair[f"{role}_path"])
        if not src or not src.is_file():
            continue
        target = folder / src.name
        shutil.copy2(src, target)
        copied.append({"role": role, "from": str(src), "to": str(target)})
        sc = sidecar_path_for(src)
        if copy_sidecars and sc.is_file():
            shutil.copy2(sc, sidecar_path_for(target))
        # Ensure sidecar at archive dest with pair info
        write_sidecar(
            target,
            tags=(m or {}).get("tags") if m else None,
            rating=(m or {}).get("rank") if m else None,
            pair_code=code,
            pair_role=role,
        )

    manifest = {
        "pair_code": code,
        "name": pair.get("name"),
        "archived_at": time.time(),
        "files": copied,
        "pair": {
            "id": pair.get("id"),
            "kind": pair.get("kind"),
            "notes": pair.get("notes"),
        },
    }
    (dest / "pair_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"ok": True, "dest": str(dest), "copied": copied, "manifest": manifest}


# ---------- Smart searches ----------

def get_smart_searches() -> list[dict]:
    raw = _ops().get_setting(SMART_SEARCHES_KEY, "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_smart_searches(items: list[dict]) -> list[dict]:
    cleaned = []
    for it in items:
        if not it.get("name"):
            continue
        cleaned.append({
            "id": it.get("id") or f"ss-{uuid.uuid4().hex[:8]}",
            "name": str(it["name"]).strip(),
            "query": it.get("query") or {},
            "created_at": it.get("created_at") or time.time(),
        })
    _ops().set_setting(SMART_SEARCHES_KEY, json.dumps(cleaned))
    return cleaned


def add_smart_search(name: str, query: dict) -> dict:
    items = get_smart_searches()
    entry = {
        "id": f"ss-{uuid.uuid4().hex[:8]}",
        "name": name.strip(),
        "query": query or {},
        "created_at": time.time(),
    }
    items.append(entry)
    save_smart_searches(items)
    return entry


def delete_smart_search(sid: str) -> bool:
    items = get_smart_searches()
    new = [i for i in items if i.get("id") != sid]
    save_smart_searches(new)
    return len(new) < len(items)


def run_smart_search(query: dict, page: int = 0, limit: int = 80) -> dict:
    """
    query keys: search, tags (list/str), type, rank_min, has_pair (bool),
    unpaired_upscale (bool), category, status, sort
    """
    tags = query.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    if query.get("unpaired_upscale"):
        items = []
        for m in _ops().get_all_media():
            if m.get("pair_id"):
                continue
            if _ops()._is_upscaled_name(m.get("name") or ""):
                items.append(m)
        return {"items": items[page * limit:(page + 1) * limit], "total": len(items), "page": page}

    if query.get("has_pair") is True:
        # filter after query
        res = _ops().query_media(
            search=query.get("search") or "",
            tags=tags,
            media_type=query.get("type"),
            category=query.get("category"),
            status=query.get("status"),
            rank_min=query.get("rank_min"),
            sort=query.get("sort") or "name",
            page=0,
            limit=5000,
        )
        items = [m for m in (res.get("items") or []) if m.get("pair_id")]
        total = len(items)
        return {"items": items[page * limit:(page + 1) * limit], "total": total, "page": page}

    if query.get("has_pair") is False:
        res = _ops().query_media(
            search=query.get("search") or "",
            tags=tags,
            media_type=query.get("type"),
            category=query.get("category"),
            status=query.get("status"),
            rank_min=query.get("rank_min"),
            sort=query.get("sort") or "name",
            page=0,
            limit=5000,
        )
        items = [m for m in (res.get("items") or []) if not m.get("pair_id")]
        total = len(items)
        return {"items": items[page * limit:(page + 1) * limit], "total": total, "page": page}

    return _ops().query_media(
        search=query.get("search") or "",
        tags=tags,
        media_type=query.get("type"),
        category=query.get("category"),
        status=query.get("status"),
        rank_min=query.get("rank_min"),
        sort=query.get("sort") or "name",
        page=page,
        limit=limit,
    )


def default_smart_searches() -> list[dict]:
    return [
        {"id": "ss-up-codes", "name": "Has UP- pair code", "query": {"search": "UP-", "sort": "name"}, "created_at": 0},
        {"id": "ss-unpaired-up", "name": "Unpaired upscale names", "query": {"unpaired_upscale": True}, "created_at": 0},
        {"id": "ss-best", "name": "Rank ★★★★+", "query": {"rank_min": 4, "sort": "rank"}, "created_at": 0},
        {"id": "ss-paired", "name": "In a pair", "query": {"has_pair": True}, "created_at": 0},
        {"id": "ss-unpaired", "name": "Not in a pair", "query": {"has_pair": False}, "created_at": 0},
    ]


def ensure_default_smart_searches() -> list[dict]:
    items = get_smart_searches()
    if items:
        return items
    return save_smart_searches(default_smart_searches())
