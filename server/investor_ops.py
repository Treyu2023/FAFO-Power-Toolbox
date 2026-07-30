"""
Private Investor Portal — only two seats (owner + Sumran).

Data lives under %LOCALAPPDATA%\\FAFO\\investor\\ (never git):
  users.json       password hashes + display names
  sessions.json    bearer tokens
  sheet.json       spreadsheet columns + rows
  receipts\\        uploaded files (any format)
  receipts.json    receipt metadata

Not a public multi-tenant product — intentional dual-access vault for
the FAFO builder and investor Muhammad Sumran Nasir.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "FAFO.InvestorPortal/1"
SESSION_TTL_SEC = 60 * 60 * 24 * 30  # 30 days
MAX_RECEIPT_BYTES = 40 * 1024 * 1024  # 40 MB
ALLOWED_USERS = ("owner", "sumran")

_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fafo_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    d = base / "FAFO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def root_dir() -> Path:
    d = _fafo_dir() / "investor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def receipts_dir() -> Path:
    d = root_dir() / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _users_path() -> Path:
    return root_dir() / "users.json"


def _sessions_path() -> Path:
    return root_dir() / "sessions.json"


def _sheet_path() -> Path:
    return root_dir() / "sheet.json"


def _receipts_meta_path() -> Path:
    return root_dir() / "receipts.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _hash_password(password: str, salt: bytes | None = None) -> dict[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    # pbkdf2 — stdlib only, fine for local dual-user vault
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return {
        "algo": "pbkdf2_sha256",
        "salt": salt.hex(),
        "hash": dk.hex(),
        "iters": "120000",
    }


def _verify_password(password: str, record: dict[str, Any]) -> bool:
    try:
        salt = bytes.fromhex(str(record.get("salt") or ""))
        iters = int(record.get("iters") or 120000)
        expected = str(record.get("hash") or "")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, TypeError):
        return False


# Column ids / name fragments treated as COST (never public on FAFO Petro).
# Customers may see inventory + sell price; COGS / our cost stays owner+Sumran only.
COST_COLUMN_IDS = frozenset({
    "cost", "cogs", "unitcost", "unit_cost", "ourcost", "our_cost", "dealer",
    "dealercost", "dealer_cost", "wholesale", "landed", "landedcost", "invoice_cost",
    "invoicecost", "purchase_cost", "purchasecost", "buyprice", "buy_price",
    "acqcost", "acquisitioncost", "netcost", "basecost", "internalcost",
    "margin", "markup_pct", "markuppct", "profit", "profit_each",
})
COST_NAME_HINTS = (
    "cost", "cogs", "wholesale", "dealer", "landed", "our price", "our cost",
    "buy price", "acquisition", "margin", "profit", "invoice cost",
)


def _norm_col_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def is_cost_column(col: dict[str, Any] | str) -> bool:
    """True if this column is cost/COGS sensitive (private). Name/id wins over a mistaken 'public' flag."""
    if isinstance(col, str):
        col = {"id": col, "name": col}
    if col.get("isCost") is True or col.get("costSensitive") is True:
        return True
    if col.get("private") is True:
        return True
    cid = _norm_col_id(col.get("id") or "")
    if cid in COST_COLUMN_IDS or cid.endswith("cost") or cid.startswith("cost"):
        return True
    name = str(col.get("name") or "").lower()
    if any(h in name for h in COST_NAME_HINTS):
        return True
    # Explicit private visibility (internal notes, etc.) — not always cost, but not public
    if col.get("visibility") == "private":
        return True
    return False


def default_columns() -> list[dict[str, Any]]:
    """
    Starter categories — Sumran can add/rename/remove freely.

    visibility:
      public  → OK on FAFO Petro inventory (customers may see)
      private → toolbox + Sumran private page only (costs, margins, etc.)
    """
    return [
        {"id": "item", "name": "Item / Asset", "type": "text", "width": 160, "visibility": "public"},
        {"id": "serial", "name": "Serial #", "type": "text", "width": 140, "visibility": "public"},
        {"id": "category", "name": "Category", "type": "text", "width": 120, "visibility": "public"},
        # What customers pay — OK to show on public inventory
        {"id": "price", "name": "Sell price", "type": "number", "width": 100, "visibility": "public"},
        # What WE pay — NEVER public on FAFO Petro
        {
            "id": "cost",
            "name": "Our cost (private)",
            "type": "number",
            "width": 110,
            "visibility": "private",
            "isCost": True,
        },
        {"id": "qty", "name": "Qty", "type": "number", "width": 70, "visibility": "public"},
        {"id": "vendor", "name": "Vendor", "type": "text", "width": 120, "visibility": "private"},
        {"id": "purchased", "name": "Purchase date", "type": "date", "width": 120, "visibility": "private"},
        {"id": "status", "name": "Status", "type": "text", "width": 100, "visibility": "public"},
        {"id": "notes", "name": "Notes (public)", "type": "text", "width": 180, "visibility": "public"},
        {
            "id": "private_notes",
            "name": "Internal notes",
            "type": "text",
            "width": 180,
            "visibility": "private",
        },
    ]


def normalize_column(c: dict[str, Any]) -> dict[str, Any]:
    cid = re.sub(r"[^a-z0-9_]+", "_", str(c.get("id") or c.get("name") or "col").lower())[:40] or "col"
    name = str(c.get("name") or cid)[:80]
    vis = str(c.get("visibility") or "").lower().strip()
    # Detect cost from id/name first (cannot be overridden to public)
    cost_probe = {"id": cid, "name": name, "isCost": c.get("isCost"), "costSensitive": c.get("costSensitive")}
    is_cost = bool(c.get("isCost") or c.get("costSensitive")) or is_cost_column(cost_probe)
    if is_cost:
        vis = "private"
    elif vis == "private":
        is_cost = False  # private non-cost (e.g. internal notes) — still stripped from public
    elif vis not in ("public", "private"):
        vis = "public"
    return {
        "id": cid,
        "name": name,
        "type": str(c.get("type") or "text")[:20],
        "width": int(c.get("width") or 120),
        "visibility": vis,
        "isCost": is_cost,
    }


def public_column_ids(columns: list[dict[str, Any]] | None = None) -> list[str]:
    cols = columns or (ensure_sheet().get("columns") or [])
    out = []
    for c in cols:
        nc = normalize_column(c) if isinstance(c, dict) else normalize_column({"id": str(c)})
        if nc["visibility"] == "public" and not nc["isCost"]:
            out.append(nc["id"])
    return out


def sanitize_sheet_public(sheet: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Strip cost / private columns for FAFO Petro public inventory.
    Inventory + sell price OK; our cost NEVER leaves private surfaces.
    """
    full = sheet or ensure_sheet()
    cols_in = full.get("columns") or []
    public_cols = []
    for c in cols_in:
        nc = normalize_column(c) if isinstance(c, dict) else normalize_column({"id": str(c)})
        if nc["isCost"] or nc["visibility"] == "private":
            continue
        public_cols.append({k: nc[k] for k in ("id", "name", "type", "width", "visibility")})
    allowed = {c["id"] for c in public_cols}
    # also strip any raw cost-like keys that slipped into rows without a column def
    rows_out = []
    for r in full.get("rows") or []:
        if not isinstance(r, dict):
            continue
        row = {"id": r.get("id")}
        for k, v in r.items():
            if k == "id":
                continue
            if k not in allowed:
                continue
            if is_cost_column(k):
                continue
            row[k] = v
        rows_out.append(row)
    return {
        "schema": SCHEMA,
        "kind": "fafo-public-inventory",
        "title": full.get("title") or "FAFO Inventory",
        "updatedAt": full.get("updatedAt"),
        "columns": public_cols,
        "rows": rows_out,
        "privacy": {
            "costsStripped": True,
            "note": "Our cost / COGS / private columns removed for public FAFO Petro pages.",
        },
    }


