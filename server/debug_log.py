"""Ring-buffer debug log — server errors, API calls, client echoes."""
from __future__ import annotations

import json
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


def log(source: str, level: str, message: str, extra: Any = None) -> dict[str, Any]:
    entry = {
        "ts": _now(),
        "source": str(source or "?")[:80],
        "level": str(level or "info")[:16],
        "message": str(message)[:2000],
        "extra": extra,
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