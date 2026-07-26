"""File operations: scan, rename, metadata, thumbnails."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterator

from db import connect, file_type, media_id, row_to_media

THUMB_DIR = Path(__file__).parent / "thumbnails"
THUMB_DIR.mkdir(exist_ok=True)

SKIP_DIR_NAMES = {
    "$recycle.bin", "$RECYCLE.BIN", "system volume information",
    "@eadir", ".git", "node_modules", "__pycache__", "thumbs.db",
}
# Windows recycle index files (not playable video — tiny metadata stubs)
SKIP_FILE_PREFIXES = ("$i", "$r0")


def mime_for_path(name: str, media_type: str) -> str:
    ext = Path(name).suffix.lower()
    video_mimes = {
        ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
        ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
        ".wmv": "video/x-ms-wmv", ".flv": "video/x-flv", ".ts": "video/mp2t",
    }
    image_mimes = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
        ".tif": "image/tiff", ".tiff": "image/tiff",
    }
    if media_type == "video":
        return video_mimes.get(ext, "video/mp4")
    return image_mimes.get(ext, "image/jpeg")


def should_skip_entry(name: str, is_dir: bool, parent_rel: str = "") -> bool:
    if is_dir:
        return name.lower() in {n.lower() for n in SKIP_DIR_NAMES} or name.startswith(".")
    parent_low = parent_rel.lower()
    if "$recycle.bin" in parent_low.replace("\\", "/"):
        return True
    if name.startswith("$I") and name.lower().endswith((".mp4", ".mkv", ".avi", ".mov")):
        return True
    return False

INVALID_WIN = re.compile(r'[<>:"/\\|?*]')


def find_ffmpeg() -> str | None:
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            return p
    for candidate in (
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def find_ffprobe() -> str | None:
    for name in ("ffprobe", "ffprobe.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def add_directory(path: str) -> dict[str, Any]:
    p = Path(path).resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"Not a directory: {path}")
    did = f"dir-{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO directories (id, path, name, added_at) VALUES (?, ?, ?, ?)",
            (did, str(p), p.name, time.time()),
        )
        row = conn.execute("SELECT * FROM directories WHERE id=?", (did,)).fetchone()
    return dict(row)


def list_directories() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM directories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def remove_directory(dir_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM directories WHERE id=?", (dir_id,))


def scan_directory(
    dir_id: str,
    recursive: bool = True,
    on_progress: Callable[[int, str], None] | None = None,
) -> int:
    with connect() as conn:
        row = conn.execute("SELECT * FROM directories WHERE id=?", (dir_id,)).fetchone()
    if not row:
        raise FileNotFoundError("Directory not registered")
    root = Path(row["path"])
    found: list[tuple[str, Path]] = []
    count = 0

    def walk(folder: Path, prefix: str = "") -> None:
        nonlocal count
        try:
            entries = sorted(folder.iterdir(), key=lambda x: x.name.lower())
        except PermissionError:
            return
        for entry in entries:
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            if entry.is_dir():
                if recursive and not should_skip_entry(entry.name, True, rel):
                    walk(entry, rel)
            elif entry.is_file():
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    walk(root)
    now = time.time()
    seen_ids: set[str] = set()

    with connect() as conn:
        for rel, full in found:
            mid = media_id(dir_id, rel)
            seen_ids.add(mid)
            stat = full.stat()
            existing = conn.execute(
                "SELECT tags, notes, thumb_path, pair_id, pair_role, rank FROM media WHERE id=?",
                (mid,),
            ).fetchone()
            # Read Explorer-visible tags/rating + optional .fafo.json sidecar
            file_meta_tags = read_embedded_tags(full)
            file_rank = 0
            try:
                from library_extras import merge_sidecar_into_meta
                fm = merge_sidecar_into_meta(full, None)
                if fm.get("tags"):
                    file_meta_tags = list(fm["tags"])
                file_rank = int(fm.get("rating") or 0)
            except Exception:
                try:
                    from file_metadata import read_file_metadata
                    fm = read_file_metadata(full)
                    if fm.get("tags"):
                        file_meta_tags = list(fm["tags"])
                    file_rank = int(fm.get("rating") or 0)
                except Exception:
                    pass
            file_tags_json = json.dumps(file_meta_tags)

            if existing:
                # Keep catalog tags if already set; otherwise import from file
                try:
                    cat_tags = json.loads(existing["tags"] or "[]")
                except Exception:
                    cat_tags = []
                if cat_tags:
                    tags = existing["tags"]
                elif file_meta_tags:
                    tags = json.dumps(file_meta_tags)
                else:
                    tags = existing["tags"] or "[]"
                notes = existing["notes"] if existing else ""
                thumb = existing["thumb_path"] if existing else None
                pair_id = existing["pair_id"] if existing else None
                pair_role = existing["pair_role"] if existing else None
                rank = int(existing["rank"] or 0) or file_rank
            else:
                tags = json.dumps(file_meta_tags)
                notes = ""
                thumb = None
                pair_id = None
                pair_role = None
                rank = file_rank

            conn.execute(
                """INSERT INTO media (id, dir_id, rel_path, name, ext, type, size, mtime, tags, notes, thumb_path, pair_id, pair_role, file_tags, rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name, size=excluded.size, mtime=excluded.mtime,
                     file_tags=excluded.file_tags,
                     tags=CASE WHEN media.tags IS NULL OR media.tags='[]' THEN excluded.tags ELSE media.tags END,
                     rank=CASE WHEN IFNULL(media.rank,0)=0 AND excluded.rank>0 THEN excluded.rank ELSE media.rank END""",
                (
                    mid, dir_id, rel, full.name, full.suffix.lower(),
                    file_type(full.name), stat.st_size, stat.st_mtime,
                    tags, notes, thumb, pair_id, pair_role, file_tags_json, rank,
                ),
            )
        all_in_dir = conn.execute("SELECT id FROM media WHERE dir_id=?", (dir_id,)).fetchall()
        for r in all_in_dir:
            if r["id"] not in seen_ids:
                # File left this folder (moved/deleted). Pair DB rows may go stale;
                # relink_pairs_from_metadata() re-attaches via UP-#### tags on disk.
                conn.execute("DELETE FROM media WHERE id=?", (r["id"],))
        conn.execute("UPDATE directories SET last_scanned=? WHERE id=?", (now, dir_id))
    # Heal before/after pairs using UP-#### tags written into the files / sidecars
    try:
        relink_pairs_from_metadata()
    except Exception:
        pass
    # Optional: auto-link new upscale siblings after scan
    try:
        if get_setting("auto_pair_after_scan", "false") == "true":
            auto_pair_upscaled(min_confidence=0.85, limit=50, dry_run=False, pin=True)
    except Exception:
        pass
    return len(found)


def _norm_subpath(subpath: str) -> str:
    return subpath.strip("/").replace("\\", "/")


def _strip_virtual_prefix(rel: str, virtual_root: str) -> str | None:
    rel = rel.replace("\\", "/")
    if rel == virtual_root:
        return ""
    prefix = f"{virtual_root}/"
    if rel.startswith(prefix):
        return rel[len(prefix):]
    return None


def list_virtual_roots() -> list[dict[str, Any]]:
    """Merge top-level folder names that appear under different watched directories."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT m.rel_path, m.dir_id, d.name AS dir_name
               FROM media m JOIN directories d ON d.id = m.dir_id
               WHERE m.rel_path LIKE '%/%'"""
        ).fetchall()
    roots: dict[str, dict[str, Any]] = {}
    for r in rows:
        rel = r["rel_path"].replace("\\", "/")
        root = rel.split("/")[0]
        if root not in roots:
            roots[root] = {"name": root, "sources": {}, "total": 0}
        roots[root]["total"] += 1
        did = r["dir_id"]
        if did not in roots[root]["sources"]:
            roots[root]["sources"][did] = {
                "dir_id": did,
                "dir_name": r["dir_name"],
                "count": 0,
            }
        roots[root]["sources"][did]["count"] += 1
    out = []
    for v in roots.values():
        v["sources"] = sorted(v["sources"].values(), key=lambda x: x["dir_name"].lower())
        out.append(v)
    return sorted(out, key=lambda x: x["name"].lower())


def list_virtual_folder_index(virtual_root: str, subpath: str = "") -> dict[str, Any]:
    virtual_root = _norm_subpath(virtual_root)
    subpath = _norm_subpath(subpath)
    with connect() as conn:
        rows = conn.execute(
            "SELECT rel_path, dir_id FROM media WHERE rel_path LIKE ?",
            (f"{virtual_root}/%",),
        ).fetchall()
        dir_names = {
            r["id"]: r["name"]
            for r in conn.execute("SELECT id, name FROM directories").fetchall()
        }

    subfolder_counts: dict[str, int] = {}
    direct_files = 0
    source_counts: dict[str, int] = {}

    for r in rows:
        remainder = _strip_virtual_prefix(r["rel_path"], virtual_root)
        if remainder is None:
            continue
        if subpath:
            if remainder == subpath:
                continue
            if not remainder.startswith(f"{subpath}/"):
                continue
            remainder = remainder[len(subpath) + 1 :]
        if not remainder:
            continue
        source_counts[r["dir_id"]] = source_counts.get(r["dir_id"], 0) + 1
        if "/" in remainder:
            name = remainder.split("/")[0]
            subfolder_counts[name] = subfolder_counts.get(name, 0) + 1
        else:
            direct_files += 1

    breadcrumb: list[dict[str, str]] = []
    if subpath:
        acc = ""
        for part in subpath.split("/"):
            acc = f"{acc}/{part}" if acc else part
            breadcrumb.append({"name": part, "path": acc})

    return {
        "virtual_root": virtual_root,
        "path": subpath,
        "breadcrumb": breadcrumb,
        "subfolders": [
            {"name": k, "count": v}
            for k, v in sorted(subfolder_counts.items(), key=lambda x: x[0].lower())
        ],
        "files_count": direct_files,
        "sources": [
            {"dir_id": k, "dir_name": dir_names.get(k, k), "count": v}
            for k, v in sorted(source_counts.items(), key=lambda x: dir_names.get(x[0], x[0]).lower())
        ],
        "total_count": sum(source_counts.values()),
    }


def get_meta_facets() -> dict[str, list]:
    with connect() as conn:
        cats = conn.execute(
            "SELECT DISTINCT category FROM media WHERE category != '' ORDER BY category COLLATE NOCASE"
        ).fetchall()
        stats = conn.execute(
            "SELECT DISTINCT status FROM media WHERE status != '' ORDER BY status COLLATE NOCASE"
        ).fetchall()
    return {
        "categories": [r["category"] for r in cats],
        "statuses": [r["status"] for r in stats],
    }


def list_folder_index(dir_id: str, subpath: str = "") -> dict[str, Any]:
    subpath = _norm_subpath(subpath)
    prefix = f"{subpath}/" if subpath else ""

    with connect() as conn:
        rows = conn.execute(
            "SELECT rel_path FROM media WHERE dir_id=?",
            (dir_id,),
        ).fetchall()

    subfolder_counts: dict[str, int] = {}
    direct_files = 0
    for r in rows:
        rel = r["rel_path"].replace("\\", "/")
        if prefix:
            if not rel.startswith(prefix):
                continue
            remainder = rel[len(prefix):]
        else:
            remainder = rel
        if not remainder:
            continue
        if "/" in remainder:
            name = remainder.split("/")[0]
            subfolder_counts[name] = subfolder_counts.get(name, 0) + 1
        else:
            direct_files += 1

    breadcrumb: list[dict[str, str]] = []
    if subpath:
        acc = ""
        for part in subpath.split("/"):
            acc = f"{acc}/{part}" if acc else part
            breadcrumb.append({"name": part, "path": acc})

    return {
        "dir_id": dir_id,
        "path": subpath,
        "breadcrumb": breadcrumb,
        "subfolders": [
            {"name": k, "count": v}
            for k, v in sorted(subfolder_counts.items(), key=lambda x: x[0].lower())
        ],
        "files_count": direct_files,
    }


def query_media(
    search: str = "",
    tags: list[str] | None = None,
    media_type: str | None = None,
    dir_id: str | None = None,
    path_prefix: str | None = None,
    folder_only: bool = False,
    virtual_root: str | None = None,
    category: str | None = None,
    status: str | None = None,
    rank_min: int | None = None,
    sort: str = "name",
    page: int = 0,
    limit: int = 80,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    if search:
        q = f"%{search.lower()}%"
        clauses.append(
            "(LOWER(name) LIKE ? OR LOWER(rel_path) LIKE ? OR LOWER(notes) LIKE ? "
            "OR LOWER(tags) LIKE ? OR LOWER(category) LIKE ? OR LOWER(status) LIKE ?)"
        )
        params.extend([q, q, q, q, q, q])
    if media_type:
        clauses.append("type=?")
        params.append(media_type)
    if dir_id:
        clauses.append("dir_id=?")
        params.append(dir_id)
    if category:
        clauses.append("category=?")
        params.append(category)
    if status:
        clauses.append("status=?")
        params.append(status)
    if rank_min is not None and rank_min > 0:
        clauses.append("rank >= ?")
        params.append(rank_min)
    if virtual_root:
        vr = _norm_subpath(virtual_root)
        clauses.append("(rel_path LIKE ? OR rel_path LIKE ?)")
        params.extend([f"{vr}/%", f"{vr}\\%"])
    if path_prefix is not None and not search:
        sub = _norm_subpath(path_prefix)
        if virtual_root:
            vr = _norm_subpath(virtual_root)
            sub = f"{vr}/{sub}" if sub else vr
        if sub:
            clauses.append("rel_path LIKE ?")
            params.append(f"{sub}/%")
            if folder_only:
                clauses.append("rel_path NOT LIKE ?")
                params.append(f"{sub}/%/%")
        elif folder_only:
            clauses.append("rel_path NOT LIKE '%/%'")
    if tags:
        for t in tags:
            clauses.append("tags LIKE ?")
            params.append(f'%"{t}"%')

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = {
        "name": "name COLLATE NOCASE",
        "path": "rel_path COLLATE NOCASE",
        "type": "type, name COLLATE NOCASE",
        "tags": "LENGTH(tags) DESC, name COLLATE NOCASE",
        "mtime": "mtime DESC",
        "size": "size DESC",
        "rank": "rank DESC, name COLLATE NOCASE",
        "category": "category COLLATE NOCASE, name COLLATE NOCASE",
    }.get(sort, "name COLLATE NOCASE")

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) as c FROM media {where}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM media {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [limit, page * limit],
        ).fetchall()
    return {"items": [row_to_media(r) for r in rows], "total": total, "page": page, "limit": limit}


def get_all_tags() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT tags FROM media").fetchall()
    tags: set[str] = set()
    for r in rows:
        for t in json.loads(r["tags"] or "[]"):
            tags.add(t)
    return sorted(tags, key=str.lower)


def get_media(mid: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone()
    return row_to_media(row) if row else None


def get_all_media() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM media").fetchall()
    return [row_to_media(r) for r in rows]


def resolve_path(media: dict) -> Path:
    with connect() as conn:
        d = conn.execute("SELECT path FROM directories WHERE id=?", (media["dir_id"],)).fetchone()
    if not d:
        raise FileNotFoundError("Directory missing")
    return Path(d["path"]) / media["rel_path"].replace("/", "\\")


def sanitize_name(name: str) -> str:
    return INVALID_WIN.sub("_", name).strip()


def apply_pattern(pattern: str, orig: str, tags: list[str], n: int) -> str:
    stem = Path(orig).stem
    ext = Path(orig).suffix
    tag_str = "_".join(tags)
    result = (
        pattern.replace("{orig}", stem).replace("{name}", stem)
        .replace("{tags}", tag_str).replace("{tag}", tags[0] if tags else "")
        .replace("{n}", str(n).zfill(3)).replace("{ext}", ext.lstrip("."))
    )
    return sanitize_name(result) + ext


def push_rename_history(pattern: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rename_history WHERE pattern=?", (pattern,))
        conn.execute("INSERT INTO rename_history (pattern, used_at) VALUES (?, ?)", (pattern, time.time()))
        old = conn.execute("SELECT id FROM rename_history ORDER BY used_at DESC").fetchall()
        for row in old[50:]:
            conn.execute("DELETE FROM rename_history WHERE id=?", (row["id"],))


def get_rename_history() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT pattern FROM rename_history ORDER BY used_at DESC LIMIT 50").fetchall()
    return [r["pattern"] for r in rows]


def rename_media(mid: str, new_name: str) -> dict:
    media = get_media(mid)
    if not media:
        raise FileNotFoundError("Media not found")
    src = resolve_path(media)
    if not src.exists():
        raise FileNotFoundError(f"File missing: {src}")
    if not new_name.lower().endswith(media["ext"].lower()):
        new_name += media["ext"]
    new_name = sanitize_name(Path(new_name).stem) + media["ext"]
    dst = src.parent / new_name
    if dst.exists() and dst != src:
        raise FileExistsError(f"Already exists: {new_name}")
    src.rename(dst)
    new_rel = str(Path(media["rel_path"]).parent / new_name).replace("\\", "/")
    if new_rel.startswith("./"):
        new_rel = new_rel[2:]
    new_id = media_id(media["dir_id"], new_rel)
    with connect() as conn:
        conn.execute("DELETE FROM media WHERE id=?", (mid,))
        media["id"] = new_id
        media["rel_path"] = new_rel
        media["name"] = new_name
        media["mtime"] = dst.stat().st_mtime
        conn.execute(
            """INSERT INTO media (id, dir_id, rel_path, name, ext, type, size, mtime, tags, notes, thumb_path, pair_id, pair_role, file_tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id, media["dir_id"], new_rel, new_name, media["ext"], media["type"],
                media["size"], media["mtime"], json.dumps(media["tags"]), media["notes"],
                media["thumb_path"], media["pair_id"], media["pair_role"],
                json.dumps(media.get("file_tags", [])),
            ),
        )
        conn.execute("UPDATE pairs SET before_media_id=? WHERE before_media_id=?", (new_id, mid))
        conn.execute("UPDATE pairs SET after_media_id=? WHERE after_media_id=?", (new_id, mid))
    return get_media(new_id) or media