def empty_sheet() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "title": "FAFO Investor Ledger",
        "updatedAt": _utc_now(),
        "updatedBy": None,
        "columns": default_columns(),
        "rows": [],
    }


def empty_receipts_meta() -> dict[str, Any]:
    return {"schema": SCHEMA, "items": []}


def status() -> dict[str, Any]:
    """Public-ish: whether vault exists (no secrets)."""
    users = _read_json(_users_path(), None)
    configured = bool(users and users.get("users"))
    return {
        "ok": True,
        "configured": configured,
        "seats": list(ALLOWED_USERS),
        "dataDir": str(root_dir()),
        "hint": (
            "Only two accounts: owner (builder) and sumran (investor). "
            "Data stays under %LOCALAPPDATA%\\FAFO\\investor on this PC."
        ),
    }


def ensure_sheet() -> dict[str, Any]:
    with _LOCK:
        sheet = _read_json(_sheet_path(), None)
        if not sheet or not isinstance(sheet, dict):
            sheet = empty_sheet()
            _write_json(_sheet_path(), sheet)
            return sheet
        # migrate columns: visibility + cost flags
        cols = sheet.get("columns") or []
        changed = False
        new_cols = []
        for c in cols:
            if not isinstance(c, dict):
                continue
            nc = normalize_column(c)
            if c.get("visibility") != nc["visibility"] or c.get("isCost") != nc["isCost"]:
                changed = True
            new_cols.append(nc)
        # ensure default cost column exists if only legacy "price" without cost
        ids = {c["id"] for c in new_cols}
        if "price" in ids and "cost" not in ids:
            new_cols.insert(
                next((i for i, c in enumerate(new_cols) if c["id"] == "price"), 0) + 1,
                normalize_column(
                    {
                        "id": "cost",
                        "name": "Our cost (private)",
                        "type": "number",
                        "width": 110,
                        "visibility": "private",
                        "isCost": True,
                    }
                ),
            )
            changed = True
            # rename ambiguous price label if still bare "Price"
            for c in new_cols:
                if c["id"] == "price" and str(c.get("name") or "").strip().lower() == "price":
                    c["name"] = "Sell price"
        if changed and new_cols:
            sheet["columns"] = new_cols
            sheet["updatedAt"] = sheet.get("updatedAt") or _utc_now()
            _write_json(_sheet_path(), sheet)
        return sheet


