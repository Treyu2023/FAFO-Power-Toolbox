"""
FAFO Task Manager Pro — process intel, efficiency scoring, optional NVD enrichment.

Design (simpler than full-web scrape of every EXE):
  1. Curated local knowledge base (process-knowledge.json) — purpose, disable pros/cons.
  2. Live metrics from psutil/network_ops — real CPU/RAM → efficiency score.
  3. Device-local "seen apps" registry + optional NVD keyword search (weekly, only for
     apps that actually ran), cached under %LOCALAPPDATA%\\FAFO\\TaskManagerPro\\.

There is no reliable free public API that maps every Windows process name to
"what it is" (ProcessLibrary-style sites are commercial/closed). Local KB +
measured load + NVD product keywords is the practical approach.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import network_ops as net
import startup_ops as startup

_KB_PATH = Path(__file__).parent / "data" / "process-knowledge.json"
_WEEK_SEC = 7 * 24 * 3600
_NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or str(Path.home())
    host = socket.gethostname() or "PC"
    d = Path(base) / "FAFO" / "Devices" / host / "TaskManagerPro"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_knowledge() -> dict[str, Any]:
    data = _load_json(_KB_PATH, {"processes": {}, "services": {}, "version": 0})
    if "processes" not in data:
        data["processes"] = {}
    if "services" not in data:
        data["services"] = {}
    return data


def _norm_proc_key(name: str) -> str:
    n = (name or "").strip().lower()
    if n.endswith(".exe"):
        n = n[:-4]
    return n


def _lookup_kb(name: str, kb: dict[str, Any] | None = None) -> dict[str, Any] | None:
    kb = kb or load_knowledge()
    key = _norm_proc_key(name)
    procs = kb.get("processes") or {}
    # direct
    if key in procs:
        return dict(procs[key], key=key)
    if f"{key}.exe" in procs:
        return dict(procs[f"{key}.exe"], key=key)
    # partial: chrome helpers etc.
    for k, v in procs.items():
        if key.startswith(k) or k.startswith(key):
            return dict(v, key=k, match="prefix")
    return None


def _lookup_service_kb(name: str, kb: dict[str, Any] | None = None) -> dict[str, Any] | None:
    kb = kb or load_knowledge()
    key = (name or "").strip().lower()
    svcs = kb.get("services") or {}
    if key in svcs:
        return dict(svcs[key], key=key)
    return None


def _efficiency_score(
    *,
    cpu: float,
    mem_percent: float,
    kb_hint: int | None,
    resource_hog: bool,
    vuln_count: int,
    known_issues: int,
) -> dict[str, Any]:
    """
    0–100 higher = healthier/more efficient.
    Live load dominates; KB and vulns adjust.
    """
    # Penalty from live use
    live = 100.0
    live -= min(50.0, cpu * 1.2)
    live -= min(35.0, mem_percent * 2.5)
    if resource_hog:
        live -= 8
    live -= min(20.0, vuln_count * 6)
    live -= min(10.0, known_issues * 3)

    if kb_hint is not None:
        # blend 60% live, 40% curated
        score = live * 0.6 + float(kb_hint) * 0.4
    else:
        score = live * 0.85 + 50 * 0.15  # unknown baseline

    score = max(0, min(100, round(score, 1)))
    if score >= 75:
        band = "good"
    elif score >= 50:
        band = "ok"
    elif score >= 30:
        band = "heavy"
    else:
        band = "critical"
    return {"score": score, "band": band}


def _seen_path() -> Path:
    return _store_dir() / "seen_apps.json"


def _vuln_cache_path() -> Path:
    return _store_dir() / "vuln_cache.json"


def record_seen_apps(process_names: list[str]) -> dict[str, Any]:
    """Merge running process names into device-local seen registry."""
    path = _seen_path()
    data = _load_json(path, {"apps": {}, "updated": None})
    apps: dict[str, Any] = data.setdefault("apps", {})
    now = _utc_now()
    for raw in process_names:
        key = _norm_proc_key(raw)
        if not key or key in ("system idle process", "system"):
            if key != "system":
                continue
        entry = apps.get(key) or {
            "name": raw,
            "first_seen": now,
            "run_count": 0,
            "last_vuln_check": None,
        }
        entry["name"] = raw or entry.get("name") or key
        entry["last_seen"] = now
        entry["run_count"] = int(entry.get("run_count") or 0) + 1
        apps[key] = entry
    data["updated"] = now
    data["apps"] = apps
    _save_json(path, data)
    return {"ok": True, "tracked": len(apps), "path": str(path)}


def get_seen_apps() -> dict[str, Any]:
    data = _load_json(_seen_path(), {"apps": {}, "updated": None})
    apps = data.get("apps") or {}
    return {
        "updated": data.get("updated"),
        "count": len(apps),
        "apps": sorted(apps.values(), key=lambda a: a.get("last_seen") or "", reverse=True),
        "store": str(_store_dir()),
    }


def enrich_process(row: dict[str, Any], kb: dict[str, Any] | None = None, vuln_cache: dict | None = None) -> dict[str, Any]:
    kb = kb or load_knowledge()
    vuln_cache = vuln_cache if vuln_cache is not None else _load_json(_vuln_cache_path(), {"by_key": {}})
    name = row.get("name") or ""
    info = _lookup_kb(name, kb)
    key = _norm_proc_key(name)
    vulns = (vuln_cache.get("by_key") or {}).get(key) or {}
    vuln_list = vulns.get("cves") or []
    known_issues = list((info or {}).get("known_issues") or [])
    resource_hog = bool((info or {}).get("resource_hog"))
    # live hog heuristic
    cpu = float(row.get("cpu_percent") or 0)
    mem_p = float(row.get("memory_percent") or 0)
    if cpu >= 25 or mem_p >= 8:
        resource_hog = True

    eff = _efficiency_score(
        cpu=cpu,
        mem_percent=mem_p,
        kb_hint=(info or {}).get("efficiency_hint"),
        resource_hog=resource_hog,
        vuln_count=len(vuln_list),
        known_issues=len(known_issues),
    )

    if info:
        purpose = info.get("purpose") or "Known process in local knowledge base."
        title = info.get("title") or name
        pros = info.get("disable_pros") or []
        cons = info.get("disable_cons") or []
        safe = bool(info.get("safe_to_disable"))
        publisher = info.get("publisher") or "Unknown"
        category = info.get("category") or "unknown"
        product_keywords = info.get("product_keywords") or [key]
    else:
        purpose = (
            "No curated entry yet. Identity inferred from process name/path only. "
            "Use Weekly Intel refresh to check NVD for product keywords, or add to knowledge base."
        )
        title = name
        path = (row.get("exe") or "").lower()
        if "\\windows\\system32\\" in path or "\\windows\\syswow64\\" in path:
            publisher, category = "Microsoft (path heuristic)", "system"
            safe = False
            pros = ["Only if you know this optional component."]
            cons = ["System path — high risk if required."]
        elif "\\program files" in path:
            publisher, category = "Third-party (Program Files)", "app"
            safe = True
            pros = ["Closing unused apps frees RAM/CPU."]
            cons = ["May lose unsaved work if force-killed."]
        else:
            publisher, category = "Unknown", "unknown"
            safe = True
            pros = ["If unrecognized and high CPU, investigate path/publisher."]
            cons = ["Do not kill if unsure — could be antivirus, driver helper, or installer."]
        product_keywords = [key]

    out = dict(row)
    out["intel"] = {
        "key": key,
        "title": title,
        "publisher": publisher,
        "category": category,
        "purpose": purpose,
        "disable_pros": pros,
        "disable_cons": cons,
        "safe_to_disable": safe,
        "resource_hog": resource_hog,
        "known_issues": known_issues,
        "efficiency": eff,
        "in_knowledge_base": info is not None,
        "product_keywords": product_keywords,
        "vulnerabilities": {
            "count": len(vuln_list),
            "last_check": vulns.get("checked_at"),
            "items": vuln_list[:8],
            "flagged": len(vuln_list) > 0,
        },
    }
    return out


def list_processes_intel(
    sort_by: str = "cpu",
    search: str = "",
    limit: int = 250,
) -> dict[str, Any]:
    raw = net.list_processes(sort_by=sort_by, search=search, limit=limit, include_network=True)
    procs = raw.get("processes") or []
    kb = load_knowledge()
    vuln_cache = _load_json(_vuln_cache_path(), {"by_key": {}})
    enriched = [enrich_process(p, kb, vuln_cache) for p in procs]
    # track seen
    try:
        record_seen_apps([p.get("name") or "" for p in procs])
    except OSError:
        pass
    # sort by efficiency if requested
    if sort_by == "efficiency":
        enriched.sort(key=lambda p: p.get("intel", {}).get("efficiency", {}).get("score", 50))
    elif sort_by == "risk":
        enriched.sort(
            key=lambda p: (
                -(p.get("intel", {}).get("vulnerabilities", {}).get("count") or 0),
                -float(p.get("cpu_percent") or 0),
            )
        )
    return {
        "timestamp": raw.get("timestamp") or _utc_now(),
        "count": len(enriched),
        "processes": enriched,
        "knowledge_version": kb.get("version"),
        "knowledge_count": len(kb.get("processes") or {}),
    }


def get_process_intel(pid: int) -> dict[str, Any]:
    detail = net.get_process_detail(pid)
    kb = load_knowledge()
    vuln_cache = _load_json(_vuln_cache_path(), {"by_key": {}})
    return enrich_process(detail, kb, vuln_cache)


def list_ratings(limit: int = 100) -> dict[str, Any]:
    """Efficiency leaderboard from current processes."""
    data = list_processes_intel(sort_by="cpu", limit=limit)
    rows = []
    for p in data["processes"]:
        intel = p.get("intel") or {}
        eff = intel.get("efficiency") or {}
        rows.append({
            "pid": p.get("pid"),
            "name": p.get("name"),
            "title": intel.get("title"),
            "category": intel.get("category"),
            "cpu_percent": p.get("cpu_percent"),
            "memory_percent": p.get("memory_percent"),
            "memory_human": p.get("memory_human"),
            "score": eff.get("score"),
            "band": eff.get("band"),
            "resource_hog": intel.get("resource_hog"),
            "vuln_count": (intel.get("vulnerabilities") or {}).get("count") or 0,
            "safe_to_disable": intel.get("safe_to_disable"),
            "in_knowledge_base": intel.get("in_knowledge_base"),
        })
    rows.sort(key=lambda r: (r.get("score") is None, r.get("score") if r.get("score") is not None else 999))
    return {
        "timestamp": data["timestamp"],
        "ratings": rows,
        "summary": {
            "good": sum(1 for r in rows if r.get("band") == "good"),
            "ok": sum(1 for r in rows if r.get("band") == "ok"),
            "heavy": sum(1 for r in rows if r.get("band") == "heavy"),
            "critical": sum(1 for r in rows if r.get("band") == "critical"),
            "hogs": sum(1 for r in rows if r.get("resource_hog")),
            "vuln_flagged": sum(1 for r in rows if (r.get("vuln_count") or 0) > 0),
        },
    }


def startup_intel() -> dict[str, Any]:
    ov = startup.get_overview()
    kb = load_knowledge()
    services = []
    for s in ov.get("services") or []:
        info = _lookup_service_kb(s.get("name") or "", kb)
        row = dict(s)
        if info:
            row["intel"] = {
                "title": info.get("title") or s.get("display_name"),
                "purpose": info.get("purpose"),
                "disable_pros": info.get("disable_pros") or [],
                "disable_cons": info.get("disable_cons") or [],
                "safe_to_disable": info.get("safe_to_disable"),
                "efficiency_hint": info.get("efficiency_hint"),
                "resource_hog": info.get("resource_hog"),
                "in_knowledge_base": True,
            }
        else:
            row["intel"] = {
                "title": s.get("display_name") or s.get("name"),
                "purpose": "Windows or third-party service. Check Display Name and Start Type before changing.",
                "disable_pros": ["Manual/disabled start can free boot time if truly unused."],
                "disable_cons": ["Dependencies may break; prefer Manual over Disabled when unsure."],
                "safe_to_disable": s.get("start_type") not in ("AUTO_START", "AUTOMATIC"),
                "efficiency_hint": 60,
                "resource_hog": False,
                "in_knowledge_base": False,
            }
        services.append(row)

    startup_items = []
    for it in ov.get("startup") or []:
        # try match command basename to process KB
        cmd = it.get("command") or it.get("name") or ""
        basem = re.search(r"([^\\/]+?\.exe)", cmd, re.I)
        pname = basem.group(1) if basem else it.get("name") or ""
        info = _lookup_kb(pname, kb)
        row = dict(it)
        if info:
            row["intel"] = {
                "title": info.get("title"),
                "purpose": info.get("purpose"),
                "disable_pros": info.get("disable_pros"),
                "disable_cons": info.get("disable_cons"),
                "safe_to_disable": info.get("safe_to_disable"),
                "efficiency_hint": info.get("efficiency_hint"),
                "in_knowledge_base": True,
            }
        else:
            row["intel"] = {
                "title": it.get("name"),
                "purpose": "Runs at user logon. Disable if you do not need it immediately after login.",
                "disable_pros": ["Faster login; less background RAM."],
                "disable_cons": ["App will not auto-start; open manually when needed."],
                "safe_to_disable": True,
                "efficiency_hint": 55,
                "in_knowledge_base": False,
            }
        startup_items.append(row)

    return {
        "timestamp": ov.get("timestamp") or _utc_now(),
        "startup_count": ov.get("startup_count"),
        "service_count": ov.get("service_count"),
        "task_count": ov.get("task_count"),
        "running_services": ov.get("running_services"),
        "services": services,
        "startup": startup_items,
        "tasks": ov.get("tasks") or [],
    }


def _nvd_search(keyword: str, results: int = 5, api_key: str | None = None) -> list[dict[str, Any]]:
    """Query NVD CVE API 2.0 by keyword. Free; key raises rate limits."""
    q = urllib.parse.urlencode({
        "keywordSearch": keyword[:100],
        "resultsPerPage": str(max(1, min(10, results))),
    })
    url = f"{_NVD_BASE}?{q}"
    headers = {
        "User-Agent": "FAFO-TaskManagerPro/1.0 (local toolbox; +https://github.com/)",
        "Accept": "application/json",
    }
    if api_key:
        headers["apiKey"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        return [{"error": str(e), "keyword": keyword}]

    out = []
    for item in payload.get("vulnerabilities") or []:
        cve = item.get("cve") or {}
        cve_id = cve.get("id") or ""
        descs = cve.get("descriptions") or []
        desc = ""
        for d in descs:
            if d.get("lang") == "en":
                desc = d.get("value") or ""
                break
        if not desc and descs:
            desc = descs[0].get("value") or ""
        metrics = cve.get("metrics") or {}
        score = None
        severity = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            arr = metrics.get(key) or []
            if arr:
                cvss = (arr[0].get("cvssData") or {})
                score = cvss.get("baseScore")
                severity = cvss.get("baseSeverity") or arr[0].get("baseSeverity")
                break
        out.append({
            "id": cve_id,
            "description": (desc or "")[:400],
            "score": score,
            "severity": severity,
            "keyword": keyword,
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}" if cve_id else None,
        })
    return out


def weekly_intel_refresh(
    *,
    force: bool = False,
    max_apps: int = 25,
    only_seen_since_days: int | None = 7,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    For apps seen on this PC, refresh NVD keyword hits if last check > 7 days (or force).
    Prefer apps seen in the last week when only_seen_since_days is set.
    """
    seen = _load_json(_seen_path(), {"apps": {}})
    apps: dict[str, Any] = seen.get("apps") or {}
    # seed from current processes
    try:
        live = net.list_processes(limit=200)
        for p in live.get("processes") or []:
            record_seen_apps([p.get("name") or ""])
        seen = _load_json(_seen_path(), {"apps": {}})
        apps = seen.get("apps") or {}
    except Exception:
        pass

    kb = load_knowledge()
    cache = _load_json(_vuln_cache_path(), {"by_key": {}, "meta": {}})
    by_key: dict[str, Any] = cache.setdefault("by_key", {})
    now = time.time()
    now_iso = _utc_now()

    candidates = []
    for key, entry in apps.items():
        last = entry.get("last_vuln_check")
        last_ts = 0.0
        if last:
            try:
                last_ts = datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp()
            except ValueError:
                last_ts = 0.0
        if not force and (now - last_ts) < _WEEK_SEC:
            continue
        if only_seen_since_days is not None:
            ls = entry.get("last_seen")
            if ls:
                try:
                    ls_ts = datetime.fromisoformat(ls.replace("Z", "+00:00")).timestamp()
                    if now - ls_ts > only_seen_since_days * 86400 and not force:
                        # still allow rarely-seen apps if never checked
                        if last_ts > 0:
                            continue
                except ValueError:
                    pass
        candidates.append((key, entry, last_ts))

    # prioritize never-checked then recently seen
    candidates.sort(key=lambda t: (t[2] > 0, -(t[1].get("run_count") or 0)))
    candidates = candidates[: max(1, min(40, max_apps))]

    checked = []
    errors = []
    for key, entry, _ in candidates:
        info = _lookup_kb(entry.get("name") or key, kb)
        keywords = list((info or {}).get("product_keywords") or [key])
        keyword = keywords[0]
        # skip pure generic windows kernel names to reduce noise
        if keyword in ("windows",) and key in ("system", "csrss", "smss", "wininit"):
            entry["last_vuln_check"] = now_iso
            apps[key] = entry
            continue
        try:
            time.sleep(0.7)  # be kind to NVD public rate limits
            cves = _nvd_search(keyword, results=5, api_key=api_key)
            if cves and cves[0].get("error"):
                errors.append({"key": key, "error": cves[0]["error"]})
                # don't stamp success
                continue
            by_key[key] = {
                "checked_at": now_iso,
                "keyword": keyword,
                "cves": [c for c in cves if c.get("id")],
            }
            entry["last_vuln_check"] = now_iso
            apps[key] = entry
            checked.append({"key": key, "keyword": keyword, "cve_count": len(by_key[key]["cves"])})
        except Exception as e:
            errors.append({"key": key, "error": str(e)})

    seen["apps"] = apps
    seen["updated"] = now_iso
    _save_json(_seen_path(), seen)
    cache["by_key"] = by_key
    cache["meta"] = {
        "last_refresh": now_iso,
        "checked": len(checked),
        "errors": len(errors),
    }
    _save_json(_vuln_cache_path(), cache)

    return {
        "ok": True,
        "checked": checked,
        "errors": errors,
        "candidates_considered": len(candidates),
        "store": str(_store_dir()),
        "message": (
            f"Refreshed NVD intel for {len(checked)} app(s). "
            "Local knowledge base is always used for purpose/pros/cons; "
            "NVD only flags published CVEs by product keyword."
        ),
    }


