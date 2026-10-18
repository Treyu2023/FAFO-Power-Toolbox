"""Ring-buffer debug log — server errors, API calls, client echoes."""
from __future__ import annotations

import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX = 800
_log: deque[dict[str, Any]] = deque(maxlen=_MAX)
_lock = threading.Lock()
_LOG_FILE = Path(__file__).resolve().parent / "debug_runtime.log"
# Cap disk growth on long-running tray servers (rotate quietly)
_LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _maybe_rotate_log() -> None:
    try:
        if _LOG_FILE.is_file() and _LOG_FILE.stat().st_size > _LOG_MAX_BYTES:
            bak = _LOG_FILE.with_suffix(".log.1")
            try:
                if bak.is_file():
                    bak.unlink()
            except OSError:
                pass
            _LOG_FILE.replace(bak)
    except OSError:
        pass


# S-SEC4b: URL secrets (?s1t= / mt= values) never reach the ring buffer or debug_runtime.log.
_SECRET_RE = re.compile(r"([?&](?:s1t|mt)=)[^&#\s\"']*")


def _redact(v: Any, depth: int = 0) -> Any:
    if isinstance(v, str):
        return _SECRET_RE.sub(r"\1[redacted]", v)
    if depth > 6:
        return v
    if isinstance(v, dict):
        return {k: _redact(x, depth + 1) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_redact(x, depth + 1) for x in v]
    if v is None or isinstance(v, (bool, int, float)):
        return v
    s = str(v)
    return _redact(s) if _SECRET_RE.search(s) else v


def log(source: str, level: str, message: str, extra: Any = None) -> dict[str, Any]:
    entry = {
        "ts": _now(),
        "source": str(source or "?")[:80],
        "level": str(level or "info")[:16],
        "message": _redact(str(message))[:2000],
        "extra": _redact(extra),
    }
    with _lock:
        _log.appendleft(entry)
    try:
        _maybe_rotate_log()
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return entry


def get_logs(limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(limit, _MAX))
    with _lock:
        items = list(_log)
    if level:
        items = [e for e in items if e.get("level") == level]
    return items[:limit]


def clear_logs() -> None:
    with _lock:
        _log.clear()
    try:
        _LOG_FILE.write_text("", encoding="utf-8")
    except OSError:
        pass