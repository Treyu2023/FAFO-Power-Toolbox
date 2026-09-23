"""Whitelisted CelesTrak GP fetch for the Solar System Debris Tracker.

The page cannot call celestrak.org itself (no CORS). This module fetches
only the four catalogs that tool displays, and caches them in-process.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable

GROUPS = (
    "fengyun-1c-debris",
    "iridium-33-debris",
    "cosmos-2251-debris",
    "analyst",
)

TTL_S = 600
MAX_BYTES = 20_000_000

_cache: dict[str, tuple[float, str]] = {}


class DebrisTleError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def clear_cache() -> None:
    _cache.clear()


def fetch_group(
    group: str,
    *,
    version: str = "0",
    clock: Callable[[], float] | None = None,
    opener=None,
) -> str:
    key = (group or "").strip().lower()
    if key not in GROUPS:
        raise DebrisTleError(400, "Unknown debris group")
    now = (clock or time.time)()
    hit = _cache.get(key)
    if hit and now - hit[0] < TTL_S:
        return hit[1]
    url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={key}&FORMAT=tle"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"FAFO-Power-Toolbox/{version} (local educational debris viz)",
            "Accept": "text/plain",
        },
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(req, timeout=25) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise DebrisTleError(502, f"CelesTrak HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise DebrisTleError(502, "CelesTrak unavailable") from e
    if len(raw) > MAX_BYTES:
        raise DebrisTleError(502, "CelesTrak response too large")
    text = raw.decode("utf-8", errors="replace")
    if "\n1 " not in text and not text.startswith("1 "):
        raise DebrisTleError(502, "CelesTrak returned no TLEs")
    _cache[key] = (now, text)
    return text
