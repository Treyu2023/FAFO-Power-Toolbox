"""Debris TLE proxy: whitelist, cache, and empty-body rejection."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import debris_tle as tle


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, n: int) -> bytes:
        return self._payload[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_rejects_unknown_group() -> None:
    tle.clear_cache()
    try:
        tle.fetch_group("stations", clock=lambda: 0)
        raise AssertionError("expected DebrisTleError")
    except tle.DebrisTleError as e:
        assert e.status == 400


def test_cache_and_tle_body() -> None:
    tle.clear_cache()
    body = b"FENGYUN 1C DEB\n1 29733U 99025X   26183.55895177  .00001092  00000+0  18470-2 0  9999\n2 29733  99.2054 213.8677 0569277  96.0251  52.4244 12.96837390917352\n"
    calls = {"n": 0}

    def opener(req, timeout=0):
        calls["n"] += 1
        assert "fengyun-1c-debris" in req.full_url
        assert timeout == 25
        return _Resp(body)

    clock = {"t": 1000.0}
    text = tle.fetch_group("fengyun-1c-debris", version="test", clock=lambda: clock["t"], opener=opener)
    assert text.startswith("FENGYUN")
    assert calls["n"] == 1
    again = tle.fetch_group("FENGYUN-1C-DEBRIS", clock=lambda: clock["t"] + 10, opener=opener)
    assert again == text
    assert calls["n"] == 1
    clock["t"] += tle.TTL_S + 1
    tle.fetch_group("fengyun-1c-debris", clock=lambda: clock["t"], opener=opener)
    assert calls["n"] == 2


def test_rejects_non_tle() -> None:
    tle.clear_cache()

    def opener(req, timeout=0):
        return _Resp(b"<html>blocked</html>")

    try:
        tle.fetch_group("analyst", clock=lambda: 0, opener=opener)
        raise AssertionError("expected DebrisTleError")
    except tle.DebrisTleError as e:
        assert e.status == 502


if __name__ == "__main__":
    test_rejects_unknown_group()
    test_cache_and_tle_body()
    test_rejects_non_tle()
    print("ok")
