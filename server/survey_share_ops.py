"""
Commander site-survey share / recovery packs.

Two primary modes:
  redacted — safe-ish for email / ticket handoff (no passwords, no OCR raw)
  full     — local tech recovery ZIP (may include secrets + photos)

Also:
  checklist — ordered recovery steps (Markdown) from what's known / missing

All packs write under the site export: survey\\share-packs\\
Never write outside the export tree.
"""
from __future__ import annotations

import json
import re
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import verifone_ops as vf

SCHEMA_SHARE = "FAFO.Commander.SurveySharePack/1"
REDACT_TOKEN = "[REDACTED]"
PRESENT_TOKEN = "[REDACTED — present on source PC]"
EMPTY_TOKEN = ""

# Credential / secret-ish keys (nested dict keys or dotted path tails)
SECRET_KEYS = {
    "password",
    "configclientpassword",
    "csrpassword",
    "maintenancemenupassword",
    "gemcompasswd",
    "otpnotes",
    "registrationkey",
    "secret",
    "pin",
    "token",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_slug(text: str, fallback: str = "site") -> str:
    s = re.sub(r"[^A-Za-z0-9._\-]+", "_", (text or "").strip())[:48].strip("._")
    return s or fallback


def _share_dir(export_path: Path) -> Path:
    d = export_path / "survey" / "share-packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_secret_key(key: str) -> bool:
    k = re.sub(r"[^a-z0-9]", "", (key or "").lower())
    if k in SECRET_KEYS:
        return True
    if "password" in k or k.endswith("pwd") or k.endswith("pass"):
        return True
    return False


def _filled(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return str(v).strip() != ""


def redact_survey(survey: dict[str, Any]) -> dict[str, Any]:
    """
    Deep-copy survey with secrets stripped/flagged.
    OCR raw text and photo raw text removed; field maps kept if non-secret.
    """
    src = deepcopy(survey or {})

    def walk(obj: Any, parent_key: str = "") -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if _is_secret_key(str(k)):
                    out[k] = PRESENT_TOKEN if _filled(v) else EMPTY_TOKEN
                elif str(k) in ("rawText", "ocrRawText", "combinedRawText", "lines"):
                    # Never ship OCR verbatim in redacted packs (may contain passwords)
                    if str(k) == "combinedRawText":
                        out[k] = PRESENT_TOKEN if _filled(v) else ""
                    elif str(k) == "lines":
                        out[k] = []
                    else:
                        out[k] = PRESENT_TOKEN if _filled(v) else ""
                elif str(k) == "accounts" and isinstance(v, list):
                    out[k] = [
                        {
                            "name": a.get("name") or "",
                            "number": a.get("number") or "",
                            "securityLevel": a.get("securityLevel") or "",
                            "password": PRESENT_TOKEN if _filled((a or {}).get("password")) else "",
                            "source": a.get("source") or "",
                            "notes": a.get("notes") or "",
                        }
                        for a in v
                        if isinstance(a, dict)
                    ]
                else:
                    out[k] = walk(v, str(k))
            return out
        if isinstance(obj, list):
            return [walk(x, parent_key) for x in obj]
        return obj

    red = walk(src)
    red["schema"] = SCHEMA_SHARE
    red["shareMode"] = "redacted"
    red["redactedAt"] = _utc_now()
    red["securityNotice"] = (
        "REDACTED share pack — passwords and OCR raw text removed. "
        "Safe for email only after a quick human review (IPs and layout remain)."
    )
    # Summarize captures without raw OCR / local paths
    orig_caps = [c for c in (survey.get("photoCaptures") or []) if isinstance(c, dict)]
    caps = []
    for oc in orig_caps:
        caps.append(
            {
                "id": oc.get("id"),
                "fileName": oc.get("fileName"),
                "capturedAt": oc.get("capturedAt"),
                "domain": oc.get("domain") or oc.get("pack"),
                "screenType": oc.get("screenType"),
                "engine": oc.get("engine"),
                "ocrOk": oc.get("ocrOk"),
                "scopedFields": _redact_field_map(oc.get("scopedFields") or {}),
                "parsedFields": _redact_field_map(oc.get("parsedFields") or {}),
                "notes": oc.get("notes") or "",
                "rawText": PRESENT_TOKEN if _filled(oc.get("rawText")) else "",
            }
        )
    red["photoCaptures"] = caps
    return red


def _redact_field_map(fields: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (fields or {}).items():
        path = str(k)
        if any(_is_secret_key(part) for part in path.split(".")) or "password" in path.lower():
            out[path] = PRESENT_TOKEN if _filled(v) else ""
        else:
            out[path] = v
    return out


def _md_kv_section(title: str, data: dict[str, Any], *, skip_empty: bool = False) -> list[str]:
    lines = [f"## {title}", ""]
    if not data:
        lines.append("_(empty)_")
        lines.append("")
        return lines
    for k, v in data.items():
        if skip_empty and not _filled(v):
            continue
        if isinstance(v, (dict, list)):
            lines.append(f"- **{k}**: `{json.dumps(v, ensure_ascii=False)[:200]}`")
        else:
            lines.append(f"- **{k}**: {v}")
    lines.append("")
    return lines


def survey_to_markdown(survey: dict[str, Any], *, mode: str) -> str:
    """Human-readable pack body."""
    s = survey or {}
    sb: list[str] = []
    title = s.get("displayName") or s.get("siteId") or "site"
    mode_label = "REDACTED (email-safe review)" if mode == "redacted" else "FULL TECH (local only)"
    sb.append(f"# Site survey share pack — {title}")
    sb.append("")
    sb.append(f"**Mode:** {mode_label}  ")
    sb.append(f"**Customer:** {s.get('customer') or '—'}  ")
    sb.append(f"**Site ID:** {s.get('siteId') or '—'}  ")
    sb.append(f"**Software:** {s.get('softwareVersion') or '—'}  ")
    sb.append(f"**Updated:** {s.get('updatedAt') or '—'}  ")
    sb.append(f"**Exported:** {_utc_now()}")
    sb.append("")
    if mode == "redacted":
        sb.append("> Passwords and OCR raw text removed. Review before emailing.")
    else:
        sb.append("> **CONFIDENTIAL** — may contain live passwords, OCR of config screens, and photos. Do not email unencrypted.")
    sb.append("")
    if s.get("securityNotice"):
        sb.append(str(s["securityNotice"]))
        sb.append("")

    si = s.get("siteInfo") or {}
    sb.extend(_md_kv_section("Site info", {
        "displayName": s.get("displayName"),
        "siteId": s.get("siteId"),
        "customer": s.get("customer"),
        **{k: si.get(k) for k in (
            "address", "city", "state", "zip", "phone", "brand", "serviceId",
            "helpDesk", "contactName", "contactPhone", "hours", "techNotes",
        )},
    }))

    net = s.get("network") or {}
    sb.extend(_md_kv_section("Network", net))

    cred = s.get("credentials") or {}
    sb.append("## Credentials")
    sb.append("")
    sb.append(f"- Config Client user: {cred.get('configClientUser') or '—'}")
    sb.append(f"- Config Client password: {cred.get('configClientPassword') or '—'}")
    sb.append(f"- CSR password: {cred.get('csrPassword') or '—'}")
    sb.append(f"- Maintenance menu password: {cred.get('maintenanceMenuPassword') or '—'}")
    sb.append("")
    sb.append("| Name | # | Lvl | Password | Source |")
    sb.append("| --- | --- | --- | --- | --- |")
    for a in cred.get("accounts") or []:
        sb.append(
            f"| {a.get('name') or ''} | {a.get('number') or ''} | {a.get('securityLevel') or ''} | "
            f"{a.get('password') or ''} | {a.get('source') or ''} |"
        )
    sb.append("")

    fc = s.get("forecourt") or {}
    sb.append("## Forecourt")
    sb.append("")
    sb.append(f"- Tank monitor: {fc.get('tankMonitorType') or '—'}")
    sb.append(f"- Car wash: {fc.get('carWashType') or '—'}")
    sb.append(f"- Dispenser brands: {', '.join(fc.get('dispenserBrands') or []) or '—'}")
    sb.append(f"- DCR brands: {', '.join(fc.get('dcrBrands') or []) or '—'}")
    sb.append(f"- Notes: {fc.get('notes') or '—'}")
    sb.append("")
    sb.append("| Pos | Fuel | DCR | Disp | CRIND | Pump FW | CRIND FW | Notes |")
    sb.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in fc.get("positions") or []:
        sb.append(
            f"| {p.get('position')} | {p.get('fuelChannel') or ''} | {p.get('dcrChannel') or ''} | "
            f"{p.get('dispenserBrand') or ''} | {p.get('dcrBrand') or ''} | "
            f"{p.get('pumpSoftwareVersion') or ''} | {p.get('crindSoftwareVersion') or ''} | "
            f"{p.get('notes') or ''} |"
        )
    sb.append("")

    layout = s.get("layout") or {}
    items = layout.get("items") or []
    if items:
        sb.append("## Aerial layout (summary)")
        sb.append("")
        sb.append(f"Canvas: {layout.get('width')}×{layout.get('height')} · items: {len(items)}")
        sb.append("")
        for it in items[:40]:
            sb.append(
                f"- **{it.get('type') or 'item'}** `{it.get('label') or it.get('id')}` "
                f"@ ({it.get('x')},{it.get('y')}) {it.get('w')}×{it.get('h')}"
            )
        sb.append("")

    caps = s.get("photoCaptures") or []
    if caps:
        sb.append("## Photo / OCR captures")
        sb.append("")
        for c in caps[:40]:
            sb.append(f"### {c.get('fileName') or c.get('id')}")
            sb.append(f"- Pack: {c.get('domain') or c.get('pack') or '—'} · screen: {c.get('screenType') or '—'}")
            sb.append(f"- Engine: {c.get('engine') or '—'} · at: {c.get('capturedAt') or '—'}")
            fields = c.get("scopedFields") or c.get("parsedFields") or {}
            if fields:
                sb.append("- Fields:")
                for k, v in fields.items():
                    sb.append(f"  - **{k}**: {v}")
            raw = c.get("rawText") or ""
            if mode == "full" and raw and raw != PRESENT_TOKEN:
                sb.append("")
                sb.append("```")
                sb.append(str(raw))
                sb.append("```")
            elif raw == PRESENT_TOKEN:
                sb.append("- Raw text: present on source (stripped for redacted pack)")
            sb.append("")

    return "\n".join(sb).rstrip() + "\n"


def build_recovery_checklist(survey: dict[str, Any]) -> str:
    """Ordered recovery checklist from filled vs missing survey fields."""
    s = survey or {}
    si = s.get("siteInfo") or {}
    net = s.get("network") or {}
    cred = s.get("credentials") or {}
    fc = s.get("forecourt") or {}
    layout = s.get("layout") or {}

    def row(done: bool, text: str) -> str:
        return f"- [{'x' if done else ' '}] {text}"

    lines = [
        f"# Recovery checklist — {s.get('displayName') or s.get('siteId') or 'site'}",
        "",
        f"Generated: {_utc_now()}  ",
        f"Site ID: {s.get('siteId') or '—'} · Customer: {s.get('customer') or '—'}",
        "",
        "Use this as the field order for reload / recovery. Unchecked items need data or action.",
        "",
        "## 1. Identity & access",
        row(_filled(s.get("siteId")), f"Confirm Site ID (`{s.get('siteId') or 'missing'}`)"),
        row(_filled(s.get("displayName")), f"Store name (`{s.get('displayName') or 'missing'}`)"),
        row(_filled(si.get("serviceId")), f"Service / ticket ID (`{si.get('serviceId') or 'missing'}`)"),
        row(_filled(si.get("address")) and _filled(si.get("city")), "Site address on file"),
        row(_filled(si.get("contactName")) or _filled(si.get("contactPhone")), "On-site contact available"),
        row(_filled(cred.get("configClientUser")), f"Config Client user (`{cred.get('configClientUser') or 'missing'}`)"),
        row(_filled(cred.get("configClientPassword")), "Config Client password on file (local / full pack only)"),
        row(_filled(cred.get("csrPassword")), "CSR password on file"),
        "",
        "## 2. Network path",
        row(_filled(net.get("lanIp")), f"LAN IP `{net.get('lanIp') or 'missing'}`"),
        row(_filled(net.get("subnet")), f"Subnet `{net.get('subnet') or 'missing'}`"),
        row(_filled(net.get("gateway")), f"Gateway `{net.get('gateway') or 'missing'}`"),
        row(_filled(net.get("dns1")), f"DNS `{net.get('dns1') or 'missing'}`"),
        row(_filled(net.get("paymentNicIp")), f"Payment NIC / EMV `{net.get('paymentNicIp') or 'missing'}`"),
        row(_filled(net.get("mnspRouter")), f"MNSP router `{net.get('mnspRouter') or 'missing'}`"),
        row(_filled(net.get("mnspPort")), f"MNSP port `{net.get('mnspPort') or 'missing'}`"),
        row(_filled(net.get("internetPathNotes")) or _filled(net.get("notes")), "Internet / firewall notes documented"),
        "",
        "## 3. Commander / POS config",
        row(_filled(s.get("softwareVersion")), f"Software version `{s.get('softwareVersion') or 'missing'}`"),
        row(bool(cred.get("accounts")), f"Employee / cashier accounts listed ({len(cred.get('accounts') or [])})"),
        row(bool(s.get("photoCaptures")), f"Config screen captures on file ({len(s.get('photoCaptures') or [])})"),
        row(_filled((s.get("ocrScratch") or {}).get("combinedRawText")), "OCR transcript available (full pack)"),
        "",
        "## 4. Forecourt",
        row(_filled(fc.get("tankMonitorType")), f"Tank monitor `{fc.get('tankMonitorType') or 'missing'}`"),
        row(_filled(fc.get("carWashType")), f"Car wash `{fc.get('carWashType') or 'n/a or missing'}`"),
        row(bool(fc.get("positions")), f"Fueling positions mapped ({len(fc.get('positions') or [])})"),
        row(
            any(
                _filled(p.get("pumpSoftwareVersion")) or _filled(p.get("crindSoftwareVersion"))
                for p in (fc.get("positions") or [])
            ),
            "Pump / CRIND firmware recorded on at least one position",
        ),
        row(bool((layout.get("items") or [])), f"Aerial layout items ({len(layout.get('items') or [])})"),
        "",
        "## 5. On-site actions (tech)",
        row(False, "Verify LAN + payment NIC isolation live"),
        row(False, "Login Config Client; confirm software / site ID"),
        row(False, "Restore or re-enter critical config from pack + SMS backup"),
        row(False, "Test pump authorize / CRIND / payment path"),
        row(False, "Update Liferaft + survey after changes"),
        row(False, "If emailing handoff: use REDACTED pack only"),
        "",
        "## Gaps (auto)",
    ]

    gaps: list[str] = []
    checks = [
        ("Site ID", s.get("siteId")),
        ("LAN IP", net.get("lanIp")),
        ("Gateway", net.get("gateway")),
        ("Payment NIC", net.get("paymentNicIp")),
        ("Config password", cred.get("configClientPassword")),
        ("Software version", s.get("softwareVersion")),
    ]
    for label, val in checks:
        if not _filled(val):
            gaps.append(f"- Missing: **{label}**")
    if not gaps:
        gaps.append("- No critical auto-gaps detected (still verify live).")
    lines.extend(gaps)
    lines.append("")
    return "\n".join(lines)


def export_share_pack(
    site_key: str,
    *,
    mode: str = "redacted",
    include_photos: bool = False,
    include_layout_json: bool = True,
    include_checklist: bool = True,
) -> dict[str, Any]:
    """
    Build a share pack under survey\\share-packs\\.

    mode:
      redacted  — folder with JSON + MD (secrets stripped); good for email after review
      full      — ZIP with full survey, checklist, optional photos; local / USB only
      checklist — Markdown recovery checklist only
    """
    mode = (mode or "redacted").strip().lower()
    if mode not in ("redacted", "full", "checklist"):
        raise ValueError("mode must be redacted | full | checklist")

    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    survey = vf.get_survey(site_key)
    share = _share_dir(export_path)
    slug = _safe_slug(
        f"{survey.get('siteId') or ''}_{survey.get('displayName') or site_key}".strip("_")
    )
    stamp = _stamp()
    written: list[str] = []

    if mode == "checklist":
        md = build_recovery_checklist(survey)
        out = share / f"{slug}_{stamp}_recovery-checklist.md"
        out.write_text(md, encoding="utf-8", newline="\n")
        written.append(str(out))
        return {
            "ok": True,
            "mode": mode,
            "path": str(out),
            "folder": str(share),
            "files": written,
            "emailSafe": True,
            "securityNotice": "Checklist has no password values (only present/missing flags).",
        }

    if mode == "redacted":
        red = redact_survey(survey)
        if not include_layout_json:
            red.pop("layout", None)
        base = share / f"{slug}_{stamp}_redacted"
        base.mkdir(parents=True, exist_ok=True)
        json_path = base / "site-survey.redacted.json"
        md_path = base / "site-survey.redacted.md"
        check_path = base / "recovery-checklist.md"
        readme = base / "README.txt"

        json_path.write_text(json.dumps(red, indent=2), encoding="utf-8")
        md_path.write_text(survey_to_markdown(red, mode="redacted"), encoding="utf-8", newline="\n")
        if include_checklist:
            check_path.write_text(build_recovery_checklist(survey), encoding="utf-8", newline="\n")
        readme.write_text(
            "\n".join(
                [
                    "FAFO Commander — REDACTED site survey share pack",
                    f"Generated: {_utc_now()}",
                    "",
                    "Contents:",
                    "  site-survey.redacted.json  — structured data, secrets stripped",
                    "  site-survey.redacted.md    — human-readable handoff",
                    "  recovery-checklist.md      — ordered recovery steps",
                    "",
                    "Safe for email only after a quick human review.",
                    "IPs, hostnames, and layout summaries are still included.",
                    "Passwords and OCR raw text are NOT included.",
                    "",
                    "Do not commit to git if the site is customer-confidential.",
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )
        written.extend([str(json_path), str(md_path), str(readme)])
        if include_checklist:
            written.append(str(check_path))

        # Optional: layout-only JSON for diagram tools
        if include_layout_json and survey.get("layout"):
            lay_path = base / "layout.json"
            lay_path.write_text(
                json.dumps(survey.get("layout"), indent=2),
                encoding="utf-8",
            )
            written.append(str(lay_path))

        return {
            "ok": True,
            "mode": mode,
            "path": str(base),
            "folder": str(share),
            "files": written,
            "emailSafe": True,
            "securityNotice": red.get("securityNotice"),
            "manifest": {
                "schema": SCHEMA_SHARE,
                "mode": "redacted",
                "siteId": survey.get("siteId"),
                "displayName": survey.get("displayName"),
                "exportedAt": _utc_now(),
                "files": [Path(p).name for p in written],
            },
        }

    # --- full tech pack (ZIP) ---
    zip_path = share / f"{slug}_{stamp}_FULL-TECH.zip"
    full_json = deepcopy(survey)
    full_json["shareMode"] = "full"
    full_json["exportedAt"] = _utc_now()
    full_json["securityNotice"] = (
        "FULL TECH PACK — may contain passwords, OCR of config screens, and photos. "
        "Local / encrypted USB only. Do not email unencrypted."
    )
    checklist_md = build_recovery_checklist(survey)
    full_md = survey_to_markdown(survey, mode="full")
    readme_txt = "\n".join(
        [
            "FAFO Commander — FULL TECH recovery pack",
            f"Generated: {_utc_now()}",
            f"Site: {survey.get('displayName') or ''} ({survey.get('siteId') or ''})",
            "",
            "CONFIDENTIAL — treat like credentials on paper.",
            "Do not email unencrypted. Do not commit to git.",
            "",
            "Contents:",
            "  site-survey.json",
            "  site-survey.md",
            "  recovery-checklist.md",
            "  README.txt",
            "  photos/   (optional)",
            "  ocr-transcript.txt (if present)",
            "",
        ]
    )

    photos_dir = export_path / "survey" / "photos"
    transcript = photos_dir / "ocr-transcript.txt"
    survey_src = export_path / "survey" / "site-survey.json"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme_txt)
        zf.writestr("site-survey.json", json.dumps(full_json, indent=2))
        zf.writestr("site-survey.md", full_md)
        zf.writestr("recovery-checklist.md", checklist_md)
        if include_layout_json and survey.get("layout"):
            zf.writestr("layout.json", json.dumps(survey.get("layout"), indent=2))
        if survey_src.is_file():
            # Also ship the on-disk file as-is (exact local save)
            zf.write(survey_src, arcname="source/site-survey.on-disk.json")
        if transcript.is_file():
            zf.write(transcript, arcname="ocr-transcript.txt")
        if include_photos and photos_dir.is_dir():
            for p in sorted(photos_dir.iterdir()):
                if not p.is_file():
                    continue
                if p.name == "photo-index.json" or p.suffix.lower() in {
                    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
                    ".txt", ".json",
                }:
                    # skip huge prep artifacts if any
                    if ".ocrprep." in p.name:
                        continue
                    zf.write(p, arcname=f"photos/{p.name}")

        manifest = {
            "schema": SCHEMA_SHARE,
            "mode": "full",
            "siteId": survey.get("siteId"),
            "displayName": survey.get("displayName"),
            "exportedAt": _utc_now(),
            "includePhotos": bool(include_photos),
            "captureCount": len(survey.get("photoCaptures") or []),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    written.append(str(zip_path))
    return {
        "ok": True,
        "mode": mode,
        "path": str(zip_path),
        "folder": str(share),
        "files": written,
        "emailSafe": False,
        "securityNotice": full_json["securityNotice"],
        "manifest": manifest,
    }


def list_share_packs(site_key: str) -> dict[str, Any]:
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    share = _share_dir(export_path)
    items: list[dict[str, Any]] = []
    for p in sorted(share.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("."):
            continue
        try:
            st = p.stat()
            items.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "isDir": p.is_dir(),
                    "bytes": st.st_size if p.is_file() else None,
                    "modifiedAt": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "kind": (
                        "full" if "FULL-TECH" in p.name
                        else "checklist" if "checklist" in p.name.lower()
                        else "redacted" if "redacted" in p.name.lower()
                        else "other"
                    ),
                }
            )
        except OSError:
            continue
    return {
        "ok": True,
        "folder": str(share),
        "packs": items[:50],
    }
