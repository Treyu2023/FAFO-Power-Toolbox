"""
Event Viewer Deep Dive — rank logged issue themes by how likely they are
real problems, and attach ordered fix alternatives (most → least likely).
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import event_ops as events

_DATA = Path(__file__).resolve().parent / "data"
_ADVICE_PATH = _DATA / "event_advice.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_advice() -> dict[str, Any]:
    try:
        return json.loads(_ADVICE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"themeAdvice": {}, "scoring": {}}


def _parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours_ago(iso: str | None) -> float | None:
    dt = _parse_time(iso)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600.0)


def _normalize_probs(fixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure likelihoods sum ~1 and sort high→low."""
    if not fixes:
        return []
    total = sum(float(f.get("likelihood") or 0) for f in fixes) or 1.0
    out = []
    for f in fixes:
        row = dict(f)
        row["likelihood"] = round(float(f.get("likelihood") or 0) / total, 3)
        row["likelihoodPercent"] = int(round(row["likelihood"] * 100))
        out.append(row)
    out.sort(key=lambda x: -x["likelihood"])
    # renumber ranks
    for i, f in enumerate(out, 1):
        f["rank"] = i
    return out


def _hardware_context() -> dict[str, Any]:
    try:
        import board_ops as board
        identity = board.detect_identity()
        intel = board.match_component_intel(identity)
        return {
            "board": (identity.get("board") or {}).get("product"),
            "cpu": (identity.get("cpu") or {}).get("name"),
            "gpus": [g.get("name") for g in (identity.get("gpus") or [])],
            "disks": [d.get("name") for d in (identity.get("disks") or [])],
            "problemDevices": [
                d.get("name") for d in (identity.get("devices") or []) if d.get("name")
            ][:12],
            "intel": intel.get("items") or [],
        }
    except Exception as e:
        return {"error": str(e), "problemDevices": [], "intel": [], "disks": [], "gpus": []}


def _theme_hardware_boost(theme_id: str, hw: dict[str, Any]) -> tuple[float, list[str]]:
    """Boost score when hardware inventory supports the theme."""
    reasons = []
    boost = 0.0
    disks = " ".join(hw.get("disks") or []).lower()
    gpus = " ".join(hw.get("gpus") or []).lower()
    problems = " ".join(hw.get("problemDevices") or []).lower()
    intel_ids = " ".join(i.get("id") or "" for i in (hw.get("intel") or [])).lower()
    intel_text = " ".join(
        f"{i.get('id')} {i.get('title')} {i.get('plainEnglish')}" for i in (hw.get("intel") or [])
    ).lower()

    if theme_id == "disk-retries":
        if any(x in disks for x in ("sandisk", "usb", "portable", "extreme")):
            boost += 12
            reasons.append("Portable/USB-class storage detected in inventory")
        if "sandisk" in intel_ids or "sandisk" in intel_text:
            boost += 8
            reasons.append("Curated notice matches SanDisk / portable SSD patterns")
    if theme_id == "usb-errors":
        if any(x in problems for x in ("bluetooth", "usb", "bt500", "hid")):
            boost += 14
            reasons.append("PnP problem devices include USB/Bluetooth-related names")
        if "bt" in intel_ids or "bluetooth" in intel_text:
            boost += 8
            reasons.append("Board/component intel mentions Bluetooth stack risk")
    if theme_id == "gpu-watchdog":
        if "nvidia" in gpus or "geforce" in gpus or "radeon" in gpus:
            boost += 6
            reasons.append("Discrete GPU present — TDR themes are relevant")
        if "4090" in gpus or "rtx" in gpus:
            boost += 4
            reasons.append("High-end NVIDIA GPU — driver TDRs are a known class of events")
    if theme_id == "ethernet-link":
        if "i226" in intel_text or "ethernet" in intel_text:
            boost += 6
            reasons.append("Intel LAN / ethernet noted on this machine")
    if theme_id == "kernel-power-41":
        if "14th" in (hw.get("cpu") or "").lower() or "14900" in (hw.get("cpu") or "").lower():
            boost += 5
            reasons.append("14th-gen Intel CPU — power/BIOS stability is a known watch item")
    return boost, reasons


