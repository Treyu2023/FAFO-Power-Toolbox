#!/usr/bin/env python3
"""FAFO Imagine Vault — local HAVE/MISS catalog for grok.com/imagine.

Listens on 127.0.0.1:18767. The Chrome overlay talks to this; grok.com never does.
No required third-party packages (Pillow and ffmpeg are optional, used only by /thumb).

Design (v2.4):
  • HTTP binds first. Disk work is background and mtime/fingerprint cheap.
  • Overlay uses GET /snapshot?rev=N (tiny JSON). Full catalog is opt-in.
  • Watch loop skips unchanged folders/files. Deep D: walks are on-demand only.
  • Idle: no overlay traffic → pause scanning, then exit HTTP so the PC can rest.
    Opening Imagine (or Start vault) brings it back in a couple of seconds.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import itertools
import os
import queue
import re
import secrets
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

VERSION = "2.5.0"
HOST = "127.0.0.1"
PORT = 18767
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FAFO" / "ImagineTracker"
DEFAULT_LIBRARY = Path.home() / "Downloads" / "GrokImagine"
X_GROK = Path(r"D:\OUTPUTS\__X_GROK")
NEW_DOWNLOADS = X_GROK / "NEW DOWNLOADS"
TOOLBOX_ORIGINS = frozenset({"null", "http://127.0.0.87:18765", "http://127.0.0.1:18765"})
GROK_ORIGIN = "https://grok.com"
# Extension origins come only from config.json allowedExtensionIds (unpacked IDs); empty = no extension access.
EXT_ID_RE = re.compile(r"[a-p]{32}")
PAIR_PATHS = ("/pair", "/api/pair")
HEALTH_PATHS = ("/health", "/api/health")
SNAPSHOT_PATHS = ("/snapshot", "/api/snapshot")
OVERLAY_PATHS = ("/overlay.js", "/api/overlay.js")
SIDE_EFFECT_GETS = {"/reveal", "/api/reveal", "/open-library", "/api/open-library"}
TOKEN_HEADER = "X-FAFO-Vault-Token"
TOKEN_FILE_NAME = ".env.vault-token.js"
VAULT_TOKEN = secrets.token_urlsafe(32)
VAULT_HEADER = "X-FAFO-Vault"
# --autostart: always-on headless mode (logon shortcut). No idle exit, no scan parking, restarts without demand.
AUTOSTART = "--autostart" in sys.argv
CONFIG_HEARTBEAT_SEC = 600.0
THUMBS_DIR = DATA / "thumbs"
THUMB_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
THUMB_MAX_BYTES = 4_000_000
THUMB_SRC_MAX_BYTES = 64_000_000
THUMB_WAIT_SEC = 10.0
_thumb_probe_lock = threading.Lock()
_PIL_MOD = None
_PIL_TRIED = False
_FFMPEG = None
_FFMPEG_TRIED = False
_PIL_SEM = threading.BoundedSemaphore(2)
_FFMPEG_SEM = threading.BoundedSemaphore(2)
_thumb_fail: dict[str, int] = {}

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
SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "node_modules", "__pycache__", ".tmp", "_duplicates"}
SHALLOW_NAMES = {"downloads", "desktop", "documents", "pictures", "videos"}

# Pause disk walks after this many seconds without an overlay client.
IDLE_SCAN_SEC = 60.0
# Exit the HTTP process after this many seconds without a real client (health/watchdog do not count).
IDLE_HTTP_SEC = 8 * 60.0
DEMAND_TTL_SEC = 8 * 60.0
PERSIST_DEBOUNCE_SEC = 1.6

_lock = threading.RLock()
_persist_lock = threading.Lock()
_state: dict[str, Any] = {}
_httpd: ThreadingHTTPServer | None = None
_stop = threading.Event()
# Media hash: q1 = sha256("q1|<size>|" + first HASH_EDGE + last HASH_EDGE bytes), 128-bit. One throttled worker.
HASH_EDGE = 2 << 20
HASH_RATE = 8 << 20
_hash_q: "queue.PriorityQueue" = queue.PriorityQueue()   # (prio 0=ingest 1=scan 2=backfill, seq, key, path, event|None)
_hash_seq = itertools.count()
_hash_idx: dict[str, list[str]] = {}                     # mh -> fingerprint keys, earliest first
_hash_pending: set[str] = set()
_hash_skip: set[str] = set()                             # unreadable or outside roots this run


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
    if pretty:
        text = json.dumps(obj, indent=2, ensure_ascii=False)
    else:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    save_text(path, text)


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + str(os.getpid()) + "." + str(threading.get_ident()) + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(6):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt >= 5:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


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
        "hashBytesPerSec": HASH_RATE,
        "allowedExtensionIds": [],
    }


def ext_origins() -> frozenset[str]:
    """chrome-extension:// origins allowed to pair, read from config at request time (edit file + restart)."""
    ids = (_state.get("config") or {}).get("allowedExtensionIds") or []
    if isinstance(ids, str):
        ids = [ids]
    if not isinstance(ids, list):
        return frozenset()
    return frozenset("chrome-extension://" + i for i in ids if isinstance(i, str) and EXT_ID_RE.fullmatch(i))


