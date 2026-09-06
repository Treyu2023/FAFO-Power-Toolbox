"""Duplicate file detection and safe removal for common Windows file types."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable

from db import IMAGE_EXT, VIDEO_EXT
from media_ops import find_ffmpeg, should_skip_entry, pair_id_from_name
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
    "windows.old", "recovery", "perflogs", "msocache", "config.msi",
    "system32", "syswow64", "winsxs", "windowsapps",
}

THIS_PC_TOKENS = {"", "*", "__this_pc__", "this pc", "thispc", "all drives", "whole system"}

# Cross-source roles: inbox copies may be deleted; before/after are evidence and stay locked.
SOURCE_ROLE_INBOX = "inbox"
SOURCE_ROLE_BEFORE = "before"
SOURCE_ROLE_AFTER = "after"
PROTECTED_ROLES = {SOURCE_ROLE_BEFORE, SOURCE_ROLE_AFTER}
VALID_SOURCE_ROLES = {SOURCE_ROLE_INBOX, SOURCE_ROLE_BEFORE, SOURCE_ROLE_AFTER}

# Group Therapy / FlashVSR pair id stamped onto pre-scaled + post-upgrade names.
_PID_IN_NAME_RE = re.compile(r"_PID_([0-9a-f]{8})(?:_|$)", re.I)
_PAIR_FOLDER_RE = re.compile(r"^GT-([0-9a-f]{8})__", re.I)
_PID_TITLE_RE = re.compile(r"PID[_-]([0-9a-f]{8})", re.I)
# Grok Imagine / X ids that survive rename better than raw filename.
_GROK_VIDEO_RE = re.compile(
    r"(grok-video-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
    re.I,
)
_GROK_NUM_RE = re.compile(r"(?<![a-z0-9])grok[-_]?(\d{2,})(?!\d)", re.I)
_LEADING_NUM_RE = re.compile(r"^(\d{7,})(?:[_-]|$)")
GROK_ID_SIZE_TOLERANCE = 0.025

DEFAULT_PIPELINE_INBOX = r"D:\OUTPUTS\__X_GROK\NEW DOWNLOADS"
DEFAULT_PIPELINE_BEFORE = r"D:\OUTPUTS\__X_GROK\Upscaled Videos\Pre Scaled videos"
DEFAULT_PIPELINE_AFTER = r"D:\OUTPUTS\__X_GROK\Upscaled Videos\Current\Ready for CIV"

# GetDriveTypeW: 2=removable, 3=fixed, 4=remote, 5=cdrom
_DRIVE_FIXED = 3
_DRIVE_REMOVABLE = 2


def list_local_drives() -> list[Path]:
    """Ready local volumes (fixed + removable). Skips empty CD/DVD trays."""
    letters: list[str] = []
    if hasattr(os, "listdrives"):
        letters = [str(d) for d in os.listdrives()]
    else:
        import string
        letters = [f"{c}:\\" for c in string.ascii_uppercase]
    roots: list[Path] = []
    get_type = None
    try:
        import ctypes
        get_type = ctypes.windll.kernel32.GetDriveTypeW
    except Exception:
        get_type = None
    for raw in letters:
        text = str(raw).strip()
        if not text:
            continue
        if len(text) == 2 and text[1] == ":":
            text += "\\"
        path = Path(text)
        try:
            if not path.exists():
                continue
        except OSError:
            continue
        if get_type is not None:
            try:
                kind = int(get_type(str(path)))
            except Exception:
                kind = _DRIVE_FIXED
            if kind not in (_DRIVE_FIXED, _DRIVE_REMOVABLE):
                continue
        roots.append(path)
    return roots


def is_whole_system_folder(folder: str | None) -> bool:
    return str(folder or "").strip().lower() in THIS_PC_TOKENS


def resolve_scan_roots(folder: str | None, *, whole_system: bool = False) -> tuple[list[Path], str]:
    """Return (roots, display_label) for a folder or This PC."""
    if whole_system or is_whole_system_folder(folder):
        roots = list_local_drives()
        if not roots:
            raise FileNotFoundError("No local drives found to scan")
        label = "This PC (" + ", ".join(str(r).rstrip("\\/") + "\\" for r in roots) + ")"
        return roots, label
    root = Path(str(folder or "").strip())
    if not str(root) or not root.is_dir():
        raise FileNotFoundError(folder or "(empty folder)")
    return [root], str(root.resolve())


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


def extract_grok_ids(name: str) -> list[str]:
    """Stable Grok/X ids from a filename (order preserved, lowercased)."""
    stem = Path(str(name or "")).name
    found: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        t = str(token or "").strip().lower()
        if not t or t in seen:
            return
        seen.add(t)
        found.append(t)

    for m in _GROK_VIDEO_RE.finditer(stem):
        add(m.group(1))
    for m in _GROK_NUM_RE.finditer(stem):
        add("grok-" + m.group(1))
    m = _LEADING_NUM_RE.match(Path(stem).stem if stem else "")
    if not m:
        m = _LEADING_NUM_RE.match(stem)
    if m:
        add(m.group(1))
    return found


def size_within_tolerance(size: int, original: int, tol: float = GROK_ID_SIZE_TOLERANCE) -> bool:
    orig = int(original or 0)
    sz = int(size or 0)
    if orig <= 0 or sz <= 0:
        return False
    return abs(sz - orig) / float(orig) <= float(tol)


def _norm_role(role: str | None) -> str:
    key = str(role or SOURCE_ROLE_INBOX).strip().lower()
    aliases = {
        "search": SOURCE_ROLE_INBOX,
        "deletable": SOURCE_ROLE_INBOX,
        "downloads": SOURCE_ROLE_INBOX,
        "inbox": SOURCE_ROLE_INBOX,
        "pre": SOURCE_ROLE_BEFORE,
        "prescaled": SOURCE_ROLE_BEFORE,
        "pre-scaled": SOURCE_ROLE_BEFORE,
        "pre_scaled": SOURCE_ROLE_BEFORE,
        "original": SOURCE_ROLE_BEFORE,
        "originals": SOURCE_ROLE_BEFORE,
        "before": SOURCE_ROLE_BEFORE,
        "reference": SOURCE_ROLE_BEFORE,
        "after": SOURCE_ROLE_AFTER,
        "post": SOURCE_ROLE_AFTER,
        "post-upgrade": SOURCE_ROLE_AFTER,
        "post_upgrade": SOURCE_ROLE_AFTER,
        "upscaled": SOURCE_ROLE_AFTER,
        "evidence": SOURCE_ROLE_AFTER,
    }
    key = aliases.get(key, key)
    if key not in VALID_SOURCE_ROLES:
        raise ValueError(f"Unknown source role: {role}")
    return key


def normalize_sources(sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Validate folder list. Each item: {path, role, label?, recursive?}."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in sources or []:
        if not isinstance(raw, dict):
            continue
        path = str(raw.get("path") or raw.get("folder") or "").strip()
        if not path:
            continue
        root = Path(path)
        if not root.is_dir():
            raise FileNotFoundError(path)
        resolved = str(root.resolve())
        role = _norm_role(raw.get("role"))
        key = resolved.casefold() + "|" + role
        if key in seen:
            continue
        seen.add(key)
        rec_flag = raw.get("recursive")
        out.append({
            "path": resolved,
            "role": role,
            "label": str(raw.get("label") or "").strip() or role,
            "recursive": True if rec_flag is None else bool(rec_flag),
            "protected": role in PROTECTED_ROLES,
        })
    if not out:
        raise ValueError("Add at least one source folder")
    if not any(s["role"] == SOURCE_ROLE_INBOX for s in out):
        raise ValueError("Cross-source scan needs at least one Inbox folder (deletable copies)")
    return out


def _path_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def is_protected_path(path: str | Path, protected_roots: list[str] | None) -> bool:
    if not protected_roots:
        return False
    target = Path(path)
    try:
        target = target.resolve()
    except OSError:
        return False
    for raw in protected_roots:
        try:
            root = Path(str(raw)).resolve()
        except OSError:
            continue
        if _path_under_root(target, root):
            return True
    return False


def default_pipeline_sources() -> dict[str, Any]:
    """Suggested Inbox / Pre-scaled / After folders from the FlashVSR profile when present."""
    downloads = str((Path.home() / "Downloads").resolve()) if (Path.home() / "Downloads").is_dir() else str(Path.home() / "Downloads")
    inbox = [DEFAULT_PIPELINE_INBOX]
    before = [DEFAULT_PIPELINE_BEFORE]
    after = [DEFAULT_PIPELINE_AFTER]
    profile = Path(__file__).resolve().parent.parent / "System Tools" / "PinokioDock" / "profiles" / "flashvsr-4090-default.json"
    try:
        if profile.is_file():
            data = json.loads(profile.read_text(encoding="utf-8"))
            settings = data.get("settings") or {}
            watch = str(settings.get("batch_watch_folder") or "").strip()
            archive = str(settings.get("batch_source_archive_dir") or "").strip()
            output = str(
                settings.get("toolbox_output_dir")
                or settings.get("gt_after_dir")
                or settings.get("output_dir")
                or ""
            ).strip()
            if watch:
                inbox = [watch]
            if archive:
                before = [archive]
            if output:
                after = [output]
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    if downloads and downloads.casefold() not in {p.casefold() for p in inbox}:
        inbox.append(downloads)

    def _annotate(paths: list[str], role: str) -> list[dict[str, Any]]:
        rows = []
        for p in paths:
            exists = Path(p).is_dir()
            rows.append({"path": p, "role": role, "exists": exists, "protected": role in PROTECTED_ROLES})
        return rows

    return {
        "inbox": _annotate(inbox, SOURCE_ROLE_INBOX),
        "before": _annotate(before, SOURCE_ROLE_BEFORE),
        "after": _annotate(after, SOURCE_ROLE_AFTER),
        "hint": (
            "Inbox copies can be recycled. Pre-scaled (before) and post-upgrade (after) "
            "are locked. After files are matched by _PID_xxxxxxxx from the pre-scaled name, "
            "not by size — they are 4K / high-fps re-encodes."
        ),
    }


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


def iter_files(root: Path, allowed_ext: set[str] | None, *, recursive: bool = True) -> list[Path]:
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
                    if not recursive:
                        continue
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
        "pid": pair_id_from_name(path.name) or pair_id_from_name(str(path)),
        "grok_ids": extract_grok_ids(path.name),
    }


def annotate_source(entry: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    entry["role"] = source["role"]
    entry["source_label"] = source.get("label") or source["role"]
    entry["protected"] = bool(source.get("protected") or source["role"] in PROTECTED_ROLES)
    if not entry.get("pid"):
        entry["pid"] = pair_id_from_name(entry.get("name") or "") or pair_id_from_name(entry.get("path") or "")
    if not entry.get("grok_ids"):
        entry["grok_ids"] = extract_grok_ids(entry.get("name") or "")
    return entry


def _deletable_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if not i.get("protected") and i.get("role") != SOURCE_ROLE_AFTER and i.get("role") != SOURCE_ROLE_BEFORE]


def _pick_cross_keep(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer a locked Before original; never suggest deleting After/Before."""
    before = [i for i in items if i.get("role") == SOURCE_ROLE_BEFORE]
    if before:
        return min(before, key=keeper_sort_key)
    locked = [i for i in items if i.get("protected")]
    if locked:
        return min(locked, key=keeper_sort_key)
    return pick_suggested_keep(items)


