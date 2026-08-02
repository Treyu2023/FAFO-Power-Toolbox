# Xero token proxy — design (implementation later)

**Status:** Implemented (DIR-20260802 Hands B+C) — see `server/xero_ops.py` + `/api/xero/*`  
**Original design DIR:** DIR-20260802-0045 (design-only). **Impl:** 2026-08-02 Hands session.  
**Bind target:** toolbox loopback `127.0.0.87:18765` (see `shared/aitoolbox-bind.json`)  
**Secrets:** FAFO.Secrets / DPAPI under `%LOCALAPPDATA%\FAFO\Secrets\` — never git, never HTML  

This document is the handoff for a **follow-on implementation DIR**. No proxy code ships with this design package.

---

## Goals

1. Complete Xero OAuth (authorization code → tokens) without putting `client_secret` or refresh/access tokens in the browser repo.
2. Keep all network exchange on **loopback only**.
3. Let TaxForge LedgerLink remain a thin UI: Client ID + redirect + optional tenant selection; server owns secrets and tokens.
4. Align with `AGENTS.md`: presence checks only in logs/UI; load order process env → DPAPI store → empty.

---

## Actors

| Actor | Trust | Holds |
|-------|-------|--------|
| Browser (LedgerLink HTML) | Untrusted for secrets | Xero **Client ID** (public), auth **code** (short-lived), UI state in `localStorage` |
| Loopback server (`server/`) | Trusted local process | **client_secret**, **refresh_token**, access token cache (memory or DPAPI) |
| Xero Identity / API | External | Tokens, tenant connections |
| FAFO.Secrets | OS-bound DPAPI | Secret blobs keyed by name (e.g. `xero.client_secret`, `xero.refresh_token`) |

---

## Sequence: OAuth → tokens → API

```
User                LedgerLink (browser)         Loopback :18765           FAFO.Secrets          Xero
 │                        │                            │                       │                  │
 │  Save Client ID        │                            │                       │                  │
 │───────────────────────>│                            │                       │                  │
 │  Start OAuth           │                            │                       │                  │
 │───────────────────────>│  redirect authorize URL    │                       │                  │
 │                        │───────────────────────────────────────────────────────────────────────>│
 │  Login / consent        │                            │                       │                  │
 │<───────────────────────────────────────────────────────────────────────────────────────────────│
 │  redirect?code&state   │                            │                       │                  │
 │───────────────────────>│  POST /api/xero/token      │                       │                  │
 │                        │  { code, redirect_uri,     │                       │                  │
 │                        │    client_id }             │                       │                  │
 │                        │───────────────────────────>│  Get-FAFOSecret       │                  │
 │                        │                            │  xero.client_secret   │                  │
 │                        │                            │──────────────────────>│                  │
 │                        │                            │<──────────────────────│                  │
 │                        │                            │  token exchange                            │
 │                        │                            │  (client_id+secret+code)──────────────────>│
 │                        │                            │<─ access + refresh ───────────────────────│
 │                        │                            │  Set-FAFOSecret                            │
 │                        │                            │  xero.refresh_token ──>│                  │
 │                        │  { ok, tenantHint,         │                       │                  │
 │                        │    expiresIn }             │                       │                  │
 │                        │  (no secret/token body)    │                       │                  │
 │                        │<───────────────────────────│                       │                  │
 │  Connected (session)   │                            │                       │                  │
 │<───────────────────────│                            │                       │                  │
 │  Sync accounts/txns    │  GET /api/xero/accounts    │  refresh if needed    │                  │
 │───────────────────────>│───────────────────────────>│───────────────────────┼──────────────────>│
 │                        │<───────────────────────────│<──────────────────────┼──────────────────│