def batch_rename(ids: list[str], pattern: str) -> list[dict]:
    results = []
    for i, mid in enumerate(ids, 1):
        m = get_media(mid)
        if not m:
            continue
        new_name = apply_pattern(pattern, m["name"], m["tags"], i)
        try:
            results.append(rename_media(mid, new_name))
        except Exception as e:
            results.append({"id": mid, "error": str(e), "name": m["name"]})
    push_rename_history(pattern)
    return results


def delete_media(mid: str, to_trash: bool = True) -> dict[str, Any]:
    media = get_media(mid)
    if not media:
        raise FileNotFoundError("Media not found")
    path = resolve_path(media)
    file_path = str(path)
    bytes_freed = 0
    if path.exists():
        bytes_freed = path.stat().st_size
        if to_trash:
            from duplicates import _send_to_recycle_bin
            _send_to_recycle_bin(path)
        else:
            path.unlink()
    thumb = media.get("thumb_path")
    if thumb:
        tp = Path(thumb)
        if tp.exists():
            tp.unlink(missing_ok=True)
    with connect() as conn:
        conn.execute("UPDATE media SET pair_id=NULL, pair_role=NULL WHERE id=?", (mid,))
        conn.execute(
            "DELETE FROM pairs WHERE before_media_id=? OR after_media_id=?",
            (mid, mid),
        )
        conn.execute("DELETE FROM playlist_items WHERE media_id=?", (mid,))
        conn.execute("DELETE FROM media WHERE id=?", (mid,))
    return {"ok": True, "id": mid, "path": file_path, "bytes_freed": bytes_freed, "to_trash": to_trash}


