"""
Write / read Windows Explorer-visible file metadata (Tags + Rating).

Order of writers (first success wins for shell props; mutagen always tried as bonus):
  1. pywin32 IPropertyStore  → System.Keywords + System.Rating  (what Explorer shows)
  2. PowerShell + C# COM     → same property store without pywin32
  3. mutagen / ffmpeg        → embedded atoms (apps that read MP4 tags/comments)

Rating scale: UI stars 0–5 map to System.Rating 0 / 1 / 25 / 50 / 75 / 99.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger("aitoolbox.file_metadata")

# Windows Explorer star → System.Rating (UInt32)
STAR_TO_RATING = {0: 0, 1: 1, 2: 25, 3: 50, 4: 75, 5: 99}
RATING_TO_STAR = {0: 0, 1: 1, 25: 2, 50: 3, 75: 4, 99: 5}


def stars_to_system_rating(stars: int | None) -> int:
    if stars is None:
        return 0
    try:
        s = max(0, min(5, int(stars)))
    except (TypeError, ValueError):
        return 0
    return STAR_TO_RATING.get(s, 0)


def system_rating_to_stars(value: int | None) -> int:
    if value is None:
        return 0
    try:
        v = int(value)
    except (TypeError, ValueError):
        return 0
    if v in RATING_TO_STAR:
        return RATING_TO_STAR[v]
    if v <= 0:
        return 0
    # nearest bucket
    best = 0
    best_d = 999
    for rating, stars in RATING_TO_STAR.items():
        d = abs(rating - v)
        if d < best_d:
            best_d = d
            best = stars
    return best


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for t in tags:
        s = str(t).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def write_file_metadata(
    path: str | Path,
    tags: list[str] | None = None,
    rating: int | None = None,
) -> dict[str, Any]:
    """
    Write tags and/or rating into the real file so Explorer and other apps see them.

    Returns { ok, path, methods: [...], errors: [...], tags, rating }.
    """
    p = Path(path)
    result: dict[str, Any] = {
        "ok": False,
        "path": str(p),
        "methods": [],
        "errors": [],
        "tags": normalize_tags(tags) if tags is not None else None,
        "rating": None if rating is None else max(0, min(5, int(rating))),
    }
    if not p.is_file():
        result["errors"].append("File not found")
        return result

    tag_list = normalize_tags(tags) if tags is not None else None
    stars = result["rating"]

    # 1) Windows Property System (Explorer Tags + Rating columns)
    if sys.platform == "win32" and (tag_list is not None or stars is not None):
        if _write_shell_props_pywin32(p, tag_list, stars, result):
            pass
        elif _write_shell_props_powershell(p, tag_list, stars, result):
            pass

    # 2) Embedded containers (mutagen) — helps VLC/other tools + some handlers
    if tag_list is not None or stars is not None:
        if _write_mutagen(p, tag_list, stars, result):
            pass

    result["ok"] = len(result["methods"]) > 0
    if not result["ok"] and not result["errors"]:
        result["errors"].append("No writer succeeded for this file type")
    return result


def read_file_metadata(path: str | Path) -> dict[str, Any]:
    """Read tags + rating from file (shell first, then mutagen)."""
    p = Path(path)
    out: dict[str, Any] = {"path": str(p), "tags": [], "rating": 0, "methods": []}
    if not p.is_file():
        return out

    if sys.platform == "win32":
        shell = _read_shell_props(p)
        if shell:
            out["tags"] = shell.get("tags") or []
            out["rating"] = shell.get("rating") or 0
            out["methods"].append(shell.get("method", "shell"))

    if not out["tags"] or not out["rating"]:
        emb = _read_mutagen(p)
        if emb:
            if not out["tags"] and emb.get("tags"):
                out["tags"] = emb["tags"]
            if not out["rating"] and emb.get("rating"):
                out["rating"] = emb["rating"]
            out["methods"].append("mutagen")
    return out


# ---------------------------------------------------------------------------
# Windows Property System via pywin32
# ---------------------------------------------------------------------------

def _write_shell_props_pywin32(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    try:
        import pythoncom
        from win32com.propsys import propsys
        from win32com.shell import shellcon
    except ImportError:
        return False
    try:
        pythoncom.CoInitialize()
        try:
            ps = propsys.SHGetPropertyStoreFromParsingName(
                str(path), None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore
            )
            if tags is not None:
                pk = propsys.PSGetPropertyKeyFromName("System.Keywords")
                if tags:
                    ps.SetValue(pk, propsys.PROPVARIANTType(tags, pythoncom.VT_VECTOR | pythoncom.VT_BSTR))
                else:
                    # Clear keywords
                    try:
                        ps.SetValue(pk, propsys.PROPVARIANTType(None, pythoncom.VT_EMPTY))
                    except Exception:
                        ps.SetValue(pk, propsys.PROPVARIANTType([], pythoncom.VT_VECTOR | pythoncom.VT_BSTR))
            if stars is not None:
                pk_r = propsys.PSGetPropertyKeyFromName("System.Rating")
                rating_val = stars_to_system_rating(stars)
                if rating_val <= 0:
                    try:
                        ps.SetValue(pk_r, propsys.PROPVARIANTType(None, pythoncom.VT_EMPTY))
                    except Exception:
                        ps.SetValue(pk_r, propsys.PROPVARIANTType(0, pythoncom.VT_UI4))
                else:
                    ps.SetValue(pk_r, propsys.PROPVARIANTType(rating_val, pythoncom.VT_UI4))
            ps.Commit()
            result["methods"].append("shell-pywin32")
            return True
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        result["errors"].append(f"shell-pywin32: {e}")
        log.warning("shell-pywin32 write failed for %s: %s", path, e)
        return False


def _read_shell_props(path: Path) -> dict[str, Any] | None:
    try:
        import pythoncom
        from win32com.propsys import propsys
        from win32com.shell import shellcon
    except ImportError:
        return _read_shell_props_powershell(path)
    try:
        pythoncom.CoInitialize()
        try:
            ps = propsys.SHGetPropertyStoreFromParsingName(
                str(path), None, shellcon.GPS_DEFAULT, propsys.IID_IPropertyStore
            )
            tags: list[str] = []
            rating = 0
            try:
                pk = propsys.PSGetPropertyKeyFromName("System.Keywords")
                val = ps.GetValue(pk).GetValue()
                if val:
                    if isinstance(val, (list, tuple)):
                        tags = [str(x) for x in val if x]
                    else:
                        tags = [str(val)]
            except Exception:
                pass
            try:
                pk_r = propsys.PSGetPropertyKeyFromName("System.Rating")
                val = ps.GetValue(pk_r).GetValue()
                if val is not None:
                    rating = system_rating_to_stars(int(val))
            except Exception:
                pass
            return {"tags": tags, "rating": rating, "method": "shell-pywin32"}
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        return _read_shell_props_powershell(path)


# ---------------------------------------------------------------------------
# PowerShell + C# IPropertyStore fallback (no pywin32)
# ---------------------------------------------------------------------------

_PS_HELPER = r'''
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$TagsJson = $null,
  [string]$RatingStars = $null,
  [switch]$ReadOnly
)
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class ShellProps {
  [StructLayout(LayoutKind.Sequential, Pack=4)]
  public struct PROPERTYKEY {
    public Guid fmtid;
    public uint pid;
  }

  [StructLayout(LayoutKind.Sequential)]
  public struct PROPVARIANT {
    public ushort vt;
    public ushort wReserved1;
    public ushort wReserved2;
    public ushort wReserved3;
    public IntPtr p;
    public int p2;
  }

  [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IPropertyStore {
    uint GetCount(out uint cProps);
    uint GetAt(uint iProp, out PROPERTYKEY pkey);
    uint GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
    uint SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
    uint Commit();
  }

  [DllImport("shell32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  public static extern void SHGetPropertyStoreFromParsingName(
    string pszPath, IntPtr pbc, uint flags, ref Guid riid, out IPropertyStore ppv);

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  public static extern void PSGetPropertyKeyFromName(string pszName, out PROPERTYKEY ppropkey);

  [DllImport("ole32.dll")]
  public static extern int PropVariantClear(ref PROPVARIANT pvar);

  public const ushort VT_EMPTY = 0;
  public const ushort VT_UI4 = 19;
  public const ushort VT_LPWSTR = 31;
  public const ushort VT_VECTOR = 0x1000;
  public const uint GPS_DEFAULT = 0;
  public const uint GPS_READWRITE = 2;

  public static readonly Guid IID_IPropertyStore = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");

  public static IPropertyStore Open(string path, bool write) {
    Guid iid = IID_IPropertyStore;
    IPropertyStore ps;
    SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, write ? GPS_READWRITE : GPS_DEFAULT, ref iid, out ps);
    return ps;
  }

  public static void SetKeywords(IPropertyStore ps, string[] tags) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Keywords", out key);
    PROPVARIANT pv = new PROPVARIANT();
    if (tags == null || tags.Length == 0) {
      pv.vt = VT_EMPTY;
    } else {
      // VT_VECTOR|VT_LPWSTR via PropVariant helper in managed form is awkward;
      // set as semicolon-joined System.Comment fallback handled elsewhere.
      // Use InitPropVariantFromStringAsVector via propsys if available.
      InitStringVector(tags, out pv);
    }
    ps.SetValue(ref key, ref pv);
    PropVariantClear(ref pv);
  }

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  private static extern void InitPropVariantFromStringAsVector(
    [MarshalAs(UnmanagedType.LPArray, ArraySubType=UnmanagedType.LPWStr)] string[] prgsz,
    uint cElems, out PROPVARIANT ppropvar);

  public static void InitStringVector(string[] tags, out PROPVARIANT pv) {
    InitPropVariantFromStringAsVector(tags, (uint)tags.Length, out pv);
  }

  public static void SetRating(IPropertyStore ps, uint rating) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Rating", out key);
    PROPVARIANT pv = new PROPVARIANT();
    if (rating == 0) {
      pv.vt = VT_EMPTY;
    } else {
      pv.vt = VT_UI4;
      pv.p = new IntPtr(rating);
    }
    ps.SetValue(ref key, ref pv);
    PropVariantClear(ref pv);
  }

  public static string[] GetKeywords(IPropertyStore ps) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Keywords", out key);
    PROPVARIANT pv;
    ps.GetValue(ref key, out pv);
    try {
      if (pv.vt == VT_EMPTY) return new string[0];
      // Best-effort: PropVariantToStringVector
      return PropVariantToStrings(ref pv);
    } finally {
      PropVariantClear(ref pv);
    }
  }

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  private static extern void PropVariantToStringVector(
    ref PROPVARIANT propvar,
    [Out, MarshalAs(UnmanagedType.LPArray, ArraySubType=UnmanagedType.LPWStr, SizeParamIndex=2)] out string[] prgsz,
    out uint pcElem);

  public static string[] PropVariantToStrings(ref PROPVARIANT pv) {
    try {
      string[] arr;
      uint n;
      PropVariantToStringVector(ref pv, out arr, out n);
      return arr ?? new string[0];
    } catch {
      return new string[0];
    }
  }

  public static uint GetRating(IPropertyStore ps) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Rating", out key);
    PROPVARIANT pv;
    ps.GetValue(ref key, out pv);
    try {
      if (pv.vt == VT_UI4) return (uint)pv.p.ToInt64();
      return 0;
    } finally {
      PropVariantClear(ref pv);
    }
  }
}
"@

if ($ReadOnly) {
  $ps = [ShellProps]::Open($Path, $false)
  $tags = [ShellProps]::GetKeywords($ps)
  $rating = [ShellProps]::GetRating($ps)
  $obj = @{ tags = @($tags); rating = [int]$rating }
  $obj | ConvertTo-Json -Compress
  exit 0
}

$ps = [ShellProps]::Open($Path, $true)
if ($null -ne $TagsJson -and $TagsJson -ne "") {
  $tagArr = @()
  if ($TagsJson -ne "[]") {
    $tagArr = @(ConvertFrom-Json $TagsJson)
  }
  [ShellProps]::SetKeywords($ps, [string[]]$tagArr)
}
if ($null -ne $RatingStars -and $RatingStars -ne "") {
  $stars = [int]$RatingStars
  $map = @{ 0 = 0; 1 = 1; 2 = 25; 3 = 50; 4 = 75; 5 = 99 }
  $r = 0
  if ($map.ContainsKey($stars)) { $r = [uint32]$map[$stars] }
  [ShellProps]::SetRating($ps, $r)
}
$ps.Commit()
Write-Output "OK"
'''


def _write_shell_props_powershell(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    script_path = Path(__file__).with_name("_shell_props.ps1")
    try:
        if not script_path.exists() or script_path.stat().st_size < 100:
            script_path.write_text(_PS_HELPER, encoding="utf-8")
    except Exception as e:
        result["errors"].append(f"ps-helper-write: {e}")
        return False

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script_path),
        "-Path", str(path),
    ]
    if tags is not None:
        cmd += ["-TagsJson", json.dumps(tags)]
    if stars is not None:
        cmd += ["-RatingStars", str(int(stars))]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if proc.returncode == 0 and "OK" in (proc.stdout or ""):
            result["methods"].append("shell-powershell")
            return True
        err = (proc.stderr or proc.stdout or "unknown error").strip()
        result["errors"].append(f"shell-powershell: {err[:300]}")
        log.warning("powershell write failed for %s: %s", path, err[:300])
        return False
    except Exception as e:
        result["errors"].append(f"shell-powershell: {e}")
        return False


def _read_shell_props_powershell(path: Path) -> dict[str, Any] | None:
    script_path = Path(__file__).with_name("_shell_props.ps1")
    try:
        if not script_path.exists():
            script_path.write_text(_PS_HELPER, encoding="utf-8")
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path), "-Path", str(path), "-ReadOnly",
            ],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout.strip() or "{}")
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        rating = system_rating_to_stars(data.get("rating", 0))
        return {"tags": list(tags), "rating": rating, "method": "shell-powershell"}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# mutagen embedded tags (MP4/JPEG etc.)
# ---------------------------------------------------------------------------

def _write_mutagen(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    ext = path.suffix.lower()
    try:
        if ext in (".mp4", ".m4v", ".mov"):
            return _write_mutagen_mp4(path, tags, stars, result)
        if ext in (".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp"):
            return _write_mutagen_image(path, tags, stars, result)
        if ext in (".mp3",):
            return _write_mutagen_mp3(path, tags, stars, result)
        if ext in (".mkv", ".webm") and tags is not None:
            return _write_ffmpeg_comment(path, tags, result)
    except Exception as e:
        result["errors"].append(f"mutagen: {e}")
        log.warning("mutagen write failed for %s: %s", path, e)
    return False


def _write_mutagen_mp4(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    from mutagen.mp4 import MP4, MP4FreeForm

    mp4 = MP4(path)
    if mp4.tags is None:
        mp4.add_tags()
    if tags is not None:
        # Comment (widely visible) + freeform keywords
        mp4.tags["\xa9cmt"] = ["; ".join(tags)] if tags else []
        # iTunes-style keywords freeform
        try:
            joined = "; ".join(tags).encode("utf-8")
            mp4.tags["----:com.apple.iTunes:Keywords"] = [MP4FreeForm(joined)]
        except Exception:
            pass
        # Some handlers read ©gen / label — skip
    if stars is not None:
        # 0–100 scale used by many players; 0 clears
        rate = 0 if stars <= 0 else min(100, stars * 20)
        try:
            mp4.tags["rate"] = [rate]
        except Exception:
            pass
        # Windows sometimes maps tmpo — skip
    mp4.save()
    result["methods"].append("mutagen-mp4")
    return True


def _write_mutagen_image(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    """Images rely primarily on Windows shell props; mutagen/PIL path is optional."""
    # Shell write already attempted. For JPEG, also try XPKeywords via piexif if present.
    if path.suffix.lower() not in (".jpg", ".jpeg"):
        return False
    try:
        import piexif  # optional
        exif_dict = piexif.load(str(path))
        if tags is not None:
            # XPKeywords is UCS2LE null-separated in 0x9C9E
            joined = ";".join(tags)
            exif_dict.setdefault("0th", {})[piexif.ImageIFD.XPKeywords] = joined.encode("utf-16le")
        if stars is not None:
            # XPRating 0-5 in 0x4746 sometimes under EXIF — Windows uses Rating in XMP/shell mainly
            pass
        piexif.insert(piexif.dump(exif_dict), str(path))
        result["methods"].append("piexif-xpkeywords")
        return True
    except Exception:
        # Not fatal — shell writer is the real Explorer path
        return False


def _write_mutagen_mp3(
    path: Path,
    tags: list[str] | None,
    stars: int | None,
    result: dict[str, Any],
) -> bool:
    from mutagen.id3 import ID3, COMM, POPM, TXXX, ID3NoHeaderError
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()
    if tags is not None:
        id3.delall("COMM")
        if tags:
            id3.add(COMM(encoding=3, lang="eng", desc="Tags", text="; ".join(tags)))
        id3.delall("TXXX:KEYWORDS")
        if tags:
            id3.add(TXXX(encoding=3, desc="KEYWORDS", text="; ".join(tags)))
    if stars is not None:
        id3.delall("POPM")
        if stars > 0:
            # POPM rating 0-255
            id3.add(POPM(email="WindowsMediaPlayer", rating=min(255, stars * 51), count=0))
    id3.save(path)
    result["methods"].append("mutagen-mp3")
    return True


def _find_ffmpeg() -> str | None:
    import shutil
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            return p
    for candidate in (
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _write_ffmpeg_comment(path: Path, tags: list[str], result: dict[str, Any]) -> bool:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        result["errors"].append("ffmpeg not found for mkv/webm tag write")
        return False
    tag_str = "; ".join(tags)
    tmp = path.with_suffix(path.suffix + ".tagging.tmp")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(path), "-c", "copy",
             "-metadata", f"comment={tag_str}",
             "-metadata", f"keywords={tag_str}",
             str(tmp)],
            check=True, capture_output=True, timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        tmp.replace(path)
        result["methods"].append("ffmpeg-comment")
        return True
    except Exception as e:
        result["errors"].append(f"ffmpeg: {e}")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False


def _read_mutagen(path: Path) -> dict[str, Any] | None:
    ext = path.suffix.lower()
    try:
        if ext in (".mp4", ".m4v", ".mov"):
            from mutagen.mp4 import MP4
            mp4 = MP4(path)
            tags: list[str] = []
            raw = (mp4.tags or {}).get("\xa9cmt") or []
            if raw:
                for item in raw:
                    for part in str(item).split(";"):
                        part = part.strip()
                        if part:
                            tags.append(part)
            rating = 0
            rate = (mp4.tags or {}).get("rate")
            if rate:
                try:
                    r = int(rate[0])
                    rating = max(0, min(5, round(r / 20))) if r else 0
                except Exception:
                    pass
            return {"tags": tags, "rating": rating}
    except Exception:
        pass
    return None