def setup_accounts(
    owner_password: str,
    sumran_password: str,
    *,
    owner_display: str = "Owner",
    sumran_display: str = "Muhammad Sumran Nasir",
    force: bool = False,
) -> dict[str, Any]:
    """
    One-time (or force reset by existing owner session via API layer).
    Creates both seats only — no third user ever.
    """
    owner_password = (owner_password or "").strip()
    sumran_password = (sumran_password or "").strip()
    if len(owner_password) < 6:
        raise ValueError("Owner password must be at least 6 characters")
    if len(sumran_password) < 6:
        raise ValueError("Sumran password must be at least 6 characters")

    with _LOCK:
        existing = _read_json(_users_path(), None)
        if existing and existing.get("users") and not force:
            raise ValueError(
                "Accounts already configured. Log in as owner to reset passwords, "
                "or pass force=true from an owner session."
            )

        users = {
            "schema": SCHEMA,
            "createdAt": (existing or {}).get("createdAt") or _utc_now(),
            "updatedAt": _utc_now(),
            "users": {
                "owner": {
                    "id": "owner",
                    "displayName": (owner_display or "Owner").strip() or "Owner",
                    "role": "admin",
                    "password": _hash_password(owner_password),
                },
                "sumran": {
                    "id": "sumran",
                    "displayName": (sumran_display or "Muhammad Sumran Nasir").strip()
                    or "Muhammad Sumran Nasir",
                    "role": "investor",
                    "password": _hash_password(sumran_password),
                },
            },
        }
        _write_json(_users_path(), users)
        ensure_sheet()
        if not _receipts_meta_path().is_file():
            _write_json(_receipts_meta_path(), empty_receipts_meta())
        # wipe sessions on full reset
        if force:
            _write_json(_sessions_path(), {"sessions": {}})

        return {
            "ok": True,
            "message": "Investor portal accounts ready (owner + sumran only).",
            "users": [
                {"id": "owner", "displayName": users["users"]["owner"]["displayName"], "role": "admin"},
                {"id": "sumran", "displayName": users["users"]["sumran"]["displayName"], "role": "investor"},
            ],
            "dataDir": str(root_dir()),
        }


def change_password(user_id: str, new_password: str, *, actor: str) -> dict[str, Any]:
    user_id = (user_id or "").strip().lower()
    new_password = (new_password or "").strip()
    if user_id not in ALLOWED_USERS:
        raise ValueError("Unknown user")
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters")
    # owner can change either; sumran only own
    if actor != "owner" and actor != user_id:
        raise PermissionError("Only owner can change the other password")

    with _LOCK:
        users = _read_json(_users_path(), None)
        if not users or user_id not in (users.get("users") or {}):
            raise ValueError("Accounts not configured")
        users["users"][user_id]["password"] = _hash_password(new_password)
        users["updatedAt"] = _utc_now()
        _write_json(_users_path(), users)
        # drop that user's sessions
        sess = _read_json(_sessions_path(), {"sessions": {}})
        sessions = sess.get("sessions") or {}
        dead = [k for k, v in sessions.items() if v.get("userId") == user_id]
        for k in dead:
            sessions.pop(k, None)
        sess["sessions"] = sessions
        _write_json(_sessions_path(), sess)
        return {"ok": True, "message": f"Password updated for {user_id}"}


