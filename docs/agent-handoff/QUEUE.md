# Direction Package Queue

**Protocol:** `docs/MULTI-AGENT-PROTOCOL.md`  
**Hands standing message:** `COMMS-HANDS-TO-EXPERTS.md`  
**Rule:** Prefer one `IN_PROGRESS` at a time.

| Priority | Status | ID | Title | Notes |
|----------|--------|-----|-------|-------|
| P1 | OPEN | DIR-20260802-1200-expert-bootstrap | Expert team bootstrap & first review pass | Experts: read project, file next DIRs |
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