def batch_delete_media(ids: list[str], to_trash: bool = True) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    deleted = 0
    failed = 0
    bytes_freed = 0
    for mid in ids:
        try:
            r = delete_media(mid, to_trash=to_trash)
            results.append(r)
            deleted += 1
            bytes_freed += r.get("bytes_freed", 0)
        except Exception as exc:
            results.append({"ok": False, "id": mid, "error": str(exc)})
            failed += 1
    return {
        "deleted": deleted,
        "failed": failed,
        "bytes_freed": bytes_freed,
        "to_trash": to_trash,
        "results": results,
    }


def update_media_meta(
    mid: str,
    tags: list[str] | None = None,
    notes: str | None = None,
    rank: int | None = None,
    category: str | None = None,
    status: str | None = None,
    write_file_tags: bool = True,
) -> dict:
    """
    Update catalog metadata. By default also writes Tags + Rating into the real
    file (Windows Explorer System.Keywords / System.Rating) so data carries across apps.
    """
    media = get_media(mid)
    if not media:
        raise FileNotFoundError("Not found")
    media.setdefault("rank", 0)
    media.setdefault("category", "")
    media.setdefault("status", "")
    media.setdefault("tags", [])
    media.setdefault("notes", "")
    if tags is not None:
        media["tags"] = list(tags)
    if notes is not None:
        media["notes"] = notes
    if rank is not None:
        try:
            media["rank"] = max(0, min(5, int(rank)))
        except (TypeError, ValueError):
            media["rank"] = 0
    if category is not None:
        media["category"] = str(category).strip()
    if status is not None:
        media["status"] = str(status).strip()
    with connect() as conn:
        conn.execute(
            "UPDATE media SET tags=?, notes=?, rank=?, category=?, status=? WHERE id=?",
            (
                json.dumps(media["tags"]),
                media["notes"],
                media["rank"],
                media["category"],
                media["status"],
                mid,
            ),
        )

    # Always push tags/rating to the file unless explicitly disabled
    file_write: dict | None = None
    if write_file_tags and (tags is not None or rank is not None):
        path = resolve_path(media)
        write_tags = media["tags"] if tags is not None else None
        # When only rank changes, still write current tags + new rank
        if tags is None and rank is not None:
            write_tags = media["tags"]
        write_rank = media["rank"] if rank is not None else (media["rank"] if tags is not None else None)
        # If tags changed but rank not in this call, still re-write rating so both stay in sync
        if tags is not None and rank is None:
            write_rank = media.get("rank") or 0
        try:
            from library_extras import write_meta_with_sidecar
            file_write = write_meta_with_sidecar(
                path,
                tags=write_tags,
                rating=write_rank,
                pair_code=extract_pair_code_from_tags(media.get("tags") or []),
                pair_role=media.get("pair_role"),
            )
            if tags is not None:
                with connect() as conn:
                    conn.execute(
                        "UPDATE media SET file_tags=? WHERE id=?",
                        (json.dumps(media["tags"]), mid),
                    )
        except Exception as e:
            file_write = {"ok": False, "errors": [str(e)]}

    out = get_media(mid) or media
    if file_write is not None:
        out = dict(out)
        out["file_write"] = file_write
    return out


def batch_update_meta(
    ids: list[str],
    rank: int | None = None,
    category: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    write_file_tags: bool = True,
) -> int:
    n = 0
    for mid in ids:
        m = get_media(mid)
        if not m:
            continue
        new_tags = m["tags"]
        if tags is not None:
            new_tags = sorted(set(m["tags"] + [t.strip() for t in tags if t.strip()]))
        update_media_meta(
            mid,
            tags=new_tags if tags is not None else None,
            rank=rank,
            category=category,
            status=status,
            write_file_tags=write_file_tags,
        )
        n += 1
    return n


def batch_add_tags(ids: list[str], new_tags: list[str], write_file_tags: bool = True) -> int:
    n = 0
    for mid in ids:
        m = get_media(mid)
        if not m:
            continue
        merged = sorted(set(m["tags"] + [t.strip() for t in new_tags if t.strip()]))
        update_media_meta(mid, tags=merged, write_file_tags=write_file_tags)
        n += 1
    return n


def find_media_by_identity(
    name: str,
    size: int | None = None,
    mtime: int | float | None = None,
) -> dict | None:
    """Locate a catalog entry by filename (+ optional size / mtime)."""
    name = (name or "").strip()
    if not name:
        return None
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM media WHERE name = ? COLLATE NOCASE",
            (name,),
        ).fetchall()
    if not rows:
        return None
    candidates = [row_to_media(r) for r in rows]
    if size is not None:
        sized = [c for c in candidates if int(c.get("size") or 0) == int(size)]
        if sized:
            candidates = sized
    if mtime is not None and len(candidates) > 1:
        # mtime may be seconds or ms
        mt = float(mtime)
        if mt > 1e12:
            mt = mt / 1000.0
        best = min(candidates, key=lambda c: abs(float(c.get("mtime") or 0) - mt))
        return best
    return candidates[0] if candidates else None


