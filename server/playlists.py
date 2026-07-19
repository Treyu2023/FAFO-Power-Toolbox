"""Playlist CRUD for Media Library — saved file lists for CapCut etc."""
from __future__ import annotations

import time
import uuid
from typing import Any

import media_ops as ops
from db import connect


def list_playlists() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM playlists ORDER BY created_at DESC").fetchall()
        counts = {
            r["playlist_id"]: r["c"]
            for r in conn.execute(
                "SELECT playlist_id, COUNT(*) as c FROM playlist_items GROUP BY playlist_id"
            ).fetchall()
        }
    return [{**dict(r), "item_count": counts.get(r["id"], 0)} for r in rows]


def create_playlist(name: str, description: str = "", kind: str = "mixed") -> dict[str, Any]:
    pid = uuid.uuid4().hex[:10]
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO playlists (id, name, description, kind, created_at) VALUES (?,?,?,?,?)",
            (pid, name.strip(), description.strip(), kind, now),
        )
    return get_playlist(pid)  # type: ignore[return-value]


def get_playlist(pid: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        item_rows = conn.execute(
            "SELECT * FROM playlist_items WHERE playlist_id=? ORDER BY sort_order, added_at",
            (pid,),
        ).fetchall()
    d = dict(row)
    d["items"] = []
    for ir in item_rows:
        m = ops.get_media(ir["media_id"])
        if m:
            d["items"].append({
                "media_id": ir["media_id"],
                "sort_order": ir["sort_order"],
                "added_at": ir["added_at"],
                "media": m,
            })
    d["item_count"] = len(d["items"])
    return d


def update_playlist(pid: str, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()
        if not row:
            raise FileNotFoundError("Playlist not found")
        new_name = name.strip() if name is not None else row["name"]
        new_desc = description.strip() if description is not None else row["description"]
        conn.execute(
            "UPDATE playlists SET name=?, description=? WHERE id=?",
            (new_name, new_desc, pid),
        )
    return get_playlist(pid)  # type: ignore[return-value]


def delete_playlist(pid: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM playlists WHERE id=?", (pid,))


def add_items(pid: str, media_ids: list[str]) -> dict[str, Any]:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM playlists WHERE id=?", (pid,)).fetchone():
            raise FileNotFoundError("Playlist not found")
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) as m FROM playlist_items WHERE playlist_id=?",
            (pid,),
        ).fetchone()["m"]
    added = 0
    now = time.time()
    order = max_order + 1
    with connect() as conn:
        for mid in media_ids:
            if not ops.get_media(mid):
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO playlist_items (playlist_id, media_id, sort_order, added_at) VALUES (?,?,?,?)",
                (pid, mid, order, now),
            )
            if cur.rowcount:
                added += 1
                order += 1
    pl = get_playlist(pid)
    return {"added": added, "playlist": pl}


def remove_item(pid: str, media_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM playlist_items WHERE playlist_id=? AND media_id=?",
            (pid, media_id),
        )


def playlist_paths(pid: str) -> list[dict[str, Any]]:
    pl = get_playlist(pid)
    if not pl:
        raise FileNotFoundError("Playlist not found")
    ids = [it["media_id"] for it in pl["items"]]
    return ops.resolve_media_paths(ids)