"""Pipeline workspace, leftover match queue, reject memory, pair undo, Imagine import."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from db import connect
from duplicates import DEFAULT_PIPELINE_AFTER, DEFAULT_PIPELINE_BEFORE, DEFAULT_PIPELINE_INBOX

UNDO_MAX = 50
LEFTOVER_KEY = "match_leftover"
UNDO_KEY = "pair_undo_stack"
PIPE_KEYS = ("pipeline_inbox", "pipeline_before", "pipeline_after")


def _ops():
    import media_ops as ops
    return ops


def get_pipeline() -> dict[str, Any]:
    ops = _ops()
    s = ops.get_settings()
    inbox = (s.get("pipeline_inbox") or "").strip() or DEFAULT_PIPELINE_INBOX
    before = (s.get("pipeline_before") or "").strip() or DEFAULT_PIPELINE_BEFORE
    after = (s.get("pipeline_after") or "").strip() or DEFAULT_PIPELINE_AFTER
    dirs = {d["path"]: d for d in ops.list_directories()}

    def row(path: str, role: str, label: str) -> dict[str, Any]:
        p = Path(path) if path else None
        hit = dirs.get(str(p)) if p else None
        if not hit and p:
            for dpath, d in dirs.items():
                try:
                    if Path(dpath).resolve() == p.resolve():
                        hit = d
                        break
                except OSError:
                    continue
        return {
            "role": role,
            "label": label,
            "path": path,
            "exists": bool(p and p.is_dir()),
            "dir_id": (hit or {}).get("id"),
            "dir_name": (hit or {}).get("name"),
        }

    return {
        "ok": True,
        "inbox": row(inbox, "inbox", "Inbox"),
        "before": row(before, "before", "Pre-scaled"),
        "after": row(after, "after", "After"),
        "named": [
            {"id": "inbox", "name": "Inbox", "hint": "New downloads / Imagine HAVE"},
            {"id": "before", "name": "Pre-scaled", "hint": "Source after processing — locked"},
            {"id": "after", "name": "After", "hint": "4K / 96fps result — matched by PID"},
        ],
    }


def set_pipeline(
    *,
    inbox: str | None = None,
    before: str | None = None,
    after: str | None = None,
    register: bool = True,
) -> dict[str, Any]:
    ops = _ops()
    current = get_pipeline()
    mapping = {
        "pipeline_inbox": inbox if inbox is not None else current["inbox"]["path"],
        "pipeline_before": before if before is not None else current["before"]["path"],
        "pipeline_after": after if after is not None else current["after"]["path"],
    }
    ops.save_settings(mapping)
    if register:
        for path in mapping.values():
            p = str(path or "").strip()
            if p and Path(p).is_dir():
                try:
                    ops.add_directory(p)
                except Exception:
                    pass
    return get_pipeline()


def apply_pipeline_to_dirs() -> dict[str, Any]:
    """Ensure pipeline folders are watch directories; return dir ids."""
    pipe = get_pipeline()
    ops = _ops()
    out = {}
    for role in ("inbox", "before", "after"):
        row = pipe[role]
        path = row.get("path") or ""
        if path and Path(path).is_dir() and not row.get("dir_id"):
            try:
                d = ops.add_directory(path)
                row["dir_id"] = d.get("id")
            except Exception:
                pass
        out[role] = row
    return {"ok": True, **{k: out[k] for k in out}}


def refresh_live(
    roles: tuple[str, ...] | list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Probe Inbox/After (live drop folders) and scan only when the catalog is stale."""
    ops = _ops()
    wanted = tuple(roles) if roles else ("inbox", "after")
    pipe = apply_pipeline_to_dirs()
    out: list[dict[str, Any]] = []
    for role in wanted:
        row = pipe.get(role) or {}
        dir_id = row.get("dir_id")
        item: dict[str, Any] = {
            "role": role,
            "path": row.get("path") or "",
            "dir_id": dir_id,
            "scanned": False,
            "indexed": 0,
        }
        if not dir_id:
            item["skipped"] = "no-dir"
            out.append(item)
            continue
        try:
            probe = ops.probe_directory(dir_id)
        except Exception as e:
            item["error"] = str(e)
            out.append(item)
            continue
        item.update(probe)
        if force or probe.get("stale"):
            try:
                n = ops.scan_directory(dir_id)
                item["scanned"] = True
                item["indexed"] = n
                item["stale"] = False
                item["catalog_count"] = n
                item["delta"] = 0
            except Exception as e:
                item["error"] = str(e)
        out.append(item)
    bits: list[str] = []
    for r in out:
        if r.get("error"):
            bits.append(f"{r['role']} error")
            continue
        if r.get("scanned"):
            n = int(r.get("indexed") or 0)
            bits.append(f"{r['role']} indexed {n}")
        elif r.get("skipped"):
            continue
        else:
            bits.append(f"{r['role']} current ({r.get('catalog_count') or 0})")
    return {
        "ok": True,
        "roles": out,
        "note": " · ".join(bits) if bits else "No live pipeline folders set",
    }