def write_metadata_for_path(
    path: str | Path,
    tags: list[str] | None = None,
    rating: int | None = None,
    update_catalog: bool = True,
) -> dict:
    """
    Write Explorer metadata to an absolute path. Optionally sync matching catalog row.
    """
    p = Path(path)
    from file_metadata import write_file_metadata
    res = write_file_metadata(p, tags=tags, rating=rating)
    catalog = None
    if update_catalog and p.is_file():
        m = find_media_by_identity(p.name, p.stat().st_size, p.stat().st_mtime)
        if m:
            update_media_meta(
                m["id"],
                tags=tags if tags is not None else None,
                rank=rating if rating is not None else None,
                write_file_tags=False,  # already wrote
            )
            if tags is not None:
                with connect() as conn:
                    conn.execute(
                        "UPDATE media SET file_tags=? WHERE id=?",
                        (json.dumps(tags), m["id"]),
                    )
            catalog = get_media(m["id"])
    res["catalog"] = catalog
    return res


def read_embedded_tags(path: Path) -> list[str]:
    """Read Explorer-visible + embedded tags from a real file."""
    try:
        from file_metadata import read_file_metadata
        meta = read_file_metadata(path)
        tags = meta.get("tags") or []
        if tags:
            return list(tags)
    except Exception:
        pass
    try:
        from mutagen.mp4 import MP4
        if path.suffix.lower() in (".mp4", ".m4v", ".mov"):
            mp4 = MP4(path)
            raw = (mp4.tags or {}).get("\xa9cmt") or (mp4.tags or {}).get("\xa9tag") or []
            if isinstance(raw, list):
                out: list[str] = []
                for x in raw:
                    for part in str(x).split(";"):
                        part = part.strip()
                        if part:
                            out.append(part)
                return out
            return [str(raw)] if raw else []
    except Exception:
        pass
    return []


def write_embedded_tags(path: Path, tags: list[str], rating: int | None = None) -> bool:
    """
    Write tags (and optional 0–5 rating) into the real file so Windows Explorer
    and other apps can see them. Uses System.Keywords / System.Rating when possible.
    """
    try:
        from file_metadata import write_file_metadata
        res = write_file_metadata(path, tags=tags, rating=rating)
        return bool(res.get("ok"))
    except Exception:
        return False


def capture_thumbnail(mid: str, timestamp: float = 0, sidecar: bool = True, sidecar_ext: str = ".thumb.jpg") -> dict:
    media = get_media(mid)
    if not media or media["type"] != "video":
        raise ValueError("Video required")
    src = resolve_path(media)
    out = THUMB_DIR / f"{mid.replace('::', '__')}.jpg"
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        subprocess.run(
            [ffmpeg, "-y", "-ss", str(timestamp), "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)],
            check=True, capture_output=True, timeout=60,
        )
    else:
        raise RuntimeError("ffmpeg not found — install ffmpeg and add to PATH")
    sidecar_path = None
    if sidecar:
        sidecar_path = src.parent / (Path(media["name"]).stem + sidecar_ext)
        shutil.copy2(out, sidecar_path)
    with connect() as conn:
        conn.execute("UPDATE media SET thumb_path=? WHERE id=?", (str(out), mid))
    return {"thumb_path": str(out), "sidecar": str(sidecar_path) if sidecar_path else None, "url": f"/api/thumb/{mid}"}


# --- Pairs ---
UPSCALE_MARKERS = (
    "_upscaled", "_upscale", "_vsr", "_flash", "_enhanced", "_4k", "_hd",
    "_interp", "_out", "scaled_", "x4_", "x2_", "_chunked",
)


def _next_pair_code() -> str:
    with connect() as conn:
        rows = conn.execute(
            "SELECT pair_code FROM pairs WHERE pair_code LIKE 'UP-%' ORDER BY pair_code DESC LIMIT 1"
        ).fetchall()
    if rows and rows[0]["pair_code"]:
        try:
            n = int(str(rows[0]["pair_code"]).split("-", 1)[1])
            return f"UP-{n + 1:04d}"
        except (ValueError, IndexError):
            pass
    return "UP-0001"


def _is_upscaled_name(name: str) -> bool:
    low = name.lower()
    return any(m in low for m in UPSCALE_MARKERS)


def _pair_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    for suffix in UPSCALE_MARKERS:
        idx = stem.find(suffix)
        if idx > 0:
            stem = stem[:idx]
    # strip trailing resolution / fps crumbs that break pairing
    stem = re.sub(r"([_\-.]?)(\d{3,4}x\d{3,4}|\d{2,3}fps|uhd|fhd|qhd|4k|8k|2160p|1440p|1080p|720p)$", "", stem)
    return stem.rstrip("._- ")


def _alnum_compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _tail_key(name: str, n: int = 5) -> str:
    """Last N alphanumeric chars of normalized stem — looser unique-id style match."""
    compact = _alnum_compact(_pair_stem(name))
    if len(compact) < 3:
        return ""
    n = max(3, min(12, int(n or 5)))
    if len(compact) <= n:
        return compact
    return compact[-n:]


def _digit_ids(name: str) -> list[str]:
    """Long digit runs often act as stable ids when prefixes differ."""
    return re.findall(r"\d{4,}", Path(name or "").stem)


def _parent_folder_hint(m: dict) -> str:
    rel = (m.get("relative_path") or m.get("rel_path") or m.get("path") or "").replace("\\", "/")
    parts = [p for p in rel.split("/") if p]
    if len(parts) >= 2:
        return parts[-2].lower()
    return ""


def _enrich_pair(row: dict | None) -> dict | None:
    if not row:
        return None
    pair = dict(row)
    pair["pinned"] = bool(pair.get("pinned"))
    before = get_media(pair.get("before_media_id") or "")
    after = get_media(pair.get("after_media_id") or "")
    pair["before_name"] = before["name"] if before else Path(pair.get("before_path") or "").name
    pair["after_name"] = after["name"] if after else Path(pair.get("after_path") or "").name
    if before and not pair.get("before_path"):
        try:
            pair["before_path"] = str(resolve_path(before))
        except FileNotFoundError:
            pass
    if after and not pair.get("after_path"):
        try:
            pair["after_path"] = str(resolve_path(after))
        except FileNotFoundError:
            pass
    return pair


def find_media_by_name(name: str, size: int | None = None) -> dict | None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM media WHERE name=? ORDER BY mtime DESC LIMIT 20",
            (name,),
        ).fetchall()
    items = [row_to_media(r) for r in rows]
    if not items:
        return None
    if size is not None:
        for m in items:
            if m.get("size") == size:
                return m
    return items[0]


def list_pairs(kind: str | None = None, pinned_only: bool = False) -> list[dict]:
    backfill_pair_codes()
    clauses: list[str] = []
    params: list[Any] = []
    if kind:
        clauses.append("kind=?")
        params.append(kind)
    if pinned_only:
        clauses.append("pinned=1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM pairs {where} ORDER BY pinned DESC, created_at DESC",
            params,
        ).fetchall()
    return [p for r in rows if (p := _enrich_pair(dict(r)))]


# Role tags applied per side when a pair is created — not copied across as "shared" project tags
PAIR_ROLE_TAGS = frozenset({
    "source", "before", "after", "upscaled", "vsr",
    "original-video", "original-image",
    "upscaled-video", "upscaled-image", "image",
})


def _pair_tags_for_media(pair_code: str, role: str, kind: str) -> list[str]:
    tags = [pair_code]
    if role == "before":
        tags.extend(["source", "before"])
        tags.append("original-image" if kind == "image" else "original-video")
    else:
        tags.extend(["upscaled", "after"])
        if kind == "image":
            tags.extend(["image", "upscaled-image"])
        else:
            tags.extend(["vsr", "upscaled-video"])
    return sorted({t.strip() for t in tags if t and str(t).strip()})


def _is_pair_code_tag(tag: str) -> bool:
    t = (tag or "").strip()
    return bool(re.match(r"^UP-\d+$", t, re.I)) or bool(re.match(r"^PAIR-", t, re.I))


def shared_tags_only(tags: list[str] | None) -> list[str]:
    """Strip role-only tags so project keywords can be applied to both pair sides."""
    out: list[str] = []
    seen: set[str] = set()
    for t in tags or []:
        s = str(t).strip()
        if not s:
            continue
        low = s.lower()
        if low in PAIR_ROLE_TAGS:
            continue
        # Keep UP-#### on both (shared identity); still allow through as shared
        if low in seen:
            continue
        seen.add(low)
        out.append(s)
    return out


