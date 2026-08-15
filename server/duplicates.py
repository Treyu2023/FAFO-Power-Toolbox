"""Duplicate file detection and safe removal for common Windows file types."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from db import IMAGE_EXT, VIDEO_EXT
from media_ops import find_ffmpeg, should_skip_entry
from video_probe import probe_video

HASH_READ_BYTES = 1024 * 1024

AUDIO_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".aiff", ".aif"}
DOCUMENT_EXT = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".rtf", ".csv", ".md", ".odt", ".ods", ".odp",
}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".cab", ".iso"}
CODE_EXT = {
    ".html", ".htm", ".css", ".js", ".ts", ".json", ".xml", ".py", ".ps1", ".bat",
    ".cmd", ".cpp", ".c", ".h", ".hpp", ".java", ".cs", ".go", ".rs", ".sql", ".yaml", ".yml",
}
TEXT_EXT = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".css", ".js", ".ts", ".py", ".ps1", ".sql", ".yaml", ".yml", ".log", ".ini", ".cfg", ".bat", ".cmd"}

FILE_TYPE_GROUPS: dict[str, set[str]] = {
    "images": set(IMAGE_EXT) | {".ico", ".svg", ".heic", ".heif"},
    "video": set(VIDEO_EXT),
    "audio": set(AUDIO_EXT),
    "documents": set(DOCUMENT_EXT),
    "archives": set(ARCHIVE_EXT),
    "code": set(CODE_EXT),
}

COMMON_FILE_EXTENSIONS: set[str] = set()
for group in FILE_TYPE_GROUPS.values():
    COMMON_FILE_EXTENSIONS |= group

SKIP_SCAN_DIRS = {
    "$recycle.bin", "$RECYCLE.BIN", "system volume information",
    "@eadir", ".git", "node_modules", "__pycache__", "thumbs.db",
    "windows", "program files", "program files (x86)", "programdata",
}


def extensions_for_type(file_types: str) -> set[str] | None:
    key = (file_types or "all").strip().lower()
    if key in ("", "all", "common"):
        return COMMON_FILE_EXTENSIONS
    if key == "media":
        return FILE_TYPE_GROUPS["images"] | FILE_TYPE_GROUPS["video"] | FILE_TYPE_GROUPS["audio"]
    return FILE_TYPE_GROUPS.get(key)


def classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT or ext in {".ico", ".svg", ".heic", ".heif"}:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in DOCUMENT_EXT:
        return "document"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in CODE_EXT:
        return "code"
    return "other"


def quick_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        size = path.stat().st_size
    except OSError as e:
        raise FileNotFoundError(str(path)) from e
    h.update(str(size).encode("utf-8", errors="replace"))
    # Binary open is portable; avoid encoding surprises on weird NTFS names
    with open(path, "rb") as f:
        h.update(f.read(min(HASH_READ_BYTES, size)))
        if size > HASH_READ_BYTES * 2:
            f.seek(-HASH_READ_BYTES, 2)
            h.update(f.read(HASH_READ_BYTES))
    return h.hexdigest()[:16]


def full_hash(path: Path, on_chunk: Callable[[], None] | None = None) -> str:
    h = hashlib.sha256()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            if on_chunk:
                on_chunk()
    return h.hexdigest()


def frame_hash(path: Path) -> str | None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None
    try:
        out = subprocess.run(
            [
                ffmpeg, "-v", "error", "-i", str(path),
                "-frames:v", "1", "-f", "image2pipe", "-vcodec", "ppm", "-",
            ],
            capture_output=True, timeout=15,
        )
        if out.stdout:
            return hashlib.md5(out.stdout[:50000]).hexdigest()[:12]
    except Exception:
        pass
    return None


def iter_files(root: Path, allowed_ext: set[str] | None) -> list[Path]:
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir():
                    if entry.name.lower() in SKIP_SCAN_DIRS or entry.name.startswith("."):
                        continue
                    if should_skip_entry(entry.name, True):
                        continue
                    stack.append(entry)
                    continue
                if not entry.is_file():
                    continue
                if should_skip_entry(entry.name, False):
                    continue
                ext = entry.suffix.lower()
                if allowed_ext is not None and ext not in allowed_ext:
                    continue
                found.append(entry)
            except (OSError, PermissionError):
                continue
    return found


# Windows-style copy numbers: "photo.jpg" < "photo (1).jpg" < "photo (2).jpg"
_RE_PAREN_NUM = re.compile(r"\s*\((\d+)\)\s*$")
_RE_COPY_WORD = re.compile(r"(?:\s+-\s+copy|\s+copy)(?:\s*\((\d+)\))?\s*$", re.I)
_RE_TRAIL_NUM = re.compile(r"[_-](\d+)$")


def copy_number_rank(name: str) -> tuple[int, int, str]:
    """Lower rank = better keeper. No copy number ranks first (0, 0); then (1, N) by N."""
    stem = Path(name or "").stem
    m = _RE_PAREN_NUM.search(stem)
    if m:
        return (1, int(m.group(1)), (name or "").lower())
    m2 = _RE_COPY_WORD.search(stem)
    if m2:
        n = int(m2.group(1)) if m2.group(1) else 1
        return (1, n, (name or "").lower())
    m3 = _RE_TRAIL_NUM.search(stem)
    if m3:
        return (1, int(m3.group(1)), (name or "").lower())
    return (0, 0, (name or "").lower())


def keeper_sort_key(item: dict[str, Any]) -> tuple:
    """Prefer no-count names, then lowest (N), then older mtime as tie-break."""
    rank = copy_number_rank(item.get("name") or "")
    mtime = float(item.get("mtime") or 0)
    return (rank[0], rank[1], mtime, (item.get("path") or "").lower())


def pick_suggested_keep(items: list[dict[str, Any]]) -> dict[str, Any]:
    return min(items, key=keeper_sort_key)


def build_group(key: str, items: list[dict[str, Any]], *, provisional: bool = False) -> dict[str, Any]:
    sorted_items = sorted(items, key=keeper_sort_key)
    keeper = sorted_items[0]
    total = sum(int(i.get("size") or 0) for i in sorted_items)
    wasted = total - int(keeper.get("size") or 0)
    return {
        "key": key,
        "count": len(sorted_items),
        "total_bytes": total,
        "wasted_bytes": max(0, wasted),
        "kind": sorted_items[0].get("kind", "other"),
        "suggested_keep": keeper["path"],
        "items": sorted_items,
        "provisional": bool(provisional),
    }


def light_entry(path: Path) -> dict[str, Any] | None:
    """Stat-only entry for the fast size pass (no hashing)."""
    try:
        st = path.stat()
    except OSError:
        return None
    size = int(st.st_size)
    return {
        "path": str(path),
        "name": path.name,
        "size": size,
        "mtime": st.st_mtime,
        "ext": path.suffix.lower(),
        "kind": classify_file(path),
        "copy_rank": list(copy_number_rank(path.name)[:2]),
        "match_key": f"size_{size}",
        "provisional": True,
    }


def apply_match_key(entry: dict[str, Any], *, match_mode: str, deep: bool) -> dict[str, Any] | None:
    """Hash / probe a light entry into a real match key. Mutates and returns entry."""
    path = Path(entry["path"])
    if not path.is_file():
        return None
    try:
        if match_mode == "full":
            entry["hash"] = full_hash(path)
            entry["match_key"] = f"full_{entry['hash']}"
        elif entry.get("kind") == "video":
            pr = probe_video(path)
            fh = frame_hash(path) if deep else None
            qh = quick_hash(path)
            entry.update({
                "duration": round(pr.get("duration", 0), 2),
                "res": pr.get("res", ""),
                "quick_hash": qh,
                "frame_hash": fh,
            })
            if deep and fh:
                entry["match_key"] = f"vd_{int(entry['duration'] * 10)}_{fh}_{entry['size'] // 10000}"
            else:
                entry["match_key"] = f"vd_{int(entry['duration'] * 10)}_{qh}"
        else:
            qh = quick_hash(path)
            entry["quick_hash"] = qh
            entry["hash"] = qh
            entry["match_key"] = f"qk_{entry['size']}_{qh}"
        entry["provisional"] = False
        return entry
    except OSError:
        return None


def file_entry(path: Path, *, match_mode: str, deep: bool) -> dict[str, Any] | None:
    entry = light_entry(path)
    if not entry:
        return None
    return apply_match_key(entry, match_mode=match_mode, deep=deep)


def scan_folder_duplicates(
    folder: str,
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
    on_progress: Callable[..., None] | None = None,
) -> dict:
    """Two-phase duplicate scan with live group streaming.

    Phase 1 (quick): walk + stat only. Same-size files appear as provisional
    groups immediately so the UI can populate while hashing still runs.

    Phase 2 (confirm): hash/probe only files that share a size with at least
    one peer (unique sizes are skipped). Groups refine live; false size
    matches drop out.

    on_progress(count, file_path, **kwargs) may include:
      phase, total, scanned, groups, wasted_bytes, duplicate_groups,
      partial, provisional_count, message
    """
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(folder)

    allowed = extensions_for_type(file_types)
    light_entries: list[dict[str, Any]] = []
    size_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    groups_by_key: dict[str, dict[str, Any]] = {}

    last_emit_idx = 0
    last_emit_t = 0.0
    EMIT_EVERY_N = 20
    EMIT_EVERY_S = 0.25
    STREAM_GROUP_CAP = 250

    def current_groups() -> list[dict[str, Any]]:
        groups = list(groups_by_key.values())
        groups.sort(key=lambda g: (-g["wasted_bytes"], -g["count"]))
        return groups[:STREAM_GROUP_CAP]

    def emit(
        idx: int,
        path: str | Path,
        *,
        phase: str,
        total: int,
        scanned: int,
        groups: list | None,
        force_groups: bool = False,
        message: str | None = None,
        extra: dict | None = None,
    ) -> None:
        nonlocal last_emit_idx, last_emit_t
        if not on_progress:
            return
        now = time.time()
        send_groups = groups
        if send_groups is not None:
            if (
                not force_groups
                and (idx - last_emit_idx) < EMIT_EVERY_N
                and (now - last_emit_t) < EMIT_EVERY_S
            ):
                send_groups = None
            else:
                last_emit_idx = idx
                last_emit_t = now
        wasted = (
            sum(g["wasted_bytes"] for g in send_groups)
            if send_groups is not None
            else None
        )
        payload_kw: dict[str, Any] = {
            "total": total,
            "scanned": scanned,
            "phase": phase,
            "partial": True,
        }
        if message:
            payload_kw["message"] = message
        if send_groups is not None:
            payload_kw["groups"] = send_groups
            payload_kw["wasted_bytes"] = wasted or 0
            payload_kw["duplicate_groups"] = len(send_groups)
            payload_kw["provisional_count"] = sum(
                1 for g in send_groups if g.get("provisional")
            )
        if extra:
            payload_kw.update(extra)
        try:
            on_progress(idx, str(path), **payload_kw)
        except TypeError:
            on_progress(idx, str(path))

    # Phase 1: walk + size index (fast) — stream provisional groups live
    walk_count = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            dir_entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in dir_entries:
            try:
                if entry.is_dir():
                    if entry.name.lower() in SKIP_SCAN_DIRS or entry.name.startswith("."):
                        continue
                    if should_skip_entry(entry.name, True):
                        continue
                    stack.append(entry)
                    continue
                if not entry.is_file():
                    continue
                if should_skip_entry(entry.name, False):
                    continue
                ext = entry.suffix.lower()
                if allowed is not None and ext not in allowed:
                    continue
                item = light_entry(entry)
                if not item:
                    continue
                walk_count += 1
                light_entries.append(item)
                size = int(item["size"])
                size_buckets[size].append(item)
                if len(size_buckets[size]) >= 2:
                    key = f"size_{size}"
                    was_new = key not in groups_by_key
                    groups_by_key[key] = build_group(
                        key, size_buckets[size], provisional=True
                    )
                    emit(
                        walk_count,
                        entry,
                        phase="quick",
                        total=0,
                        scanned=walk_count,
                        groups=current_groups(),
                        force_groups=was_new or (walk_count % 40 == 0),
                        message=f"Quick size pass — {len(groups_by_key)} possible groups",
                    )
                elif walk_count % 100 == 0:
                    emit(
                        walk_count,
                        entry,
                        phase="quick",
                        total=0,
                        scanned=walk_count,
                        groups=current_groups() if groups_by_key else None,
                        message=f"Walking files… {walk_count}",
                    )
            except (OSError, PermissionError):
                continue

    total = len(light_entries)
    emit(
        total or 1,
        root,
        phase="quick_done",
        total=total,
        scanned=total,
        groups=current_groups(),
        force_groups=True,
        message=f"Quick pass done — {len(groups_by_key)} size groups · hashing next",
        extra={"quick_groups": len(groups_by_key)},
    )

    # Phase 2: hash only same-size peers
    candidates: list[dict[str, Any]] = []
    for size, items in size_buckets.items():
        if len(items) >= 2:
            candidates.extend(items)

    hash_total = len(candidates)
    if not candidates:
        return {
            "folder": str(root.resolve()),
            "scanned": total,
            "duplicate_groups": 0,
            "wasted_bytes": 0,
            "match_mode": match_mode,
            "file_types": file_types,
            "groups": [],
            "total_candidates": total,
            "hash_candidates": 0,
            "partial": False,
            "phase": "done",
        }

    hash_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups_by_key = {}  # rebuild as confirmed hashes arrive

    for idx, entry in enumerate(candidates, start=1):
        refined = apply_match_key(dict(entry), match_mode=match_mode, deep=deep)
        if not refined:
            continue
        key = refined["match_key"]
        hash_buckets[key].append(refined)
        if len(hash_buckets[key]) >= 2:
            groups_by_key[key] = build_group(
                key, hash_buckets[key], provisional=False
            )
        emit(
            idx,
            refined.get("path") or "",
            phase="hash",
            total=hash_total,
            scanned=idx,
            groups=current_groups(),
            force_groups=(idx == 1 or idx == hash_total or idx % 12 == 0),
            message=f"Confirming {idx}/{hash_total} · {len(groups_by_key)} confirmed groups",
            extra={
                "hash_total": hash_total,
                "walk_total": total,
                "skipped_unique": max(0, total - hash_total),
            },
        )

    groups = list(groups_by_key.values())
    groups.sort(key=lambda g: (-g["wasted_bytes"], -g["count"]))
    wasted_total = sum(g["wasted_bytes"] for g in groups)

    return {
        "folder": str(root.resolve()),
        "scanned": total,
        "duplicate_groups": len(groups),
        "wasted_bytes": wasted_total,
        "match_mode": match_mode,
        "file_types": file_types,
        "groups": groups,
        "total_candidates": total,
        "hash_candidates": hash_total,
        "partial": False,
        "phase": "done",
    }


def scan_catalog_duplicates(dir_ids: list[str] | None = None) -> dict:
    from media_ops import get_all_media, resolve_path

    items = []
    for m in get_all_media():
        if dir_ids and m["dir_id"] not in dir_ids:
            continue
        try:
            p = resolve_path(m)
            if p.exists():
                pr = probe_video(p) if m.get("type") == "video" else {}
                items.append({
                    **m,
                    "abs_path": str(p),
                    "probe": pr,
                    "quick_hash": quick_hash(p),
                    "size": p.stat().st_size,
                })
        except Exception:
            continue

    buckets: dict[str, list] = defaultdict(list)
    for e in items:
        dur = int((e["probe"].get("duration") or 0) * 10)
        key = f"{dur}_{e['quick_hash']}_{e['size']}"
        buckets[key].append(e)

    groups = []
    for v in buckets.values():
        if len(v) < 2:
            continue
        # Annotate pair relationships so UI can avoid "delete the upscaled twin"
        pair_ids = {e.get("pair_id") for e in v if e.get("pair_id")}
        pair_codes = set()
        for e in v:
            for t in e.get("tags") or []:
                if isinstance(t, str) and t.upper().startswith("UP-"):
                    pair_codes.add(t.upper())
        # If two files share a pair_id or UP-code, flag as likely before/after not true dups
        same_pair = False
        if len(pair_ids) == 1 and list(pair_ids)[0]:
            roles = {e.get("pair_role") for e in v}
            if "before" in roles and "after" in roles:
                same_pair = True
        if not same_pair and len(pair_codes) == 1:
            same_pair = True
        groups.append({
            "items": v,
            "likely_pair_not_duplicate": same_pair,
            "pair_codes": sorted(pair_codes),
        })
    return {"groups": groups, "count": len(groups)}


def _send_to_recycle_bin(path: Path) -> None:
    if os.name != "nt":
        path.unlink()
        return
    quoted = str(path).replace("'", "''")
    ps = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{quoted}', "
        "'OnlyErrorDialogs', 'SendToRecycleBin')"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise OSError(err or f"Recycle delete failed for {path}")


def delete_paths(
    *,
    keep_path: str | None,
    delete_paths_list: list[str],
    to_trash: bool = True,
    dry_run: bool = False,
) -> dict:
    keep = Path(keep_path).resolve() if keep_path else None
    results = []
    deleted = 0
    failed = 0
    bytes_freed = 0

    for raw in delete_paths_list:
        target = Path(raw).resolve()
        item = {"path": str(target), "ok": False, "error": None, "bytes": 0}
        try:
            if not target.is_file():
                raise FileNotFoundError(f"Not a file: {target}")
            if keep and target == keep:
                raise ValueError("Cannot delete the keeper file")
            size = target.stat().st_size
            item["bytes"] = size
            if dry_run:
                item["ok"] = True
                item["action"] = "dry_run"
            elif to_trash:
                _send_to_recycle_bin(target)
                item["ok"] = True
                item["action"] = "recycle_bin"
            else:
                target.unlink()
                item["ok"] = True
                item["action"] = "permanent"
            if item["ok"]:
                deleted += 1
                bytes_freed += size
        except Exception as exc:
            item["error"] = str(exc)
            failed += 1
        results.append(item)

    return {
        "dry_run": dry_run,
        "to_trash": to_trash,
        "keep_path": str(keep) if keep else None,
        "deleted": deleted,
        "failed": failed,
        "bytes_freed": bytes_freed,
        "results": results,
    }


def merge_duplicate_group(
    *,
    keep_path: str,
    group_paths: list[str],
    to_trash: bool = True,
    dry_run: bool = False,
) -> dict:
    keep = Path(keep_path).resolve()
    to_delete = []
    for raw in group_paths:
        p = Path(raw).resolve()
        if p == keep:
            continue
        if p.is_file():
            to_delete.append(str(p))
    return delete_paths(
        keep_path=str(keep),
        delete_paths_list=to_delete,
        to_trash=to_trash,
        dry_run=dry_run,
    )


def read_text_preview(path: str, max_bytes: int = 65536) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    if p.suffix.lower() not in TEXT_EXT and not p.suffix:
        raise ValueError("Not a text-previewable file type")
    data = p.read_bytes()[:max_bytes]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return {
        "path": str(p.resolve()),
        "truncated": p.stat().st_size > max_bytes,
        "size": p.stat().st_size,
        "text": text,
    }


def preview_cache_dir() -> Path:
    d = Path(__file__).resolve().parent / "thumbnails" / "file_preview"
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_preview_image(path: str, timestamp: float = 0.5) -> tuple[Path, str]:
    """Return (image_path, media_type) for UI thumbnails.

    - Images: original path
    - Video: first-ish frame via ffmpeg (cached by path+mtime)
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    kind = classify_file(p)
    if kind == "image":
        mime, _ = mimetypes.guess_type(str(p))
        return p, (mime or "image/jpeg")
    if kind != "video":
        raise ValueError(f"No still preview for kind={kind}")

    st = p.stat()
    key = hashlib.sha256(f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}|{timestamp}".encode()).hexdigest()[:24]
    out = preview_cache_dir() / f"{key}.jpg"
    if out.is_file() and out.stat().st_size > 0:
        return out, "image/jpeg"

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found — install ffmpeg for video thumbnails")
    t = max(0.0, float(timestamp or 0.5))
    # -ss before -i is faster for first-frame style peeks
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(t),
        "-i",
        str(p),
        "-frames:v",
        "1",
        "-q:v",
        "4",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        # Fallback: try near t=0
        cmd[3] = "0.1"
        proc2 = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if proc2.returncode != 0 or not out.is_file():
            err = (proc2.stderr or proc.stderr or "ffmpeg failed").strip()
            raise RuntimeError(err[:400])
    return out, "image/jpeg"


def file_info(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    stat = p.stat()
    mime, _ = mimetypes.guess_type(str(p))
    return {
        "path": str(p.resolve()),
        "name": p.name,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "ext": p.suffix.lower(),
        "kind": classify_file(p),
        "mime": mime or "application/octet-stream",
        "hash_quick": quick_hash(p),
    }