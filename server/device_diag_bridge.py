"""Load the standalone fafo-device-diagnostics package for the toolbox API."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_path() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("FAFO_DIAG_HOME")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name.lower() == "repos":
            candidates.append(parent / "fafo-device-diagnostics")
            break
    candidates.append(Path(r"C:\_Git\repos\fafo-device-diagnostics"))
    for path in candidates:
        if (path / "fafo_diag" / "__init__.py").is_file():
            return path
    return None


def load():
    path = repo_path()
    if path is None:
        raise FileNotFoundError(
            "Device diagnostics repo is not on this PC. Expected C:\\_Git\\repos\\fafo-device-diagnostics."
        )
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
    import fafo_diag.collect as collect
    import fafo_diag.history as history
    import fafo_diag.server as diag_server
    import fafo_diag.store as store

    return collect, history, diag_server, store