def _tag_linked_media(
    before_id: str | None,
    after_id: str | None,
    pair_code: str,
    kind: str,
) -> None:
    """Apply role tags + pair code to each side; writes into real files by default."""
    if not pair_code:
        return
    if before_id:
        batch_add_tags([before_id], _pair_tags_for_media(pair_code, "before", kind), write_file_tags=True)
    if after_id:
        batch_add_tags([after_id], _pair_tags_for_media(pair_code, "after", kind), write_file_tags=True)


def get_pair_partner_id(media_id: str) -> str | None:
    """Return the other media id in a locked pair, if any."""
    m = get_media(media_id)
    if not m:
        return None
    pid = m.get("pair_id") or m.get("pairId")
    if not pid:
        return None
    pair = get_pair(pid)
    if not pair:
        return None
    before = pair.get("before_media_id")
    after = pair.get("after_media_id")
    if media_id == before:
        return after
    if media_id == after:
        return before
    return None


def tag_both_in_pair(
    pair_id: str,
    tags: list[str],
    *,
    write_file_tags: bool = True,
    rank: int | None = None,
    shared_only: bool = True,
) -> dict:
    """
    Add tags (and optional rank) to BOTH files in a pair.
    By default strips role-only tags so you don't mark the source as 'upscaled'.
    Always keeps/applies pair code style tags if present in the list.
    """
    pair = get_pair(pair_id)
    if not pair:
        raise FileNotFoundError("Pair not found")
    to_add = shared_tags_only(tags) if shared_only else [t.strip() for t in (tags or []) if t and str(t).strip()]
    ids = [i for i in (pair.get("before_media_id"), pair.get("after_media_id")) if i]
    updated = 0
    results = []
    for mid in ids:
        if to_add:
            batch_add_tags([mid], to_add, write_file_tags=write_file_tags)
        if rank is not None:
            update_media_meta(mid, rank=rank, write_file_tags=write_file_tags)
        updated += 1
        results.append(get_media(mid))
    return {
        "ok": True,
        "pair_id": pair_id,
        "pair_code": pair.get("pair_code"),
        "tags_applied": to_add,
        "rank": rank,
        "updated": updated,
        "items": results,
    }


def tag_media_and_pair_partner(
    media_id: str,
    tags: list[str] | None = None,
    *,
    notes: str | None = None,
    rank: int | None = None,
    write_file_tags: bool = True,
    tag_partner: bool = True,
    shared_only_on_partner: bool = True,
) -> dict:
    """
    Update this media item; if it belongs to a pair and tag_partner=True,
    also add shared tags (and optional rank) to the partner file.
    """
    primary = update_media_meta(
        media_id,
        tags=tags,
        notes=notes,
        rank=rank,
        write_file_tags=write_file_tags,
    )
    partner_result = None
    partner_id = get_pair_partner_id(media_id) if tag_partner else None
    if partner_id and (tags is not None or rank is not None):
        partner_tags = shared_tags_only(tags) if (tags is not None and shared_only_on_partner) else tags
        if tags is not None and partner_tags is not None:
            # Merge onto partner (don't wipe partner's role tags)
            batch_add_tags([partner_id], partner_tags, write_file_tags=write_file_tags)
        if rank is not None:
            update_media_meta(partner_id, rank=rank, write_file_tags=write_file_tags)
        partner_result = get_media(partner_id)
    return {
        "media": primary,
        "partner": partner_result,
        "partner_id": partner_id,
        "tagged_partner": partner_result is not None,
    }


def save_pair(
    name: str,
    before_id: str,
    after_id: str,
    kind: str = "video",
    *,
    pinned: bool = False,
    notes: str = "",
    source: str = "manual",
    pair_code: str | None = None,
) -> dict:
    before = get_media(before_id)
    after = get_media(after_id)
    if not before or not after:
        raise FileNotFoundError("Media items not found")
    pid = f"pair-{uuid.uuid4().hex[:10]}"
    if not name:
        name = f"{before['name']} ↔ {after['name']}"
    code = pair_code or _next_pair_code()
    before_path = str(resolve_path(before))
    after_path = str(resolve_path(after))
    with connect() as conn:
        conn.execute(
            """INSERT INTO pairs (
                id, name, kind, before_media_id, after_media_id, created_at,
                pair_code, pinned, notes, before_path, after_path, source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                pid, name, kind, before_id, after_id, time.time(),
                code, 1 if pinned else 0, notes, before_path, after_path, source,
            ),
        )
        conn.execute("UPDATE media SET pair_id=?, pair_role='before' WHERE id=?", (pid, before_id))
        conn.execute("UPDATE media SET pair_id=?, pair_role='after' WHERE id=?", (pid, after_id))
        row = conn.execute("SELECT * FROM pairs WHERE id=?", (pid,)).fetchone()
    enriched = _enrich_pair(dict(row)) or {}
    _tag_linked_media(before_id, after_id, code, kind)
    return enriched


def save_pair_from_paths(
    before_path: str,
    after_path: str,
    name: str = "",
    kind: str = "video",
    *,
    pinned: bool = True,
    notes: str = "",
    source: str = "manual",
) -> dict:
    bp = Path(before_path).resolve()
    ap = Path(after_path).resolve()
    if not bp.is_file() or not ap.is_file():
        raise FileNotFoundError("Before and after files must exist on disk")
    before_m = find_media_by_name(bp.name, bp.stat().st_size)
    after_m = find_media_by_name(ap.name, ap.stat().st_size)
    if before_m and after_m:
        return save_pair(
            name or f"{bp.name} ↔ {ap.name}",
            before_m["id"],
            after_m["id"],
            kind,
            pinned=pinned,
            notes=notes,
            source=source,
        )
    pid = f"pair-{uuid.uuid4().hex[:10]}"
    code = _next_pair_code()
    display = name or f"{bp.name} ↔ {ap.name}"
    with connect() as conn:
        conn.execute(
            """INSERT INTO pairs (
                id, name, kind, before_media_id, after_media_id, created_at,
                pair_code, pinned, notes, before_path, after_path, source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                pid, display, kind,
                before_m["id"] if before_m else None,
                after_m["id"] if after_m else None,
                time.time(),
                code, 1 if pinned else 0, notes, str(bp), str(ap), source,
            ),
        )
        if before_m:
            conn.execute("UPDATE media SET pair_id=?, pair_role='before' WHERE id=?", (pid, before_m["id"]))
        if after_m:
            conn.execute("UPDATE media SET pair_id=?, pair_role='after' WHERE id=?", (pid, after_m["id"]))
        row = conn.execute("SELECT * FROM pairs WHERE id=?", (pid,)).fetchone()
    enriched = _enrich_pair(dict(row)) or {}
    _tag_linked_media(
        before_m["id"] if before_m else None,
        after_m["id"] if after_m else None,
        code,
        kind,
    )
    return enriched


def update_pair_meta(
    pid: str,
    *,
    name: str | None = None,
    pinned: bool | None = None,
    notes: str | None = None,
) -> dict:
    pair = get_pair(pid)
    if not pair:
        raise FileNotFoundError("Pair not found")
    if name is not None:
        pair["name"] = name.strip() or pair["name"]
    if pinned is not None:
        pair["pinned"] = 1 if pinned else 0
    if notes is not None:
        pair["notes"] = notes
    with connect() as conn:
        conn.execute(
            "UPDATE pairs SET name=?, pinned=?, notes=? WHERE id=?",
            (pair["name"], pair["pinned"], pair.get("notes", ""), pid),
        )
    return get_pair(pid) or pair


