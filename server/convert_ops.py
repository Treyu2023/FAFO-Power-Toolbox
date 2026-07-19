"""Batch Media Converter — FFmpeg-powered batch transcode."""
from __future__ import annotations

import json
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from media_ops import find_ffmpeg, find_ffprobe

ProgressFn = Callable[[str, dict[str, Any] | None], None]

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".m4v", ".ts", ".mpeg", ".mpg"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"}

PRESETS = {
    "mp4_h264": {"label": "MP4 H.264", "args": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k"]},
    "mp4_fast": {"label": "MP4 Fast (copy)", "args": ["-c", "copy"]},
    "webm": {"label": "WebM VP9", "args": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"]},
    "audio_mp3": {"label": "MP3 Audio", "args": ["-vn", "-c:a", "libmp3lame", "-b:a", "320k"]},
    "audio_aac": {"label": "AAC Audio", "args": ["-vn", "-c:a", "aac", "-b:a", "256k"]},
    "gif": {"label": "GIF (short clips)", "args": ["-vf", "fps=10,scale=480:-1:flags=lanczos", "-t", "10"]},
}

_jobs: dict[str, dict[str, Any]] = {}


def list_presets() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in PRESETS.items()]


def _probe_duration(ffmpeg: str, path: Path) -> float | None:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError):
        return None


def scan_folder(folder: str, recursive: bool = True) -> dict[str, Any]:
    base = Path(folder).resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    files = []
    exts = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT
    iterator = base.rglob("*") if recursive else base.iterdir()
    for p in iterator:
        if p.is_file() and p.suffix.lower() in exts:
            try:
                st = p.stat()
                files.append({
                    "path": str(p),
                    "name": p.name,
                    "ext": p.suffix.lower(),
                    "size": st.st_size,
                    "type": "video" if p.suffix.lower() in VIDEO_EXT else "audio" if p.suffix.lower() in AUDIO_EXT else "image",
                })
            except OSError:
                pass
    files.sort(key=lambda x: x["name"].lower())
    return {"folder": str(base), "count": len(files), "files": files}


def _output_path(src: Path, out_dir: Path | None, preset: str) -> Path:
    ext_map = {"mp4_h264": ".mp4", "mp4_fast": ".mp4", "webm": ".webm", "audio_mp3": ".mp3", "audio_aac": ".m4a", "gif": ".gif"}
    new_ext = ext_map.get(preset, ".mp4")
    dest_dir = out_dir or src.parent
    return dest_dir / f"{src.stem}_converted{new_ext}"


def convert_batch(
    files: list[str],
    preset: str = "mp4_h264",
    output_dir: str | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found — install ffmpeg and add to PATH")

    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")

    job_id = str(uuid.uuid4())[:8]
    out_path = Path(output_dir).resolve() if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(files)
    for i, f in enumerate(files):
        src = Path(f)
        if not src.is_file():
            results.append({"input": f, "ok": False, "error": "not found"})
            continue
        dest = _output_path(src, out_path, preset)
        if on_progress:
            on_progress(f"Converting {src.name} ({i+1}/{total})…", {"index": i, "total": total, "file": src.name})

        cmd = [ffmpeg, "-y", "-i", str(src)] + PRESETS[preset]["args"] + [str(dest)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            ok = proc.returncode == 0 and dest.exists()
            results.append({
                "input": str(src),
                "output": str(dest) if ok else None,
                "ok": ok,
                "error": proc.stderr[-500:] if not ok else "",
            })
        except subprocess.TimeoutExpired:
            results.append({"input": str(src), "ok": False, "error": "timeout"})

    succeeded = sum(1 for r in results if r["ok"])
    job = {
        "job_id": job_id,
        "preset": preset,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "results": results,
    }
    _jobs[job_id] = job
    if on_progress:
        on_progress(f"Done — {succeeded}/{total} converted", {"job_id": job_id})
    return job


def get_job(job_id: str) -> dict[str, Any]:
    if job_id not in _jobs:
        raise FileNotFoundError("Job not found")
    return _jobs[job_id]