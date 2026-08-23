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
import survey_ocr_ops as survey_ocr
import survey_share_ops as survey_share
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
    before_dir_id: str | None = None
    after_dir_id: str | None = None
    require_upscale_name: bool | None = None


class SuggestPairsRequest(BaseModel):
    """Optional two-folder mode + multi-signal matching knobs."""
    limit: int = 50
    min_ratio: float = 0.5
    before_dir_id: str | None = None
    after_dir_id: str | None = None
    unpaired_only: bool = True
    kind: str | None = None
    # Looser unique-id style match: last N alnum chars of stem (default 5)
    tail_len: int = 5
    use_tail: bool = True
    use_digits: bool = True
    use_fuzzy: bool = True
    use_folder: bool = True


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


def _resolve_toolbox_file(file_path: str) -> Path:
    """Map /toolbox/... URL path → real file under ROOT.

    Handles:
    - normal spaces
    - percent-encoding (%20) and accidental double-encoding (%2520)
    - backslashes
    - leading ./ or toolbox/ prefixes from bad clients
    """
    from urllib.parse import unquote

    raw = str(file_path or "").replace("\\", "/").lstrip("/")
    raw = raw.split("#", 1)[0].split("?", 1)[0]
    # Decode once or twice (browsers / proxies sometimes re-encode)
    for _ in range(2):
        if "%" not in raw:
            break
        decoded = unquote(raw)
        if decoded == raw:
            break
        raw = decoded
    # %23 / %3F become # / ? only after unquote — strip again so
    # /toolbox/Media Hub.html%23duplicates cannot 404 as a filename.
    raw = raw.split("#", 1)[0].split("?", 1)[0]
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.lower().startswith("toolbox/"):
        raw = raw[8:]
    rel = Path(raw)
    if ".." in rel.parts or rel.is_absolute():
        raise HTTPException(400, "Invalid path")
    root = ROOT.resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise HTTPException(403, "Path outside toolbox") from e
    return target


# Serve toolbox HTML/tools from the same origin as the API so browsers do not
# block fetch() (file:// → 127.x private network / CORS edge cases).
@app.get("/toolbox/{file_path:path}")
def toolbox_static(file_path: str):
    """Read-only static files under the toolbox root (HTML tools + shared JS)."""
    target = _resolve_toolbox_file(file_path)
    if not target.is_file():
        raise HTTPException(
            404,
            f"Not found: {file_path} (root={ROOT})",
        )
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
    # HTML/JS/CSS: never let the browser keep a stale mojibake copy of the launcher
    headers = {}
    if lower in {".html", ".js", ".css"}:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        }
    return FileResponse(target, media_type=media, headers=headers)


@app.get("/")
def root_redirect():
    """Open the launcher when someone hits the S1 origin directly."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/toolbox/Toolbox%20Launcher.html", status_code=307)


@app.get("/toolbox")
@app.get("/toolbox/")
def toolbox_index_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/toolbox/Toolbox%20Launcher.html", status_code=307)


@app.get("/Toolbox Launcher.html")
@app.get("/Toolbox%20Launcher.html")
def launcher_shortcut():
    """Legacy / bare paths some shortcuts still use without /toolbox/ prefix."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/toolbox/Toolbox%20Launcher.html", status_code=307)


@app.get("/commander")
def commander_redirect():
    """Shortcut to Commander Site Console over HTTP (same-origin as API)."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url="/toolbox/Verifone%20Tools/Commander%20Site%20Console.html",
        status_code=307,
    )


# --- Site Intelligence Registry (persistent growing site dossiers) ---
import site_registry_ops as site_reg


class SiteEnsureBody(BaseModel):
    display_name: str | None = ""
    host_ip: str | None = ""
    address: str | None = ""
    city: str | None = ""
    phone: str | None = ""
    site_id: str | None = ""
    export_id: str | None = ""
    export_path: str | None = ""
    group_key: str | None = ""
    source: str | None = "manual"
    note: str | None = ""
    facts: list[str] | None = None
    area_tags: list[str] | None = None


class SiteQuickStartBody(BaseModel):
    seed_layouts: bool = True
    import_notes: bool = True


class SiteCachePolicyBody(BaseModel):
    localHotDays: int | None = None
    maxLocalGb: float | None = None
    preferExternalDrive: bool | None = None
    externalDrivePath: str | None = None
    coldStore: str | None = None
    coldStorePath: str | None = None
    autoEvictUnused: bool | None = None
    allowFullMirror: bool | None = None


@app.get("/api/verifone/registry")
def api_site_registry_list(q: str = "", status: str = ""):
    return site_reg.list_sites(q=q, status=status)


@app.get("/api/verifone/registry/roadmap")
def api_site_registry_roadmap():
    return site_reg.product_roadmap()


@app.get("/api/verifone/registry/policy")
def api_site_registry_policy_get():
    return {"ok": True, "policy": site_reg.get_cache_policy()}


@app.put("/api/verifone/registry/policy")
def api_site_registry_policy_put(body: SiteCachePolicyBody):
    return {"ok": True, "policy": site_reg.save_cache_policy(body.model_dump(exclude_unset=True))}


@app.post("/api/verifone/registry/ensure")
def api_site_registry_ensure(body: SiteEnsureBody):
    return site_reg.ensure_site(
        display_name=body.display_name or "",
        host_ip=body.host_ip or "",
        address=body.address or "",
        city=body.city or "",
        phone=body.phone or "",
        site_id=body.site_id or "",
        export_id=body.export_id or "",
        export_path=body.export_path or "",
        group_key=body.group_key or "",
        source=body.source or "manual",
        note=body.note or "",
        facts=body.facts,
        area_tags=body.area_tags,
    )


@app.post("/api/verifone/registry/ingest-backups")
def api_site_registry_ingest():
    return site_reg.ingest_backups(sync_folders=True)


@app.post("/api/verifone/registry/import-sticky-notes")
def api_site_registry_sticky():
    return site_reg.import_sticky_notes()


@app.post("/api/verifone/registry/seed-area")
def api_site_registry_area():
    return site_reg.seed_area_stubs()


@app.post("/api/verifone/registry/quick-start")
def api_site_registry_quick_start(body: SiteQuickStartBody | None = None):
    """One-button: sync backups → registry shells → sticky notes → seed layouts."""
    b = body or SiteQuickStartBody()
    return site_reg.quick_start(seed_layouts=b.seed_layouts, import_notes=b.import_notes)


@app.get("/api/verifone/registry/{key}")
def api_site_registry_get(key: str):
    site = site_reg.load_site(key)
    if not site:
        raise HTTPException(404, "Site not in registry")
    return {"ok": True, "site": site}


# --- Equipment field knowledge (tech-editable pros/cons + promote to multi-site) ---
import equipment_knowledge_ops as equip_know


class EquipKnowledgeBody(BaseModel):
    id: str | None = None
    siteKey: str | None = None
    site_key: str | None = None
    exportId: str | None = None
    export_id: str | None = None
    groupKey: str | None = None
    group_key: str | None = None
    title: str | None = None
    notes: str | None = None
    pros: list[str] | str | None = None
    cons: list[str] | str | None = None
    compat: list[str] | str | None = None
    dayZero: list[str] | str | None = None
    day_zero: list[str] | str | None = None
    equipment: dict | None = None
    transfer: dict | None = None
    view3d: dict | None = None
    author: str | None = "tech"


class EquipPromoteBody(BaseModel):
    siteKey: str
    entryId: str
    answers: dict | None = None
    author: str | None = "tech"


class EquipApplyLibBody(BaseModel):
    siteKey: str
    libraryEntryId: str
    exportId: str | None = ""
    author: str | None = "tech"


class EquipFromLayoutBody(BaseModel):
    siteKey: str
    exportId: str | None = ""
    item: dict
    author: str | None = "tech"


@app.get("/api/verifone/equipment-knowledge/criteria")
def api_equip_know_criteria():
    return {"ok": True, "criteria": equip_know.promote_criteria()}


@app.get("/api/verifone/equipment-knowledge")
def api_equip_know_list(
    site_key: str,
    export_id: str = "",
    include_library: bool = True,
    equipment_type: str = "",
):
    return equip_know.list_for_site(
        site_key,
        export_id=export_id,
        include_library=include_library,
        equipment_type=equipment_type,
    )


@app.post("/api/verifone/equipment-knowledge")
def api_equip_know_save(body: EquipKnowledgeBody):
    try:
        payload = body.model_dump(exclude_none=True)
        author = payload.pop("author", None) or "tech"
        return equip_know.save_entry(payload, author=author)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/verifone/equipment-knowledge/{site_key}/{entry_id}")
def api_equip_know_delete(site_key: str, entry_id: str):
    try:
        return equip_know.delete_entry(site_key, entry_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/equipment-knowledge/promote")
def api_equip_know_promote(body: EquipPromoteBody):
    try:
        return equip_know.request_promote(
            body.siteKey,
            body.entryId,
            body.answers or {},
            author=body.author or "tech",
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/equipment-knowledge/apply-library")
def api_equip_know_apply(body: EquipApplyLibBody):
    try:
        return equip_know.apply_library_to_site(
            body.siteKey,
            body.libraryEntryId,
            author=body.author or "tech",
            export_id=body.exportId or "",
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/equipment-knowledge/from-layout")
def api_equip_know_from_layout(body: EquipFromLayoutBody):
    return equip_know.seed_from_layout_item(
        body.siteKey,
        body.item,
        export_id=body.exportId or "",
        author=body.author or "tech",
    )


@app.get("/setup")
def setup_configurator_redirect():
    """Quick Start setup configurator (personalized BAT packs)."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/toolbox/Setup%20Configurator.html", status_code=307)


