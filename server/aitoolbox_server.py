"""
AI Toolbox Local Server — powers the HTML tools with real file system access.
Run: python aitoolbox_server.py

Binds to a dedicated loopback host + port (see shared/aitoolbox-bind.json)
so it never fights FAFO companion or other apps on 127.0.0.1:8765.
"""
from __future__ import annotations

import json
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import media_ops as ops
import playlists as pl
import debug_log as dbg
import verifone_ops as vf
import commander_live as cmd_live
import journal_ops as journal
from db import init_db
from fastapi import Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
BIND_FILE = ROOT / "shared" / "aitoolbox-bind.json"

# Defaults match shared/aitoolbox-bind.json and shared/aitoolbox-config.js
DEFAULT_HOST = "127.0.0.87"
DEFAULT_PORT = 18765


def read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.00.00"
    except OSError:
        return "0.00.00"


def load_bind() -> tuple[str, int]:
    """Resolve bind host/port: env override → bind.json → defaults."""
    host = os.environ.get("AITOOLBOX_HOST", "").strip()
    port_raw = os.environ.get("AITOOLBOX_PORT", "").strip()
    port: int | None = None
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError:
            port = None

    if BIND_FILE.is_file():
        try:
            data = json.loads(BIND_FILE.read_text(encoding="utf-8"))
            if not host:
                host = str(data.get("host") or "").strip()
            if port is None and data.get("port") is not None:
                port = int(data["port"])
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if not host:
        host = DEFAULT_HOST
    if port is None or port <= 0 or port > 65535:
        port = DEFAULT_PORT
    return host, port


TOOLBOX_VERSION = read_version()
BIND_HOST, BIND_PORT = load_bind()

app = FastAPI(title="AI Toolbox Server", version=TOOLBOX_VERSION)
# allow_credentials=True + allow_origins=["*"] is invalid CORS and breaks
# fetch() from file:// (Origin: null) and some Chromium private-network cases.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

init_db()
try:
    vf.ensure_tables()
except Exception:
    pass


@app.middleware("http")
async def debug_request_middleware(request: Request, call_next):
    # Chromium Private Network Access preflight (file:// / http → 127.x)
    if request.method == "OPTIONS" and request.headers.get(
        "access-control-request-private-network"
    ):
        from starlette.responses import Response

        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin") or "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Allow-Private-Network": "true",
            },
        )
    response = await call_next(request)
    response.headers.setdefault("Access-Control-Allow-Private-Network", "true")
    if response.status_code >= 500:
        dbg.log("server", "error", f"{request.method} {request.url.path} → {response.status_code}")
    elif response.status_code >= 400:
        dbg.log("server", "warn", f"{request.method} {request.url.path} → {response.status_code}")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        dbg.log("server", "error", str(exc.detail), {"path": request.url.path})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    dbg.log("server", "error", str(exc), {"path": request.url.path, "type": type(exc).__name__})
    return JSONResponse(status_code=500, content={"detail": str(exc)})


class DirAdd(BaseModel):
    path: str


class MediaPatch(BaseModel):
    tags: list[str] | None = None
    notes: str | None = None
    rank: int | None = None
    category: str | None = None
    status: str | None = None
    # Default ON — write System.Keywords / System.Rating into the real file
    write_file_tags: bool = True
    # When true and media is in a pair, also add shared tags (+ optional rank) to the partner
    tag_pair_partner: bool = False
    # When tagging partner, strip role tags like "upscaled"/"source" (recommended)
    shared_only_on_partner: bool = True


class BatchMeta(BaseModel):
    ids: list[str]
    rank: int | None = None
    category: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    write_file_tags: bool = True


class BatchRename(BaseModel):
    ids: list[str]
    pattern: str


class BatchTags(BaseModel):
    ids: list[str]
    tags: list[str]
    write_file_tags: bool = True


class FileMetaWrite(BaseModel):
    """Write Explorer-visible tags/rating to a real file (used by FAFO + tools)."""
    path: str | None = None
    name: str | None = None
    size: int | None = None
    mtime: float | None = None
    tags: list[str] | None = None
    rating: int | None = None
    update_catalog: bool = True


class MediaDelete(BaseModel):
    ids: list[str]
    to_trash: bool = True


class PairCreate(BaseModel):
    name: str = ""
    before_media_id: str
    after_media_id: str
    kind: str = "video"
    pinned: bool = False
    notes: str = ""


class PairFromPaths(BaseModel):
    before_path: str
    after_path: str
    name: str = ""
    kind: str = "video"
    pinned: bool = True
    notes: str = ""


class PairPatch(BaseModel):
    name: str | None = None
    pinned: bool | None = None
    notes: str | None = None


class PairTagBoth(BaseModel):
    """Apply the same project tags to both files in a before/after pair."""
    tags: list[str]
    rank: int | None = None
    write_file_tags: bool = True
    shared_only: bool = True


class AutoPairRequest(BaseModel):
    min_confidence: float = 0.7
    limit: int = 200
    dry_run: bool = False
    pin: bool = True
    kind: str | None = None


class ThumbCapture(BaseModel):
    timestamp: float = 0
    sidecar: bool = True


class RenameOne(BaseModel):
    new_name: str


class DebugEntry(BaseModel):
    source: str = "client"
    level: str = "info"
    message: str
    extra: dict | None = None
    ts: str | None = None


class MediaPathsRequest(BaseModel):
    ids: list[str]


class PlaylistCreate(BaseModel):
    name: str
    description: str = ""
    kind: str = "mixed"


class PlaylistPatch(BaseModel):
    name: str | None = None
    description: str | None = None


class PlaylistItemsAdd(BaseModel):
    ids: list[str]


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ffmpeg": ops.find_ffmpeg() is not None,
        "version": TOOLBOX_VERSION,
        "host": BIND_HOST,
        "port": BIND_PORT,
        "endpoint": f"http://{BIND_HOST}:{BIND_PORT}",
        "features": [
            "vsr_pipeline",
            "duplicates",
            "tag_rules",
            "tray",
            "git_manager",
            "unique_bind",
            "tool_icons",
            "commander_sites",
            "pc_diagnostics",
        ],
        "commanderConsole": f"http://{BIND_HOST}:{BIND_PORT}/toolbox/Verifone%20Tools/Commander%20Site%20Console.html",
    }


# Serve toolbox HTML/tools from the same origin as the API so browsers do not
# block fetch() (file:// → 127.x private network / CORS edge cases).
@app.get("/toolbox/{file_path:path}")
def toolbox_static(file_path: str):
    """Read-only static files under the toolbox root (HTML tools + shared JS)."""
    # Normalize and block path traversal
    rel = Path(file_path.replace("\\", "/"))
    if ".." in rel.parts or rel.is_absolute():
        raise HTTPException(400, "Invalid path")
    target = (ROOT / rel).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as e:
        raise HTTPException(403, "Path outside toolbox") from e
    if not target.is_file():
        raise HTTPException(404, f"Not found: {file_path}")
    # Skip sensitive trees
    blocked = {".git", ".venv", "node_modules", "__pycache__"}
    if any(part in blocked for part in target.relative_to(ROOT.resolve()).parts):
        raise HTTPException(403, "Forbidden")
    # Never serve the SQLite DBs or secrets
    if target.suffix.lower() in {".db", ".db-wal", ".db-shm", ".env"}:
        raise HTTPException(403, "Forbidden")
    media = None
    lower = target.suffix.lower()
    if lower == ".html":
        media = "text/html; charset=utf-8"
    elif lower == ".js":
        media = "application/javascript; charset=utf-8"
    elif lower == ".css":
        media = "text/css; charset=utf-8"
    elif lower == ".json":
        media = "application/json; charset=utf-8"
    return FileResponse(target, media_type=media)


@app.get("/commander")
def commander_redirect():
    """Shortcut to Commander Site Console over HTTP (same-origin as API)."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url="/toolbox/Verifone%20Tools/Commander%20Site%20Console.html",
        status_code=307,
    )


# --- Commander (VAPS) site backup console ---

class VfRootBody(BaseModel):
    path: str | None = None
    # When true (default for multi-folder), POST /sync scans all watched folders
    all: bool | None = True
    set_as_primary: bool | None = False


class VfWatchFoldersBody(BaseModel):
    paths: list[str] | None = None
    primary: str | None = None


class VfPunchBody(BaseModel):
    id: str | None = None
    path: str | None = None


class VfSurveyBody(BaseModel):
    survey: dict | None = None


@app.get("/api/verifone/status")
def verifone_status():
    return vf.status(ROOT)


@app.get("/api/verifone/watch-folders")
def verifone_list_watch_folders():
    """List machine-local folders scanned for Commander site exports."""
    st = vf.status(ROOT)
    return {
        "ok": True,
        "watchFolders": st.get("watchFolders") or [],
        "watchFolderDetails": st.get("watchFolderDetails") or [],
        "sitesRoot": st.get("sitesRoot"),
        "localPathsConfig": st.get("localPathsConfig"),
    }


@app.put("/api/verifone/watch-folders")
def verifone_put_watch_folders(body: VfWatchFoldersBody):
    """Replace the full watch list (each tech sets paths on their own PC)."""
    if not body.paths:
        raise HTTPException(400, "paths array required (at least one folder)")
    try:
        result = vf.set_watch_folders(body.paths, ROOT, primary=body.primary)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result


@app.post("/api/verifone/watch-folders")
def verifone_add_watch_folder(body: VfRootBody):
    """Add one folder to the watch list."""
    if not body.path:
        raise HTTPException(400, "path required")
    return vf.add_watch_folder(body.path, ROOT, set_as_primary=bool(body.set_as_primary))


@app.delete("/api/verifone/watch-folders")
def verifone_remove_watch_folder(path: str = ""):
    """Stop watching a folder (does not delete files). Query: ?path=..."""
    if not path or not str(path).strip():
        raise HTTPException(400, "path query parameter required")
    return vf.remove_watch_folder(path, ROOT)


@app.post("/api/verifone/watch-folders/pick")
def verifone_pick_watch_folder(set_as_primary: bool = False):
    """Native folder picker → add to watch list (Windows tkinter)."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select Commander backup folder to watch")
        root.destroy()
        if not path:
            raise HTTPException(400, "Cancelled")
        return vf.add_watch_folder(path, ROOT, set_as_primary=set_as_primary)
    except ImportError as e:
        raise HTTPException(500, "tkinter not available for folder picker") from e


