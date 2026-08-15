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
    info = _probe_video_info(path)
    return int(info.get("width") or 0), int(info.get("height") or 0)


def _probe_video_info(path: Path) -> dict[str, Any]:
    """Probe size + bitrates for quality matching. Missing fields → 0/None."""
    empty: dict[str, Any] = {
        "width": 0,
        "height": 0,
        "v_bitrate": 0,
        "a_bitrate": 0,
        "format_bitrate": 0,
        "duration": 0.0,
        "size_bytes": 0,
        "pix_fmt": "",
        "color_space": "",
        "color_transfer": "",
        "color_primaries": "",
        "color_range": "",
    }
    ffprobe = find_ffprobe()
    try:
        empty["size_bytes"] = path.stat().st_size if path.is_file() else 0
    except OSError:
        pass
    if not ffprobe:
        return empty
    try:
        out = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=bit_rate,duration,size",
                "-show_entries",
                "stream=index,codec_type,width,height,bit_rate,pix_fmt,"
                "color_space,color_transfer,color_primaries,color_range",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, timeout=45,
        )
        data = json.loads(out.stdout or "{}")
        fmt = data.get("format") or {}
        try:
            empty["format_bitrate"] = int(float(fmt.get("bit_rate") or 0))
        except (TypeError, ValueError):
            empty["format_bitrate"] = 0
        try:
            empty["duration"] = float(fmt.get("duration") or 0)
        except (TypeError, ValueError):
            empty["duration"] = 0.0
        try:
            sz = int(float(fmt.get("size") or 0))
            if sz > 0:
                empty["size_bytes"] = sz
        except (TypeError, ValueError):
            pass

        for st in data.get("streams") or []:
            ctype = (st.get("codec_type") or "").lower()
            if ctype == "video" and not empty["width"]:
                try:
                    empty["width"] = max(0, int(st.get("width") or 0))
                    empty["height"] = max(0, int(st.get("height") or 0))
                except (TypeError, ValueError):
                    pass
                try:
                    empty["v_bitrate"] = int(float(st.get("bit_rate") or 0))
                except (TypeError, ValueError):
                    empty["v_bitrate"] = 0
                empty["pix_fmt"] = str(st.get("pix_fmt") or "")
                empty["color_space"] = str(st.get("color_space") or "")
                empty["color_transfer"] = str(st.get("color_transfer") or "")
                empty["color_primaries"] = str(st.get("color_primaries") or "")
                empty["color_range"] = str(st.get("color_range") or "")
            elif ctype == "audio" and not empty["a_bitrate"]:
                try:
                    empty["a_bitrate"] = int(float(st.get("bit_rate") or 0))
                except (TypeError, ValueError):
                    empty["a_bitrate"] = 0

        # Fallback: derive average bitrate from file size / duration
        if empty["format_bitrate"] <= 0 and empty["duration"] > 0.5 and empty["size_bytes"] > 1000:
            empty["format_bitrate"] = int(empty["size_bytes"] * 8 / empty["duration"])

        # Video bitrate often missing on VFR/MP4 — estimate from container − audio
        if empty["v_bitrate"] <= 0 and empty["format_bitrate"] > 0:
            ab = empty["a_bitrate"] or 160_000
            empty["v_bitrate"] = max(0, empty["format_bitrate"] - ab)

        # Still missing: size/duration estimate for video-only share of file
        if empty["v_bitrate"] <= 0 and empty["duration"] > 0.5 and empty["size_bytes"] > 1000:
            ab = empty["a_bitrate"] or 160_000
            est = int(empty["size_bytes"] * 8 / empty["duration"]) - ab
            empty["v_bitrate"] = max(0, est)

        return empty
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError, TypeError):
        return empty


