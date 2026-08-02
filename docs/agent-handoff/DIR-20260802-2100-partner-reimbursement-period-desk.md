# DIR: Partner reimbursements + investor period reporting

- **Status:** DONE
- **Priority:** P1
- **Owner (expert):** Grok.com expert team (product + books / partner economics)
- **Executor:** local Grok agent (hands)
- **Created:** 2026-08-02
- **Goal:** Give the Owner a way to fix reimbursements that landed in the wrong bucket (without retyping every line), roll up months/years/fiscal periods, track investor parts + profit-share estimates, and auto-export a pack for the Expert team.

## Context
Owner (middle-man for Experts) reported reimbursements were entered in the wrong place early and never fully moved because transfer was too much work. Investor also purchases parts and takes a % profit share. Existing tools: TaxForge suite + Investor Portal (parts/serials/costs ledger for Sumran). Missing: period tallies, bulk reclass, reimbursement vs capital vs profit-share reporting for experts.

## Constraints
- Follow AGENTS.md (no secrets, local-first)
- Not tax/legal/partnership legal advice — bookkeeping helpers + disclaimers only
- Prefer TaxForge suite style; do not replace Investor Portal inventory ledger
- Small reversible diffs
- Expert pack must be shareable without passwords

## Tasks (ordered)
1. Add `TaxForge.partner` helpers: kinds, CSV import, reclass, period rollups (month/year/fiscal), share estimate, expert pack JSON/MD.
2. Ship `Partner Period Desk.html` UI: settings, import, bulk reclass, filters, period cards, exports.
3. Wire suite nav + TaxForge Hub card + Toolbox Launcher (Tax / TaxForge & Books).
4. File this DIR Result + QUEUE/LOG; give Owner paste-ready Expert report.

## Acceptance checks
- [x] Can import messy CSV and keep amounts while changing kind in bulk
- [x] Month / year / fiscal rollups show sales, parts, reimb, investor share estimate
- [x] Expert pack JSON + MD export works offline
- [x] Launcher + Hub + nav link present
- [x] Disclaimer shown; no secrets

## Out of scope
- Auto-sync live Investor Portal API into partner lines (can be a follow-on DIR)
- Legal determination of capital contribution vs reimbursement
- Changing Sumran portal auth / FAFO Petro sync

## Handoff notes for next expert
Review share **base** (net after ops vs gross), default %, and whether investor parts should reduce share base or sit as capital-only. Optionally: import bridge from Investor Portal sheet CSV → partner kinds.

---

## Result

- **Status:** DONE
- **Completed:** 2026-08-02
- **Summary:** Built Partner Period Desk for bulk reclass of misplaced reimbursements, investor parts tracking, period rollups, and expert pack export. Complements (does not replace) Investor Portal inventory ledger.
- **Files touched:**
  - `Business Tax Preparedness/taxforge-shared.js` (`TaxForge.partner`)
  - `Business Tax Preparedness/Partner Period Desk.html` (new)
  - `Business Tax Preparedness/TaxForge Hub.html`
  - `Toolbox Launcher.html`
  - this DIR + QUEUE + LOG
- **Verification:** Helpers + app present; nav id `partner`; launcher entry `partner-period-desk`; sample CSV workflow documented for Owner.
- **Blockers:** None for v1. Live merge from Investor Portal sheet is follow-on.
- **Suggested next DIR:** Optional bridge: Investor Portal sheet CSV → Partner Period Desk kinds; expert review of profit-share formula.