def get_pair(pid: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM pairs WHERE id=?", (pid,)).fetchone()
    return _enrich_pair(dict(row)) if row else None


def get_pair_by_code(code: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM pairs WHERE pair_code=? COLLATE NOCASE",
            (code.strip().upper(),),
        ).fetchone()
    return _enrich_pair(dict(row)) if row else None


def extract_pair_code_from_tags(tags: list | None) -> str | None:
    """Find UP-#### (or similar) pair code in a tag list."""
    for t in tags or []:
        s = str(t).strip()
        m = re.match(r"^(UP-\d+)$", s, re.I)
        if m:
            # Normalize UP-12 → UP-0012 when short; keep zero-padded codes as-is if already 4+
            raw = m.group(1).upper()
            try:
                n = int(raw.split("-", 1)[1])
                return f"UP-{n:04d}"
            except ValueError:
                return raw
    return None


def infer_pair_role_from_tags(tags: list | None, filename: str = "") -> str | None:
    """before | after | None from role tags or filename heuristics."""
    tagset = {str(t).strip().lower() for t in (tags or []) if t}
    before_marks = {"source", "before", "original-video", "original-image"}
    after_marks = {"upscaled", "after", "vsr", "upscaled-video", "upscaled-image"}
    if tagset & before_marks and not (tagset & after_marks):
        return "before"
    if tagset & after_marks and not (tagset & before_marks):
        return "after"
    if tagset & before_marks and tagset & after_marks:
        # Prefer filename if both present (messy tags)
        return "after" if _is_upscaled_name(filename) else "before"
    if filename:
        return "after" if _is_upscaled_name(filename) else "before"
    return None


def relink_pairs_from_metadata() -> dict:
    """
    Rebuild catalog pair links from durable file/catalog tags (UP-#### + role).

    Why: media ids are path-based (`dir_id::rel_path`). Moving a file to another
    folder changes its media id, which would break pairs that only store media ids.
    Pair codes written into System.Keywords / tags travel with the file, so after a
    move + rescan we can reattach before/after even across directories.
    """
    with connect() as conn:
        rows = conn.execute("SELECT * FROM media").fetchall()
    items = [row_to_media(r) for r in rows]

    by_code: dict[str, dict[str, dict | None]] = {}
    for m in items:
        tags = list(m.get("tags") or [])
        # Merge lightweight .fafo.json sidecar only (avoid slow shell prop reads in bulk)
        try:
            from library_extras import read_sidecar
            p = resolve_path(m)
            side = read_sidecar(p) or {}
            for t in side.get("tags") or []:
                if t not in tags:
                    tags.append(t)
            code = extract_pair_code_from_tags(tags) or side.get("pair_code")
            role = side.get("pair_role") or infer_pair_role_from_tags(tags, m.get("name") or "")
        except Exception:
            code = extract_pair_code_from_tags(tags)
            role = infer_pair_role_from_tags(tags, m.get("name") or "")
        if not code:
            continue
        if role not in ("before", "after"):
            continue
        bucket = by_code.setdefault(code, {"before": None, "after": None})
        # Prefer first solid match; don't overwrite if already set unless same file
        prev = bucket.get(role)
        if prev is None or prev.get("id") == m["id"]:
            bucket[role] = m

    created = 0
    updated = 0
    partial = 0
    linked_media = 0

    for code, sides in by_code.items():
        before = sides.get("before")
        after = sides.get("after")
        if not before and not after:
            continue

        existing = get_pair_by_code(code)
        kind = "video"
        if (before and before.get("type") == "image") and (not after or after.get("type") == "image"):
            kind = "image"
        if (after and after.get("type") == "image") and (not before or before.get("type") == "image"):
            if not before or before.get("type") == "image":
                kind = "image"

        before_id = before["id"] if before else None
        after_id = after["id"] if after else None
        # Keep previous partner id if only one side rediscovered this scan
        if existing:
            if not before_id:
                before_id = existing.get("before_media_id")
                # Drop stale id if media row gone
                if before_id and not get_media(before_id):
                    before_id = None
            if not after_id:
                after_id = existing.get("after_media_id")
                if after_id and not get_media(after_id):
                    after_id = None

        def _path_for(media_row: dict | None, fallback: str = "") -> str:
            if not media_row:
                return fallback or ""
            try:
                return str(resolve_path(media_row))
            except Exception:
                return fallback or ""

        before_path = _path_for(before, (existing or {}).get("before_path") or "")
        after_path = _path_for(after, (existing or {}).get("after_path") or "")

        if existing:
            pid = existing["id"]
            with connect() as conn:
                conn.execute(
                    """UPDATE pairs SET
                        before_media_id=?, after_media_id=?,
                        before_path=?, after_path=?, kind=?
                       WHERE id=?""",
                    (before_id, after_id, before_path, after_path, kind, pid),
                )
                # Detach media that no longer belong to this pair
                keep = [i for i in (before_id, after_id) if i]
                if keep:
                    placeholders = ",".join("?" * len(keep))
                    conn.execute(
                        f"UPDATE media SET pair_id=NULL, pair_role=NULL "
                        f"WHERE pair_id=? AND id NOT IN ({placeholders})",
                        [pid, *keep],
                    )
                else:
                    conn.execute(
                        "UPDATE media SET pair_id=NULL, pair_role=NULL WHERE pair_id=?",
                        (pid,),
                    )
                if before_id:
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='before' WHERE id=?",
                        (pid, before_id),
                    )
                    linked_media += 1
                if after_id:
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='after' WHERE id=?",
                        (pid, after_id),
                    )
                    linked_media += 1
            updated += 1
            if not (before_id and after_id):
                partial += 1
        else:
            # Create a new pair row preserving the code from tags
            if not before_id and not after_id:
                continue
            pid = f"pair-{uuid.uuid4().hex[:10]}"
            name_parts = []
            if before:
                name_parts.append(before["name"])
            if after:
                name_parts.append(after["name"])
            name = " ↔ ".join(name_parts) if name_parts else code
            with connect() as conn:
                conn.execute(
                    """INSERT INTO pairs (
                        id, name, kind, before_media_id, after_media_id, created_at,
                        pair_code, pinned, notes, before_path, after_path, source
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, name, kind, before_id, after_id, time.time(),
                        code, 1, "relinked-from-file-tags", before_path, after_path, "relink",
                    ),
                )
                if before_id:
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='before' WHERE id=?",
                        (pid, before_id),
                    )
                    linked_media += 1
                if after_id:
                    conn.execute(
                        "UPDATE media SET pair_id=?, pair_role='after' WHERE id=?",
                        (pid, after_id),
                    )
                    linked_media += 1
            created += 1
            if not (before_id and after_id):
                partial += 1

    return {
        "ok": True,
        "codes_seen": len(by_code),
        "pairs_created": created,
        "pairs_updated": updated,
        "partial_pairs": partial,
        "media_linked": linked_media,
    }


def delete_pair(pid: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE media SET pair_id=NULL, pair_role=NULL WHERE pair_id=?", (pid,))
        conn.execute("DELETE FROM pairs WHERE id=?", (pid,))


def pair_file_paths(pid: str) -> dict[str, str]:
    pair = get_pair(pid)
    if not pair:
        raise FileNotFoundError("Pair not found")
    before = get_media(pair["before_media_id"])
    after = get_media(pair["after_media_id"])
    if not before or not after:
        raise FileNotFoundError("Pair media missing")
    return {"before": str(resolve_path(before)), "after": str(resolve_path(after)), "pair": pair}


def _pick_before_after(a: dict, b: dict) -> tuple[dict, dict, float]:
    a_up = _is_upscaled_name(a["name"])
    b_up = _is_upscaled_name(b["name"])
    if a_up != b_up:
        return (b, a, 0.95) if a_up else (a, b, 0.95)
    sa, sb = int(a.get("size") or 0), int(b.get("size") or 0)
    if sa != sb and sa > 0 and sb > 0:
        return (a, b, 0.85) if sa <= sb else (b, a, 0.85)
    ratio = SequenceMatcher(None, a["name"].lower(), b["name"].lower()).ratio()
    return (a, b, ratio)


def _pair_confidence(a: dict, b: dict, *, method: str, tail_len: int = 5) -> tuple[dict, dict, float, str]:
    """Score two media rows; returns ordered (before, after, conf, reason)."""
    before, after, base = _pick_before_after(a, b)
    a_stem = _pair_stem(before["name"])
    b_stem = _pair_stem(after["name"])
    a_tail = _tail_key(before["name"], tail_len)
    b_tail = _tail_key(after["name"], tail_len)
    name_r = SequenceMatcher(None, before["name"].lower(), after["name"].lower()).ratio()
    stem_r = SequenceMatcher(None, a_stem, b_stem).ratio() if a_stem and b_stem else 0.0
    conf = base
    reason = method

    if method == "stem":
        conf = max(base, 0.92 if a_stem and a_stem == b_stem else stem_r)
        reason = "upscale_suffix" if _is_upscaled_name(after["name"]) else "stem_exact"
    elif method == "tail":
        # Same trailing unique chunk (e.g. last 5 alnum) — more hits when prefixes differ
        conf = 0.72
        if a_tail and a_tail == b_tail:
            conf = 0.78 + min(0.12, len(a_tail) * 0.01)
        conf = max(conf, stem_r * 0.85, name_r * 0.7)
        if _is_upscaled_name(after["name"]) and not _is_upscaled_name(before["name"]):
            conf = min(1.0, conf + 0.06)
        reason = f"tail_{tail_len}"
    elif method == "digit_id":
        conf = 0.74
        if _is_upscaled_name(after["name"]) and not _is_upscaled_name(before["name"]):
            conf = min(1.0, conf + 0.08)
        conf = max(conf, stem_r * 0.8)
        reason = "digit_id"
    elif method == "folder":
        conf = max(0.6, stem_r * 0.9, name_r * 0.75)
        if _is_upscaled_name(after["name"]) and not _is_upscaled_name(before["name"]):
            conf = min(1.0, conf + 0.05)
        reason = "same_folder_fuzzy"
    elif method == "fuzzy":
        conf = max(stem_r, name_r * 0.92)
        if _is_upscaled_name(after["name"]) and not _is_upscaled_name(before["name"]):
            conf = min(1.0, conf + 0.05)
        # Size cue: larger file often after/upscale
        sa, sb = int(before.get("size") or 0), int(after.get("size") or 0)
        if sa > 0 and sb > sa * 1.05:
            conf = min(1.0, conf + 0.03)
        reason = "fuzzy_name"
    else:
        conf = max(base, stem_r)
        reason = method or "name_match"

    # Type mismatch heavily discouraged
    if before.get("type") and after.get("type") and before["type"] != after["type"]:
        conf *= 0.4

    return before, after, float(min(1.0, conf)), reason


def _append_suggestion(
    suggestions: list[dict],
    seen: set[frozenset[str]],
    before: dict,
    after: dict,
    conf: float,
    reason: str,
    stem: str,
    min_ratio: float,
) -> bool:
    if conf < min_ratio or before["id"] == after["id"]:
        return False
    key = frozenset((before["id"], after["id"]))
    if key in seen:
        # Keep higher confidence if duplicate method finds same pair
        for s in suggestions:
            if frozenset((s["before_id"], s["after_id"])) == key:
                if conf > s["confidence"]:
                    s["confidence"] = round(conf, 2)
                    s["reason"] = reason
                    s["stem"] = stem
                return False
        return False
    seen.add(key)
    suggestions.append({
        "before_id": before["id"],
        "after_id": after["id"],
        "before_name": before["name"],
        "after_name": after["name"],
        "before_dir_id": before.get("dir_id"),
        "after_dir_id": after.get("dir_id"),
        "confidence": round(conf, 2),
        "stem": stem,
        "reason": reason,
        "tail": _tail_key(before["name"]),
    })
    return True


def suggest_pairs(
    min_ratio: float = 0.55,
    limit: int = 30,
    media_type: str | None = None,
    before_dir_id: str | None = None,
    after_dir_id: str | None = None,
    unpaired_only: bool = True,
    tail_len: int = 5,
    use_tail: bool = True,
    use_digits: bool = True,
    use_fuzzy: bool = True,
    use_folder: bool = True,
) -> list[dict]:
    """
    Suggest before/after pairs using multiple signals:
    - exact normalized stem
    - trailing unique-id chunk (last N alnum chars — more hits when prefixes differ)
    - shared long digit runs
    - same parent folder + fuzzy stem
    - general fuzzy name (capped)

    Two-folder mode: when before_dir_id and after_dir_id differ, only match across those dirs.
    """
    tail_len = max(3, min(12, int(tail_len or 5)))
    clauses: list[str] = []
    params: list[Any] = []
    if unpaired_only:
        clauses.append("pair_id IS NULL")
    if media_type in ("video", "image"):
        clauses.append("type=?")
        params.append(media_type)
    else:
        clauses.append("type IN ('video', 'image')")
    where = " AND ".join(clauses) if clauses else "1=1"
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM media WHERE {where}", params).fetchall()
    items = [row_to_media(r) for r in rows]

    # --- Two watched folders: Before dir × After dir ---
    if before_dir_id and after_dir_id:
        before_items = [m for m in items if m.get("dir_id") == before_dir_id]
        after_items = [m for m in items if m.get("dir_id") == after_dir_id]
        if before_dir_id == after_dir_id:
            items = before_items
        else:
            return _suggest_pairs_cross_dirs(
                before_items,
                after_items,
                min_ratio=min_ratio,
                limit=limit,
                tail_len=tail_len,
                use_tail=use_tail,
                use_digits=use_digits,
                use_fuzzy=use_fuzzy,
            )

    return _suggest_pairs_multi(
        items,
        min_ratio=min_ratio,
        limit=limit,
        tail_len=tail_len,
        use_tail=use_tail,
        use_digits=use_digits,
        use_fuzzy=use_fuzzy,
        use_folder=use_folder,
    )


def _suggest_pairs_multi(
    items: list[dict],
    *,
    min_ratio: float,
    limit: int,
    tail_len: int,
    use_tail: bool,
    use_digits: bool,
    use_fuzzy: bool,
    use_folder: bool,
) -> list[dict]:
    suggestions: list[dict] = []
    seen: set[frozenset[str]] = set()

    # Pass 1: exact normalized stem
    stems: dict[str, list[dict]] = {}
    for m in items:
        stems.setdefault(_pair_stem(m["name"]), []).append(m)
    for stem, group in stems.items():
        if len(group) < 2 or not stem:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                before, after, conf, reason = _pair_confidence(
                    group[i], group[j], method="stem", tail_len=tail_len
                )
                _append_suggestion(suggestions, seen, before, after, conf, reason, stem, min_ratio)

    # Pass 2: tail key (last N alnum) — looser unique id
    if use_tail:
        tails: dict[str, list[dict]] = {}
        for m in items:
            t = _tail_key(m["name"], tail_len)
            if t:
                tails.setdefault(t, []).append(m)
        for tkey, group in tails.items():
            if len(group) < 2 or len(group) > 40:
                # huge buckets are noise (e.g. "00000")
                continue
            for i in range(len(group)):
                for j in range(i + 1, min(len(group), i + 12)):
                    before, after, conf, reason = _pair_confidence(
                        group[i], group[j], method="tail", tail_len=tail_len
                    )
                    _append_suggestion(
                        suggestions, seen, before, after, conf, reason, tkey, min_ratio
                    )

    # Pass 3: shared long digit ids
    if use_digits:
        by_digit: dict[str, list[dict]] = {}
        for m in items:
            for dig in _digit_ids(m["name"]):
                by_digit.setdefault(dig, []).append(m)
        for dig, group in by_digit.items():
            # de-dupe media that list same id twice
            uniq: dict[str, dict] = {m["id"]: m for m in group}
            group = list(uniq.values())
            if len(group) < 2 or len(group) > 30:
                continue
            for i in range(len(group)):
                for j in range(i + 1, min(len(group), i + 10)):
                    before, after, conf, reason = _pair_confidence(
                        group[i], group[j], method="digit_id", tail_len=tail_len
                    )
                    _append_suggestion(
                        suggestions, seen, before, after, conf, reason, dig, min_ratio
                    )

    # Pass 4: same parent folder + fuzzy stem (handles mixed naming in one batch folder)
    if use_folder:
        by_folder: dict[str, list[dict]] = {}
        for m in items:
            folder = _parent_folder_hint(m) or m.get("dir_id") or ""
            if folder:
                by_folder.setdefault(str(folder), []).append(m)
        for folder, group in by_folder.items():
            if len(group) < 2 or len(group) > 80:
                continue
            # Prefer pairing upscaled names with non-upscaled in same folder
            plain = [m for m in group if not _is_upscaled_name(m["name"])]
            up = [m for m in group if _is_upscaled_name(m["name"])]
            if plain and up:
                for b in plain:
                    best = None
                    best_conf = 0.0
                    best_reason = "folder"
                    for a in up:
                        before, after, conf, reason = _pair_confidence(
                            b, a, method="folder", tail_len=tail_len
                        )
                        if conf > best_conf:
                            best_conf, best, best_reason = conf, (before, after), reason
                    if best and best_conf >= min_ratio:
                        _append_suggestion(
                            suggestions, seen, best[0], best[1], best_conf, best_reason,
                            _pair_stem(best[0]["name"]), min_ratio,
                        )

    # Pass 5: capped fuzzy among remaining high-signal unpaired (expensive)
    if use_fuzzy and len(items) <= 400:
        # Only try items not yet used as before or after
        used_ids = {s["before_id"] for s in suggestions} | {s["after_id"] for s in suggestions}
        remain = [m for m in items if m["id"] not in used_ids]
        # Bias: try plain × upscaled only
        plain = [m for m in remain if not _is_upscaled_name(m["name"])]
        up = [m for m in remain if _is_upscaled_name(m["name"])]
        if plain and up:
            for b in plain[:120]:
                best = None
                best_conf = 0.0
                for a in up[:200]:
                    before, after, conf, reason = _pair_confidence(
                        b, a, method="fuzzy", tail_len=tail_len
                    )
                    if conf > best_conf:
                        best_conf, best = conf, (before, after, reason)
                if best and best_conf >= max(min_ratio, 0.62):
                    _append_suggestion(
                        suggestions, seen, best[0], best[1], best_conf, best[2],
                        _pair_stem(best[0]["name"]), min_ratio,
                    )

    suggestions.sort(key=lambda x: (-x["confidence"], x.get("stem") or ""))
    return suggestions[:limit]


def _suggest_pairs_cross_dirs(
    before_items: list[dict],
    after_items: list[dict],
    *,
    min_ratio: float,
    limit: int,
    tail_len: int = 5,
    use_tail: bool = True,
    use_digits: bool = True,
    use_fuzzy: bool = True,
) -> list[dict]:
    """Match every Before-folder file to best After-folder candidate(s) with multi-signal passes."""
    if not before_items or not after_items:
        return []

    after_by_stem: dict[str, list[dict]] = {}
    after_by_tail: dict[str, list[dict]] = {}
    after_by_digit: dict[str, list[dict]] = {}
    for a in after_items:
        after_by_stem.setdefault(_pair_stem(a["name"]), []).append(a)
        t = _tail_key(a["name"], tail_len)
        if t:
            after_by_tail.setdefault(t, []).append(a)
        for dig in _digit_ids(a["name"]):
            after_by_digit.setdefault(dig, []).append(a)

    suggestions: list[dict] = []
    used_after: set[str] = set()
    used_before: set[str] = set()

    def try_candidates(b: dict, candidates: list[dict], method: str) -> bool:
        best = None
        best_conf = 0.0
        best_reason = method
        for a in candidates:
            if a["id"] in used_after or a["id"] == b["id"]:
                continue
            before, after, conf, reason = _pair_confidence(b, a, method=method, tail_len=tail_len)
            if conf > best_conf:
                best_conf, best, best_reason = conf, after, reason
        if best and best_conf >= min_ratio:
            used_after.add(best["id"])
            used_before.add(b["id"])
            suggestions.append({
                "before_id": b["id"], "after_id": best["id"],
                "before_name": b["name"], "after_name": best["name"],
                "before_dir_id": b.get("dir_id"),
                "after_dir_id": best.get("dir_id"),
                "confidence": round(best_conf, 2),
                "stem": _pair_stem(b["name"]),
                "reason": best_reason if method == "stem" else f"two_dir_{best_reason}",
                "tail": _tail_key(b["name"], tail_len),
            })
            return True
        return False

    # Pass 1: exact stem
    for b in before_items:
        if b["id"] in used_before:
            continue
        try_candidates(b, after_by_stem.get(_pair_stem(b["name"])) or [], "stem")

    # Pass 2: tail key
    if use_tail:
        for b in before_items:
            if b["id"] in used_before:
                continue
            t = _tail_key(b["name"], tail_len)
            if not t:
                continue
            try_candidates(b, after_by_tail.get(t) or [], "tail")

    # Pass 3: digit ids
    if use_digits:
        for b in before_items:
            if b["id"] in used_before:
                continue
            cands: list[dict] = []
            for dig in _digit_ids(b["name"]):
                cands.extend(after_by_digit.get(dig) or [])
            # unique by id
            uniq = {c["id"]: c for c in cands}
            try_candidates(b, list(uniq.values()), "digit_id")

    # Pass 4: fuzzy remaining
    if use_fuzzy:
        remaining_before = [b for b in before_items if b["id"] not in used_before]
        remaining_after = [a for a in after_items if a["id"] not in used_after]
        for b in remaining_before:
            best = None
            best_conf = 0.0
            best_reason = "fuzzy"
            for a in remaining_after:
                if a["id"] == b["id"]:
                    continue
                before, after, conf, reason = _pair_confidence(
                    b, a, method="fuzzy", tail_len=tail_len
                )
                if conf > best_conf:
                    best_conf, best, best_reason = conf, after, reason
            if best and best_conf >= min_ratio:
                used_after.add(best["id"])
                remaining_after = [a for a in remaining_after if a["id"] != best["id"]]
                suggestions.append({
                    "before_id": b["id"], "after_id": best["id"],
                    "before_name": b["name"], "after_name": best["name"],
                    "before_dir_id": b.get("dir_id"),
                    "after_dir_id": best.get("dir_id"),
                    "confidence": round(best_conf, 2),
                    "stem": _pair_stem(b["name"]),
                    "reason": f"two_dir_{best_reason}",
                    "tail": _tail_key(b["name"], tail_len),
                })

    suggestions.sort(key=lambda x: (-x["confidence"], x.get("stem") or ""))
    return suggestions[:limit]


def auto_pair_upscaled(
    *,
    min_confidence: float = 0.7,
    limit: int = 200,
    dry_run: bool = False,
    pin: bool = True,
    kind: str | None = None,
    before_dir_id: str | None = None,
    after_dir_id: str | None = None,
    require_upscale_name: bool | None = None,
) -> dict[str, Any]:
    media_type = kind if kind in ("video", "image") else None
    two_dir = bool(before_dir_id and after_dir_id and before_dir_id != after_dir_id)
    # Two-folder mode: allow same stem without _upscaled suffix (before vs after dirs)
    if require_upscale_name is None:
        require_upscale_name = not two_dir
    suggestions = suggest_pairs(
        min_ratio=min_confidence,
        limit=limit * 3,
        media_type=media_type,
        before_dir_id=before_dir_id,
        after_dir_id=after_dir_id,
        unpaired_only=True,
    )
    created = []
    skipped = 0
    for s in suggestions:
        if len(created) >= limit:
            break
        if require_upscale_name and not _is_upscaled_name(s["after_name"]):
            skipped += 1
            continue
        if dry_run:
            created.append(s)
            continue
        try:
            before = get_media(s["before_id"])
            pair_kind = (before or {}).get("type") or "video"
            if pair_kind not in ("video", "image"):
                pair_kind = "video"
            stem = _pair_stem(s["before_name"]) or Path(s["before_name"]).stem
            pair = save_pair(
                f"{stem} — before/after",
                s["before_id"],
                s["after_id"],
                pair_kind,
                pinned=pin,
                source="auto-two-dir" if two_dir else "auto-upscale",
            )
            pair["confidence"] = s["confidence"]
            created.append(pair)
        except FileNotFoundError:
            skipped += 1
    return {
        "dry_run": dry_run,
        "created": len(created),
        "skipped": skipped,
        "pairs": created,
        "mode": "two_dir" if two_dir else "global",
        "before_dir_id": before_dir_id,
        "after_dir_id": after_dir_id,
    }


def backfill_pair_codes() -> int:
    n = 0
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM pairs WHERE pair_code IS NULL OR pair_code=''"
        ).fetchall()
        for row in rows:
            code = _next_pair_code()
            conn.execute("UPDATE pairs SET pair_code=? WHERE id=?", (code, row["id"]))
            n += 1
    return n


def resolve_media_paths(ids: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for mid in ids:
        m = get_media(mid)
        if not m:
            results.append({"id": mid, "path": None, "name": None, "error": "not found"})
            continue
        try:
            p = resolve_path(m)
            results.append({
                "id": mid,
                "path": str(p),
                "name": m["name"],
                "type": m["type"],
            })
        except FileNotFoundError:
            results.append({"id": mid, "path": None, "name": m["name"], "error": "directory missing"})
    return results


def get_settings() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    defaults = {
        "thumb_sidecar": "true",
        "thumb_ext": ".thumb.jpg",
        "thumb_shortcut": "none",
        "write_file_tags": "true",
        "auto_pair_after_scan": "false",
        "comparator_video": "../Video Tools/Video Comparison Slider Tool.html",
        "comparator_image": "../Image tools/Image Comparitor With Slider.html",
    }
    for r in rows:
        defaults[r["key"]] = r["value"]
    return defaults


def get_setting(key: str, default: str = "") -> str:
    return str(get_settings().get(key, default))


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


def save_settings(data: dict) -> dict:
    with connect() as conn:
        for k, v in data.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    return get_settings()