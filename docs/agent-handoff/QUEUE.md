# Direction Package Queue

**Protocol:** `docs/MULTI-AGENT-PROTOCOL.md`  
**Hands standing message:** `COMMS-HANDS-TO-EXPERTS.md`  
**Hands seat:** Grok Build (local) · **Experts seat:** Grok.com · **Owner:** middle-man relay  
**Rule:** Prefer one `IN_PROGRESS` at a time.

| Priority | Status | ID | Title | Notes |
|----------|--------|-----|-------|-------|
| P1 | DONE | DIR-20260802-2200-xero-token-proxy-impl | Xero token proxy implementation | Hands 2026-08-02 B+C; needs Owner Client ID/Secret at runtime |
| P2 | DONE | DIR-20260802-0035-google-takeout-location-xero-tickets | Google Takeout / Timeline → draft Xero tickets | Hands 2026-08-02; local placeVisit importer + stage drafts |
| P1 | DONE | DIR-20260802-2100-partner-reimbursement-period-desk | Partner reimb + investor period desk | Hands 2026-08-02; Owner request for reclass + fiscal rollups + expert packs |
| P1 | DONE | DIR-20260802-0045-taxforge-mileage-quarterly-xero-design | TaxForge mileage + quarterly SE + Xero proxy design | Closed by Hands 2026-08-02; proxy impl is natural follow-on |
| P1 | DONE | DIR-20260802-1200-expert-bootstrap | Expert team bootstrap & first review pass | Closed by Experts 2026-08-02; follow-on DIR filed |
| — | DONE | (bootstrap commit) | Land TaxForge + games + multi-agent docs | Hands shipped 2026-08-02 |

## Status legend

- **OPEN** — ready for Hands  
- **IN_PROGRESS** — Hands working  
- **BLOCKED** — needs Owner/Expert input  
- **DONE** — Result written  
- **CANCELLED** — abandoned  

## How to add work

1. Create `DIR-YYYYMMDD-HHMM-slug.md`  
2. Insert a row at the top of the table (after header)  
3. Hands will pick highest Priority among OPEN  
