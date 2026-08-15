"""ffprobe helpers for resolution, fps, duration fingerprinting."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

from media_ops import find_ffprobe

# Bounded LRU so long library scans don't grow unbounded memory
_PROBE_CACHE_MAX = 512
_probe_cache: "OrderedDict[str, dict]" = OrderedDict()


def res_tier(height: int) -> str:
    h = max(0, int(height or 0))
    if h >= 4320:
        return "8K"
    if h >= 2160:
        return "4K"
    if h >= 1440:
        return "2K-QHD"
    if h >= 1080:
        return "1080p"
    if h >= 720:
        return "720p"
    if h > 0:
        return f"{h}p"
    return "?"


def parse_fps(rate: str) -> float:
    if not rate or rate in ("0/0", "N/A", "nan"):
        return 0.0
    try:
        if "/" in rate:
            a, b = rate.split("/", 1)
            den = float(b)
            if den == 0:
                return 0.0
            return round(float(a) / den, 3)
        return float(rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def probe_video(path: str | Path, use_cache: bool = True) -> dict:
    try:
        path = str(Path(path).expanduser().resolve())
    except OSError:
        path = str(path)

    if use_cache and path in _probe_cache:
        _probe_cache.move_to_end(path)
        return _probe_cache[path]

    ffprobe = find_ffprobe()
    p = Path(path)
    try:
        size = p.stat().st_size if p.is_file() else 0
    except OSError:
        size = 0

    info = {
        "path": path,
        "name": p.name,
        "size": size,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "fps_label": "0",
        "duration": 0.0,
        "res": "0x0",
        "res_tier": "?",
        "aspect": 0.0,
        "error": None,
    }

    if not ffprobe or not p.is_file():
        info["error"] = "ffprobe missing or file not found"
        return info

    try:
        run_kw: dict = dict(
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if sys.platform == "win32":
            run_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(
            [
                ffprobe, "-v", "error", "-print_format", "json",
                "-show_streams", "-show_format", path,
            ],
            **run_kw,
        )
        if out.returncode != 0 or not (out.stdout or "").strip():
            info["error"] = (out.stderr or "ffprobe failed").strip()[:300] or "ffprobe failed"
            return info
        data = json.loads(out.stdout)
        vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        fmt = data.get("format", {}) or {}
        if vstream:
            info["width"] = int(vstream.get("width") or 0)
            info["height"] = int(vstream.get("height") or 0)
            fps = parse_fps(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0")
            info["fps"] = fps
            info["fps_label"] = str(int(round(fps))) if fps else "0"
            info["res"] = f"{info['width']}x{info['height']}"
            info["res_tier"] = res_tier(info["height"])
            # Guard zero-height (corrupt / image-as-video streams)
            if info["width"] > 0 and info["height"] > 0:
                info["aspect"] = round(info["width"] / info["height"], 4)
        try:
            dur = fmt.get("duration")
            if dur is None and vstream:
                dur = vstream.get("duration")
            info["duration"] = float(dur or 0)
        except (TypeError, ValueError):
            info["duration"] = 0.0
    except subprocess.TimeoutExpired:
        info["error"] = "ffprobe timed out"
    except (json.JSONDecodeError, OSError, ValueError, TypeError) as e:
        info["error"] = str(e)

    if use_cache:
        _probe_cache[path] = info
        _probe_cache.move_to_end(path)
        while len(_probe_cache) > _PROBE_CACHE_MAX:
            _probe_cache.popitem(last=False)
    return info


def clear_probe_cache() -> None:
    _probe_cache.clear()