# Named quality tiers — preserve detail on downscale (never upscale).
# Lower CRF = higher quality. Slower presets keep more fine detail.
# "match" = constrained-CRF near source Mbps (quality floor + maxrate), NOT pure ABR/CBR.
# Pure ABR with a bad probe produced splotchy 16-bit-looking macroblocks at HD.
_SCALE_QUALITY: dict[str, dict[str, Any]] = {
    "match": {
        "crf": 15,  # quality floor when rate control is active
        "preset": "slow",
        "audio_k": 320,
        "vp9_crf": 24,
        "x264_params": (
            "ref=5:bframes=6:me=umh:subme=9:trellis=1:aq-mode=3:aq-strength=0.9:"
            "psy-rd=1.0,0.15:deblock=-1,-1:rc-lookahead=60"
        ),
        "rate_mode": "match",
    },
    "archive": {
        "crf": 14,
        "preset": "slower",
        "audio_k": 320,
        "vp9_crf": 22,
        "x264_params": (
            "ref=6:bframes=8:me=umh:subme=10:trellis=2:aq-mode=3:aq-strength=0.9:"
            "psy-rd=1.0,0.15:deblock=-1,-1:rc-lookahead=60"
        ),
        "rate_mode": "crf",
    },
    "high": {
        "crf": 16,
        "preset": "slow",
        "audio_k": 256,
        "vp9_crf": 26,
        "x264_params": (
            "ref=5:bframes=6:me=umh:subme=9:trellis=1:aq-mode=3:aq-strength=0.85:"
            "psy-rd=1.0,0.12:deblock=-1,-1:rc-lookahead=40"
        ),
        "rate_mode": "crf",
    },
    "balanced": {
        "crf": 18,
        "preset": "medium",
        "audio_k": 224,
        "vp9_crf": 29,
        "x264_params": "aq-mode=3:aq-strength=0.8:psy-rd=1.0,0.1:deblock=-1,-1",
        "rate_mode": "crf",
    },
    "small": {
        "crf": 22,
        "preset": "fast",
        "audio_k": 160,
        "vp9_crf": 32,
        "x264_params": "aq-mode=2",
        "rate_mode": "crf",
    },
}


def _resolution_bitrate_floor(width: int, height: int) -> int:
    """
    Minimum video bits/s for clean HD/4K — prevents splotchy macroblocks when
    ffprobe under-reports bitrate or match mode would starve the encode.
    """
    px = max(0, int(width or 0)) * max(0, int(height or 0))
    if px <= 0:
        return 8_000_000
    # Rough quality floors (H.264 high profile, progressive):
    # 720p ~6, 1080p ~12, 1440p ~20, 4K ~35 Mbps
    if px >= 3840 * 2000:  # ~4K
        return 32_000_000
    if px >= 2560 * 1400:  # 1440p
        return 18_000_000
    if px >= 1920 * 1000:  # 1080p
        return 10_000_000
    if px >= 1280 * 700:  # 720p
        return 6_000_000
    return 4_000_000


