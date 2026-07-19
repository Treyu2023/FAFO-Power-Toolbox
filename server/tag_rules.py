"""Re-apply catalog tags after rescan / VSR rename using fingerprint + rules."""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from db import connect
from video_probe import probe_video

DEFAULT_RULES = {
    "enabled": True,
    "match_by_duration": True,
    "duration_tolerance": 0.3,
    "match_by_stem": True,
    "strip_patterns": [
        r"_S_I[I]?$",
        r"_upscaled?$",
        r"_vsr.*$",
        r"_flash.*$",
        r"_interp.*$",
        r"_\d{4}p$",
    ],
    "auto_tag_on_match": ["vsr-pipeline"],
    "preserve_notes": True,
}


def get_tag_rules() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='tag_rules'").fetchone()
    if row:
        return {**DEFAULT_RULES, **json.loads(row["value"])}
    return dict(DEFAULT_RULES)


def save_tag_rules(rules: dict) -> dict:
    merged = {**DEFAULT_RULES, **rules}
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("tag_rules", json.dumps(merged)),
        )
    return merged


def normalize_stem(name: str, rules: dict) -> str:
    stem = Path(name).stem
    for pat in rules.get("strip_patterns", []):
        stem = re.sub(pat, "", stem, flags=re.I)
    for suf in rules.get("manual_strip_suffixes", []):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    return stem.lower().strip("_-")


def fingerprint(path: Path) -> dict:
    pr = probe_video(path)
    return {
        "duration": pr.get("duration", 0),
        "aspect": pr.get("aspect", 0),
        "stem": normalize_stem(path.name, get_tag_rules()),
        "res": pr.get("res", ""),
    }


def apply_tag_rules_after_scan(dir_id: str | None = None) -> dict:
    from media_ops import get_all_media, resolve_path, update_media_meta

    rules = get_tag_rules()
    if not rules.get("enabled"):
        return {"applied": 0, "skipped": "disabled"}

    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM media WHERE tags != '[]' AND tags IS NOT NULL"
            + (" AND dir_id=?" if dir_id else ""),
            (dir_id,) if dir_id else (),
        ).fetchall()

    tagged_archive = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"] or "[]")
        try:
            p = resolve_path(d)
            if p.exists():
                tagged_archive.append({
                    "tags": d["tags"],
                    "notes": d.get("notes", ""),
                    "fp": fingerprint(p),
                    "stem": normalize_stem(d["name"], rules),
                })
        except Exception:
            pass

    current = get_all_media()
    if dir_id:
        current = [m for m in current if m["dir_id"] == dir_id]

    applied = 0
    for m in current:
        if m.get("tags"):
            continue
        try:
            p = resolve_path(m)
            if not p.exists():
                continue
            fp = fingerprint(p)
            stem = normalize_stem(m["name"], rules)
            best = None
            best_score = 0.0
            for arch in tagged_archive:
                score = 0.0
                if rules.get("match_by_stem"):
                    sr = SequenceMatcher(None, stem, arch["stem"]).ratio()
                    score += 0.4 * sr
                    if stem == arch["stem"]:
                        score += 0.3
                if rules.get("match_by_duration") and fp["duration"] and arch["fp"]["duration"]:
                    diff = abs(fp["duration"] - arch["fp"]["duration"]) / max(fp["duration"], arch["fp"]["duration"])
                    tol = rules.get("duration_tolerance", 0.3)
                    if diff <= tol:
                        score += 0.3 * (1 - diff / tol)
                if score > best_score:
                    best_score = score
                    best = arch
            if best and best_score >= 0.55:
                merged_tags = list(set(best["tags"] + rules.get("auto_tag_on_match", [])))
                notes = best["notes"] if rules.get("preserve_notes") else m.get("notes", "")
                update_media_meta(m["id"], tags=merged_tags, notes=notes)
                applied += 1
        except Exception:
            continue

    return {"applied": applied, "archive_size": len(tagged_archive)}