# TaxForge — Expert Brief for Grok.com / Collaborators

**Product:** TaxForge (Business Tax Preparedness suite)  
**Host platform:** FAFO Power Toolbox / AI HTML Toolbox (local-first)  
**Status:** v1.1 — demo + CSV + OAuth scaffold + mileage import + quarterly SE card + Xero proxy design  
**Audience:** Product, engineering, tax/accounting domain experts, Grok.com partners  
**Date:** 2026-08-02  

**Disclaimer:** This is not tax, legal, or accounting advice — for preparedness and bookkeeping support only.

---

## 30-second pitch

TaxForge is a **local-first “tax season command center”** that sits on top of a business’s books (especially **Xero**). It doesn’t replace a CPA or file returns. It **automates readiness**: connect or import the ledger, score how tax-ready the books are, clean write-offs, and drive year-end close with deadlines, a document vault, and a one-click preparer pack.

Built as **five animated HTML apps** inside an existing power-user toolbox — no cloud SaaS required for the core loop.

---

## Problem

| Pain | Reality for SMBs |
|------|------------------|
| Tax prep is seasonal panic | Books are messy 10 months of the year |
| Tools are fragmented | Xero + receipts + checklists + accountant email threads |
| “Am I ready?” is fuzzy | No single readiness score tied to real ledger hygiene |
| Automation often means SaaS lock-in | Users lose control of data and secrets |
| AI-assisted prep needs clean inputs | Garbage coding → garbage advice |

**Opportunity:** A **preparedness layer** that makes ledgers reviewable *before* AI or a human expert touches them.

---

## What we built

### Suite brand: **TaxForge**
Folder: `Business Tax Preparedness/`  
Launcher section: **TaxForge & Books**

| App | Codename role | What it does |
|-----|---------------|--------------|
| **TaxForge Hub** | Mission control | Animated landing, recommended 4-step flow, suite navigation |
| **LedgerLink Console** | Xero bridge | Demo org, chart of accounts, bank CSV import, OAuth + **loopback token proxy** (`/api/xero/*`, FAFO DPAPI secrets), live sync when connected, **2026 mileage CSV**, **Google Takeout / Timeline placeVisit → draft tickets** |
| **Compliance Pulse** | Readiness engine | Weighted score (coding, checklist, volume, reviews), ECG/ring animation, **quarterly SE estimate card** |
| **Write-Off Workshop** | Deduction forge | Triage uncategorized spend, keyword auto-suggest → Xero accounts, export CSV |
| **Partner Period Desk** | Reimb + investor periods | Bulk reclass misplaced reimbursements, investor parts, profit-share estimates, month/year/fiscal rollups, expert pack export |
| **Year-End War Room** | Close-out ops | Deadline orbit, document vault, kanban tasks, JSON preparer pack |

**Shared layer:** `taxforge-shared.css` + `taxforge-shared.js`  
- LocalStorage namespace `taxforge.*` (apps share org, accounts, transactions, pulse, war-room, mileage, quarterly state)  
- Particle FX, toasts, demo Xero-shaped data, bank CSV parser, OAuth URL builder  
- **Mileage helpers:** 2026 IRS business rates (72.5¢/mi Jan–Jun, 76¢/mi Jul–Dec), MileIQ-style CSV parse, stage/export  
- **Quarterly helpers:** SE tax ≈ 15.3% × 92.35% of net; SS wage base note $184,500 (2026); deadline countdown  

### 2026 reference figures (helpers only — verify with IRS / preparer)

| Item | Value used in UI |
|------|------------------|
| Business standard mileage H1 (Jan 1 – Jun 30) | **72.5¢/mi** |
| Business standard mileage H2 (Jul 1 – Dec 31) | **76¢/mi** |
| SE tax rate (combined) | **15.3%** on **92.35%** of net earnings from self-employment |
| Social Security wage base (capacity note) | **$184,500** |
| Federal estimated tax deadlines (calendar year) | Apr 15, Jun 15, Sep 15, Jan 15 (following year) |

Panels that show calculated dollars include the standard disclaimer:  
*This is not tax, legal, or accounting advice — for preparedness and bookkeeping support only.*

---

## Architecture (honest & security-conscious)

```
[User browser — local HTML tools]
        │
        ├─ Demo mode (instant)
        ├─ CSV import (Xero/bank exports)
        ├─ OAuth authorize → auth code only
        │
        ▼ (design ready — see docs/XERO-TOKEN-PROXY-DESIGN.md)
[Toolbox loopback server 127.0.0.87]
        │  client_secret + refresh via FAFO.Secrets (DPAPI) — never in git/HTML
        │  proposed /api/xero/* (status, token, refresh, tenants, accounts, txns)
        ▼
[Xero API — tenants, accounts, transactions]
```

**Non-negotiables already baked in:**
- No client secrets in frontend or repo  
- OAuth code handoff only; token exchange belongs on loopback backend  
- Local-first: useful offline after first load of static assets  
- Explicit disclaimer: **not tax advice**  
- Xero live token proxy is **design-only** until Owner supplies app credentials and a follow-on DIR

---

## User journey (demo script — ~5 minutes)

