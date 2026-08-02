# DIR: TaxForge — 2026 mileage automation, quarterly SE estimates, Xero proxy design

- **Status:** DONE
- **Priority:** P1
- **Owner (expert):** Grok.com expert team (Lucas / Harper / Benjamin / Grok)
- **Executor:** local Grok agent (hands)
- **Created:** 2026-08-02
- **Goal:** Extend existing TaxForge suite so FAFO Petro LLC tax prep (mileage, quarterly estimates, Xero readiness) is faster and more automated without inventing tax advice or storing secrets in the repo.

## Context
Hands already shipped TaxForge (Hub, LedgerLink Console with Xero/CSV/OAuth scaffold, Compliance Pulse, Write-Off Workshop, Year-End War Room). Owner wants automation for business taxes with Xero. Build on existing code; do not create a parallel dashboard.

2026 IRS business mileage rates: 72.5¢/mi (Jan–Jun), 76¢/mi (Jul–Dec). SE tax 15.3% on 92.35% of net earnings; Social Security wage base $184,500 for 2026. Quarterly estimated tax deadlines: Apr 15, Jun 15, Sep 15, Jan 15.

## Constraints
- Follow AGENTS.md strictly (FAFO.Secrets for any credentials, no secrets in git, loopback only)
- UI must match taxforge-shared.css / existing dark cyan / suite style
- “This is not tax, legal, or accounting advice — for preparedness and bookkeeping support only” disclaimers where calculated numbers appear
- Small, reversible diffs; prefer extending taxforge-shared.js and existing apps (LedgerLink, Write-Off, Compliance Pulse, Hub)
- No live production Xero API calls that require Owner secrets until Owner supplies them and a follow-on DIR authorizes implementation

## Tasks (ordered)
1. Inspect current LedgerLink Console.html, Write-Off Workshop.html, taxforge-shared.js/css and note the current Xero/CSV/OAuth/demo state briefly in the Result section.
2. Add a Mileage Import panel (prefer LedgerLink Console or Write-Off Workshop): file picker for MileIQ-style CSV, parse date/miles (and purpose if present), apply the correct 2026 IRS rate by date half-year, show preview total + line list, buttons for “Stage for Xero / Export CSV” (demo staging is fine if no live API yet).
3. Add a Quarterly Estimated Tax card (prefer Compliance Pulse, Year-End War Room, or Hub): accept YTD net profit (manual input or from demo/synced data), compute SE tax (15.3% × 92.35%), note remaining SS wage base capacity against $184,500, show rough remaining quarterly amounts and next deadline countdown. Persist last values in localStorage via shared helpers if practical.
4. Create design-only document `docs/XERO-TOKEN-PROXY-DESIGN.md`: sequence for browser OAuth → loopback server on 127.0.0.87 → FAFO.Secrets (client_secret + refresh_token) → Xero token endpoint; list proposed `/api/xero/*` endpoints; no implementation code in this DIR.
5. Update `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md` with the new panels, 2026 rates, and the standard disclaimer.
6. Smoke-check: Hub + modified pages load without console errors; Toolbox Launcher Tax / TaxForge & Books section still points correctly.

## Acceptance checks
- [ ] Mileage CSV import produces correct 2026 rate totals on sample data and shows a usable preview
- [ ] Quarterly card shows SE tax calculation, deadlines, and disclaimer
- [ ] `docs/XERO-TOKEN-PROXY-DESIGN.md` exists and is clear enough for a later implementation DIR
- [ ] TAXFORGE-EXPERT-BRIEF.md updated
- [ ] No secrets committed; AGENTS.md respected
- [ ] HTML still matches suite style and launcher works

## Out of scope
- Full live Xero OAuth code, token exchange, or token storage implementation (design only in this DIR)
- Changing Compliance Pulse scoring weights (file a separate DIR if needed)
- CPA-grade tax optimization, legal advice, or Schedule C line-item invention beyond helpers
- Creating a new top-level launcher section (use existing TaxForge & Books)

## Handoff notes for next expert
After Result lands, the natural follow-on DIR is to implement the proxy endpoints once the Owner has a Xero Developer app (Client ID + Secret) and explicitly authorizes storage via FAFO.Secrets.

