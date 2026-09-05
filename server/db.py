"""SQLite catalog for AI Toolbox media library."""
from __future__ import annotations

import json
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


def row_to_media(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["file_tags"] = json.loads(d.get("file_tags") or "[]")
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