def _score_theme(
    theme: dict[str, Any],
    *,
    total_events: int,
    scoring: dict[str, Any],
    hw: dict[str, Any],
) -> dict[str, Any]:
    level = theme.get("level") or "info"
    count = int(theme.get("count") or 0)
    err_c = int(theme.get("errorCount") or 0)
    tid = theme.get("id") or "unknown"

    level_w = (scoring.get("levelWeight") or {}).get(level, 8)
    # Frequency: log scale so 100 DCOM doesn't automatically win
    freq = 18 * math.log1p(count) if count else 0
    err_boost = min(25, err_c * 3)
    share = (count / total_events * 30) if total_events else 0

    noise = scoring.get("noiseThemes") or []
    noise_pen = float(scoring.get("noisePenalty") or 35) if tid in noise else 0.0

    # Recency
    hours = _hours_ago(theme.get("latestTime"))
    recent_h = float(scoring.get("recentBoostHours") or 6)
    recent = float(scoring.get("recentBoost") or 10) if hours is not None and hours <= recent_h else 0.0

    hw_boost, hw_reasons = _theme_hardware_boost(tid, hw)

    # ok-level themes are almost never "problems"
    is_noise = tid in noise or level == "ok"
    if level == "ok":
        noise_pen = max(noise_pen, 40)

    raw = level_w + freq + err_boost + share + recent + hw_boost - noise_pen
    raw = max(0.0, raw)

    # Hard-cap pure noise so volume never outranks real issues
    if is_noise and level in ("ok", "info"):
        raw = min(raw * 0.12, 18.0)
    elif is_noise:
        raw = raw * 0.35

    # Likelihood of being a *user-relevant problem* (0–100 scale before normalize)
    problem_likelihood = raw

    return {
        "rawScore": round(raw, 2),
        "problemLikelihood": problem_likelihood,
        "scoreBreakdown": {
            "severity": level_w,
            "frequency": round(freq, 2),
            "errors": err_boost,
            "shareOfSample": round(share, 2),
            "recency": recent,
            "hardware": hw_boost,
            "noisePenalty": -noise_pen,
        },
        "hardwareReasons": hw_reasons,
        "hoursSinceLatest": round(hours, 2) if hours is not None else None,
        "isLikelyNoise": tid in noise or level == "ok",
    }


def _attach_fixes(
    theme_id: str,
    advice_catalog: dict[str, Any],
    hw: dict[str, Any],
) -> dict[str, Any]:
    theme_adv = (advice_catalog.get("themeAdvice") or {}).get(theme_id) or (
        advice_catalog.get("themeAdvice") or {}
    ).get("unknown") or {}
    fixes = _normalize_probs(list(theme_adv.get("fixes") or []))

    # Nudge fix likelihoods using hardware
    problems = " ".join(hw.get("problemDevices") or []).lower()
    disks = " ".join(hw.get("disks") or []).lower()
    if theme_id == "usb-errors" and ("bluetooth" in problems or "bt" in problems):
        for f in fixes:
            if f.get("id") == "bt-stack":
                f["likelihood"] = min(0.55, f["likelihood"] + 0.12)
            elif f.get("id") == "port-power":
                f["likelihood"] = max(0.08, f["likelihood"] - 0.05)
        fixes = _normalize_probs(fixes)
    if theme_id == "disk-retries" and any(x in disks for x in ("sandisk", "extreme", "usb")):
        for f in fixes:
            if f.get("id") == "cable-port":
                f["likelihood"] = min(0.55, f["likelihood"] + 0.08)
        fixes = _normalize_probs(fixes)

    playbook = None
    pb_id = theme_adv.get("playbookId")
    if pb_id:
        try:
            import board_ops as board
            playbook = board.get_playbook(pb_id)
        except Exception:
            playbook = None

    board_name = hw.get("board") or "Windows 11 PC"
    search_q = f'{board_name} {theme_adv.get("symptom") or theme_id} fix'
    if playbook and playbook.get("searchQueryTemplate"):
        try:
            search_q = playbook["searchQueryTemplate"].format(
                board=board_name,
                cpu=hw.get("cpu") or "",
                gpu=(hw.get("gpus") or [""])[0] if hw.get("gpus") else "",
                disk=(hw.get("disks") or [""])[0] if hw.get("disks") else "",
                process="",
            )
        except (KeyError, ValueError, IndexError):
            pass

    return {
        "symptom": theme_adv.get("symptom") or "",
        "fixes": fixes,
        "playbookId": pb_id,
        "playbook": {
            "id": playbook.get("id"),
            "title": playbook.get("title"),
            "summary": playbook.get("summary"),
            "steps": playbook.get("steps"),
            "whenToStop": playbook.get("whenToStop"),
            "links": playbook.get("links"),
        } if playbook else None,
        "searchQuery": search_q,
        "searchUrl": "https://www.bing.com/search?q=" + quote_plus(search_q),
        "assistUrl": f"Hardware Board Map.html?assist=1&theme={theme_id}"
        + (f"&playbook={pb_id}" if pb_id else ""),
    }


