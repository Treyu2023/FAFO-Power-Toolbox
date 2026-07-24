"""
Commander site-survey photo OCR (EZ Mode foundation).

Techs photograph POS / Commander config screens on site. Images + OCR text
are stored next to the site export under survey\\photos\\ (local only).
Parsed key/value guesses can fill the site-survey form; raw OCR is always
kept exactly as recognized for later agentic fill-in.

Engines (first available wins):
  1. Windows.Media.Ocr via Scripts\\Invoke-WindowsOcr.ps1
  2. pytesseract (if installed + tesseract.exe on PATH)
  3. Manual / pasted text only
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import verifone_ops as vf

SCHEMA_CAPTURE = "FAFO.Commander.SurveyPhotoCapture/1"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024  # 25 MB per image
MAX_IMAGES_PER_REQUEST = 20

# Field-survey packs (same site-survey.json; separate workflows)
# POS is the home for photo OCR; other packs get specialized intake later.
SURVEY_PACKS = ("site", "network", "pos", "forecourt")
PACK_META = {
    "site": {
        "id": "site",
        "label": "Site info",
        "short": "Site",
        "description": "Address, contacts, brand, service IDs — who/where this store is.",
    },
    "network": {
        "id": "network",
        "label": "Network",
        "short": "Network",
        "description": "LAN, payment NIC, MNSP, routes, firewall path.",
    },
    "pos": {
        "id": "pos",
        "label": "POS / Commander",
        "short": "POS",
        "description": "Photo OCR of config screens, software version, accounts & passwords.",
    },
    "forecourt": {
        "id": "forecourt",
        "label": "Forecourt",
        "short": "Forecourt",
        "description": "Pumps, CRIND firmware, tank monitor, car wash.",
    },
}
# Optional screen tags within a pack (especially POS photo batches)
SCREEN_TYPES = (
    "auto",
    "network_menu",
    "employees",
    "software",
    "forecourt_menu",
    "site_signage",
    "other",
)

# Which survey paths belong to which pack (for apply filtering + completeness)
PACK_FIELD_PREFIXES: dict[str, tuple[str, ...]] = {
    "site": ("siteInfo.", "siteId", "displayName", "customer"),
    "network": ("network.",),
    "pos": ("credentials.", "softwareVersion", "displayName"),
    "forecourt": ("forecourt.",),
}

# Map parser labels -> survey dotted paths (values stored exactly as OCR text)
FIELD_ALIASES: list[tuple[re.Pattern[str], str]] = [
    # Network
    (re.compile(r"^(?:lan\s*)?ip(?:\s*address)?$|host\s*ip|ethernet\s*ip|eth0\s*ip|local\s*ip", re.I), "network.lanIp"),
    (re.compile(r"subnet(?:\s*mask)?$|netmask|network\s*mask", re.I), "network.subnet"),
    (re.compile(r"(?:default\s*)?gateway$|gw$|default\s*route", re.I), "network.gateway"),
    (re.compile(r"dns\s*(?:1|primary|pref(?:erred)?)$|primary\s*dns", re.I), "network.dns1"),
    (re.compile(r"dns\s*(?:2|secondary|alt(?:ernate)?)$|secondary\s*dns", re.I), "network.dns2"),
    (re.compile(r"^dns$", re.I), "network.dns1"),
    (re.compile(r"payment\s*nic(?:\s*ip)?|emv\s*ip|pin\s*pad\s*ip|payment\s*ip", re.I), "network.paymentNicIp"),
    (re.compile(r"payment\s*(?:nic\s*)?subnet", re.I), "network.paymentNicSubnet"),
    (re.compile(r"payment\s*(?:nic\s*)?gateway", re.I), "network.paymentNicGateway"),
    (re.compile(r"mnsp\s*(?:router|ip|host)?$|router\s*ip", re.I), "network.mnspRouter"),
    (re.compile(r"mnsp\s*port|router\s*port", re.I), "network.mnspPort"),
    (re.compile(r"mnsp\s*(?:variant|circuit|type)", re.I), "network.mnspVariant"),
    (re.compile(r"daily\s*msg(?:\s*server)?|dailymsg", re.I), "network.dailyMsgServer"),
    (re.compile(r"remote\s*server(?:\s*host)?$", re.I), "network.remoteServer"),
    (re.compile(r"remote\s*server\s*port", re.I), "network.remoteServerPort"),
    # Site identity
    (re.compile(r"site\s*id|store\s*(?:#|number|id)|site\s*number", re.I), "siteId"),
    (re.compile(r"service\s*id|svc\s*id", re.I), "siteInfo.serviceId"),
    (re.compile(r"help\s*desk(?:\s*phone)?|support\s*phone", re.I), "siteInfo.helpDesk"),
    (re.compile(r"^(?:store\s*)?phone$|main\s*phone", re.I), "siteInfo.phone"),
    (re.compile(r"address|street", re.I), "siteInfo.address"),
    (re.compile(r"^city$", re.I), "siteInfo.city"),
    (re.compile(r"^state$", re.I), "siteInfo.state"),
    (re.compile(r"zip(?:\s*code)?|postal", re.I), "siteInfo.zip"),
    (re.compile(r"brand|banner", re.I), "siteInfo.brand"),
    (re.compile(r"software(?:\s*version)?|base\s*version|commander\s*version|version$", re.I), "softwareVersion"),
    (re.compile(r"customer|merchant\s*name|site\s*name|store\s*name", re.I), "displayName"),
    # Credentials (store as OCR gives them — tech reviews before apply)
    (re.compile(r"config\s*client\s*user|manager\s*user|login\s*name|user\s*name|username", re.I), "credentials.configClientUser"),
    (re.compile(r"config\s*client\s*(?:password|pwd|pass)|manager\s*password", re.I), "credentials.configClientPassword"),
    (re.compile(r"csr\s*(?:password|pwd|pass)", re.I), "credentials.csrPassword"),
    (re.compile(r"maintenance\s*(?:menu\s*)?(?:password|pwd|pass)", re.I), "credentials.maintenanceMenuPassword"),
]

IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
KV_RE = re.compile(
    r"^[\s\-\*•]*([A-Za-z][A-Za-z0-9 ./\-#()]{1,48}?)\s*[:#=\|]\s*(.+?)\s*$"
)
LABEL_THEN_VALUE_RE = re.compile(
    r"^[\s\-\*•]*([A-Za-z][A-Za-z0-9 ./\-#()]{1,40}?)\s{2,}(.+?)\s*$"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize_pack(domain: str | None) -> str:
    d = (domain or "pos").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "site_info": "site",
        "siteinfo": "site",
        "info": "site",
        "net": "network",
        "commander": "pos",
        "pos_config": "pos",
        "pump": "forecourt",
        "pumps": "forecourt",
        "equipment": "forecourt",
        "all": "pos",
        "auto": "pos",
    }
    d = aliases.get(d, d)
    return d if d in SURVEY_PACKS else "pos"


def normalize_screen_type(screen_type: str | None) -> str:
    s = (screen_type or "auto").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "network": "network_menu",
        "net_menu": "network_menu",
        "employee": "employees",
        "cashiers": "employees",
        "accounts": "employees",
        "version": "software",
        "fw": "forecourt_menu",
        "crind": "forecourt_menu",
        "pump": "forecourt_menu",
        "sign": "site_signage",
        "signage": "site_signage",
        "": "auto",
    }
    s = aliases.get(s, s)
    return s if s in SCREEN_TYPES else "auto"


def field_matches_pack(path: str, pack: str, screen_type: str = "auto") -> bool:
    """Whether a parsed field path should apply into the given survey pack."""
    pack = normalize_pack(pack)
    screen_type = normalize_screen_type(screen_type)
    path = path or ""

    # Screen-type can widen or redirect apply scope
    if screen_type == "network_menu":
        return path.startswith("network.") or path in ("siteId",)
    if screen_type == "employees":
        return path.startswith("credentials.")
    if screen_type == "software":
        return path in ("softwareVersion", "displayName") or path.startswith("credentials.")
    if screen_type == "forecourt_menu":
        return path.startswith("forecourt.") or path.startswith("network.payment")
    if screen_type == "site_signage":
        return path.startswith("siteInfo.") or path in ("siteId", "displayName", "customer")

    prefixes = PACK_FIELD_PREFIXES.get(pack) or ()
    for pref in prefixes:
        if pref.endswith("."):
            if path.startswith(pref):
                return True
        elif path == pref:
            return True
    # POS default also accepts loose software/site id from menus
    if pack == "pos" and path in ("siteId", "softwareVersion"):
        return True
    return False


def filter_fields_for_pack(
    fields: dict[str, str],
    pack: str,
    screen_type: str = "auto",
) -> dict[str, str]:
    """Keep only fields that belong to the capture's pack / screen type."""
    pack = normalize_pack(pack)
    screen_type = normalize_screen_type(screen_type)
    if screen_type == "auto" and pack == "pos":
        # POS auto: keep everything OCR found (tech may have shot any menu)
        return dict(fields or {})
    out: dict[str, str] = {}
    for k, v in (fields or {}).items():
        if field_matches_pack(k, pack, screen_type):
            out[k] = v
    # If filter wiped everything, fall back to full map so raw value is not lost on apply
    if fields and not out:
        return dict(fields)
    return out