def _purge_sessions(sessions: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    return {
        k: v
        for k, v in sessions.items()
        if float(v.get("expiresAt", 0)) > now
    }


def login(username: str, password: str) -> dict[str, Any]:
    username = (username or "").strip().lower()
    # allow aliases
    if username in {"admin", "builder", "neon", "neoninja", "neon-ninja", "me"}:
        username = "owner"
    if username in {"investor", "sumran nasir", "muhammad sumran nasir", "m. sumran", "nasir"}:
        username = "sumran"
    if username not in ALLOWED_USERS:
        raise ValueError("Only owner or sumran may log in")

    with _LOCK:
        users = _read_json(_users_path(), None)
        if not users or not users.get("users"):
            raise ValueError("Portal not set up yet — complete first-time setup")
        rec = users["users"].get(username)
        if not rec or not _verify_password(password, rec.get("password") or {}):
            raise ValueError("Invalid username or password")

        token = secrets.token_urlsafe(32)
        sess_file = _read_json(_sessions_path(), {"sessions": {}})
        sessions = _purge_sessions(sess_file.get("sessions") or {})
        sessions[token] = {
            "userId": username,
            "displayName": rec.get("displayName") or username,
            "role": rec.get("role") or "investor",
            "createdAt": time.time(),
            "expiresAt": time.time() + SESSION_TTL_SEC,
        }
        sess_file["sessions"] = sessions
        _write_json(_sessions_path(), sess_file)

        return {
            "ok": True,
            "token": token,
            "user": {
                "id": username,
                "displayName": rec.get("displayName") or username,
                "role": rec.get("role") or "investor",
            },
            "expiresInSec": SESSION_TTL_SEC,
            "message": f"Welcome, {rec.get('displayName') or username}",
        }


def logout(token: str | None) -> dict[str, Any]:
    if not token:
        return {"ok": True}
    with _LOCK:
        sess_file = _read_json(_sessions_path(), {"sessions": {}})
        sessions = sess_file.get("sessions") or {}
        sessions.pop(token, None)
        sess_file["sessions"] = sessions
        _write_json(_sessions_path(), sess_file)
    return {"ok": True}


def resolve_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    with _LOCK:
        sess_file = _read_json(_sessions_path(), {"sessions": {}})
        sessions = _purge_sessions(sess_file.get("sessions") or {})
        if sessions != (sess_file.get("sessions") or {}):
            sess_file["sessions"] = sessions
            _write_json(_sessions_path(), sess_file)
        row = sessions.get(token)
        if not row:
            return None
        return {
            "token": token,
            "userId": row["userId"],
            "displayName": row.get("displayName") or row["userId"],
            "role": row.get("role") or "investor",
        }


def require_user(token: str | None) -> dict[str, Any]:
    u = resolve_session(token)
    if not u:
        raise PermissionError("Login required")
    return u


def get_sheet(user: dict[str, Any]) -> dict[str, Any]:
    sheet = ensure_sheet()
    return {
        "ok": True,
        "sheet": sheet,
        "user": {"id": user["userId"], "displayName": user["displayName"], "role": user["role"]},
    }


def save_sheet(user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Replace columns and/or rows (full or partial)."""
    with _LOCK:
        sheet = ensure_sheet()
        if "title" in payload and payload["title"] is not None:
            sheet["title"] = str(payload["title"])[:120]
        if "columns" in payload and isinstance(payload["columns"], list):
            cols = []
            for c in payload["columns"]:
                if not isinstance(c, dict):
                    continue
                cols.append(normalize_column(c))
            if not cols:
                raise ValueError("At least one column required")
            # de-dupe ids; force cost columns private
            seen: set[str] = set()
            unique = []
            for c in cols:
                base = c["id"]
                n = 2
                while c["id"] in seen:
                    c["id"] = f"{base}_{n}"
                    n += 1
                seen.add(c["id"])
                if is_cost_column(c):
                    c["visibility"] = "private"
                    c["isCost"] = True
                unique.append(c)
            sheet["columns"] = unique
        if "rows" in payload and isinstance(payload["rows"], list):
            rows = []
            for r in payload["rows"]:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("id") or uuid.uuid4().hex[:12])
                cell = {k: v for k, v in r.items() if k != "id"}
                # coerce nothing heavy — keep JSON-safe
                clean: dict[str, Any] = {"id": rid}
                for k, v in cell.items():
                    if v is None:
                        clean[k] = ""
                    elif isinstance(v, (str, int, float, bool)):
                        clean[k] = v
                    else:
                        clean[k] = str(v)
                rows.append(clean)
            sheet["rows"] = rows
        sheet["updatedAt"] = _utc_now()
        sheet["updatedBy"] = user["userId"]
        _write_json(_sheet_path(), sheet)
        out: dict[str, Any] = {"ok": True, "sheet": sheet, "message": "Ledger saved"}
        # Best-effort web backup (does not fail the save)
        try:
            push_res = maybe_auto_push_after_save()
            if push_res:
                out["webPush"] = push_res
        except Exception as e:  # noqa: BLE001
            out["webPush"] = {"ok": False, "error": str(e)}
        return out


def list_receipts(user: dict[str, Any]) -> dict[str, Any]:
    meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
    items = list(meta.get("items") or [])
    items.sort(key=lambda x: str(x.get("uploadedAt") or ""), reverse=True)
    return {"ok": True, "receipts": items, "count": len(items)}


def save_receipt(
    user: dict[str, Any],
    *,
    filename: str,
    data: bytes,
    content_type: str | None = None,
    note: str = "",
    row_id: str | None = None,
) -> dict[str, Any]:
    if not data:
        raise ValueError("Empty file")
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError(f"File too large (max {MAX_RECEIPT_BYTES // (1024 * 1024)} MB)")

    raw_name = Path(filename or "receipt.bin").name
    safe = re.sub(r"[^\w.\- ()\[\]]+", "_", raw_name)[:120] or "receipt.bin"
    rid = uuid.uuid4().hex[:16]
    stored = f"{rid}_{safe}"
    path = receipts_dir() / stored
    path.write_bytes(data)

    item = {
        "id": rid,
        "originalName": raw_name,
        "storedName": stored,
        "contentType": content_type or "application/octet-stream",
        "size": len(data),
        "note": (note or "")[:500],
        "rowId": (row_id or "")[:40] or None,
        "uploadedBy": user["userId"],
        "uploadedByName": user.get("displayName") or user["userId"],
        "uploadedAt": _utc_now(),
    }
    with _LOCK:
        meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
        items = list(meta.get("items") or [])
        items.insert(0, item)
        meta["items"] = items
        meta["updatedAt"] = _utc_now()
        _write_json(_receipts_meta_path(), meta)
    return {"ok": True, "receipt": item, "message": f"Uploaded {raw_name}"}


def get_receipt_file(receipt_id: str) -> tuple[Path, dict[str, Any]]:
    meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
    item = next((x for x in (meta.get("items") or []) if x.get("id") == receipt_id), None)
    if not item:
        raise FileNotFoundError("Receipt not found")
    path = receipts_dir() / str(item.get("storedName") or "")
    if not path.is_file():
        raise FileNotFoundError("Receipt file missing on disk")
    return path, item


def delete_receipt(user: dict[str, Any], receipt_id: str) -> dict[str, Any]:
    with _LOCK:
        meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
        items = list(meta.get("items") or [])
        item = next((x for x in items if x.get("id") == receipt_id), None)
        if not item:
            raise FileNotFoundError("Receipt not found")
        # both seats may delete (shared ledger)
        path = receipts_dir() / str(item.get("storedName") or "")
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        meta["items"] = [x for x in items if x.get("id") != receipt_id]
        meta["updatedAt"] = _utc_now()
        _write_json(_receipts_meta_path(), meta)
    return {"ok": True, "message": "Receipt deleted", "id": receipt_id}


def update_receipt_meta(
    user: dict[str, Any],
    receipt_id: str,
    *,
    note: str | None = None,
    row_id: str | None = None,
) -> dict[str, Any]:
    with _LOCK:
        meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
        items = list(meta.get("items") or [])
        found = None
        for x in items:
            if x.get("id") == receipt_id:
                if note is not None:
                    x["note"] = str(note)[:500]
                if row_id is not None:
                    x["rowId"] = (str(row_id)[:40] or None)
                x["updatedAt"] = _utc_now()
                x["updatedBy"] = user["userId"]
                found = x
                break
        if not found:
            raise FileNotFoundError("Receipt not found")
        meta["items"] = items
        _write_json(_receipts_meta_path(), meta)
        return {"ok": True, "receipt": found}


def export_sheet_csv() -> str:
    sheet = ensure_sheet()
    cols = sheet.get("columns") or []
    rows = sheet.get("rows") or []
    headers = ["id"] + [c.get("id") for c in cols]
    lines = [",".join(_csv_escape(h) for h in headers)]
    for r in rows:
        lines.append(",".join(_csv_escape(r.get(h, "")) for h in headers))
    return "\n".join(lines) + "\n"


def _csv_escape(v: Any) -> str:
    s = "" if v is None else str(v)
    if any(c in s for c in ',"\n\r'):
        return '"' + s.replace('"', '""') + '"'
    return s


# --- Web sync (toolbox ↔ website backup) ------------------------------------
# Contract the public site can implement later:
#   GET  {remoteUrl}/bundle   Authorization: Bearer {remoteToken}
#        → { schema, updatedAt, sheet, receipts }
#   PUT  {remoteUrl}/bundle   same body  (website stores as backup)
# Receipts: metadata sync always; binary files optional (includeFiles=true).
# Toolbox pulls on open when online, or at least every intervalHours (default 8).

DEFAULT_SYNC_INTERVAL_HOURS = 8


def _sync_path() -> Path:
    return root_dir() / "sync.json"


def default_sync_config() -> dict[str, Any]:
    """
    Dual-channel sync to FAFO Petro:
      publicUrl  → inventory without costs (OK if world-readable)
      privateUrl → full ledger + costs (Sumran private page; requires token)
    Legacy single remoteUrl maps to private channel.
    """
    return {
        "schema": SCHEMA,
        "enabled": False,
        # FAFO Petro.com — set real paths when the site endpoints go live
        "site": "https://fafopetro.com",
        "publicUrl": "https://fafopetro.com/api/fafo/inventory",
        "privateUrl": "https://fafopetro.com/api/fafo/investor-private",
        "remoteUrl": "",  # legacy alias → privateUrl
        "remoteToken": "",
        "privateToken": "",
        "publicToken": "",  # optional; public inventory usually needs none or publish key
        "pullOnOpen": True,
        "intervalHours": DEFAULT_SYNC_INTERVAL_HOURS,
        "autoPushAfterSave": True,
        "includeReceiptFiles": False,
        "pushPublicInventory": True,
        "pushPrivateLedger": True,
        "stripCostsFromPublic": True,  # always enforce — cannot be disabled by investor seat
        "lastPullAt": None,
        "lastPushAt": None,
        "lastPullOk": None,
        "lastPushOk": None,
        "lastPublicPushAt": None,
        "lastPrivatePushAt": None,
        "lastError": None,
        "lastRemoteUpdatedAt": None,
    }


def get_sync_config(*, include_secret: bool = False) -> dict[str, Any]:
    cfg = default_sync_config()
    stored = _read_json(_sync_path(), None)
    if isinstance(stored, dict):
        cfg.update({k: stored[k] for k in cfg if k in stored})
        for k, v in stored.items():
            if k not in cfg:
                cfg[k] = v
    # always enforce cost strip on public
    cfg["stripCostsFromPublic"] = True
    out = dict(cfg)
    if not include_secret:
        for key in ("remoteToken", "privateToken", "publicToken"):
            tok = str(out.get(key) or "")
            out[key + "Set"] = bool(tok)
            out[key] = ("••••" + tok[-4:]) if len(tok) > 4 else ("••••" if tok else "")
    return out


def save_sync_config(patch: dict[str, Any], *, actor: str) -> dict[str, Any]:
    if actor != "owner":
        # Sumran can trigger sync but only owner sets remote URL/token
        allowed = {"pullOnOpen", "autoPushAfterSave", "pushPublicInventory"}
        patch = {k: v for k, v in (patch or {}).items() if k in allowed}
    with _LOCK:
        cfg = get_sync_config(include_secret=True)
        if "enabled" in patch:
            cfg["enabled"] = bool(patch["enabled"])
        for url_key in ("remoteUrl", "publicUrl", "privateUrl", "site"):
            if url_key in patch:
                cfg[url_key] = str(patch[url_key] or "").strip().rstrip("/")
        # tokens: empty keeps existing; "-" clears
        for tok_key in ("remoteToken", "privateToken", "publicToken"):
            if tok_key not in patch:
                continue
            val = patch[tok_key]
            if val is None or val == "":
                pass
            elif val == "-":
                cfg[tok_key] = ""
            else:
                cfg[tok_key] = str(val).strip()
        # mirror legacy remote → private
        if cfg.get("remoteUrl") and not cfg.get("privateUrl"):
            cfg["privateUrl"] = cfg["remoteUrl"]
        if cfg.get("remoteToken") and not cfg.get("privateToken"):
            cfg["privateToken"] = cfg["remoteToken"]
        if "pullOnOpen" in patch:
            cfg["pullOnOpen"] = bool(patch["pullOnOpen"])
        if "autoPushAfterSave" in patch:
            cfg["autoPushAfterSave"] = bool(patch["autoPushAfterSave"])
        if "includeReceiptFiles" in patch:
            cfg["includeReceiptFiles"] = bool(patch["includeReceiptFiles"])
        if "pushPublicInventory" in patch:
            cfg["pushPublicInventory"] = bool(patch["pushPublicInventory"])
        if "pushPrivateLedger" in patch:
            cfg["pushPrivateLedger"] = bool(patch["pushPrivateLedger"])
        # stripCostsFromPublic is always True — business rule, not optional
        cfg["stripCostsFromPublic"] = True
        if "intervalHours" in patch:
            try:
                h = float(patch["intervalHours"])
                cfg["intervalHours"] = max(0.25, min(168.0, h))
            except (TypeError, ValueError):
                pass
        cfg["updatedAt"] = _utc_now()
        _write_json(_sync_path(), cfg)
        return get_sync_config(include_secret=False)


def build_bundle(*, include_files: bool = False, public_only: bool = False) -> dict[str, Any]:
    """
    Full private bundle (default) or public inventory (costs stripped).
    public_only=True → safe for FAFO Petro public pages / unauthenticated inventory.
    """
    sheet = ensure_sheet()
    if public_only:
        pub = sanitize_sheet_public(sheet)
        return {
            "schema": SCHEMA,
            "kind": "fafo-public-inventory",
            "site": "fafopetro.com",
            "exportedAt": _utc_now(),
            "updatedAt": sheet.get("updatedAt") or _utc_now(),
            "sheet": pub,
            "privacy": pub.get("privacy"),
            # never attach receipts or cost data to public bundle
        }

    receipts_meta = _read_json(_receipts_meta_path(), empty_receipts_meta())
    bundle: dict[str, Any] = {
        "schema": SCHEMA,
        "kind": "fafo-investor-bundle-private",
        "site": "fafopetro.com",
        "exportedAt": _utc_now(),
        "updatedAt": sheet.get("updatedAt") or _utc_now(),
        "sheet": sheet,
        "receipts": receipts_meta,
        "privacy": {
            "includesCosts": True,
            "audience": "owner+sumran private page only",
            "note": "Do not expose this bundle on public FAFO Petro routes.",
        },
    }
    if include_files:
        files = []
        for item in receipts_meta.get("items") or []:
            path = receipts_dir() / str(item.get("storedName") or "")
            if not path.is_file():
                continue
            import base64

            raw = path.read_bytes()
            if len(raw) > MAX_RECEIPT_BYTES:
                continue
            files.append(
                {
                    "id": item.get("id"),
                    "storedName": item.get("storedName"),
                    "originalName": item.get("originalName"),
                    "contentType": item.get("contentType"),
                    "dataBase64": base64.b64encode(raw).decode("ascii"),
                }
            )
        bundle["receiptFiles"] = files
    return bundle


def apply_bundle(bundle: dict[str, Any], *, source: str = "remote") -> dict[str, Any]:
    """Merge remote/local backup into this PC vault (last-write-wins by sheet.updatedAt)."""
    if not isinstance(bundle, dict):
        raise ValueError("Invalid bundle")
    remote_sheet = bundle.get("sheet")
    if not isinstance(remote_sheet, dict):
        raise ValueError("Bundle missing sheet")

    with _LOCK:
        local = ensure_sheet()
        local_ts = str(local.get("updatedAt") or "")
        remote_ts = str(remote_sheet.get("updatedAt") or bundle.get("updatedAt") or "")
        applied_sheet = False
        if remote_ts >= local_ts or not local.get("rows"):
            # accept remote sheet
            sheet = {
                "schema": SCHEMA,
                "title": remote_sheet.get("title") or local.get("title") or "FAFO Investor Ledger",
                "updatedAt": remote_ts or _utc_now(),
                "updatedBy": remote_sheet.get("updatedBy") or source,
                "columns": remote_sheet.get("columns") or local.get("columns") or default_columns(),
                "rows": remote_sheet.get("rows") if isinstance(remote_sheet.get("rows"), list) else local.get("rows") or [],
            }
            _write_json(_sheet_path(), sheet)
            applied_sheet = True
        else:
            sheet = local

        # merge receipts by id (prefer newer uploadedAt)
        remote_rc = bundle.get("receipts") if isinstance(bundle.get("receipts"), dict) else {}
        local_rc = _read_json(_receipts_meta_path(), empty_receipts_meta())
        by_id: dict[str, dict[str, Any]] = {}
        for it in local_rc.get("items") or []:
            if it.get("id"):
                by_id[str(it["id"])] = it
        for it in remote_rc.get("items") or []:
            if not it.get("id"):
                continue
            rid = str(it["id"])
            cur = by_id.get(rid)
            if not cur or str(it.get("uploadedAt") or "") >= str(cur.get("uploadedAt") or ""):
                by_id[rid] = it
        merged = {
            "schema": SCHEMA,
            "items": sorted(by_id.values(), key=lambda x: str(x.get("uploadedAt") or ""), reverse=True),
            "updatedAt": _utc_now(),
        }
        _write_json(_receipts_meta_path(), merged)

        # optional file blobs
        files = bundle.get("receiptFiles") or []
        restored = 0
        if isinstance(files, list):
            import base64

            for f in files:
                if not isinstance(f, dict):
                    continue
                name = str(f.get("storedName") or "")
                b64 = f.get("dataBase64")
                if not name or not b64:
                    continue
                try:
                    raw = base64.b64decode(b64)
                except Exception:  # noqa: BLE001
                    continue
                if len(raw) > MAX_RECEIPT_BYTES:
                    continue
                dest = receipts_dir() / Path(name).name
                if not dest.is_file():
                    dest.write_bytes(raw)
                    restored += 1

        return {
            "ok": True,
            "appliedSheet": applied_sheet,
            "localSheetUpdatedAt": local_ts,
            "remoteSheetUpdatedAt": remote_ts,
            "receiptCount": len(merged["items"]),
            "filesRestored": restored,
            "sheet": sheet,
        }


def _http_json(
    method: str,
    url: str,
    *,
    token: str = "",
    body: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Minimal HTTPS client (stdlib) for web backup."""
    import urllib.error
    import urllib.request

    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "FAFO-InvestorPortal/1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {"ok": True, "status": resp.status}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {"ok": True, "status": resp.status, "raw": raw[:500]}
            if isinstance(parsed, dict):
                parsed.setdefault("ok", True)
                parsed["status"] = resp.status
                return parsed
            return {"ok": True, "status": resp.status, "data": parsed}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {e.code}: {err_body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def _hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        s = str(iso).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
    except ValueError:
        return None


def should_auto_pull(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or get_sync_config(include_secret=True)
    if not cfg.get("enabled") or not cfg.get("remoteUrl"):
        return False
    if cfg.get("pullOnOpen"):
        # still honor interval so we don't thrash on every tab flick
        hours = _hours_since(cfg.get("lastPullAt"))
        interval = float(cfg.get("intervalHours") or DEFAULT_SYNC_INTERVAL_HOURS)
        if hours is None:
            return True
        return hours >= min(interval, 0.05)  # at least ~3 min if interval tiny; pullOnOpen uses full interval
    hours = _hours_since(cfg.get("lastPullAt"))
    interval = float(cfg.get("intervalHours") or DEFAULT_SYNC_INTERVAL_HOURS)
    if hours is None:
        return True
    return hours >= interval


def pull_from_web(*, force: bool = False) -> dict[str, Any]:
    """Pull full private ledger from FAFO Petro private endpoint (costs included)."""
    cfg = get_sync_config(include_secret=True)
    if not cfg.get("enabled"):
        return {"ok": False, "skipped": True, "reason": "sync disabled"}
    base = _private_base_url(cfg)
    if not base:
        return {"ok": False, "skipped": True, "reason": "no privateUrl configured"}
    if not force and not should_auto_pull(cfg):
        return {
            "ok": True,
            "skipped": True,
            "reason": "within interval",
            "lastPullAt": cfg.get("lastPullAt"),
            "intervalHours": cfg.get("intervalHours"),
        }

    url = base if base.endswith("/bundle") else base.rstrip("/") + "/bundle"
    try:
        remote = _http_json("GET", url, token=_private_token(cfg))
        # allow envelope { bundle: {...} } or bare bundle
        bundle = remote.get("bundle") if isinstance(remote.get("bundle"), dict) else remote
        if "sheet" not in bundle:
            raise RuntimeError("Remote response missing sheet (is FAFO Petro private endpoint live?)")
        # Never apply a "public" sanitized sheet as full local (would wipe costs)
        if bundle.get("kind") == "fafo-public-inventory" or (bundle.get("sheet") or {}).get("kind") == "fafo-public-inventory":
            raise RuntimeError(
                "Refusing to pull public inventory into private vault "
                "(would not include costs). Use privateUrl for full ledger."
            )
        result = apply_bundle(bundle, source="web-private")
        with _LOCK:
            cfg2 = get_sync_config(include_secret=True)
            cfg2["lastPullAt"] = _utc_now()
            cfg2["lastPullOk"] = True
            cfg2["lastError"] = None
            cfg2["lastRemoteUpdatedAt"] = bundle.get("updatedAt") or (bundle.get("sheet") or {}).get("updatedAt")
            _write_json(_sync_path(), cfg2)
        return {
            "ok": True,
            "pulled": True,
            "message": "Pulled private ledger from FAFO Petro (includes costs)",
            **result,
            "sync": get_sync_config(include_secret=False),
        }
    except Exception as e:  # noqa: BLE001
        with _LOCK:
            cfg2 = get_sync_config(include_secret=True)
            cfg2["lastPullOk"] = False
            cfg2["lastError"] = str(e)[:300]
            cfg2["lastPullAt"] = _utc_now()
            _write_json(_sync_path(), cfg2)
        return {
            "ok": False,
            "pulled": False,
            "error": str(e),
            "sync": get_sync_config(include_secret=False),
        }


def _private_base_url(cfg: dict[str, Any]) -> str:
    return str(cfg.get("privateUrl") or cfg.get("remoteUrl") or "").rstrip("/")


def _public_base_url(cfg: dict[str, Any]) -> str:
    return str(cfg.get("publicUrl") or "").rstrip("/")


def _private_token(cfg: dict[str, Any]) -> str:
    return str(cfg.get("privateToken") or cfg.get("remoteToken") or "")


def push_to_web(*, force: bool = False) -> dict[str, Any]:
    """
    Push two channels when enabled:
      1) PUBLIC inventory → FAFO Petro (costs stripped always)
      2) PRIVATE full ledger → Sumran private page (token required)
    """
    cfg = get_sync_config(include_secret=True)
    if not cfg.get("enabled"):
        return {"ok": False, "skipped": True, "reason": "sync disabled"}

    results: dict[str, Any] = {"ok": True, "pushed": False, "channels": {}}
    errors: list[str] = []

    # --- Public inventory (no costs) ---
    pub_base = _public_base_url(cfg)
    if cfg.get("pushPublicInventory", True) and pub_base:
        pub_url = pub_base if pub_base.endswith("/bundle") else pub_base.rstrip("/") + "/bundle"
        # Always strip costs — stripCostsFromPublic cannot be turned off
        pub_bundle = build_bundle(public_only=True)
        # belt-and-suspenders: re-scan for cost keys
        for row in (pub_bundle.get("sheet") or {}).get("rows") or []:
            for bad in list(row.keys()):
                if is_cost_column(bad):
                    row.pop(bad, None)
        try:
            remote = _http_json(
                "PUT",
                pub_url,
                token=str(cfg.get("publicToken") or ""),
                body=pub_bundle,
            )
            results["channels"]["public"] = {
                "ok": True,
                "url": pub_url,
                "costsIncluded": False,
                "rowCount": len((pub_bundle.get("sheet") or {}).get("rows") or []),
                "remote": {k: remote.get(k) for k in ("ok", "status", "message") if k in remote},
            }
            results["pushed"] = True
            with _LOCK:
                cfg2 = get_sync_config(include_secret=True)
                cfg2["lastPublicPushAt"] = _utc_now()
                _write_json(_sync_path(), cfg2)
        except Exception as e:  # noqa: BLE001
            errors.append(f"public: {e}")
            results["channels"]["public"] = {"ok": False, "error": str(e), "costsIncluded": False}

    # --- Private full ledger (includes costs) ---
    priv_base = _private_base_url(cfg)
    if cfg.get("pushPrivateLedger", True) and priv_base:
        priv_url = priv_base if priv_base.endswith("/bundle") else priv_base.rstrip("/") + "/bundle"
        priv_bundle = build_bundle(include_files=bool(cfg.get("includeReceiptFiles")), public_only=False)
        try:
            remote = _http_json(
                "PUT",
                priv_url,
                token=_private_token(cfg),
                body=priv_bundle,
            )
            results["channels"]["private"] = {
                "ok": True,
                "url": priv_url,
                "costsIncluded": True,
                "audience": "Sumran private page only",
                "remote": {k: remote.get(k) for k in ("ok", "status", "message") if k in remote},
            }
            results["pushed"] = True
            with _LOCK:
                cfg2 = get_sync_config(include_secret=True)
                cfg2["lastPrivatePushAt"] = _utc_now()
                _write_json(_sync_path(), cfg2)
        except Exception as e:  # noqa: BLE001
            errors.append(f"private: {e}")
            results["channels"]["private"] = {"ok": False, "error": str(e), "costsIncluded": True}

    if not pub_base and not priv_base:
        return {
            "ok": False,
            "skipped": True,
            "reason": "no publicUrl/privateUrl configured (set FAFO Petro endpoints)",
            "sync": get_sync_config(include_secret=False),
        }

    with _LOCK:
        cfg2 = get_sync_config(include_secret=True)
        cfg2["lastPushAt"] = _utc_now()
        cfg2["lastPushOk"] = not errors
        cfg2["lastError"] = "; ".join(errors)[:300] if errors else None
        _write_json(_sync_path(), cfg2)

    results["ok"] = not errors
    results["error"] = "; ".join(errors) if errors else None
    results["message"] = (
        "Pushed to FAFO Petro (public inventory without costs"
        + ("; private ledger with costs" if results["channels"].get("private", {}).get("ok") else "")
        + ")"
        if results["pushed"]
        else "Push failed"
    )
    results["sync"] = get_sync_config(include_secret=False)
    results["privacyNote"] = (
        "Public channel never includes our cost / COGS. "
        "Private channel is for Sumran’s logged-in page only."
    )
    return results


def sync_on_open() -> dict[str, Any]:
    """Called when portal loads — pull if due (online + interval / pullOnOpen)."""
    cfg = get_sync_config(include_secret=True)
    if not cfg.get("enabled") or not cfg.get("remoteUrl"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "web sync not configured (local-only mode)",
            "sync": get_sync_config(include_secret=False),
        }
    return pull_from_web(force=False)


def maybe_auto_push_after_save() -> dict[str, Any] | None:
    cfg = get_sync_config(include_secret=True)
    if cfg.get("enabled") and cfg.get("autoPushAfterSave") and cfg.get("remoteUrl"):
        return push_to_web(force=True)
    return None
