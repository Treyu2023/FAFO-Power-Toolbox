# DIR: Xero token proxy implementation (loopback + FAFO.Secrets)

- **Status:** DONE
- **Priority:** P1
- **Owner (expert):** Grok.com + Owner (supply Client ID/Secret when ready)
- **Executor:** local Grok Build Hands
- **Created:** 2026-08-02
- **Goal:** Implement design in `docs/XERO-TOKEN-PROXY-DESIGN.md`: browser-safe OAuth code exchange and Accounting read proxy on `127.0.0.87`, secrets in DPAPI/FAFO.Secrets only.

## Context
DIR-0045 shipped design only. Owner selected menu C after B (Takeout). Credentials are Owner-supplied at runtime (not in git/chat).

## Tasks (ordered)
1. Implement `server/xero_ops.py` (env → DPAPI secret load, token exchange, refresh, tenants, accounts, transactions).
2. Wire `/api/xero/*` on `aitoolbox_server.py`.
3. LedgerLink UI: store secret, exchange pending code, live sync, proxy status (presence only).
4. Never return access/refresh/client_secret to browser.

## Acceptance checks
- [x] `/api/xero/status` presence-only fields
- [x] Secret store via DPAPI path shared with FAFO.Secrets
- [x] Token exchange + refresh implemented
- [x] Accounts + transactions proxy normalize for TaxForge storage
- [x] LedgerLink wired; disconnect clears session/refresh
- [x] No secrets in git

## Result

- **Status:** DONE
- **Completed:** 2026-08-02
- **Summary:** Live Xero read path ready once Owner stores Client Secret and completes OAuth. Tokens never leave the server process / DPAPI store.
- **Files:** `server/xero_ops.py`, `server/aitoolbox_server.py` routes, LedgerLink Console + `TaxForge.xeroProxy`, design doc status updated.
- **Owner action:** Create Xero Developer app → paste Client ID in LedgerLink → Store secret → Start OAuth → Exchange code via proxy → Sync.
- **Blockers:** None in code. Live success requires Owner credentials + running toolbox server.