def packs_catalog() -> list[dict[str, Any]]:
    return [dict(PACK_META[p]) for p in SURVEY_PACKS]


def _photos_dir(export_path: Path) -> Path:
    d = export_path / "survey" / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(export_path: Path) -> Path:
    return _photos_dir(export_path) / "photo-index.json"


def _safe_stem(name: str) -> str:
    stem = Path(name or "photo").stem
    stem = re.sub(r"[^A-Za-z0-9._\-]+", "_", stem).strip("._") or "photo"
    return stem[:48]


def ocr_engine_status() -> dict[str, Any]:
    """Report which OCR backends are usable on this PC."""
    status: dict[str, Any] = {
        "primary": None,
        "engines": {},
        "hint": "",
    }
    ps1 = _repo_root() / "Scripts" / "Invoke-WindowsOcr.ps1"
    win_ok = ps1.is_file() and os.name == "nt"
    status["engines"]["windows_ocr"] = {
        "available": win_ok,
        "script": str(ps1) if win_ok else None,
        "note": "Built-in Windows OCR (Settings → Language → English OCR)",
    }
    tess_path = shutil.which("tesseract")
    try:
        import pytesseract  # type: ignore  # noqa: F401

        tess_mod = True
    except Exception:
        tess_mod = False
    status["engines"]["tesseract"] = {
        "available": bool(tess_path and tess_mod),
        "exe": tess_path,
        "module": tess_mod,
        "note": "Optional: pip install pytesseract + install Tesseract-OCR",
    }
    if win_ok:
        status["primary"] = "windows_ocr"
    elif tess_path and tess_mod:
        status["primary"] = "tesseract"
    else:
        status["primary"] = None
        status["hint"] = (
            "No automatic OCR engine found. You can still upload photos and paste text. "
            "On Windows 10/11 install the English OCR language pack, or install Tesseract."
        )
    return status