def build_cross_group(
    key: str,
    items: list[dict[str, Any]],
    *,
    provisional: bool = False,
    match_kinds: list[str] | None = None,
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        unique[str(item.get("path") or "")] = item
    rows = [v for k, v in unique.items() if k]
    if not rows:
        return build_group(key, items, provisional=provisional)
    sorted_items = sorted(rows, key=keeper_sort_key)
    keeper = _pick_cross_keep(sorted_items)
    deletable = _deletable_items(sorted_items)
    wasted = sum(int(i.get("size") or 0) for i in deletable)
    kinds = list(match_kinds or [])
    if not kinds:
        kinds = ["size"] if provisional else ["exact"]
    pids = sorted({str(i.get("pid") or "") for i in sorted_items if i.get("pid")})
    grok_ids = []
    seen_g: set[str] = set()
    for i in sorted_items:
        for gid in i.get("grok_ids") or []:
            if gid not in seen_g:
                seen_g.add(gid)
                grok_ids.append(gid)
    return {
        "key": key,
        "count": len(sorted_items),
        "total_bytes": sum(int(i.get("size") or 0) for i in sorted_items),
        "wasted_bytes": max(0, wasted),
        "kind": sorted_items[0].get("kind", "other"),
        "suggested_keep": keeper["path"],
        "items": sorted_items,
        "provisional": bool(provisional),
        "match_kinds": kinds,
        "cross_source": True,
        "has_before": any(i.get("role") == SOURCE_ROLE_BEFORE for i in sorted_items),
        "has_after": any(i.get("role") == SOURCE_ROLE_AFTER for i in sorted_items),
        "has_inbox": any(i.get("role") == SOURCE_ROLE_INBOX for i in sorted_items),
        "deletable_count": len(deletable),
        "protected_count": sum(1 for i in sorted_items if i.get("protected")),
        "pids": pids,
        "grok_ids": grok_ids,
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


class ScanController:
    """Pause / resume / cancel a live duplicate scan without dropping groups already found."""

    def __init__(self) -> None:
        self._run = threading.Event()
        self._run.set()
        self._cancel = threading.Event()

    def wait_if_paused(self) -> None:
        self._run.wait()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def is_paused(self) -> bool:
        return not self._run.is_set() and not self._cancel.is_set()

    def pause(self) -> None:
        if not self._cancel.is_set():
            self._run.clear()

    def resume(self) -> None:
        self._run.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._run.set()


def scan_folder_duplicates(
    folder: str,
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
    recursive: bool = True,
    whole_system: bool = False,
    on_progress: Callable[..., None] | None = None,
    controller: ScanController | None = None,
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
    roots, label = resolve_scan_roots(folder, whole_system=whole_system)
    allowed = extensions_for_type(file_types)
    light_entries: list[dict[str, Any]] = []
    size_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    groups_by_key: dict[str, dict[str, Any]] = {}

    last_emit_idx = 0
    last_emit_t = 0.0
    EMIT_EVERY_N = 20
    EMIT_EVERY_S = 0.25
    STREAM_GROUP_CAP = 250
    cancelled = False

    def should_stop() -> bool:
        nonlocal cancelled
        if not controller:
            return False
        controller.wait_if_paused()
        if controller.is_cancelled():
            cancelled = True
            return True
        return False

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
    stack = list(roots)
    stop = False
    while stack and not stop:
        if should_stop():
            break
        current = stack.pop()
        try:
            dir_entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in dir_entries:
            if should_stop():
                stop = True
                break
            try:
                if entry.is_dir():
                    if not recursive:
                        continue
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
        label,
        phase="quick_done",
        total=total,
        scanned=total,
        groups=current_groups(),
        force_groups=True,
        message=(
            f"Cancelled after {total} files — {len(groups_by_key)} groups kept"
            if cancelled else
            f"Quick pass done — {len(groups_by_key)} size groups · hashing next"
        ),
        extra={"quick_groups": len(groups_by_key)},
    )

    def _result(groups_list, *, hash_candidates=0, phase="done"):
        groups_list = list(groups_list)
        groups_list.sort(key=lambda g: (-g["wasted_bytes"], -g["count"]))
        wasted = sum(g["wasted_bytes"] for g in groups_list)
        return {
            "folder": label,
            "roots": [str(r) for r in roots],
            "recursive": bool(recursive),
            "whole_system": bool(whole_system or is_whole_system_folder(folder)),
            "scanned": total,
            "duplicate_groups": len(groups_list),
            "wasted_bytes": wasted,
            "match_mode": match_mode,
            "file_types": file_types,
            "groups": groups_list,
            "total_candidates": total,
            "hash_candidates": hash_candidates,
            "partial": False,
            "phase": "cancelled" if cancelled else phase,
            "cancelled": cancelled,
        }

    if cancelled:
        return _result(groups_by_key.values(), phase="cancelled")

    # Phase 2: hash only same-size peers
    candidates: list[dict[str, Any]] = []
    for size, items in size_buckets.items():
        if len(items) >= 2:
            candidates.extend(items)

    hash_total = len(candidates)
    if not candidates:
        return _result([], hash_candidates=0)

    hash_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups_by_key = {}  # rebuild as confirmed hashes arrive

    for idx, entry in enumerate(candidates, start=1):
        if should_stop():
            break
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

    return _result(groups_by_key.values(), hash_candidates=hash_total)


def scan_cross_source_duplicates(
    sources: list[dict[str, Any]],
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "video",
    recursive: bool = True,
    on_progress: Callable[..., None] | None = None,
    controller: ScanController | None = None,
) -> dict:
    """Cross-folder duplicate screen for the FlashVSR / Imagine pipeline.

    Inbox folders (Downloads, NEW DOWNLOADS) are compared against each other
    with the usual size+hash method. Pre-scaled / Before originals are the
    same bytes as the download, so they join those groups — but they are
    locked. After / post-upgrade files are 4K high-fps re-encodes, so they
    are attached only via `_PID_xxxxxxxx` (or a surviving Grok id) from the
    pre-scaled copy. After files are never deletable through this scan.
    """
    normalized = normalize_sources(sources)
    allowed = extensions_for_type(file_types)
    cancelled = False

    def should_stop() -> bool:
        nonlocal cancelled
        if not controller:
            return False
        controller.wait_if_paused()
        if controller.is_cancelled():
            cancelled = True
            return True
        return False

    comparable: list[dict[str, Any]] = []  # inbox + before (size/hash)
    after_entries: list[dict[str, Any]] = []
    size_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    groups_by_key: dict[str, dict[str, Any]] = {}
    walk_count = 0
    last_emit_idx = 0
    last_emit_t = 0.0
    EMIT_EVERY_N = 20
    EMIT_EVERY_S = 0.25
    STREAM_GROUP_CAP = 250

    def current_groups() -> list[dict[str, Any]]:
        groups = [g for g in groups_by_key.values() if g.get("deletable_count", 0) >= 1]
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
            "cross_source": True,
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

    def walk_source(source: dict[str, Any]) -> None:
        nonlocal walk_count
        root = Path(source["path"])
        rec = bool(source.get("recursive", recursive))
        role = source["role"]
        stack = [root]
        stop = False
        while stack and not stop:
            if should_stop():
                return
            current = stack.pop()
            try:
                dir_entries = list(current.iterdir())
            except (OSError, PermissionError):
                continue
            for entry in dir_entries:
                if should_stop():
                    stop = True
                    break
                try:
                    if entry.is_dir():
                        if not rec:
                            continue
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
                    annotate_source(item, source)
                    walk_count += 1
                    if role == SOURCE_ROLE_AFTER:
                        after_entries.append(item)
                    else:
                        comparable.append(item)
                        size = int(item["size"])
                        size_buckets[size].append(item)
                        if len(size_buckets[size]) >= 2:
                            peers = size_buckets[size]
                            if any(p.get("role") == SOURCE_ROLE_INBOX for p in peers):
                                key = f"size_{size}"
                                was_new = key not in groups_by_key
                                groups_by_key[key] = build_cross_group(
                                    key, peers, provisional=True, match_kinds=["size"]
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
                    if walk_count % 100 == 0:
                        emit(
                            walk_count,
                            entry,
                            phase="quick",
                            total=0,
                            scanned=walk_count,
                            groups=current_groups() if groups_by_key else None,
                            message=f"Walking {source['label']}… {walk_count}",
                        )
                except (OSError, PermissionError):
                    continue

    for src in normalized:
        if should_stop():
            break
        emit(
            walk_count or 1,
            src["path"],
            phase="quick",
            total=0,
            scanned=walk_count,
            groups=current_groups() if groups_by_key else None,
            force_groups=True,
            message=f"Scanning {src['role']}: {src['path']}",
        )
        walk_source(src)

    total = walk_count
    protected_roots = [s["path"] for s in normalized if s["protected"]]
    inbox_roots = [s["path"] for s in normalized if s["role"] == SOURCE_ROLE_INBOX]
    before_roots = [s["path"] for s in normalized if s["role"] == SOURCE_ROLE_BEFORE]
    after_roots = [s["path"] for s in normalized if s["role"] == SOURCE_ROLE_AFTER]
    label = " + ".join(f"{s['role']}:{s['path']}" for s in normalized)

    emit(
        total or 1,
        label,
        phase="quick_done",
        total=total,
        scanned=total,
        groups=current_groups(),
        force_groups=True,
        message=(
            f"Cancelled after {total} files"
            if cancelled else
            f"Quick pass done — hashing Inbox vs Pre-scaled next"
        ),
    )

    def _result(groups_list, *, hash_candidates=0, phase="done") -> dict[str, Any]:
        groups_list = [g for g in groups_list if g.get("deletable_count", 0) >= 1 and g.get("count", 0) >= 2]
        groups_list.sort(key=lambda g: (-g["wasted_bytes"], -g["count"]))
        wasted = sum(g["wasted_bytes"] for g in groups_list)
        return {
            "folder": label,
            "roots": [s["path"] for s in normalized],
            "sources": normalized,
            "cross_source": True,
            "recursive": bool(recursive),
            "whole_system": False,
            "scanned": total,
            "duplicate_groups": len(groups_list),
            "wasted_bytes": wasted,
            "match_mode": match_mode,
            "file_types": file_types,
            "groups": groups_list,
            "total_candidates": total,
            "hash_candidates": hash_candidates,
            "partial": False,
            "phase": "cancelled" if cancelled else phase,
            "cancelled": cancelled,
            "protected_roots": protected_roots,
            "inbox_roots": inbox_roots,
            "before_roots": before_roots,
            "after_roots": after_roots,
            "after_indexed": len(after_entries),
        }

    if cancelled:
        return _result(groups_by_key.values(), phase="cancelled")

    # Phase 2: hash inbox+before that share a size
    candidates: list[dict[str, Any]] = []
    for size, items in size_buckets.items():
        if len(items) >= 2 and any(i.get("role") == SOURCE_ROLE_INBOX for i in items):
            candidates.extend(items)

    hash_total = len(candidates)
    hash_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path_index: dict[str, dict[str, Any]] = {}
    groups_by_key = {}

    for idx, entry in enumerate(candidates, start=1):
        if should_stop():
            break
        refined = apply_match_key(dict(entry), match_mode=match_mode, deep=deep)
        if not refined:
            continue
        annotate_source(refined, {
            "role": entry.get("role") or SOURCE_ROLE_INBOX,
            "label": entry.get("source_label") or entry.get("role") or SOURCE_ROLE_INBOX,
            "protected": entry.get("protected"),
        })
        refined["pid"] = entry.get("pid")
        refined["grok_ids"] = entry.get("grok_ids") or []
        path_index[refined["path"]] = refined
        key = refined["match_key"]
        hash_buckets[key].append(refined)
        if len(hash_buckets[key]) >= 2 and any(i.get("role") == SOURCE_ROLE_INBOX for i in hash_buckets[key]):
            groups_by_key[key] = build_cross_group(
                key, hash_buckets[key], provisional=False, match_kinds=["exact"]
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
            extra={"hash_total": hash_total, "walk_total": total},
        )

    if cancelled:
        return _result(groups_by_key.values(), hash_candidates=hash_total, phase="cancelled")

    # Index remaining comparable files that were unique-size (for grok-id / PID links)
    for entry in comparable:
        if entry["path"] in path_index:
            continue
        path_index[entry["path"]] = entry

    parent: dict[str, str] = {}

    def _find(p: str) -> str:
        parent.setdefault(p, p)
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    for bucket in hash_buckets.values():
        paths = [i["path"] for i in bucket if i.get("path")]
        for extra in paths[1:]:
            _union(paths[0], extra)

    # Grok-id: inbox vs before (size may differ slightly on re-downloads)
    grok_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in path_index.values():
        if entry.get("role") == SOURCE_ROLE_AFTER:
            continue
        for gid in entry.get("grok_ids") or []:
            grok_map[gid].append(entry)
    grok_unions = 0
    for gid, rows in grok_map.items():
        if len(rows) < 2:
            continue
        if not any(r.get("role") == SOURCE_ROLE_INBOX for r in rows):
            continue
        # Prefer linking when a before original exists, or when sizes agree.
        before_rows = [r for r in rows if r.get("role") == SOURCE_ROLE_BEFORE]
        inbox_rows = [r for r in rows if r.get("role") == SOURCE_ROLE_INBOX]
        linkable = []
        if before_rows:
            # Same Grok id across inbox + pre-scaled is the identity even when
            # Windows added "(1)" or the pre-scaled name gained _PID_.
            linkable.extend(before_rows)
            linkable.extend(inbox_rows)
        else:
            # inbox-only grok-id copies (same download twice, possibly renamed)
            linkable = inbox_rows
        if len(linkable) < 2:
            continue
        grok_unions += 1
        base = linkable[0]["path"]
        for extra in linkable[1:]:
            _union(base, extra["path"])

    emit(
        total or 1,
        label,
        phase="hash",
        total=max(hash_total, 1),
        scanned=hash_total,
        groups=current_groups(),
        force_groups=True,
        message=f"Linking Grok ids ({grok_unions}) and PID after-files…",
    )

    after_by_pid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    after_by_grok: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in after_entries:
        if item.get("pid"):
            after_by_pid[str(item["pid"])].append(item)
        for gid in item.get("grok_ids") or []:
            after_by_grok[gid].append(item)

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, entry in path_index.items():
        components[_find(path)].append(entry)

    final_groups: list[dict[str, Any]] = []
    for idx, (root_path, members) in enumerate(components.items(), start=1):
        if should_stop():
            break
        if not any(m.get("role") == SOURCE_ROLE_INBOX for m in members):
            continue
        kinds: list[str] = []
        sizes = {int(m.get("size") or 0) for m in members}
        hashes = {m.get("match_key") for m in members if m.get("match_key") and not str(m.get("match_key")).startswith("size_")}
        if len(hashes) == 1:
            kinds.append("exact")
        elif len(sizes) == 1:
            kinds.append("size")
        grok_overlap: set[str] = set()
        for m in members:
            grok_overlap.update(m.get("grok_ids") or [])
        shared_grok = [
            gid for gid in grok_overlap
            if sum(1 for m in members if gid in (m.get("grok_ids") or [])) >= 2
        ]
        if shared_grok:
            kinds.append("grok_id")
        attached_after: list[dict[str, Any]] = []
        seen_after: set[str] = set()
        pids = {str(m.get("pid")) for m in members if m.get("pid") and m.get("role") in (SOURCE_ROLE_BEFORE, SOURCE_ROLE_INBOX)}
        for pid in pids:
            for after in after_by_pid.get(pid, []):
                ap = after["path"]
                if ap not in seen_after:
                    seen_after.add(ap)
                    attached_after.append(after)
        for gid in grok_overlap:
            for after in after_by_grok.get(gid, []):
                ap = after["path"]
                if ap not in seen_after:
                    seen_after.add(ap)
                    attached_after.append(after)
        if attached_after:
            kinds.append("pid_after" if pids else "grok_after")
            members = members + attached_after
        if len(members) < 2:
            continue
        if not _deletable_items(members):
            continue
        key = f"cross_{idx}_{root_path[-24:]}"
        kinds = kinds or ["cross"]
        final_groups.append(
            build_cross_group(key, members, provisional=False, match_kinds=kinds)
        )
        if idx % 15 == 0:
            groups_by_key = {g["key"]: g for g in final_groups}
            emit(
                idx,
                members[0].get("path") or "",
                phase="hash",
                total=len(components),
                scanned=idx,
                groups=current_groups(),
                message=f"PID / Grok linking {idx}/{len(components)}",
            )

    groups_by_key = {g["key"]: g for g in final_groups}
    emit(
        len(final_groups) or 1,
        label,
        phase="done",
        total=total,
        scanned=total,
        groups=current_groups(),
        force_groups=True,
        message=f"Cross-source done — {len(final_groups)} groups · After files locked",
    )
    return _result(final_groups, hash_candidates=hash_total)


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
    protected_roots: list[str] | None = None,
) -> dict:
    keep = Path(keep_path).resolve() if keep_path else None
    results = []
    deleted = 0
    failed = 0
    bytes_freed = 0
    skipped_protected = 0

    for raw in delete_paths_list:
        target = Path(raw).resolve()
        item = {"path": str(target), "ok": False, "error": None, "bytes": 0}
        try:
            if not target.is_file():
                raise FileNotFoundError(f"Not a file: {target}")
            if keep and target == keep:
                raise ValueError("Cannot delete the keeper file")
            if is_protected_path(target, protected_roots):
                skipped_protected += 1
                raise ValueError("Protected source (pre-scaled / post-upgrade) cannot be deleted from this scan")
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
        "skipped_protected": skipped_protected,
        "bytes_freed": bytes_freed,
        "results": results,
    }


def merge_duplicate_group(
    *,
    keep_path: str,
    group_paths: list[str],
    to_trash: bool = True,
    dry_run: bool = False,
    protected_roots: list[str] | None = None,
) -> dict:
    keep = Path(keep_path).resolve()
    to_delete = []
    skipped_protected = []
    for raw in group_paths:
        p = Path(raw).resolve()
        if p == keep:
            continue
        if is_protected_path(p, protected_roots):
            skipped_protected.append(str(p))
            continue
        if p.is_file():
            to_delete.append(str(p))
    result = delete_paths(
        keep_path=str(keep),
        delete_paths_list=to_delete,
        to_trash=to_trash,
        dry_run=dry_run,
        protected_roots=protected_roots,
    )
    result["skipped_protected_paths"] = skipped_protected
    return result


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


# --- Live scan jobs (pause / resume / cancel) ---

class DupScanJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.controller = ScanController()
        self.lock = threading.Lock()
        self.events: deque[dict[str, Any]] = deque()
        self.pending_progress: dict[str, Any] | None = None
        self.state = "running"
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.finished = False
        self.created_at = time.time()
        self.folder = ""
        self._got_event = threading.Event()

    def emit(self, payload: dict[str, Any]) -> None:
        with self.lock:
            if payload.get("groups") is not None or payload.get("done") or payload.get("error") or payload.get("state") in ("paused", "running"):
                self.events.append(payload)
            elif "count" in payload:
                self.pending_progress = payload
            else:
                self.events.append(payload)
            self._got_event.set()

    def drain(self, timeout: float = 0.12) -> list[dict[str, Any]]:
        self._got_event.wait(timeout)
        with self.lock:
            out = list(self.events)
            self.events.clear()
            if self.pending_progress is not None:
                out.append(self.pending_progress)
                self.pending_progress = None
            self._got_event.clear()
            return out


_JOBS: dict[str, DupScanJob] = {}
_JOBS_LOCK = threading.Lock()


def _prune_jobs(max_age: float = 3600, keep: int = 8) -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [jid for jid, job in _JOBS.items() if job.finished and (now - job.created_at) > max_age]
        for jid in stale:
            _JOBS.pop(jid, None)
        if len(_JOBS) > keep:
            finished = sorted(
                (j for j in _JOBS.values() if j.finished),
                key=lambda j: j.created_at,
            )
            for job in finished[: max(0, len(_JOBS) - keep)]:
                _JOBS.pop(job.id, None)


def get_scan_job(job_id: str) -> DupScanJob | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def find_active_scan_job(folder: str | None = None) -> DupScanJob | None:
    with _JOBS_LOCK:
        for job in _JOBS.values():
            if job.finished:
                continue
            if folder is not None and job.folder != folder:
                continue
            return job
    return None


def job_state(job_id: str) -> str | None:
    job = get_scan_job(job_id)
    if not job:
        return None
    if job.controller.is_paused():
        return "paused"
    return job.state


def control_scan_job(job_id: str, action: str) -> bool:
    job = get_scan_job(job_id)
    if not job:
        return False
    act = (action or "").strip().lower()
    if act == "pause":
        job.controller.pause()
        job.state = "paused"
        job.emit({"state": "paused"})
        return True
    if act == "resume":
        job.controller.resume()
        job.state = "running"
        job.emit({"state": "running"})
        return True
    if act == "cancel":
        job.controller.cancel()
        job.state = "cancelled"
        return True
    return False


def start_scan_job(
    folder: str,
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
    recursive: bool = True,
    whole_system: bool = False,
) -> DupScanJob:
    _prune_jobs()
    job = DupScanJob()
    job.folder = folder or ""
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    job.emit({"job_id": job.id, "state": "running"})

    def run() -> None:
        def on_progress(count, file_path, **kw):
            payload = {"count": count, "file": file_path, "state": job.state, "job_id": job.id}
            payload.update({k: v for k, v in kw.items() if v is not None})
            job.emit(payload)

        try:
            result = scan_folder_duplicates(
                folder,
                deep=deep,
                match_mode=match_mode,
                file_types=file_types,
                recursive=recursive,
                whole_system=whole_system,
                on_progress=on_progress,
                controller=job.controller,
            )
            job.result = result
            job.state = "cancelled" if result.get("cancelled") else "done"
            job.emit({"done": True, "result": result, "state": job.state})
        except Exception as exc:
            job.error = str(exc)
            job.state = "error"
            job.emit({"error": str(exc)})
        finally:
            job.finished = True
            job._got_event.set()

    threading.Thread(target=run, daemon=True, name=f"dup-scan-{job.id}").start()
    return job


def start_cross_scan_job(
    sources: list[dict[str, Any]],
    *,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "video",
    recursive: bool = True,
) -> DupScanJob:
    _prune_jobs()
    job = DupScanJob()
    with _JOBS_LOCK:
        _JOBS[job.id] = job

    def run() -> None:
        def on_progress(count, file_path, **kw):
            payload = {"count": count, "file": file_path, "state": job.state}
            payload.update({k: v for k, v in kw.items() if v is not None})
            job.emit(payload)

        try:
            result = scan_cross_source_duplicates(
                sources,
                deep=deep,
                match_mode=match_mode,
                file_types=file_types,
                recursive=recursive,
                on_progress=on_progress,
                controller=job.controller,
            )
            job.result = result
            job.state = "cancelled" if result.get("cancelled") else "done"
            job.emit({"done": True, "result": result, "state": job.state})
        except Exception as exc:
            job.error = str(exc)
            job.state = "error"
            job.emit({"error": str(exc)})
        finally:
            job.finished = True
            job._got_event.set()

    threading.Thread(target=run, daemon=True, name=f"dup-cross-{job.id}").start()
    return job