```

**Rules on responses to the browser:**

- Never return `client_secret`, `refresh_token`, or long-lived `access_token` to HTML.
- Prefer opaque session cookie (HttpOnly, Secure optional on loopback, SameSite=Strict) **or** short-lived browser flag `connected: true` while server holds tokens.
- Log only: presence (`has_refresh_token: true`), HTTP status, tenant id (non-secret).

---

## Proposed endpoints (`/api/xero/*`)

All routes: **loopback bind only** (`127.0.0.87`). Reject non-loopback if the stack ever widens.

| Method | Path | Purpose | Body / query | Response (browser-safe) |
|--------|------|---------|--------------|-------------------------|
| `GET` | `/api/xero/status` | Connection health | — | `{ connected, hasClientSecret, hasRefreshToken, tenantId?, expiresAt?, lastError? }` |
| `POST` | `/api/xero/config` | Register public client id + redirect (optional mirror of localStorage) | `{ clientId, redirectUri }` | `{ ok }` |
| `POST` | `/api/xero/secrets` | Store client secret via FAFO.Secrets (Owner action / elevated UI) | `{ clientSecret }` once | `{ ok, has_client_secret: true }` — never echo secret |
| `POST` | `/api/xero/token` | Exchange auth code | `{ code, redirectUri, clientId }` | `{ ok, expiresIn, tenantCount }` |
| `POST` | `/api/xero/refresh` | Force refresh | — | `{ ok, expiresIn }` |
| `DELETE` | `/api/xero/session` | Disconnect: clear memory tokens; optional delete refresh from secrets | `?purgeSecrets=0\|1` | `{ ok }` |
| `GET` | `/api/xero/tenants` | List connections after token | — | `[{ tenantId, tenantName, … }]` |
| `POST` | `/api/xero/tenant` | Select active tenant | `{ tenantId }` | `{ ok }` |
| `GET` | `/api/xero/accounts` | Proxy Accounting API chart of accounts | — | Xero-shaped account list (filtered) |
| `GET` | `/api/xero/transactions` | Proxy bank transactions / invoices (scope TBD) | `?from=&to=&page=` | Normalized rows for TaxForge storage |
| `POST` | `/api/xero/mileage-stage` | **Future:** push staged mileage summary as draft expense (not in first proxy DIR) | staged payload | `{ ok, draftId? }` |

### Token endpoint mapping (server → Xero)

- **Token URL:** `https://identity.xero.com/connect/token`
- **Grant (code):** `grant_type=authorization_code` + `code` + `redirect_uri` + Basic or body `client_id`/`client_secret`
- **Grant (refresh):** `grant_type=refresh_token` + `refresh_token`
- **API base:** `https://api.xero.com/api.xro/2.0` with header `Xero-tenant-id`

Scopes (already scaffolded in `taxforge-shared.js`):  
`openid profile email offline_access accounting.transactions.read accounting.contacts.read accounting.settings.read`  
Write scopes (mileage push) are **out of scope** until a later DIR.

---

## Secret key names (convention)

| FAFO.Secrets name | Content |
|-------------------|---------|
| `xero.client_secret` | Developer app secret |
| `xero.refresh_token` | Latest refresh token |
| Optional: `xero.client_id` | Only if Owner wants server-side source of truth (UI may still hold public id) |

**Load order:** process env (`XERO_CLIENT_SECRET`, etc.) → DPAPI store → empty.  
Do **not** fall back to `server/security_config.json` for the real secret (flags only, e.g. `has_xero_client_secret`).

---

## Browser ↔ server contract (LedgerLink)

Today LedgerLink:

1. Stores Client ID in `taxforge.xero.config` (localStorage).
2. Builds authorize URL; captures `?code=` as `taxforge.xero.pending_code`.
3. Shows “OAuth code captured — exchange via secure backend.”

After proxy implementation:

1. On pending code, `POST /api/xero/token` once; clear pending code from storage.
2. Poll `GET /api/xero/status` for connected state.
3. “Sync” buttons call `/api/xero/accounts` and `/api/xero/transactions`, then write into existing `taxforge.accounts` / `taxforge.transactions` keys so Pulse / Write-Off keep working.

PKCE: recommended for public clients; if Client Secret remains confidential on the server only, confidential-client code flow is acceptable for a **local** Owner-only toolbox. Prefer PKCE + secret on server for defense in depth.

---

## Security checklist (implementation DIR must meet)

- [ ] Bind `127.0.0.87` only (or documented equivalent loopback)
- [ ] No secrets in git, HTML, or expert briefs
- [ ] Token/refresh never logged in full
- [ ] CORS locked to local file / loopback origins as required by the stack
- [ ] Disconnect + optional secret purge
- [ ] Pre-push check still clean (`Invoke-FAFOPrePushCheck.ps1`)
- [ ] No live calls in CI without mocks

---

## Out of scope for first implementation DIR

- Multi-user cloud SaaS Xero app  
- Storing Xero tokens in repo or OneDrive  
- Automatic production tenant selection without Owner click  
- Write APIs (create bills/expenses) until mileage stage DIR  
- Mobile remote access to the proxy  

---

## Acceptance for *this* design package

- [x] Sequence described (browser → loopback → FAFO.Secrets → Xero)  
- [x] Endpoint list proposed  
- [x] No implementation code required in DIR-20260802-0045  

**Suggested next DIR title:** `DIR-…-xero-token-proxy-impl` — implement status/token/refresh/tenants/accounts read path with FAFO.Secrets, after Owner supplies Client ID + Secret and authorizes DPAPI storage.

---

*Design only. Not tax advice. Not a live integration.*