@app.get("/startup")
def startup_board_redirect():
    """Server command board — status, block auto-start, manual override."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/toolbox/Startup%20Command%20Board.html", status_code=307)


class SetupPackBody(BaseModel):
    packName: str | None = "My-FAFO-Setup"
    modules: list[str] | None = None
    workflow: str | None = None


class SetupOpenPathBody(BaseModel):
    path: str


@app.get("/api/setup/catalog")
def api_setup_catalog():
    """Index of install/start scripts — files are not moved."""
    import json as _json

    cat_path = ROOT / "setup" / "install-catalog.json"
    if not cat_path.is_file():
        raise HTTPException(404, "setup/install-catalog.json missing")
    try:
        catalog = _json.loads(cat_path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as e:
        raise HTTPException(500, f"Catalog unreadable: {e}") from e
    # annotate exists
    for mod in catalog.get("modules") or []:
        for sc in mod.get("scripts") or []:
            rel = sc.get("path") or ""
            sc["exists"] = (ROOT / rel).is_file() if rel else False
    for sc in catalog.get("looseScripts") or []:
        rel = sc.get("path") or ""
        sc["exists"] = (ROOT / rel).is_file() if rel else False
    return {"ok": True, "catalog": catalog, "toolboxRoot": str(ROOT)}


@app.post("/api/setup/build-pack")
def api_setup_build_pack(body: SetupPackBody):
    """Compose personalized BAT pack via Build-UserSetupPack.ps1."""
    import subprocess
    import json as _json

    ps1 = ROOT / "Scripts" / "Build-UserSetupPack.ps1"
    if not ps1.is_file():
        raise HTTPException(500, "Scripts/Build-UserSetupPack.ps1 missing")
    pack_name = (body.packName or "My-FAFO-Setup").strip() or "My-FAFO-Setup"
    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-ToolboxRoot",
        str(ROOT),
        "-PackName",
        pack_name,
        "-AsObject",
    ]
    if body.workflow:
        args.extend(["-Workflow", body.workflow])
    if body.modules:
        # PowerShell string array: -Modules a,b,c
        args.extend(["-Modules", ",".join(body.modules)])
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired as e:
        raise HTTPException(504, "Pack build timed out") from e
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise HTTPException(500, err or out or f"Build failed code {proc.returncode}")
    # Last JSON line
    data = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = _json.loads(line)
                break
            except _json.JSONDecodeError:
                continue
    if not data:
        # AsObject may print object formatting; fallback parse whole
        try:
            data = _json.loads(out)
        except _json.JSONDecodeError:
            data = {"ok": True, "raw": out, "message": "Pack built (see stdout)"}
    data.setdefault("ok", True)
    return data


@app.post("/api/setup/open-pack-folder")
def api_setup_open_pack_folder(body: SetupOpenPathBody):
    import subprocess
    from pathlib import Path as _P

    p = _P(body.path or "")
    if not p.is_dir():
        raise HTTPException(404, "Folder not found")
    # Only allow under LOCALAPPDATA\FAFO or toolbox root
    try:
        local_fafo = _P(os.environ.get("LOCALAPPDATA") or "") / "FAFO"
        p.resolve().relative_to(local_fafo.resolve())
        ok = True
    except Exception:
        try:
            p.resolve().relative_to(ROOT.resolve())
            ok = True
        except Exception:
            ok = False
    if not ok:
        raise HTTPException(403, "Path not allowed")
    subprocess.Popen(["explorer.exe", str(p)], shell=False)
    return {"ok": True, "path": str(p)}



# --- Optional private extensions (local-only modules; gitignored) ---
try:
    from _private_investor_routes import register as _register_investor
    _register_investor(app)
except ImportError:
    pass  # public clone: Investor Portal not shipped


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
    # When true, open the generated punch list with the OS default app (Excel)
    open: bool = False


class VfSurveyBody(BaseModel):
    survey: dict | None = None


class VfSurveyOcrBody(BaseModel):
    """Photo / text ingest for site survey OCR (EZ Mode foundation)."""
    images: list[dict] | None = None  # [{filename, data_base64, pastedText?}]
    raw_texts: list[dict] | None = None  # [{text, notes?}]
    apply_mode: str | None = "fill_empty"  # none | fill_empty | overwrite
    notes: str | None = None
    prefer_engine: str | None = None  # windows_ocr | tesseract
    domain: str | None = "pos"  # site | network | pos | forecourt
    screen_type: str | None = "auto"  # auto | network_menu | employees | software | …


class VfSurveyOcrApplyBody(BaseModel):
    capture_id: str | None = None
    mode: str | None = "fill_empty"
    fields: dict | None = None  # optional override map path -> value (as-given)


class VfSurveyShareBody(BaseModel):
    """Build redacted email pack, full tech ZIP, or recovery checklist."""
    mode: str | None = "redacted"  # redacted | full | checklist
    include_photos: bool | None = False  # full pack only
    include_layout_json: bool | None = True
    include_checklist: bool | None = True


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
    """Detect BOTH Import-Export tools (new Base 55+ and legacy SMS) on this PC."""
    return cmd_live.detect_import_export_utility()


class CmdLaunchImportExportBody(BaseModel):
    tool_id: str | None = None
    base_version: str | None = None
    generation: str | None = None  # new | legacy


@app.post("/api/verifone/live/import-export/launch")
def verifone_import_export_launch(body: CmdLaunchImportExportBody | None = None):
    """
    Launch NEW ImportExportUtility.exe (Base 55+) or LEGACY SMSImportExport.exe.
    Login in the GUI is site-specific Manager (same as Config Client).
    """
    tool_id = body.tool_id if body else None
    base_version = body.base_version if body else None
    generation = body.generation if body else None
    try:
        return cmd_live.launch_import_export_utility(
            tool_id=tool_id, base_version=base_version, generation=generation
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except OSError as e:
        raise HTTPException(500, f"Failed to launch: {e}") from e


# --- FAFO SMS Import-Export Shell (CGILink, site Manager, controlled paths) ---
import sms_ie_ops as sms_ie


class SmsIeLoginBody(BaseModel):
    host: str
    username: str | None = "Manager"
    password: str | None = ""
    otp: str | None = None
    profile_id: str | None = None
    site_number: str | None = None  # store label for folders e.g. "Quick N Easy 1" (NOT the password)
    export_id: str | None = None
    tool_id: str | None = None  # import_export_utility | sms_import_export
    base_version: str | None = None


class SmsIeExportBody(BaseModel):
    session_id: str
    database_ids: list[str] | None = None
    cmds: list[str] | None = None
    preset: str | None = None  # plu_core | merchandise | fuel | …
    save_path: str | None = None
    timeout: float = 60.0


class SmsIeImportBody(BaseModel):
    session_id: str
    folder: str | None = None
    files: list[str] | None = None
    cmds: list[str] | None = None
    timeout: float = 90.0


@app.get("/api/verifone/sms-ie/tools")
def verifone_sms_ie_tools():
    """Both utilities + catalogs + presets."""
    return sms_ie.detect_tools()


@app.get("/api/verifone/sms-ie/databases")
def verifone_sms_ie_databases(tool_id: str | None = None, base_version: str | None = None):
    try:
        return sms_ie.databases_for_tool(tool_id, base_version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/sms-ie/login")
def verifone_sms_ie_login(body: SmsIeLoginBody):
    """
    CGILink login with site-specific Manager credentials (same as Config Client).
    password = that store's Manager password; site_number = optional label (e.g. Quick N Easy 1).
    """
    try:
        return sms_ie.login(
            body.host,
            username=body.username or "Manager",
            password=body.password or "",
            otp=body.otp,
            profile_id=body.profile_id,
            site_number=body.site_number,
            export_id=body.export_id,
            tool_id=body.tool_id,
            base_version=body.base_version,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/sms-ie/logout")
def verifone_sms_ie_logout(session_id: str):
    return sms_ie.logout(session_id)


@app.get("/api/verifone/sms-ie/session")
def verifone_sms_ie_session(session_id: str | None = None):
    return sms_ie.session_status(session_id)


@app.get("/api/verifone/sms-ie/suggest-path")
def verifone_sms_ie_suggest_path(
    site_number: str | None = None,
    host: str | None = None,
    export_id: str | None = None,
    label: str | None = None,
):
    return sms_ie.suggest_save_path(
        site_number=site_number, host=host, export_id=export_id, label=label
    )


@app.post("/api/verifone/sms-ie/export")
def verifone_sms_ie_export(body: SmsIeExportBody):
    try:
        return sms_ie.export_databases(
            body.session_id,
            database_ids=body.database_ids,
            cmds=body.cmds,
            preset=body.preset,
            save_path=body.save_path,
            timeout=body.timeout,
        )
    except (ValueError, KeyError, PermissionError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/sms-ie/import")
def verifone_sms_ie_import(body: SmsIeImportBody):
    try:
        return sms_ie.import_files(
            body.session_id,
            folder=body.folder,
            files=body.files,
            cmds=body.cmds,
            timeout=body.timeout,
        )
    except (ValueError, KeyError, PermissionError, FileNotFoundError, NotADirectoryError) as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/sms-ie/folder")
def verifone_sms_ie_folder(path: str):
    try:
        return sms_ie.list_folder_xml(path)
    except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/sms-ie/jobs")
def verifone_sms_ie_jobs(limit: int = 20):
    return sms_ie.recent_jobs(limit=limit)


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


class BackupStageBulkBody(BaseModel):
    site_id: str
    upcs: list[str] | None = None
    exclude_upcs: list[str] | None = None
    operation: str = "set"  # set | price_percent | price_amount
    field: str = "price"
    value: str | None = None
    department: str | None = None
    q: str | None = None
    source: str | None = None
    select_all_matches: bool = False


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


class BackupFinalizeBody(BaseModel):
    site_id: str
    note: str | None = None
    signed_by: str | None = None


class BackupRestoreFinalizedBody(BaseModel):
    site_id: str
    history_id: str


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


@app.get("/api/verifone/backup/{site_id}/plus")
def verifone_backup_list_plus(
    site_id: str,
    q: str | None = None,
    department: str | None = None,
    pcode: str | None = None,
    food_stamp: str | None = None,
    upc: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Browse/filter PLUs from local SMS backup for the bulk PLU editor."""
    try:
        return bedit.list_plus(
            site_id,
            q=q,
            department=department,
            pcode=pcode,
            food_stamp=food_stamp,
            upc=upc,
            limit=limit,
            offset=offset,
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


@app.post("/api/verifone/backup/stage-bulk")
def verifone_backup_stage_bulk(body: BackupStageBulkBody):
    """Stage the same partial update across many selected PLUs (price %/$, EBT, dept, …)."""
    try:
        return bedit.stage_bulk(
            body.site_id,
            upcs=body.upcs,
            exclude_upcs=body.exclude_upcs,
            operation=body.operation,
            field=body.field,
            value=body.value,
            department=body.department,
            q=body.q,
            source=body.source,
            select_all_matches=body.select_all_matches,
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
    """Apply verified staged edits to local backup files (safe-copy + protect original first)."""
    try:
        return bedit.apply_verified_changes(body.site_id, only_verified=body.only_verified)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.get("/api/verifone/backup/{site_id}/safe-copies")
def verifone_backup_safe_copies(site_id: str):
    return bedit.list_safe_copies(site_id)


@app.get("/api/verifone/backup/{site_id}/original")
def verifone_backup_original_status(site_id: str):
    """Protected original baseline + finalized history (last 3)."""
    return bedit.get_original_status(site_id)


@app.post("/api/verifone/backup/{site_id}/ensure-original")
def verifone_backup_ensure_original(site_id: str):
    """Create protected original snapshot if missing (does not overwrite)."""
    try:
        return bedit.ensure_protected_original(site_id, force=False)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/backup/restore-original")
def verifone_backup_restore_original(body: BackupApplyBody):
    """Fail-safe: restore protected original over working PLUs.xml."""
    try:
        return bedit.restore_from_original(body.site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.post("/api/verifone/backup/finalize-original")
def verifone_backup_finalize_original(body: BackupFinalizeBody):
    """Sign-off: archive protected original to history (keep last 3), re-baseline from current."""
    try:
        return bedit.finalize_original(
            body.site_id, note=body.note, signed_by=body.signed_by
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@app.post("/api/verifone/backup/restore-finalized")
def verifone_backup_restore_finalized(body: BackupRestoreFinalizedBody):
    try:
        return bedit.restore_finalized(body.site_id, body.history_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


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
    changed_at: str | None = None  # YYYY-MM-DD when password was changed on site


class ManagerPasswordDateBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    changed_at: str  # YYYY-MM-DD from site notes (required)
    interval_days: int | None = None
    note: str | None = ""


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
    """Set Manager password on site liferaft (parses letter-cycle; optional changed_at date)."""
    try:
        gk = sprof.resolve_group_key(body.group_key, body.export_id)
        return sprof.set_manager_password(
            gk,
            body.password,
            mark_changed=body.mark_changed,
            scheme=body.scheme,
            note=body.note or "",
            sync_live_profile=body.sync_live_profile,
            changed_at=body.changed_at,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/master-profile/password/change-date")
def verifone_master_password_change_date(body: ManagerPasswordDateBody):
    """
    Record last Manager password change date from site notes (YYYY-MM-DD).
    Recalculates days remaining and next due (interval default 90).
    """
    try:
        gk = sprof.resolve_group_key(body.group_key, body.export_id)
        return sprof.set_password_change_date(
            gk,
            changed_at=body.changed_at,
            interval_days=body.interval_days,
            note=body.note or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/verifone/master-profile/password/status")
def verifone_master_password_status(group_key: str | None = None, export_id: str | None = None):
    """Letter + days remaining summary for a site (from last known change date)."""
    try:
        gk = sprof.resolve_group_key(group_key, export_id)
        prof = sprof.get_master_profile(group_key=gk, merge_sources=True)
        status = sprof.password_status_summary((prof or {}).get("credentials") or {})
        return {"ok": True, "groupKey": gk, "status": status, "hasSaved": bool((prof or {}).get("hasSaved"))}
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


# --- Fleet tech defaults (SSH maint shell, etc. — machine-local) ---
import fleet_tech_ops as fleet_tech


@app.get("/api/verifone/fleet-tech-defaults")
def verifone_fleet_tech_defaults(include_password: bool = True):
    """PuTTY/SSH maint credentials + playbooks stored under %LOCALAPPDATA%\\FAFO (not git)."""
    return fleet_tech.get_defaults(include_password=include_password)


class FleetTechBody(BaseModel):
    data: dict | None = None


@app.put("/api/verifone/fleet-tech-defaults")
def verifone_fleet_tech_defaults_put(body: FleetTechBody):
    if not body.data:
        raise HTTPException(400, "data required")
    return fleet_tech.save_defaults(body.data)


# --- Manager reset via maint SSH (secrets stay machine-local) ---
import commander_ssh_ops as cmd_ssh


class SshResetManagerBody(BaseModel):
    host: str
    port: int | None = 22
    group_key: str | None = None
    export_id: str | None = None
    target_letter: str = "A"
    password_base: str | None = None  # e.g. 6652990 → final A6652990 after force-change
    update_liferaft: bool = True
    # Optional one-shot overrides (default: fleet-tech-defaults / Liferaft)
    ssh_user: str | None = None
    ssh_password: str | None = None


class SshConfirmManagerBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    password: str | None = None  # default: pending target e.g. A6652990
    use_pending: bool = True
    mark_changed: bool = True


@app.get("/api/verifone/ssh/capabilities")
def verifone_ssh_capabilities():
    return cmd_ssh.ssh_capabilities()


# --- High-impact tech helpers (dashboard, playbook, preflight, field pack) ---
import tech_ops as tech


@app.get("/api/verifone/docs/user-guide")
def verifone_user_guide():
    """
    Full Commander FAFO user manual (Markdown).
    Also available as static file under /toolbox/docs/Commander-FAFO-User-Guide.md
    """
    from pathlib import Path as _P

    candidates = [
        _P(__file__).resolve().parent.parent / "docs" / "Commander-FAFO-User-Guide.md",
        _P(__file__).resolve().parent.parent / "Verifone Tools" / "Commander-FAFO-User-Guide.md",
    ]
    for p in candidates:
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            return {
                "ok": True,
                "path": str(p),
                "relativePath": str(p.relative_to(_P(__file__).resolve().parent.parent)),
                "bytes": len(text.encode("utf-8")),
                "markdown": text,
                "toolboxUrl": "/toolbox/docs/Commander-FAFO-User-Guide.md",
                "title": "FAFO Commander Tools — Feature Guide & User Manual",
            }
    raise HTTPException(404, "User guide not found — expected docs/Commander-FAFO-User-Guide.md")


@app.get("/api/verifone/tech/password-dashboard")
def verifone_password_dashboard(days_warn: int = 14):
    """Sites with Manager letter-cycle overdue / due soon / missing change date."""
    return tech.password_rotation_dashboard(days_warn=days_warn)


@app.get("/api/verifone/tech/dead-manager-playbook")
def verifone_dead_manager_playbook(
    group_key: str | None = None,
    export_id: str | None = None,
    host: str | None = None,
):
    return tech.dead_manager_playbook(group_key=group_key, export_id=export_id, host=host)


@app.get("/api/verifone/tech/otp-card")
def verifone_otp_card():
    return {"ok": True, "cards": tech.OTP_CHEAT_CARD}


class PreflightBody(BaseModel):
    host: str
    username: str | None = "Manager"
    password: str | None = ""


@app.post("/api/verifone/tech/preflight")
def verifone_tech_preflight(body: PreflightBody):
    """Ping/ports (+ optional CGILink validate) before Journal / IE / SSH."""
    try:
        return tech.connectivity_preflight(
            body.host,
            username=body.username or "Manager",
            password=body.password or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class FieldPackBody(BaseModel):
    site_id: str
    group_key: str | None = None
    include_redacted_share: bool = True
    seed_layout_if_empty: bool = True


@app.post("/api/verifone/tech/field-pack")
def verifone_field_pack(body: FieldPackBody):
    """One-click field pack under backup/survey/field-packs/."""
    try:
        return tech.build_field_pack(
            body.site_id,
            group_key=body.group_key,
            include_redacted_share=body.include_redacted_share,
            seed_layout_if_empty=body.seed_layout_if_empty,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


class CallLogBody(BaseModel):
    group_key: str | None = None
    export_id: str | None = None
    summary: str
    what_failed: str | None = ""
    resolved: bool = False


@app.post("/api/verifone/tech/log-call")
def verifone_log_call(body: CallLogBody):
    """One-tap after-call note into Liferaft emergency block."""
    try:
        return tech.log_call_outcome(
            body.group_key,
            body.export_id,
            summary=body.summary,
            what_failed=body.what_failed or "",
            resolved=body.resolved,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/ssh/reset-manager")
def verifone_ssh_reset_manager(body: SshResetManagerBody):
    """
    SSH as maint (local fleet secret) and run ``resetpw manager``.
    Returns temp Manager password once; does not put secrets in git.
    Final password (e.g. A6652990) is set in Config Client forced-change, then confirm endpoint.
    """
    try:
        return cmd_ssh.reset_manager_password(
            body.host,
            port=body.port or 22,
            username=body.ssh_user,
            password=body.ssh_password,
            group_key=body.group_key,
            export_id=body.export_id,
            target_letter=body.target_letter or "A",
            password_base=body.password_base,
            update_liferaft=body.update_liferaft,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/verifone/ssh/confirm-manager-password")
def verifone_ssh_confirm_manager(body: SshConfirmManagerBody):
    """After Config Client forced change, record final Manager password (A+base) in Liferaft."""
    try:
        return cmd_ssh.confirm_manager_final_password(
            body.group_key,
            body.export_id,
            password=body.password,
            use_pending=body.use_pending,
            mark_changed=body.mark_changed,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# --- SITE-INFO.md in backup folder (users, Manager days, network, equipment, topography) ---
import site_info_ops as site_info


class SiteInfoWriteBody(BaseModel):
    also_seed_layout: bool = False


class SiteLayoutSeedBody(BaseModel):
    force: bool = False


@app.get("/api/verifone/sites/{site_id}/site-info")
def verifone_site_info_preview(site_id: str):
    """Preview SITE-INFO.md content (POS users, Manager letter/days, network, equipment)."""
    try:
        return site_info.build_site_info_markdown(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/sites/{site_id}/site-info/write")
def verifone_site_info_write(site_id: str, body: SiteInfoWriteBody | None = None):
    """
    Write SITE-INFO.md into the SMS backup folder.
    Includes POS passwords (no 90-day rule), Manager letter + days remaining,
    survey network/routes (reference only — not pushable), equipment from backup.
    """
    try:
        also = body.also_seed_layout if body else False
        return site_info.write_site_info_md(site_id, also_seed_layout=also)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except OSError as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/verifone/sites/{site_id}/layout/seed-from-backup")
def verifone_layout_seed(site_id: str, body: SiteLayoutSeedBody | None = None):
    """Seed aerial topography defaults from backup (pumps, tanks, registers, CRIND palette)."""
    try:
        force = bool(body.force) if body else False
        return site_info.apply_topography_to_survey(site_id, only_if_empty=not force)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/verifone/sites/{site_id}/survey/share-packs")
def verifone_list_share_packs(site_id: str):
    """List previously built share packs under survey\\share-packs\\."""
    try:
        return survey_share.list_share_packs(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/sites/{site_id}/survey/share-pack")
def verifone_export_share_pack(site_id: str, body: VfSurveyShareBody | None = None):
    """
    Build a share / recovery pack:
      redacted  — email-safe folder (secrets + OCR raw stripped)
      full      — local tech ZIP (optional photos)
      checklist — recovery checklist Markdown only
    """
    body = body or VfSurveyShareBody()
    try:
        return survey_share.export_share_pack(
            site_id,
            mode=body.mode or "redacted",
            include_photos=bool(body.include_photos),
            include_layout_json=bool(body.include_layout_json if body.include_layout_json is not None else True),
            include_checklist=bool(body.include_checklist if body.include_checklist is not None else True),
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Share pack failed: {e}") from e


@app.get("/api/verifone/survey/ocr-status")
def verifone_survey_ocr_status():
    """Which OCR engines are available on this PC."""
    return {"ok": True, **survey_ocr.ocr_engine_status()}


@app.get("/api/verifone/sites/{site_id}/survey/photos")
def verifone_survey_list_photos(site_id: str):
    try:
        return survey_ocr.list_captures(site_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/verifone/sites/{site_id}/survey/photos/{capture_id}")
def verifone_survey_get_photo(site_id: str, capture_id: str):
    try:
        return survey_ocr.get_capture(site_id, capture_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/verifone/sites/{site_id}/survey/ocr")
def verifone_survey_ocr_ingest(site_id: str, body: VfSurveyOcrBody):
    """
    Upload POS/Commander screen photos (base64) and/or pasted OCR text.
    Stores images + exact raw text under survey\\photos, parses config fields,
    and optionally fills the site-survey form (fill_empty by default).
    """
    try:
        return survey_ocr.ingest_photos(
            site_id,
            images=body.images,
            raw_texts=body.raw_texts,
            apply_mode=body.apply_mode or "fill_empty",
            notes=body.notes or "",
            prefer_engine=body.prefer_engine,
            domain=body.domain or "pos",
            screen_type=body.screen_type or "auto",
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"OCR ingest failed: {e}") from e


@app.post("/api/verifone/sites/{site_id}/survey/ocr/apply")
def verifone_survey_ocr_apply(site_id: str, body: VfSurveyOcrApplyBody):
    """Apply a prior capture's fields (or explicit field map) onto the site survey."""
    if not body.capture_id and not body.fields:
        raise HTTPException(400, "capture_id or fields required")
    try:
        if body.capture_id:
            return survey_ocr.apply_capture_fields(
                site_id,
                body.capture_id,
                mode=body.mode or "fill_empty",
                fields=body.fields,
            )
        survey = vf.get_survey(site_id)
        result = survey_ocr.apply_fields_to_survey(
            survey, body.fields or {}, mode=body.mode or "fill_empty"
        )
        saved = vf.save_survey(site_id, result["survey"])
        return {
            "ok": True,
            "path": saved.get("path"),
            "applied": result["applied"],
            "skipped": result["skipped"],
            "mode": result["mode"],
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/verifone/punch-list")
def verifone_punch_list(body: VfPunchBody):
    import os

    def _finish(result: dict) -> dict:
        path = (result or {}).get("path")
        opened = False
        if body.open and path:
            try:
                p = Path(path)
                if p.is_file():
                    os.startfile(str(p))  # Excel / SpreadsheetML default app
                    opened = True
                elif p.parent.is_dir():
                    os.startfile(str(p.parent))
                    opened = True
            except OSError:
                opened = False
        out = dict(result or {})
        out["opened"] = opened
        return out

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
        return _finish(vf.prefill_punch_list(ROOT, dossier))
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
    return _finish(vf.prefill_punch_list(ROOT, dossier))


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
            before_dir_id=body.before_dir_id,
            after_dir_id=body.after_dir_id,
            require_upscale_name=body.require_upscale_name,
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
def api_suggest_pairs(
    limit: int = 30,
    min_ratio: float = 0.55,
    before_dir_id: str | None = None,
    after_dir_id: str | None = None,
    unpaired_only: bool = True,
    tail_len: int = 5,
    use_tail: bool = True,
    use_digits: bool = True,
    use_fuzzy: bool = True,
    use_folder: bool = True,
):
    return ops.suggest_pairs(
        limit=limit,
        min_ratio=min_ratio,
        before_dir_id=before_dir_id or None,
        after_dir_id=after_dir_id or None,
        unpaired_only=unpaired_only,
        tail_len=tail_len,
        use_tail=use_tail,
        use_digits=use_digits,
        use_fuzzy=use_fuzzy,
        use_folder=use_folder,
    )


@app.post("/api/pairs/suggest")
def api_suggest_pairs_post(body: SuggestPairsRequest):
    return {
        "ok": True,
        "suggestions": ops.suggest_pairs(
            limit=body.limit,
            min_ratio=body.min_ratio,
            media_type=body.kind if body.kind in ("video", "image") else None,
            before_dir_id=body.before_dir_id,
            after_dir_id=body.after_dir_id,
            unpaired_only=body.unpaired_only,
            tail_len=body.tail_len,
            use_tail=body.use_tail,
            use_digits=body.use_digits,
            use_fuzzy=body.use_fuzzy,
            use_folder=body.use_folder,
        ),
        "before_dir_id": body.before_dir_id,
        "after_dir_id": body.after_dir_id,
        "tail_len": body.tail_len,
    }


class PairCandidatesRequest(BaseModel):
    media_id: str
    limit: int = 10
    min_ratio: float = 0.35
    exclude_ids: list[str] = []
    unpaired_only: bool = True
    tail_len: int = 5
    after_dir_id: str | None = None
    before_dir_id: str | None = None


@app.get("/api/pairs/learn")
def api_pair_learn_summary():
    """Naming schemes learned from confirmed pairs (guided match memory)."""
    try:
        from pair_learn import summary
        return summary()
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/pairs/learn/reset")
def api_pair_learn_reset():
    try:
        from pair_learn import reset_model
        return reset_model()
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/pairs/anchors")
def api_pair_anchors(
    limit: int = 200,
    kind: str | None = None,
    dir_id: str | None = None,
    before_dir_id: str | None = None,
    after_dir_id: str | None = None,
    prefer_sources: bool = True,
):
    """Unpaired files for guided match queue (sources first).

    Pass before_dir_id to queue only files from the Before/source folder.
    """
    return {
        "anchors": ops.list_unpaired_anchors(
            kind=kind if kind in ("video", "image") else None,
            limit=limit,
            prefer_sources=prefer_sources,
            dir_id=dir_id,
            before_dir_id=before_dir_id,
            after_dir_id=after_dir_id,
        )
    }


@app.get("/api/pairs/candidates")
def api_pair_candidates_get(
    mid: str = Query(..., description="Anchor media id"),
    limit: int = 10,
    min_ratio: float = 0.35,
    exclude: str = "",
    unpaired_only: bool = True,
    tail_len: int = 5,
    after_dir_id: str | None = None,
    before_dir_id: str | None = None,
):
    """Top N match candidates for one media (guided elimination)."""
    exclude_ids = [x.strip() for x in (exclude or "").split(",") if x.strip()]
    try:
        return ops.candidates_for_media(
            mid,
            limit=limit,
            min_ratio=min_ratio,
            exclude_ids=exclude_ids,
            unpaired_only=unpaired_only,
            tail_len=tail_len,
            after_dir_id=after_dir_id,
            before_dir_id=before_dir_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/pairs/candidates")
def api_pair_candidates_post(body: PairCandidatesRequest):
    try:
        return ops.candidates_for_media(
            body.media_id,
            limit=body.limit,
            min_ratio=body.min_ratio,
            exclude_ids=body.exclude_ids or [],
            unpaired_only=body.unpaired_only,
            tail_len=body.tail_len,
            after_dir_id=body.after_dir_id,
            before_dir_id=body.before_dir_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e

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
import task_manager_pro as tmpro
import setup_ops
import launch_ops
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


class DupScanControl(BaseModel):
    job_id: str
    action: str  # pause | resume | cancel


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


@app.get("/api/duplicates/drives")
def api_dup_drives():
    """Local drives available for a This PC / whole-system scan."""
    roots = [str(p) for p in dup.list_local_drives()]
    return {"ok": True, "drives": roots, "label": "This PC (" + ", ".join(roots) + ")" if roots else "This PC"}


@app.get("/api/duplicates/scan")
def api_dup_scan(
    folder: str = "",
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "video",
    recursive: bool = True,
    whole_system: bool = False,
):
    try:
        return dup.scan_folder_duplicates(
            folder,
            deep=deep,
            match_mode=match_mode,
            file_types=file_types,
            recursive=recursive,
            whole_system=whole_system,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/duplicates/scan/stream")
def api_dup_scan_stream(
    folder: str = "",
    deep: bool = False,
    match_mode: str = "quick",
    file_types: str = "all",
    recursive: bool = True,
    whole_system: bool = False,
):
    """SSE scan stream. Emits path progress and live `groups` as duplicates appear."""
    job = dup.start_scan_job(
        folder,
        deep=deep,
        match_mode=match_mode,
        file_types=file_types,
        recursive=recursive,
        whole_system=whole_system,
    )

    def gen():
        yield f"data: {json.dumps({'job_id': job.id, 'state': job.state})}\n\n"
        try:
            while True:
                batch = job.drain(timeout=0.12)
                for item in batch:
                    yield f"data: {json.dumps(item)}\n\n"
                    if item.get("done") or item.get("error"):
                        return
                if job.finished and not batch:
                    return
        except GeneratorExit:
            job.controller.cancel()
            raise

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/duplicates/scan/control")
def api_dup_scan_control(body: DupScanControl):
    ok = dup.control_scan_job(body.job_id, body.action)
    if not ok:
        raise HTTPException(404, "Scan job not found")
    return {"ok": True, "job_id": body.job_id, "state": dup.job_state(body.job_id)}


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


@app.get("/api/files/preview")
def api_files_preview(path: str = Query(...), t: float = Query(0.5, ge=0, le=36000)):
    """Still preview for duplicate browser: image as-is, video = first frame (ffmpeg)."""
    try:
        img_path, media_type = dup.file_preview_image(path, timestamp=float(t or 0.5))
        return FileResponse(
            img_path,
            media_type=media_type,
            headers={
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(415, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


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


# --- FAFO Task Manager Pro (intel + efficiency + optional NVD) ---
class TmproRefresh(BaseModel):
    force: bool = False
    max_apps: int = 20
    only_seen_since_days: int | None = 7


@app.get("/api/tmpro/overview")
def api_tmpro_overview():
    try:
        return tmpro.overview()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/processes")
def api_tmpro_processes(
    sort_by: str = "cpu",
    search: str = "",
    limit: int = 250,
):
    try:
        return tmpro.list_processes_intel(sort_by=sort_by, search=search, limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/processes/{pid}")
def api_tmpro_process_detail(pid: int):
    try:
        return tmpro.get_process_intel(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/ratings")
def api_tmpro_ratings(limit: int = 100):
    try:
        return tmpro.list_ratings(limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/startup")
def api_tmpro_startup():
    try:
        return tmpro.startup_intel()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/knowledge")
def api_tmpro_knowledge():
    try:
        return tmpro.knowledge_stats()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tmpro/seen")
def api_tmpro_seen():
    try:
        return tmpro.get_seen_apps()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/tmpro/refresh")
def api_tmpro_refresh(body: TmproRefresh = TmproRefresh()):
    """Weekly-style NVD keyword refresh for apps seen on this PC."""
    try:
        # Optional NVD API key from env only (never from JSON secrets file)
        import os as _os
        key = _os.environ.get("NVD_API_KEY") or _os.environ.get("FAFO_NVD_API_KEY") or None
        return tmpro.weekly_intel_refresh(
            force=bool(body.force),
            max_apps=int(body.max_apps or 20),
            only_seen_since_days=body.only_seen_since_days,
            api_key=key,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/setup/status")
def api_setup_status():
    """First-run / setup completeness for launcher thin-shell UX."""
    try:
        return setup_ops.get_setup_status()
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Multi-server launch prefs + Windows startup ---
class LaunchPrefsBody(BaseModel):
    startWithOneClick: dict[str, bool] | None = None
    windowsStartup: dict[str, bool] | None = None
    blockAutoStart: dict[str, bool] | None = None
    fafoMetaRoot: str | None = None


class LaunchCompanionsBody(BaseModel):
    toolbox: bool | None = None
    fafoMeta: bool | None = None
    waitSec: float = 12.0
    force: bool = False  # ignore blockAutoStart (manual command-board start)


class WindowsStartupBody(BaseModel):
    servers: bool | None = None
    app: bool | None = None


@app.get("/api/launch/status")
def api_launch_status():
    """Companion server health + launch prefs + Windows startup flags."""
    try:
        return launch_ops.companion_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/launch/prefs")
def api_launch_prefs_get():
    try:
        return launch_ops.get_prefs()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/api/launch/prefs")
def api_launch_prefs_put(body: LaunchPrefsBody):
    try:
        payload = body.model_dump(exclude_none=True)
        return launch_ops.apply_prefs_and_startup(payload)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/companions/start")
def api_launch_companions_start(body: LaunchCompanionsBody | None = None):
    """Start toolbox and/or FAFO tagging companion (uses prefs when flags omitted)."""
    try:
        b = body or LaunchCompanionsBody()
        return launch_ops.start_companions(
            toolbox=b.toolbox,
            fafo_meta=b.fafoMeta,
            wait_sec=b.waitSec,
            force=bool(b.force),
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/companions/restart")
def api_launch_companions_restart(body: LaunchCompanionsBody | None = None):
    """Stop then start companions (hidden). Used by tray / Launcher relaunch."""
    try:
        b = body or LaunchCompanionsBody()
        return launch_ops.restart_companions(
            toolbox=b.toolbox,
            fafo_meta=b.fafoMeta,
            wait_sec=b.waitSec if b.waitSec else 15.0,
            force=bool(b.force),
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/companions/stop")
def api_launch_companions_stop(body: LaunchCompanionsBody | None = None):
    """Stop S1 and/or S2 and mark them sleeping so watchdog/tray will not auto-restart.

    S1 = HTML Toolbox · S2 = Ultimate Tab (independent products).
    """
    try:
        b = body or LaunchCompanionsBody()
        # Default body None fields mean "stop both" in stop_companions
        return launch_ops.stop_companions(
            toolbox=b.toolbox if body is not None else None,
            fafo_meta=b.fafoMeta if body is not None else None,
            mark_sleep=True,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/companions/sleep")
def api_launch_companions_sleep(body: LaunchCompanionsBody | None = None):
    """Sleep (stop + sticky off) S1 HTML Toolbox and/or S2 Ultimate Tab independently."""
    try:
        b = body or LaunchCompanionsBody()
        return launch_ops.sleep_companions(
            toolbox=True if body is None else (True if b.toolbox is None else bool(b.toolbox)),
            fafo_meta=True if body is None else (True if b.fafoMeta is None else bool(b.fafoMeta)),
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/companions/wake")
def api_launch_companions_wake(body: LaunchCompanionsBody | None = None):
    """Wake (clear sleep + start) S1 and/or S2 independently."""
    try:
        b = body or LaunchCompanionsBody()
        return launch_ops.wake_companions(
            toolbox=True if body is None else (True if b.toolbox is None else bool(b.toolbox)),
            fafo_meta=True if body is None else (True if b.fafoMeta is None else bool(b.fafoMeta)),
            wait_sec=b.waitSec if body is not None else 12.0,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/launch/windows-startup")
def api_windows_startup_get():
    try:
        return launch_ops.windows_startup_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/windows-startup")
def api_windows_startup_set(body: WindowsStartupBody):
    """Enable/disable current-user Startup shortcuts for servers and/or app."""
    try:
        return launch_ops.set_windows_startup(servers=body.servers, app=body.app)
    except Exception as e:
        raise HTTPException(500, str(e))


class ToolsLaunchBody(BaseModel):
    """Allowlisted local Windows tools that browsers cannot run directly (.bat / elevated)."""
    id: str
    action: str | None = "run"  # run | folder | ui


@app.post("/api/tools/launch")
def api_tools_launch(body: ToolsLaunchBody):
    """
    Launch allowlisted desktop tools (elevated PowerShell, Explorer, etc.).
    Used when Chrome cannot execute .bat/.ps1 from http:// toolbox pages.
    """
    import subprocess

    tid = (body.id or "").strip().lower()
    action = (body.action or "run").strip().lower()

    # Explicit allowlist only — never run arbitrary paths from the browser
    if tid in ("ghost-device-cleaner", "ghost", "ghost-cleaner", "ghostcleaner"):
        folder = ROOT / "GhostDeviceCleaner"
        if action in ("folder", "open-folder"):
            target = folder
            if not target.is_dir():
                raise HTTPException(404, "GhostDeviceCleaner folder missing")
            subprocess.Popen(["explorer.exe", str(target)], shell=False)
            return {"ok": True, "launched": "folder", "path": str(target)}

        if action in ("ui", "html", "page"):
            html = folder / "Clear-GhostDevices.html"
            if not html.is_file():
                raise HTTPException(404, "Clear-GhostDevices.html missing")
            # Prefer mshta for the HTA-style shell; fall back to default association
            try:
                subprocess.Popen(["mshta.exe", str(html)], cwd=str(folder), shell=False)
            except OSError:
                subprocess.Popen(["cmd.exe", "/c", "start", "", str(html)], cwd=str(folder), shell=False)
            return {"ok": True, "launched": "ui", "path": str(html)}

        # Default: elevated cleaner (UAC prompt → picker UI in PowerShell)
        bat = folder / "Run-Cleaner-Elevated.bat"
        ps1 = folder / "Clear-GhostDevices.ps1"
        if bat.is_file():
            creation = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat)],
                cwd=str(folder),
                shell=False,
                creationflags=creation,
            )
            return {"ok": True, "launched": "ghost-elevated", "via": "Run-Cleaner-Elevated.bat"}
        if ps1.is_file():
            # Direct elevate if bat missing
            ps = r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
            ps = os.path.expandvars(ps)
            arg = (
                f"Start-Process -FilePath '{ps}' -Verb RunAs -ArgumentList "
                f"@('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','{ps1}')"
            )
            subprocess.Popen(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", arg],
                cwd=str(folder),
                shell=False,
            )
            return {"ok": True, "launched": "ghost-elevated", "via": "Clear-GhostDevices.ps1"}
        raise HTTPException(404, "Ghost cleaner scripts missing")

    if tid in (
        "transfer-monitor",
        "transfermonitor",
        "download-monitor",
        "downloadmonitor",
        "transfers",
    ):
        folder = ROOT / "System Tools" / "TransferMonitor"
        if action in ("folder", "open-folder"):
            target = folder
            if not target.is_dir():
                raise HTTPException(404, "TransferMonitor folder missing")
            subprocess.Popen(["explorer.exe", str(target)], shell=False)
            return {"ok": True, "launched": "folder", "path": str(target)}

        if action in ("ui", "html", "page"):
            html = folder / "Transfer Monitor.html"
            if not html.is_file():
                raise HTTPException(404, "Transfer Monitor.html missing")
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", str(html)],
                cwd=str(folder),
                shell=False,
            )
            return {"ok": True, "launched": "ui", "path": str(html)}

        # Default: tray app, no console (prefer VBS hidden launch)
        bat = folder / "Launch-TransferMonitor.bat"
        vbs = folder / "Launch-TransferMonitor.vbs"
        ps1 = folder / "TransferMonitor.ps1"
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if vbs.is_file():
            subprocess.Popen(
                ["wscript.exe", "//B", str(vbs)],
                cwd=str(folder),
                shell=False,
                creationflags=creation,
            )
            return {"ok": True, "launched": "transfer-monitor", "via": "Launch-TransferMonitor.vbs"}
        if bat.is_file():
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat)],
                cwd=str(folder),
                shell=False,
                creationflags=creation,
            )
            return {"ok": True, "launched": "transfer-monitor", "via": "Launch-TransferMonitor.bat"}
        if ps1.is_file():
            ps = os.path.expandvars(r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
            subprocess.Popen(
                [
                    ps,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    str(ps1),
                ],
                cwd=str(folder),
                shell=False,
                creationflags=creation,
            )
            return {"ok": True, "launched": "transfer-monitor", "via": "TransferMonitor.ps1"}
        raise HTTPException(404, "Transfer Monitor scripts missing")

    raise HTTPException(400, f"Unknown or blocked tool launch id: {tid}")
@app.get("/api/launch/watchdog/status")
def api_watchdog_status():
    """Server watchdog report + whether monitor process is running."""
    try:
        return launch_ops.watchdog_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/watchdog/start")
def api_watchdog_start():
    """Start the S1/S2 watchdog monitor (hidden)."""
    try:
        return launch_ops.watchdog_start()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/watchdog/install")
def api_watchdog_install():
    """Install login/poll keep-alive + start watchdog."""
    try:
        return launch_ops.watchdog_install()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/watchdog/open-status")
def api_watchdog_open_status():
    """Open server-watchdog-status.html (generate if needed)."""
    try:
        return launch_ops.watchdog_open_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/launch/watchdog/open-folder")
def api_watchdog_open_folder():
    """Open Explorer to the watchdog .bat files in the toolbox root."""
    try:
        return launch_ops.watchdog_open_bats_folder()
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
    """Pull public threat feeds (no API key required). Optional abuse.ch key adds extras."""
    try:
        return sec.update_threat_intel()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/security/ensure-db")
def api_security_ensure_db():
    """If the hash DB is empty, download open feeds automatically."""
    try:
        return sec.ensure_threat_db_populated()
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


class ScaleMaxSideBody(BaseModel):
    src: str
    max_side: int = 3840
    output_dir: str | None = None
    fmt: str = "mp4"
    crf: int | None = None
    fps: int | None = None
    quality: str = "high"  # match | archive | high | balanced | small
    copy_if_fits: bool = True  # stream-copy when already ≤ max_side (no quality loss)
    bitrate_mode: str = "retain"  # retain source Mbps | proportional to pixel area
    video_bitrate: int | None = None  # optional explicit bits/s target


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


@app.get("/api/pc-diagnostics/prefs")
def api_pc_diag_prefs():
    prefs = pc_diag.load_prefs()
    return {
        "ok": True,
        "prefs": prefs,
        "knownFindingKeys": [
            {"key": k, "label": v.get("label") or k}
            for k, v in pc_diag.KNOWN_FINDING_KEYS.items()
        ],
    }


@app.get("/api/pc-diagnostics/ignored-devices")
def api_pc_diag_ignored_get():
    return {"ok": True, "ignored": pc_diag.load_ignored_devices()}


@app.post("/api/pc-diagnostics/ignored-devices")
def api_pc_diag_ignored_add(body: dict | None = None):
    body = body or {}
    entry = {
        "id": str(body.get("id") or "").strip(),
        "name": str(body.get("name") or "").strip(),
        "class": str(body.get("class") or body.get("class_") or "").strip(),
        "kind": str(body.get("kind") or "").strip(),
        "nameContains": str(body.get("nameContains") or body.get("pattern") or "").strip(),
        "reason": str(body.get("reason") or "user").strip() or "user",
    }
    if not any(entry.get(k) for k in ("id", "name", "nameContains", "class", "kind")):
        raise HTTPException(400, "Provide device id, name, nameContains, class, or kind to mute")
    try:
        rows = pc_diag.ignore_device(entry)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    report = pc_diag.load_latest()
    return {"ok": True, "ignored": rows, "report": report, "prefs": pc_diag.load_prefs()}


@app.delete("/api/pc-diagnostics/ignored-devices")
def api_pc_diag_ignored_delete(id: str = "", name: str = ""):
    if not id and not name:
        raise HTTPException(400, "Provide id or name query param")
    rows = pc_diag.unignore_device(device_id=id, name=name)
    report = pc_diag.load_latest()
    return {"ok": True, "ignored": rows, "report": report, "prefs": pc_diag.load_prefs()}


@app.get("/api/pc-diagnostics/dismissed-findings")
def api_pc_diag_dismissed_get():
    return {
        "ok": True,
        "dismissed": pc_diag.load_dismissed_findings(),
        "knownFindingKeys": [
            {"key": k, "label": v.get("label") or k}
            for k, v in pc_diag.KNOWN_FINDING_KEYS.items()
        ],
    }


@app.post("/api/pc-diagnostics/dismiss-finding")
def api_pc_diag_dismiss_finding(body: dict | None = None):
    """Dismiss a known finding (e.g. power-outage Kernel-Power 41 / Event 6008)."""
    body = body or {}
    key = str(body.get("key") or "").strip()
    if not key:
        # Convenience aliases
        alias = str(body.get("alias") or body.get("type") or "").strip().lower()
        if alias in ("power", "power_outage", "outage", "shutdown", "kernel_power", "41", "6008"):
            key = "stability:unexpected_shutdown"
        elif alias in ("devices", "device_errors"):
            key = "devices:errors"
    if not key:
        raise HTTPException(
            400,
            "Provide key (e.g. stability:unexpected_shutdown) or alias=power_outage",
        )
    try:
        rows = pc_diag.dismiss_finding(
            key,
            note=str(body.get("note") or body.get("reason") or ""),
            label=str(body.get("label") or ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    report = pc_diag.load_latest()
    return {"ok": True, "dismissed": rows, "report": report, "prefs": pc_diag.load_prefs()}


@app.delete("/api/pc-diagnostics/dismiss-finding")
def api_pc_diag_undismiss_finding(key: str = ""):
    if not key:
        raise HTTPException(400, "Provide key query param")
    rows = pc_diag.undismiss_finding(key)
    report = pc_diag.load_latest()
    return {"ok": True, "dismissed": rows, "report": report, "prefs": pc_diag.load_prefs()}


@app.post("/api/pc-diagnostics/dismiss-suggestion")
def api_pc_diag_dismiss_suggestion(body: dict | None = None):
    body = body or {}
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "Provide suggestion title")
    try:
        rows = pc_diag.dismiss_suggestion(
            title=title,
            component_id=str(body.get("componentId") or body.get("component_id") or ""),
            note=str(body.get("note") or body.get("reason") or ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    report = pc_diag.load_latest()
    return {"ok": True, "dismissedSuggestions": rows, "report": report, "prefs": pc_diag.load_prefs()}


@app.delete("/api/pc-diagnostics/dismiss-suggestion")
def api_pc_diag_undismiss_suggestion(key: str = "", title: str = ""):
    if not key and not title:
        raise HTTPException(400, "Provide key or title")
    rows = pc_diag.undismiss_suggestion(key=key, title=title)
    report = pc_diag.load_latest()
    return {"ok": True, "dismissedSuggestions": rows, "report": report, "prefs": pc_diag.load_prefs()}


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


@app.get("/api/convert/list-dir")
def api_convert_list_dir(folder: str, limit: int = 40):
    """List files in a folder (output directory browser for VID TRIM)."""
    try:
        return convert.list_dir_brief(folder, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/convert/scale-max-side")
def api_convert_scale_max_side(body: ScaleMaxSideBody):
    """Scale one video so longest side ≤ max_side (never upscale); write MP4/WebM to output_dir."""
    try:
        return convert.scale_max_side(
            body.src,
            max_side=body.max_side,
            output_dir=body.output_dir,
            fmt=body.fmt,
            crf=body.crf,
            fps=body.fps,
            quality=body.quality or "high",
            copy_if_fits=body.copy_if_fits is not False,
            bitrate_mode=body.bitrate_mode or "retain",
            video_bitrate=body.video_bitrate,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
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



# --- Optional Xero proxy (local-only module; gitignored) ---
try:
    from _private_xero_routes import register as _register_xero
    _register_xero(app)
except ImportError:
    pass  # public clone: Xero integration not shipped


# --- Admin ops: system health + secrets presence (never return secret values) ---
import sys_ops as sysops


@app.get("/api/sys/health")
def api_sys_health(force: int = Query(0)):
    """
    System Health Desk metrics. Loopback metrics + toolbox/Xero presence only.
    Never includes tokens, secrets, or process command lines.
    """
    try:
        return sysops.get_sys_health(force=bool(force))
    except Exception as e:
        # Degrade rather than 500 crash — UI still loads
        return {
            "ok": False,
            "error": str(e)[:200],
            "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "securityNote": "No secrets/tokens returned.",
        }


@app.get("/api/secrets/presence")
def api_secrets_presence(force: int = Query(0)):
    """
    Secrets Presence Console — names + has/age flags only.
    Never decrypts DPAPI or returns secret/token material.
    """
    try:
        return sysops.get_secrets_presence(force=bool(force))
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:200],
            "secrets": [],
            "flags": {},
            "banner": "Values never shown in this UI — presence flags only.",
            "securityNote": "Never returns secret material, tokens, or DPAPI bytes.",
        }


def _safe_stdio() -> None:
    """Make print() safe on Windows (cp1252 consoles / redirected log files).

    Watchdog/tray launch S1 with stdout/stderr appended to S1-toolbox-server.log.
    Without UTF-8 reconfigure, a single Unicode character in a banner print
    (e.g. U+2192 RIGHTWARDS ARROW) raises UnicodeEncodeError and the process
    dies before uvicorn binds - crash-loop + unstable S1.
    """
    import sys

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
                continue
        except Exception:
            pass
        try:
            buf = getattr(stream, "buffer", None)
            if buf is not None:
                import io

                wrapped = io.TextIOWrapper(
                    buf,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                    write_through=True,
                )
                setattr(sys, stream_name, wrapped)
        except Exception:
            pass


def main():
    _safe_stdio()
    host, port = load_bind()
    # Re-bind module globals if env changed after import
    global BIND_HOST, BIND_PORT
    BIND_HOST, BIND_PORT = host, port
    # ASCII-only banners so even a broken stdio encoding cannot kill bind.
    print(f"\n  AI Toolbox Server -> http://{host}:{port}", flush=True)
    print(f"  (dedicated bind - not 127.0.0.1:8765 / FAFO companion)", flush=True)
    print(f"  FFmpeg: {'yes' if ops.find_ffmpeg() else 'install ffmpeg for pro thumbnails'}", flush=True)
    print("  Press Ctrl+C to stop\n", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
