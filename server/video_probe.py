"""ffprobe helpers for resolution, fps, duration fingerprinting."""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

from media_ops import find_ffprobe

_probe_cache: dict[str, dict] = {}


def res_tier(height: int) -> str:
    if height >= 4320:
        return "8K"
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "2K-QHD"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    return f"{height}p"


def parse_fps(rate: str) -> float:
    if not rate or rate == "0/0":
        return 0.0
    if "/" in rate:
        a, b = rate.split("/", 1)
        return round(float(a) / float(b), 3) if float(b) else 0.0
    return float(rate)


def probe_video(path: str | Path, use_cache: bool = True) -> dict:
    path = str(Path(path).resolve())
    if use_cache and path in _probe_cache:
        return _probe_cache[path]

    ffprobe = find_ffprobe()
    info = {
        "path": path,
        "name": Path(path).name,
        "size": Path(path).stat().st_size if Path(path).exists() else 0,
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

    if not ffprobe or not Path(path).exists():
        info["error"] = "ffprobe missing or file not found"
        return info

    try:
        out = subprocess.run(
            [
                ffprobe, "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", path,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(out.stdout)
        vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        fmt = data.get("format", {})
        if vstream:
            info["width"] = int(vstream.get("width") or 0)
            info["height"] = int(vstream.get("height") or 0)
            fps = parse_fps(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0")
            info["fps"] = fps
            info["fps_label"] = str(int(round(fps))) if fps else "0"
            info["res"] = f"{info['width']}x{info['height']}"
            info["res_tier"] = res_tier(info["height"])
            if info["width"]:
                info["aspect"] = round(info["width"] / info["height"], 4)
        info["duration"] = float(fmt.get("duration") or vstream.get("duration") or 0)
    except Exception as e:
        info["error"] = str(e)

    if use_cache:
        _probe_cache[path] = info
    return info


def clear_probe_cache() -> None:
    _probe_cache.clear()