def _output_dims_for_side(src_w: int, src_h: int, side: int, needs_scale: bool) -> tuple[int, int]:
    if src_w <= 0 or src_h <= 0:
        return 0, 0
    if not needs_scale:
        return src_w, src_h
    longest = max(src_w, src_h)
    if longest <= side:
        return src_w, src_h
    scale = side / float(longest)
    ow = max(2, int(round(src_w * scale)) // 2 * 2)
    oh = max(2, int(round(src_h * scale)) // 2 * 2)
    return ow, oh


def _target_video_bitrate(
    info: dict[str, Any],
    *,
    needs_scale: bool,
    side: int,
    bitrate_mode: str = "retain",
) -> int:
    """
    Choose target video bitrate (bits/s) used as a *ceiling* for constrained-CRF.
    - retain: near source video bitrate (more bits/pixel after crop/downscale)
    - proportional: scale bitrate by output pixel area / source area
    Always enforces a resolution floor so HD never starves into blocky garbage.
    """
    src_w = int(info.get("width") or 0)
    src_h = int(info.get("height") or 0)
    out_w, out_h = _output_dims_for_side(src_w, src_h, side, needs_scale)
    floor = _resolution_bitrate_floor(out_w or src_w, out_h or src_h)

    v_br = int(info.get("v_bitrate") or 0)
    if v_br <= 0:
        # Prefer a healthy resolution-based estimate over a flat 8 Mbps (crushed 4K)
        v_br = max(floor, int(floor * 1.15))

    mode = (bitrate_mode or "retain").lower().strip()
    if mode == "proportional" and needs_scale and src_w > 0 and src_h > 0:
        longest = max(src_w, src_h)
        if longest > side:
            scale = side / float(longest)
            out_px = (src_w * scale) * (src_h * scale)
            src_px = float(src_w * src_h)
            if src_px > 0:
                ratio = max(0.45, min(1.0, out_px / src_px))
                v_br = int(v_br * max(0.75, ratio))

    # Never go below resolution floor (kills 16-bit-looking block artifacts)
    v_br = max(floor, v_br)
    # Clamp: floor … 150 Mbps
    return max(floor, min(150_000_000, v_br))


def _color_flags(info: dict[str, Any]) -> list[str]:
    """Preserve source color tags when present; default HD to BT.709 limited."""
    cs = (info.get("color_space") or "").lower()
    ct = (info.get("color_transfer") or "").lower()
    cp = (info.get("color_primaries") or "").lower()
    cr = (info.get("color_range") or "").lower()

    # Normalize unknown / unspecified → BT.709 for HD+
    w = int(info.get("width") or 0)
    h = int(info.get("height") or 0)
    is_hd = max(w, h) >= 720

    def ok(tag: str) -> bool:
        return bool(tag) and tag not in ("unknown", "unspecified", "reserved", "nb")

    if not ok(cs) and is_hd:
        cs = "bt709"
    if not ok(ct) and is_hd:
        ct = "bt709"
    if not ok(cp) and is_hd:
        cp = "bt709"
    if not ok(cr):
        cr = "tv"

    flags: list[str] = []
    # ffmpeg accepts these as output metadata + encoder hints
    if ok(cs):
        flags += ["-colorspace", cs]
    if ok(ct):
        flags += ["-color_trc", ct]
    if ok(cp):
        flags += ["-color_primaries", cp]
    if ok(cr):
        # tv/pc → mpeg/jpeg for some tools; ffmpeg accepts tv/pc too
        flags += ["-color_range", "tv" if cr in ("tv", "mpeg", "limited") else "pc"]
    return flags


def _scale_vf(side: int, needs_scale: bool) -> str:
    """
    High-quality scale → yuv420p.
    full_chroma_int/inp + accurate_rnd reduce chroma splotch on downscale.
    """
    if needs_scale:
        return (
            f"scale='min({side},iw)':'min({side},ih)':"
            "force_original_aspect_ratio=decrease:"
            "flags=lanczos+accurate_rnd+full_chroma_int+full_chroma_inp:"
            "force_divisible_by=2,"
            "setsar=1,"
            "format=yuv420p"
        )
    # Fits but needs re-encode — even dimensions only, no resize softener
    return (
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:"
        "flags=lanczos+accurate_rnd+full_chroma_int+full_chroma_inp,"
        "setsar=1,format=yuv420p"
    )


def scale_max_side(
    src: str,
    max_side: int = 3840,
    output_dir: str | None = None,
    fmt: str = "mp4",
    crf: int | None = None,
    fps: int | None = None,
    quality: str = "high",
    copy_if_fits: bool = True,
    bitrate_mode: str = "retain",
    video_bitrate: int | None = None,
) -> dict[str, Any]:
    """
    Cap longest side to max_side (never upscale). High-quality lanczos downscale.
    If already within cap and copy_if_fits, remux/stream-copy to avoid generational loss.

    quality:
      match    — encode near source video bitrate (best detail retention vs CRF shrink)
      archive / high / balanced / small — CRF tiers
    bitrate_mode (when quality=match or video_bitrate set):
      retain       — keep source Mbps (recommended after crop/scale)
      proportional — scale Mbps with pixel area
    video_bitrate — optional explicit target bits/s (overrides probe)
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
    # aliases
    if qkey in ("match-source", "source", "bitrate", "same"):
        qkey = "match"
    if qkey not in _SCALE_QUALITY:
        qkey = "high"
    q = _SCALE_QUALITY[qkey]
    rate_mode = str(q.get("rate_mode") or "crf")
    # Explicit crf overrides named tier when provided (still used as CQ fallback)
    crf_i = int(crf) if crf is not None else int(q["crf"])
    # Allow archive-grade CRF 12; still clamp absurd values
    crf_i = max(12, min(32, crf_i))
    preset = str(q["preset"])
    audio_k = int(q["audio_k"])
    vp9_crf = int(q["vp9_crf"])
    x264_params = str(q.get("x264_params") or "")

    out_dir = Path(output_dir).expanduser().resolve() if output_dir else src_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    info = _probe_video_info(src_path)
    src_w = int(info.get("width") or 0)
    src_h = int(info.get("height") or 0)
    longest = max(src_w, src_h) if src_w and src_h else 0
    needs_scale = True
    if longest > 0 and longest <= side:
        needs_scale = False

    tag = f"{side}max" if needs_scale else "fit"
    dest = out_dir / f"{src_path.stem}_{tag}.{fmt}"

    # Already within cap → stream copy when possible (true zero quality loss)
    can_copy = (
        copy_if_fits
        and not needs_scale
        and fps in (None, 0)
        and (
            (fmt == "mp4" and src_path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"})
            or (fmt == "webm" and src_path.suffix.lower() in {".webm", ".mkv"})
        )
    )

    target_v_br = 0
    if video_bitrate is not None and int(video_bitrate) > 0:
        ow, oh = _output_dims_for_side(src_w, src_h, side, needs_scale)
        floor = _resolution_bitrate_floor(ow or src_w, oh or src_h)
        target_v_br = max(floor, min(150_000_000, int(video_bitrate)))
    elif rate_mode == "match":
        target_v_br = _target_video_bitrate(
            info, needs_scale=needs_scale, side=side, bitrate_mode=bitrate_mode or "retain"
        )

    color_flags = _color_flags(info)

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
        vf = _scale_vf(side, needs_scale)
        # High-quality software scaler + avoid limited/full range surprises
        cmd = [
            ffmpeg, "-y",
            "-i", str(src_path),
            "-vf", vf,
            "-sws_flags", "lanczos+accurate_rnd+full_chroma_int+full_chroma_inp",
        ]
        if fps and int(fps) > 0:
            cmd += ["-r", str(int(fps))]

        use_match = target_v_br > 0 and rate_mode == "match"

        if fmt == "webm":
            if use_match:
                # Constrained quality: CRF floor + maxrate ceiling (not pure CBR)
                cmd += [
                    "-c:v", "libvpx-vp9",
                    "-crf", str(max(15, min(35, vp9_crf))),
                    "-b:v", str(target_v_br),
                    "-maxrate", str(int(target_v_br * 1.5)),
                    "-minrate", "0",
                    "-row-mt", "1",
                    "-tile-columns", "2",
                    "-frame-parallel", "1",
                    "-c:a", "libopus", "-b:a", f"{audio_k}k",
                ]
                method = "match-cq" if needs_scale else "match-cq-fit"
            else:
                cmd += [
                    "-c:v", "libvpx-vp9",
                    "-crf", str(max(15, min(40, vp9_crf if crf is None else min(40, crf_i + 6)))),
                    "-b:v", "0",
                    "-row-mt", "1",
                    "-tile-columns", "2",
                    "-frame-parallel", "1",
                    "-c:a", "libopus", "-b:a", f"{audio_k}k",
                ]
                method = "encode" if needs_scale else "reencode-fit"
        else:
            # H.264 high — quality-first
            cmd += [
                "-c:v", "libx264",
                "-preset", preset,
                "-profile:v", "high",
                "-level", "5.2",
                "-pix_fmt", "yuv420p",
            ]
            if use_match:
                # Constrained CRF: never drop below quality floor; maxrate ≈ source/probe
                # Pure ABR caused blocky posterization when probe under-reported Mbps.
                cmd += [
                    "-crf", str(crf_i),
                    "-maxrate", str(int(target_v_br * 1.35)),
                    "-bufsize", str(int(target_v_br * 2.5)),
                ]
                method = "match-crf" if needs_scale else "match-crf-fit"
            else:
                cmd += ["-crf", str(crf_i)]
                # Soft maxrate so complex scenes don't explode size, still quality-first
                ow, oh = _output_dims_for_side(src_w, src_h, side, needs_scale)
                soft_cap = max(
                    _resolution_bitrate_floor(ow or src_w, oh or src_h) * 3,
                    25_000_000,
                )
                cmd += [
                    "-maxrate", str(soft_cap),
                    "-bufsize", str(int(soft_cap * 2)),
                ]
                method = "encode" if needs_scale else "reencode-fit"
            if x264_params:
                cmd += ["-x264-params", x264_params]
            cmd += color_flags
            # Prefer audio stream copy when source has AAC (avoids second-gen audio loss)
            src_ext = src_path.suffix.lower()
            if src_ext in {".mp4", ".m4v", ".mov", ".mkv"} and use_match:
                cmd += ["-c:a", "copy"]
            else:
                cmd += ["-c:a", "aac", "-b:a", f"{audio_k}k"]
            cmd += ["-movflags", "+faststart"]
        cmd.append(str(dest))

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
        vf = _scale_vf(side, needs_scale=False)
        cmd = [
            ffmpeg, "-y", "-i", str(src_path),
            "-vf", vf,
            "-sws_flags", "lanczos+accurate_rnd+full_chroma_int+full_chroma_inp",
            "-c:v", "libx264", "-preset", preset,
            "-profile:v", "high", "-level", "5.2", "-pix_fmt", "yuv420p",
            "-crf", str(crf_i),
        ]
        if target_v_br > 0:
            cmd += [
                "-maxrate", str(int(target_v_br * 1.35)),
                "-bufsize", str(int(target_v_br * 2.5)),
            ]
            method = "match-crf-fit"
        else:
            method = "reencode-fit"
        if x264_params:
            cmd += ["-x264-params", x264_params]
        cmd += color_flags
        cmd += ["-c:a", "aac", "-b:a", f"{audio_k}k", "-movflags", "+faststart", str(dest)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("ffmpeg timed out") from e

    # Audio copy can fail if source audio isn't AAC-compatible in MP4 — retry with AAC
    if (
        not can_copy
        and proc.returncode != 0
        and target_v_br > 0
        and fmt == "mp4"
        and "-c:a" in cmd
        and "copy" in cmd
    ):
        try:
            if dest.is_file():
                dest.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            pass
        # rebuild last video args with AAC
        cmd_retry = [c for c in cmd]
        try:
            ia = cmd_retry.index("-c:a")
            # replace copy with aac
            if ia + 1 < len(cmd_retry) and cmd_retry[ia + 1] == "copy":
                cmd_retry[ia + 1] = "aac"
                cmd_retry.insert(ia + 2, "-b:a")
                cmd_retry.insert(ia + 3, f"{audio_k}k")
        except ValueError:
            pass
        try:
            proc = subprocess.run(cmd_retry, capture_output=True, text=True, timeout=7200)
            cmd = cmd_retry
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("ffmpeg timed out") from e

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
        "source_v_bitrate": int(info.get("v_bitrate") or 0),
        "target_v_bitrate": target_v_br or None,
        "bitrate_mode": (bitrate_mode or "retain") if target_v_br else None,
        "scaled": needs_scale,
        "error": (proc.stderr or "")[-800:] if not ok else "",
        "cmd": " ".join(cmd),
    }