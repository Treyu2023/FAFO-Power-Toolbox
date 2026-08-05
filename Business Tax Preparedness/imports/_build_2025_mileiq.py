"""One-shot: parse 2025 MileIQ annual CSV → TaxForge import + summary."""
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\rkey2\OneDrive\Bankruptcy documents\Mileage Reports\2025")
ANNUAL = BASE / "MileIQ_2025_2025-01-01_2025-12-31.csv"
OUT_DIR = Path(__file__).resolve().parent


def main():
    text = ANNUAL.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    rate = None
    for line in lines[:5]:
        if line.lower().startswith("rates"):
            parts = next(csv.reader([line]))
            for i, p in enumerate(parts):
                if "business" in p.lower() and i + 1 < len(parts):
                    try:
                        rate = float(parts[i + 1])
                    except ValueError:
                        pass

    hi = next(i for i, l in enumerate(lines) if l.startswith("START_DATE"))
    reader = csv.DictReader(lines[hi:])

    def nk(k):
        return re.sub(r"\*$", "", (k or "").strip()).lower().replace(" ", "_")

    def num(x):
        if not x or str(x).startswith("="):
            return 0.0
        try:
            return float(str(x).replace(",", "").replace("$", ""))
        except ValueError:
            return 0.0

    rows = []
    for raw in reader:
        if not raw:
            continue
        d = {nk(k): (v or "").strip() for k, v in raw.items() if k is not None}
        start = d.get("start_date") or ""
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", start)
        if not m:
            continue
        mm, dd, yyyy = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if yyyy != "2025":
            continue
        cat = d.get("category") or ""
        purpose = d.get("purpose") or cat or "Drive"
        notes_parts = []
        if d.get("notes"):
            notes_parts.append(d["notes"])
        park, toll = num(d.get("parking")), num(d.get("tolls"))
        if park:
            notes_parts.append(f"Parking: ${park:.2f}")
        if toll:
            notes_parts.append(f"Tolls: ${toll:.2f}")
        if " " in start:
            notes_parts.append("Start: " + start.split(" ", 1)[1][:5])
        notes_parts.append("MileIQ")
        is_personal = cat.lower() in ("personal", "commute", "personal (other)")
        trip = {
            "id": f"mileiq_2025_{len(rows) + 1:04d}",
            "date": f"{yyyy}-{mm}-{dd}",
            "miles": num(d.get("miles")),
            "purpose": purpose,
            "from": d.get("start") or "",
            "to": d.get("stop") or "",
            "vehicle": d.get("vehicle") or "",
            "odometer": None,
            "business": not is_personal,
            "category": cat or ("Personal" if is_personal else "Business"),
            "parking": park,
            "tolls": toll,
            "rate": num(d.get("rate")) or rate,
            "notes": " · ".join(notes_parts),
            "source": "mileiq",
            "sourceFile": ANNUAL.name,
            "importedAt": datetime.now().isoformat(timespec="seconds"),
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
        rows.append(trip)

    by_cat = Counter(r["category"] for r in rows)
    by_month = defaultdict(lambda: {"trips": 0, "miles": 0.0, "biz_miles": 0.0})
    biz_miles = pers_miles = parking = tolls = 0.0
    for r in rows:
        mo = r["date"][:7]
        by_month[mo]["trips"] += 1
        by_month[mo]["miles"] += r["miles"]
        if r["business"]:
            by_month[mo]["biz_miles"] += r["miles"]
            biz_miles += r["miles"]
        else:
            pers_miles += r["miles"]
        parking += r["parking"]
        tolls += r["tolls"]

    purpose_top = Counter(r["purpose"] for r in rows if r["business"]).most_common(15)
    rrate = rate or 0.7

    pack = {
        "version": 1,
        "exportedAt": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "TaxForge import from MileIQ 2025 annual CSV — organization only, not tax advice.",
        "settings": {
            "businessName": "FAFO Petro Services",
            "taxYear": 2025,
            "mileageRate": rrate,
            "defaultVehicle": rows[0]["vehicle"] if rows else "",
            "seRatePercent": 15.3,
            "incomeTaxBufferPercent": 25,
        },
        "mileage": rows,
        "expenses": [],
        "quarterly": {},
        "questions": [],
    }

    path_json = OUT_DIR / "taxforge-2025-mileiq-import.json"
    path_json.write_text(json.dumps(pack, indent=2), encoding="utf-8")

    # CPA-friendly CSV of business trips only
    path_csv = OUT_DIR / "2025-business-mileage-for-cpa.csv"
    with path_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Date",
                "Business Purpose",
                "From",
                "To",
                "Miles",
                "Category",
                "Rate",
                "Amount At Rate",
                "Parking",
                "Tolls",
                "Vehicle",
                "Notes",
            ]
        )
        for r in sorted(rows, key=lambda x: x["date"]):
            if not r["business"]:
                continue
            w.writerow(
                [
                    r["date"],
                    r["purpose"],
                    r["from"],
                    r["to"],
                    r["miles"],
                    r["category"],
                    rrate,
                    round(r["miles"] * rrate, 2),
                    r["parking"],
                    r["tolls"],
                    r["vehicle"],
                    r["notes"],
                ]
            )

    md = [
        "# 2025 tax prep — MileIQ mileage focus",
        "",
        f"**Source:** `{ANNUAL.name}`",
        f"**Business rate in MileIQ file:** ${rrate}",
        f"**Trips parsed:** {len(rows)}",
        f"**Business miles:** {biz_miles:.1f}",
        f"**Personal/other miles:** {pers_miles:.1f}",
        f"**Mileage value (biz × rate):** ${biz_miles * rrate:,.2f}",
        f"**Parking total (logged):** ${parking:.2f}",
        f"**Tolls total (logged):** ${tolls:.2f}",
        "",
        "> Extended 2025 return — prep focus this month. **Not tax advice.** Confirm rate & deductibility with your CPA.",
        "",
        "## By category",
    ]
    for k, v in by_cat.most_common():
        md.append(f"- {k}: {v} trips")
    md += ["", "## By month (business miles)"]
    for mo in sorted(by_month):
        b = by_month[mo]
        md.append(
            f"- {mo}: **{b['biz_miles']:.1f}** biz mi · {b['trips']} trips · {b['miles']:.1f} total mi"
        )
    md += ["", "## Top purposes (business trips)"]
    for p, c in purpose_top:
        md.append(f"- {p}: {c}")
    md += [
        "",
        "## Files ready",
        f"- TaxForge Hub import: `{path_json.name}`",
        f"- CPA business-only CSV: `{path_csv.name}`",
        "",
        "## How to load into TaxForge",
        "1. Open **TaxForge Hub**",
        "2. Set tax year **2025** (import also sets this)",
        "3. **Import backup…** → choose `taxforge-2025-mileiq-import.json`",
        "4. Choose **Replace** if mileage is empty, or **Merge** if you already imported",
        "5. Open **Mileage Log** and filter year **2025** to verify totals",
        "",
        "## Still needed for 2025 filing (you / CPA)",
        "- [ ] Income: 1099s, invoices, deposits",
        "- [ ] Expense receipts / bank & card statements (full year)",
        "- [ ] Quarterly estimated payments made in 2025 (if any)",
        "- [ ] Entity docs (AOI, EIN) if CPA does not already have them",
        "- [ ] Confirm IRS standard mileage rate used for 2025 matches what you want to claim",
        "- [ ] Extension confirmation / prior filings notes",
        "",
    ]
    (OUT_DIR / "2025-MILEAGE-SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print(
        json.dumps(
            {
                "trips": len(rows),
                "biz_miles": round(biz_miles, 1),
                "pers_miles": round(pers_miles, 1),
                "rate": rrate,
                "value": round(biz_miles * rrate, 2),
                "parking": round(parking, 2),
                "tolls": round(tolls, 2),
                "by_cat": dict(by_cat),
                "months": {
                    k: {"trips": v["trips"], "biz_miles": round(v["biz_miles"], 1)}
                    for k, v in sorted(by_month.items())
                },
                "json": str(path_json),
                "csv": str(path_csv),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
