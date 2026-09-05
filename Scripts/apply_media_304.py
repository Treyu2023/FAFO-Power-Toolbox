#!/usr/bin/env python3
"""FAFO media 3.0.4 — combine duplicate hub/DOM, catalog integrity, scan jobs, comparator save."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sub_once(path: pathlib.Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"  SKIP {label}: pattern missing in {path.name}")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  OK   {label}")
    return True


def sub_all(path: pathlib.Path, old: str, new: str, label: str) -> int:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if not n:
        print(f"  SKIP {label}: pattern missing in {path.name}")
        return 0
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"  OK   {label} x{n}")
    return n


def patch_scan_directory():
    path = ROOT / "server" / "media_ops.py"
    old = '''def scan_directory(
    dir_id: str,
    recursive: bool = True,
    on_progress: Callable[[int, str], None] | None = None,
) -> int:
'''
    new = '''def scan_directory(
    dir_id: str,
    recursive: bool = True,
    on_progress: Callable[[int, str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> int:
'''
    sub_once(path, old, new, "scan_directory signature")

    old = '''            elif entry.is_file():
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    walk(root)
    now = time.time()
    seen_ids: set[str] = set()

    with connect() as conn:
'''
    new = '''            elif entry.is_file():
                if should_cancel and should_cancel():
                    raise InterruptedError("scan cancelled")
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    cancelled = False
    try:
        walk(root)
    except InterruptedError:
        cancelled = True
    now = time.time()
    seen_ids: set[str] = set()

    with connect() as conn:
'''
    # The file uses single backslash in replace. Fix.
    text = path.read_text(encoding="utf-8")
    needle = '''            elif entry.is_file():
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    walk(root)
'''
    # actual source uses "\\", which in the file is two chars \ \
    alt = '''            elif entry.is_file():
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    walk(root)
'''
    repl = '''            elif entry.is_file():
                if should_cancel and should_cancel():
                    raise InterruptedError("scan cancelled")
                if should_skip_entry(entry.name, False, prefix):
                    continue
                ft = file_type(entry.name)
                if ft:
                    found.append((rel.replace("\\", "/"), entry))
                    count += 1
                    if on_progress:
                        on_progress(count, rel)

    cancelled = False
    try:
        walk(root)
    except InterruptedError:
        cancelled = True
'''
    if alt in text:
        path.write_text(text.replace(alt, repl, 1), encoding="utf-8")
        print("  OK   scan_directory walk cancel")
    else:
        print("  SKIP scan_directory walk cancel")

    text = path.read_text(encoding="utf-8")
    old = '''        all_in_dir = conn.execute("SELECT id FROM media WHERE dir_id=?", (dir_id,)).fetchall()
        for r in all_in_dir:
            if r["id"] not in seen_ids:
'''
    new = '''        if cancelled:
            # Incomplete walk — never prune unseen rows or we wipe the catalog.
            pass
        else:
            all_in_dir = conn.execute("SELECT id FROM media WHERE dir_id=?", (dir_id,)).fetchall()
            for r in all_in_dir:
                if r["id"] not in seen_ids:
'''
    if old in text:
        # Need to indent the prune block. Do a more careful replace.
        start = text.find(old)
        if start < 0:
            print("  SKIP prune-guard start")
            return
        # find the last_scanned update after this
        marker = 'conn.execute("UPDATE directories SET last_scanned=? WHERE id=?", (now, dir_id))'
        end = text.find(marker, start)
        if end < 0:
            print("  SKIP prune-guard end")
            return
        block = text[start:end]
        # indent inner for-loop body extra 4 spaces after wrapping with if cancelled
        lines = block.splitlines(True)
        # first 3 lines are the old header we replace
        rest = "".join(lines[3:])
        indented = "".join(("    " + ln if ln.strip() else ln) for ln in rest.splitlines(True))
        wrapped = (
            "        if cancelled:\n"
            "            # Incomplete walk — never prune unseen rows or we wipe the catalog.\n"
            "            pass\n"
            "        else:\n"
            "            all_in_dir = conn.execute(\"SELECT id FROM media WHERE dir_id=?\", (dir_id,)).fetchall()\n"
            "            for r in all_in_dir:\n"
            "                if r[\"id\"] not in seen_ids:\n"
            + indented
        )
        path.write_text(text[:start] + wrapped + text[end:], encoding="utf-8")
        print("  OK   scan prune skipped on cancel")
    else:
        print("  SKIP scan prune wrap")

    text = path.read_text(encoding="utf-8")
    old = '''        conn.execute("UPDATE directories SET last_scanned=? WHERE id=?", (now, dir_id))
    # Heal before/after pairs using UP-#### tags written into the files / sidecars
    try:
        relink_pairs_from_metadata()
'''
    new = '''        if not cancelled:
            conn.execute("UPDATE directories SET last_scanned=? WHERE id=?", (now, dir_id))
    if cancelled:
        return count
    # Heal before/after pairs using UP-#### tags written into the files / sidecars
    try:
        relink_pairs_from_metadata()
'''
    sub_once(path, old, new, "skip last_scanned/relink on cancel")


def patch_list_pairs_and_tags():
    path = ROOT / "server" / "media_ops.py"
    old = '''def _enrich_pair(row: dict | None) -> dict | None:
    if not row:
        return None
    pair = dict(row)
    pair["pinned"] = bool(pair.get("pinned"))
    before = get_media(pair.get("before_media_id") or "")
    after = get_media(pair.get("after_media_id") or "")
    pair["before_name"] = before["name"] if before else Path(pair.get("before_path") or "").name
    pair["after_name"] = after["name"] if after else Path(pair.get("after_path") or "").name
    if before and not pair.get("before_path"):
        try:
            pair["before_path"] = str(resolve_path(before))
        except FileNotFoundError:
            pass
    if after and not pair.get("after_path"):
        try:
            pair["after_path"] = str(resolve_path(after))
        except FileNotFoundError:
            pass
    return pair
'''
    new = '''def _media_map(ids: list[str]) -> dict[str, dict]:
    clean = [i for i in ids if i]
    if not clean:
        return {}
    out: dict[str, dict] = {}
    with connect() as conn:
        chunk = 400
        for i in range(0, len(clean), chunk):
            part = clean[i:i + chunk]
            q = f"SELECT * FROM media WHERE id IN ({','.join('?' * len(part))})"
            for r in conn.execute(q, part):
                m = row_to_media(r)
                out[m["id"]] = m
    return out


def _dir_paths(dir_ids: list[str]) -> dict[str, str]:
    clean = [i for i in dir_ids if i]
    if not clean:
        return {}
    out: dict[str, str] = {}
    with connect() as conn:
        q = f"SELECT id, path FROM directories WHERE id IN ({','.join('?' * len(clean))})"
        for r in conn.execute(q, clean):
            out[r["id"]] = r["path"]
    return out


def _enrich_pair(row: dict | None, media_map: dict[str, dict] | None = None, dir_map: dict[str, str] | None = None) -> dict | None:
    if not row:
        return None
    pair = dict(row)
    pair["pinned"] = bool(pair.get("pinned"))
    bid = pair.get("before_media_id") or ""
    aid = pair.get("after_media_id") or ""
    if media_map is None:
        media_map = _media_map([bid, aid])
    before = media_map.get(bid)
    after = media_map.get(aid)
    pair["before_name"] = before["name"] if before else Path(pair.get("before_path") or "").name
    pair["after_name"] = after["name"] if after else Path(pair.get("after_path") or "").name
    if before and not pair.get("before_path"):
        try:
            if dir_map is not None and before.get("dir_id") in dir_map:
                pair["before_path"] = str(Path(dir_map[before["dir_id"]]) / before["rel_path"])
            else:
                pair["before_path"] = str(resolve_path(before))
        except FileNotFoundError:
            pass
    if after and not pair.get("after_path"):
        try:
            if dir_map is not None and after.get("dir_id") in dir_map:
                pair["after_path"] = str(Path(dir_map[after["dir_id"]]) / after["rel_path"])
            else:
                pair["after_path"] = str(resolve_path(after))
        except FileNotFoundError:
            pass
    return pair
'''
    sub_once(path, old, new, "_enrich_pair batch")

    old = '''    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM pairs {where} ORDER BY pinned DESC, created_at DESC",
            params,
        ).fetchall()
    return [p for r in rows if (p := _enrich_pair(dict(r)))]
'''
    new = '''    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM pairs {where} ORDER BY pinned DESC, created_at DESC",
            params,
        ).fetchall()
    raw = [dict(r) for r in rows]
    ids = []
    for r in raw:
        ids.append(r.get("before_media_id") or "")
        ids.append(r.get("after_media_id") or "")
    mmap = _media_map(ids)
    dmap = _dir_paths([m.get("dir_id") or "" for m in mmap.values()])
    return [p for r in raw if (p := _enrich_pair(r, mmap, dmap))]
'''
    sub_once(path, old, new, "list_pairs batch enrich")

    old = '''def get_all_tags() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT tags FROM media").fetchall()
    tags: set[str] = set()
    for r in rows:
        for t in json.loads(r["tags"] or "[]"):
            tags.add(t)
    return sorted(tags, key=str.lower)
'''
    new = '''def get_all_tags() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tags FROM media WHERE tags IS NOT NULL AND tags != '[]' AND tags != ''"
        ).fetchall()
    tags: set[str] = set()
    for r in rows:
        try:
            blob = json.loads(r["tags"] or "[]")
        except Exception:
            continue
        if isinstance(blob, list):
            for t in blob:
                if t:
                    tags.add(str(t))
    return sorted(tags, key=str.lower)
'''
    sub_once(path, old, new, "get_all_tags distinct")

    old = '''    if filename:
        return "after" if _is_upscaled_name(filename) else "before"
    return None
'''
    new = '''    if filename and _is_upscaled_name(filename):
        return "after"
    return None
'''
    sub_once(path, old, new, "infer_pair_role no default-before")

    old = '''def delete_pair(pid: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE media SET pair_id=NULL, pair_role=NULL WHERE pair_id=?", (pid,))
        conn.execute("DELETE FROM pairs WHERE id=?", (pid,))
'''
    new = '''def delete_pair(pid: str) -> None:
    pair = get_pair(pid)
    sides: list[str] = []
    if pair:
        for key in ("before_media_id", "after_media_id"):
            mid = pair.get(key)
            if mid:
                sides.append(mid)
    with connect() as conn:
        conn.execute("UPDATE media SET pair_id=NULL, pair_role=NULL WHERE pair_id=?", (pid,))
        conn.execute("DELETE FROM pairs WHERE id=?", (pid,))
    # Strip UP-#### / role tags so relink does not resurrect the pair.
    for mid in sides:
        media = get_media(mid)
        if not media:
            continue
        kept = [
            t for t in (media.get("tags") or [])
            if t and not _is_pair_code_tag(str(t)) and str(t).strip().lower() not in PAIR_ROLE_TAGS
        ]
        try:
            update_media_meta(mid, tags=kept, write_file_tags=True)
        except Exception:
            pass
'''
    sub_once(path, old, new, "delete_pair strip tags")


def patch_library_extras():
    path = ROOT / "server" / "library_extras.py"
    old = '''    for p in pairs:
        bid = p.get("before_media_id")
        aid = p.get("after_media_id")
        before = _ops().get_media(bid) if bid else None
        after = _ops().get_media(aid) if aid else None
        before_ok = False
        after_ok = False
        before_path = p.get("before_path") or ""
        after_path = p.get("after_path") or ""
        try:
            if before:
                before_path = str(_ops().resolve_path(before))
                before_ok = Path(before_path).is_file()
            elif before_path:
                before_ok = Path(before_path).is_file()
        except Exception:
            before_ok = False
        try:
            if after:
                after_path = str(_ops().resolve_path(after))
                after_ok = Path(after_path).is_file()
            elif after_path:
                after_ok = Path(after_path).is_file()
        except Exception:
            after_ok = False
'''
    new = '''    occupancy: dict[str, str] = {}
    duplicate_occupancy: list[dict[str, Any]] = []
    self_pairs: list[dict[str, Any]] = []
    for p in pairs:
        bid = p.get("before_media_id")
        aid = p.get("after_media_id")
        before_ok = False
        after_ok = False
        before_path = p.get("before_path") or ""
        after_path = p.get("after_path") or ""
        try:
            if before_path:
                before_ok = Path(before_path).is_file()
        except Exception:
            before_ok = False
        try:
            if after_path:
                after_ok = Path(after_path).is_file()
        except Exception:
            after_ok = False
        if bid and aid and bid == aid:
            self_pairs.append({"id": p.get("id"), "pair_code": p.get("pair_code"), "media_id": bid})
        for mid in (bid, aid):
            if not mid:
                continue
            prev = occupancy.get(mid)
            if prev and prev != p.get("id"):
                duplicate_occupancy.append({
                    "media_id": mid,
                    "pair_a": prev,
                    "pair_b": p.get("id"),
                })
            else:
                occupancy[mid] = p.get("id")
'''
    sub_once(path, old, new, "pair_health no N+1")

    old = '''            "unpaired_upscale_named": len(looks_upscaled),
            "total_pairs": len(pairs),
        },
        "complete": complete,
        "partial": partial,
        "broken": broken,
        "orphan_tagged": orphans,
        "unpaired_upscale_named": looks_upscaled[:100],
    }
'''
    new = '''            "unpaired_upscale_named": len(looks_upscaled),
            "total_pairs": len(pairs),
            "duplicate_occupancy": len(duplicate_occupancy),
            "self_pairs": len(self_pairs),
        },
        "complete": complete,
        "partial": partial,
        "broken": broken,
        "orphan_tagged": orphans,
        "unpaired_upscale_named": looks_upscaled[:100],
        "duplicate_occupancy": duplicate_occupancy[:50],
        "self_pairs": self_pairs[:50],
    }
'''
    sub_once(path, old, new, "pair_health occupancy summary")

    old = '''    if query.get("unpaired_upscale"):
        items = []
        for m in _ops().get_all_media():
            if m.get("pair_id"):
                continue
            if _ops()._is_upscaled_name(m.get("name") or ""):
                items.append(m)
        return {"items": items[page * limit:(page + 1) * limit], "total": len(items), "page": page}
'''
    new = '''    if query.get("unpaired_upscale"):
        res = _ops().query_media(
            pair_filter="unpaired",
            page=0,
            limit=2000,
            cap=2000,
            sort="name",
        )
        items = [
            m for m in (res.get("items") or [])
            if _ops()._is_upscaled_name(m.get("name") or "")
        ]
        return {"items": items[page * limit:(page + 1) * limit], "total": len(items), "page": page}
'''
    sub_once(path, old, new, "unpaired_upscale via query_media")


def patch_server_scan_jobs():
    path = ROOT / "server" / "aitoolbox_server.py"
    old = '''_LIB_SCANS: dict[str, dict] = {}
_LIB_SCANS_LOCK = threading.Lock()


@app.get("/api/scan/{dir_id}/stream")
def api_scan_stream(dir_id: str, recursive: bool = True):
    with _LIB_SCANS_LOCK:
        job = _LIB_SCANS.get(dir_id)
        if job and not job.get("done"):
            progress = job["progress"]
        else:
            progress: list[str] = []
            job = {"progress": progress, "done": False}
            _LIB_SCANS[dir_id] = job

            def run():
                try:
                    n = ops.scan_directory(
                        dir_id,
                        recursive,
                        on_progress=lambda c, r: progress.append(json.dumps({"count": c, "file": r})),
                    )
                    progress.append(json.dumps({"done": True, "count": n}))
                except Exception as e:
                    progress.append(json.dumps({"error": str(e)}))
                finally:
                    job["done"] = True

            threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        idle = 0
        while True:
            while sent < len(progress):
                raw = progress[sent]
                yield f"data: {raw}\\n\\n"
                sent += 1
                idle = 0
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                if "done" in item or "error" in item:
                    return
            if job.get("done"):
                return
            time.sleep(0.15)
            idle += 1
            if idle > 8000:
                return

    return StreamingResponse(gen(), media_type="text/event-stream")
'''
    new = '''_LIB_SCANS: dict[str, dict] = {}
_LIB_SCANS_BY_DIR: dict[str, str] = {}
_LIB_SCANS_LOCK = threading.Lock()


def _lib_scan_start(dir_id: str, recursive: bool = True) -> dict:
    with _LIB_SCANS_LOCK:
        active_id = _LIB_SCANS_BY_DIR.get(dir_id)
        if active_id:
            job = _LIB_SCANS.get(active_id)
            if job and not job.get("done"):
                return job
        import uuid
        job_id = "scan-" + uuid.uuid4().hex[:12]
        progress: list[str] = []
        job = {
            "id": job_id,
            "dir_id": dir_id,
            "progress": progress,
            "done": False,
            "cancel": False,
            "lock": threading.Lock(),
        }
        _LIB_SCANS[job_id] = job
        _LIB_SCANS_BY_DIR[dir_id] = job_id

        def emit(obj: dict) -> None:
            with job["lock"]:
                progress.append(json.dumps(obj))

        def run():
            try:
                n = ops.scan_directory(
                    dir_id,
                    recursive,
                    on_progress=lambda c, r: emit({"count": c, "file": r, "job_id": job_id}),
                    should_cancel=lambda: bool(job.get("cancel")),
                )
                emit({"done": True, "count": n, "job_id": job_id, "cancelled": bool(job.get("cancel"))})
            except Exception as e:
                emit({"error": str(e), "job_id": job_id})
            finally:
                job["done"] = True

        threading.Thread(target=run, daemon=True).start()
        return job


def _lib_scan_sse(job: dict):
    progress = job["progress"]

    def gen():
        sent = 0
        import time
        idle = 0
        yield f"data: {json.dumps({'job_id': job.get('id'), 'state': 'running' if not job.get('done') else 'done'})}\\n\\n"
        while True:
            with job.get("lock") or threading.Lock():
                chunk = progress[sent:]
            for raw in chunk:
                yield f"data: {raw}\\n\\n"
                sent += 1
                idle = 0
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                if "done" in item or "error" in item:
                    return
            if job.get("done"):
                return
            time.sleep(0.15)
            idle += 1
            if idle > 8000:
                return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/scan/{dir_id}/start")
def api_scan_start(dir_id: str, recursive: bool = True):
    job = _lib_scan_start(dir_id, recursive)
    return {"ok": True, "job_id": job["id"], "dir_id": dir_id}


@app.post("/api/scan/{dir_id}/cancel")
def api_scan_cancel(dir_id: str, job_id: str = ""):
    with _LIB_SCANS_LOCK:
        jid = job_id or _LIB_SCANS_BY_DIR.get(dir_id) or ""
        job = _LIB_SCANS.get(jid)
    if not job:
        raise HTTPException(404, "Scan job not found")
    job["cancel"] = True
    return {"ok": True, "job_id": job.get("id")}


@app.get("/api/scan/{dir_id}/stream")
def api_scan_stream(dir_id: str, recursive: bool = True, job_id: str = ""):
    """SSE attach. Pass job_id from POST /start. Reconnect never starts a new walk."""
    with _LIB_SCANS_LOCK:
        job = _LIB_SCANS.get(job_id) if job_id else None
        if job is None:
            active_id = _LIB_SCANS_BY_DIR.get(dir_id)
            job = _LIB_SCANS.get(active_id) if active_id else None
    if job is None:
        # Backward compat for old EventSource clients: start once.
        job = _lib_scan_start(dir_id, recursive)
    return _lib_scan_sse(job)
'''
    # File uses actual newlines in yield strings. Read and replace based on unique start.
    text = path.read_text(encoding="utf-8")
    start = text.find("_LIB_SCANS: dict[str, dict] = {}")
    end = text.find("@app.get(\"/api/media\")")
    if start < 0 or end < 0:
        # try after stream function - find next route after api_scan_stream
        end = text.find("def api_query_media")
        # go back to @app.get("/api/media")
        idx = text.find("@app.get(\"/api/media\")", start)
        if idx > 0:
            end = idx
    if start < 0 or end < 0:
        print("  SKIP lib scan jobs: anchors missing")
        print("  start", start, "end", end)
        return
    # Keep api_query_media intact. Insert new block replacing from _LIB_SCANS through end of api_scan_stream.
    # Find the StreamingResponse return of api_scan_stream
    marker = 'return StreamingResponse(gen(), media_type="text/event-stream")\n'
    mpos = text.find(marker, start)
    if mpos < 0:
        print("  SKIP lib scan jobs: stream return missing")
        return
    end = mpos + len(marker)
    path.write_text(text[:start] + new.strip() + "\n\n\n" + text[end:], encoding="utf-8")
    print("  OK   lib scan job_id start/cancel/stream")

    text = path.read_text(encoding="utf-8")
    old = '''    limit = max(1, min(200, limit or 80))
    return ops.query_media(
        search, tag_list, type, dir_id, prefix, folder_only,
        virtual_root, category, status, rank_min, sort, page, limit,
        pair_filter=pair_filter,
    )
'''
    new = '''    cap = 2000
    limit = max(1, min(cap, limit or 80))
    return ops.query_media(
        search, tag_list, type, dir_id, prefix, folder_only,
        virtual_root, category, status, rank_min, sort, page, limit,
        pair_filter=pair_filter,
        cap=cap,
    )
'''
    sub_once(path, old, new, "query_media route cap 2000")


def patch_api_js():
    path = ROOT / "shared" / "aitoolbox-api.js"
    old = '''        async scanDirectory(dirId, onProgress) {
            if (await checkServer()) {
                if (onProgress) {
                    return new Promise((resolve, reject) => {
                        const es = new EventSource(`${apiBase()}/scan/${encodeURIComponent(dirId)}/stream`);
                        let errCount = 0;
                        const onHide = () => { try { es.close(); } catch { /* ignore */ } };
                        try { window.addEventListener('pagehide', onHide); } catch { /* ignore */ }
                        const finish = (fn, arg) => {
                            try { window.removeEventListener('pagehide', onHide); } catch { /* ignore */ }
                            try { es.close(); } catch { /* ignore */ }
                            fn(arg);
                        };
                        es.onmessage = e => {
                            let d;
                            try { d = JSON.parse(e.data); }
                            catch (_) { return; }
                            if (d.error) { finish(reject, new Error(d.error)); }
                            else if (d.done) { finish(resolve, { indexed: d.count }); }
                            else onProgress(d.count, d.file);
                        };
                        es.onerror = () => {
                            errCount += 1;
                            if (errCount <= 2) return;
                            finish(reject, new Error('Scan stream failed'));
                        };
                    });
                }
                return api(`/scan/${encodeURIComponent(dirId)}`, { method: 'POST' });
            }
'''
    new = '''        async scanDirectory(dirId, onProgress) {
            if (await checkServer()) {
                if (onProgress) {
                    const started = await api(`/scan/${encodeURIComponent(dirId)}/start`, { method: 'POST' });
                    const jobId = started && started.job_id;
                    const qs = jobId ? `?job_id=${encodeURIComponent(jobId)}` : '';
                    return new Promise((resolve, reject) => {
                        const es = new EventSource(`${apiBase()}/scan/${encodeURIComponent(dirId)}/stream${qs}`);
                        let errCount = 0;
                        let closed = false;
                        const finish = (fn, arg) => {
                            if (closed) return;
                            closed = true;
                            try { window.removeEventListener('pagehide', onHide); } catch { /* ignore */ }
                            try { es.close(); } catch { /* ignore */ }
                            fn(arg);
                        };
                        const onHide = () => {
                            try { es.close(); } catch { /* ignore */ }
                            if (jobId) {
                                api(`/scan/${encodeURIComponent(dirId)}/cancel?job_id=${encodeURIComponent(jobId)}`, { method: 'POST' }).catch(() => {});
                            }
                            finish(resolve, { indexed: 0, cancelled: true });
                        };
                        try { window.addEventListener('pagehide', onHide); } catch { /* ignore */ }
                        es.onmessage = e => {
                            let d;
                            try { d = JSON.parse(e.data); }
                            catch (_) { return; }
                            if (d.error) { finish(reject, new Error(d.error)); }
                            else if (d.done) { finish(resolve, { indexed: d.count, cancelled: !!d.cancelled }); }
                            else if (d.count != null) onProgress(d.count, d.file);
                        };
                        es.onerror = () => {
                            errCount += 1;
                            if (errCount <= 2) return;
                            finish(reject, new Error('Scan stream failed'));
                        };
                    });
                }
                return api(`/scan/${encodeURIComponent(dirId)}`, { method: 'POST' });
            }
'''
    sub_once(path, old, new, "scanDirectory POST start + cancel")

    old = '''            const rawLimit = opts.limit == null ? 80 : Number(opts.limit);
            const limit = Math.max(1, Math.min(200, Number.isFinite(rawLimit) ? rawLimit : 80));
'''
    new = '''            const rawLimit = opts.limit == null ? 80 : Number(opts.limit);
            const cap = Math.max(1, Math.min(2000, Number(opts.cap) || 2000));
            const limit = Math.max(1, Math.min(cap, Number.isFinite(rawLimit) ? rawLimit : 80));
'''
    sub_once(path, old, new, "queryMedia cap 2000")

    old = '''                async cancel() {
                    closed = true;
                    if (!handle.jobId) return;
                    return api('/duplicates/scan/control', {
                        method: 'POST',
                        body: JSON.stringify({ job_id: handle.jobId, action: 'cancel' }),
                    });
                },
            };
            if (typeof opts.onHandle === 'function') opts.onHandle(handle);
            const promise = (async () => {
'''
    new = '''                async cancel() {
                    closed = true;
                    try { if (handle.es) handle.es.close(); } catch { /* ignore */ }
                    if (!handle.jobId) return;
                    return api('/duplicates/scan/control', {
                        method: 'POST',
                        body: JSON.stringify({ job_id: handle.jobId, action: 'cancel' }),
                    });
                },
            };
            if (typeof opts.onHandle === 'function') opts.onHandle(handle);
            try {
                window.addEventListener('pagehide', () => { try { handle.cancel(); } catch { /* ignore */ } });
            } catch { /* ignore */ }
            const promise = (async () => {
'''
    sub_once(path, old, new, "cross-scan cancel closes ES + pagehide")


def patch_html_media_inject():
    files = [
        ROOT / "Movie File Manager" / "Media Hub.html",
        ROOT / "Movie File Manager" / "Compare Hub.html",
        ROOT / "Movie File Manager" / "Media Library Manager.html",
        ROOT / "Movie File Manager" / "File Organizer.html",
        ROOT / "Movie File Manager" / "Guided Pair Match.html",
        ROOT / "Movie File Manager" / "Pair Review Queue.html",
        ROOT / "Movie File Manager" / "Mismatched Source Companion.html",
        ROOT / "File Tools" / "Duplicate File Manager.html",
        ROOT / "Video Tools" / "Video Comparison Slider Tool.html",
        ROOT / "Video Tools" / "FAFO_VID_TRIM.html",
        ROOT / "Video Tools" / "GEMPlayHTML.html",
        ROOT / "Image tools" / "Image Comparitor With Slider.html",
        ROOT / "Image tools" / "image Converter_Cropper for chrome store resolution.html",
        ROOT / "System Tools" / "Batch Media Converter.html",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        orig = text
        text = text.replace("?v=3.0.3", "?v=3.0.4")
        text = text.replace("?v=3.0.2", "?v=3.0.4")
        inject = '<script src="../shared/aitoolbox-media.js?v=3.0.4"></script>'
        extra = inject + '\n    <script src="../shared/aitoolbox-dom.js?v=3.0.4"></script>'
        if path.name in ("Media Hub.html", "Compare Hub.html"):
            extra += '\n    <script src="../shared/aitoolbox-hub.js?v=3.0.4"></script>'
        if inject in text and "aitoolbox-dom.js" not in text:
            text = text.replace(inject, extra, 1)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            print(f"  OK   inject/version {path.name}")
        else:
            print(f"  SKIP inject {path.name}")

    tracker = ROOT / "System Tools" / "ImagineTracker" / "Imagine Tracker.html"
    if tracker.exists():
        text = tracker.read_text(encoding="utf-8")
        orig = text
        text = text.replace("?v=3.0.3", "?v=3.0.4")
        inject = '<script src="../../shared/aitoolbox-media.js?v=3.0.4"></script>'
        extra = inject + '\n    <script src="../../shared/aitoolbox-dom.js?v=3.0.4"></script>'
        if inject in text and "aitoolbox-dom.js" not in text:
            text = text.replace(inject, extra, 1)
        if text != orig:
            tracker.write_text(text, encoding="utf-8")
            print("  OK   inject Imagine Tracker")


def patch_library_html():
    path = ROOT / "Movie File Manager" / "Media Library Manager.html"
    old = '''                <button type="button" class="row-del" title="Delete" data-del="${item.id}">🗑</button>`;'''
    new = '''                <button type="button" class="row-del" title="Delete" data-del="${escHtml(item.id)}">🗑</button>`;'''
    sub_once(path, old, new, "library XSS data-del")

    old = '''                document.querySelector(`[data-id="${item.id}"]`)?.scrollIntoView({ block: 'nearest' });'''
    new = '''                document.querySelector(`[data-id="${(window.CSS && CSS.escape) ? CSS.escape(String(item.id)) : String(item.id).replace(/"/g, '')}"]`)?.scrollIntoView({ block: 'nearest' });'''
    sub_once(path, old, new, "library CSS.escape scroll")

    old = '''            if (e.key === '[' || e.key === 'ArrowUp') {
                e.preventDefault();
                selectAdjacentMedia(-1);
                return;
            }
            if (e.key === ']' || e.key === 'ArrowDown') {
                e.preventDefault();
                selectAdjacentMedia(1);
                return;
            }'''
    new = '''            if (e.key === '[' || e.key === 'ArrowUp' || e.key === 'k' || e.key === 'K') {
                e.preventDefault();
                selectAdjacentMedia(-1);
                return;
            }
            if (e.key === ']' || e.key === 'ArrowDown' || e.key === 'j' || e.key === 'J') {
                e.preventDefault();
                selectAdjacentMedia(1);
                return;
            }
            if (e.key === '/' ) {
                e.preventDefault();
                (el('searchInput') || el('q') || document.querySelector('input[type="search"]'))?.focus();
                return;
            }'''
    sub_once(path, old, new, "library j/k and / search")

    old = '''        async function addDirectoryByPath(path) {
            if (!path?.trim()) return;
            try {
                const entry = await API().addDirectory(path.trim());
                showToast(`Added: ${entry.name}`);
                await refreshDirs();
                await scanDir(entry);
            } catch (e) { alert(e.message); }
        }
'''
    new = '''        async function addDirectoryByPath(path) {
            if (!path?.trim()) return;
            try {
                const entry = await API().addDirectory(path.trim());
                try { window.AIToolboxDom?.pushRecentFolder?.(entry.path || path.trim(), entry.name); } catch (_) {}
                showToast(`Added: ${entry.name}`);
                await refreshDirs();
                await scanDir(entry);
            } catch (e) { alert(e.message); }
        }

        function renderRecentFolders() {
            const host = el('dirList');
            if (!host || !window.AIToolboxDom?.recentFolders) return;
            const recents = AIToolboxDom.recentFolders();
            const watched = new Set((watchedDirs || []).map(d => String(d.path || '').toLowerCase()));
            const fresh = recents.filter(r => r.path && !watched.has(String(r.path).toLowerCase()));
            if (!fresh.length) return;
            const wrap = document.createElement('div');
            wrap.className = 'recent-folders';
            wrap.style.cssText = 'padding:6px 8px 10px;font-size:11px;color:var(--muted);';
            wrap.innerHTML = '<div style="font-weight:700;margin-bottom:4px;letter-spacing:.04em;text-transform:uppercase;">Recent folders</div>';
            fresh.slice(0, 6).forEach(r => {
                const b = document.createElement('button');
                b.type = 'button';
                b.className = 'btn';
                b.style.cssText = 'display:block;width:100%;text-align:left;margin:3px 0;font-size:11px;';
                b.textContent = r.label || r.path;
                b.title = r.path;
                b.addEventListener('click', () => addDirectoryByPath(r.path));
                wrap.appendChild(b);
            });
            host.appendChild(wrap);
        }
'''
    sub_once(path, old, new, "library recent folders")

    old = '''            if (els.dirList) els.dirList.appendChild(allBtn);

            for (const d of dirs) {
'''
    new = '''            if (els.dirList) els.dirList.appendChild(allBtn);
            try { renderRecentFolders(); } catch (_) {}

            for (const d of dirs) {
'''
    sub_once(path, old, new, "library render recents in dir list")

    # Replace dead scanDuplicates body with redirect (keep function for any leftover callers)
    text = path.read_text(encoding="utf-8")
    start = text.find("        async function scanDuplicates() {")
    if start < 0:
        print("  SKIP scanDuplicates replace")
        return
    end = text.find("        async function buildPathIndex()", start)
    if end < 0:
        print("  SKIP scanDuplicates end")
        return
    repl = '''        async function scanDuplicates() {
            return openDuplicateManager({ scan: true });
        }

        '''
    path.write_text(text[:start] + repl + text[end:], encoding="utf-8")
    print("  OK   scanDuplicates collapsed to hub deep-link")


def patch_comparators():
    video = ROOT / "Video Tools" / "Video Comparison Slider Tool.html"
    old = '''            try {
                if (await AIToolboxAPI.isOnline()) {
                    const bq = await AIToolboxAPI.queryMedia({ search: fileCacheBefore.name, limit: 10 });
                    const aq = await AIToolboxAPI.queryMedia({ search: fileCacheAfter.name, limit: 10 });
                    const bm = (bq.items || []).find(m => m.name === fileCacheBefore.name);
                    const am = (aq.items || []).find(m => m.name === fileCacheAfter.name);
                    let pair;
                    if (bm && am) {
                        pair = await AIToolboxAPI.savePair({
                            name, kind: 'video', beforeMediaId: bm.id, afterMediaId: am.id, pinned,
                        });
                    } else if (knownBeforePath && knownAfterPath) {
                        pair = await AIToolboxAPI.savePairFromPaths({
                            beforePath: knownBeforePath, afterPath: knownAfterPath, name, kind: 'video', pinned,
                        });
                    } else {
                        showToast('Add files to Media Library first, or load a server pair to save by path.', 'warn');
                        return;
                    }
'''
    new = '''            try {
                if (await AIToolboxAPI.isOnline()) {
                    let pair;
                    const saver = window.AIToolboxHub && AIToolboxHub.saveComparatorPair;
                    if (saver) {
                        pair = await saver(AIToolboxAPI, {
                            name, kind: 'video', pinned,
                            beforePath: knownBeforePath, afterPath: knownAfterPath,
                            beforeName: fileCacheBefore.name, afterName: fileCacheAfter.name,
                            beforeSize: fileCacheBefore.size, afterSize: fileCacheAfter.size,
                        });
                    } else if (knownBeforePath && knownAfterPath) {
                        pair = await AIToolboxAPI.savePairFromPaths({
                            beforePath: knownBeforePath, afterPath: knownAfterPath, name, kind: 'video', pinned,
                        });
                    } else {
                        showToast('Add files to Media Library first, or load a server pair to save by path.', 'warn');
                        return;
                    }
'''
    sub_once(video, old, new, "video comparator path-first save")

    image = ROOT / "Image tools" / "Image Comparitor With Slider.html"
    old = '''            try {
                if (await AIToolboxAPI.isOnline()) {
                    const bq = await AIToolboxAPI.queryMedia({ search: fileCacheBefore.name, limit: 10 });
                    const aq = await AIToolboxAPI.queryMedia({ search: fileCacheAfter.name, limit: 10 });
                    const bm = (bq.items || []).find(m => m.name === fileCacheBefore.name);
                    const am = (aq.items || []).find(m => m.name === fileCacheAfter.name);
                    let pair;
                    if (bm && am) {
                        pair = await AIToolboxAPI.savePair({
                            name, kind: 'image', beforeMediaId: bm.id, afterMediaId: am.id, pinned,
                        });
                    } else if (knownBeforePath && knownAfterPath) {
                        pair = await AIToolboxAPI.savePairFromPaths({
                            beforePath: knownBeforePath, afterPath: knownAfterPath, name, kind: 'image', pinned,
                        });
                    } else {
                        showToast('Add files to Media Library first, or load a server pair.');
                        return;
                    }
'''
    new = '''            try {
                if (await AIToolboxAPI.isOnline()) {
                    let pair;
                    const saver = window.AIToolboxHub && AIToolboxHub.saveComparatorPair;
                    if (saver) {
                        pair = await saver(AIToolboxAPI, {
                            name, kind: 'image', pinned,
                            beforePath: knownBeforePath, afterPath: knownAfterPath,
                            beforeName: fileCacheBefore.name, afterName: fileCacheAfter.name,
                            beforeSize: fileCacheBefore.size, afterSize: fileCacheAfter.size,
                        });
                    } else if (knownBeforePath && knownAfterPath) {
                        pair = await AIToolboxAPI.savePairFromPaths({
                            beforePath: knownBeforePath, afterPath: knownAfterPath, name, kind: 'image', pinned,
                        });
                    } else {
                        showToast('Add files to Media Library first, or load a server pair.');
                        return;
                    }
'''
    sub_once(image, old, new, "image comparator path-first save")

    # comparators need hub.js for saveComparatorPair
    for p in (video, image):
        t = p.read_text(encoding="utf-8")
        if "aitoolbox-hub.js" not in t:
            t = t.replace(
                '<script src="../shared/aitoolbox-dom.js?v=3.0.4"></script>',
                '<script src="../shared/aitoolbox-dom.js?v=3.0.4"></script>\n    <script src="../shared/aitoolbox-hub.js?v=3.0.4"></script>',
                1,
            )
            p.write_text(t, encoding="utf-8")
            print(f"  OK   hub.js on {p.name}")


def patch_hubs():
    media = ROOT / "Movie File Manager" / "Media Hub.html"
    text = media.read_text(encoding="utf-8")
    start = text.find("  <script>\n    (function () {")
    end = text.find("<script data-tool-polish=\"media-hub\">")
    if start < 0 or end < 0:
        print("  SKIP Media Hub script", start, end)
    else:
        script = r'''  <script>
    (function () {
      if (!window.AIToolboxHub || !AIToolboxHub.mount) {
        document.getElementById('loading').textContent = 'Hub runtime failed to load.';
        return;
      }
      AIToolboxHub.mount({
        hubName: 'Media Hub',
        tabs: {
          library: {
            path: 'Media Library Manager.html',
            title: 'Media Library',
            meta: 'Catalog, preview, pair & search. Use <strong>Duplicates</strong> tab for full cleanup.'
          },
          duplicates: {
            path: '../File Tools/Duplicate File Manager.html',
            title: 'Duplicates',
            meta: 'Scan, compare, merge & recycle exact/near duplicates — same library server.'
          },
          organizer: {
            path: 'File Organizer.html',
            title: 'File Organizer',
            meta: 'Rename, tag, rank, merge same-named folders — metadata-first (no grid).'
          }
        },
        order: ['library', 'duplicates', 'organizer'],
        aliases: { dupes: 'duplicates', duplicate: 'duplicates', org: 'organizer', organize: 'organizer', lib: 'library' },
        defaultTab: 'library',
        lsKey: 'fafo_media_hub_last_tab',
        pairHealthId: 'pairHealth',
        forwardSearchOnTab: 'duplicates',
        messageType: 'fafo-hub-tab',
        keyMap: { '1': 'library', '2': 'duplicates', '3': 'organizer' },
        reportTitle: 'FAFO Media Hub',
        reportLines: ['Counterparts: Compare Hub · Guided Match · VSR · Duplicates · Organizer'],
      });
    })();
  </script>

'''
        media.write_text(text[:start] + script + text[end:], encoding="utf-8")
        print("  OK   Media Hub uses shared mount")

    compare = ROOT / "Movie File Manager" / "Compare Hub.html"
    text = compare.read_text(encoding="utf-8")
    start = text.find("  <script>\n    (function () {")
    end = text.find("<script data-tool-polish=\"compare-hub\">")
    if start < 0 or end < 0:
        print("  SKIP Compare Hub script", start, end)
        return
    script = r'''  <script>
    (function () {
      if (!window.AIToolboxHub || !AIToolboxHub.mount) {
        document.getElementById('loading').textContent = 'Hub runtime failed to load.';
        return;
      }
      AIToolboxHub.mount({
        hubName: 'Compare Hub',
        tabs: {
          match: {
            path: 'Guided Pair Match.html',
            toolboxPath: 'Movie File Manager/Guided Pair Match.html',
            title: 'Guided Pair Match',
            meta: 'One unpaired file at a time · up to 10 candidates · Y match / N next · process of elimination with you at the helm.'
          },
          pairs: {
            path: 'Pair Review Queue.html',
            toolboxPath: 'Movie File Manager/Pair Review Queue.html',
            title: 'Pair Review',
            meta: 'Review before/after pairs, accept or reject, batch-fix catalog links — then jump to a comparator.'
          },
          video: {
            path: '../Video Tools/Video Comparison Slider Tool.html',
            toolboxPath: 'Video Tools/Video Comparison Slider Tool.html',
            title: 'Video Comparator',
            meta: 'Side-by-side / slider sync playback for upscaled vs source video pairs.'
          },
          image: {
            path: '../Image tools/Image Comparitor With Slider.html',
            toolboxPath: 'Image tools/Image Comparitor With Slider.html',
            title: 'Image Comparator',
            meta: 'Before/after image slider with blend & loupe.'
          }
        },
        order: ['match', 'pairs', 'video', 'image'],
        aliases: { guided: 'match', elim: 'match', studio: 'match', pair: 'pairs', review: 'pairs', queue: 'pairs', vid: 'video', vc: 'video', img: 'image', ic: 'image' },
        defaultTab: 'match',
        lsKey: 'fafo_compare_hub_last_tab',
        messageType: 'fafo-compare-tab',
        keyMap: { '1': 'match', '2': 'pairs', '3': 'video', '4': 'image' },
        reportTitle: 'FAFO Compare Hub',
        reportLines: ['Tabs: Guided Match · Pair Review · Video Comparator · Image Comparator', 'Counterparts: Media Hub · VSR · Pair Review · Guided Match'],
      });
    })();
  </script>

'''
    compare.write_text(text[:start] + script + text[end:], encoding="utf-8")
    print("  OK   Compare Hub uses shared mount")


def patch_version():
    (ROOT / "VERSION").write_text("3.0.4\n", encoding="utf-8")
    ver = ROOT / "shared" / "aitoolbox-version.js"
    t = ver.read_text(encoding="utf-8")
    t = t.replace("var V = '3.0.3';", "var V = '3.0.4';")
    t = t.replace("var V = '3.0.2';", "var V = '3.0.4';")
    ver.write_text(t, encoding="utf-8")
    print("  OK   VERSION 3.0.4")


def patch_media_js_export():
    path = ROOT / "shared" / "aitoolbox-media.js"
    old = '''    global.AIToolboxMedia = {
        watchServer: watchServer,
        bindSearch: bindSearch,
        safeJson: safeJson,
        rafify: rafify,
        observeVideos: observeVideos,
        isIframe: isIframe,
    };
'''
    new = '''    global.AIToolboxMedia = {
        watchServer: watchServer,
        bindSearch: bindSearch,
        safeJson: safeJson,
        rafify: rafify,
        observeVideos: observeVideos,
        isIframe: isIframe,
        // aliases once aitoolbox-dom.js is present
        get el() { return (global.AIToolboxDom && AIToolboxDom.el) || null; },
        get bind() { return (global.AIToolboxDom && AIToolboxDom.bind) || null; },
        get escapeHtml() { return (global.AIToolboxDom && AIToolboxDom.escapeHtml) || null; },
        get withBusy() { return (global.AIToolboxDom && AIToolboxDom.withBusy) || null; },
        get recentFolders() { return (global.AIToolboxDom && AIToolboxDom.recentFolders) || (function () { return []; }); },
        get pushRecentFolder() { return (global.AIToolboxDom && AIToolboxDom.pushRecentFolder) || (function () { return []; }); },
    };
'''
    sub_once(path, old, new, "media.js aliases DOM kit")


def main():
    print("== media 3.0.4 ==")
    patch_scan_directory()
    patch_list_pairs_and_tags()
    patch_library_extras()
    patch_server_scan_jobs()
    patch_api_js()
    patch_html_media_inject()
    patch_library_html()
    patch_comparators()
    patch_hubs()
    patch_version()
    patch_media_js_export()
    print("done")


if __name__ == "__main__":
    sys.exit(main() or 0)
