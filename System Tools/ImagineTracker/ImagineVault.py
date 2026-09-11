#!/usr/bin/env python3
"""FAFO Imagine Vault — local HAVE/MISS catalog for grok.com/imagine.

Listens on 127.0.0.1:18767. The Chrome overlay talks to this; grok.com never does.
No third-party packages.

Design (v2.4):
  • HTTP binds first. Disk work is background and mtime/fingerprint cheap.
  • Overlay uses GET /snapshot?rev=N (tiny JSON). Full catalog is opt-in.
  • Watch loop skips unchanged folders/files. Deep D: walks are on-demand only.
  • Idle: no overlay traffic → pause scanning, then exit HTTP so the PC can rest.
    Opening Imagine (or Start vault) brings it back in a couple of seconds.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

VERSION = "2.4.0"
HOST = "127.0.0.1"
PORT = 18767
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FAFO" / "ImagineTracker"
DEFAULT_LIBRARY = Path.home() / "Downloads" / "GrokImagine"
X_GROK = Path(r"D:\OUTPUTS\__X_GROK")
NEW_DOWNLOADS = X_GROK / "NEW DOWNLOADS"

UUID_RE = re.compile(
    r"(?:grok-video-|grok-image-|share-videos/|share-images/|generated/|/imagine/(?:post/|saved/)?)"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
UUID_BARE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
GROK_HINT = re.compile(
    r"grok-video|grok-image|vidgen|assets\.grok|imagine-public|share-videos|share-images|imgen\.x\.ai|__x_grok|grokimagine",
    re.I,
)
MEDIA_EXT = {".mp4", ".webm", ".mov", ".m4v", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "node_modules", "__pycache__", ".tmp"}
SHALLOW_NAMES = {"downloads", "desktop", "documents", "pictures", "videos"}

# Pause disk walks after this many seconds without an overlay client.
IDLE_SCAN_SEC = 60.0
# Exit the HTTP process after this many seconds without a real client (health/watchdog do not count).
IDLE_HTTP_SEC = 8 * 60.0
DEMAND_TTL_SEC = 8 * 60.0
PERSIST_DEBOUNCE_SEC = 1.6

_lock = threading.RLock()
_state: dict[str, Any] = {}
_httpd: ThreadingHTTPServer | None = None
_stop = threading.Event()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, obj, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if pretty:
        text = json.dumps(obj, indent=2, ensure_ascii=False)
    else:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def extract_ids(text: str, *, allow_bare: bool = False) -> list[str]:
    """Pull Grok Imagine UUIDs out of a filename, URL, or path."""
    s = str(text or "")
    if not s:
        return []
    found = [m.group(1).lower() for m in UUID_RE.finditer(s)]
    if not found and (allow_bare or GROK_HINT.search(s)):
        found = [m.group(1).lower() for m in UUID_BARE.finditer(s)]
    out: list[str] = []
    for i in found:
        if i not in out:
            out.append(i)
    return out


def ids_for_media_path(path: Path) -> list[str]:
    """IDs from a file on disk. Bare UUIDs only in grok library folders."""
    ids = extract_ids(path.name)
    if ids:
        return ids
    blob = str(path)
    if GROK_HINT.search(path.name) or GROK_HINT.search(blob):
        return extract_ids(path.name, allow_bare=True) or extract_ids(blob, allow_bare=True)
    lower = blob.lower()
    if "grokimagine" in lower or "__x_grok" in lower or "new downloads" in lower:
        return extract_ids(path.name, allow_bare=True)
    return []


def normalize_prompt(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def prompt_hash(text: str) -> str:
    n = normalize_prompt(text)
    if not n:
        return ""
    return hashlib.sha256(n.encode("utf-8")).hexdigest()[:16]


def sentence_parts(text: str) -> list[str]:
    parts = []
    for m in SENTENCE_RE.finditer(text or ""):
        p = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(p) >= 12:
            parts.append(p)
    return parts


def safe_is_dir(path) -> bool:
    try:
        return Path(path).is_dir()
    except OSError:
        return False


def safe_is_file(path) -> bool:
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _norm_dir_list(raw) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in raw or []:
        s = str(p or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _is_shallow_root(path: Path) -> bool:
    name = path.name.lower()
    if name in SHALLOW_NAMES:
        return True
    try:
        home = Path.home()
        if path.resolve() == (home / "Downloads").resolve():
            return True
        if path.resolve() == (home / "Desktop").resolve():
            return True
    except OSError:
        pass
    return False


def default_config() -> dict:
    watch: list[str] = []
    if safe_is_dir(NEW_DOWNLOADS):
        watch.append(str(NEW_DOWNLOADS))
    else:
        watch.append(str(DEFAULT_LIBRARY))
    downloads = Path.home() / "Downloads"
    if safe_is_dir(downloads) and str(downloads) not in watch:
        watch.append(str(downloads))
    deep: list[str] = []
    if safe_is_dir(X_GROK):
        deep.append(str(X_GROK))
    lib = str(NEW_DOWNLOADS) if safe_is_dir(NEW_DOWNLOADS) else str(DEFAULT_LIBRARY)
    return {
        "libraryDir": lib,
        "watchDirs": watch,
        "deepIndexDirs": deep,
        "copyIntoLibrary": False,
        "scanSeconds": 8.0,
        "recoverSidecars": True,
        "watchDepth": 4,
        "idleScanSeconds": IDLE_SCAN_SEC,
        "idleHttpSeconds": IDLE_HTTP_SEC,
    }


def paths() -> dict[str, Path]:
    return {
        "data": DATA,
        "config": DATA / "config.json",
        "catalog": DATA / "catalog.json",
        "unique": DATA / "unique-prompts.json",
        "delta": DATA / "logs" / "prompt-delta.jsonl",
        "activity": DATA / "logs" / "activity.jsonl",
        "seen_sentences": DATA / "seen-sentences.json",
        "fingerprints": DATA / "fingerprints.json",
        "demand": Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "FAFO"
        / "demand-vault.json",
    }


def log_activity(kind: str, **extra) -> None:
    rec = {"ts": utc_now(), "kind": kind, **extra}
    try:
        append_jsonl(paths()["activity"], rec)
    except OSError:
        pass


def _lower_priority() -> None:
    try:
        if os.name == "nt":
            import ctypes

            k32 = ctypes.windll.kernel32
            # BELOW_NORMAL_PRIORITY_CLASS
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass


def note_demand(app: str = "imagine-overlay") -> None:
    rec = {"at": time.time(), "app": app, "which": "vault"}
    try:
        p = paths()["demand"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec), encoding="utf-8")
    except OSError:
        pass
    with _lock:
        _state["last_client"] = time.time()


def demand_fresh(ttl: float = DEMAND_TTL_SEC) -> bool:
    with _lock:
        last = float(_state.get("last_client") or 0)
    if last and (time.time() - last) <= ttl:
        return True
    raw = load_json(paths()["demand"], {}) or {}
    try:
        at = float(raw.get("at") or 0)
    except (TypeError, ValueError):
        at = 0
    return at > 0 and (time.time() - at) <= ttl


def mark_dirty() -> None:
    with _lock:
        _state["dirty"] = True
        _state["rev"] = int(_state.get("rev") or 0) + 1
        _state["compact_stale"] = True


def persist(force: bool = False) -> None:
    p = paths()
    with _lock:
        if not force and not _state.get("dirty"):
            return
        now = time.time()
        if not force and (now - float(_state.get("last_persist") or 0)) < PERSIST_DEBOUNCE_SEC:
            return
        catalog = _state["catalog"]
        unique = _state["unique"]
        seen = _state["seen"]
        cfg = _state["config"]
        fps = _state.get("fingerprints") or {}
        _state["last_persist"] = now
    try:
        save_json(p["catalog"], catalog, pretty=False)
        save_json(p["unique"], unique, pretty=True)
        save_json(p["seen_sentences"], sorted(seen) if len(seen) < 20000 else list(seen)[:20000], pretty=False)
        save_json(p["config"], cfg, pretty=True)
        save_json(p["fingerprints"], fps, pretty=False)
        with _lock:
            _state["dirty"] = False
    except OSError as exc:
        with _lock:
            _state["dirty"] = True
        log_activity("persist-error", error=str(exc)[-300:])


def init_state() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    p = paths()
    dflt = default_config()
    disk = load_json(p["config"], {})
    had_user = bool(isinstance(disk, dict) and str(disk.get("libraryDir") or "").strip())
    cfg = {**dflt, **(disk if isinstance(disk, dict) else {})}
    for k, v in dflt.items():
        if k not in cfg or cfg.get(k) in (None, "", []):
            cfg[k] = v
    if not had_user:
        if safe_is_dir(X_GROK) and str(X_GROK) not in (cfg.get("deepIndexDirs") or []):
            cfg.setdefault("deepIndexDirs", []).append(str(X_GROK))
        if safe_is_dir(NEW_DOWNLOADS) and str(NEW_DOWNLOADS) not in (cfg.get("watchDirs") or []):
            cfg.setdefault("watchDirs", []).insert(0, str(NEW_DOWNLOADS))
            cfg["libraryDir"] = str(NEW_DOWNLOADS)
    cfg["copyIntoLibrary"] = False
    cfg["watchDirs"] = _norm_dir_list(cfg.get("watchDirs"))
    cfg["deepIndexDirs"] = _norm_dir_list(cfg.get("deepIndexDirs"))
    try:
        Path(cfg["libraryDir"]).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    save_json(p["config"], cfg, pretty=True)
    with _lock:
        _state["config"] = cfg
        _state["catalog"] = load_json(p["catalog"], {}) or {}
        _state["unique"] = load_json(p["unique"], {}) or {}
        _state["seen"] = set(load_json(p["seen_sentences"], []) or [])
        _state["fingerprints"] = load_json(p["fingerprints"], {}) or {}
        _state["last_scan"] = 0.0
        _state["last_client"] = 0.0
        _state["last_persist"] = 0.0
        _state["dirty"] = False
        _state["rev"] = 1
        _state["compact_stale"] = True
        _state["compact"] = {}
        _state["folder_stamp"] = {}
        _state["scan"] = {
            "running": False,
            "deep": False,
            "done": 0,
            "added": 0,
            "totalHint": 0,
            "message": "idle",
        }
        _state["started_at"] = time.time()


def record_prompt(item: dict, prompt: str, source: str) -> dict:
    prompt = (prompt or "").strip()
    if not prompt:
        return {"unique": False, "newParts": []}
    h = prompt_hash(prompt)
    new_parts: list[str] = []
    unique = False
    with _lock:
        existing = _state["unique"].get(h)
        if not existing:
            unique = True
            _state["unique"][h] = {
                "hash": h,
                "prompt": prompt,
                "firstId": item.get("id"),
                "firstSeen": utc_now(),
                "count": 1,
                "ids": [item.get("id")] if item.get("id") else [],
            }
        else:
            existing["count"] = int(existing.get("count") or 1) + 1
            existing["lastSeen"] = utc_now()
            iid = item.get("id")
            if iid and iid not in existing.get("ids", []):
                existing.setdefault("ids", []).append(iid)
                if len(existing["ids"]) > 40:
                    existing["ids"] = existing["ids"][-40:]
        for part in sentence_parts(prompt):
            key = normalize_prompt(part)
            if key not in _state["seen"]:
                _state["seen"].add(key)
                new_parts.append(part)
    if unique or new_parts:
        append_jsonl(
            paths()["delta"],
            {
                "ts": utc_now(),
                "id": item.get("id"),
                "hash": h,
                "uniquePrompt": unique,
                "newParts": new_parts,
                "prompt": prompt if unique else "",
                "source": source,
            },
        )
        mark_dirty()
    return {"unique": unique, "newParts": new_parts}


def media_type_for(path: Path) -> str:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "image"
    return "video"


def stage_of(name: str) -> str:
    n = (name or "").lower()
    if "upscale8k" in n or "upscale_8k" in n or "exported_3840" in n:
        return "8k"
    if "upscale4k" in n or "upscale_4k" in n:
        return "4k"
    if "upscale2k" in n or "qhd" in n or "2k_" in n:
        return "2k"
    if "upscaled" in n or "upscale" in n:
        return "up"
    return "orig"


def stage_rank(stage: str) -> int:
    return {"orig": 0, "up": 1, "2k": 2, "4k": 3, "8k": 4}.get(stage or "orig", 0)


def compact_item(v: dict, iid: str = "") -> dict:
    return {
        "id": iid or v.get("id") or "",
        "hasFile": bool(v.get("hasFile")),
        "hasPrompt": bool(v.get("prompt")),
        "filename": v.get("filename") or "",
        "stage": v.get("stage") or "",
        "copies": int(v.get("copies") or 0),
    }


def rebuild_compact() -> dict:
    with _lock:
        compact = {iid: compact_item(v, iid) for iid, v in _state["catalog"].items()}
        _state["compact"] = compact
        _state["compact_stale"] = False
        return compact


def compact_ids() -> dict:
    with _lock:
        if _state.get("compact_stale") or not _state.get("compact"):
            pass
        else:
            return dict(_state["compact"])
    return rebuild_compact()


def stats_view() -> dict:
    with _lock:
        cat = _state["catalog"]
        have = sum(1 for v in cat.values() if v.get("hasFile"))
        with_prompt = sum(1 for v in cat.values() if v.get("prompt"))
        missing_file = sum(1 for v in cat.values() if v.get("prompt") and not v.get("hasFile"))
        idle_for = time.time() - float(_state.get("last_client") or _state.get("started_at") or time.time())
        return {
            "ok": True,
            "service": "imagine-vault",
            "version": VERSION,
            "rev": int(_state.get("rev") or 1),
            "ts": utc_now(),
            "count": len(cat),
            "haveFile": have,
            "withPrompt": with_prompt,
            "missingFile": missing_file,
            "uniquePrompts": len(_state["unique"]),
            "scan": dict(_state.get("scan") or {}),
            "idle": idle_for >= float((_state.get("config") or {}).get("idleScanSeconds") or IDLE_SCAN_SEC),
            "idleForSec": int(idle_for),
            "libraryDir": (_state.get("config") or {}).get("libraryDir"),
            "watchDirs": list((_state.get("config") or {}).get("watchDirs") or []),
            "deepIndexDirs": list((_state.get("config") or {}).get("deepIndexDirs") or []),
        }


def snapshot(rev: int | None = None) -> dict:
    current = int(_state.get("rev") or 1)
    if rev is not None and int(rev) == current and not _state.get("compact_stale"):
        st = stats_view()
        st["unchanged"] = True
        st["items"] = None
        return st
    st = stats_view()
    st["unchanged"] = False
    st["items"] = compact_ids()
    return st


def catalog_view() -> dict:
    st = stats_view()
    with _lock:
        st["items"] = dict(_state["catalog"])
    return st


def pick_preview_path(item: dict) -> str:
    for key in ("pathOrig", "pathPreview", "path"):
        p = item.get(key)
        if p and Path(p).is_file():
            return p
    best = item.get("pathBest") or ""
    if best and Path(best).is_file():
        return best
    return ""


def write_sidecar(item: dict) -> None:
    side_dir = DATA / "sidecars"
    try:
        side_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    sid = side_dir / f"{item['id']}.json"
    body = {
        "id": item["id"],
        "prompt": item.get("prompt") or "",
        "originalPrompt": item.get("originalPrompt") or "",
        "mediaType": item.get("mediaType") or "",
        "url": item.get("url") or "",
        "hdUrl": item.get("hdUrl") or "",
        "thumbUrl": item.get("thumbUrl") or "",
        "title": item.get("title") or "",
        "modelName": item.get("modelName") or "",
        "folders": item.get("folders") or [],
        "tags": item.get("tags") or [],
        "file": item.get("filename") or "",
        "path": item.get("path") or "",
        "updatedAt": item.get("updatedAt"),
    }
    try:
        sid.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        if item.get("path") and NEW_DOWNLOADS.is_dir():
            p = Path(item["path"])
            try:
                if p.is_file() and p.parent.resolve() == NEW_DOWNLOADS.resolve():
                    p.with_name(p.stem + ".json").write_text(
                        sid.read_text(encoding="utf-8"), encoding="utf-8"
                    )
            except OSError:
                pass
    except OSError:
        pass


def recover_prompt_from_neighbors(file_path: Path) -> str:
    stem = file_path.stem
    for cand in (
        file_path.with_suffix(".json"),
        file_path.with_name(stem + ".txt"),
        file_path.with_name(stem + ".prompt.txt"),
    ):
        if not cand.is_file():
            continue
        try:
            raw = cand.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if cand.suffix.lower() == ".json":
            try:
                obj = json.loads(raw)
                for k in ("prompt", "originalPrompt", "text", "query"):
                    if isinstance(obj, dict) and obj.get(k):
                        return str(obj[k]).strip()
            except json.JSONDecodeError:
                pass
        else:
            t = raw.strip()
            if t:
                return t
    return ""


def _touch_item_path(item: dict, path: Path, stage: str, size: int) -> None:
    copies_map = dict(item.get("paths") or {})
    copies_map[str(path)] = {"stage": stage, "size": size}
    item["paths"] = copies_map
    item["copies"] = len(copies_map)
    item["hasFile"] = True
    if stage == "orig" or not item.get("pathOrig"):
        if stage == "orig":
            item["pathOrig"] = str(path)
            item["pathPreview"] = str(path)
            item["filename"] = path.name
            item["path"] = str(path)
            item["bytes"] = size
    if stage_rank(stage) >= stage_rank(item.get("stage") or "orig"):
        item["stage"] = stage
        item["pathBest"] = str(path)
    if not item.get("path"):
        item["path"] = str(path)
        item["filename"] = path.name
        item["bytes"] = size
    if not item.get("pathPreview"):
        item["pathPreview"] = str(path)


def upsert_item(payload: dict, source: str = "ingest") -> dict:
    iid = str(payload.get("id") or "").lower().strip()
    blob = iid + " " + str(payload.get("filename") or "") + " " + str(payload.get("url") or "") + " " + str(
        payload.get("path") or ""
    )
    ids = extract_ids(blob, allow_bare=True)
    if not iid and ids:
        iid = ids[0]
    if not iid:
        return {"ok": False, "error": "no-id"}
    prompt = (payload.get("prompt") or payload.get("originalPrompt") or "").strip()
    with _lock:
        prev = dict(_state["catalog"].get(iid) or {})
        item = {
            **prev,
            "id": iid,
            "filename": payload.get("filename") or prev.get("filename") or "",
            "path": payload.get("path") or prev.get("path") or "",
            "url": payload.get("url") or prev.get("url") or "",
            "hdUrl": payload.get("hdUrl") or prev.get("hdUrl") or "",
            "thumbUrl": payload.get("thumbUrl") or prev.get("thumbUrl") or "",
            "mediaType": payload.get("mediaType") or prev.get("mediaType") or "",
            "title": payload.get("title") or prev.get("title") or "",
            "modelName": payload.get("modelName") or prev.get("modelName") or "",
            "folders": payload.get("folders") or prev.get("folders") or [],
            "tags": payload.get("tags") or prev.get("tags") or [],
            "bytes": payload.get("bytes") or prev.get("bytes") or 0,
            "hasFile": bool(prev.get("hasFile")),
            "copies": int(prev.get("copies") or 0) or (1 if prev.get("hasFile") else 0),
            "stage": prev.get("stage") or payload.get("stage") or "",
            "pathOrig": prev.get("pathOrig") or "",
            "pathBest": prev.get("pathBest") or "",
            "pathPreview": prev.get("pathPreview") or "",
            "paths": dict(prev.get("paths") or {}),
            "source": source or prev.get("source") or "ingest",
            "updatedAt": utc_now(),
            "createdAt": prev.get("createdAt") or utc_now(),
        }
        if prompt:
            item["prompt"] = prompt
            item["originalPrompt"] = payload.get("originalPrompt") or prev.get("originalPrompt") or prompt
        path_s = str(payload.get("path") or "")
        if payload.get("hasFile") is True or (path_s and Path(path_s).is_file()):
            item["hasFile"] = True
            if path_s:
                pp = Path(path_s)
                item["path"] = path_s
                item["filename"] = pp.name
                try:
                    size = pp.stat().st_size
                    item["bytes"] = size
                except OSError:
                    size = int(payload.get("bytes") or 0)
                _touch_item_path(item, pp, stage_of(pp.name), size)
        _state["catalog"][iid] = item
    mark_dirty()
    prompt_info = {"unique": False, "newParts": []}
    if prompt:
        prompt_info = record_prompt(item, prompt, source)
        write_sidecar(item)
    return {"ok": True, "id": iid, "item": item, **prompt_info}


def ingest_file(path: Path, source: str = "scan") -> dict | None:
    if not path.is_file() or path.suffix.lower() not in MEDIA_EXT:
        return None
    ids = ids_for_media_path(path)
    if not ids:
        return None
    iid = ids[0]
    cfg = _state["config"]
    lib = Path(cfg["libraryDir"])
    dest = path
    try:
        src_s = str(path.resolve()).lower()
    except OSError:
        src_s = str(path).lower()
    already_on_d = src_s.startswith(str(X_GROK).lower()) if X_GROK.exists() else False
    if cfg.get("copyIntoLibrary") and not already_on_d:
        try:
            if path.parent.resolve() != lib.resolve():
                lib.mkdir(parents=True, exist_ok=True)
                prefix = "grok-image-" if media_type_for(path) == "image" else "grok-video-"
                dest = lib / f"{prefix}{iid}{path.suffix.lower()}"
                if not dest.exists() or dest.stat().st_size < path.stat().st_size:
                    shutil.copy2(path, dest)
        except OSError:
            dest = path
    prompt = recover_prompt_from_neighbors(path) or recover_prompt_from_neighbors(dest)
    try:
        size = dest.stat().st_size if dest.is_file() else 0
    except OSError:
        size = 0
    return upsert_item(
        {
            "id": iid,
            "path": str(dest),
            "filename": dest.name,
            "hasFile": True,
            "prompt": prompt,
            "mediaType": media_type_for(path),
            "bytes": size,
        },
        source=source,
    )


def fingerprint_known(path: Path, st=None) -> bool:
    """True if this file is already catalogued at the same mtime/size."""
    key = str(path).lower()
    with _lock:
        fp = _state["fingerprints"].get(key)
        if not fp:
            return False
        iid = fp.get("id")
        item = _state["catalog"].get(iid) if iid else None
        if not item or not item.get("hasFile"):
            return False
        if st is None:
            try:
                st = path.stat()
            except OSError:
                return False
        return fp.get("mtime") == st.st_mtime and fp.get("size") == st.st_size


def fast_index_file(path: Path) -> bool:
    """Filename-only HAVE mark. Tracks copies + orig/upscale stage via path map."""
    ids = ids_for_media_path(path)
    if not ids:
        return False
    iid = ids[0]
    stage = stage_of(path.name)
    try:
        st = path.stat()
        size = st.st_size
        mtime = st.st_mtime
    except OSError:
        return False
    if fingerprint_known(path, st):
        return False
    key = str(path).lower()
    with _lock:
        prev = dict(_state["catalog"].get(iid) or {})
        added = not prev.get("hasFile")
        item = {
            **prev,
            "id": iid,
            "hasFile": True,
            "mediaType": media_type_for(path),
            "source": prev.get("source") or "deep-index",
            "updatedAt": utc_now(),
            "createdAt": prev.get("createdAt") or utc_now(),
            "paths": dict(prev.get("paths") or {}),
        }
        _touch_item_path(item, path, stage, size)
        _state["catalog"][iid] = item
        _state["fingerprints"][key] = {"mtime": mtime, "size": size, "id": iid, "stage": stage}
    mark_dirty()
    return added


def folder_stamp(root: Path) -> tuple:
    """Cheap change detector: dir mtime + top-level entry count."""
    try:
        st = root.stat()
        n = 0
        newest = st.st_mtime
        with os.scandir(root) as it:
            for i, ent in enumerate(it):
                n += 1
                if i >= 80:
                    break
                try:
                    newest = max(newest, ent.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    continue
        return (int(st.st_mtime), n, int(newest))
    except OSError:
        return (0, 0, 0)


def folder_unchanged(root: Path) -> bool:
    stamp = folder_stamp(root)
    key = str(root).lower()
    with _lock:
        prev = _state["folder_stamp"].get(key)
        return prev == stamp


def remember_folder_stamp(root: Path) -> None:
    stamp = folder_stamp(root)
    key = str(root).lower()
    with _lock:
        _state["folder_stamp"][key] = stamp


def iter_dir_files(root: Path, recursive: bool, max_depth: int = 8) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    root_s = str(root)
    try:
        if not recursive:
            with os.scandir(root) as it:
                for ent in it:
                    if not ent.is_file():
                        continue
                    ext = os.path.splitext(ent.name)[1].lower()
                    if ext in MEDIA_EXT or ext == ".json":
                        out.append(Path(ent.path))
            return out
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root_s)
            depth = 0 if rel in (".", "") else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in MEDIA_EXT or ext == ".json":
                    out.append(Path(dirpath) / name)
    except OSError:
        pass
    return out


def watch_roots() -> list[Path]:
    cfg = _state["config"]
    roots = [Path(cfg["libraryDir"]), *[Path(p) for p in (cfg.get("watchDirs") or [])]]
    seen: set[str] = set()
    out: list[Path] = []
    for root in roots:
        try:
            key = str(root.resolve()).lower()
        except OSError:
            key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out


def pick_directory(title: str = "Watch folder") -> str:
    desc = title.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        f"$d.Description = '{desc}'; $d.ShowNewFolderButton = $true; "
        "if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"
    )
    try:
        r = subprocess.run(
            [
                os.path.expandvars(r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"),
                "-STA",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def scan_once(deep: bool = False) -> dict:
    added = 0
    updated = 0
    recovered = 0
    skipped = 0
    with _lock:
        _state["scan"] = {
            "running": True,
            "deep": deep,
            "done": 0,
            "added": 0,
            "totalHint": 0,
            "message": "deep index" if deep else "watch folders",
        }
    try:
        if deep:
            for root in [Path(p) for p in (_state["config"].get("deepIndexDirs") or [])]:
                if not safe_is_dir(root):
                    continue
                try:
                    for dirpath, dirnames, filenames in os.walk(root):
                        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
                        folder = Path(dirpath)
                        if folder_unchanged(folder):
                            continue
                        for name in filenames:
                            ext = os.path.splitext(name)[1].lower()
                            if ext not in MEDIA_EXT:
                                continue
                            pth = Path(dirpath) / name
                            if not ids_for_media_path(pth):
                                continue
                            if fast_index_file(pth):
                                added += 1
                            else:
                                skipped += 1
                            with _lock:
                                _state["scan"]["done"] += 1
                                _state["scan"]["added"] = added
                            if _state["scan"]["done"] % 800 == 0:
                                persist()
                        remember_folder_stamp(folder)
                except OSError as exc:
                    log_activity("deep-scan-error", root=str(root), error=str(exc)[-300:])
                    continue
            persist(force=True)
            import_loose_prompts()
            return {"added": added, "updated": 0, "recovered": 0, "skipped": skipped, "total": len(_state["catalog"])}

        cfg = _state["config"]
        depth_default = int(cfg.get("watchDepth") or 4)
        for root in watch_roots():
            if not safe_is_dir(root):
                continue
            if folder_unchanged(root) and not deep:
                skipped += 1
                continue
            recursive = not _is_shallow_root(root)
            depth = 1 if _is_shallow_root(root) else depth_default
            for f in iter_dir_files(root, recursive=recursive, max_depth=depth):
                if f.suffix.lower() == ".json":
                    try:
                        obj = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if isinstance(obj, dict) and (obj.get("id") or obj.get("prompt")):
                        r = upsert_item(obj, source="sidecar")
                        if r.get("ok"):
                            recovered += 1
                    continue
                try:
                    st = f.stat()
                except OSError:
                    continue
                if fingerprint_known(f, st):
                    skipped += 1
                    continue
                ids = ids_for_media_path(f)
                before = _state["catalog"].get(ids[0]) if ids else None
                r = ingest_file(f, source="scan")
                if not r or not r.get("ok"):
                    continue
                with _lock:
                    _state["fingerprints"][str(f).lower()] = {
                        "mtime": st.st_mtime,
                        "size": st.st_size,
                        "id": r.get("id"),
                        "stage": stage_of(f.name),
                    }
                    _state["scan"]["done"] += 1
                    _state["scan"]["added"] = added
                if not before:
                    added += 1
                else:
                    updated += 1
                    if r.get("item", {}).get("prompt") and not (before or {}).get("prompt"):
                        recovered += 1
            remember_folder_stamp(root)
        persist()
        return {
            "added": added,
            "updated": updated,
            "recovered": recovered,
            "skipped": skipped,
            "total": len(_state["catalog"]),
        }
    except OSError as exc:
        log_activity("scan-error", error=str(exc)[-300:])
        return {
            "added": added,
            "updated": updated,
            "recovered": recovered,
            "skipped": skipped,
            "total": len(_state["catalog"]),
            "error": str(exc),
        }
    finally:
        with _lock:
            _state["scan"]["running"] = False
            _state["scan"]["message"] = "deep done" if deep else "idle"
            _state["last_scan"] = time.time()


def import_loose_prompts() -> int:
    candidates = [
        Path.home() / "Desktop" / "text docs" / "Prompts.txt",
        Path.home() / "Desktop" / "Prompts.txt",
        NEW_DOWNLOADS / "Prompts.txt",
        DATA / "Prompts.txt",
    ]
    n = 0
    for path in candidates:
        if not safe_is_file(path):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        blocks = re.split(r"\n\s*\n|^\[[^\]]+\]\s*$", raw, flags=re.M)
        for block in blocks:
            text = block.strip()
            if len(text) < 80:
                continue
            info = record_prompt({"id": "loose:" + path.name}, text, source="prompts-txt")
            if info.get("unique") or info.get("newParts"):
                n += 1
        log_activity("import-prompts", path=str(path), blocks=n)
    if n:
        persist()
    return n


def clients_idle(scan: bool = True) -> bool:
    cfg = _state.get("config") or {}
    limit = float(cfg.get("idleScanSeconds") if scan else cfg.get("idleHttpSeconds") or IDLE_HTTP_SEC)
    if not scan:
        limit = float(cfg.get("idleHttpSeconds") or IDLE_HTTP_SEC)
    last = float(_state.get("last_client") or 0)
    if last <= 0:
        # Just started — give the overlay a few seconds to connect before idling scan.
        started = float(_state.get("started_at") or time.time())
        return (time.time() - started) > (45 if scan else limit)
    return (time.time() - last) >= limit


def scan_loop() -> None:
    first = True
    while not _stop.is_set():
        try:
            sc = _state.get("scan") or {}
            if sc.get("running") and sc.get("deep"):
                time.sleep(1.0)
                continue
            if clients_idle(scan=True) and not first:
                with _lock:
                    _state["scan"]["message"] = "parked"
                time.sleep(4.0)
                continue
            scan_once(deep=False)
            if first:
                first = False
                if (_state.get("config") or {}).get("deepIndexDirs"):
                    threading.Thread(target=lambda: scan_once(deep=True), name="imagine-first-deep", daemon=True).start()
        except Exception:
            log_activity("scan-error", error=traceback.format_exc()[-500:])
        delay = float((_state.get("config") or {}).get("scanSeconds") or 8.0)
        time.sleep(max(4.0, delay))


def idle_watch() -> None:
    """When the overlay is gone, drop the HTTP process so RAM/CPU go back to the PC."""
    while not _stop.is_set():
        time.sleep(8.0)
        if clients_idle(scan=False):
            log_activity("idle-exit", idleForSec=int(time.time() - float(_state.get("last_client") or 0)))
            persist(force=True)
            httpd = _httpd
            if httpd is not None:
                threading.Thread(target=httpd.shutdown, name="imagine-idle-stop", daemon=True).start()
            return


def unique_view(limit: int | None = None) -> dict:
    with _lock:
        rows = sorted(
            _state["unique"].values(),
            key=lambda r: (r.get("lastSeen") or r.get("firstSeen") or ""),
            reverse=True,
        )
        total = len(rows)
        if limit:
            rows = rows[: max(1, min(int(limit), 500))]
        return {"ok": True, "count": total, "prompts": rows}


def delta_since(since: str | None, limit: int = 200) -> dict:
    path = paths()["delta"]
    rows = []
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as fh:
                # Tail without loading a huge log: last ~1.5 MB.
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 1_500_000))
                if size > 1_500_000:
                    fh.readline()
                lines = fh.read().splitlines()
        except OSError:
            lines = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and str(obj.get("ts") or "") <= since:
                continue
            rows.append(obj)
            if len(rows) >= limit:
                break
    return {"ok": True, "rows": rows}


def reveal_item(iid: str) -> bool:
    with _lock:
        item = dict(_state["catalog"].get(iid) or {})
    path = pick_preview_path(item)
    if not path or not Path(path).is_file():
        lib = str((_state.get("config") or {}).get("libraryDir") or "")
        target = lib if lib and Path(lib).exists() else (str(NEW_DOWNLOADS) if NEW_DOWNLOADS.is_dir() else "")
        if target:
            subprocess.Popen(["explorer.exe", target], shell=False)
            return True
        return False
    subprocess.Popen(["explorer.exe", "/select,", str(path)], shell=False)
    return True


def export_prompts_text() -> str:
    rows = unique_view().get("prompts") or []
    blocks = []
    for r in rows:
        p = (r.get("prompt") or "").strip()
        if p:
            blocks.append(p)
    return "\n\n---\n\n".join(blocks) + ("\n" if blocks else "")


class Handler(BaseHTTPRequestHandler):
    server_version = f"ImagineVault/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        msg = fmt % args if args else str(fmt)
        if "/health" in msg or "/snapshot" in msg:
            return
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), msg))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Cache-Control", "no-store")

    def _send_text(self, text: str, ctype: str = "text/plain; charset=utf-8") -> None:
        raw = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _send(self, code: int, obj) -> None:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _send_preview(self, iid: str) -> None:
        with _lock:
            item = dict(_state["catalog"].get(iid) or {})
        path = Path(pick_preview_path(item) or "")
        if not path.is_file():
            self._send(404, {"ok": False, "error": "no-file"})
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range") or ""
        code = 200
        if rng.startswith("bytes="):
            spec = rng[6:].split("-", 1)
            try:
                if spec[0]:
                    start = int(spec[0])
                if len(spec) > 1 and spec[1]:
                    end = int(spec[1])
            except ValueError:
                start, end = 0, size - 1
            end = min(end, size - 1)
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self._cors()
        self.end_headers()
        with path.open("rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(256 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(min(n, 8_000_000))
        try:
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _is_watchdog(self) -> bool:
        ua = (self.headers.get("User-Agent") or "").lower()
        return "watchdog" in ua or "imagine-watch" in ua

    def _touch_if_client(self) -> None:
        if self._is_watchdog():
            return
        note_demand("imagine-http")

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path.rstrip("/") or "/"
        if path in ("/", "/health", "/api/health"):
            # Health is for the supervisor — do not treat it as overlay demand.
            self._send(200, {
                **stats_view(),
                "port": PORT,
            })
            return
        if path in ("/snapshot", "/api/snapshot"):
            self._touch_if_client()
            rev_raw = (q.get("rev") or [None])[0]
            try:
                rev = int(rev_raw) if rev_raw not in (None, "") else None
            except ValueError:
                rev = None
            self._send(200, snapshot(rev))
            return
        if path in ("/catalog", "/api/catalog"):
            self._touch_if_client()
            if (q.get("compact") or ["0"])[0] in ("1", "true"):
                self._send(200, {"ok": True, "rev": int(_state.get("rev") or 1), "count": len(compact_ids()), "items": compact_ids()})
                return
            self._send(200, catalog_view())
            return
        if path in ("/ids", "/api/ids"):
            self._touch_if_client()
            compact = compact_ids()
            self._send(200, {"ok": True, "rev": int(_state.get("rev") or 1), "count": len(compact), "items": compact})
            return
        if path in ("/preview", "/api/preview"):
            self._touch_if_client()
            iid = str((q.get("id") or [""])[0]).lower()
            self._send_preview(iid)
            return
        if path in ("/reveal", "/api/reveal"):
            self._touch_if_client()
            iid = str((q.get("id") or [""])[0]).lower()
            self._send(200, {"ok": reveal_item(iid)})
            return
        if path in ("/export/prompts", "/api/export/prompts"):
            self._touch_if_client()
            self._send_text(export_prompts_text())
            return
        if path in ("/stats", "/api/stats"):
            self._touch_if_client()
            self._send(200, stats_view())
            return
        if path in ("/prompts/unique", "/api/prompts/unique"):
            self._touch_if_client()
            try:
                limit_raw = (q.get("limit") or [None])[0]
                limit = int(limit_raw) if limit_raw not in (None, "") else 80
            except ValueError:
                limit = 80
            self._send(200, unique_view(limit))
            return
        if path in ("/prompts/delta", "/api/prompts/delta"):
            self._touch_if_client()
            since = (q.get("since") or [None])[0]
            try:
                limit = int((q.get("limit") or ["200"])[0] or 200)
            except ValueError:
                limit = 200
            self._send(200, delta_since(since, min(500, max(1, limit))))
            return
        if path in ("/config", "/api/config"):
            self._touch_if_client()
            self._send(200, {"ok": True, "config": _state["config"], "dataDir": str(DATA), "version": VERSION})
            return
        if path in ("/open-library", "/api/open-library"):
            self._touch_if_client()
            lib = str((_state.get("config") or {}).get("libraryDir") or "")
            ok = False
            if lib and Path(lib).exists():
                try:
                    subprocess.Popen(["explorer.exe", lib], shell=False)
                    ok = True
                except Exception:
                    ok = False
            self._send(200, {"ok": ok, "path": lib})
            return
        if path in ("/item", "/api/item"):
            self._touch_if_client()
            iid = str((q.get("id") or [""])[0]).lower()
            self._send(200, {"ok": True, "item": _state["catalog"].get(iid)})
            return
        if path in ("/overlay.js", "/api/overlay.js"):
            overlay = Path(__file__).resolve().parent / "imagine-overlay.js"
            try:
                if overlay.is_file():
                    self._send_text(overlay.read_text(encoding="utf-8"), "application/javascript; charset=utf-8")
                    return
            except OSError:
                pass
            self._send(404, {"ok": False, "error": "no-overlay"})
            return
        self._send(404, {"ok": False, "error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        body = self._body()
        if path in ("/touch", "/api/touch"):
            note_demand(str(body.get("app") or "imagine-overlay"))
            self._send(200, {"ok": True, "idle": False, "rev": int(_state.get("rev") or 1)})
            return
        if path in ("/ingest", "/api/ingest"):
            self._touch_if_client()
            items = body.get("items") if isinstance(body.get("items"), list) else [body]
            results = []
            for it in items:
                if isinstance(it, dict):
                    results.append(upsert_item(it, source=str(body.get("source") or "overlay")))
            persist()
            self._send(200, {"ok": True, "results": results, "rev": int(_state.get("rev") or 1), "total": len(_state["catalog"])})
            return
        if path in ("/scan", "/api/scan"):
            self._touch_if_client()
            deep = bool(body.get("deep", False))
            if deep:
                threading.Thread(target=lambda: scan_once(deep=True), name="imagine-deep", daemon=True).start()
                self._send(200, {"ok": True, "started": True, "deep": True, "total": len(_state["catalog"])})
                return
            self._send(200, {"ok": True, **scan_once(deep=False)})
            return
        if path in ("/import-prompts", "/api/import-prompts"):
            self._touch_if_client()
            n = import_loose_prompts()
            self._send(200, {"ok": True, "imported": n, "unique": len(_state["unique"])})
            return
        if path in ("/idle", "/api/idle"):
            with _lock:
                _state["last_client"] = time.time() - IDLE_HTTP_SEC
            self._send(200, {"ok": True, "parking": True})
            return
        if path in ("/config", "/api/config"):
            self._touch_if_client()
            with _lock:
                nxt = {**_state["config"], **body}
                if "watchDirs" in body:
                    nxt["watchDirs"] = _norm_dir_list(body.get("watchDirs"))
                if "deepIndexDirs" in body:
                    nxt["deepIndexDirs"] = _norm_dir_list(body.get("deepIndexDirs"))
                lib = str(nxt.get("libraryDir") or "").strip()
                if lib:
                    nxt["libraryDir"] = lib
                    try:
                        Path(lib).mkdir(parents=True, exist_ok=True)
                    except OSError:
                        pass
                _state["config"] = nxt
            persist(force=True)
            threading.Thread(target=lambda: scan_once(deep=False), name="imagine-rescan", daemon=True).start()
            self._send(200, {"ok": True, "config": _state["config"]})
            return
        if path in ("/pick-folder", "/api/pick-folder"):
            self._touch_if_client()
            role = str(body.get("role") or "watch").lower()
            title = "Library folder (HAVE files live here)" if role == "library" else "Add a watch folder"
            picked = pick_directory(title)
            if not picked:
                self._send(200, {"ok": False, "cancelled": True})
                return
            with _lock:
                cfg = dict(_state["config"])
                if role == "library":
                    cfg["libraryDir"] = picked
                    dirs = _norm_dir_list(cfg.get("watchDirs"))
                    if picked not in dirs:
                        dirs.insert(0, picked)
                    cfg["watchDirs"] = dirs
                else:
                    dirs = _norm_dir_list(cfg.get("watchDirs"))
                    if picked not in dirs:
                        dirs.append(picked)
                    cfg["watchDirs"] = dirs
                try:
                    Path(cfg["libraryDir"]).mkdir(parents=True, exist_ok=True)
                except OSError:
                    pass
                _state["config"] = cfg
            persist(force=True)
            threading.Thread(target=lambda: scan_once(deep=False), name="imagine-rescan", daemon=True).start()
            self._send(200, {"ok": True, "path": picked, "config": _state["config"]})
            return
        if path in ("/reveal", "/api/reveal"):
            self._touch_if_client()
            iid = str(body.get("id") or "").lower()
            self._send(200, {"ok": reveal_item(iid)})
            return
        if path in ("/unmark", "/api/unmark"):
            self._touch_if_client()
            iid = str(body.get("id") or "").lower()
            with _lock:
                _state["catalog"].pop(iid, None)
            mark_dirty()
            persist(force=True)
            self._send(200, {"ok": True, "total": len(_state["catalog"])})
            return
        self._send(404, {"ok": False, "error": "not-found"})


class VaultServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _win_mutex(name: str):
    if os.name != "nt":
        return None
    try:
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.CreateMutexW(None, True, name)
        if ctypes.get_last_error() == 183:
            return False
        return handle
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _health_ok(timeout: float = 1.5) -> bool:
    try:
        import urllib.request

        req = urllib.request.Request(
            f"http://{HOST}:{PORT}/health",
            headers={"User-Agent": "imagine-watch/2.4"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return int(getattr(res, "status", 200) or 200) < 400
    except Exception:
        return False


def _no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def main() -> None:
    global _httpd
    mutex = _win_mutex("Local\\FAFOImagineVaultHttp")
    if mutex is False:
        print(f"[imagine-vault] already running on port {PORT}", flush=True)
        return
    _lower_priority()
    init_state()
    try:
        httpd = VaultServer((HOST, PORT), Handler)
    except OSError as exc:
        print(f"[imagine-vault] port {PORT} in use — {exc}", flush=True)
        return
    _httpd = httpd
    print(f"[imagine-vault] http://{HOST}:{PORT}  v{VERSION}  data={DATA}", flush=True)
    threading.Thread(target=scan_loop, name="imagine-scan", daemon=True).start()
    threading.Thread(target=idle_watch, name="imagine-idle", daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        persist(force=True)
        try:
            httpd.server_close()
        except Exception:
            pass
        _httpd = None


def run_watch() -> None:
    """Keep the vault HTTP server up while Imagine is in use. Park it when idle."""
    DATA.mkdir(parents=True, exist_ok=True)
    mutex = _win_mutex("Local\\FAFOImagineVaultWatch")
    if mutex is False:
        return
    _lower_priority()
    lock = DATA / "vault-watch.pid"
    stop = DATA / "stop.flag"
    me = os.getpid()
    if lock.is_file():
        try:
            old = int((lock.read_text(encoding="utf-8") or "0").strip() or 0)
        except ValueError:
            old = 0
        if old and old != me and _pid_alive(old):
            return
    lock.write_text(str(me), encoding="utf-8")
    if stop.is_file():
        try:
            stop.unlink()
        except OSError:
            pass
    script = Path(__file__).resolve()
    cwd = str(script.parent)
    py = sys.executable
    stdout = DATA / "stdout.log"
    stderr = DATA / "stderr.log"
    child = None

    def kill_child() -> None:
        nonlocal child
        if child is None:
            return
        if child.poll() is None:
            try:
                child.terminate()
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        child = None

    try:
        while not stop.is_file():
            up = _health_ok()
            wanted = demand_fresh()
            if up and not wanted:
                kill_child()
                time.sleep(10)
                continue
            if up:
                time.sleep(8)
                continue
            if not wanted:
                time.sleep(10)
                continue
            kill_child()
            time.sleep(0.3)
            with stdout.open("a", encoding="utf-8") as out, stderr.open("a", encoding="utf-8") as err:
                child = subprocess.Popen(
                    [py, "-u", script.name],
                    cwd=cwd,
                    stdout=out,
                    stderr=err,
                    creationflags=_no_window_flags(),
                )
            try:
                (DATA / "vault-server.pid").write_text(str(child.pid), encoding="utf-8")
            except OSError:
                pass
            for _ in range(40):
                if _health_ok() or (child and child.poll() is not None) or stop.is_file():
                    break
                time.sleep(0.2)
            time.sleep(2)
    finally:
        kill_child()
        try:
            if lock.is_file() and lock.read_text(encoding="utf-8").strip() == str(me):
                lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    if "--watch" in sys.argv:
        run_watch()
    else:
        main()
