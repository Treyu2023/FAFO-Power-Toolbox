"""SQLite catalog for AI Toolbox media library."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "aitoolbox.db"

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".flv", ".ts"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


def connect() -> sqlite3.Connection:
    # timeout: wait for locks when Media Library + Duplicates + VSR hit the DB together
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")  # ms — multi-tool / multi-tab friendliness
        conn.execute("PRAGMA temp_store=MEMORY")
    except sqlite3.Error:
        # Older SQLite builds may reject some PRAGMAs — still usable
        pass
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(media)")}
    migrations = [
        ("rank", "INTEGER DEFAULT 0"),
        ("category", "TEXT DEFAULT ''"),
        ("status", "TEXT DEFAULT ''"),
    ]
    for name, typedef in migrations:
        if name not in cols:
            conn.execute(f"ALTER TABLE media ADD COLUMN {name} {typedef}")

    pair_cols = {r[1] for r in conn.execute("PRAGMA table_info(pairs)")}
    pair_migrations = [
        ("pair_code", "TEXT"),
        ("pinned", "INTEGER DEFAULT 0"),
        ("notes", "TEXT DEFAULT ''"),
        ("before_path", "TEXT DEFAULT ''"),
        ("after_path", "TEXT DEFAULT ''"),
        ("source", "TEXT DEFAULT 'manual'"),
        ("confidence", "REAL"),
        ("match_method", "TEXT DEFAULT ''"),
        ("file_pid", "TEXT DEFAULT ''"),
    ]
    for name, typedef in pair_migrations:
        if name not in pair_cols:
            conn.execute(f"ALTER TABLE pairs ADD COLUMN {name} {typedef}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pairs_code ON pairs(pair_code) WHERE pair_code IS NOT NULL AND pair_code != ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pairs_ends ON pairs(before_media_id, after_media_id) "
        "WHERE before_media_id IS NOT NULL AND after_media_id IS NOT NULL"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pair_rejects (
            anchor_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            pid TEXT DEFAULT '',
            stem TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            created_at REAL NOT NULL,
            PRIMARY KEY (anchor_id, candidate_id)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pair_rejects_pid ON pair_rejects(pid)")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS directories (
                id TEXT PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                added_at REAL NOT NULL,
                last_scanned REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                dir_id TEXT NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
                rel_path TEXT NOT NULL,
                name TEXT NOT NULL,
                ext TEXT,
                type TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                mtime REAL DEFAULT 0,
                tags TEXT DEFAULT '[]',
                notes TEXT DEFAULT '',
                thumb_path TEXT,
                pair_id TEXT,
                pair_role TEXT,
                file_tags TEXT DEFAULT '[]',
                UNIQUE(dir_id, rel_path)
            );
            CREATE INDEX IF NOT EXISTS idx_media_dir ON media(dir_id);
            CREATE INDEX IF NOT EXISTS idx_media_name ON media(name);
            CREATE INDEX IF NOT EXISTS idx_media_type ON media(type);
            CREATE TABLE IF NOT EXISTS pairs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT DEFAULT 'video',
                before_media_id TEXT,
                after_media_id TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rename_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                used_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                kind TEXT DEFAULT 'mixed',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS playlist_items (
                playlist_id TEXT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                media_id TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                added_at REAL NOT NULL,
                PRIMARY KEY (playlist_id, media_id)
            );
            CREATE INDEX IF NOT EXISTS idx_playlist_items ON playlist_items(playlist_id);
            """
        )
        _migrate_schema(conn)
        repair_media_tag_blobs(conn)


_QUOTED_TAG = re.compile(r'"((?:[^"\\]|\\.){1,120})"')
_PAIR_CODE = re.compile(r"\bUP-\d{3,}\b", re.I)


def parse_stored_tags(raw: Any) -> list[str]:
    """Turn a catalog tag cell into a list.

    Pair bots sometimes stored ``[],UP-0058`` or a Signature blob chopped
    mid-JSON. Those rows used to 500 the comparator (``/api/pairs``).
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        items: list[Any] = list(raw)
    else:
        text = str(raw).strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, str) and data.strip():
            items = [data]
        else:
            items = []
            if text.startswith("[]"):
                rest = text[2:].lstrip(" \t,;")
                if rest:
                    items.extend(part.strip().strip('"') for part in rest.split(","))
            else:
                items.extend(_QUOTED_TAG.findall(text))
            items.extend(m.group(0) for m in _PAIR_CODE.finditer(text))
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item).replace("\x00", "").strip()
        if not s or s.lower().startswith("signature:"):
            continue
        if len(s) > 100:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def repair_media_tag_blobs(conn: sqlite3.Connection) -> int:
    """Rewrite tag cells that are not a JSON list of short keywords."""
    changed = 0
    rows = conn.execute("SELECT id, tags, file_tags FROM media").fetchall()
    for row in rows:
        for col in ("tags", "file_tags"):
            raw = row[col]
            if raw is None:
                continue
            cleaned = parse_stored_tags(raw)
            encoded = json.dumps(cleaned)
            if encoded == raw:
                continue
            conn.execute(f"UPDATE media SET {col}=? WHERE id=?", (encoded, row["id"]))
            changed += 1
    return changed


def row_to_media(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = parse_stored_tags(d.get("tags"))
    d["file_tags"] = parse_stored_tags(d.get("file_tags"))
    d["rank"] = int(d.get("rank") or 0)
    d["category"] = d.get("category") or ""
    d["status"] = d.get("status") or ""
    return d


def media_id(dir_id: str, rel_path: str) -> str:
    return f"{dir_id}::{rel_path}"


def file_type(name: str) -> str | None:
    ext = Path(name).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    return None