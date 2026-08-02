"""
Xero token proxy ops — loopback-only token exchange + Accounting API read path.

Secrets: process env → DPAPI under %LOCALAPPDATA%\\FAFO\\Secrets\\ (same family as FAFO.Secrets).
Never return client_secret, refresh_token, or access_token to browser clients.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Reuse DPAPI helpers from security_scan (same FAFO Secrets directory layout)
from security_scan import (
    FAFO_SECRETS_DIR,
    _read_dpapi_secret,
    _write_dpapi_secret,
    _secret_path,
)

TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"
API_BASE = "https://api.xero.com/api.xro/2.0"

SECRET_CLIENT_SECRET = "xero.client_secret"
SECRET_REFRESH = "xero.refresh_token"
ENV_CLIENT_SECRET = "XERO_CLIENT_SECRET"
ENV_REFRESH = "XERO_REFRESH_TOKEN"
ENV_CLIENT_ID = "XERO_CLIENT_ID"

# Non-secret local config (client id, redirect, tenant)
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "FAFO" / "Xero"
CONFIG_FILE = CONFIG_DIR / "proxy_config.json"

_lock = threading.Lock()
_memory: dict[str, Any] = {
    "access_token": None,
    "expires_at": 0.0,  # epoch seconds
    "token_type": "Bearer",
    "last_error": None,
    "tenant_id": None,
    "tenants": [],
}


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_config() -> dict[str, Any]:
    if CONFIG_FILE.is_file():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.pop("clientSecret", None)
                data.pop("client_secret", None)
                data.pop("refresh_token", None)
                data.pop("access_token", None)
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"clientId": "", "redirectUri": "", "tenantId": ""}


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    safe = {
        "clientId": str(cfg.get("clientId") or ""),
        "redirectUri": str(cfg.get("redirectUri") or ""),
        "tenantId": str(cfg.get("tenantId") or ""),
        "updatedAt": _utc_now_iso(),
    }
    CONFIG_FILE.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")


def _get_secret(name: str, env_name: str) -> str:
    env_val = (os.environ.get(env_name) or "").strip()
    if env_val:
        return env_val
    return (_read_dpapi_secret(name) or "").strip()


def _set_secret(name: str, env_name: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        path = _secret_path(name)
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        os.environ.pop(env_name, None)
        return
    _write_dpapi_secret(name, value)
    os.environ[env_name] = value


def has_client_secret() -> bool:
    return bool(_get_secret(SECRET_CLIENT_SECRET, ENV_CLIENT_SECRET))


def has_refresh_token() -> bool:
    return bool(_get_secret(SECRET_REFRESH, ENV_REFRESH))


def status() -> dict[str, Any]:
    with _lock:
        exp = _memory.get("expires_at") or 0
        connected = bool(_memory.get("access_token")) and exp > time.time() + 30
        if not connected and has_refresh_token():
            connected = True  # can re-mint
        return {
            "ok": True,
            "connected": connected,
            "hasClientSecret": has_client_secret(),
            "hasRefreshToken": has_refresh_token(),
            "hasAccessToken": bool(_memory.get("access_token")),
            "tenantId": _memory.get("tenant_id") or _load_config().get("tenantId") or None,
            "tenantCount": len(_memory.get("tenants") or []),
            "expiresAt": int(exp) if exp else None,
            "lastError": _memory.get("last_error"),
            "secretsDir": str(FAFO_SECRETS_DIR),
            "bindHint": "loopback proxy — never returns secrets/tokens to browser",
        }


def save_public_config(client_id: str, redirect_uri: str) -> dict[str, Any]:
    cfg = _load_config()
    if client_id is not None:
        cfg["clientId"] = str(client_id or "").strip()
    if redirect_uri is not None:
        cfg["redirectUri"] = str(redirect_uri or "").strip()
    if client_id:
        os.environ[ENV_CLIENT_ID] = cfg["clientId"]
    _save_config(cfg)
    return {"ok": True, "hasClientId": bool(cfg.get("clientId"))}


def store_client_secret(client_secret: str) -> dict[str, Any]:
    _set_secret(SECRET_CLIENT_SECRET, ENV_CLIENT_SECRET, client_secret)
    return {"ok": True, "has_client_secret": has_client_secret()}


def _form_post(url: str, data: dict[str, str], basic_auth: tuple[str, str] | None = None) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if basic_auth:
        import base64

        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Xero token HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Xero token network error: {e.reason}") from e


def _api_get(path: str, access_token: str, tenant_id: str, query: dict[str, str] | None = None) -> Any:
    q = ("?" + urllib.parse.urlencode(query)) if query else ""
    url = API_BASE + path + q
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Xero-tenant-id", tenant_id)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Xero API HTTP {e.code}: {err_body}") from e


def _store_token_response(tok: dict[str, Any]) -> int:
    access = tok.get("access_token")
    refresh = tok.get("refresh_token")
    expires_in = int(tok.get("expires_in") or 1800)
    if not access:
        raise RuntimeError("Token response missing access_token")
    with _lock:
        _memory["access_token"] = access
        _memory["expires_at"] = time.time() + max(60, expires_in - 60)
        _memory["token_type"] = tok.get("token_type") or "Bearer"
        _memory["last_error"] = None
    if refresh:
        _set_secret(SECRET_REFRESH, ENV_REFRESH, str(refresh))
    return expires_in


def _fetch_connections(access_token: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(CONNECTIONS_URL, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Connections HTTP {e.code}: {err_body}") from e
    if not isinstance(data, list):
        return []
    tenants = []
    for c in data:
        if not isinstance(c, dict):
            continue
        tenants.append({
            "tenantId": c.get("tenantId"),
            "tenantName": c.get("tenantName") or c.get("tenantType"),
            "tenantType": c.get("tenantType"),
        })
    with _lock:
        _memory["tenants"] = tenants
        if tenants and not _memory.get("tenant_id"):
            _memory["tenant_id"] = tenants[0].get("tenantId")
            cfg = _load_config()
            cfg["tenantId"] = _memory["tenant_id"] or ""
            _save_config(cfg)
    return tenants


def exchange_code(code: str, redirect_uri: str, client_id: str) -> dict[str, Any]:
    code = (code or "").strip()
    if not code:
        raise ValueError("Authorization code required")
    cfg = _load_config()
    cid = (client_id or cfg.get("clientId") or os.environ.get(ENV_CLIENT_ID) or "").strip()
    redir = (redirect_uri or cfg.get("redirectUri") or "").strip()
    secret = _get_secret(SECRET_CLIENT_SECRET, ENV_CLIENT_SECRET)
    if not cid:
        raise ValueError("Client ID required")
    if not secret:
        raise ValueError("Client secret not stored — POST /api/xero/secrets first")
    if not redir:
        raise ValueError("redirect_uri required")

    if cid:
        save_public_config(cid, redir)

    try:
        tok = _form_post(
            TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redir,
            },
            basic_auth=(cid, secret),
        )
        expires_in = _store_token_response(tok)
        with _lock:
            access = _memory["access_token"]
        tenants = _fetch_connections(access) if access else []
        return {
            "ok": True,
            "expiresIn": expires_in,
            "tenantCount": len(tenants),
            "tenantId": (_memory.get("tenant_id") if tenants else None),
        }
    except Exception as e:
        with _lock:
            _memory["last_error"] = str(e)[:300]
        raise


def refresh_access() -> dict[str, Any]:
    cfg = _load_config()
    cid = (cfg.get("clientId") or os.environ.get(ENV_CLIENT_ID) or "").strip()
    secret = _get_secret(SECRET_CLIENT_SECRET, ENV_CLIENT_SECRET)
    refresh = _get_secret(SECRET_REFRESH, ENV_REFRESH)
    if not cid or not secret:
        raise ValueError("Client ID and client secret required to refresh")
    if not refresh:
        raise ValueError("No refresh token stored")
    try:
        tok = _form_post(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            basic_auth=(cid, secret),
        )
        expires_in = _store_token_response(tok)
        return {"ok": True, "expiresIn": expires_in}
    except Exception as e:
        with _lock:
            _memory["last_error"] = str(e)[:300]
        raise


def clear_session(purge_secrets: bool = False) -> dict[str, Any]:
    with _lock:
        _memory["access_token"] = None
        _memory["expires_at"] = 0.0
        _memory["tenants"] = []
        _memory["tenant_id"] = None
        _memory["last_error"] = None
    if purge_secrets:
        _set_secret(SECRET_REFRESH, ENV_REFRESH, "")
        # do not auto-purge client_secret unless explicitly requested via purgeSecrets=1
        # Owner may want to reconnect; still purge refresh only by default
        # purgeSecrets=1 also clears client secret
        _set_secret(SECRET_CLIENT_SECRET, ENV_CLIENT_SECRET, "")
    else:
        _set_secret(SECRET_REFRESH, ENV_REFRESH, "")
    return {"ok": True, "purgedSecrets": bool(purge_secrets)}


def list_tenants() -> list[dict[str, Any]]:
    access = _ensure_access()
    return _fetch_connections(access)


def select_tenant(tenant_id: str) -> dict[str, Any]:
    tid = (tenant_id or "").strip()
    if not tid:
        raise ValueError("tenantId required")
    with _lock:
        _memory["tenant_id"] = tid
    cfg = _load_config()
    cfg["tenantId"] = tid
    _save_config(cfg)
    return {"ok": True, "tenantId": tid}


def _ensure_access() -> str:
    with _lock:
        access = _memory.get("access_token")
        exp = _memory.get("expires_at") or 0
    if access and exp > time.time() + 30:
        return access
    if has_refresh_token():
        refresh_access()
        with _lock:
            access = _memory.get("access_token")
        if access:
            return access
    raise RuntimeError("Not connected — complete OAuth token exchange first")


def _active_tenant() -> str:
    with _lock:
        tid = _memory.get("tenant_id")
    if not tid:
        tid = _load_config().get("tenantId")
    if not tid:
        tenants = list_tenants()
        if tenants:
            tid = tenants[0].get("tenantId")
            select_tenant(str(tid))
    if not tid:
        raise RuntimeError("No Xero tenant selected")
    return str(tid)


def get_accounts() -> dict[str, Any]:
    access = _ensure_access()
    tenant = _active_tenant()
    data = _api_get("/Accounts", access, tenant)
    accounts_raw = data.get("Accounts") if isinstance(data, dict) else []
    out = []
    for a in accounts_raw or []:
        if not isinstance(a, dict):
            continue
        out.append({
            "code": a.get("Code") or "",
            "name": a.get("Name") or "",
            "type": a.get("Type") or "",
            "taxType": a.get("TaxType") or "NONE",
            "class": a.get("Class") or a.get("Type") or "",
            "status": a.get("Status") or "",
        })
    return {"ok": True, "accounts": out, "count": len(out)}


def get_transactions(from_date: str | None = None, to_date: str | None = None, page: int = 1) -> dict[str, Any]:
    """
    Pull bank transactions (read scope). Normalize to TaxForge transaction shape.
    """
    access = _ensure_access()
    tenant = _active_tenant()
    query: dict[str, str] = {"page": str(max(1, int(page or 1)))}
    # Xero where clause for dates if provided
    clauses = []
    if from_date:
        clauses.append(f'Date >= DateTime({from_date.replace("-", ", ")})')
    if to_date:
        clauses.append(f'Date <= DateTime({to_date.replace("-", ", ")})')
    if clauses:
        query["where"] = " && ".join(clauses)

    try:
        data = _api_get("/BankTransactions", access, tenant, query)
    except RuntimeError:
        # Fallback: Invoices as spend signals if bank txns fail
        data = _api_get("/Invoices", access, tenant, {"page": query["page"]})
        inv = data.get("Invoices") if isinstance(data, dict) else []
        rows = []
        for inv_row in inv or []:
            if not isinstance(inv_row, dict):
                continue
            total = abs(float(inv_row.get("Total") or 0))
            if not total:
                continue
            contact = (inv_row.get("Contact") or {}).get("Name") if isinstance(inv_row.get("Contact"), dict) else "Contact"
            rows.append({
                "id": "xero-inv-" + str(inv_row.get("InvoiceID") or ""),
                "date": str(inv_row.get("DateString") or inv_row.get("Date") or "")[:10],
                "contact": contact or "Contact",
                "description": inv_row.get("Reference") or inv_row.get("Type") or "Invoice",
                "accountCode": "",
                "accountName": "Uncategorized",
                "amount": total,
                "tax": abs(float(inv_row.get("TotalTax") or 0)),
                "status": "needs-review",
                "deductible": "unknown",
                "source": "xero-invoice",
            })
        return {"ok": True, "transactions": rows, "count": len(rows), "source": "invoices"}

    btx = data.get("BankTransactions") if isinstance(data, dict) else []
    rows = []
    for t in btx or []:
        if not isinstance(t, dict):
            continue
        total = abs(float(t.get("Total") or 0))
        if not total:
            continue
        contact = (t.get("Contact") or {}).get("Name") if isinstance(t.get("Contact"), dict) else "Bank"
        lines = t.get("LineItems") or []
        code = ""
        name = t.get("Type") or "Bank transaction"
        if lines and isinstance(lines[0], dict):
            code = str(lines[0].get("AccountCode") or "")
            name = lines[0].get("Description") or name
        rows.append({
            "id": "xero-bt-" + str(t.get("BankTransactionID") or ""),
            "date": str(t.get("DateString") or t.get("Date") or "")[:10],
            "contact": contact or "Bank",
            "description": name,
            "accountCode": code,
            "accountName": name if code else "Uncategorized",
            "amount": total,
            "tax": abs(float(t.get("TotalTax") or 0)),
            "status": "coded" if code else "needs-review",
            "deductible": "likely" if code else "unknown",
            "source": "xero-bank",
        })
    return {"ok": True, "transactions": rows, "count": len(rows), "source": "bank_transactions"}