def _preprocess_for_ocr(src: Path) -> Path:
    """Upscale + contrast boost for small screen photos; returns path (may be temp)."""
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except Exception:
        return src

    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        # Upscale small / phone-ish crops so OCR has more pixels
        scale = 1.0
        long_edge = max(w, h)
        if long_edge < 1200:
            scale = 1200 / long_edge
        elif long_edge < 1800:
            scale = 1.5
        if scale > 1.01:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        # Mild contrast for dim POS screens
        img = ImageEnhance.Contrast(img).enhance(1.35)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        out = src.with_suffix(".ocrprep.png")
        img.save(out, format="PNG")
        return out
    except Exception:
        return src


def _run_windows_ocr(image_path: Path) -> tuple[str, str]:
    ps1 = _repo_root() / "Scripts" / "Invoke-WindowsOcr.ps1"
    if not ps1.is_file():
        raise RuntimeError("Invoke-WindowsOcr.ps1 missing")
    prep = _preprocess_for_ocr(image_path)
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1),
                "-ImagePath",
                str(prep),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(_repo_root()),
        )
    finally:
        if prep != image_path and prep.is_file():
            try:
                prep.unlink()
            except OSError:
                pass
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "Windows OCR failed").strip()
        raise RuntimeError(err[:500])
    text = (r.stdout or "").strip()
    # Normalize newlines only — do not rewrite OCR characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, "windows_ocr"


def _run_tesseract(image_path: Path) -> tuple[str, str]:
    import pytesseract  # type: ignore
    from PIL import Image, ImageOps

    prep = _preprocess_for_ocr(image_path)
    try:
        img = ImageOps.exif_transpose(Image.open(prep))
        text = pytesseract.image_to_string(img) or ""
    finally:
        if prep != image_path and prep.is_file():
            try:
                prep.unlink()
            except OSError:
                pass
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text, "tesseract"


