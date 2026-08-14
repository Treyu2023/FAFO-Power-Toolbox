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


def list_dir_brief(folder: str, limit: int = 40) -> dict[str, Any]:
    """List recent files in an output folder (for FAFO VID TRIM)."""
    base = Path(folder).expanduser().resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    files = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        try:
            st = p.stat()
            files.append({
                "name": p.name,
                "path": str(p),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "ext": p.suffix.lower(),
            })
        except OSError:
            pass
    files.sort(key=lambda x: x["mtime"], reverse=True)
    lim = max(1, min(200, int(limit or 40)))
    return {
        "folder": str(base),
        "count": len(files),
        "files": files[:lim],
    }


def _probe_video_size(path: Path) -> tuple[int, int]:
    """Return (width, height) or (0, 0) if unknown."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        return 0, 0
    try:
        out = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        streams = data.get("streams") or []
        if not streams:
            return 0, 0
        w = int(streams[0].get("width") or 0)
        h = int(streams[0].get("height") or 0)
        return max(0, w), max(0, h)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError, TypeError):
        return 0, 0


# Named quality tiers — preserve detail on downscale (never upscale).
# Lower CRF = higher quality. Slower presets keep more fine detail.
_SCALE_QUALITY: dict[str, dict[str, Any]] = {
    "archive": {
        "crf": 15,
        "preset": "slower",
        "audio_k": 320,
        "vp9_crf": 24,
        "x264_params": "ref=6:bframes=8:me=umh:subme=10:trellis=2:aq-mode=3:aq-strength=0.9:psy-rd=1.0,0.15",
    },
    "high": {
        "crf": 17,
        "preset": "slow",
        "audio_k": 256,
        "vp9_crf": 28,
        "x264_params": "ref=5:bframes=6:me=umh:subme=9:trellis=1:aq-mode=3:aq-strength=0.8",
    },
    "balanced": {
        "crf": 20,
        "preset": "medium",
        "audio_k": 192,
        "vp9_crf": 31,
        "x264_params": "aq-mode=2",
    },
    "small": {
        "crf": 24,
        "preset": "fast",
        "audio_k": 160,
        "vp9_crf": 34,
        "x264_params": "",
    },
}


def scale_max_side(
    src: str,
    max_side: int = 3840,
    output_dir: str | None = None,
    fmt: str = "mp4",
    crf: int | None = None,
    fps: int | None = None,
    quality: str = "high",
    copy_if_fits: bool = True,
) -> dict[str, Any]:
    """
    Cap longest side to max_side (never upscale). High-quality lanczos downscale.
    If already within cap and copy_if_fits, remux/stream-copy to avoid generational loss.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found — install ffmpeg and add to PATH")

    src_path = Path(src).expanduser().resolve()
    if not src_path.is_file():
        raise FileNotFoundError(f"File not found: {src}")

    side = max(256, min(7680, int(max_side or 3840)))
    fmt = (fmt or "mp4").lower().lstrip(".")
    if fmt not in ("mp4", "webm"):
        fmt = "mp4"

    qkey = (quality or "high").lower().strip()
    if qkey not in _SCALE_QUALITY:
        qkey = "high"
    q = _SCALE_QUALITY[qkey]
    # Explicit crf overrides named tier when provided
    crf_i = int(crf) if crf is not None else int(q["crf"])
    crf_i = max(12, min(36, crf_i))
    preset = str(q["preset"])
    audio_k = int(q["audio_k"])
    vp9_crf = int(q["vp9_crf"])
    x264_params = str(q.get("x264_params") or "")

    out_dir = Path(output_dir).expanduser().resolve() if output_dir else src_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    src_w, src_h = _probe_video_size(src_path)
    longest = max(src_w, src_h) if src_w and src_h else 0
    needs_scale = True
    if longest > 0 and longest <= side:
        needs_scale = False

    tag = f"{side}max" if needs_scale else "fit"
    dest = out_dir / f"{src_path.stem}_{tag}.{fmt}"

    # Already within cap → stream copy when possible (no quality loss)
    # MP4 copy works for most masters; WebM copy only if source is already webm-like
    can_copy = (
        copy_if_fits
        and not needs_scale
        and fps in (None, 0)
        and (
            (fmt == "mp4" and src_path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"})
            or (fmt == "webm" and src_path.suffix.lower() in {".webm", ".mkv"})
        )
    )

    if can_copy and fmt == "mp4":
        cmd = [
            ffmpeg, "-y", "-i", str(src_path),
            "-map", "0:v:0", "-map", "0:a?",
            "-c", "copy",
            "-movflags", "+faststart",
            str(dest),
        ]
        method = "copy"
    elif can_copy and fmt == "webm":
        cmd = [
            ffmpeg, "-y", "-i", str(src_path),
            "-map", "0:v:0", "-map", "0:a?",
            "-c", "copy",
            str(dest),
        ]
        method = "copy"
    else:
        # Lanczos downscale only (decrease never enlarges). force_divisible_by=2 for codec friendliness.
        # accurate_rnd + full_chroma_int keep chroma detail on downscale.
        if needs_scale:
            vf = (
                f"scale='min({side},iw)':'min({side},ih)':"
                "force_original_aspect_ratio=decrease:"
                "flags=lanczos+accurate_rnd+full_chroma_int:"
                "force_divisible_by=2,"
                "setsar=1,"
                "format=yuv420p"
            )
        else:
            # Fits but needs re-encode (wrong container / fps cap) — no resize, just encode well
            vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=neighbor,setsar=1,format=yuv420p"

        cmd = [ffmpeg, "-y", "-i", str(src_path), "-vf", vf]
        if fps and int(fps) > 0:
            cmd += ["-r", str(int(fps))]

        if fmt == "webm":
            # VP9 CQ mode (b:v 0) — lower crf number is higher quality
            cmd += [
                "-c:v", "libvpx-vp9",
                "-crf", str(max(15, min(40, vp9_crf if crf is None else crf_i + 8))),
                "-b:v", "0",
                "-row-mt", "1",
                "-tile-columns", "2",
                "-frame-parallel", "1",
                "-c:a", "libopus", "-b:a", f"{audio_k}k",
            ]
        else:
            cmd += [
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf_i),
                "-profile:v", "high",
                "-level", "5.1",
                "-pix_fmt", "yuv420p",
            ]
            if x264_params:
                cmd += ["-x264-params", x264_params]
            cmd += [
                "-c:a", "aac", "-b:a", f"{audio_k}k",
                "-movflags", "+faststart",
            ]
        cmd.append(str(dest))
        method = "encode" if needs_scale else "reencode-fit"

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("ffmpeg timed out") from e

    # If stream-copy failed (incompatible codecs), retry with quality encode (still no upscale)
    if can_copy and (proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 500):
        try:
            if dest.is_file():
                dest.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            pass
        vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=neighbor,setsar=1,format=yuv420p"
        cmd = [
            ffmpeg, "-y", "-i", str(src_path), "-vf", vf,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf_i),
            "-profile:v", "high", "-pix_fmt", "yuv420p",
        ]
        if x264_params:
            cmd += ["-x264-params", x264_params]
        cmd += ["-c:a", "aac", "-b:a", f"{audio_k}k", "-movflags", "+faststart", str(dest)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("ffmpeg timed out") from e
        method = "reencode-fit"

    ok = proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 500
    return {
        "ok": ok,
        "input": str(src_path),
        "output": str(dest) if ok else None,
        "max_side": side,
        "format": fmt,
        "quality": qkey,
        "crf": crf_i,
        "preset": preset,
        "method": method,
        "source_w": src_w,
        "source_h": src_h,
        "scaled": needs_scale,
        "error": (proc.stderr or "")[-800:] if not ok else "",
        "cmd": " ".join(cmd),
    }