# --- reject memory ---

def reject_candidate(
    anchor_id: str,
    candidate_id: str,
    *,
    pid: str = "",
    stem: str = "",
    reason: str = "guided-reject",
) -> dict[str, Any]:
    if not anchor_id or not candidate_id or anchor_id == candidate_id:
        raise ValueError("Need two different media ids")
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pair_rejects
               (anchor_id, candidate_id, pid, stem, reason, created_at)
               VALUES (?,?,?,?,?,?)""",
            (anchor_id, candidate_id, pid or "", stem or "", reason or "", time.time()),
        )
    return {"ok": True, "anchor_id": anchor_id, "candidate_id": candidate_id}


def list_rejects(limit: int = 2000) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM pair_rejects ORDER BY created_at DESC LIMIT ?",
            (max(1, min(5000, int(limit or 2000))),),
        ).fetchall()
    return [dict(r) for r in rows]


def reject_set() -> set[tuple[str, str]]:
    with connect() as conn:
        rows = conn.execute("SELECT anchor_id, candidate_id FROM pair_rejects").fetchall()
    return {(r["anchor_id"], r["candidate_id"]) for r in rows}


def clear_rejects() -> dict[str, Any]:
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM pair_rejects").fetchone()["n"]
        conn.execute("DELETE FROM pair_rejects")
    return {"ok": True, "cleared": n}


# --- leftover queue ---

def get_leftover() -> dict[str, Any]:
    raw = _ops().get_setting(LEFTOVER_KEY, "")
    if not raw:
        return {
            "unique_trusted": 0,
            "ambiguous": [],
            "fuzzy_ids": [],
            "rejected": 0,
            "updated_at": 0,
        }
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"unique_trusted": 0, "ambiguous": [], "fuzzy_ids": [], "rejected": 0, "updated_at": 0}


def save_leftover(data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "unique_trusted": int(data.get("unique_trusted") or 0),
        "ambiguous": list(data.get("ambiguous") or [])[:400],
        "fuzzy_ids": list(data.get("fuzzy_ids") or [])[:2000],
        "rejected": int(data.get("rejected") or 0),
        "updated_at": time.time(),
        "note": data.get("note") or "",
    }
    _ops().set_setting(LEFTOVER_KEY, json.dumps(payload))
    return payload


def rebuild_leftover(
    *,
    before_dir_id: str | None = None,
    after_dir_id: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    ops = _ops()
    pid_data = ops.list_pid_matches(
        media_type=kind if kind in ("video", "image") else None,
        before_dir_id=before_dir_id,
        after_dir_id=after_dir_id,
        unpaired_only=True,
        limit=800,
    )
    unique_n = pid_data.get("unique_count") or 0
    ambiguous = pid_data.get("ambiguous") or []
    used = set()
    for m in (pid_data.get("matches") or []):
        used.add(m.get("before_id"))
        used.add(m.get("after_id"))
    anchors = ops.list_unpaired_anchors(
        kind=kind if kind in ("video", "image") else None,
        limit=800,
        prefer_sources=True,
        before_dir_id=before_dir_id,
    )
    fuzzy_ids = [a["id"] for a in anchors if a["id"] not in used]
    rejects = list_rejects(limit=1)
    payload = save_leftover({
        "unique_trusted": 0,
        "ambiguous": ambiguous,
        "fuzzy_ids": fuzzy_ids,
        "rejected": len(reject_set()) if rejects else 0,
        "note": f"{unique_n} unique ready · {len(ambiguous)} ambiguous · {len(fuzzy_ids)} leftover",
    })
    payload["unique_ready"] = unique_n
    payload["pid"] = pid_data
    return payload


# --- undo ---

def _undo_stack() -> list[dict[str, Any]]:
    raw = _ops().get_setting(UNDO_KEY, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def push_undo(entry: dict[str, Any]) -> None:
    stack = _undo_stack()
    entry = {**entry, "at": time.time(), "id": "undo-" + uuid.uuid4().hex[:8]}
    stack.append(entry)
    _ops().set_setting(UNDO_KEY, json.dumps(stack[-UNDO_MAX:]))


def list_undo() -> dict[str, Any]:
    stack = _undo_stack()
    return {"ok": True, "count": len(stack), "items": stack[-20:]}


def undo_last() -> dict[str, Any]:
    ops = _ops()
    stack = _undo_stack()
    if not stack:
        return {"ok": False, "error": "Nothing to undo"}
    entry = stack.pop()
    ops.set_setting(UNDO_KEY, json.dumps(stack))
    kind = entry.get("type")
    try:
        if kind == "lock":
            pid = entry.get("pair_id")
            if pid:
                ops.delete_pair(pid, record_undo=False)
            return {"ok": True, "undid": "lock", "pair_id": pid}
        if kind == "unlock":
            snap = entry.get("snapshot") or {}
            if snap.get("before_id") and snap.get("after_id"):
                pair = ops.save_pair(
                    snap.get("name") or "",
                    snap["before_id"],
                    snap["after_id"],
                    snap.get("kind") or "video",
                    pinned=bool(snap.get("pinned")),
                    notes=snap.get("notes") or "undo-relock",
                    source="undo",
                    pair_code=snap.get("pair_code"),
                    confidence=snap.get("confidence"),
                    match_method=snap.get("match_method") or "undo",
                    mint_pid=False,
                    record_undo=False,
                )
                return {"ok": True, "undid": "unlock", "pair": pair}
        if kind == "rename":
            mid = entry.get("new_id") or entry.get("media_id")
            old_name = entry.get("old_name")
            if mid and old_name:
                ops.rename_media(mid, old_name)
            return {"ok": True, "undid": "rename", "name": old_name}
        if kind == "pid-trust":
            for pid in entry.get("pair_ids") or []:
                try:
                    ops.delete_pair(pid)
                except Exception:
                    pass
            return {"ok": True, "undid": "pid-trust", "count": len(entry.get("pair_ids") or [])}
    except Exception as e:
        stack.append(entry)
        ops.set_setting(UNDO_KEY, json.dumps(stack[-UNDO_MAX:]))
        return {"ok": False, "error": str(e)[:200], "entry": entry}
    return {"ok": False, "error": f"Unknown undo type {kind}", "entry": entry}


# --- Imagine HAVE → catalog ---

def import_imagine_have(*, dest: str | None = None, limit: int = 400) -> dict[str, Any]:
    """Pull HAVE files from Imagine Vault into the Inbox watch folder (catalog only — no copy)."""
    import urllib.request

    ops = _ops()
    pipe = get_pipeline()
    dest_path = (dest or pipe["inbox"]["path"] or "").strip()
    added_dir = None
    if dest_path and Path(dest_path).is_dir():
        try:
            added_dir = ops.add_directory(dest_path)
        except Exception:
            added_dir = None
    items: list[dict[str, Any]] = []
    vault_error = None
    for base in ("http://127.0.0.1:18767", "http://127.0.0.87:18767"):
        try:
            req = urllib.request.Request(base + "/catalog", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            raw = data.get("items") or data.get("catalog") or {}
            if isinstance(raw, dict):
                items = list(raw.values())
            elif isinstance(raw, list):
                items = raw
            vault_error = None
            break
        except Exception as e:
            vault_error = str(e)[:160]
    if vault_error and not items:
        return {"ok": False, "error": "Imagine Vault not reachable — start it, then retry", "detail": vault_error}

    imported = []
    skipped = 0
    dir_id = (added_dir or {}).get("id")
    for it in items[: max(1, min(2000, int(limit or 400)))]:
        if not (it.get("hasFile") or it.get("path") or it.get("pathBest")):
            skipped += 1
            continue
        path = str(it.get("pathBest") or it.get("path") or it.get("pathOrig") or "").strip()
        if not path or not Path(path).is_file():
            skipped += 1
            continue
        parent = str(Path(path).parent)
        try:
            d = ops.add_directory(parent)
            ops.scan_directory(d["id"], recursive=False)
            imported.append({"path": path, "name": Path(path).name, "dir_id": d.get("id")})
        except Exception:
            skipped += 1
    return {
        "ok": True,
        "imported": len(imported),
        "skipped": skipped,
        "inbox": dest_path,
        "dir_id": dir_id,
        "items": imported[:40],
    }