1. Open **Toolbox Launcher** → section **TaxForge & Books** → **TaxForge Hub**  
2. **LedgerLink Console** → **Load Demo Org** → see accounts + sync health  
3. Optionally **Seed demo transactions** or import a bank CSV  
4. **Mileage import** → **Load sample rows** or pick a MileIQ-style CSV → preview H1/H2 rates → **Stage for Xero (demo)** or **Export deduction CSV**  
4b. **Location History** → sample or Takeout Semantic JSON → select visits → stage draft tickets (local)  
4c. **Live Xero** (server on) → Store client secret → OAuth → Exchange code via proxy → Sync accounts/txns  
5. **Compliance Pulse** → **Recalculate** → watch score + factors + checklist  
6. **Quarterly estimated tax** card → enter YTD net (or demo figures) → SE tax, remaining installments, next deadline countdown  
7. **Write-Off Workshop** → filter “Needs review” → **Auto-suggest** → **Apply** → export CSV  
8. **Year-End War Room** → check docs, advance kanban tasks, **Download preparer pack**  

**Success moment:** Pulse climbs as coding coverage and checklist improve; preparer pack becomes the artifact you hand an expert (human or Grok).

---

## Why this fits Grok / expert workflows

| Angle | Fit |
|-------|-----|
| **Grounded AI** | Clean, structured local pack (JSON/CSV) before model reasoning |
| **Tool-using agents** | Clear app boundaries: connect → score → classify → close |
| **Privacy** | Books stay on-device until user exports |
| **SMB real-world** | Xero is dominant for many small businesses |
| **Productizable** | Suite pattern can extend (receipts OCR, multi-entity, multi-jurisdiction) |

**Expert ask for Grok.com team:**
1. Domain review: scoring weights, deadline templates, deductible rules  
2. Product review: naming, IA, “path to live Xero sync”  
3. Engineering: PKCE + secure token proxy design on loopback  
4. Grok integration ideas: chat over preparer pack, “explain my pulse score,” anomaly scan on uncategorized spend  

---

## What’s intentionally *not* in v1 / v1.1

- Xero **write** APIs (create bills/invoices in Xero) — read path + token proxy shipped; draft stage is local first  
- Continuous Google Maps API access (Takeout JSON import only)  
- Multi-user / cloud sync  
- Actual e-file or form generation  
- CPA-grade quarterly safe-harbor / full Form 1040-ES optimization  
- Jurisdiction-complete tax calendars (US templates only)  
- Receipt photo OCR  

These are the natural **v2** wedge once experts validate the preparedness loop.

---

## Suggested next milestones

| Milestone | Outcome |
|-----------|---------|
| **M1 — Live LedgerLink** | **Shipped:** loopback `/api/xero/*` + DPAPI secrets; pull accounts + bank txns/invoices when Owner connects |
| **M2 — Grok Assist panel** | “Explain score,” “propose codes,” “year-end questions” over local pack |
| **M3 — Multi-jurisdiction** | AU/UK/US deadline packs; tax-type mapping from Xero |
| **M4 — Evidence locker** | Attach receipt files/hashes to write-off lines |
| **M5 — Mileage → Xero write** | Push staged mileage summary via write-scoped proxy (after M1) |

---

## File map (for engineers)

```
Business Tax Preparedness/
  TaxForge Hub.html
  LedgerLink Console.html      ← includes Mileage import panel
  Compliance Pulse.html        ← includes Quarterly SE estimate card
  Write-Off Workshop.html
  Year-End War Room.html
  taxforge-shared.css
  taxforge-shared.js           ← mileage + quarterly helpers
  TAXFORGE-EXPERT-BRIEF.md     ← this document
  TAXFORGE-EMAIL-TO-EXPERTS.txt

docs/
  XERO-TOKEN-PROXY-DESIGN.md   ← design-only token proxy sequence + endpoints
```

Launcher registration: `Toolbox Launcher.html` → category `Tax`, section **TaxForge & Books**.

---

## One-liner options (pick a tone)

- **Product:** “TaxForge turns Xero chaos into a tax-ready score and a preparer pack.”  
- **Engineering:** “Local-first tax preparedness suite with Xero OAuth scaffold and shared ledger state.”  
- **AI:** “The missing cleanliness layer between SMB books and expert (or Grok) review.”  

---

## Multi-agent collaboration (Grok.com ↔ local Hands)

Experts do **not** only review this brief — they **direct** the local coding agent via repo handoffs:

| Doc | Purpose |
|-----|---------|
| `docs/MULTI-AGENT-PROTOCOL.md` | Full Expert ↔ Hands protocol |
| `docs/agent-handoff/COMMS-HANDS-TO-EXPERTS.md` | Standing message from Hands |
| `docs/agent-handoff/QUEUE.md` | Work queue |
| `docs/agent-handoff/DIR-*.md` | Direction packages Hands executes |
| `docs/PROJECT-MAP.md` | Whole toolbox map |

**Protocol in one line:** Experts file DIR packages with ordered tasks + acceptance checks; Hands implements on the owner’s machine and reports Results in-repo.

## Contact / handoff notes (fill in)

- **Owner:** _______________________  
- **Repo:** `Treyu2023/FAFO-Power-Toolbox` · path `Business Tax Preparedness/`  
- **Demo environment:** Local browser; optional toolbox server for future Xero tokens  
- **Ask of experts:** File follow-on DIRs after reading bootstrap package  

---

*Prepared for sharing with Grok.com / domain experts. Safe to forward; contains no secrets or credentials.*
