"""
Guided pair learning — remember naming schemes from confirmed pairs.

As users lock before/after pairs, we learn:
  • tokens that usually appear only on AFTER names (upscaled, 60fps, …)
  • tokens that usually appear only on BEFORE names
  • intermediate / stage-2 leftovers to skip (huge unplayable mid-pipeline files)
  • typical after/before size ratios

Applied when ranking candidates so matching gets smarter after a few pairs.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

LEARN_PATH = Path(__file__).resolve().parent / "data" / "pair_learn_v1.json"

# Seed knowledge for VSR-style pipelines (stage 1 source ↔ stage 3 final)
SEED_AFTER_ONLY = {
    "upscaled", "upscale", "vsr", "flash", "flashvsr", "interp", "interpolated",
    "enhanced", "4k", "8k", "uhd", "fhd", "2160p", "1440p", "1080p", "720p",
    "fps", "24fps", "25fps", "30fps", "48fps", "50fps", "60fps", "120fps",
    "x2", "x4", "out", "final", "stage3", "s3", "pass3",
}
SEED_SKIP = {
    # Stage-2 / intermediate leftovers — usually huge, often not playable
    "stage2", "stage_2", "stage-2", "s2", "pass2", "pass_2",
    "intermediate", "intermed", "temp", "tmp", "chunked", "chunk",
    "partial", "processing", "workdir", "scratch", "raw_vsr",
    "tile", "tiles", "cache",
}
SEED_BEFORE_ONLY = {
    "source", "src", "original", "orig", "raw", "before", "input",
    "stage1", "stage_1", "s1", "pass1",
}

# Generic tokens never useful as scheme signals
STOP = {
    "the", "and", "for", "with", "from", "video", "image", "file", "copy",
    "new", "old", "mp4", "mkv", "mov", "avi", "webm", "png", "jpg", "jpeg",
}


def _empty_model() -> dict[str, Any]:
    return {
        "schema": 1,
        "pair_count": 0,
        "updated_at": None,
        "after_only": {},       # token -> count
        "before_only": {},
        "shared": {},
        "skip_tokens": {t: 2 for t in SEED_SKIP},  # seed with weight
        "size_ratios": [],     # after/before size ratio samples
        "recent": [],           # last N observations for UI
        "seed_after": sorted(SEED_AFTER_ONLY),
        "seed_skip": sorted(SEED_SKIP),
    }


def load_model() -> dict[str, Any]:
    try:
        if LEARN_PATH.is_file():
            raw = json.loads(LEARN_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                base = _empty_model()
                base.update(raw)
                # ensure counters are dicts
                for k in ("after_only", "before_only", "shared", "skip_tokens"):
                    if not isinstance(base.get(k), dict):
                        base[k] = {}
                if not isinstance(base.get("size_ratios"), list):
                    base["size_ratios"] = []
                if not isinstance(base.get("recent"), list):
                    base["recent"] = []
                return base
    except Exception:
        pass
    return _empty_model()


def save_model(model: dict[str, Any]) -> None:
    LEARN_PATH.parent.mkdir(parents=True, exist_ok=True)
    model["updated_at"] = time.time()
    LEARN_PATH.write_text(json.dumps(model, indent=2), encoding="utf-8")


def name_tokens(name: str) -> set[str]:
    """Extract scheme-relevant tokens from a filename."""
    stem = Path(name or "").stem.lower()
    toks: set[str] = set()
    # fps / resolution glued forms
    for m in re.finditer(r"\d{2,3}\s*fps|\d{3,4}\s*x\s*\d{3,4}|\d{3,4}p", stem):
        toks.add(re.sub(r"\s+", "", m.group(0)))
    # stage markers
    for m in re.finditer(r"stage[\s_\-]?[123]|pass[\s_\-]?[123]|s[123]\b", stem):
        toks.add(re.sub(r"[\s_\-]", "", m.group(0)))
    parts = re.split(r"[^a-z0-9]+", stem)
    for p in parts:
        if not p or len(p) < 2:
            continue
        if p in STOP:
            continue
        if p.isdigit() and len(p) >= 6:
            # long digit ids are shared keys, keep lightly
            toks.add(p)
            continue
        if p.isdigit() and len(p) <= 2:
            continue
        toks.add(p)
    return toks


def _bump(counter: dict[str, int], key: str, n: int = 1) -> None:
    counter[key] = int(counter.get(key) or 0) + n


def observe_pair(
    before_name: str,
    after_name: str,
    *,
    before_size: int = 0,
    after_size: int = 0,
    before_path: str = "",
    after_path: str = "",
    source: str = "guided",
) -> dict[str, Any]:
    """Learn from one confirmed before/after pair."""
    model = load_model()
    bt = name_tokens(before_name)
    at = name_tokens(after_name)
    only_after = at - bt
    only_before = bt - at
    shared = bt & at

    for t in only_after:
        _bump(model["after_only"], t)
        # If it looks like intermediate marker but appeared on a kept after, don't skip it
        if t in model.get("skip_tokens", {}) and t not in SEED_SKIP:
            model["skip_tokens"][t] = max(0, int(model["skip_tokens"].get(t) or 0) - 1)
    for t in only_before:
        _bump(model["before_only"], t)
    for t in shared:
        _bump(model["shared"], t)

    # Path folder hints — intermediate folders rarely hold finals
    for path, side in ((before_path, "before"), (after_path, "after")):
        parts = re.split(r"[/\\]+", (path or "").lower())
        for part in parts[-4:]:
            if not part:
                continue
            pt = name_tokens(part)
            if side == "after":
                for t in pt:
                    if t in SEED_AFTER_ONLY or "fps" in t or "upscale" in t:
                        _bump(model["after_only"], t)
            if any(s in part for s in ("stage2", "stage_2", "intermediate", "chunk", "temp")):
                _bump(model["skip_tokens"], "stage2")
                _bump(model["skip_tokens"], "intermediate")

    bs, az = int(before_size or 0), int(after_size or 0)
    if bs > 0 and az > 0 and az > bs:
        ratio = az / bs
        model["size_ratios"] = (model.get("size_ratios") or [])[-40:] + [round(ratio, 3)]

    model["pair_count"] = int(model.get("pair_count") or 0) + 1
    recent = model.get("recent") or []
    recent.insert(0, {
        "at": time.time(),
        "before": before_name,
        "after": after_name,
        "only_after": sorted(only_after)[:12],
        "only_before": sorted(only_before)[:12],
        "ratio": round(az / bs, 3) if bs and az > bs else None,
        "source": source,
    })
    model["recent"] = recent[:25]
    save_model(model)
    return model


def top_tokens(counter: dict[str, int], *, min_count: int = 1, limit: int = 20) -> list[tuple[str, int]]:
    items = [(k, int(v)) for k, v in (counter or {}).items() if int(v) >= min_count]
    items.sort(key=lambda x: (-x[1], x[0]))
    return items[:limit]


def after_marker_set(model: dict[str, Any] | None = None) -> set[str]:
    model = model or load_model()
    learned = {t for t, c in (model.get("after_only") or {}).items() if int(c) >= 1}
    return set(SEED_AFTER_ONLY) | learned


def skip_marker_set(model: dict[str, Any] | None = None) -> set[str]:
    model = model or load_model()
    learned = {t for t, c in (model.get("skip_tokens") or {}).items() if int(c) >= 1}
    return set(SEED_SKIP) | learned


def is_intermediate_leftover(
    name: str,
    *,
    size: int = 0,
    path: str = "",
    model: dict[str, Any] | None = None,
    peer_sizes: list[int] | None = None,
) -> bool:
    """True if this file looks like stage-2 / intermediate junk, not a pair side."""
    model = model or load_model()
    low = (name or "").lower()
    path_l = (path or "").lower()
    toks = name_tokens(name) | name_tokens(path_l)
    skip = skip_marker_set(model)

    # Strong name / path hits
    for s in skip:
        if s in low or s in path_l or s in toks:
            # stage3/final should not skip even if 'stage' substring — check carefully
            if s in ("s2", "stage2", "stage_2", "stage-2", "pass2", "intermediate", "chunked", "chunk"):
                return True
            if s in toks:
                return True

    # Explicit stage2 / intermediate path segments
    if re.search(r"stage[\s_\-]?2|pass[\s_\-]?2|(^|[/\\])s2([/\\]|$)", path_l):
        return True
    if re.search(r"stage[\s_\-]?2|pass[\s_\-]?2", low):
        return True

    # Huge vs typical learned after sizes — intermediate often enormous
    sz = int(size or 0)
    if sz > 0:
        # Absolute very large video-ish leftovers (> 8 GB) with mid markers nearby
        if sz >= 8 * 1024 ** 3 and any(x in low or x in path_l for x in ("vsr", "flash", "chunk", "tile", "stage")):
            return True
        # Relative: much larger than other candidates for this anchor
        if peer_sizes:
            peers = [p for p in peer_sizes if p and p > 0]
            if peers:
                med = sorted(peers)[len(peers) // 2]
                if med > 0 and sz > med * 4 and sz > 500 * 1024 * 1024:
                    return True

    return False


def looks_like_final_after(name: str, model: dict[str, Any] | None = None) -> bool:
    model = model or load_model()
    toks = name_tokens(name)
    after = after_marker_set(model)
    # fps / upscaled strongly suggest final or stage-1-upscale output
    if any(t in after for t in toks):
        return True
    if re.search(r"\d{2,3}fps", (name or "").lower()):
        return True
    return False


def looks_like_source_before(name: str, model: dict[str, Any] | None = None) -> bool:
    model = model or load_model()
    toks = name_tokens(name)
    after = after_marker_set(model)
    # Source usually lacks after-only process tokens
    if toks & after:
        return False
    if re.search(r"\d{2,3}fps|upscaled|stage[\s_\-]?2", (name or "").lower()):
        return False
    return True


def adjust_confidence(
    conf: float,
    *,
    before_name: str,
    after_name: str,
    before_size: int = 0,
    after_size: int = 0,
    model: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Boost/penalty conf from learned naming schemes. Returns (conf, reason tags)."""
    model = model or load_model()
    tags: list[str] = []
    c = float(conf)
    bt, at = name_tokens(before_name), name_tokens(after_name)
    after_marks = after_marker_set(model)
    before_only_learned = {
        t for t, n in (model.get("before_only") or {}).items() if int(n) >= 2
    }

    only_after = at - bt
    only_before = bt - at

    # After carries process tokens (fps, upscaled) that before lacks — classic 1→3
    hit_after = only_after & after_marks
    if hit_after:
        c = min(1.0, c + 0.06 + 0.02 * min(3, len(hit_after)))
        tags.append("learn_after_tokens:" + ",".join(sorted(hit_after)[:4]))

    # Before looking clean (no process tokens)
    if looks_like_source_before(before_name, model) and not looks_like_source_before(after_name, model):
        c = min(1.0, c + 0.04)
        tags.append("learn_source_after_roles")

    # Learned before-only tokens on the after side is a smell
    if only_after & before_only_learned:
        c *= 0.85
        tags.append("learn_before_token_on_after")

    # Size ratio near learned median
    ratios = model.get("size_ratios") or []
    bs, az = int(before_size or 0), int(after_size or 0)
    if ratios and bs > 0 and az > bs:
        med = sorted(ratios)[len(ratios) // 2]
        r = az / bs
        if med > 0 and 0.5 * med <= r <= 2.0 * med:
            c = min(1.0, c + 0.03)
            tags.append("learn_size_ratio")

    # Intermediate after name
    if is_intermediate_leftover(after_name, size=az, model=model):
        c *= 0.25
        tags.append("learn_skip_intermediate_after")

    return float(min(1.0, max(0.0, c))), tags


def summary(model: dict[str, Any] | None = None) -> dict[str, Any]:
    model = model or load_model()
    return {
        "pair_count": model.get("pair_count") or 0,
        "updated_at": model.get("updated_at"),
        "after_tokens": [{"token": t, "n": n} for t, n in top_tokens(model.get("after_only") or {}, min_count=1, limit=15)],
        "before_tokens": [{"token": t, "n": n} for t, n in top_tokens(model.get("before_only") or {}, min_count=1, limit=10)],
        "skip_tokens": [{"token": t, "n": n} for t, n in top_tokens(model.get("skip_tokens") or {}, min_count=1, limit=15)],
        "size_ratio_median": (
            sorted(model["size_ratios"])[len(model["size_ratios"]) // 2]
            if model.get("size_ratios") else None
        ),
        "recent": (model.get("recent") or [])[:8],
        "hints": [
            "After names often gain tokens like upscaled / NNfps (final process).",
            "Stage-2 intermediates are skipped (huge leftovers, not pair sides).",
            "Matching prefers source (stage 1) ↔ final (stage 3).",
        ],
    }


def reset_model() -> dict[str, Any]:
    model = _empty_model()
    save_model(model)
    return summary(model)
