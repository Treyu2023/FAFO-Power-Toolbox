"""VSR two-stage pipeline: smart matching, adaptive naming, batch rename."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from db import connect
from media_ops import sanitize_name
from video_probe import probe_video, res_tier

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".flv", ".ts"}

DEFAULT_PIPELINE = {
    "folder_source": "",
    "folder_stage1": "",
    "folder_stage2": "",
    "template_stage1": "UpScale{res_tier}_{orig}_S_I",
    "template_stage2": "Interp{fps}_{res}_{orig}_S_II",
    "include_date": False,
    "include_time": False,
    "date_source": "mtime",
    "duration_tolerance": 0.35,
    "min_match_score": 0.52,
    "learned_strip_suffixes": [],
    "learned_strip_prefixes": [],
    "custom_tokens": {},
}


def get_pipeline_config() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='vsr_pipeline'").fetchone()
    if row:
        cfg = {**DEFAULT_PIPELINE, **json.loads(row["value"])}
    else:
        cfg = dict(DEFAULT_PIPELINE)
    return cfg


def save_pipeline_config(cfg: dict) -> dict:
    merged = {**DEFAULT_PIPELINE, **cfg}
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("vsr_pipeline", json.dumps(merged)),
        )
    return merged


def list_videos(folder: str) -> list[dict]:
    root = Path(folder)
    if not root.is_dir():
        return []
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in VIDEO_EXT:
            files.append({"path": str(p), "name": p.name, "rel": str(p.relative_to(root))})
    return files


def _stem(name: str) -> str:
    return Path(name).stem


def _ext(name: str) -> str:
    return Path(name).suffix


def strip_learned(name: str, cfg: dict) -> str:
    stem = _stem(name)
    for suf in cfg.get("learned_strip_suffixes", []):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    for pre in cfg.get("learned_strip_prefixes", []):
        if stem.startswith(pre):
            stem = stem[len(pre):]
    return stem


def learn_from_pairs(pairs: list[dict], cfg: dict | None = None) -> dict:
    """pairs: [{source_path, output_path}, ...] — infer strip patterns."""
    cfg = cfg or get_pipeline_config()
    suffixes: set[str] = set(cfg.get("learned_strip_suffixes", []))
    prefixes: set[str] = set(cfg.get("learned_strip_prefixes", []))

    for pair in pairs:
        src = Path(pair["source_path"]).stem
        out = Path(pair["output_path"]).stem
        if src in out:
            idx = out.find(src)
            if idx > 0:
                prefixes.add(out[:idx])
            tail = out[idx + len(src):]
            if tail:
                suffixes.add(tail)
        else:
            sm = SequenceMatcher(None, src.lower(), out.lower())
            match = sm.find_longest_match(0, len(src), 0, len(out))
            if match.size >= len(src) * 0.5:
                if match.b > 0:
                    prefixes.add(out[: match.b])
                end = match.b + match.size
                if end < len(out):
                    suffixes.add(out[end:])

    cfg["learned_strip_suffixes"] = sorted(suffixes, key=len, reverse=True)[:20]
    cfg["learned_strip_prefixes"] = sorted(prefixes, key=len, reverse=True)[:20]
    return save_pipeline_config(cfg)


def match_score(source: dict, candidate: dict, cfg: dict) -> float:
    sp = source.get("probe") or probe_video(source["path"])
    cp = candidate.get("probe") or probe_video(candidate["path"])
    score = 0.0

    sd, cd = sp.get("duration", 0), cp.get("duration", 0)
    if sd > 0 and cd > 0:
        diff = abs(sd - cd) / max(sd, cd)
        tol = float(cfg.get("duration_tolerance", 0.35))
        if diff <= tol:
            score += 0.45 * (1 - diff / tol)
        elif diff <= tol * 2:
            score += 0.15

    if sp.get("aspect") and cp.get("aspect"):
        ad = abs(sp["aspect"] - cp["aspect"])
        if ad < 0.05:
            score += 0.15

    src_stem = strip_learned(source["name"], cfg).lower()
    out_stem = strip_learned(candidate["name"], cfg).lower()
    name_ratio = SequenceMatcher(None, src_stem, out_stem).ratio()
    score += 0.25 * name_ratio

    if src_stem in out_stem or out_stem in src_stem:
        score += 0.1

    if sp.get("height") and cp.get("height") and cp["height"] >= sp["height"]:
        score += 0.05

    return min(1.0, score)


def greedy_match(sources: list[dict], outputs: list[dict], cfg: dict) -> list[dict]:
    for s in sources:
        s["probe"] = probe_video(s["path"])
    for o in outputs:
        o["probe"] = probe_video(o["path"])

    used_out: set[str] = set()
    matches = []
    min_score = float(cfg.get("min_match_score", 0.52))

    for src in sources:
        best = None
        best_score = 0.0
        for out in outputs:
            if out["path"] in used_out:
                continue
            sc = match_score(src, out, cfg)
            if sc > best_score:
                best_score = sc
                best = out
        if best and best_score >= min_score:
            used_out.add(best["path"])
            matches.append({
                "source": src,
                "output": best,
                "score": round(best_score, 3),
                "source_probe": src["probe"],
                "output_probe": best["probe"],
            })
    return matches


def apply_template(
    template: str,
    orig_name: str,
    probe: dict,
    stage: str,
    cfg: dict,
    source_probe: dict | None = None,
) -> str:
    orig_stem = strip_learned(orig_name, cfg)
    path = Path(orig_name)
    mtime = path.stat().st_mtime if path.exists() else time.time()
    dt = datetime.fromtimestamp(mtime)

    src_p = source_probe or probe
    tokens = {
        "orig": orig_stem,
        "orig_full": orig_name,
        "w": str(probe.get("width", 0)),
        "h": str(probe.get("height", 0)),
        "res": probe.get("res", "0x0"),
        "res_tier": probe.get("res_tier", res_tier(probe.get("height", 0))),
        "fps": probe.get("fps_label", "0"),
        "fps_raw": str(probe.get("fps", 0)),
        "duration": f"{probe.get('duration', 0):.1f}",
        "stage": stage,
        "src_res": src_p.get("res", ""),
        "src_tier": src_p.get("res_tier", ""),
        "date": dt.strftime("%Y%m%d"),
        "time": dt.strftime("%H%M%S"),
        "datetime": dt.strftime("%Y%m%d_%H%M%S"),
    }
    if cfg.get("include_date") and "{date}" not in template:
        template += "_{date}"
    if cfg.get("include_time") and "{time}" not in template:
        template += "_{time}"

    for k, v in (cfg.get("custom_tokens") or {}).items():
        tokens[k] = v

    result = template
    for key, val in tokens.items():
        result = result.replace("{" + key + "}", str(val))
    result = sanitize_name(result)
    return result + _ext(orig_name) if not result.lower().endswith(_ext(orig_name).lower()) else result


def preview_pipeline(cfg: dict | None = None) -> dict:
    cfg = cfg or get_pipeline_config()
    result = {"stage1": [], "stage2": [], "unmatched_source": [], "unmatched_stage1": [], "config": cfg}

    if not cfg.get("folder_source"):
        return {**result, "error": "Set folder_source in pipeline config"}

    sources = list_videos(cfg["folder_source"])
    stage1_outs = list_videos(cfg["folder_stage1"]) if cfg.get("folder_stage1") else []
    stage2_outs = list_videos(cfg["folder_stage2"]) if cfg.get("folder_stage2") else []

    s1_matches = greedy_match(sources, stage1_outs, cfg) if stage1_outs else []
    matched_src_paths = {m["source"]["path"] for m in s1_matches}

    for m in s1_matches:
        new_name = apply_template(
            cfg["template_stage1"], m["source"]["name"],
            m["output"]["probe"], "I", cfg, m["source"]["probe"],
        )
        result["stage1"].append({
            **m,
            "proposed_name": new_name,
            "current_name": m["output"]["name"],
            "rename_needed": new_name != m["output"]["name"],
        })

    if stage2_outs and s1_matches:
        stage1_as_sources = [
            {"path": m["output"]["path"], "name": m["output"]["name"], "rel": m["output"].get("rel", "")}
            for m in s1_matches
        ]
        s2_matches = greedy_match(stage1_as_sources, stage2_outs, cfg)
        matched_s1 = {m["source"]["path"] for m in s2_matches}
        for m in s2_matches:
            orig = next((x for x in s1_matches if x["output"]["path"] == m["source"]["path"]), None)
            orig_source_name = orig["source"]["name"] if orig else m["source"]["name"]
            new_name = apply_template(
                cfg["template_stage2"], orig_source_name,
                m["output"]["probe"], "II", cfg,
                orig["source"]["probe"] if orig else m["source"]["probe"],
            )
            result["stage2"].append({
                **m,
                "original_source": orig_source_name,
                "proposed_name": new_name,
                "current_name": m["output"]["name"],
                "rename_needed": new_name != m["output"]["name"],
            })
        result["unmatched_stage1"] = [s for s in stage1_as_sources if s["path"] not in matched_s1]
    elif stage2_outs:
        s2_direct = greedy_match(sources, stage2_outs, cfg)
        for m in s2_direct:
            new_name = apply_template(
                cfg["template_stage2"], m["source"]["name"],
                m["output"]["probe"], "II", cfg, m["source"]["probe"],
            )
            result["stage2"].append({
                **m,
                "original_source": m["source"]["name"],
                "proposed_name": new_name,
                "current_name": m["output"]["name"],
                "rename_needed": new_name != m["output"]["name"],
            })

    result["unmatched_source"] = [s for s in sources if s["path"] not in matched_src_paths]
    return result


def apply_renames(renames: list[dict], dry_run: bool = False) -> list[dict]:
    """renames: [{path, new_name}]"""
    results = []
    for item in renames:
        src = Path(item["path"])
        if not src.exists():
            results.append({"path": item["path"], "ok": False, "error": "missing"})
            continue
        dst = src.parent / item["new_name"]
        if dst.exists() and dst != src:
            results.append({"path": item["path"], "ok": False, "error": f"exists: {item['new_name']}"})
            continue
        if dry_run:
            results.append({"path": item["path"], "ok": True, "new_path": str(dst), "dry_run": True})
            continue
        try:
            src.rename(dst)
            results.append({"path": item["path"], "ok": True, "new_path": str(dst)})
        except Exception as e:
            results.append({"path": item["path"], "ok": False, "error": str(e)})
    return results


def apply_pipeline_stage(stage: str, cfg: dict | None = None, dry_run: bool = False) -> dict:
    preview = preview_pipeline(cfg)
    key = "stage1" if stage in ("1", "stage1", "I") else "stage2"
    renames = [
        {"path": item["output"]["path"], "new_name": item["proposed_name"]}
        for item in preview.get(key, [])
        if item.get("rename_needed")
    ]
    results = apply_renames(renames, dry_run=dry_run)
    return {"stage": key, "count": len(results), "results": results, "preview": preview[key]}