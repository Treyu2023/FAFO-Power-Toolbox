# TaxForge — START HERE (2025 extended return)

**Not tax advice.** This is a local checklist to organize numbers for you and your CPA.

## Open TaxForge

1. Start toolbox servers if needed (`0-Start-ALL-Servers.bat` or Launcher **Start All**).
2. Open **Toolbox Launcher** → **TaxForge Hub**  
   Or: `C:\AI HTML TOOLBOX\Business Tax Preparedness\TaxForge Hub.html`  
   Prefer via S1 (`http://127.0.0.87:18765/...`) so one-click pack load works.

## Do this in order (today)

### 1. Load mileage (already prepared for you)

On **TaxForge Hub**:

- Click **Load 2025 MileIQ pack now**  
  - Pack: `imports/taxforge-2025-mileiq-import.json`  
  - **618** business trips · **~16,091 mi** · **~$11,263** @ **$0.70**/mi  
  - Jun–Dec 2025 only (your annual MileIQ export)
- If fetch fails (file://), click **Browse for pack…** and pick that JSON manually.

Then open **Mileage Log** → year filter **2025** → confirm totals.

CPA CSV already built: `imports/2025-business-mileage-for-cpa.csv`

### 2. Expenses / bank

Open **Write-Off Workshop**:

- Drop **bank/card CSVs** for 2025 (or full year if available).
- **Auto-suggest codes** → apply what looks right.
- Export **review CSV** for the CPA for the rest.

### 3. Income stack (offline folder)

Gather (doesn’t have to be in TaxForge yet):

- 1099s / invoices / deposit summaries  
- Prior year return / extension confirmation  

Mark items on Hub **Filing checklist**.

### 4. Estimated taxes (if any)

**Quarterly Tracker** → enter payments you actually made in 2025.

### 5. Handoff

On Hub:

- **Export TaxForge backup JSON**
- Download CPA mileage CSV  
- Write-Off review CSV  
- List of **Questions for CPA**

Send that pack + your PDF docs to the preparer.

## What is already done for you

| Item | Status |
|------|--------|
| MileIQ 2025 parsed | Ready in `imports/` |
| Hub one-click load | TaxForge Hub |
| Bank CSV import UI | Write-Off Workshop |
| Checklist + CPA questions | Hub |
| Rate default | $0.70 / mi · year 2025 |

## Still on you / CPA

- Confirm IRS mileage rate & vehicle eligibility for 2025  
- Full bank statements / receipts  
- Income docs  
- Entity docs if CPA doesn’t have them  
- Actual filing / e-file (TaxForge does **not** file)

## Tools map

| Need | Open |
|------|------|
| Start + load pack | TaxForge Hub |
| Verify trips | Mileage Log |
| Bank expenses | Write-Off Workshop |
| Estimates | Quarterly Tracker |
| Deadlines / vault | Year-End War Room |
| Xero later | LedgerLink Console |