@app.get("/api/verifone/sites")
def verifone_sites(
    q: str | None = None,
    customer: str | None = None,
    root: str | None = None,
    grouped: bool = True,
):
    if grouped:
        return {"ok": True, "grouped": True, "groups": vf.group_sites(q=q, customer=customer, root=root)}
    return {"ok": True, "grouped": False, "sites": vf.list_sites(q=q, customer=customer, root=root)}


@app.get("/api/verifone/sites/{site_id}")
def verifone_site_detail(site_id: str):
    row = vf.get_site(site_id)
    if not row:
        raise HTTPException(404, "Site export not found - run Sync first")
    # attach equipment from dossier if present
    d = row.get("dossier") or {}
    row["equipment"] = d.get("equipment") or {}
    row["softwareVersion"] = d.get("softwareVersion") or ""
    row["brand"] = d.get("brand") or ""
    return {"ok": True, "site": row}


@app.get("/api/verifone/sites/{site_id}/files")
def verifone_site_files(site_id: str):
    try:
        files = vf.list_export_files(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"ok": True, "files": files}


@app.get("/api/verifone/sites/{site_id}/files/{filename}")
def verifone_site_file_content(site_id: str, filename: str):
    try:
        data = vf.read_export_file(site_id, filename)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"ok": True, **data}


@app.post("/api/verifone/sync")
def verifone_sync(body: VfRootBody | None = None):
    """
    Scan watched Commander backup folder(s) for new/updated site exports.

    Default: scan ALL configured watch folders (so new sites like Quick N Easy 8
    appear without manual re-index). Pass {"path": "...", "all": false} to scan one.
    """
    scan_all = True if body is None else (body.all is not False)
    single = (body.path if body else None) or None
    try:
        if single and not scan_all:
            result = vf.sync_root(single)
        elif single and scan_all:
            # Explicit path + all: ensure path is watched, then scan everything
            folders = vf.get_watch_folders(ROOT)
            if single not in folders:
                vf.add_watch_folder(single, ROOT)
            result = vf.sync_all_roots(ROOT)
        else:
            result = vf.sync_all_roots(ROOT)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return result


@app.post("/api/verifone/root")
def verifone_set_root(body: VfRootBody):
    """Set primary backup root (also added to the watch list)."""
    if not body.path:
        raise HTTPException(400, "path required")
    return {"ok": True, **vf.set_sites_root(body.path, ROOT)}


# --- Commander live status HUD (reachability + credential profiles) ---

class CmdLiveProbeBody(BaseModel):
    host: str
    username: str | None = ""
    password: str | None = ""
    otp: str | None = None  # Config OTP when CGIPortal.OTPRequired
    ports: list[int] | None = None
    export_id: str | None = None
    profile_id: str | None = None
    do_login: bool = True
    do_http: bool = True
    ping_count: int = 2
    timeout: float = 1.5


class CmdProfileBody(BaseModel):
    id: str | None = None
    name: str | None = None
    host: str
    username: str | None = ""
    password: str | None = None
    export_id: str | None = None
    ports: list[int] | None = None
    notes: str | None = ""
    keep_password_if_empty: bool = True


@app.get("/api/verifone/live/profiles")
def verifone_live_profiles():
    """Saved Commander connection profiles (passwords never returned in list)."""
    return {"ok": True, "profiles": cmd_live.list_profiles()}


@app.get("/api/verifone/live/profiles/{profile_id}")
def verifone_live_profile_get(profile_id: str, include_password: bool = False):
    row = cmd_live.get_profile(profile_id, include_password=include_password)
    if not row:
        raise HTTPException(404, "Profile not found")
    return {"ok": True, "profile": row}


@app.post("/api/verifone/live/profiles")
def verifone_live_profile_save(body: CmdProfileBody):
    try:
        row = cmd_live.save_profile(
            name=body.name or body.host,
            host=body.host,
            username=body.username or "",
            password=body.password,
            profile_id=body.id,
            export_id=body.export_id,
            ports=body.ports,
            notes=body.notes or "",
            keep_password_if_empty=body.keep_password_if_empty,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "profile": row}


@app.delete("/api/verifone/live/profiles/{profile_id}")
def verifone_live_profile_delete(profile_id: str):
    return cmd_live.delete_profile(profile_id)


@app.get("/api/verifone/live/targets")
def verifone_live_targets(limit: int = 40):
    """Indexed sites with suggested LAN/MNSP hosts for the HUD connect picker."""
    return {"ok": True, "targets": cmd_live.suggested_targets_from_library(limit=limit)}


