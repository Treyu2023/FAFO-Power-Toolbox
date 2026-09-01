#!/usr/bin/env python3
"""FAFO Imagine Vault — local catalog, unique-prompt table, append-only delta log.

Listens on 127.0.0.1:18767. The Chrome overlay talks to this; grok.com never does.
No third-party packages. Polls watch folders for grok-video / Imagine files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import mimetypes
import subprocess

HOST = "127.0.0.1"
PORT = 18767
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FAFO" / "ImagineTracker"
DEFAULT_LIBRARY = Path.home() / "Downloads" / "GrokImagine"
UUID_RE = re.compile(
    r"(?:grok-video-|grok-image-|share-videos/|share-images/|generated/|/imagine/(?:post/)?)"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
X_GROK = Path(r"D:\OUTPUTS\__X_GROK")
NEW_DOWNLOADS = X_GROK / "NEW DOWNLOADS"
UUID_BARE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
MEDIA_EXT = {".mp4", ".webm", ".mov", ".m4v", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")

_lock = threading.RLock()
_state: dict[str, Any] = {}


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


def extract_ids(text: str) -> list[str]:
    s = str(text or "")
    found = [m.group(1).lower() for m in UUID_RE.finditer(s)]
    if not found and re.search(r"grok-video|vidgen|assets\.grok|imagine-public|share-videos", s, re.I):
        found = [m.group(1).lower() for m in UUID_BARE.finditer(s)]
    out: list[str] = []
    for i in found:
        if i not in out:
            out.append(i)
    return out


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


def default_config() -> dict:
    watch = [
        str(NEW_DOWNLOADS) if NEW_DOWNLOADS.is_dir() else str(DEFAULT_LIBRARY),
        str(Path.home() / "Downloads"),
    ]
    deep = []
    if X_GROK.is_dir():
        deep = [str(X_GROK)]
    return {
        "libraryDir": str(NEW_DOWNLOADS if NEW_DOWNLOADS.is_dir() else DEFAULT_LIBRARY),
        "watchDirs": watch,
        "deepIndexDirs": deep,
        "copyIntoLibrary": False,
        "scanSeconds": 3.0,
        "recoverSidecars": True,
        "watchDepth": 6,
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
    }


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
    # Only seed the D:\OUTPUTS defaults on first run. Never overwrite a saved library.
    if not had_user:
        if X_GROK.is_dir() and str(X_GROK) not in (cfg.get("deepIndexDirs") or []):
            cfg.setdefault("deepIndexDirs", []).append(str(X_GROK))
        if NEW_DOWNLOADS.is_dir() and str(NEW_DOWNLOADS) not in (cfg.get("watchDirs") or []):
            cfg.setdefault("watchDirs", []).insert(0, str(NEW_DOWNLOADS))
            cfg["libraryDir"] = str(NEW_DOWNLOADS)
    cfg["copyIntoLibrary"] = False
    cfg["watchDirs"] = _norm_dir_list(cfg.get("watchDirs"))
    cfg["deepIndexDirs"] = _norm_dir_list(cfg.get("deepIndexDirs"))
    try:
        Path(cfg["libraryDir"]).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    save_json(p["config"], cfg)
    with _lock:
        _state["config"] = cfg
        _state["catalog"] = load_json(p["catalog"], {})
        _state["unique"] = load_json(p["unique"], {})
        _state["seen"] = set(load_json(p["seen_sentences"], []))
        _state["last_scan"] = 0.0
        _state["scan"] = {
            "running": False,
            "deep": False,
            "done": 0,
            "added": 0,
            "totalHint": 0,
            "message": "idle",
        }


def persist() -> None:
    p = paths()
    with _lock:
        save_json(p["catalog"], _state["catalog"], pretty=False)
        save_json(p["unique"], _state["unique"], pretty=True)
        save_json(p["seen_sentences"], sorted(_state["seen"]), pretty=False)
        save_json(p["config"], _state["config"], pretty=True)


def log_activity(kind: str, **extra) -> None:
    rec = {"ts": utc_now(), "kind": kind, **extra}
    append_jsonl(paths()["activity"], rec)


def record_prompt(item: dict, prompt: str, source: str) -> dict:
    """Return {unique: bool, newParts: [str]}."""
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
    return {"unique": unique, "newParts": new_parts}


def upsert_item(payload: dict, source: str = "ingest") -> dict:
    iid = str(payload.get("id") or "").lower().strip()
    ids = extract_ids(iid + " " + str(payload.get("filename") or "") + " " + str(payload.get("url") or ""))
    if not iid and ids:
        iid = ids[0]
    if not iid:
        return {"ok": False, "error": "no-id"}
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
            "source": source or prev.get("source") or "ingest",
            "updatedAt": utc_now(),
            "createdAt": prev.get("createdAt") or utc_now(),
        }
        prompt = (payload.get("prompt") or payload.get("originalPrompt") or "").strip()
        if prompt:
            item["prompt"] = prompt
            item["originalPrompt"] = payload.get("originalPrompt") or prev.get("originalPrompt") or prompt
        if payload.get("hasFile") is True or (payload.get("path") and Path(str(payload["path"])).is_file()):
            item["hasFile"] = True
            item["path"] = str(payload["path"]) if payload.get("path") else item.get("path")
            if payload.get("path"):
                item["filename"] = Path(payload["path"]).name
                try:
                    item["bytes"] = Path(payload["path"]).stat().st_size
                except OSError:
                    pass
        _state["catalog"][iid] = item
    prompt_info = {"unique": False, "newParts": []}
    if prompt:
        prompt_info = record_prompt(item, prompt, source)
        write_sidecar(item)
    return {"ok": True, "id": iid, "item": item, **prompt_info}


def write_sidecar(item: dict) -> None:
    side_dir = DATA / "sidecars"
    side_dir.mkdir(parents=True, exist_ok=True)
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


def ingest_file(path: Path, source: str = "scan") -> dict | None:
    if not path.is_file() or path.suffix.lower() not in MEDIA_EXT:
        return None
    if path.name.endswith(".json"):
        return None
    ids = extract_ids(path.name)
    if not ids and path.suffix.lower() in {".mp4", ".webm", ".mov", ".png", ".webp"}:
        return None
    if not ids:
        return None
    iid = ids[0]
    cfg = _state["config"]
    lib = Path(cfg["libraryDir"])
    dest = path
    src_s = str(path.resolve()).lower()
    already_on_d = src_s.startswith(str(X_GROK).lower()) if X_GROK.exists() else False
    if cfg.get("copyIntoLibrary") and not already_on_d and path.parent.resolve() != lib.resolve():
        lib.mkdir(parents=True, exist_ok=True)
        prefix = "grok-image-" if media_type_for(path) == "image" else "grok-video-"
        dest = lib / f"{prefix}{iid}{path.suffix.lower()}"
        try:
            if not dest.exists() or dest.stat().st_size < path.stat().st_size:
                shutil.copy2(path, dest)
        except OSError:
            dest = path
    prompt = recover_prompt_from_neighbors(path) or recover_prompt_from_neighbors(dest)
    media_type = media_type_for(path)
    return upsert_item(
        {
            "id": iid,
            "path": str(dest),
            "filename": dest.name,
            "hasFile": True,
            "prompt": prompt,
            "mediaType": media_type,
            "bytes": dest.stat().st_size if dest.is_file() else 0,
        },
        source=source,
    )


def media_type_for(path: Path) -> str:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "image"
    return "video"


def _norm_dir_list(raw) -> list[str]:
    out: list[str] = []
    for p in raw or []:
        s = str(p or "").strip()
        if not s:
            continue
        key = s.lower()
        if key not in {x.lower() for x in out}:
            out.append(s)
    return out


def pick_directory(title: str = "Watch folder") -> str:
    """Windows folder picker (STA). Empty string if cancelled."""
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


def iter_dir_files(
    root: Path,
    recursive: bool,
    max_depth: int = 8,
    require_id: bool = False,
) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    root_s = str(root)
    try:
        if not recursive:
            for entry in root.iterdir():
                if entry.is_file() and (entry.suffix.lower() in MEDIA_EXT or entry.suffix.lower() == ".json"):
                    if require_id and entry.suffix.lower() != ".json" and not extract_ids(entry.name):
                        continue
                    out.append(entry)
            return out
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root_s)
            depth = 0 if rel in (".", "") else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() in MEDIA_EXT or p.suffix.lower() == ".json":
                    if require_id and p.suffix.lower() != ".json" and not extract_ids(name):
                        continue
                    out.append(p)
    except OSError:
        pass
    return out


SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "node_modules", "__pycache__"}


def iter_watch_files(deep: bool = False) -> list[Path]:
    cfg = _state["config"]
    depth = int(cfg.get("watchDepth") or 6)
    roots = [Path(cfg["libraryDir"]), *[Path(p) for p in (cfg.get("watchDirs") or [])]]
    seen: set[str] = set()
    out: list[Path] = []
    for root in roots:
        # Nested downloads count. Do not require a UUID in the filename.
        for entry in iter_dir_files(root, recursive=True, max_depth=depth, require_id=False):
            key = str(entry).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
    if deep:
        for root in [Path(p) for p in (cfg.get("deepIndexDirs") or [])]:
            for entry in iter_dir_files(root, recursive=True, max_depth=20, require_id=True):
                key = str(entry).lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(entry)
    return out


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


def pick_preview_path(item: dict) -> str:
    for key in ("pathOrig", "pathPreview", "path"):
        p = item.get(key)
        if p and Path(p).is_file():
            return p
    return item.get("pathBest") or ""


def fast_index_file(path: Path) -> bool:
    """Filename-only HAVE mark. Tracks copies + orig/upscale stage."""
    ids = extract_ids(path.name)
    if not ids:
        return False
    iid = ids[0]
    stage = stage_of(path.name)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    added = False
    with _lock:
        prev = dict(_state["catalog"].get(iid) or {})
        added = not prev.get("hasFile")
        copies = int(prev.get("copies") or 0) + 1
        item = {
            **prev,
            "id": iid,
            "hasFile": True,
            "copies": copies,
            "mediaType": media_type_for(path),
            "source": prev.get("source") or "deep-index",
            "updatedAt": utc_now(),
            "createdAt": prev.get("createdAt") or utc_now(),
        }
        if stage == "orig" or not prev.get("pathOrig"):
            if stage == "orig":
                item["pathOrig"] = str(path)
                item["pathPreview"] = str(path)
                item["filename"] = path.name
                item["path"] = str(path)
                item["bytes"] = size
        if stage_rank(stage) >= stage_rank(prev.get("stage") or "orig"):
            item["stage"] = stage
            item["pathBest"] = str(path)
        if not item.get("path"):
            item["path"] = str(path)
            item["filename"] = path.name
            item["bytes"] = size
        if not item.get("pathPreview"):
            item["pathPreview"] = str(path)
        _state["catalog"][iid] = item
    return added


def scan_once(deep: bool = False) -> dict:
    added = 0
    updated = 0
    recovered = 0
    with _lock:
        _state["scan"] = {
            "running": True,
            "deep": deep,
            "done": 0,
            "added": 0,
            "totalHint": 0,
            "message": "deep index" if deep else "watch folders",
        }
    if deep:
        with _lock:
            for v in _state["catalog"].values():
                v["copies"] = 0
        for root in [Path(p) for p in (_state["config"].get("deepIndexDirs") or [])]:
            if not root.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
                for name in filenames:
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in MEDIA_EXT:
                        continue
                    if not extract_ids(name):
                        continue
                    pth = Path(dirpath) / name
                    if fast_index_file(pth):
                        added += 1
                    with _lock:
                        _state["scan"]["done"] += 1
                        _state["scan"]["added"] = added
                    if _state["scan"]["done"] % 500 == 0:
                        persist()
        persist()
        import_loose_prompts()
        with _lock:
            _state["scan"]["running"] = False
            _state["scan"]["message"] = "deep done"
            _state["last_scan"] = time.time()
        return {"added": added, "updated": 0, "recovered": 0, "total": len(_state["catalog"])}

    for f in iter_watch_files(deep=False):
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
        before = _state["catalog"].get((extract_ids(f.name) or [""])[0])
        r = ingest_file(f, source="scan")
        if not r or not r.get("ok"):
            continue
        if not before:
            added += 1
        else:
            updated += 1
            if r.get("item", {}).get("prompt") and not (before or {}).get("prompt"):
                recovered += 1
        with _lock:
            _state["scan"]["done"] += 1
            _state["scan"]["added"] = added
    persist()
    with _lock:
        _state["scan"]["running"] = False
        _state["scan"]["message"] = "idle"
        _state["last_scan"] = time.time()
    return {"added": added, "updated": updated, "recovered": recovered, "total": len(_state["catalog"])}


def import_loose_prompts() -> int:
    """Load standalone prompt dumps (not tied to UUIDs) into unique-prompts."""
    candidates = [
        Path.home() / "Desktop" / "text docs" / "Prompts.txt",
        Path.home() / "Desktop" / "Prompts.txt",
        NEW_DOWNLOADS / "Prompts.txt",
        DATA / "Prompts.txt",
    ]
    n = 0
    for path in candidates:
        if not path.is_file():
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


def scan_loop() -> None:
    while True:
        try:
            sc = _state.get("scan") or {}
            if sc.get("running") and sc.get("deep"):
                time.sleep(1.0)
                continue
            scan_once(deep=False)
        except Exception:
            log_activity("scan-error", error=traceback.format_exc()[-500:])
        time.sleep(float(_state["config"].get("scanSeconds") or 2.5))


def catalog_view() -> dict:
    with _lock:
        cat = _state["catalog"]
        unique = _state["unique"]
        have = sum(1 for v in cat.values() if v.get("hasFile"))
        with_prompt = sum(1 for v in cat.values() if v.get("prompt"))
        missing_file = sum(1 for v in cat.values() if v.get("prompt") and not v.get("hasFile"))
        return {
            "ok": True,
            "ts": utc_now(),
            "count": len(cat),
            "haveFile": have,
            "withPrompt": with_prompt,
            "missingFile": missing_file,
            "uniquePrompts": len(unique),
            "scan": dict(_state.get("scan") or {}),
            "libraryDir": _state["config"].get("libraryDir"),
            "watchDirs": list(_state["config"].get("watchDirs") or []),
            "deepIndexDirs": list(_state["config"].get("deepIndexDirs") or []),
            "items": cat,
        }


def _compact_ids() -> dict:
    with _lock:
        return {
            iid: {
                "hasFile": bool(v.get("hasFile")),
                "hasPrompt": bool(v.get("prompt")),
                "filename": v.get("filename") or "",
                "stage": v.get("stage") or "",
                "copies": int(v.get("copies") or 0),
            }
            for iid, v in _state["catalog"].items()
        }


def reveal_item(iid: str) -> bool:
    with _lock:
        item = dict(_state["catalog"].get(iid) or {})
    path = pick_preview_path(item)
    if not path or not Path(path).is_file():
        if NEW_DOWNLOADS.is_dir():
            subprocess.Popen(["explorer.exe", str(NEW_DOWNLOADS)], shell=False)
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


def unique_view() -> dict:
    with _lock:
        rows = sorted(
            _state["unique"].values(),
            key=lambda r: (r.get("lastSeen") or r.get("firstSeen") or ""),
            reverse=True,
        )
        return {"ok": True, "count": len(rows), "prompts": rows}


def delta_since(since: str | None, limit: int = 200) -> dict:
    path = paths()["delta"]
    rows = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
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


class Handler(BaseHTTPRequestHandler):
    server_version = "ImagineVault/2.2"

    def log_message(self, fmt: str, *args) -> None:
        if "/health" in str(args[:1]):
            return
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")

    def _send_text(self, text: str, ctype: str = "text/plain; charset=utf-8") -> None:
        raw = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
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

    def _send(self, code: int, obj) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/health", "/api/health"):
            scan = dict(_state.get("scan") or {})
            self._send(200, {
                "ok": True,
                "service": "imagine-vault",
                "port": PORT,
                "ts": utc_now(),
                "count": len(_state.get("catalog") or {}),
                "scan": scan,
                "libraryDir": (_state.get("config") or {}).get("libraryDir"),
                "watchDirs": list((_state.get("config") or {}).get("watchDirs") or []),
            })
            return
        if u.path in ("/catalog", "/api/catalog"):
            q = parse_qs(u.query)
            if (q.get("compact") or ["0"])[0] in ("1", "true"):
                with _lock:
                    compact = _compact_ids()
                self._send(200, {"ok": True, "count": len(compact), "items": compact})
                return
            self._send(200, catalog_view())
            return
        if u.path in ("/ids", "/api/ids"):
            compact = _compact_ids()
            self._send(200, {"ok": True, "count": len(compact), "items": compact})
            return
        if u.path in ("/preview", "/api/preview"):
            iid = str((q.get("id") or [""])[0]).lower()
            self._send_preview(iid)
            return
        if u.path in ("/reveal", "/api/reveal"):
            iid = str((q.get("id") or [""])[0]).lower()
            self._send(200, {"ok": reveal_item(iid)})
            return
        if u.path in ("/export/prompts", "/api/export/prompts"):
            self._send_text(export_prompts_text())
            return
        if u.path in ("/stats", "/api/stats"):
            self._send(200, {k: v for k, v in catalog_view().items() if k != "items"})
            return
        if u.path in ("/prompts/unique", "/api/prompts/unique"):
            self._send(200, unique_view())
            return
        if u.path in ("/prompts/delta", "/api/prompts/delta"):
            since = (q.get("since") or [None])[0]
            limit = int((q.get("limit") or ["200"])[0] or 200)
            self._send(200, delta_since(since, limit))
            return
        if u.path in ("/config", "/api/config"):
            self._send(200, {"ok": True, "config": _state["config"], "dataDir": str(DATA)})
            return
        if u.path in ("/open-library", "/api/open-library"):
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
        if u.path in ("/item", "/api/item"):
            iid = str((q.get("id") or [""])[0]).lower()
            self._send(200, {"ok": True, "item": _state["catalog"].get(iid)})
            return
        self._send(404, {"ok": False, "error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        body = self._body()
        if u.path in ("/ingest", "/api/ingest"):
            items = body.get("items") if isinstance(body.get("items"), list) else [body]
            results = []
            for it in items:
                if isinstance(it, dict):
                    results.append(upsert_item(it, source=str(body.get("source") or "overlay")))
            persist()
            self._send(200, {"ok": True, "results": results, "total": len(_state["catalog"])})
            return
        if u.path in ("/scan", "/api/scan"):
            deep = bool(body.get("deep", True))
            if deep:
                threading.Thread(
                    target=lambda: scan_once(deep=True),
                    name="imagine-deep",
                    daemon=True,
                ).start()
                self._send(200, {"ok": True, "started": True, "deep": True, "total": len(_state["catalog"])})
                return
            self._send(200, {"ok": True, **scan_once(deep=False)})
            return
        if u.path in ("/import-prompts", "/api/import-prompts"):
            n = import_loose_prompts()
            self._send(200, {"ok": True, "imported": n, "unique": len(_state["unique"])})
            return
        if u.path in ("/config", "/api/config"):
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
            persist()
            threading.Thread(target=lambda: scan_once(deep=False), name="imagine-rescan", daemon=True).start()
            self._send(200, {"ok": True, "config": _state["config"]})
            return
        if u.path in ("/pick-folder", "/api/pick-folder"):
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
            persist()
            threading.Thread(target=lambda: scan_once(deep=False), name="imagine-rescan", daemon=True).start()
            self._send(200, {"ok": True, "path": picked, "config": _state["config"]})
            return
        if u.path in ("/reveal", "/api/reveal"):
            iid = str(body.get("id") or "").lower()
            self._send(200, {"ok": reveal_item(iid)})
            return
        if u.path in ("/unmark", "/api/unmark"):
            iid = str(body.get("id") or "").lower()
            with _lock:
                _state["catalog"].pop(iid, None)
            persist()
            self._send(200, {"ok": True, "total": len(_state["catalog"])})
            return
        self._send(404, {"ok": False, "error": "not-found"})


def main() -> None:
    init_state()
    t = threading.Thread(target=scan_loop, name="imagine-scan", daemon=True)
    t.start()
    threading.Thread(target=lambda: scan_once(deep=True), name="imagine-deep", daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[imagine-vault] http://{HOST}:{PORT}  data={DATA}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        persist()
        httpd.server_close()


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
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=timeout) as res:
            return int(getattr(res, "status", 200) or 200) < 400
    except Exception:
        return False


def _no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def run_watch() -> None:
    """Keep the vault HTTP server up. Separate process from the server itself."""
    DATA.mkdir(parents=True, exist_ok=True)
    mutex = None
    if os.name == "nt":
        try:
            import ctypes
            mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Local\\FAFOImagineVaultWatch")
            if ctypes.windll.kernel32.GetLastError() == 183:
                return
        except Exception:
            mutex = None
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
    try:
        while not stop.is_file():
            if _health_ok():
                time.sleep(3)
                continue
            if child is not None and child.poll() is None:
                try:
                    child.kill()
                except Exception:
                    pass
                child = None
                time.sleep(0.4)
            with stdout.open("a", encoding="utf-8") as out, stderr.open("a", encoding="utf-8") as err:
                child = subprocess.Popen(
                    [py, "-u", script.name],
                    cwd=cwd,
                    stdout=out,
                    stderr=err,
                    creationflags=_no_window_flags(),
                )
            (DATA / "vault-server.pid").write_text(str(child.pid), encoding="utf-8")
            for _ in range(50):
                if _health_ok() or child.poll() is not None or stop.is_file():
                    break
                time.sleep(0.2)
            while child.poll() is None and not stop.is_file():
                time.sleep(3)
                if not _health_ok():
                    try:
                        child.kill()
                    except Exception:
                        pass
                    break
            time.sleep(1)
    finally:
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except Exception:
                pass
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