def knowledge_stats() -> dict[str, Any]:
    kb = load_knowledge()
    seen = get_seen_apps()
    cache = _load_json(_vuln_cache_path(), {"by_key": {}, "meta": {}})
    return {
        "knowledge_version": kb.get("version"),
        "knowledge_updated": kb.get("updated"),
        "process_entries": len(kb.get("processes") or {}),
        "service_entries": len(kb.get("services") or {}),
        "seen_apps": seen.get("count"),
        "seen_store": seen.get("store"),
        "vuln_keys_cached": len(cache.get("by_key") or {}),
        "vuln_meta": cache.get("meta") or {},
        "strategy": {
            "local_kb": "Primary — purpose, disable pros/cons, baseline efficiency.",
            "live_metrics": "CPU/RAM from this PC — efficiency score.",
            "nvd": "Optional weekly keyword CVE check for apps that actually ran.",
            "not_used": "No commercial ProcessLibrary scrape; no cloud upload of process lists.",
        },
    }


def overview() -> dict[str, Any]:
    sys_ov = net.get_system_overview()
    ratings = list_ratings(limit=80)
    stats = knowledge_stats()
    return {
        "timestamp": _utc_now(),
        "system": sys_ov,
        "ratings_summary": ratings.get("summary"),
        "knowledge": stats,
    }
