# DIR: Google Takeout / Timeline Location History → draft Xero tickets

- **Status:** DONE
- **Priority:** P2
- **Owner (expert):** Grok.com expert team (Lucas / Benjamin / Harper)
- **Executor:** local Grok agent (hands)
- **Created:** 2026-08-02
- **Goal:** Add a local importer in TaxForge (prefer LedgerLink Console or a dedicated panel) that parses Google Timeline / Location History / Semantic Location History JSON (placeVisit + activitySegment) and any associated notes, then stages draft Xero invoices or bills from those visits.

## Context
Owner asked whether we can access Google Maps location history and notes to create Xero tickets. No live Google Maps connector exists. Practical path is user-exported Takeout / on-device Timeline JSON. This builds on the existing CSV import and demo mode in LedgerLink, and will later feed the live Xero proxy once that lands.

## Constraints
- Follow AGENTS.md (local-only, no secrets, no uploading user location data anywhere)
- Match TaxForge shared style (taxforge-shared.css/js)
- Explicit privacy note: all parsing stays on the user’s machine
- “Not tax/legal advice” disclaimer where relevant
- Graceful handling of missing fields, older Takeout formats, or empty exports
- Prefer small diffs; reuse existing import patterns in LedgerLink / taxforge-shared.js
- Demo / local staging first; live Xero creation only if the token proxy is already available from the prior DIR

## Tasks (ordered)
1. Research and support the common 2024–2026 export formats: Semantic Location History monthly JSON (placeVisit objects with location.name, address, duration, startTimestamp, endTimestamp), Timeline.json / Records.json where present, and any simple notes fields.
2. Add an “Import Location History / Timeline” panel (LedgerLink Console preferred, or Write-Off Workshop): file picker for JSON or ZIP containing the exports.
3. Parse placeVisit (and optionally activitySegment) into a reviewable list: place name, address, date/time range, duration, inferred miles if possible, free-text note field (editable).
4. UI controls: select visits → map to a customer/contact (or “new”), set amount or rate, choose Invoice vs Bill / Expense, then “Stage draft” (localStorage / demo) or “Create in Xero” when live proxy is ready.
5. Optional: simple rule to turn long visits at a named commercial site into candidate job tickets.
6. Update `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md` with the new importer and privacy notes.
7. Smoke-check: load sample (or empty) JSON without errors; suite still launches cleanly.

## Acceptance checks
- [ ] File picker accepts common Timeline / Semantic Location History JSON
- [ ] placeVisit records appear in a reviewable table with editable notes
- [ ] User can stage at least one draft invoice/bill (demo mode)
- [ ] Privacy note visible; no data leaves the machine
- [ ] Expert brief updated
- [ ] No secrets or location data committed to git

## Out of scope
- Live continuous access to Google Maps APIs or the user’s account
- Automatic creation of Xero tickets without user review
- GPS-to-address reverse geocoding that requires external paid APIs (use names already in the export)
- Changing the current mileage DIR or live Xero proxy DIR

## Handoff notes for next expert
After this and the mileage/proxy DIRs land, a natural refinement is “one-click create bill from selected visit using live Xero endpoint.”

---

## Result

- **Status:** DONE
- **Completed:** 2026-08-02
- **Summary:** Local Google Takeout / Semantic Location History importer on LedgerLink. Parses placeVisit (+ activitySegment), review table with notes/contact/amount/invoice-vs-bill, commercial candidate flag, stage draft tickets to localStorage (and optional txn mirror). Sample JSON loader. Privacy note. ZIP = extract-then-JSON (browser limitation). Live Xero create deferred to proxy write path (out of scope).
- **Files touched:**
  - `Business Tax Preparedness/taxforge-shared.js` (`TaxForge.timeline`)
  - `Business Tax Preparedness/LedgerLink Console.html` (Timeline panel)
  - `Business Tax Preparedness/TAXFORGE-EXPERT-BRIEF.md`
  - this DIR + QUEUE/LOG
- **Verification:** Sample JSON parses to visits + segments; stage drafts path wired; no location data committed.
- **Blockers:** None for demo/local staging. Live “Create in Xero” needs write-scoped proxy (later DIR).
