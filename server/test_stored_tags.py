"""Catalog tag cells that pair bots chopped must still parse."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import parse_stored_tags


def test_comma_joined_pair_code() -> None:
    assert parse_stored_tags("[],UP-0058") == ["UP-0058"]
    assert parse_stored_tags("[],UP-0049,UP-0066") == ["UP-0049", "UP-0066"]


def test_truncated_signature_keeps_real_keywords() -> None:
    raw = '["vsr-pipeline", "Signature: AAAA/BBBB'
    assert parse_stored_tags(raw) == ["vsr-pipeline"]


def test_valid_list_drops_signature_blob() -> None:
    raw = json.dumps(["before", "source", "Signature: not-a-keyword"])
    assert parse_stored_tags(raw) == ["before", "source"]


def test_empty() -> None:
    assert parse_stored_tags(None) == []
    assert parse_stored_tags("") == []
    assert parse_stored_tags("[]") == []


if __name__ == "__main__":
    test_comma_joined_pair_code()
    test_truncated_signature_keeps_real_keywords()
    test_valid_list_drops_signature_blob()
    test_empty()
    print("ok")