def run_ocr(image_path: Path, prefer: str | None = None) -> dict[str, Any]:
    """OCR an image file. Returns raw text exactly as engine produced (newline-normalized)."""
    engines_try: list[str] = []
    if prefer in ("windows_ocr", "tesseract"):
        engines_try.append(prefer)
    st = ocr_engine_status()
    if st.get("primary") and st["primary"] not in engines_try:
        engines_try.append(st["primary"])
    for eng in ("windows_ocr", "tesseract"):
        if eng not in engines_try and st["engines"].get(eng, {}).get("available"):
            engines_try.append(eng)

    errors: list[str] = []
    for eng in engines_try:
        try:
            if eng == "windows_ocr":
                text, used = _run_windows_ocr(image_path)
            elif eng == "tesseract":
                text, used = _run_tesseract(image_path)
            else:
                continue
            lines = [ln for ln in text.split("\n")]
            return {
                "ok": True,
                "engine": used,
                "rawText": text,
                "lines": lines,
                "charCount": len(text),
                "lineCount": len([ln for ln in lines if ln.strip()]),
                "errors": errors,
            }
        except Exception as e:
            errors.append(f"{eng}: {e}")

    return {
        "ok": False,
        "engine": None,
        "rawText": "",
        "lines": [],
        "charCount": 0,
        "lineCount": 0,
        "errors": errors or ["No OCR engine available"],
    }


def _match_field_key(label: str) -> str | None:
    lab = re.sub(r"\s+", " ", (label or "").strip())
    if not lab:
        return None
    for pat, path in FIELD_ALIASES:
        if pat.search(lab):
            return path
    return None


def _clean_value(val: str) -> str:
    """Trim only; keep OCR characters as given."""
    return (val or "").strip().strip("\"'“”‘’")


def parse_config_text(raw_text: str) -> dict[str, Any]:
    """
    Extract survey field guesses from OCR/pasted text.
    Values are stored exactly as recognized (trimmed only).
    """
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    fields: dict[str, str] = {}
    field_sources: dict[str, str] = {}
    free_ips: list[str] = []
    unmatched_kv: list[dict[str, str]] = []

    # Pass 1: explicit key:value lines
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = KV_RE.match(s) or LABEL_THEN_VALUE_RE.match(s)
        if not m:
            continue
        label, value = m.group(1), _clean_value(m.group(2))
        if not value:
            continue
        path = _match_field_key(label)
        if path:
            # First win keeps earliest/top-of-screen value; do not rewrite
            if path not in fields:
                fields[path] = value
                field_sources[path] = s
        else:
            unmatched_kv.append({"label": label.strip(), "value": value, "line": s})

    # Pass 2: label on one line, value on next (common on POS menus)
    for i, ln in enumerate(lines[:-1]):
        lab = ln.strip().rstrip(":").strip()
        if not lab or len(lab) > 40:
            continue
        path = _match_field_key(lab)
        if not path or path in fields:
            continue
        nxt = _clean_value(lines[i + 1])
        if not nxt or KV_RE.match(nxt):
            continue
        # Avoid treating another label as value
        if _match_field_key(nxt.rstrip(":")):
            continue
        fields[path] = nxt
        field_sources[path] = f"{lab} → {nxt}"

    # Pass 3: loose IPs when LAN IP still empty (skip netmasks like 255.x.x.x)
    for m in IP_RE.finditer(text):
        ip = m.group(0)
        if ip.startswith("255."):
            continue
        if ip not in free_ips:
            free_ips.append(ip)
    if "network.lanIp" not in fields and free_ips:
        # Prefer private LAN ranges for lanIp
        private = [
            ip
            for ip in free_ips
            if ip.startswith("192.168.") or ip.startswith("10.") or re.match(r"172\.(1[6-9]|2\d|3[0-1])\.", ip)
        ]
        pick = private[0] if private else free_ips[0]
        fields["network.lanIp"] = pick
        field_sources["network.lanIp"] = f"(first IP in OCR) {pick}"

    if "network.gateway" not in fields and free_ips:
        for ip in free_ips:
            if ip.endswith(".1") or ip.endswith(".254"):
                fields["network.gateway"] = ip
                field_sources["network.gateway"] = f"(guess from IP) {ip}"
                break

    return {
        "fields": fields,
        "fieldSources": field_sources,
        "unmatchedKeyValues": unmatched_kv[:80],
        "ipsFound": free_ips,
        "lineCount": len([ln for ln in lines if ln.strip()]),
    }