@app.post("/api/verifone/live/probe")
def verifone_live_probe(body: CmdLiveProbeBody):
    """
    Probe a Commander host: DNS, ping, ports, HTTP discovery, optional login test.
    Loads backup/survey context when export_id is provided.
    """
    if not body.host or not body.host.strip():
        raise HTTPException(400, "host required")
    password = body.password or ""
    # If profile selected and password omitted, load DPAPI secret
    if body.profile_id and not password:
        prof = cmd_live.get_profile(body.profile_id, include_password=True)
        if prof:
            password = prof.get("password") or ""
            if not body.username:
                body.username = prof.get("username") or ""
    try:
        result = cmd_live.gather_status(
            body.host.strip(),
            username=body.username or "",
            password=password,
            otp=body.otp,
            ports=body.ports,
            export_id=body.export_id,
            profile_id=body.profile_id,
            ping_count=body.ping_count,
            do_login=body.do_login,
            do_http=body.do_http,
            timeout=body.timeout,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result


@app.get("/api/verifone/live/import-export")
def verifone_import_export_status():
    """Detect Verifone Import-Export Utility install paths on this PC."""
    return cmd_live.detect_import_export_utility()


class CmdLaunchImportExportBody(BaseModel):
    tool_id: str | None = None


@app.post("/api/verifone/live/import-export/launch")
def verifone_import_export_launch(body: CmdLaunchImportExportBody | None = None):
    """
    Launch ImportExportUtility.exe for SMS/Commander config backups.
    Uses same per-site Manager credentials as Config Client (entered in the utility UI).
    """
    tool_id = body.tool_id if body else None
    try:
        return cmd_live.launch_import_export_utility(tool_id=tool_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except OSError as e:
        raise HTTPException(500, f"Failed to launch: {e}") from e


# --- Journal Browser (T-log periods + transaction search / drill-down) ---

class JournalLoginBody(BaseModel):
    host: str
    username: str | None = ""
    password: str | None = ""
    otp: str | None = None
    profile_id: str | None = None


class JournalPeriodBody(BaseModel):
    session_id: str
    period_key: str
    force: bool = False


class JournalSearchBody(BaseModel):
    session_id: str
    period_key: str
    criteria: dict | None = None


class JournalXmlBody(BaseModel):
    path: str


class JournalSearchLocalBody(BaseModel):
    transactions: list[dict] | None = None
    criteria: dict | None = None


@app.post("/api/verifone/journal/login")
def verifone_journal_login(body: JournalLoginBody):
    """Authenticate to Commander CGILink and list journal periods (vtlogpdlist)."""
    if not body.host or not body.host.strip():
        raise HTTPException(400, "host required")
    password = body.password or ""
    username = body.username or ""
    if body.profile_id and not password:
        prof = cmd_live.get_profile(body.profile_id, include_password=True)
        if prof:
            password = prof.get("password") or ""
            username = username or (prof.get("username") or "")
    try:
        return journal.journal_login(
            body.host.strip(),
            username,
            password,
            otp=body.otp,
            profile_id=body.profile_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/journal/session")
def verifone_journal_session(session_id: str | None = None):
    return journal.session_status(session_id)


@app.post("/api/verifone/journal/logout")
def verifone_journal_logout(session_id: str = Query("")):
    if not session_id:
        raise HTTPException(400, "session_id required")
    return journal.journal_logout(session_id)


@app.get("/api/verifone/journal/periods")
def verifone_journal_periods(session_id: str, refresh: bool = True):
    try:
        return journal.journal_periods(session_id, refresh=refresh)
    except KeyError as e:
        raise HTTPException(401, str(e)) from e


@app.post("/api/verifone/journal/load")
def verifone_journal_load(body: JournalPeriodBody):
    """Get Data — fetch T-log for a period and parse transactions."""
    try:
        return journal.journal_load_period(body.session_id, body.period_key, force=body.force)
    except KeyError as e:
        raise HTTPException(401, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/journal/search")
def verifone_journal_search(body: JournalSearchBody):
    """Search/filter transactions in a loaded period (register, amount, time, fuel, etc.)."""
    try:
        return journal.journal_search(body.session_id, body.period_key, body.criteria or {})
    except KeyError as e:
        raise HTTPException(401, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/journal/search-local")
def verifone_journal_search_local(body: JournalSearchLocalBody):
    """Client already has transactions (or offline XML parse) — filter only."""
    return journal.search_transactions(body.transactions or [], body.criteria or {})


@app.post("/api/verifone/journal/load-xml")
def verifone_journal_load_xml(body: JournalXmlBody):
    """Offline: parse a saved period/T-log XML from disk."""
    if not body.path:
        raise HTTPException(400, "path required")
    try:
        return journal.journal_load_xml_file(body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


class JournalScanBody(BaseModel):
    path: str | None = None
    site_id: str | None = None


@app.post("/api/verifone/journal/scan-backup")
def verifone_journal_scan_backup(body: JournalScanBody):
    """Scan a site export / watched backup folder for offline T-log XML files."""
    path = (body.path or "").strip()
    if not path and body.site_id:
        row = vf.get_site(body.site_id)
        if not row:
            raise HTTPException(404, "site not found")
        path = row.get("path") or row.get("export_path") or ""
    if not path:
        raise HTTPException(400, "path or site_id required")
    return journal.scan_backup_journal_files(path)


@app.get("/api/verifone/sites/{site_id}/journal-files")
def verifone_site_journal_files(site_id: str):
    """List possible offline journal/T-log XML under this site's backup export path."""
    row = vf.get_site(site_id)
    if not row:
        raise HTTPException(404, "site not found")
    path = row.get("path") or row.get("export_path") or ""
    if not path:
        raise HTTPException(404, "site has no export path")
    return journal.scan_backup_journal_files(path)


# --- Local backup PLU lookup + staged edits (safe copies, review queue) ---
import backup_edit_ops as bedit


class BackupLookupBody(BaseModel):
    site_id: str
    barcode: str | None = None
    description: str | None = None
    department: str | None = None
    product: str | None = None


class BackupStageBody(BaseModel):
    site_id: str
    upc: str
    field: str
    new_value: str
    old_value: str | None = None
    source: str | None = None


class BackupChangeStatusBody(BaseModel):
    site_id: str
    change_id: str
    status: str  # pending | verified | rejected


class BackupApplyBody(BaseModel):
    site_id: str
    only_verified: bool = True


class BackupRestoreBody(BaseModel):
    site_id: str
    copy_id: str


@app.post("/api/verifone/backup/lookup-item")
def verifone_backup_lookup_item(body: BackupLookupBody):
    """Match a journal receipt line to PLUs.xml in the site's local SMS backup."""
    if not body.site_id:
        raise HTTPException(400, "site_id required")
    try:
        return bedit.lookup_item(
            body.site_id,
            barcode=body.barcode,
            description=body.description,
            department=body.department,
            product=body.product,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.get("/api/verifone/backup/{site_id}/changes")
def verifone_backup_list_changes(site_id: str, include_applied: bool = True):
    return bedit.list_changes(site_id, include_applied=include_applied)


@app.post("/api/verifone/backup/stage")
def verifone_backup_stage(body: BackupStageBody):
    """Stage a PLU field edit against the local backup (not live Commander)."""
    try:
        return bedit.stage_plu_edit(
            body.site_id,
            upc=body.upc,
            field=body.field,
            new_value=body.new_value,
            old_value=body.old_value,
            source=body.source,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.post("/api/verifone/backup/change-status")
def verifone_backup_change_status(body: BackupChangeStatusBody):
    try:
        return bedit.set_change_status(body.site_id, body.change_id, body.status)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/backup/{site_id}/verify-all")
def verifone_backup_verify_all(site_id: str):
    return bedit.verify_all_pending(site_id)


@app.post("/api/verifone/backup/apply")
def verifone_backup_apply(body: BackupApplyBody):
    """Apply verified staged edits to local backup files (safe-copy first)."""
    try:
        return bedit.apply_verified_changes(body.site_id, only_verified=body.only_verified)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.get("/api/verifone/backup/{site_id}/safe-copies")
def verifone_backup_safe_copies(site_id: str):
    return bedit.list_safe_copies(site_id)


@app.post("/api/verifone/backup/restore-safe")
def verifone_backup_restore_safe(body: BackupRestoreBody):
    try:
        return bedit.restore_safe_copy(body.site_id, body.copy_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.post("/api/verifone/backup/prune-safe")
def verifone_backup_prune_safe(site_id: str | None = None):
    return bedit.prune_safe_copies(site_id)


# --- Master site profile (tech liferaft — group-level, not per backup version) ---
import site_profile_ops as sprof


class MasterProfileBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    profile: dict | None = None
    overwrite_empty_only: bool = True


@app.get("/api/verifone/master-profiles")
def verifone_master_profiles_list():
    return sprof.list_master_profiles()


@app.get("/api/verifone/master-profile")
def verifone_master_profile_get(group_key: str | None = None, export_id: str | None = None, merge: bool = True):
    """Physical-site liferaft profile (auto-fills empty fields from backup/survey when merge=true)."""
    try:
        return {"ok": True, "profile": sprof.get_master_profile(group_key=group_key, export_id=export_id, merge_sources=merge)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.put("/api/verifone/master-profile")
def verifone_master_profile_save(body: MasterProfileBody):
    if not body.group_key and not body.export_id:
        raise HTTPException(400, "group_key or export_id required")
    try:
        gk = sprof.resolve_group_key(body.group_key, body.export_id)
        return sprof.save_master_profile(gk, body.profile or {})
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/master-profile/refresh")
def verifone_master_profile_refresh(body: MasterProfileBody):
    """Re-merge from latest backup/survey into empty fields (preserves tech-entered data by default)."""
    try:
        prof = sprof.refresh_master_from_backup(
            group_key=body.group_key,
            export_id=body.export_id,
            overwrite_empty_only=body.overwrite_empty_only,
        )
        return {"ok": True, "profile": prof}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/master-profile/export-md")
def verifone_master_profile_export_md(group_key: str | None = None, export_id: str | None = None):
    try:
        gk = sprof.resolve_group_key(group_key, export_id)
        return sprof.export_liferaft_markdown(gk)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class ManagerPasswordRotateBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    direction: str = "next"  # next | prev | set
    letter: str | None = None
    mark_changed: bool = True
    note: str | None = ""
    sync_live_profile: bool = True


class ManagerPasswordSetBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    password: str
    mark_changed: bool = True
    scheme: str | None = None  # letter_cycle | manual
    note: str | None = ""
    sync_live_profile: bool = True


@app.post("/api/verifone/master-profile/password/rotate")
def verifone_master_password_rotate(body: ManagerPasswordRotateBody):
    """Advance Manager password letter A→B→C→D→E→A for this site (local liferaft + optional DPAPI profile)."""
    try:
        gk = sprof.resolve_group_key(body.group_key, body.export_id)
        return sprof.rotate_manager_password(
            gk,
            direction=body.direction or "next",
            set_letter=body.letter,
            mark_changed=body.mark_changed,
            note=body.note or "",
            sync_live_profile=body.sync_live_profile,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/master-profile/password/set")
def verifone_master_password_set(body: ManagerPasswordSetBody):
    """Set Manager password on site liferaft (parses trailing letter when scheme is letter_cycle)."""
    try:
        gk = sprof.resolve_group_key(body.group_key, body.export_id)
        return sprof.set_manager_password(
            gk,
            body.password,
            mark_changed=body.mark_changed,
            scheme=body.scheme,
            note=body.note or "",
            sync_live_profile=body.sync_live_profile,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/sites/{site_id}/survey")
def verifone_get_survey(site_id: str):
    try:
        survey = vf.get_survey(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, "survey": survey}


@app.put("/api/verifone/sites/{site_id}/survey")
def verifone_put_survey(site_id: str, body: VfSurveyBody):
    if not body.survey:
        raise HTTPException(400, "survey object required")
    try:
        result = vf.save_survey(site_id, body.survey)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return result


@app.post("/api/verifone/sites/{site_id}/survey/export-md")
def verifone_export_survey_md(site_id: str):
    try:
        return vf.export_survey_markdown(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/punch-list")
def verifone_punch_list(body: VfPunchBody):
    row = None
    if body.id:
        row = vf.get_site(body.id)
    if not row and body.path:
        # build live dossier if path exists
        p = Path(body.path)
        root = vf.get_sites_root(ROOT)
        if not p.is_dir():
            raise HTTPException(404, f"Export path not found: {body.path}")
        root_p = Path(root) if root else p.parent
        try:
            dossier = vf.build_dossier(p, root_p if root_p.is_dir() else p.parent)
        except Exception as e:
            raise HTTPException(500, f"Failed to read export: {e}") from e
        result = vf.prefill_punch_list(ROOT, dossier)
        return result
    if not row:
        raise HTTPException(400, "Provide site id or path")
    dossier = row.get("dossier") or {}
    if not dossier:
        dossier = {
            "customer": row.get("customer"),
            "displayName": row.get("display_name"),
            "siteId": row.get("site_id"),
            "serviceId": row.get("service_id"),
            "storePhone": row.get("store_phone"),
            "postalCode": row.get("postal_code"),
            "path": row.get("path"),
            "relativePath": row.get("relative_path"),
            "prefill": {
                "siteName": row.get("display_name"),
                "customer": row.get("customer"),
                "storeNumber": row.get("site_id"),
                "serviceId": row.get("service_id"),
                "phone": row.get("store_phone"),
                "postalCode": row.get("postal_code"),
                "hasCSiteConfig": bool(row.get("cloud_agent") is not None),
                "hasMobileMop28": bool(row.get("has_mobile_mop")),
                "dcrRewardsKey": bool(row.get("dcr_rewards")),
                "registerIds": row.get("register_ids") or "",
                "namedTanks": row.get("named_tanks") or "",
            },
        }
    result = vf.prefill_punch_list(ROOT, dossier)
    return result


# --- Shared tool icons (repo assets/tool-icons) ---
ICONS_DIR = ROOT / "assets" / "tool-icons"
ICONS_MANIFEST = ICONS_DIR / "manifest.json"
_ICON_EXT_OK = {
    ".png", ".gif", ".jpg", ".jpeg", ".webp", ".ico", ".svg", ".bmp",
}
_ICON_MIME_EXT = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}


def _safe_tool_id(tool_id: str) -> str:
    tid = (tool_id or "").strip().lower()
    tid = "".join(c if c.isalnum() or c in "-_" else "-" for c in tid)
    tid = tid.strip("-_") or "tool"
    if tid in {".", ".."} or len(tid) > 80:
        raise HTTPException(400, "Invalid tool id")
    return tid


def _load_icon_manifest() -> dict:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    if ICONS_MANIFEST.is_file():
        try:
            data = json.loads(ICONS_MANIFEST.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("icons", {})
                if not isinstance(data["icons"], dict):
                    data["icons"] = {}
                return data
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return {
        "version": 1,
        "updatedAt": None,
        "note": "Shared tool icons for all users.",
        "app": None,
        "icons": {},
    }


def _save_icon_manifest(data: dict) -> dict:
    from datetime import datetime, timezone

    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    data["version"] = int(data.get("version") or 1)
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    data.setdefault("icons", {})
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    ICONS_MANIFEST.write_text(payload + "\n", encoding="utf-8")
    # JS companion so file:// launcher can load without fetch CORS issues
    js_path = ICONS_DIR / "manifest.js"
    js_path.write_text(
        "/* Auto-generated — shared tool icons. Do not edit by hand. */\n"
        "window.AITOOLBOX_ICON_MANIFEST = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    return data


def _ext_from_name_or_mime(filename: str | None, mime: str | None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext == ".jpeg":
            ext = ".jpg"
        if ext in _ICON_EXT_OK:
            return ext
    if mime:
        m = mime.split(";")[0].strip().lower()
        if m in _ICON_MIME_EXT:
            return _ICON_MIME_EXT[m]
    return ".png"


class IconSaveBody(BaseModel):
    """Save a tool icon into assets/tool-icons and update manifest.json."""

    toolId: str
    # data URL (data:image/png;base64,...) or raw base64
    dataUrl: str | None = None
    base64: str | None = None
    mimeType: str | None = None
    filename: str | None = None
    # When true, also set as the main app / Desktop shortcut icon
    asAppIcon: bool = False


@app.get("/api/icons/manifest")
def api_icons_manifest():
    data = _load_icon_manifest()
    # Expose absolute file paths only as relative web paths for the launcher
    icons_out = {}
    for tid, fname in (data.get("icons") or {}).items():
        if not fname:
            continue
        p = ICONS_DIR / str(fname)
        icons_out[tid] = {
            "file": str(fname),
            "url": f"assets/tool-icons/{fname}",
            "exists": p.is_file(),
        }
    app_name = data.get("app")
    app_out = None
    if app_name:
        p = ICONS_DIR / str(app_name)
        app_out = {
            "file": str(app_name),
            "url": f"assets/tool-icons/{app_name}",
            "exists": p.is_file(),
        }
    return {
        "ok": True,
        "version": data.get("version", 1),
        "updatedAt": data.get("updatedAt"),
        "app": app_out,
        "icons": icons_out,
        "dir": str(ICONS_DIR),
    }


@app.get("/api/icons/file/{filename}")
def api_icons_file(filename: str):
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext not in _ICON_EXT_OK:
        raise HTTPException(400, "Unsupported icon type")
    path = ICONS_DIR / name
    if not path.is_file():
        raise HTTPException(404, "Icon not found")
    return FileResponse(path)


@app.post("/api/icons")
def api_icons_save(body: IconSaveBody):
    import base64
    import re

    tid = _safe_tool_id(body.toolId)
    raw_b64 = body.base64
    mime = body.mimeType
    if body.dataUrl:
        m = re.match(
            r"^data:([^;]+);base64,(.+)$",
            body.dataUrl.strip(),
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not m:
            raise HTTPException(400, "dataUrl must be a base64 data URL")
        mime = m.group(1).strip()
        raw_b64 = m.group(2).strip()
    if not raw_b64:
        raise HTTPException(400, "Provide dataUrl or base64")

    try:
        blob = base64.b64decode(raw_b64, validate=False)
    except Exception as e:
        raise HTTPException(400, f"Invalid base64: {e}") from e
    if not blob:
        raise HTTPException(400, "Empty image data")
    if len(blob) > 12 * 1024 * 1024:
        raise HTTPException(400, "Icon too large (max 12 MB)")

    ext = _ext_from_name_or_mime(body.filename, mime)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove previous files for this tool id (any extension)
    for old in ICONS_DIR.glob(f"{tid}.*"):
        if old.suffix.lower() in _ICON_EXT_OK:
            try:
                old.unlink()
            except OSError:
                pass

    dest_name = f"{tid}{ext}"
    dest = ICONS_DIR / dest_name
    dest.write_bytes(blob)

    manifest = _load_icon_manifest()
    if tid == "app" or body.asAppIcon:
        manifest["app"] = dest_name
        # Keep app listed under icons as well for uniform lookup
        manifest.setdefault("icons", {})
        if tid != "app":
            manifest["icons"][tid] = dest_name
        else:
            # app id reserved for main launcher/shortcut
            pass
    else:
        manifest.setdefault("icons", {})[tid] = dest_name
    _save_icon_manifest(manifest)

    return {
        "ok": True,
        "toolId": tid,
        "file": dest_name,
        "url": f"assets/tool-icons/{dest_name}",
        "bytes": len(blob),
        "path": str(dest),
    }


@app.delete("/api/icons/{tool_id}")
def api_icons_delete(tool_id: str):
    tid = _safe_tool_id(tool_id)
    manifest = _load_icon_manifest()
    removed = []
    for old in ICONS_DIR.glob(f"{tid}.*"):
        if old.suffix.lower() in _ICON_EXT_OK:
            try:
                old.unlink()
                removed.append(old.name)
            except OSError:
                pass
    icons = manifest.setdefault("icons", {})
    if tid in icons:
        icons.pop(tid, None)
    if tid == "app" or manifest.get("app") in removed:
        if tid == "app":
            manifest["app"] = None
    _save_icon_manifest(manifest)
    return {"ok": True, "toolId": tid, "removed": removed}


@app.get("/api/directories")
def api_list_dirs():
    return ops.list_directories()


@app.post("/api/directories")
def api_add_dir(body: DirAdd):
    try:
        return ops.add_directory(body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/directories/pick")
def api_pick_dir():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select folder to watch")
        root.destroy()
        if not path:
            raise HTTPException(400, "Cancelled")
        return ops.add_directory(path)
    except ImportError:
        raise HTTPException(500, "tkinter not available")


@app.post("/api/pick-folder")
def api_pick_folder_only():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select folder to scan")
        root.destroy()
        if not path:
            raise HTTPException(400, "Cancelled")
        return {"path": str(Path(path).resolve())}
    except ImportError:
        raise HTTPException(500, "tkinter not available")


@app.delete("/api/directories/{dir_id}")
def api_remove_dir(dir_id: str):
    ops.remove_directory(dir_id)
    return {"ok": True}


@app.post("/api/scan/{dir_id}")
def api_scan(dir_id: str, recursive: bool = True):
    try:
        n = ops.scan_directory(dir_id, recursive=recursive)
        # scan_directory already relinks pairs from UP-#### file tags
        return {"indexed": n}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/scan/{dir_id}/stream")
def api_scan_stream(dir_id: str, recursive: bool = True):
    progress: list[str] = []

    def run():
        try:
            ops.scan_directory(dir_id, recursive, on_progress=lambda c, r: progress.append(json.dumps({"count": c, "file": r})))
            progress.append(json.dumps({"done": True, "count": len(progress)}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.15)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/media")
def api_query_media(
    search: str = "",
    tags: str = "",
    type: str | None = None,
    dir_id: str | None = None,
    path_prefix: str = "",
    folder_only: bool = False,
    virtual_root: str | None = None,
    category: str | None = None,
    status: str | None = None,
    rank_min: int | None = None,
    sort: str = "name",
    page: int = 0,
    limit: int = 80,
):
    tag_list = [t for t in tags.split(",") if t.strip()] if tags else []
    prefix = path_prefix if path_prefix or folder_only else None
    return ops.query_media(
        search, tag_list, type, dir_id, prefix, folder_only,
        virtual_root, category, status, rank_min, sort, page, limit,
    )


def _serve_media_file(mid: str):
    m = ops.get_media(mid)
    if not m:
        raise HTTPException(404, "Not found")
    p = ops.resolve_path(m)
    if not p.exists():
        raise HTTPException(404, "File missing on disk")
    mt = ops.mime_for_path(m["name"], m["type"])
    return FileResponse(
        p,
        media_type=mt,
        filename=m["name"],
        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"},
    )


@app.get("/api/media/file")
def api_serve_media_query(mid: str = Query(..., description="Media catalog id")):
    """Stream file by id — must be registered before /api/media/{mid}."""
    return _serve_media_file(mid)


@app.get("/api/thumb")
def api_serve_thumb_query(mid: str = Query(...)):
    m = ops.get_media(mid)
    if not m or not m.get("thumb_path"):
        raise HTTPException(404, "No thumbnail")
    p = Path(m["thumb_path"])
    if not p.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/directories/{dir_id}/folders")
def api_folder_index(dir_id: str, path: str = ""):
    if not any(d["id"] == dir_id for d in ops.list_directories()):
        raise HTTPException(404, "Directory not found")
    return ops.list_folder_index(dir_id, path)


@app.get("/api/media/item")
def api_get_media_item(mid: str = Query(...)):
    m = ops.get_media(mid)
    if not m:
        raise HTTPException(404, "Not found")
    return m


@app.patch("/api/media/patch")
def api_patch_media_query(mid: str = Query(...), body: MediaPatch = Body(...)):
    """Update metadata — query id avoids broken paths when id contains slashes."""
    try:
        if body.tag_pair_partner and (body.tags is not None or body.rank is not None):
            result = ops.tag_media_and_pair_partner(
                mid,
                tags=body.tags,
                notes=body.notes,
                rank=body.rank,
                write_file_tags=body.write_file_tags,
                tag_partner=True,
                shared_only_on_partner=body.shared_only_on_partner,
            )
            # Keep response shape as media row + extras for the UI
            media = dict(result.get("media") or {})
            media["tagged_partner"] = result.get("tagged_partner")
            media["partner_id"] = result.get("partner_id")
            media["partner"] = result.get("partner")
            if body.category is not None or body.status is not None:
                media = ops.update_media_meta(
                    mid,
                    category=body.category,
                    status=body.status,
                    write_file_tags=False,
                )
                media = dict(media)
                media["tagged_partner"] = result.get("tagged_partner")
                media["partner_id"] = result.get("partner_id")
            return media
        return ops.update_media_meta(
            mid, body.tags, body.notes, body.rank, body.category, body.status, body.write_file_tags,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/media/rename")
def api_rename_media_query(mid: str = Query(...), body: RenameOne = Body(...)):
    try:
        result = ops.rename_media(mid, body.new_name)
        ops.push_rename_history(body.new_name)
        return result
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/media/thumbnail")
def api_thumb_query(mid: str = Query(...), body: ThumbCapture = ThumbCapture()):
    try:
        return ops.capture_thumbnail(mid, body.timestamp, body.sidecar)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/media/{mid}")
def api_get_media(mid: str):
    m = ops.get_media(mid)
    if not m:
        raise HTTPException(404, "Not found")
    return m


@app.patch("/api/media/{mid}")
def api_patch_media(mid: str, body: MediaPatch):
    try:
        # Delegate to query-style handler logic
        return api_patch_media_query(mid, body)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/media/{mid}/rename")
def api_rename_one(mid: str, body: RenameOne):
    try:
        result = ops.rename_media(mid, body.new_name)
        ops.push_rename_history(body.new_name)
        return result
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/media/batch-rename")
def api_batch_rename(body: BatchRename):
    return {"results": ops.batch_rename(body.ids, body.pattern)}


@app.post("/api/media/batch-tags")
def api_batch_tags(body: BatchTags):
    return {"updated": ops.batch_add_tags(body.ids, body.tags, write_file_tags=body.write_file_tags)}


@app.post("/api/media/batch-meta")
def api_batch_meta(body: BatchMeta):
    return {
        "updated": ops.batch_update_meta(
            body.ids, body.rank, body.category, body.status, body.tags,
            write_file_tags=body.write_file_tags,
        )
    }


@app.post("/api/fs/write-metadata")
def api_fs_write_metadata(body: FileMetaWrite):
    """
    Write Tags + Rating into a real file for Windows Explorer / cross-app use.
    Prefer absolute `path`. Otherwise match catalog by name (+ size/mtime).
    """
    if body.tags is None and body.rating is None:
        raise HTTPException(400, "Provide tags and/or rating")

    # Path-based write
    if body.path:
        p = Path(body.path)
        if not p.is_file():
            raise HTTPException(404, f"File not found: {body.path}")
        return ops.write_metadata_for_path(
            p,
            tags=body.tags,
            rating=body.rating,
            update_catalog=body.update_catalog,
        )

    # Match by identity (FAFO sends name/size/mtime from FileSystemFileHandle)
    if not body.name:
        raise HTTPException(400, "Provide path or name")
    media = ops.find_media_by_identity(body.name, body.size, body.mtime)
    if not media:
        raise HTTPException(
            404,
            "File not in toolbox library. Add the folder in Media Library (or pass absolute path).",
        )
    updated = ops.update_media_meta(
        media["id"],
        tags=body.tags,
        rank=body.rating,
        write_file_tags=True,
    )
    try:
        resolved = str(ops.resolve_path(media))
    except Exception:
        resolved = None
    fw = updated.get("file_write") or {}
    return {
        "ok": bool(fw.get("ok", True)),
        "path": resolved,
        "catalog": updated,
        "file_write": fw,
        "methods": fw.get("methods") or [],
        "errors": fw.get("errors") or [],
    }


@app.get("/api/fs/read-metadata")
def api_fs_read_metadata(path: str = Query(...)):
    from file_metadata import read_file_metadata
    p = Path(path)
    if not p.is_file():
        raise HTTPException(404, "File not found")
    return read_file_metadata(p)


@app.post("/api/media/delete")
def api_delete_media(body: MediaDelete):
    try:
        if len(body.ids) == 1:
            return ops.delete_media(body.ids[0], to_trash=body.to_trash)
        return ops.batch_delete_media(body.ids, to_trash=body.to_trash)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/meta/facets")
def api_meta_facets():
    return ops.get_meta_facets()


@app.get("/api/virtual-folders")
def api_virtual_roots():
    return ops.list_virtual_roots()


@app.get("/api/virtual-folders/{name}/folders")
def api_virtual_folder_index(name: str, path: str = ""):
    return ops.list_virtual_folder_index(name, path)


@app.post("/api/media/paths")
def api_resolve_paths(body: MediaPathsRequest):
    return {"paths": ops.resolve_media_paths(body.ids)}


@app.get("/api/tags")
def api_tags():
    return ops.get_all_tags()


@app.get("/api/rename-history")
def api_rename_history():
    return ops.get_rename_history()


@app.get("/api/pairs")
def api_pairs(kind: str | None = None, pinned: bool = False):
    return ops.list_pairs(kind, pinned_only=pinned)


@app.get("/api/pairs/code/{code}")
def api_pair_by_code(code: str):
    p = ops.get_pair_by_code(code)
    if not p:
        raise HTTPException(404, "Pair not found")
    return p


@app.post("/api/pairs")
def api_create_pair(body: PairCreate):
    try:
        return ops.save_pair(
            body.name, body.before_media_id, body.after_media_id, body.kind,
            pinned=body.pinned, notes=body.notes,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/pairs/from-paths")
def api_create_pair_paths(body: PairFromPaths):
    try:
        return ops.save_pair_from_paths(
            body.before_path, body.after_path, body.name, body.kind,
            pinned=body.pinned, notes=body.notes,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/pairs/auto-upscale")
def api_auto_pair_upscale(body: AutoPairRequest):
    try:
        return ops.auto_pair_upscaled(
            min_confidence=body.min_confidence,
            limit=body.limit,
            dry_run=body.dry_run,
            pin=body.pin,
            kind=body.kind,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/pairs/{pid}")
def api_patch_pair(pid: str, body: PairPatch):
    try:
        return ops.update_pair_meta(pid, name=body.name, pinned=body.pinned, notes=body.notes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/pairs/{pid}/tags")
def api_pair_tag_both(pid: str, body: PairTagBoth):
    """Add the same shared tags (optional rank) to both before + after files in a pair."""
    try:
        return ops.tag_both_in_pair(
            pid,
            body.tags,
            write_file_tags=body.write_file_tags,
            rank=body.rank,
            shared_only=body.shared_only,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/pairs/relink")
def api_pairs_relink():
    """
    Re-attach before/after pairs using durable UP-#### tags on files.
    Use after moving paired files into different folders, then rescanning.
    """
    return ops.relink_pairs_from_metadata()


# --- Library extras: health, verify, smart searches, archive, pair map ---
import library_extras as lex


class SmartSearchBody(BaseModel):
    name: str
    query: dict = {}


class SmartSearchRun(BaseModel):
    query: dict = {}
    page: int = 0
    limit: int = 80


class VerifyTagsBody(BaseModel):
    ids: list[str] | None = None
    limit: int = 500
    fix: bool = False


class ArchivePairBody(BaseModel):
    dest: str
    pair_id: str | None = None  # id or UP-#### code; can also pass as path param


class ImportPairMapBody(BaseModel):
    data: dict
    write_files: bool = True


@app.get("/api/pairs/health")
def api_pair_health(relink: bool = False):
    return lex.pair_health_report(relink=relink)


@app.post("/api/media/verify-tags")
def api_verify_tags(body: VerifyTagsBody):
    return lex.verify_tags_on_disk(body.ids, limit=body.limit, fix=body.fix)


@app.get("/api/pairs/export-map")
def api_export_pair_map():
    return lex.export_pair_map()


@app.post("/api/pairs/import-map")
def api_import_pair_map(body: ImportPairMapBody):
    return lex.import_pair_map(body.data, write_files=body.write_files)


@app.post("/api/pairs/{pid}/archive")
def api_archive_pair(pid: str, body: ArchivePairBody):
    try:
        return lex.archive_pair(pid, body.dest)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/smart-searches")
def api_list_smart_searches():
    return lex.ensure_default_smart_searches()


@app.post("/api/smart-searches")
def api_add_smart_search(body: SmartSearchBody):
    return lex.add_smart_search(body.name, body.query)


@app.delete("/api/smart-searches/{sid}")
def api_del_smart_search(sid: str):
    return {"ok": lex.delete_smart_search(sid)}


@app.post("/api/smart-searches/run")
def api_run_smart_search(body: SmartSearchRun):
    return lex.run_smart_search(body.query, page=body.page, limit=body.limit)


@app.get("/api/pairs/suggest")
def api_suggest_pairs(limit: int = 30):
    return ops.suggest_pairs(limit=limit)


@app.get("/api/pairs/{pid}")
def api_get_pair(pid: str):
    p = ops.get_pair(pid) or ops.get_pair_by_code(pid)
    if not p:
        raise HTTPException(404, "Not found")
    return p


@app.delete("/api/pairs/{pid}")
def api_delete_pair(pid: str):
    ops.delete_pair(pid)
    return {"ok": True}


@app.get("/api/pairs/{pid}/paths")
def api_pair_paths(pid: str):
    try:
        return ops.pair_file_paths(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/media/{mid}/thumbnail")
def api_thumb(mid: str, body: ThumbCapture):
    try:
        return ops.capture_thumbnail(mid, body.timestamp, body.sidecar)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/playlists")
def api_list_playlists():
    return pl.list_playlists()


@app.post("/api/playlists")
def api_create_playlist(body: PlaylistCreate):
    return pl.create_playlist(body.name, body.description, body.kind)


@app.get("/api/playlists/{playlist_id}")
def api_get_playlist(playlist_id: str):
    p = pl.get_playlist(playlist_id)
    if not p:
        raise HTTPException(404, "Not found")
    return p


@app.patch("/api/playlists/{playlist_id}")
def api_patch_playlist(playlist_id: str, body: PlaylistPatch):
    try:
        return pl.update_playlist(playlist_id, body.name, body.description)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.delete("/api/playlists/{playlist_id}")
def api_delete_playlist(playlist_id: str):
    pl.delete_playlist(playlist_id)
    return {"ok": True}


@app.post("/api/playlists/{playlist_id}/items")
def api_add_playlist_items(playlist_id: str, body: PlaylistItemsAdd):
    try:
        return pl.add_items(playlist_id, body.ids)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.delete("/api/playlists/{playlist_id}/items")
def api_remove_playlist_item(playlist_id: str, mid: str = Query(...)):
    pl.remove_item(playlist_id, mid)
    return {"ok": True}


@app.get("/api/playlists/{playlist_id}/paths")
def api_playlist_paths(playlist_id: str):
    try:
        return {"paths": pl.playlist_paths(playlist_id)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/settings")
def api_settings():
    return ops.get_settings()


@app.patch("/api/settings")
def api_save_settings(data: dict):
    return ops.save_settings(data)


@app.get("/api/open-folder")
def api_open_folder(path: str = Query(...)):
    import os
    p = Path(path)
    folder = str(p.parent if p.is_file() else p)
    if not Path(folder).exists():
        raise HTTPException(404, "Path not found")
    os.startfile(folder)
    return {"ok": True}


# --- VSR Pipeline ---
import duplicates as dup
import tag_rules as tags
import network_ops as net
import security_scan as sec
import startup_ops as startup
import disk_ops as disk
import hosts_ops as hosts
import convert_ops as convert
import health_ops as health
import event_ops as events
import board_ops as board
import diagnostics_ops as diag
import pc_diagnostics as pc_diag
import git_ops as git
import vsr_pipeline as vsr
import ip_profile_ops as ip_profiles


class PipelineConfig(BaseModel):
    config: dict


class LearnPairs(BaseModel):
    pairs: list[dict]


class ApplyStage(BaseModel):
    stage: str = "1"
    dry_run: bool = False


class DupScan(BaseModel):
    folder: str
    deep: bool = False
    match_mode: str = "quick"
    file_types: str = "all"


class DupDelete(BaseModel):
    keep_path: str | None = None
    delete_paths: list[str]
    to_trash: bool = True
    dry_run: bool = False


class DupMerge(BaseModel):
    keep_path: str
    group_paths: list[str]
    to_trash: bool = True
    dry_run: bool = False


@app.get("/api/vsr/config")
def api_vsr_config():
    return vsr.get_pipeline_config()


@app.patch("/api/vsr/config")
def api_vsr_save(body: PipelineConfig):
    return vsr.save_pipeline_config(body.config)


@app.get("/api/vsr/preview")
def api_vsr_preview():
    return vsr.preview_pipeline()


@app.post("/api/vsr/learn")
def api_vsr_learn(body: LearnPairs):
    return vsr.learn_from_pairs(body.pairs)


@app.post("/api/vsr/apply")
def api_vsr_apply(body: ApplyStage):
    return vsr.apply_pipeline_stage(body.stage, dry_run=body.dry_run)


@app.post("/api/vsr/match")
def api_vsr_manual_match():
    return vsr.preview_pipeline()


@app.get("/api/duplicates/scan")
def api_dup_scan(
    folder: str,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "video",
):
    try:
        return dup.scan_folder_duplicates(
            folder, deep=deep, match_mode=match_mode, file_types=file_types,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/duplicates/scan/stream")
def api_dup_scan_stream(
    folder: str,
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
):
    progress: list[str] = []

    def run():
        try:
            def on_progress(count, file_path):
                progress.append(json.dumps({"count": count, "file": file_path}))

            result = dup.scan_folder_duplicates(
                folder,
                deep=deep,
                match_mode=match_mode,
                file_types=file_types,
                on_progress=on_progress,
            )
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.15)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/duplicates/delete")
def api_dup_delete(body: DupDelete):
    try:
        return dup.delete_paths(
            keep_path=body.keep_path,
            delete_paths_list=body.delete_paths,
            to_trash=body.to_trash,
            dry_run=body.dry_run,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/duplicates/merge")
def api_dup_merge(body: DupMerge):
    try:
        return dup.merge_duplicate_group(
            keep_path=body.keep_path,
            group_paths=body.group_paths,
            to_trash=body.to_trash,
            dry_run=body.dry_run,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/files/serve")
def api_files_serve(path: str = Query(...)):
    import mimetypes
    p = Path(path)
    if not p.is_file():
        raise HTTPException(404, "File not found")
    mime, _ = mimetypes.guess_type(str(p))
    return FileResponse(p, media_type=mime or "application/octet-stream", filename=p.name)


@app.get("/api/files/info")
def api_files_info(path: str = Query(...)):
    try:
        return dup.file_info(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/files/text")
def api_files_text(path: str = Query(...), max_bytes: int = 65536):
    try:
        return dup.read_text_preview(path, max_bytes=max_bytes)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


class NetPing(BaseModel):
    host: str
    count: int = 4
    timeout_ms: int = 1000


class NetTraceroute(BaseModel):
    host: str
    max_hops: int = 30
    timeout_ms: int = 3000


class NetTelnet(BaseModel):
    host: str
    port: int
    timeout_sec: float = 5.0


class NetDns(BaseModel):
    host: str
    record_type: str = "AUTO"


class NetPortScan(BaseModel):
    host: str
    ports: list[int] | None = None
    timeout_sec: float = 1.0


class NetDiscover(BaseModel):
    subnet: str = ""
    timeout_ms: int = 500


class NetKillProcess(BaseModel):
    pid: int
    force: bool = False


@app.get("/api/network/overview")
def api_network_overview():
    try:
        return net.get_system_overview()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/interfaces")
def api_network_interfaces():
    try:
        return {"interfaces": net.list_network_interfaces()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/connections")
def api_network_connections(
    kind: str = "all",
    search: str = "",
    limit: int = 500,
):
    try:
        return net.list_connections(kind=kind, search=search, limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/processes")
def api_network_processes(
    sort_by: str = "cpu",
    search: str = "",
    limit: int = 200,
):
    try:
        return net.list_processes(sort_by=sort_by, search=search, limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/processes/{pid}")
def api_network_process_detail(pid: int):
    try:
        return net.get_process_detail(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/processes/kill")
def api_network_kill_process(body: NetKillProcess):
    try:
        return net.kill_process(body.pid, force=body.force)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/listening")
def api_network_listening():
    try:
        return {"ports": net.get_listening_ports()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/arp")
def api_network_arp():
    try:
        return {"entries": net.get_arp_table()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/discover")
def api_network_discover(body: NetDiscover):
    try:
        return net.discover_lan(subnet=body.subnet, timeout_ms=body.timeout_ms)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/ping")
def api_network_ping(body: NetPing):
    try:
        return net.ping_host(body.host, count=body.count, timeout_ms=body.timeout_ms)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/traceroute")
def api_network_traceroute(body: NetTraceroute):
    try:
        return net.traceroute(body.host, max_hops=body.max_hops, timeout_ms=body.timeout_ms)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/telnet")
def api_network_telnet(body: NetTelnet):
    try:
        return net.telnet_test(body.host, body.port, timeout_sec=body.timeout_sec)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/dns")
def api_network_dns(body: NetDns):
    try:
        return net.dns_lookup(body.host, record_type=body.record_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/network/portscan")
def api_network_portscan(body: NetPortScan):
    try:
        return net.port_scan(body.host, ports=body.ports, timeout_sec=body.timeout_sec)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/network/diagnostics")
def api_network_diagnostics():
    try:
        return net.run_diagnostics()
    except Exception as e:
        raise HTTPException(500, str(e))


class SecScan(BaseModel):
    scan_type: str = "full"
    update_first: bool = True


class SecRemove(BaseModel):
    items: list[dict]
    permanent: bool = False


class SecConfig(BaseModel):
    abuse_ch_auth_key: str | None = None


@app.get("/api/security/status")
def api_security_status():
    try:
        return sec.get_intel_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/security/config")
def api_security_config(body: SecConfig):
    """Save abuse.ch key via DPAPI (never plaintext JSON). See security_scan.save_config."""
    try:
        data = {}
        if body.abuse_ch_auth_key is not None:
            data["abuse_ch_auth_key"] = body.abuse_ch_auth_key.strip()
        return sec.save_config(data)
    except Exception as e:
        raise HTTPException(500, str(e))



@app.post("/api/security/update")
def api_security_update():
    try:
        return sec.update_threat_intel()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/security/scan")
def api_security_scan(body: SecScan):
    try:
        return sec.run_scan(scan_type=body.scan_type, update_first=body.update_first)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/security/scan/stream")
def api_security_scan_stream(scan_type: str = "full", update_first: bool = True):
    progress: list[str] = []

    def on_progress(phase: str, msg: str, extra: dict | None = None):
        progress.append(json.dumps({"phase": phase, "message": msg, "extra": extra or {}}))

    def run():
        try:
            result = sec.run_scan(
                scan_type=scan_type,
                update_first=update_first,
                on_progress=on_progress,
            )
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.12)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/security/remove")
def api_security_remove(body: SecRemove):
    try:
        return sec.remove_findings(body.items, permanent=body.permanent)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/security/quarantine")
def api_security_quarantine_list():
    try:
        return {"items": sec.list_quarantine()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/security/quarantine/restore")
def api_security_quarantine_restore(qid: str = Query(...)):
    try:
        return sec.restore_quarantine(qid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


class StartupAction(BaseModel):
    item_id: str


class DiskScan(BaseModel):
    path: str
    min_size_mb: float = 10
    max_files: int = 5000


class DiskDelete(BaseModel):
    paths: list[str]
    dry_run: bool = True


class HostsApply(BaseModel):
    feed_id: str = "ads"
    enabled: bool = True


class HostsCustom(BaseModel):
    host: str
    ip: str = "0.0.0.0"


class ConvertBatch(BaseModel):
    files: list[str]
    preset: str = "mp4_h264"
    output_dir: str | None = None


@app.get("/api/health/dashboard")
def api_health_dashboard():
    try:
        return health.get_dashboard()
    except Exception as e:
        raise HTTPException(500, str(e))


class AlertSnoozeBody(BaseModel):
    alert_id: str
    hours: float = 24
    reason: str = ""


class AlertDismissBody(BaseModel):
    alert_id: str
    reason: str = ""


class AlertClearBody(BaseModel):
    alert_id: str = ""


class SectionRunBody(BaseModel):
    section: str = "full"
    write_report: bool = True


class DiagRunBody(BaseModel):
    open_viewer: bool = False


@app.get("/api/health/alerts/prefs")
def api_health_alert_prefs():
    import health_prefs
    return health_prefs.get_public_prefs()


@app.post("/api/health/alerts/snooze")
def api_health_alert_snooze(body: AlertSnoozeBody):
    import health_prefs
    try:
        return health_prefs.snooze_alert(body.alert_id, hours=body.hours, reason=body.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/health/alerts/dismiss")
def api_health_alert_dismiss(body: AlertDismissBody):
    import health_prefs
    try:
        return health_prefs.dismiss_alert(body.alert_id, reason=body.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/health/alerts/clear")
def api_health_alert_clear(body: AlertClearBody | None = None):
    import health_prefs
    try:
        if body and body.alert_id:
            return health_prefs.clear_alert(body.alert_id)
        return health_prefs.clear_all()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/health/report/generate")
def api_health_report_generate():
    """Write plain-English health-hub-summary.json + pc-health-readable-auto.html."""
    import health_report
    try:
        return health_report.generate_now(ROOT)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/diagnostics/run-section")
def api_diagnostics_run_section(body: SectionRunBody | None = None):
    """Re-run one hub section (or section=full for complete diagnostics)."""
    section = (body.section if body else "full") or "full"
    write_report = True if body is None else bool(body.write_report)
    try:
        return diag.run_section(section, ROOT, write_report=write_report)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except TimeoutError as e:
        raise HTTPException(504, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/diagnostics/status")
def api_diag_status():
    return diag.status(ROOT)


@app.get("/api/diagnostics/catalog")
def api_diag_catalog():
    built = diag.build_catalog_and_logs(ROOT)
    logs_meta = [
        {k: v for k, v in row.items() if k != "content"}
        for row in (built.get("logs") or [])
    ]
    return {"catalog": built["catalog"], "logs": logs_meta}


@app.post("/api/diagnostics/pack")
def api_diag_pack():
    try:
        result = diag.write_viewer_packs(ROOT)
        return {
            "ok": True,
            "deviceId": result["deviceId"],
            "deviceRoot": result["deviceRoot"],
            "reportCount": result["reportCount"],
            "logCount": result["logCount"],
            "catalogPath": result["catalogPath"],
            "logsPath": result["logsPath"],
        }
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/diagnostics/run")
def api_diag_run(body: DiagRunBody | None = None):
    open_viewer = bool(body and body.open_viewer)
    try:
        return diag.run_system_diagnostics(ROOT, open_viewer=open_viewer)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except TimeoutError as e:
        raise HTTPException(504, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/events/summary")
def api_events_summary(hours: int = 24, max_events: int = 400):
    """Plain-English themed summary of recent System/Application events."""
    try:
        return events.get_summary(hours=hours, max_events=max_events)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/events/deep-dive")
def api_events_deep_dive(
    hours: int = 72,
    max_events: int = 600,
    include_noise: bool = True,
):
    """
    Rank event themes most→least likely to be real problems,
    each with fix alternatives ordered most→least likely.
    """
    import event_deep_dive as deep
    try:
        return deep.run_deep_dive(
            hours=hours,
            max_events=max_events,
            include_noise=include_noise,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/events/themes")
def api_events_themes(hours: int = 24):
    try:
        return events.get_themes_only(hours=hours)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/events/query")
def api_events_query(
    hours: int = 24,
    max_events: int = 200,
    log: str = "",
    level: str = "",
    provider: str = "",
    q: str = "",
    theme: str = "",
):
    """Filtered event rows (timeline) for Event Viewer."""
    try:
        return events.query_events(
            hours=hours,
            max_events=max_events,
            log=log,
            level=level,
            provider=provider,
            q=q,
            theme_id=theme,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hardware/identity")
def api_hardware_identity():
    try:
        return board.detect_identity()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hardware/board")
def api_hardware_board():
    """Matched motherboard pack + rear I/O ports + vendor links."""
    try:
        return board.get_board_bundle()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hardware/board/{board_id}/rear-io.svg")
def api_hardware_board_svg(board_id: str):
    from fastapi.responses import Response
    pack = board.get_rear_io_svg(board_id)
    if not pack:
        raise HTTPException(404, "Board SVG not found")
    data, ctype = pack
    return Response(content=data, media_type=ctype)


@app.get("/api/hardware/intel")
def api_hardware_intel():
    try:
        return board.match_component_intel()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hardware/playbooks")
def api_hardware_playbooks():
    try:
        return board.list_playbooks()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hardware/playbooks/{playbook_id}")
def api_hardware_playbook(playbook_id: str):
    pb = board.get_playbook(playbook_id)
    if not pb:
        raise HTTPException(404, "Playbook not found")
    return pb


@app.get("/api/hardware/assist")
def api_hardware_assist(
    playbook: str = "",
    theme: str = "",
    alert: str = "",
    process: str = "",
):
    """Offline playbook + guided search for a hub alert / event theme."""
    try:
        return board.assist(
            playbook_id=playbook or None,
            theme_id=theme or None,
            alert_id=alert or None,
            process_name=process or None,
        )
    except Exception as e:
        raise HTTPException(500, str(e))





# --- Comprehensive PC diagnostics HUD ---
class PcDiagRun(BaseModel):
    options: dict[str, bool] | None = None
    eventLogDays: int = 7
    persist: bool = True


@app.get("/api/pc-diagnostics/options")
def api_pc_diag_options():
    return pc_diag.get_options_schema()


@app.get("/api/pc-diagnostics/latest")
def api_pc_diag_latest():
    report = pc_diag.load_latest()
    if not report:
        return {"ok": False, "report": None, "message": "No report yet — run a scan from the Diagnostics HUD."}
    return {"ok": True, "report": report}


@app.post("/api/pc-diagnostics/run")
def api_pc_diag_run(body: PcDiagRun | None = None):
    body = body or PcDiagRun()
    days = max(1, min(int(body.eventLogDays or 7), 30))
    try:
        report = pc_diag.run_diagnostics(
            options=body.options,
            event_log_days=days,
            persist=bool(body.persist),
        )
        return {"ok": True, "report": report}
    except Exception as e:
        raise HTTPException(500, f"Diagnostics failed: {e}") from e


@app.get("/api/startup/overview")
def api_startup_overview():
    try:
        return startup.get_overview()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/startup/disable")
def api_startup_disable(body: StartupAction):
    try:
        return startup.disable_item(body.item_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/startup/enable")
def api_startup_enable(body: StartupAction):
    try:
        return startup.enable_item(body.item_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/disk/overview")
def api_disk_overview():
    try:
        return disk.get_overview()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/disk/scan")
def api_disk_scan(body: DiskScan):
    try:
        return disk.scan_path(body.path, max_files=body.max_files, min_size_mb=body.min_size_mb)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/disk/scan/stream")
def api_disk_scan_stream(path: str, min_size_mb: float = 10, max_files: int = 5000):
    progress: list[str] = []

    def on_progress(msg: str, extra: dict | None = None):
        progress.append(json.dumps({"message": msg, "extra": extra or {}}))

    def run():
        try:
            result = disk.scan_path(path, max_files=max_files, min_size_mb=min_size_mb, on_progress=on_progress)
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.12)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/disk/delete")
def api_disk_delete(body: DiskDelete):
    try:
        return disk.delete_paths(body.paths, dry_run=body.dry_run)
    except Exception as e:
        raise HTTPException(500, str(e))


# --- IP Profile Switcher ---
class IpProfileBody(BaseModel):
    id: str | None = None
    name: str | None = None
    color: str | None = None
    adapter: str | None = None
    mode: str = "static"  # static | dhcp
    ip: str | None = None
    prefix: int | None = None
    netmask: str | None = None
    gateway: str | None = None
    dns: list[str] | str | None = None
    notes: str | None = None


class IpCaptureBody(BaseModel):
    adapter: str
    name: str | None = None
    color: str | None = None


class IpApplyBody(BaseModel):
    profile_id: str | None = None
    profile: dict | None = None


@app.get("/api/ip/adapters")
def api_ip_adapters():
    try:
        return {"adapters": ip_profiles.list_adapters()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/ip/adapters/{name}")
def api_ip_adapter_detail(name: str):
    try:
        return ip_profiles.get_adapter_detail(name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/ip/profiles")
def api_ip_profiles_list():
    try:
        return ip_profiles.list_profiles()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/ip/profiles")
def api_ip_profiles_save(body: IpProfileBody):
    try:
        return ip_profiles.save_profile(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/ip/profiles/{profile_id}")
def api_ip_profiles_delete(profile_id: str):
    try:
        return ip_profiles.delete_profile(profile_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/ip/profiles/capture")
def api_ip_profiles_capture(body: IpCaptureBody):
    try:
        return ip_profiles.capture_current(body.adapter, name=body.name, color=body.color)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/ip/apply")
def api_ip_apply(body: IpApplyBody):
    try:
        result = ip_profiles.apply_profile(profile_id=body.profile_id, profile=body.profile)
        if result.get("admin_required"):
            raise HTTPException(403, result.get("message") or "Admin rights required to change IP")
        if not result.get("ok"):
            raise HTTPException(500, result.get("message") or "Failed to apply IP profile")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(501, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/ip/profiles/export")
def api_ip_profiles_export():
    """Downloadable portable JSON for moving setups to another PC."""
    try:
        return ip_profiles.export_profiles_blob()
    except Exception as e:
        raise HTTPException(500, str(e))


class IpImportBody(BaseModel):
    profiles: list | None = None
    merge: bool = True
    # Allow full export blob or {profiles:[...]}
    format: str | None = None
    version: int | None = None
    exported_at: str | None = None
    toolbox_relative_path: str | None = None
    instructions: str | None = None


@app.post("/api/ip/profiles/import")
def api_ip_profiles_import(body: IpImportBody):
    try:
        blob = body.model_dump()
        if not blob.get("profiles") and isinstance(body.model_dump(), dict):
            blob = body.model_dump()
        return ip_profiles.import_profiles_blob(blob, merge=body.merge)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hosts/status")
def api_hosts_status():
    try:
        return hosts.get_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hosts/read")
def api_hosts_read():
    try:
        return hosts.read_hosts()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/hosts/apply")
def api_hosts_apply(body: HostsApply):
    try:
        return hosts.apply_blocklist(body.feed_id, body.enabled)
    except PermissionError:
        raise HTTPException(403, "Admin rights required to edit hosts file")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/hosts/add")
def api_hosts_add(body: HostsCustom):
    try:
        return hosts.add_custom_block(body.host, body.ip)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError:
        raise HTTPException(403, "Admin rights required")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/hosts/remove")
def api_hosts_remove(body: HostsCustom):
    try:
        return hosts.remove_custom_block(body.host)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/convert/presets")
def api_convert_presets():
    return {"presets": convert.list_presets()}


@app.get("/api/convert/scan")
def api_convert_scan(folder: str, recursive: bool = True):
    try:
        return convert.scan_folder(folder, recursive=recursive)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/convert/batch")
def api_convert_batch(body: ConvertBatch):
    try:
        return convert.convert_batch(body.files, preset=body.preset, output_dir=body.output_dir)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/convert/stream")
def api_convert_stream(files: str, preset: str = "mp4_h264", output_dir: str | None = None):
    file_list = [f.strip() for f in files.split("|") if f.strip()]
    progress: list[str] = []

    def on_progress(msg: str, extra: dict | None = None):
        progress.append(json.dumps({"message": msg, "extra": extra or {}}))

    def run():
        try:
            result = convert.convert_batch(file_list, preset=preset, output_dir=output_dir, on_progress=on_progress)
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.12)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/tag-rules")
def api_tag_rules_get():
    return tags.get_tag_rules()


@app.patch("/api/tag-rules")
def api_tag_rules_save(data: dict):
    return tags.save_tag_rules(data)


@app.post("/api/tag-rules/apply")
def api_tag_rules_apply(dir_id: str | None = None):
    return tags.apply_tag_rules_after_scan(dir_id)


@app.get("/api/debug/logs")
def api_debug_logs(limit: int = 200, level: str | None = None):
    return {"logs": dbg.get_logs(limit, level)}


@app.post("/api/debug/log")
def api_debug_log(entry: DebugEntry):
    return dbg.log(entry.source, entry.level, entry.message, entry.extra)


@app.post("/api/debug/clear")
def api_debug_clear():
    dbg.clear_logs()
    return {"ok": True}


# --- Git Repository Manager ---

class GitOrganize(BaseModel):
    path: str
    group_id: str | None = None
    order: int | None = None
    pinned: bool | None = None
    notes: str | None = None


class GitClone(BaseModel):
    url: str
    target_dir: str | None = None
    group_id: str = "default"


class GitInit(BaseModel):
    path: str
    group_id: str = "default"


class GitPathAction(BaseModel):
    path: str


class GitSavedUrl(BaseModel):
    url: str
    name: str = ""
    group_id: str = "default"


class GitConfigPatch(BaseModel):
    scan_roots: list[str] | None = None
    clone_root: str | None = None
    groups: list[dict] | None = None


class GitGroups(BaseModel):
    groups: list[dict]


@app.get("/api/git/tooling")
def api_git_tooling():
    return git.get_tooling()


@app.get("/api/git/repos")
def api_git_repos():
    try:
        return git.list_repos()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/git/repo")
def api_git_repo_status(path: str):
    try:
        return git.get_repo_status(path)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/git/scan/stream")
def api_git_scan_stream():
    progress: list[str] = []

    def on_progress(msg: str, extra: dict | None = None):
        progress.append(json.dumps({"message": msg, "extra": extra or {}}))

    def run():
        try:
            result = git.scan_and_merge(on_progress=on_progress)
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.12)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/git/clone/stream")
def api_git_clone_stream(url: str, target_dir: str | None = None, group_id: str = "default"):
    progress: list[str] = []

    def on_progress(msg: str, extra: dict | None = None):
        progress.append(json.dumps({"message": msg, "extra": extra or {}}))

    def run():
        try:
            result = git.clone_repo(url, target_dir=target_dir, group_id=group_id, on_progress=on_progress)
            progress.append(json.dumps({"done": True, "result": result}))
        except Exception as e:
            progress.append(json.dumps({"error": str(e)}))

    threading.Thread(target=run, daemon=True).start()

    def gen():
        sent = 0
        import time
        while True:
            while sent < len(progress):
                yield f"data: {progress[sent]}\n\n"
                sent += 1
                item = json.loads(progress[sent - 1])
                if "done" in item or "error" in item:
                    return
            time.sleep(0.12)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/git/organize")
def api_git_organize(body: GitOrganize):
    try:
        return git.organize_repo(body.path, body.group_id, body.order, body.pinned, body.notes)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/hide")
def api_git_hide(body: GitPathAction):
    try:
        return git.hide_repo(body.path)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/groups")
def api_git_groups(body: GitGroups):
    try:
        return git.save_groups(body.groups)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/git/config")
def api_git_config(body: GitConfigPatch):
    try:
        return git.update_config(body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/saved-urls")
def api_git_saved_url(body: GitSavedUrl):
    try:
        return git.add_saved_url(body.url, body.name, body.group_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/git/saved-urls/{url_id}")
def api_git_remove_saved_url(url_id: str):
    try:
        return git.remove_saved_url(url_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/pull")
def api_git_pull(body: GitPathAction):
    try:
        return git.pull_repo(body.path)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/push")
def api_git_push(body: GitPathAction):
    try:
        return git.push_repo(body.path)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/fetch")
def api_git_fetch(body: GitPathAction):
    try:
        return git.fetch_repo(body.path)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/clone")
def api_git_clone(body: GitClone):
    try:
        return git.clone_repo(body.url, body.target_dir, body.group_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/init")
def api_git_init(body: GitInit):
    try:
        return git.init_repo(body.path, body.group_id)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/open-folder")
def api_git_open_folder(body: GitPathAction):
    try:
        return git.open_folder(body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/git/open-github-desktop")
def api_git_open_gh_desktop(body: GitPathAction):
    try:
        return git.open_github_desktop(body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


def main():
    host, port = load_bind()
    # Re-bind module globals if env changed after import
    global BIND_HOST, BIND_PORT
    BIND_HOST, BIND_PORT = host, port
    print(f"\n  AI Toolbox Server → http://{host}:{port}")
    print(f"  (dedicated bind — not 127.0.0.1:8765 / FAFO companion)")
    print(f"  FFmpeg: {'yes' if ops.find_ffmpeg() else 'install ffmpeg for pro thumbnails'}")
    print("  Press Ctrl+C to stop\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()