def _clip_url(raw) -> str:
    s = str(raw or "").strip()
    return s[:2048] if re.match(r"https?://", s, re.I) else ""


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
    now = time.time()
    rec = {"at": now, "app": app, "which": "vault"}
    with _lock:
        _state["last_client"] = now
        if now - float(_state.get("demand_written_at") or 0) < 1.0:
            return
        _state["demand_written_at"] = now
        try:
            p = paths()["demand"]
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + "." + str(os.getpid()) + ".tmp")
            tmp.write_text(json.dumps(rec), encoding="utf-8")
            os.replace(tmp, p)
        except OSError:
            pass


def demand_fresh(ttl: float = DEMAND_TTL_SEC) -> bool | None:
    with _lock:
        last = float(_state.get("last_client") or 0)
    if last and (time.time() - last) <= ttl:
        return True
    try:
        raw = json.loads(paths()["demand"].read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        at = float(raw.get("at"))
    except (TypeError, ValueError):
        return None
    return at > 0 and (time.time() - at) <= ttl


def mark_dirty() -> None:
    with _lock:
        _state["dirty"] = True
        _state["rev"] = int(_state.get("rev") or 0) + 1
        _state["compact_stale"] = True


def persist(force: bool = False) -> None:
    p = paths()
    try:
        with _lock:
            if not force and not _state.get("dirty"):
                return
            now = time.time()
            if not force and (now - float(_state.get("last_persist") or 0)) < PERSIST_DEBOUNCE_SEC:
                return
            seen = _state["seen"]
            texts = [
                (p["catalog"], json.dumps(_state["catalog"], ensure_ascii=False, separators=(",", ":"))),
                (p["unique"], json.dumps(_state["unique"], indent=2, ensure_ascii=False)),
                (
                    p["seen_sentences"],
                    json.dumps(
                        sorted(seen) if len(seen) < 20000 else list(seen)[:20000],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
                (p["config"], json.dumps(_state["config"], indent=2, ensure_ascii=False)),
                (p["fingerprints"], json.dumps(_state.get("fingerprints") or {}, ensure_ascii=False, separators=(",", ":"))),
            ]
            _state["last_persist"] = now
        with _persist_lock:
            for path, text in texts:
                save_text(path, text)
        with _lock:
            _state["dirty"] = False
    except Exception as exc:
        with _lock:
            _state["dirty"] = True
        log_activity("persist-error", error=str(exc)[-300:])


def _keep_corrupt_json(path: Path) -> None:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return
        json.loads(path.read_text(encoding="utf-8"))
        return
    except OSError:
        return
    except Exception:
        pass
    bad = path.with_name(path.name + ".bad-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    try:
        shutil.copy2(path, bad)
    except OSError:
        pass
    log_activity("json-corrupt", file=str(path))


def init_state() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    p = paths()
    dflt = default_config()
    _keep_corrupt_json(p["config"])
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
    prev_run = dict(cfg.get("lastRun") or {}) if isinstance(cfg.get("lastRun"), dict) else {}
    cfg["lastRun"] = {**prev_run, "startedAt": time.time(), "autostart": AUTOSTART}
    save_json(p["config"], cfg, pretty=True)
    _keep_corrupt_json(p["catalog"])
    with _lock:
        _state["config"] = cfg
        _state["catalog"] = load_json(p["catalog"], {}) or {}
        _state["unique"] = load_json(p["unique"], {}) or {}
        _state["seen"] = set(load_json(p["seen_sentences"], []) or [])
        _state["fingerprints"] = load_json(p["fingerprints"], {}) or {}
        _hash_idx.clear()
        hashed = [(k, v) for k, v in _state["fingerprints"].items() if isinstance(v, dict) and v.get("mh")]
        for k, v in sorted(hashed, key=lambda kv: kv[1].get("mtime") or 0):
            _hash_idx.setdefault(v["mh"], []).append(k)
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
        _state["prev_run"] = prev_run


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
        "dupes": int(v.get("dupeCount") or 0),
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
            "autostart": AUTOSTART,
            "lastRun": dict((_state.get("config") or {}).get("lastRun") or {}),
            "hash": {
                "queued": _hash_q.qsize(),
                "backfillLeft": sum(1 for v in (_state.get("fingerprints") or {}).values() if isinstance(v, dict) and not v.get("mh")),
            },
        }


def snapshot(rev: int | None = None) -> dict:
    with _lock:
        cat = _state["catalog"]
        current = int(_state.get("rev") or 1)
        st = {
            "ok": True,
            "rev": current,
            "count": len(cat),
            "haveFile": sum(1 for v in cat.values() if v.get("hasFile")),
        }
        if rev is not None and int(rev) == current:
            st["unchanged"] = True
            st["items"] = None
        else:
            st["unchanged"] = False
            st["items"] = {iid: {"hasFile": bool(v.get("hasFile"))} for iid, v in cat.items()}
        return st


def catalog_view() -> dict:
    st = stats_view()
    with _lock:
        st["items"] = dict(_state["catalog"])
    return st


def catalog_page(q: dict) -> dict:
    try:
        offset = max(0, int((q.get("offset") or ["0"])[0]))
    except ValueError:
        offset = 0
    try:
        limit = int((q.get("limit") or ["120"])[0])
    except ValueError:
        limit = 120
    limit = max(1, min(500, limit))
    tab = (q.get("tab") or ["all"])[0]
    if tab not in ("all", "miss", "have"):
        tab = "all"
    mtype = (q.get("type") or [""])[0]
    if mtype not in ("", "video", "image"):
        mtype = ""
    needle = str((q.get("q") or [""])[0]).strip().lower()[:200]

    def s(x) -> str:
        return "" if x is None else str(x)

    with _lock:
        rev = _state.get("rev")
        rows = list(_state["catalog"].items())
    rows.reverse()
    filtered = []
    for iid, v in rows:
        if tab == "miss" and v.get("hasFile"):
            continue
        if tab == "have" and not v.get("hasFile"):
            continue
        if mtype and (v.get("mediaType") or "") != mtype:
            continue
        if needle:
            tags = " ".join(str(t) for t in v["tags"]) if isinstance(v.get("tags"), list) else ""
            blob = " ".join([s(v.get("filename")), s(v.get("prompt")), s(v.get("id")), s(v.get("title")), tags]).lower()
            if needle not in blob:
                continue
        filtered.append((iid, v))
    total = len(filtered)
    page = filtered[offset:offset + limit]
    items = []
    for iid, v in page:
        items.append({
            "id": v.get("id") or iid,
            "hasFile": bool(v.get("hasFile")),
            "mediaType": v.get("mediaType") or "",
            "filename": v.get("filename") or "",
            "title": v.get("title") or "",
            "prompt": str(v.get("prompt") or "")[:300],
            "thumbUrl": v.get("thumbUrl") or "",
            "thumb": thumb_kind(v),
            "dupeCount": int(v.get("dupeCount") or 0),
        })
    nxt = offset + len(page)
    return {
        "ok": True,
        "rev": rev,
        "total": total,
        "offset": offset,
        "limit": limit,
        "nextOffset": nxt if nxt < total else None,
        "items": items,
    }


def pick_preview_path(item: dict) -> str:
    for key in ("pathOrig", "pathPreview", "path"):
        p = item.get(key)
        if p and Path(p).is_file():
            return p
    best = item.get("pathBest") or ""
    if best and Path(best).is_file():
        return best
    return ""


def _pil():
    global _PIL_MOD, _PIL_TRIED
    with _thumb_probe_lock:
        if not _PIL_TRIED:
            try:
                from PIL import Image, ImageOps

                _PIL_MOD = (Image, ImageOps)
            except Exception:
                _PIL_MOD = None
            _PIL_TRIED = True
        return _PIL_MOD


def _ffmpeg():
    global _FFMPEG, _FFMPEG_TRIED
    with _thumb_probe_lock:
        if not _FFMPEG_TRIED:
            try:
                _FFMPEG = shutil.which("ffmpeg")
            except Exception:
                _FFMPEG = None
            _FFMPEG_TRIED = True
        return _FFMPEG


def thumb_kind(v: dict) -> str:
    if not v.get("hasFile") or not THUMB_ID_RE.fullmatch(str(v.get("id") or "").lower()):
        return ""
    if (v.get("mediaType") or "") == "image":
        return "img" if _pil() else ""
    return "poster" if _ffmpeg() else ""


def _thumb_source(item: dict) -> tuple[Path | None, str]:
    outside = False
    for key in ("pathOrig", "pathPreview", "path", "pathBest"):
        p = item.get(key)
        if not p:
            continue
        if not path_allowed(p):
            outside = True
            continue
        if Path(str(p)).is_file():
            return (Path(str(p)), "")
    return (None, "path-outside-roots" if outside else "no-file")


def _thumb_cache_path(iid: str) -> Path | None:
    c = THUMBS_DIR / (iid + ".jpg")
    if os.path.normcase(os.path.realpath(c.parent)) != os.path.normcase(os.path.realpath(THUMBS_DIR)):
        return None
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    return c


def _make_thumb(src: Path, src_st, cache: Path, iid: str, is_image: bool) -> bool:
    tmp = THUMBS_DIR / f"{iid}.{os.getpid()}.{threading.get_ident()}.tmp.jpg"
    ok = False
    try:
        if is_image:
            mods = _pil()
            if mods and src_st.st_size <= THUMB_SRC_MAX_BYTES:
                Image, ImageOps = mods
                with Image.open(src) as im0:
                    im0.draft("RGB", (640, 640))
                    im = ImageOps.exif_transpose(im0)
                    im.thumbnail((320, 320))
                    im = im if im.mode == "RGB" else im.convert("RGB")
                    im.save(tmp, "JPEG", quality=80, optimize=True)
                ok = True
        else:
            ff = _ffmpeg()
            if ff:
                src_abs = os.path.realpath(src)
                for ss in ("1", "0"):
                    args = [ff, "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-ss", ss, "-i", "file:" + src_abs,
                            "-frames:v", "1", "-an",
                            "-vf", "scale=320:320:force_original_aspect_ratio=decrease:force_divisible_by=2",
                            "-q:v", "5", "-update", "1", "-y", str(tmp)]
                    try:
                        res = subprocess.run(
                            args,
                            shell=False,
                            timeout=10,
                            capture_output=True,
                            stdin=subprocess.DEVNULL,
                            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
                        )
                    except subprocess.TimeoutExpired:
                        break
                    if res.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 0:
                        ok = True
                        break
        if ok:
            os.utime(tmp, ns=(src_st.st_atime_ns, src_st.st_mtime_ns))
            os.replace(tmp, cache)
    except Exception:
        ok = False
    if not ok:
        try:
            tmp.unlink()
        except OSError:
            pass
        with _thumb_probe_lock:
            _thumb_fail[iid] = src_st.st_mtime_ns
    return ok


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
            cur_orig = str(item.get("pathOrig") or "")
            repoint = (
                not cur_orig
                or not Path(cur_orig).is_file()
                or os.path.normcase(os.path.realpath(cur_orig)) == os.path.normcase(os.path.realpath(str(path)))
            )
            if repoint:
                item["pathOrig"] = str(path)
            item["pathPreview"] = str(path)
            if repoint:
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
    post_id = str(payload.get("postId") or "").strip().lower()
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
            "referrer": _clip_url(payload.get("referrer")) or prev.get("referrer") or "",
            "postId": post_id if THUMB_ID_RE.fullmatch(post_id) else (prev.get("postId") or ""),
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
    enqueue_hash(path, 1)
    mark_dirty()
    return added


def folder_stamp(root: Path, depth: int = 0) -> tuple:
    """Cheap change detector: directory count + newest directory mtime, down to depth."""
    root_s = str(root)
    count = 0
    newest = 0
    try:
        for dirpath, dirnames, _filenames in os.walk(root_s):
            rel = os.path.relpath(dirpath, root_s)
            d = 0 if rel in (".", "") else rel.count(os.sep) + 1
            if d > depth:
                dirnames[:] = []
                continue
            dirnames[:] = [x for x in dirnames if x.lower() not in SKIP_DIRS]
            count += 1
            try:
                newest = max(newest, os.stat(dirpath).st_mtime_ns)
            except OSError:
                continue
    except OSError:
        return (0, 0)
    return (count, newest)


def folder_unchanged(root: Path, depth: int = 0) -> bool:
    stamp = folder_stamp(root, depth)
    key = str(root).lower()
    with _lock:
        prev = _state["folder_stamp"].get(key)
        return prev == stamp


def remember_folder_stamp(root: Path, depth: int = 0) -> None:
    stamp = folder_stamp(root, depth)
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


def _allowed_roots() -> list[str]:
    cfg = _state.get("config") or {}
    return [
        os.path.normcase(os.path.realpath(str(s)))
        for s in [cfg.get("libraryDir"), *(cfg.get("watchDirs") or []), *(cfg.get("deepIndexDirs") or [])]
        if str(s or "").strip()
    ]


def path_allowed(p: str | Path) -> bool:
    if not p or "\x00" in str(p):
        return False
    real = os.path.normcase(os.path.realpath(str(p)))
    for r in _allowed_roots():
        base = r.rstrip("\\/")
        if real == base or real.startswith(base + os.sep):
            return True
    return False


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


def _bad_root(p) -> bool:
    real = os.path.normcase(os.path.realpath(str(p)))
    if os.path.dirname(real) == real:
        return True
    for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        v = os.environ.get(key)
        if not v:
            continue
        base = os.path.normcase(os.path.realpath(os.path.expandvars(v))).rstrip("\\/")
        if real == base or real.startswith(base + os.sep):
            return True
    return False


def apply_picked_root(role: str, picked: str) -> tuple[int, dict]:
    if not picked:
        return 200, {"ok": False, "cancelled": True}
    if _bad_root(picked):
        return 403, {"ok": False, "error": "bad-root"}
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
    return 200, {"ok": True, "path": picked, "config": _state["config"]}


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
            recursive = not _is_shallow_root(root)
            depth = 1 if _is_shallow_root(root) else depth_default
            if folder_unchanged(root, depth if recursive else 0) and not deep:
                skipped += 1
                continue
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
                enqueue_hash(f, 1)
                if not before:
                    added += 1
                else:
                    updated += 1
                    if r.get("item", {}).get("prompt") and not (before or {}).get("prompt"):
                        recovered += 1
            remember_folder_stamp(root, depth if recursive else 0)
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
            run = (_state.get("config") or {}).setdefault("lastRun", {})
            if isinstance(run, dict):
                run["lastScanAt"] = _state["last_scan"]


def _in_dup_dir(p) -> bool:
    return any(part.lower() == "_duplicates" for part in re.split(r"[\\/]+", str(p)))


def media_hash(p: Path, rate: float = HASH_RATE) -> str | None:
    """q1 content hash: whole file up to 2*HASH_EDGE, else head + tail. None if the file changed meanwhile."""
    st = p.stat()
    size = st.st_size
    h = hashlib.sha256(b"q1|%d|" % size)
    rate = max(float(rate or HASH_RATE), 64 * 1024)
    t0 = time.monotonic()
    done = 0

    def take(f, n: int) -> bool:
        nonlocal done
        while n > 0 and not _stop.is_set():
            b = f.read(min(1 << 20, n))
            if not b:
                break
            h.update(b)
            n -= len(b)
            done += len(b)
            lag = done / rate - (time.monotonic() - t0)   # bytes/sec cap
            if lag > 0:
                time.sleep(lag)
        return n == 0

    with open(p, "rb", buffering=0) as f:
        if size <= 2 * HASH_EDGE:
            ok = take(f, size)
        else:
            ok = take(f, HASH_EDGE)
            if ok:
                f.seek(size - HASH_EDGE)
                ok = take(f, HASH_EDGE)
    if not ok:
        return None
    st2 = p.stat()
    if (st2.st_size, st2.st_mtime) != (size, st.st_mtime):
        return None   # still being written: backfill retries it later
    return "q1:" + h.hexdigest()[:32]


def enqueue_hash(p, prio: int = 1, ev=None) -> bool:
    if _in_dup_dir(p):
        return False
    key = str(p).lower()
    with _lock:
        if ev is None and key in _hash_pending:
            return False
        _hash_pending.add(key)
    _hash_q.put((prio, next(_hash_seq), key, str(p), ev))
    return True


def enqueue_backfill(n: int = 50) -> int:
    """Queue unhashed fingerprints under the configured roots, oldest mtime first (originals before re-downloads)."""
    with _lock:
        cand = sorted(
            (float(v.get("mtime") or 0), k)
            for k, v in (_state.get("fingerprints") or {}).items()
            if isinstance(v, dict) and not v.get("mh") and k not in _hash_pending and k not in _hash_skip
        )
    out = 0
    for _mt, k in cand:
        if out >= n:
            break
        if _in_dup_dir(k) or not path_allowed(k):
            with _lock:
                _hash_skip.add(k)
            continue
        if enqueue_hash(k, 2):
            out += 1
    return out


def apply_hash(key: str, p: str, mh: str) -> dict:
    """Dupe = same content as an earlier-indexed copy that is still on disk. A moved file is not a dupe."""
    with _lock:
        fp = _state["fingerprints"].setdefault(key, {})
        old = fp.get("mh")
        if old and old != mh and key in _hash_idx.get(old, []):
            _hash_idx[old].remove(key)
        fp["mh"] = mh
        lst = _hash_idx.setdefault(mh, [])
        prior = lst[: lst.index(key)] if key in lst else list(lst)
        if key not in lst:
            lst.append(key)
        iid = fp.get("id")
    others = [k for k in prior if k != key and os.path.isfile(k)]
    with _lock:
        item = _state["catalog"].get(iid) if iid else None
        if item is not None:
            pmap = item.get("paths") or {}
            pe = next((v for k2, v in pmap.items() if k2.lower() == key and isinstance(v, dict)), None)
            if pe is not None:
                pe["mh"] = mh
                if others:
                    pe["dupeOf"] = others[0]
                else:
                    pe.pop("dupeOf", None)
            item.setdefault("mediaHash", mh)
            item["dupeCount"] = sum(1 for v in pmap.values() if isinstance(v, dict) and v.get("dupeOf"))
        dupe_id = (_state["fingerprints"].get(others[0]) or {}).get("id") if others else None
    mark_dirty()
    return {"dupe": bool(others), "dupeOf": ({"id": dupe_id, "path": others[0]} if others else None), "mediaHash": mh}


def hash_worker() -> None:
    if os.name == "nt":
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            k32.SetThreadPriority(k32.GetCurrentThread(), 0x00010000)   # THREAD_MODE_BACKGROUND_BEGIN: low I/O + CPU
        except Exception:
            pass
    while not _stop.is_set():
        try:
            _prio, _seq, key, p, ev = _hash_q.get(timeout=5)
        except queue.Empty:
            try:
                enqueue_backfill(50)   # lazy backfill only when idle
            except Exception:
                log_activity("hash-error", error=traceback.format_exc()[-300:])
            continue
        mh = None
        verdict = None
        try:
            mh = media_hash(Path(p), float((_state.get("config") or {}).get("hashBytesPerSec") or HASH_RATE))
        except OSError:
            with _lock:
                _hash_skip.add(key)
        except Exception:
            log_activity("hash-error", error=traceback.format_exc()[-300:])
        finally:
            with _lock:
                _hash_pending.discard(key)
        if mh:
            try:
                verdict = apply_hash(key, p, mh)
            except Exception:
                log_activity("hash-error", error=traceback.format_exc()[-300:])
        if ev is not None:
            ev.result = verdict
            ev.set()
        time.sleep(0.05)


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
    last_hb = time.time()
    while not _stop.is_set():
        try:
            if time.time() - last_hb >= CONFIG_HEARTBEAT_SEC:
                # lastRun survives a hard logoff even when nothing else marks the state dirty.
                last_hb = time.time()
                with _lock:
                    text = json.dumps(_state["config"], indent=2, ensure_ascii=False)
                with _persist_lock:
                    save_text(paths()["config"], text)
            sc = _state.get("scan") or {}
            if sc.get("running") and sc.get("deep"):
                time.sleep(1.0)
                continue
            if not AUTOSTART and clients_idle(scan=True) and not first:
                with _lock:
                    _state["scan"]["message"] = "parked"
                time.sleep(4.0)
                continue
            r = scan_once(deep=False)
            if first:
                first = False
                prev = _state.get("prev_run") or {}
                log_activity("catch-up", since=prev.get("lastScanAt"), added=r.get("added"), updated=r.get("updated"))
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
            try:
                persist(force=True)
            except Exception as exc:
                log_activity("persist-error", error=str(exc)[-300:])
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
            if not path_allowed(target):
                return "forbidden"
            try:
                subprocess.Popen(["explorer.exe", target], shell=False)
            except OSError:
                return False
            return True
        return False
    if not path_allowed(path):
        return "forbidden"
    try:
        subprocess.Popen(["explorer.exe", "/select,", str(path)], shell=False)
    except OSError:
        return False
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
        if "/health" in msg or "/snapshot" in msg or "/preview" in msg or "/thumb" in msg:
            return
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), msg))

    def _token_ok(self) -> bool:
        tok = (self.headers.get(TOKEN_HEADER) or "").encode("utf-8", "replace")
        return hmac.compare_digest(tok, VAULT_TOKEN.encode("ascii"))

    def _gate(self, method: str) -> bool:
        self._acao = None
        path = urlparse(self.path).path.rstrip("/") or "/"
        origin = self.headers.get("Origin")
        mut = method == "POST" or (method == "GET" and path in SIDE_EFFECT_GETS)
        err = None
        if origin is None:
            # Native/CLI callers: mutating routes need the run token.
            if mut and not self._token_ok():
                err = "bad-token"
        elif origin in TOOLBOX_ORIGINS:
            self._acao = origin
            if origin == "null" and method != "OPTIONS" and not self._token_ok():
                err = "bad-token"
        elif origin in ext_origins():
            # Allowlisted extension: token on every route except /health, /pair and preflight.
            self._acao = origin
            if method != "OPTIONS" and path not in PAIR_PATHS + HEALTH_PATHS and not self._token_ok():
                err = "bad-token"
        elif origin == GROK_ORIGIN and path in SNAPSHOT_PATHS + OVERLAY_PATHS and method in ("GET", "OPTIONS"):
            self._acao = origin
        else:
            err = "pair-forbidden" if path in PAIR_PATHS else "origin-forbidden"
        if err is None and mut and self.headers.get(VAULT_HEADER) != "1":
            err = "missing-header"
        if err is None:
            return True
        # bad-token keeps the exact caller origin ("null" page or allowlisted extension) so it can read the JSON and re-pair.
        self._acao = origin if err == "bad-token" and origin is not None else None
        raw = json.dumps({"ok": False, "error": err}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.close_connection = True
        self.send_response(403)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        if self._acao:
            self.send_header("Access-Control-Allow-Origin", self._acao)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(raw)
        return False

    def _cors(self, cache: str = "no-store") -> None:
        if self._acao:
            self.send_header("Access-Control-Allow-Origin", self._acao)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS" if self._acao == GROK_ORIGIN else "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, X-FAFO-Vault, X-FAFO-Vault-Token")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Cache-Control", cache)

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
        if not path_allowed(path):
            self._send(403, {"ok": False, "error": "path-outside-roots"})
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
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    chunk = fh.read(min(256 * 1024, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _send_thumb(self, iid: str) -> None:
        with _lock:
            item = dict(_state["catalog"].get(iid) or {})
        if not item:
            self._send(404, {"ok": False, "error": "no-thumb"})
            return
        src, err = _thumb_source(item)
        if src is None:
            if err == "path-outside-roots":
                self._send(403, {"ok": False, "error": "path-outside-roots"})
            else:
                self._send(404, {"ok": False, "error": "no-thumb"})
            return
        try:
            src_st = src.stat()
            cache = _thumb_cache_path(iid)
        except OSError:
            self._send(404, {"ok": False, "error": "no-thumb"})
            return
        if cache is None:
            self._send(400, {"ok": False, "error": "bad-id"})
            return

        def cache_valid() -> bool:
            try:
                return cache.stat().st_mtime_ns == src_st.st_mtime_ns
            except OSError:
                return False

        def serve(how: str) -> None:
            try:
                if cache.stat().st_size > THUMB_MAX_BYTES:
                    self._send(413, {"ok": False, "error": "too-large"})
                    return
                raw = cache.read_bytes()
            except OSError:
                self._send(404, {"ok": False, "error": "no-thumb"})
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("X-Thumb", how)
                self._cors(cache="private, max-age=86400")
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        if cache_valid():
            serve("hit")
            return
        with _thumb_probe_lock:
            known_bad = _thumb_fail.get(iid) == src_st.st_mtime_ns
        if known_bad:
            self._send(404, {"ok": False, "error": "no-thumb"})
            return
        is_image = (item.get("mediaType") or "") == "image"
        if (is_image and not _pil()) or (not is_image and not _ffmpeg()):
            self._send(404, {"ok": False, "error": "no-thumb"})
            return
        sem = _PIL_SEM if is_image else _FFMPEG_SEM
        if not sem.acquire(timeout=THUMB_WAIT_SEC):
            raw = json.dumps({"ok": False, "error": "busy"}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            try:
                self.send_response(503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Retry-After", "2")
                self._cors()
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        try:
            if cache_valid():
                how = "hit"
            elif _make_thumb(src, src_st, cache, iid, is_image):
                how = "made"
            else:
                how = ""
        finally:
            sem.release()
        if not how:
            self._send(404, {"ok": False, "error": "no-thumb"})
            return
        serve(how)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._gate("OPTIONS"):
            return
        self.send_response(204)
        self._cors()
        if self.headers.get("Access-Control-Request-Private-Network") is not None:
            self.send_header("Access-Control-Allow-Private-Network", "true")
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
        if not self._gate("GET"):
            return
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
        if path in PAIR_PATHS:
            # The run token goes only to an allowlisted extension origin that sent X-FAFO-Vault: 1.
            if self.headers.get("Origin") in ext_origins() and self.headers.get(VAULT_HEADER) == "1":
                self._send(200, {"ok": True, "token": VAULT_TOKEN})
            else:
                self._send(403, {"ok": False, "error": "pair-forbidden"})
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
            if "offset" in q or "limit" in q:
                self._send(200, catalog_page(q))
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
        if path in ("/thumb", "/api/thumb"):
            iid = str((q.get("id") or [""])[0]).lower()
            if not THUMB_ID_RE.fullmatch(iid):
                self._send(400, {"ok": False, "error": "bad-id"})
                return
            self._touch_if_client()
            self._send_thumb(iid)
            return
        if path in ("/reveal", "/api/reveal"):
            self._touch_if_client()
            iid = str((q.get("id") or [""])[0]).lower()
            r = reveal_item(iid)
            if r == "forbidden":
                self._send(403, {"ok": False, "error": "path-outside-roots"})
                return
            self._send(200, {"ok": bool(r)})
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
        if not self._gate("POST"):
            return
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
            waits = []
            for it in items:
                if isinstance(it, dict):
                    if str(it.get("path") or "").strip() and not path_allowed(it["path"]):
                        results.append({"ok": False, "error": "path-outside-roots", "id": str(it.get("id") or "")})
                        continue
                    r = upsert_item(it, source=str(body.get("source") or "overlay"))
                    if r.get("ok"):
                        r.update({"dupe": None, "dupeOf": None, "mediaHash": None})
                        pth = str(it.get("path") or "").strip()
                        if pth and os.path.isfile(pth):
                            try:
                                st = os.stat(pth)
                                with _lock:
                                    _state["fingerprints"][pth.lower()] = {
                                        "mtime": st.st_mtime,
                                        "size": st.st_size,
                                        "id": r.get("id"),
                                        "stage": stage_of(Path(pth).name),
                                    }
                                ev = threading.Event()
                                ev.result = None
                                if enqueue_hash(pth, 0, ev):
                                    waits.append((r, ev))
                            except OSError:
                                pass
                    results.append(r)
            deadline = time.monotonic() + 3.0
            for r, ev in waits:
                if ev.wait(max(0.0, deadline - time.monotonic())) and ev.result:
                    r.update(ev.result)
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
            if AUTOSTART:
                self._send(200, {"ok": True, "parking": False})
                return
            with _lock:
                _state["last_client"] = time.time() - IDLE_HTTP_SEC
            self._send(200, {"ok": True, "parking": True})
            return
        if path in ("/config", "/api/config"):
            self._touch_if_client()
            body.pop("lastRun", None)
            body.pop("allowedExtensionIds", None)   # allowlist is file-only; a token holder can't widen it over HTTP
            with _lock:
                have = set(_allowed_roots())
                asked = []
                if "libraryDir" in body and str(body["libraryDir"] or "").strip():
                    asked.append(body["libraryDir"])
                if "watchDirs" in body:
                    asked.extend(_norm_dir_list(body.get("watchDirs")))
                if "deepIndexDirs" in body:
                    asked.extend(_norm_dir_list(body.get("deepIndexDirs")))
                bad = [a for a in asked if os.path.normcase(os.path.realpath(str(a))) not in have]
                if not bad:
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
            if bad:
                self._send(403, {"ok": False, "error": "roots-via-picker-only"})
                return
            persist(force=True)
            threading.Thread(target=lambda: scan_once(deep=False), name="imagine-rescan", daemon=True).start()
            self._send(200, {"ok": True, "config": _state["config"]})
            return
        if path in ("/pick-folder", "/api/pick-folder"):
            self._touch_if_client()
            role = str(body.get("role") or "watch").lower()
            title = "Library folder (HAVE files live here)" if role == "library" else "Add a watch folder"
            picked = pick_directory(title)
            code, body = apply_picked_root(role, picked)
            self._send(code, body)
            return
        if path in ("/reveal", "/api/reveal"):
            self._touch_if_client()
            iid = str(body.get("id") or "").lower()
            r = reveal_item(iid)
            if r == "forbidden":
                self._send(403, {"ok": False, "error": "path-outside-roots"})
                return
            self._send(200, {"ok": bool(r)})
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
    # Windows SO_REUSEADDR lets a second vault bind the same port; keep the bind exclusive there.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        sys.stderr.write(f"[imagine-vault] handler error: {exc!r}\n")


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


def _token_page_dir() -> Path | None:
    try:
        root = (DATA / "toolbox-root.txt").read_text(encoding="utf-8-sig").strip()
    except OSError:
        root = ""
    if root:
        d = Path(root) / "System Tools" / "ImagineTracker"
        if (d / "Imagine Tracker.html").is_file():
            return d
    here = Path(__file__).resolve().parent
    if (here / "Imagine Tracker.html").is_file():
        return here
    return None


def write_token_file() -> None:
    d = _token_page_dir()
    if d is None:
        log_activity("token-no-page-dir")
        return
    try:
        text = "window.FAFO_VAULT_TOKEN=" + json.dumps(VAULT_TOKEN) + ";\n"
        tmp = d / (TOKEN_FILE_NAME + "." + str(os.getpid()) + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, d / TOKEN_FILE_NAME)
    except OSError:
        log_activity("token-write-failed")


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
    write_token_file()
    _httpd = httpd
    print(f"[imagine-vault] http://{HOST}:{PORT}  v{VERSION}  data={DATA}", flush=True)
    threading.Thread(target=scan_loop, name="imagine-scan", daemon=True).start()
    threading.Thread(target=hash_worker, name="imagine-hash", daemon=True).start()
    if not AUTOSTART:
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
    try:
        (DATA / "vault-watch.mode").write_text("autostart" if AUTOSTART else "manual", encoding="utf-8")
    except OSError:
        pass
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

    last_wanted = True
    try:
        while not stop.is_file():
            up = _health_ok()
            w = True if AUTOSTART else demand_fresh()
            wanted = last_wanted if w is None else w
            last_wanted = wanted
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
            for lp in (stdout, stderr):
                try:
                    if lp.is_file() and lp.stat().st_size > 5_000_000:
                        os.replace(lp, lp.with_name(lp.name + ".1"))
                except OSError:
                    pass
            with stdout.open("a", encoding="utf-8") as out, stderr.open("a", encoding="utf-8") as err:
                child = subprocess.Popen(
                    [py, "-u", script.name] + (["--autostart"] if AUTOSTART else []),
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