def _set_by_path(obj: dict[str, Any], path: str, value: str, overwrite: bool) -> bool:
    parts = path.split(".")
    cur: Any = obj
    for p in parts[:-1]:
        if not isinstance(cur, dict):
            return False
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    last = parts[-1]
    if not isinstance(cur, dict):
        return False
    existing = cur.get(last)
    if not overwrite and existing not in (None, ""):
        return False
    cur[last] = value
    return True


def apply_fields_to_survey(
    survey: dict[str, Any],
    fields: dict[str, str],
    *,
    mode: str = "fill_empty",
) -> dict[str, Any]:
    """
    Apply parsed fields onto a survey object.
    mode: none | fill_empty | overwrite
    Values are written exactly as provided (no reformatting).
    """
    mode = (mode or "fill_empty").lower().strip()
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    if mode == "none" or not fields:
        return {"survey": survey, "applied": applied, "skipped": skipped, "mode": mode}

    overwrite = mode == "overwrite"
    for path, value in fields.items():
        if value is None:
            continue
        # Keep OCR string as-is (only ensure str)
        val = str(value)
        ok = _set_by_path(survey, path, val, overwrite=overwrite)
        if ok:
            applied.append({"path": path, "value": val})
        else:
            skipped.append({"path": path, "value": val, "reason": "already filled" if not overwrite else "failed"})

    # Append raw applied note into tech notes (audit trail, not overwriting free text)
    if applied:
        stamp = _utc_now()
        note_line = f"[OCR {stamp}] applied {len(applied)} field(s): " + ", ".join(
            a["path"] for a in applied[:20]
        )
        si = survey.setdefault("siteInfo", {})
        prev = (si.get("techNotes") or "").rstrip()
        si["techNotes"] = (prev + "\n" + note_line).strip() if prev else note_line

    return {"survey": survey, "applied": applied, "skipped": skipped, "mode": mode}


def _load_index(export_path: Path) -> dict[str, Any]:
    p = _index_path(export_path)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("captures", [])
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"schema": "FAFO.Commander.SurveyPhotoIndex/1", "captures": []}


