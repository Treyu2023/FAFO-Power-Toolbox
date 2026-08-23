"""Ditto clipboard group round-trip — list / edit / inject, then bounce Ditto so the tray reflects it.

Ditto.db (%APPDATA%\\Ditto\\Ditto.db) is SQLite journal_mode=delete. Ditto keeps the file
open and caches clips, so writes while it is running are either SQLITE_BUSY or get
overwritten when Ditto flushes. Every mutation therefore: stop Ditto → write → start Ditto
when reflect=True (default).

CRC is zlib.crc32 of concatenated format blobs (matches this install). Groups use CRC NULL.
Data.lParentID points at Main.lID (there is no lClipID column).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

import psutil

IS_WINDOWS = os.name == "nt"
STICKY_NONE = -2147483647.0
DEFAULT_DB = Path(os.environ.get("APPDATA", "")) / "Ditto" / "Ditto.db"
EXE_CANDIDATES = [
    Path(r"C:\Program Files\Ditto\Ditto.exe"),
    Path(r"C:\Program Files (x86)\Ditto\Ditto.exe"),
]
OPS_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FAFO" / "DittoOps"
UNDO_PATH = OPS_DIR / "mutations.jsonl"
BACKUP_DIR = OPS_DIR / "backups"
SELECTION_PATH = OPS_DIR / "selection.json"
MAX_UNDO = 80
MTEXT_CAP = 50000
T = TypeVar("T")


def _now() -> int:
    return int(time.time())


def db_path() -> Path:
    override = os.environ.get("FAFO_DITTO_DB", "").strip()
    return Path(override) if override else DEFAULT_DB


def ditto_exe() -> Path | None:
    override = os.environ.get("FAFO_DITTO_EXE", "").strip()
    if override:
        p = Path(override)
        return p if p.is_file() else None
    for p in EXE_CANDIDATES:
        if p.is_file():
            return p
    return None


def _procs() -> list[psutil.Process]:
    found: list[psutil.Process] = []
    for p in psutil.process_iter(["name", "exe"]):
        try:
            name = (p.info.get("name") or "").lower()
            exe = (p.info.get("exe") or "").lower()
        except (psutil.Error, TypeError):
            continue
        if name == "ditto.exe" or exe.endswith("\\ditto.exe"):
            found.append(p)
    return found


def is_running() -> bool:
    return bool(_procs())


def process_info() -> list[dict[str, Any]]:
    rows = []
    for p in _procs():
        try:
            rows.append({"pid": p.pid, "exe": p.exe() if p.exe() else None})
        except psutil.Error:
            rows.append({"pid": p.pid, "exe": None})
    return rows


def stop_ditto(timeout: float = 12.0) -> dict[str, Any]:
    procs = _procs()
    if not procs:
        return {"ok": True, "stopped": 0, "already_stopped": True}
    pids = [p.pid for p in procs]
    for p in procs:
        try:
            p.terminate()
        except psutil.Error:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=timeout)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass
    if alive:
        psutil.wait_procs(alive, timeout=4)
    still = _procs()
    return {
        "ok": not still,
        "stopped": len(gone) + (len(procs) - len(alive)),
        "pids": pids,
        "still_running": [p.pid for p in still],
        "already_stopped": False,
    }


def start_ditto() -> dict[str, Any]:
    if is_running():
        return {"ok": True, "already_running": True, "exe": str(ditto_exe() or "")}
    exe = ditto_exe()
    if not exe:
        return {"ok": False, "error": "Ditto.exe not found under Program Files"}
    flags = 0
    if IS_WINDOWS:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(exe)],
        cwd=str(exe.parent),
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    deadline = time.time() + 8
    while time.time() < deadline:
        if is_running():
            return {"ok": True, "already_running": False, "exe": str(exe)}
        time.sleep(0.2)
    return {"ok": is_running(), "already_running": False, "exe": str(exe)}


def bounce_ditto() -> dict[str, Any]:
    stopped = stop_ditto()
    started = start_ditto()
    return {"ok": bool(stopped.get("ok") and started.get("ok")), "stop": stopped, "start": started}


def _connect(write: bool = False) -> sqlite3.Connection:
    path = db_path()
    if not path.is_file():
        raise FileNotFoundError(f"Ditto.db not found: {path}")
    if write:
        con = sqlite3.connect(str(path), timeout=12)
    else:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=8)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=8000")
    return con


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {k: r[k] for k in r.keys()}


def _signed_crc(blobs: list[bytes]) -> int:
    c = 0
    for b in blobs:
        c = zlib.crc32(b, c)
    c &= 0xFFFFFFFF
    return c - 0x100000000 if c >= 0x80000000 else c


def _cf_text(text: str) -> bytes:
    return text.encode("cp1252", errors="replace") + b"\x00"


def _cf_unicode(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\x00\x00"


def _decode_unicode_blob(blob: Any) -> str:
    if not blob:
        return ""
    raw = bytes(blob)
    if raw.endswith(b"\x00\x00"):
        raw = raw[:-2]
    return raw.decode("utf-16-le", errors="replace")


def _preview(text: str | None, n: int = 140) -> str:
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _max_order(cur: sqlite3.Cursor, column: str, parent_id: int | None = None) -> float:
    if parent_id is None:
        row = cur.execute(f"SELECT MAX({column}) FROM Main").fetchone()
    else:
        row = cur.execute(
            f"SELECT MAX({column}) FROM Main WHERE lParentID=?", (parent_id,)
        ).fetchone()
    val = row[0] if row else None
    try:
        return float(val) + 1.0 if val is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def _log_mutation(action: str, payload: dict[str, Any]) -> None:
    try:
        OPS_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **payload,
        }
        with UNDO_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        lines = UNDO_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > MAX_UNDO:
            UNDO_PATH.write_text("\n".join(lines[-MAX_UNDO:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def _ancestors(cur: sqlite3.Cursor, item_id: int) -> set[int]:
    seen: set[int] = set()
    current = item_id
    for _ in range(64):
        if current in seen or current in (None, 0, -1):
            break
        seen.add(current)
        row = cur.execute("SELECT lParentID FROM Main WHERE lID=?", (current,)).fetchone()
        if not row:
            break
        current = int(row[0] or -1)
    return seen


def _descendants(cur: sqlite3.Cursor, group_id: int) -> list[int]:
    ids = [group_id]
    out: list[int] = []
    seen: set[int] = set()
    while ids:
        gid = ids.pop()
        if gid in seen:
            continue
        seen.add(gid)
        rows = cur.execute("SELECT lID, bIsGroup FROM Main WHERE lParentID=?", (gid,)).fetchall()
        for r in rows:
            out.append(int(r["lID"]))
            if r["bIsGroup"]:
                ids.append(int(r["lID"]))
    return out


def status() -> dict[str, Any]:
    path = db_path()
    st: dict[str, Any] = {
        "db_path": str(path),
        "db_exists": path.is_file(),
        "db_bytes": path.stat().st_size if path.is_file() else 0,
        "ditto_running": is_running(),
        "ditto_exe": str(ditto_exe() or ""),
        "processes": process_info(),
        "undo_path": str(UNDO_PATH),
        "backup_dir": str(BACKUP_DIR),
    }
    if not path.is_file():
        return st
    con = _connect(False)
    try:
        cur = con.cursor()
        st["journal_mode"] = cur.execute("PRAGMA journal_mode").fetchone()[0]
        st["groups"] = cur.execute("SELECT COUNT(*) FROM Main WHERE bIsGroup=1").fetchone()[0]
        st["clips"] = cur.execute("SELECT COUNT(*) FROM Main WHERE bIsGroup=0").fetchone()[0]
        st["data_rows"] = cur.execute("SELECT COUNT(*) FROM Data").fetchone()[0]
        seq = {
            r["name"]: r["seq"]
            for r in cur.execute("SELECT name, seq FROM sqlite_sequence")
        }
        st["sqlite_sequence"] = seq
    finally:
        con.close()
    return st


def list_groups() -> dict[str, Any]:
    con = _connect(False)
    try:
        cur = con.cursor()
        groups = [
            dict(r)
            for r in cur.execute(
                "SELECT lID, mText, lParentID, lDate, lDontAutoDelete "
                "FROM Main WHERE bIsGroup=1 ORDER BY mText COLLATE NOCASE"
            )
        ]
        counts: dict[int, dict[str, int]] = {}
        for r in cur.execute(
            "SELECT lParentID AS pid, bIsGroup AS g, COUNT(*) AS n FROM Main GROUP BY lParentID, bIsGroup"
        ):
            bucket = counts.setdefault(int(r["pid"] if r["pid"] is not None else -1), {"clips": 0, "groups": 0})
            if r["g"]:
                bucket["groups"] = int(r["n"])
            else:
                bucket["clips"] = int(r["n"])
        for g in groups:
            c = counts.get(int(g["lID"]), {"clips": 0, "groups": 0})
            g["clip_count"] = c["clips"]
            g["child_group_count"] = c["groups"]
            g["preview"] = _preview(g.get("mText"), 80)
        by_id = {int(g["lID"]): g for g in groups}
        roots: list[dict[str, Any]] = []

        def attach(node: dict[str, Any]) -> None:
            node["children"] = []
            nid = int(node["lID"])
            for g in groups:
                if int(g["lParentID"] or -1) == nid:
                    child = by_id[int(g["lID"])]
                    if "children" not in child:
                        attach(child)
                    node["children"].append(child)
            node["children"].sort(key=lambda x: (x.get("mText") or "").lower())

        for g in groups:
            pid = int(g["lParentID"] or -1)
            if pid in ( -1, 0) or pid not in by_id:
                if "children" not in g:
                    attach(g)
                if g not in roots:
                    roots.append(g)
        roots.sort(key=lambda x: (x.get("mText") or "").lower())
        return {"ok": True, "groups": groups, "tree": roots, "count": len(groups)}
    finally:
        con.close()


def list_clips(group_id: int, q: str = "", limit: int = 200, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    con = _connect(False)
    try:
        cur = con.cursor()
        group = cur.execute(
            "SELECT lID, mText, lParentID, bIsGroup FROM Main WHERE lID=?", (group_id,)
        ).fetchone()
        if not group:
            raise FileNotFoundError(f"Group {group_id} not found")
        params: list[Any] = [group_id]
        where = "lParentID=? AND bIsGroup=0"
        if q.strip():
            where += " AND mText LIKE ?"
            params.append(f"%{q.strip()}%")
        total = cur.execute(f"SELECT COUNT(*) FROM Main WHERE {where}", params).fetchone()[0]
        rows = cur.execute(
            f"SELECT lID, lDate, mText, CRC, lDontAutoDelete, clipOrder, clipGroupOrder, lastPasteDate "
            f"FROM Main WHERE {where} ORDER BY clipGroupOrder DESC, clipOrder DESC, lID DESC "
            f"LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        clips = []
        for r in rows:
            d = dict(r)
            d["preview"] = _preview(d.get("mText"))
            d["chars"] = len(d.get("mText") or "")
            clips.append(d)
        child_groups = [
            dict(r)
            for r in cur.execute(
                "SELECT lID, mText FROM Main WHERE lParentID=? AND bIsGroup=1 ORDER BY mText COLLATE NOCASE",
                (group_id,),
            )
        ]
        return {
            "ok": True,
            "group": dict(group),
            "total": total,
            "limit": limit,
            "offset": offset,
            "clips": clips,
            "child_groups": child_groups,
        }
    finally:
        con.close()


def get_clip(clip_id: int) -> dict[str, Any]:
    con = _connect(False)
    try:
        cur = con.cursor()
        row = cur.execute("SELECT * FROM Main WHERE lID=?", (clip_id,)).fetchone()
        if not row:
            raise FileNotFoundError(f"Clip {clip_id} not found")
        formats = []
        text = row["mText"] or ""
        for f in cur.execute(
            "SELECT lID, strClipBoardFormat, length(ooData) AS nbytes FROM Data WHERE lParentID=? ORDER BY lID",
            (clip_id,),
        ):
            formats.append(dict(f))
        uni = cur.execute(
            "SELECT ooData FROM Data WHERE lParentID=? AND strClipBoardFormat='CF_UNICODETEXT' LIMIT 1",
            (clip_id,),
        ).fetchone()
        if uni and uni[0]:
            text = _decode_unicode_blob(uni[0])
        parent = cur.execute(
            "SELECT lID, mText, bIsGroup FROM Main WHERE lID=?", (row["lParentID"],)
        ).fetchone()
        return {
            "ok": True,
            "clip": dict(row),
            "text": text,
            "formats": formats,
            "parent": dict(parent) if parent else None,
        }
    finally:
        con.close()


def _with_write(fn: Callable[[sqlite3.Connection], T], reflect: bool) -> tuple[T, dict[str, Any]]:
    bounce_meta: dict[str, Any] = {"reflect": reflect, "was_running": is_running()}
    if reflect:
        bounce_meta["stop"] = stop_ditto()
        if not bounce_meta["stop"].get("ok"):
            raise RuntimeError(
                "Could not close Ditto before writing (still running: "
                f"{bounce_meta['stop'].get('still_running')}). Close it from the tray and retry."
            )
    try:
        con = _connect(True)
        try:
            result = fn(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    except Exception:
        if reflect and bounce_meta.get("was_running"):
            bounce_meta["start"] = start_ditto()
        raise
    if reflect:
        bounce_meta["start"] = start_ditto()
    return result, bounce_meta


def _insert_group(cur: sqlite3.Cursor, name: str, parent_id: int) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("Group name is empty")
    if parent_id not in (-1, 0):
        prow = cur.execute("SELECT bIsGroup FROM Main WHERE lID=?", (parent_id,)).fetchone()
        if not prow:
            raise FileNotFoundError(f"Parent {parent_id} not found")
        if not prow["bIsGroup"]:
            raise ValueError("Parent must be a group")
    cur.execute(
        """
        INSERT INTO Main (
            lDate, mText, lShortCut, lDontAutoDelete, CRC, bIsGroup, lParentID,
            QuickPasteText, clipOrder, clipGroupOrder, globalShortCut, lastPasteDate,
            stickyClipOrder, stickyClipGroupOrder, MoveToGroupShortCut, GlobalMoveToGroupShortCut
        ) VALUES (?, ?, 0, 0, NULL, 1, ?, NULL, NULL, NULL, 0, 0, ?, ?, 0, 0)
        """,
        (_now(), name, parent_id, STICKY_NONE, STICKY_NONE),
    )
    return int(cur.lastrowid)


def _insert_clip(cur: sqlite3.Cursor, parent_id: int, text: str, pin: bool) -> int:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError("Clip text is empty")
    if parent_id not in (-1, 0):
        prow = cur.execute("SELECT bIsGroup FROM Main WHERE lID=?", (parent_id,)).fetchone()
        if not prow:
            raise FileNotFoundError(f"Parent group {parent_id} not found")
        if not prow["bIsGroup"]:
            raise ValueError("Clips must go in a group (or root)")
    cf_text = _cf_text(text)
    cf_uni = _cf_unicode(text)
    crc = _signed_crc([cf_text, cf_uni])
    mtext = text if len(text) <= MTEXT_CAP else text[:MTEXT_CAP]
    clip_order = _max_order(cur, "clipOrder")
    group_order = _max_order(cur, "clipGroupOrder", parent_id)
    cur.execute(
        """
        INSERT INTO Main (
            lDate, mText, lShortCut, lDontAutoDelete, CRC, bIsGroup, lParentID,
            QuickPasteText, clipOrder, clipGroupOrder, globalShortCut, lastPasteDate,
            stickyClipOrder, stickyClipGroupOrder, MoveToGroupShortCut, GlobalMoveToGroupShortCut
        ) VALUES (?, ?, 0, ?, ?, 0, ?, NULL, ?, ?, 0, 0, ?, ?, 0, 0)
        """,
        (
            _now(),
            mtext,
            1 if pin else 0,
            crc,
            parent_id,
            clip_order,
            group_order,
            STICKY_NONE,
            STICKY_NONE,
        ),
    )
    clip_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO Data (lParentID, strClipBoardFormat, ooData) VALUES (?, 'CF_TEXT', ?)",
        (clip_id, cf_text),
    )
    cur.execute(
        "INSERT INTO Data (lParentID, strClipBoardFormat, ooData) VALUES (?, 'CF_UNICODETEXT', ?)",
        (clip_id, cf_uni),
    )
    return clip_id


def create_group(name: str, parent_id: int = -1, reflect: bool = True) -> dict[str, Any]:
    def work(con: sqlite3.Connection) -> dict[str, Any]:
        gid = _insert_group(con.cursor(), name, int(parent_id))
        return {"id": gid, "name": name.strip(), "parent_id": int(parent_id)}

    data, bounce = _with_write(work, reflect)
    _log_mutation("create_group", data)
    return {"ok": True, **data, "bounce": bounce}


def rename_item(item_id: int, name: str, reflect: bool = True) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is empty")

    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.cursor()
        row = cur.execute("SELECT lID, mText, bIsGroup FROM Main WHERE lID=?", (item_id,)).fetchone()
        if not row:
            raise FileNotFoundError(f"Item {item_id} not found")
        old = row["mText"]
        cur.execute("UPDATE Main SET mText=? WHERE lID=?", (name, item_id))
        return {
            "id": item_id,
            "name": name,
            "old_name": old,
            "is_group": bool(row["bIsGroup"]),
        }

    data, bounce = _with_write(work, reflect)
    _log_mutation("rename", data)
    return {"ok": True, **data, "bounce": bounce}


def move_item(item_id: int, parent_id: int, reflect: bool = True) -> dict[str, Any]:
    parent_id = int(parent_id)

    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.cursor()
        row = cur.execute(
            "SELECT lID, mText, bIsGroup, lParentID FROM Main WHERE lID=?", (item_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"Item {item_id} not found")
        if parent_id == int(item_id):
            raise ValueError("Cannot move an item into itself")
        if parent_id not in (-1, 0):
            prow = cur.execute("SELECT bIsGroup FROM Main WHERE lID=?", (parent_id,)).fetchone()
            if not prow:
                raise FileNotFoundError(f"Parent {parent_id} not found")
            if not prow["bIsGroup"]:
                raise ValueError("Destination must be a group")
            if int(item_id) in _ancestors(cur, parent_id) or parent_id in _descendants(cur, int(item_id)):
                raise ValueError("That move would create a cycle")
        old_parent = int(row["lParentID"] or -1)
        group_order = _max_order(cur, "clipGroupOrder", parent_id)
        cur.execute(
            "UPDATE Main SET lParentID=?, clipGroupOrder=? WHERE lID=?",
            (parent_id, group_order, item_id),
        )
        return {
            "id": item_id,
            "parent_id": parent_id,
            "old_parent_id": old_parent,
            "is_group": bool(row["bIsGroup"]),
            "name": row["mText"],
        }

    data, bounce = _with_write(work, reflect)
    _log_mutation("move", data)
    return {"ok": True, **data, "bounce": bounce}


def inject_clip(parent_id: int, text: str, pin: bool = False, reflect: bool = True) -> dict[str, Any]:
    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cid = _insert_clip(con.cursor(), int(parent_id), text, pin)
        return {"id": cid, "parent_id": int(parent_id), "chars": len(text), "pin": pin}

    data, bounce = _with_write(work, reflect)
    _log_mutation("inject", {"id": data["id"], "parent_id": data["parent_id"], "chars": data["chars"]})
    return {"ok": True, **data, "bounce": bounce}


def inject_clips(parent_id: int, texts: list[str], pin: bool = False, reflect: bool = True) -> dict[str, Any]:
    cleaned = [t for t in texts if (t or "").strip()]
    if not cleaned:
        raise ValueError("No clip texts to inject")

    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.cursor()
        ids = [_insert_clip(cur, int(parent_id), t, pin) for t in cleaned]
        return {"ids": ids, "parent_id": int(parent_id), "count": len(ids), "pin": pin}

    data, bounce = _with_write(work, reflect)
    _log_mutation("inject_bulk", {"ids": data["ids"], "parent_id": data["parent_id"], "count": data["count"]})
    return {"ok": True, **data, "bounce": bounce}


def update_clip(clip_id: int, text: str | None = None, pin: bool | None = None, reflect: bool = True) -> dict[str, Any]:
    if text is None and pin is None:
        raise ValueError("Nothing to update")

    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.cursor()
        row = cur.execute("SELECT * FROM Main WHERE lID=?", (clip_id,)).fetchone()
        if not row:
            raise FileNotFoundError(f"Clip {clip_id} not found")
        if row["bIsGroup"]:
            raise ValueError("Use rename for groups")
        old_text = row["mText"]
        uni = cur.execute(
            "SELECT ooData FROM Data WHERE lParentID=? AND strClipBoardFormat='CF_UNICODETEXT' LIMIT 1",
            (clip_id,),
        ).fetchone()
        if uni and uni[0]:
            raw = bytes(uni[0])
            if raw.endswith(b"\x00\x00"):
                raw = raw[:-2]
            old_text = raw.decode("utf-16-le", errors="replace")
        if text is not None:
            new_text = text.replace("\r\n", "\n").replace("\r", "\n")
            if not new_text.strip():
                raise ValueError("Clip text is empty")
            cf_text = _cf_text(new_text)
            cf_uni = _cf_unicode(new_text)
            crc = _signed_crc([cf_text, cf_uni])
            mtext = new_text if len(new_text) <= MTEXT_CAP else new_text[:MTEXT_CAP]
            cur.execute(
                "UPDATE Main SET mText=?, CRC=?, lDate=? WHERE lID=?",
                (mtext, crc, _now(), clip_id),
            )
            cur.execute(
                "DELETE FROM Data WHERE lParentID=? AND strClipBoardFormat IN "
                "('CF_TEXT','CF_UNICODETEXT','HTML Format','Rich Text Format')",
                (clip_id,),
            )
            cur.execute(
                "INSERT INTO Data (lParentID, strClipBoardFormat, ooData) VALUES (?, 'CF_TEXT', ?)",
                (clip_id, cf_text),
            )
            cur.execute(
                "INSERT INTO Data (lParentID, strClipBoardFormat, ooData) VALUES (?, 'CF_UNICODETEXT', ?)",
                (clip_id, cf_uni),
            )
        if pin is not None:
            cur.execute("UPDATE Main SET lDontAutoDelete=? WHERE lID=?", (1 if pin else 0, clip_id))
        return {
            "id": clip_id,
            "old_text": old_text,
            "chars": len(text) if text is not None else len(old_text or ""),
            "pin": pin,
        }

    data, bounce = _with_write(work, reflect)
    _log_mutation(
        "update_clip",
        {"id": data["id"], "old_text": data.get("old_text"), "pin": pin},
    )
    return {"ok": True, "id": clip_id, "chars": data["chars"], "pin": pin, "bounce": bounce}


def delete_item(item_id: int, recursive: bool = False, reflect: bool = True) -> dict[str, Any]:
    def work(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.cursor()
        row = cur.execute(
            "SELECT lID, mText, bIsGroup, lParentID FROM Main WHERE lID=?", (item_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"Item {item_id} not found")
        ids = [int(item_id)]
        if row["bIsGroup"]:
            kids = _descendants(cur, int(item_id))
            if kids and not recursive:
                raise ValueError(
                    f"Group '{row['mText']}' has {len(kids)} nested item(s). Pass recursive=true to delete them."
                )
            ids.extend(kids)
        snap = []
        for iid in ids:
            info = cur.execute("SELECT lID, mText, bIsGroup, lParentID FROM Main WHERE lID=?", (iid,)).fetchone()
            if info:
                snap.append(dict(info))
        qmarks = ",".join("?" * len(ids))
        cur.execute(f"DELETE FROM Data WHERE lParentID IN ({qmarks})", ids)
        cur.execute(f"DELETE FROM Main WHERE lID IN ({qmarks})", ids)
        now = _now()
        cur.executemany(
            "INSERT INTO MainDeletes (clipID, modifiedDate) VALUES (?, ?)",
            [(iid, now) for iid in ids],
        )
        return {
            "id": item_id,
            "deleted_ids": ids,
            "count": len(ids),
            "name": row["mText"],
            "is_group": bool(row["bIsGroup"]),
            "snapshot": snap[:40],
        }

    data, bounce = _with_write(work, reflect)
    _log_mutation("delete", {k: data[k] for k in ("id", "deleted_ids", "count", "name", "is_group")})
    return {"ok": True, **data, "bounce": bounce}


def backup_db() -> dict[str, Any]:
    src = db_path()
    if not src.is_file():
        raise FileNotFoundError(f"Ditto.db not found: {src}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"Ditto-{stamp}.db"
    size = src.stat().st_size
    # Copy while Ditto is running can get a torn file; stop only if > lock. sqlite backup API
    # is consistent if we can open the DB. Prefer sqlite backup over shutil for a live DB.
    con = _connect(False)
    try:
        dest_con = sqlite3.connect(str(dest))
        try:
            con.backup(dest_con)
        finally:
            dest_con.close()
    finally:
        con.close()
    return {
        "ok": True,
        "src": str(src),
        "dest": str(dest),
        "src_bytes": size,
        "dest_bytes": dest.stat().st_size if dest.is_file() else 0,
    }


def get_selection() -> dict[str, Any]:
    data: dict[str, Any] = {"id": None, "name": None, "updated": None, "exists": False}
    if SELECTION_PATH.is_file():
        try:
            loaded = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    gid = data.get("id")
    if gid in (None, "", 0):
        return {"ok": True, **data, "id": None}
    con = _connect(False)
    try:
        row = con.execute(
            "SELECT lID, mText, bIsGroup FROM Main WHERE lID=?", (int(gid),)
        ).fetchone()
    finally:
        con.close()
    if not row:
        data["exists"] = False
        return {"ok": True, **data, "id": int(gid)}
    data["id"] = int(row["lID"])
    data["name"] = row["mText"]
    data["is_group"] = bool(row["bIsGroup"])
    data["exists"] = True
    return {"ok": True, **data}


def set_selection(group_id: int | None) -> dict[str, Any]:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    if group_id in (None, "", 0, -1):
        payload = {"id": None, "name": None, "updated": datetime.now(timezone.utc).isoformat()}
        SELECTION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, **payload}
    gid = int(group_id)
    con = _connect(False)
    try:
        row = con.execute(
            "SELECT lID, mText, bIsGroup FROM Main WHERE lID=?", (gid,)
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise FileNotFoundError(f"Group {gid} not found")
    if not row["bIsGroup"]:
        raise ValueError("Selection must be a group")
    payload = {
        "id": int(row["lID"]),
        "name": row["mText"],
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    SELECTION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, **payload, "is_group": True, "exists": True}


def list_clip_texts(
    group_id: int, include_children: bool = False, limit: int = 200
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    con = _connect(False)
    try:
        cur = con.cursor()
        group = cur.execute(
            "SELECT lID, mText, bIsGroup, lParentID FROM Main WHERE lID=?", (group_id,)
        ).fetchone()
        if not group:
            raise FileNotFoundError(f"Group {group_id} not found")
        if not group["bIsGroup"]:
            raise ValueError("Not a group")
        parent_ids = [int(group_id)]
        if include_children:
            desc = _descendants(cur, int(group_id))
            if desc:
                qmarks = ",".join("?" * len(desc))
                for r in cur.execute(
                    f"SELECT lID FROM Main WHERE lID IN ({qmarks}) AND bIsGroup=1", desc
                ):
                    parent_ids.append(int(r["lID"]))
        qmarks = ",".join("?" * len(parent_ids))
        rows = cur.execute(
            f"""
            SELECT m.lID, m.mText, m.lParentID, m.clipGroupOrder, m.clipOrder, d.ooData
            FROM Main m
            LEFT JOIN Data d
              ON d.lParentID = m.lID AND d.strClipBoardFormat = 'CF_UNICODETEXT'
            WHERE m.lParentID IN ({qmarks}) AND m.bIsGroup = 0
            ORDER BY m.clipGroupOrder DESC, m.clipOrder DESC, m.lID DESC
            LIMIT ?
            """,
            [*parent_ids, limit],
        ).fetchall()
        clips = []
        for r in rows:
            text = _decode_unicode_blob(r["ooData"]) if r["ooData"] else (r["mText"] or "")
            if not (text or "").strip():
                continue
            clips.append(
                {
                    "id": int(r["lID"]),
                    "parent_id": int(r["lParentID"] or -1),
                    "text": text,
                    "preview": _preview(text),
                    "chars": len(text),
                }
            )
        return {
            "ok": True,
            "group": dict(group),
            "include_children": bool(include_children),
            "parent_ids": parent_ids,
            "count": len(clips),
            "clips": clips,
        }
    finally:
        con.close()


def export_group(group_id: int) -> dict[str, Any]:
    tree = list_groups()
    clips = list_clips(group_id, limit=500, offset=0)
    more: list[dict[str, Any]] = list(clips["clips"])
    off = clips["limit"]
    while off < clips["total"]:
        page = list_clips(group_id, limit=500, offset=off)
        more.extend(page["clips"])
        off += page["limit"]
    texts = []
    for c in more:
        detail = get_clip(int(c["lID"]))
        texts.append({"id": c["lID"], "text": detail["text"]})
    return {
        "ok": True,
        "group": clips["group"],
        "child_groups": clips["child_groups"],
        "clips": texts,
        "count": len(texts),
        "tree_hint": [g for g in tree["groups"] if int(g["lParentID"] or -1) == int(group_id)],
    }
