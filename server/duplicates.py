"""Duplicate file detection and safe removal for common Windows file types."""
from __future__ import annotations

import hashlib
import mimetypes
import os
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
    size = path.stat().st_size
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(min(HASH_READ_BYTES, size)))
        if size > HASH_READ_BYTES * 2:
            f.seek(-HASH_READ_BYTES, 2)
            h.update(f.read(HASH_READ_BYTES))
    return h.hexdigest()[:16]


def full_hash(path: Path, on_chunk: Callable[[], None] | None = None) -> str:
    h = hashlib.sha256()
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


def file_entry(path: Path, *, match_mode: str, deep: bool) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None

    entry: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "ext": path.suffix.lower(),
        "kind": classify_file(path),
    }

    if match_mode == "full":
        entry["hash"] = full_hash(path)
        entry["match_key"] = f"full_{entry['hash']}"
    elif entry["kind"] == "video":
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

    return entry


def scan_folder_duplicates(
    folder: str,
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(folder)

    allowed = extensions_for_type(file_types)
    paths = iter_files(root, allowed)
    entries: list[dict[str, Any]] = []
    total = len(paths)

    for idx, path in enumerate(paths, start=1):
        if on_progress:
            on_progress(idx, str(path))
        item = file_entry(path, match_mode=match_mode, deep=deep)
        if item:
            entries.append(item)

    buckets: dict[str, list] = defaultdict(list)
    for entry in entries:
        buckets[entry["match_key"]].append(entry)

    groups = []
    for key, items in buckets.items():
        if len(items) < 2:
            continue
        sorted_items = sorted(items, key=lambda x: (x["mtime"], x["path"]), reverse=True)
        keeper = sorted_items[0]
        wasted = sum(i["size"] for i in sorted_items) - keeper["size"]
        groups.append({
            "key": key,
            "count": len(sorted_items),
            "total_bytes": sum(i["size"] for i in sorted_items),
            "wasted_bytes": wasted,
            "kind": sorted_items[0].get("kind", "other"),
            "suggested_keep": keeper["path"],
            "items": sorted_items,
        })

    groups.sort(key=lambda g: (-g["wasted_bytes"], -g["count"]))
    wasted_total = sum(g["wasted_bytes"] for g in groups)

    return {
        "folder": str(root.resolve()),
        "scanned": len(entries),
        "duplicate_groups": len(groups),
        "wasted_bytes": wasted_total,
        "match_mode": match_mode,
        "file_types": file_types,
        "groups": groups,
        "total_candidates": total,
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