def _save_index(export_path: Path, index: dict[str, Any]) -> None:
    p = _index_path(export_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    index["updatedAt"] = _utc_now()
    p.write_text(json.dumps(index, indent=2), encoding="utf-8")


def list_captures(site_key: str) -> dict[str, Any]:
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    index = _load_index(export_path)
    return {
        "ok": True,
        "siteId": site_key,
        "photosDir": str(_photos_dir(export_path)),
        "captures": index.get("captures") or [],
        "packs": packs_catalog(),
        "engine": ocr_engine_status(),
    }


def _decode_image(item: dict[str, Any]) -> tuple[bytes, str]:
    b64 = item.get("data_base64") or item.get("dataBase64") or item.get("base64") or ""
    if isinstance(b64, str) and "," in b64 and b64.strip().lower().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    b64 = re.sub(r"\s+", "", str(b64))
    if not b64:
        raise ValueError("image data_base64 is required")
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception as e:
        raise ValueError(f"invalid base64 image: {e}") from e
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit")
    if len(raw) < 32:
        raise ValueError("image data too small")

    filename = str(item.get("filename") or item.get("name") or "photo.png")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        # sniff
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
            filename = _safe_stem(filename) + ".png"
        elif raw[:2] == b"\xff\xd8":
            ext = ".jpg"
            filename = _safe_stem(filename) + ".jpg"
        else:
            ext = ".png"
            filename = _safe_stem(filename) + ".png"
    else:
        filename = _safe_stem(filename) + ext
    return raw, filename


def ingest_photos(
    site_key: str,
    images: list[dict[str, Any]] | None = None,
    *,
    raw_texts: list[dict[str, Any]] | None = None,
    apply_mode: str = "fill_empty",
    notes: str = "",
    prefer_engine: str | None = None,
    domain: str | None = "pos",
    screen_type: str | None = "auto",
) -> dict[str, Any]:
    """
    Save photos + OCR (or pasted text) under the site survey folder,
    parse config fields, optionally merge into site-survey.json.

    domain: site | network | pos | forecourt (pack ownership of this batch)
    screen_type: auto | network_menu | employees | software | forecourt_menu | site_signage | other
    apply_mode: none | fill_empty | overwrite
    """
    pack = normalize_pack(domain)
    screen = normalize_screen_type(screen_type)
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    photos = _photos_dir(export_path)
    index = _load_index(export_path)
    captures_out: list[dict[str, Any]] = []
    all_fields: dict[str, str] = {}
    combined_raw_parts: list[str] = []

    images = list(images or [])
    raw_texts = list(raw_texts or [])
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise ValueError(f"max {MAX_IMAGES_PER_REQUEST} images per request")

    # --- image items ---
    for item in images:
        raw, filename = _decode_image(item if isinstance(item, dict) else {})
        # Per-item domain override
        item_pack = normalize_pack(
            (item.get("domain") or item.get("pack") or pack) if isinstance(item, dict) else pack
        )
        item_screen = normalize_screen_type(
            (item.get("screen_type") or item.get("screenType") or screen)
            if isinstance(item, dict)
            else screen
        )
        cap_id = uuid.uuid4().hex[:12]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_name = f"{stamp}_{cap_id}_{filename}"
        img_path = photos / img_name
        img_path.write_bytes(raw)

        ocr = run_ocr(img_path, prefer=prefer_engine)
        # optional per-image pasted override / supplement
        pasted = ""
        if isinstance(item, dict):
            pasted = str(item.get("pastedText") or item.get("rawText") or "").strip()
        if pasted:
            # Prefer explicit paste when provided; keep OCR separately
            effective_text = pasted
            ocr["pastedText"] = pasted
            ocr["ocrRawText"] = ocr.get("rawText") or ""
            ocr["rawText"] = pasted
            ocr["lines"] = pasted.replace("\r\n", "\n").split("\n")
            ocr["engine"] = (ocr.get("engine") or "none") + "+paste"
            ocr["ok"] = True
        elif not ocr.get("ok"):
            effective_text = ""
        else:
            effective_text = ocr.get("rawText") or ""

        parsed = parse_config_text(effective_text) if effective_text else parse_config_text("")
        scoped = filter_fields_for_pack(parsed.get("fields") or {}, item_pack, item_screen)
        for k, v in scoped.items():
            if k not in all_fields:
                all_fields[k] = v

        if effective_text:
            combined_raw_parts.append(
                f"--- [{item_pack}/{item_screen}] {img_name} ---\n{effective_text}"
            )

        sha = hashlib.sha256(raw).hexdigest()[:16]
        capture = {
            "schema": SCHEMA_CAPTURE,
            "id": cap_id,
            "kind": "image",
            "domain": item_pack,
            "pack": item_pack,
            "screenType": item_screen,
            "fileName": img_name,
            "imagePath": str(img_path),
            "sha256_16": sha,
            "bytes": len(raw),
            "capturedAt": _utc_now(),
            "notes": notes or (item.get("notes") if isinstance(item, dict) else "") or "",
            "engine": ocr.get("engine"),
            "ocrOk": bool(ocr.get("ok") or pasted),
            "rawText": effective_text,  # as given (paste or OCR)
            "ocrRawText": ocr.get("ocrRawText") if pasted else (ocr.get("rawText") or ""),
            "lines": ocr.get("lines") or [],
            "parsedFields": parsed.get("fields") or {},
            "scopedFields": scoped,
            "fieldSources": parsed.get("fieldSources") or {},
            "unmatchedKeyValues": parsed.get("unmatchedKeyValues") or [],
            "ipsFound": parsed.get("ipsFound") or [],
            "ocrErrors": ocr.get("errors") or [],
            "appliedAt": None,
            "applyMode": None,
        }
        # sidecar JSON next to image
        side = img_path.with_suffix(img_path.suffix + ".ocr.json")
        side.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        capture["sidecarPath"] = str(side)
        captures_out.append(capture)
        index.setdefault("captures", []).insert(0, {
            "id": cap_id,
            "kind": "image",
            "domain": item_pack,
            "pack": item_pack,
            "screenType": item_screen,
            "fileName": img_name,
            "imagePath": str(img_path),
            "sidecarPath": str(side),
            "capturedAt": capture["capturedAt"],
            "engine": capture["engine"],
            "ocrOk": capture["ocrOk"],
            "charCount": len(effective_text),
            "fieldCount": len(scoped),
            "notes": capture["notes"],
        })

    # --- text-only items (no photo) ---
    for item in raw_texts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("rawText") or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            continue
        item_pack = normalize_pack(item.get("domain") or item.get("pack") or pack)
        item_screen = normalize_screen_type(item.get("screen_type") or item.get("screenType") or screen)
        cap_id = uuid.uuid4().hex[:12]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_name = f"{stamp}_{cap_id}_pasted.txt"
        txt_path = photos / txt_name
        # Store exactly as given
        txt_path.write_text(text, encoding="utf-8", newline="\n")
        parsed = parse_config_text(text)
        scoped = filter_fields_for_pack(parsed.get("fields") or {}, item_pack, item_screen)
        for k, v in scoped.items():
            if k not in all_fields:
                all_fields[k] = v
        combined_raw_parts.append(f"--- [{item_pack}/{item_screen}] {txt_name} ---\n{text}")
        capture = {
            "schema": SCHEMA_CAPTURE,
            "id": cap_id,
            "kind": "text",
            "domain": item_pack,
            "pack": item_pack,
            "screenType": item_screen,
            "fileName": txt_name,
            "imagePath": None,
            "textPath": str(txt_path),
            "capturedAt": _utc_now(),
            "notes": notes or item.get("notes") or "",
            "engine": "paste",
            "ocrOk": True,
            "rawText": text,
            "lines": text.split("\n"),
            "parsedFields": parsed.get("fields") or {},
            "scopedFields": scoped,
            "fieldSources": parsed.get("fieldSources") or {},
            "unmatchedKeyValues": parsed.get("unmatchedKeyValues") or [],
            "ipsFound": parsed.get("ipsFound") or [],
            "ocrErrors": [],
            "appliedAt": None,
            "applyMode": None,
        }
        side = txt_path.with_suffix(".ocr.json")
        side.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        capture["sidecarPath"] = str(side)
        captures_out.append(capture)
        index.setdefault("captures", []).insert(0, {
            "id": cap_id,
            "kind": "text",
            "domain": item_pack,
            "pack": item_pack,
            "screenType": item_screen,
            "fileName": txt_name,
            "textPath": str(txt_path),
            "sidecarPath": str(side),
            "capturedAt": capture["capturedAt"],
            "engine": "paste",
            "ocrOk": True,
            "charCount": len(text),
            "fieldCount": len(scoped),
            "notes": capture["notes"],
        })

    if not captures_out:
        raise ValueError("Provide at least one image (data_base64) or raw_texts entry")

    # Combined raw dump (append-only transcript for agentic later)
    if combined_raw_parts:
        dump_path = photos / "ocr-transcript.txt"
        header = f"\n\n===== batch {_utc_now()} =====\n"
        with dump_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(header)
            f.write("\n\n".join(combined_raw_parts))
            f.write("\n")

    _save_index(export_path, index)

    apply_result = None
    survey_path = None
    if apply_mode and apply_mode.lower() != "none":
        survey = vf.get_survey(site_key)
        # Keep photoCaptures list on survey for form visibility
        caps = list(survey.get("photoCaptures") or [])
        for c in captures_out:
            caps.insert(0, _capture_summary(c))
        survey["photoCaptures"] = caps[:100]
        survey.setdefault("packs", {})
        survey["packs"]["catalog"] = packs_catalog()
        survey["packs"]["lastActive"] = pack
        # Full combined raw for this batch (exact text)
        scratch = survey.setdefault("ocrScratch", {})
        batch_raw = "\n\n".join(combined_raw_parts)
        prev_combined = scratch.get("combinedRawText") or ""
        scratch["combinedRawText"] = (prev_combined + "\n\n" + batch_raw).strip() if prev_combined else batch_raw
        scratch["lastIngestAt"] = _utc_now()
        scratch["lastParsedFields"] = all_fields
        scratch["lastDomain"] = pack
        scratch["lastScreenType"] = screen

        apply_result = apply_fields_to_survey(survey, all_fields, mode=apply_mode)
        survey = apply_result["survey"]
        for c in captures_out:
            c["appliedAt"] = _utc_now() if apply_result["applied"] else None
            c["applyMode"] = apply_mode
            # update sidecar
            side = c.get("sidecarPath")
            if side:
                try:
                    Path(side).write_text(json.dumps(c, indent=2), encoding="utf-8")
                except OSError:
                    pass
        saved = vf.save_survey(site_key, survey)
        survey_path = saved.get("path")
        apply_result["surveyPath"] = survey_path
    else:
        # Still record captures on survey without field apply
        try:
            survey = vf.get_survey(site_key)
            caps = list(survey.get("photoCaptures") or [])
            for c in captures_out:
                caps.insert(0, _capture_summary(c))
            survey["photoCaptures"] = caps[:100]
            survey.setdefault("packs", {})
            survey["packs"]["catalog"] = packs_catalog()
            survey["packs"]["lastActive"] = pack
            scratch = survey.setdefault("ocrScratch", {})
            batch_raw = "\n\n".join(combined_raw_parts)
            prev_combined = scratch.get("combinedRawText") or ""
            scratch["combinedRawText"] = (prev_combined + "\n\n" + batch_raw).strip() if prev_combined else batch_raw
            scratch["lastIngestAt"] = _utc_now()
            scratch["lastParsedFields"] = all_fields
            scratch["lastDomain"] = pack
            scratch["lastScreenType"] = screen
            saved = vf.save_survey(site_key, survey)
            survey_path = saved.get("path")
        except Exception:
            survey_path = None

    return {
        "ok": True,
        "siteId": site_key,
        "domain": pack,
        "screenType": screen,
        "photosDir": str(photos),
        "surveyPath": survey_path,
        "captures": captures_out,
        "parsedFields": all_fields,
        "packs": packs_catalog(),
        "apply": {
            "mode": apply_mode,
            "applied": (apply_result or {}).get("applied") or [],
            "skipped": (apply_result or {}).get("skipped") or [],
        },
        "engine": ocr_engine_status(),
        "securityNotice": (
            "Photo OCR may capture passwords from screens. Stored ONLY under this site's "
            "survey\\photos and site-survey.json. Do not commit or email."
        ),
    }


def _capture_summary(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c.get("id"),
        "fileName": c.get("fileName"),
        "capturedAt": c.get("capturedAt"),
        "engine": c.get("engine"),
        "ocrOk": c.get("ocrOk"),
        "domain": c.get("domain") or c.get("pack") or "pos",
        "pack": c.get("pack") or c.get("domain") or "pos",
        "screenType": c.get("screenType") or "auto",
        "rawText": c.get("rawText") or "",
        "parsedFields": c.get("parsedFields") or {},
        "scopedFields": c.get("scopedFields") or {},
        "fieldSources": c.get("fieldSources") or {},
        "imagePath": c.get("imagePath"),
        "textPath": c.get("textPath"),
        "notes": c.get("notes") or "",
    }


def get_capture(site_key: str, capture_id: str) -> dict[str, Any]:
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    index = _load_index(export_path)
    meta = None
    for c in index.get("captures") or []:
        if c.get("id") == capture_id:
            meta = c
            break
    if not meta:
        raise FileNotFoundError("Capture not found")
    side = meta.get("sidecarPath")
    if side and Path(side).is_file():
        try:
            return {"ok": True, "capture": json.loads(Path(side).read_text(encoding="utf-8"))}
        except (OSError, json.JSONDecodeError):
            pass
    return {"ok": True, "capture": meta}


def apply_capture_fields(
    site_key: str,
    capture_id: str,
    *,
    mode: str = "fill_empty",
    fields: dict[str, str] | None = None,
    use_scoped: bool = True,
) -> dict[str, Any]:
    """Re-apply a capture's parsed (or caller-supplied) fields to the survey."""
    detail = get_capture(site_key, capture_id)
    cap = detail["capture"]
    if fields is not None:
        use_fields = fields
    elif use_scoped and cap.get("scopedFields"):
        use_fields = cap.get("scopedFields") or {}
    else:
        pack = normalize_pack(cap.get("domain") or cap.get("pack"))
        screen = normalize_screen_type(cap.get("screenType"))
        use_fields = filter_fields_for_pack(cap.get("parsedFields") or {}, pack, screen)
    survey = vf.get_survey(site_key)
    result = apply_fields_to_survey(survey, use_fields, mode=mode)
    saved = vf.save_survey(site_key, result["survey"])
    # update sidecar appliedAt
    side = cap.get("sidecarPath")
    if side and Path(side).is_file():
        try:
            cap["appliedAt"] = _utc_now()
            cap["applyMode"] = mode
            Path(side).write_text(json.dumps(cap, indent=2), encoding="utf-8")
        except OSError:
            pass
    return {
        "ok": True,
        "path": saved.get("path"),
        "applied": result["applied"],
        "skipped": result["skipped"],
        "mode": mode,
    }
