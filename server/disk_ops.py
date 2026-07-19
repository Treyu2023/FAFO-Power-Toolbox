"""Disk Space Analyzer — usage, large files, cleanup candidates."""
from __future__ import annotations

import os
import platform
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

IS_WINDOWS = platform.system() == "Windows"
ProgressFn = Callable[[str, dict[str, Any] | None], None]

JUNK_PATTERNS = {
    "temp": {".tmp", ".temp", ".log"},
    "thumbs": {"thumbs.db", "desktop.ini"},
}
JUNK_DIRS = {"temp", "tmp", "cache", "caches", "$recycle.bin", "prefetch"}


def _bytes_human(n: int | float) -> str:
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} PB"


def get_overview() -> dict[str, Any]:
    drives = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drives.append({
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "total_human": _bytes_human(usage.total),
                "used_human": _bytes_human(usage.used),
                "free_human": _bytes_human(usage.free),
            })
        except (PermissionError, OSError):
            continue

    home = Path.home()
    quick_dirs = []
    for name, label in [
        ("Downloads", "Downloads"), ("Desktop", "Desktop"), ("Documents", "Documents"),
        ("Videos", "Videos"), ("Pictures", "Pictures"),
    ]:
        p = home / name
        if p.exists():
            size = _dir_size_fast(p, max_depth=2, max_files=500)
            quick_dirs.append({"name": label, "path": str(p), "size": size, "size_human": _bytes_human(size)})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "drives": drives,
        "user_folders": sorted(quick_dirs, key=lambda x: -x["size"]),
    }


def _dir_size_fast(path: Path, max_depth: int = 3, max_files: int = 2000) -> int:
    total = 0
    count = 0
    try:
        for root, dirs, files in os.walk(path):
            depth = root.replace(str(path), "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()
            for f in files:
                if count >= max_files:
                    return total
                try:
                    total += (Path(root) / f).stat().st_size
                    count += 1
                except OSError:
                    pass
    except (PermissionError, OSError):
        pass
    return total


def scan_path(
    root: str,
    max_files: int = 5000,
    min_size_mb: float = 10,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    base = Path(root).resolve()
    if not base.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    min_bytes = int(min_size_mb * 1024 * 1024)
    files: list[dict[str, Any]] = []
    dir_sizes: dict[str, int] = {}
    junk: list[dict[str, Any]] = []
    scanned = 0

    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d.lower() not in {"windows", "program files", "program files (x86)", "$recycle.bin"} and not d.startswith(".")]
        rel_dir = str(Path(dirpath).relative_to(base)) if dirpath != str(base) else "."
        for fname in filenames:
            if scanned >= max_files:
                break
            fpath = Path(dirpath) / fname
            try:
                st = fpath.stat()
            except OSError:
                continue
            scanned += 1
            size = st.st_size
            parent_key = rel_dir
            dir_sizes[parent_key] = dir_sizes.get(parent_key, 0) + size

            if size >= min_bytes:
                files.append({
                    "path": str(fpath),
                    "name": fname,
                    "size": size,
                    "size_human": _bytes_human(size),
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "folder": rel_dir,
                })

            low = fname.lower()
            if low in JUNK_PATTERNS["thumbs"] or low.endswith(tuple(JUNK_PATTERNS["temp"])):
                junk.append({"path": str(fpath), "size": size, "reason": "temp/metadata"})
            elif any(j in dirpath.lower() for j in JUNK_DIRS):
                junk.append({"path": str(fpath), "size": size, "reason": "cache/temp folder"})

            if scanned % 200 == 0 and on_progress:
                on_progress(f"Scanned {scanned} files…", {"scanned": scanned})

    files.sort(key=lambda x: -x["size"])
    top_dirs = sorted(
        [{"path": k, "size": v, "size_human": _bytes_human(v)} for k, v in dir_sizes.items()],
        key=lambda x: -x["size"],
    )[:40]

    junk_size = sum(j["size"] for j in junk)
    return {
        "root": str(base),
        "scanned_files": scanned,
        "large_files": files[:100],
        "large_count": len(files),
        "top_folders": top_dirs,
        "junk_candidates": junk[:200],
        "junk_count": len(junk),
        "junk_size": junk_size,
        "junk_size_human": _bytes_human(junk_size),
    }


def delete_paths(paths: list[str], dry_run: bool = True) -> dict[str, Any]:
    results = []
    freed = 0
    for p in paths:
        path = Path(p)
        try:
            if not path.exists():
                results.append({"path": p, "ok": False, "error": "not found"})
                continue
            size = path.stat().st_size if path.is_file() else 0
            if dry_run:
                results.append({"path": p, "ok": True, "dry_run": True, "size": size})
            else:
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path, ignore_errors=True)
                freed += size
                results.append({"path": p, "ok": True, "size": size})
        except OSError as e:
            results.append({"path": p, "ok": False, "error": str(e)})
    return {"dry_run": dry_run, "freed": freed, "freed_human": _bytes_human(freed), "results": results}