def run_deep_dive(
    *,
    hours: int = 72,
    max_events: int = 600,
    include_noise: bool = True,
) -> dict[str, Any]:
    """
    Full deep dive payload for Event Viewer.
    Issues ranked most → least likely to be real problems.
    Each issue has fixes ranked most → least likely cause.
    """
    hours = max(1, min(int(hours), 168))
    max_events = max(50, min(int(max_events), 1000))

    # Fresh sample (bypass summary cache for deeper window)
    events.clear_cache()
    raw_events = events._query_events_raw(hours=hours, max_events=max_events)
    catalog = events._load_themes()
    themes = events._aggregate_themes(raw_events, catalog)
    advice = _load_advice()
    scoring = advice.get("scoring") or {}
    hw = _hardware_context()

    total = len(raw_events) or 1
    findings = []

    for th in themes:
        scored = _score_theme(th, total_events=total, scoring=scoring, hw=hw)
        if not include_noise and scored.get("isLikelyNoise") and (th.get("level") in ("ok", "info")):
            continue

        fixes_block = _attach_fixes(th.get("id") or "unknown", advice, hw)

        # Sample recent messages for this theme
        samples = []
        for ev in raw_events:
            matched = events._match_theme(ev, catalog)
            if (matched.get("id") or "") != (th.get("id") or ""):
                continue
            samples.append({
                "time": ev.get("time"),
                "provider": ev.get("provider"),
                "id": ev.get("id"),
                "level": ev.get("uiLevel") or ev.get("level"),
                "log": ev.get("log"),
                "message": (ev.get("message") or "")[:280],
            })
            if len(samples) >= 5:
                break

        top_fix = (fixes_block.get("fixes") or [{}])[0]
        findings.append({
            "themeId": th.get("id"),
            "title": th.get("title"),
            "plainEnglish": th.get("plainEnglish"),
            "care": th.get("care"),
            "level": th.get("level"),
            "count": th.get("count"),
            "errorCount": th.get("errorCount"),
            "warningCount": th.get("warningCount"),
            "providers": th.get("providers") or [],
            "latestTime": th.get("latestTime"),
            "problemScore": scored["rawScore"],
            "scoreBreakdown": scored["scoreBreakdown"],
            "hardwareReasons": scored["hardwareReasons"],
            "hoursSinceLatest": scored["hoursSinceLatest"],
            "isLikelyNoise": scored["isLikelyNoise"],
            "topFixSummary": top_fix.get("title"),
            "topFixLikelihoodPercent": top_fix.get("likelihoodPercent"),
            "advice": fixes_block,
            "sampleEvents": samples,
            "timelineUrl": f"Event Viewer.html?theme={th.get('id')}",
        })

    # Rank issues: highest problem score first; noise themes sink
    findings.sort(
        key=lambda f: (
            0 if f.get("isLikelyNoise") and f.get("level") in ("ok", "info") else 1,
            f.get("problemScore") or 0,
            f.get("count") or 0,
        ),
        reverse=True,
    )
    # Stable re-sort: primary by score descending among same noise class
    findings.sort(key=lambda f: (-(f.get("problemScore") or 0), 1 if f.get("isLikelyNoise") else 0))

    # Assign rank among actionable (non-noise) first, then noise
    actionable = [f for f in findings if not (f.get("isLikelyNoise") and f.get("level") in ("ok", "info"))]
    noise = [f for f in findings if f not in actionable]
    ranked = []
    for i, f in enumerate(actionable, 1):
        f = dict(f)
        f["rank"] = i
        f["tier"] = "investigate" if (f.get("level") in ("warn", "error") or (f.get("problemScore") or 0) >= 25) else "watch"
        ranked.append(f)
    for j, f in enumerate(noise, 1):
        f = dict(f)
        f["rank"] = len(actionable) + j
        f["tier"] = "noise"
        ranked.append(f)

    # Relative bar vs best *actionable* issue (not vs DCOM noise volume)
    top_score = max((f.get("problemScore") or 0) for f in actionable) if actionable else (
        max((f.get("problemScore") or 0) for f in ranked) if ranked else 1
    )
    top_score = top_score or 1
    for f in ranked:
        f["relativeLikelihoodPercent"] = int(min(100, round(100 * (f.get("problemScore") or 0) / top_score)))

    # Executive narrative
    top3 = [f for f in ranked if f.get("tier") != "noise"][:3]
    if not top3:
        headline = "No strong problem signals — mostly normal log noise"
        summary = (
            "The deep dive sampled recent errors and warnings. What remains looks like common Windows clutter "
            "(DCOM, ACPI, printer chatter). No high-likelihood fix path is required unless you feel a real symptom."
        )
    else:
        names = ", ".join(f.get("title") or f.get("themeId") for f in top3)
        headline = f"Top issues to consider: {names}"
        parts = []
        for f in top3:
            tf = f.get("topFixSummary") or "see fix list"
            pct = f.get("topFixLikelihoodPercent")
            parts.append(
                f"{f.get('title')}: most likely fix is “{tf}”"
                + (f" (~{pct}%)" if pct is not None else "")
            )
        summary = " · ".join(parts)

    return {
        "timestamp": _utc_now(),
        "supported": events.IS_WINDOWS,
        "windowHours": hours,
        "sampled": len(raw_events),
        "errorCount": sum(1 for e in raw_events if e.get("level") in ("error", "critical")),
        "warningCount": sum(1 for e in raw_events if e.get("level") == "warning"),
        "headline": headline,
        "summary": summary,
        "methodology": (
            "Issues are scored from severity, frequency (log-scaled), error share, recency, and hardware match, "
            "with penalties for known-noise themes (DCOM, ACPI, etc.). "
            "Each issue lists alternative fixes ordered most→least likely. "
            "This is heuristic advice — not a lab diagnosis."
        ),
        "hardware": {
            "board": hw.get("board"),
            "cpu": hw.get("cpu"),
            "gpus": hw.get("gpus"),
            "disks": hw.get("disks"),
            "problemDevices": hw.get("problemDevices"),
        },
        "findings": ranked,
        "actionableCount": len(actionable),
        "noiseCount": len(noise),
    }