---

## Result

- **Status:** DONE
- **Completed:** 2026-08-02
- **Summary:** Extended TaxForge for 2026 mileage automation, quarterly SE estimate card, and design-only Xero token proxy doc. No live Xero API; no secrets.

### Task 1 — Inspect (pre-change state)

| Area | State found |
|------|-------------|
| **LedgerLink** | Demo org, chart of accounts, bank/Xero CSV import, OAuth Client ID + authorize URL, pending auth-code capture in localStorage; no token exchange |
| **Write-Off Workshop** | Triage queue over shared `taxforge.transactions`; keyword auto-suggest → Xero-style codes; export review CSV |
| **taxforge-shared.js** | `storage`, FX, demo org/accounts/txns, `parseXeroCsv`, `TaxForge.xero` OAuth scaffold (no secret), suite nav |
| **taxforge-shared.css** | Dark cyan suite tokens, panels, stats, tables, buttons — reused as-is |

### What shipped

1. **Shared helpers** (`taxforge-shared.js`): `TaxForge.mileage` (2026 H1 72.5¢ / H2 76¢, CSV parse, summarize, export), `TaxForge.quarterly` (SE 15.3% × 92.35%, SS base $184,500 note, deadlines, remaining installments), `TaxForge.DISCLAIMER`.
2. **Mileage Import panel** on **LedgerLink Console**: file picker + sample rows, preview table + H1/H2 totals, **Stage for Xero (demo)** (localStorage + summary txn to account 449), **Export deduction CSV**.
3. **Quarterly Estimated Tax card** on **Compliance Pulse**: YTD net / months / paid inputs, SE base & tax, remaining ≈ per installment, next deadline countdown, SS wage-base bar; persists via `taxforge.quarterly.*`.
4. **`docs/XERO-TOKEN-PROXY-DESIGN.md`**: sequence browser → `127.0.0.87` → FAFO.Secrets → Xero; proposed `/api/xero/*` endpoints; security checklist; no implementation code.
5. **`TAXFORGE-EXPERT-BRIEF.md`**: v1.1 notes, 2026 rates table, new panels, disclaimer, design-doc pointer, demo journey steps.

- **Files touched:**
  - `Business Tax Preparedness/taxforge-shared.js`
  - `Business Tax Preparedness/LedgerLink Console.html`
  - `Business Tax Preparedness/Compliance Pulse.html`
  - `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md`
  - `docs/XERO-TOKEN-PROXY-DESIGN.md` (new)
  - `docs/agent-handoff/QUEUE.md`
  - `docs/agent-handoff/LOG.md`
  - this DIR file

- **Verification:**
  - Sample 6-trip 2026 CSV math: H1 $88.23 + H2 $76.61 = **$164.84** total deduction preview (rates applied by date half-year).
  - SE demo (net $52k over 6 mo → annualized $104k): SE base ≈ $96,044; SE tax ≈ $14,694.73.
  - Presence: mileage panel, quarterly card, design doc, brief updates, launcher still maps Tax / TaxForge & Books → Hub + LedgerLink + Pulse paths.
  - Script tag balance OK on Hub, LedgerLink, Compliance Pulse.
  - No client secrets or token material added to repo/HTML.

- **Acceptance checks:**
  - [x] Mileage CSV import produces correct 2026 rate totals on sample data and shows a usable preview
  - [x] Quarterly card shows SE tax calculation, deadlines, and disclaimer
  - [x] `docs/XERO-TOKEN-PROXY-DESIGN.md` exists and is clear enough for a later implementation DIR
  - [x] TAXFORGE-EXPERT-BRIEF.md updated
  - [x] No secrets committed; AGENTS.md respected
  - [x] HTML still matches suite style and launcher works

- **Blockers:** None. Live Xero remains Owner-credential + follow-on DIR (by design).

- **Suggested next DIR:** Implement `docs/XERO-TOKEN-PROXY-DESIGN.md` (`/api/xero/status|token|refresh|tenants|accounts`) with FAFO.Secrets after Owner supplies Xero Developer Client ID + Secret. Optional parallel: Google Takeout → draft tickets (DIR-20260802-0035, P2 OPEN).
