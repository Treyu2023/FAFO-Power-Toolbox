"""Cross-source duplicate scan: Inbox vs Pre-scaled vs After (PID)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duplicates as dup


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_ids() -> None:
    assert dup.pair_id_from_name("clip_PID_deadbeef.mp4") == "deadbeef"
    assert dup.pair_id_from_name("clip_PID_DEADBEEF_extra.mp4") == "deadbeef"
    assert dup.extract_grok_ids("grok-video-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee (1).mp4") == [
        "grok-video-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    ]
    assert "grok-12" in dup.extract_grok_ids("GROK-12_tiny.mp4")
    assert dup.extract_grok_ids("115668687_tiny_s2.mp4")[0] == "115668687"


def test_cross_scan_pid_and_protect() -> None:
    blob = os.urandom(64 * 1024)
    after_blob = os.urandom(180 * 1024)  # different size — 4K stand-in
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        inbox = root / "downloads"
        before = root / "pre-scaled"
        after = root / "post-upgrade"
        other = os.urandom(32 * 1024)
        _write(inbox / "grok-video-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.mp4", blob)
        _write(inbox / "grok-video-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee (1).mp4", blob)
        _write(inbox / "unrelated.mp4", other)
        _write(before / "grok-video-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee_PID_deadbeef.mp4", blob)
        _write(after / "UpScale4K_clip_PID_deadbeef.mp4", after_blob)

        result = dup.scan_cross_source_duplicates(
            [
                {"path": str(inbox), "role": "inbox"},
                {"path": str(before), "role": "before"},
                {"path": str(after), "role": "after"},
            ],
            match_mode="quick",
            file_types="video",
            recursive=False,
        )
        assert result["cross_source"] is True
        assert result["duplicate_groups"] >= 1
        group = result["groups"][0]
        roles = {i["role"] for i in group["items"]}
        assert "inbox" in roles
        assert "before" in roles
        assert "after" in roles
        assert "pid_after" in (group.get("match_kinds") or []) or "exact" in (group.get("match_kinds") or [])
        assert group["deletable_count"] >= 1
        assert all(i.get("protected") for i in group["items"] if i["role"] in ("before", "after"))
        keep = Path(group["suggested_keep"])
        assert str(before) in str(keep) or keep.parent == before

        protected = result["protected_roots"]
        blocked = dup.delete_paths(
            keep_path=group["suggested_keep"],
            delete_paths_list=[i["path"] for i in group["items"] if i["role"] == "after"],
            to_trash=False,
            dry_run=True,
            protected_roots=protected,
        )
        assert blocked["deleted"] == 0
        assert blocked["skipped_protected"] >= 1
        assert (after / "UpScale4K_clip_PID_deadbeef.mp4").is_file()

        merged = dup.merge_duplicate_group(
            keep_path=group["suggested_keep"],
            group_paths=[i["path"] for i in group["items"]],
            to_trash=False,
            dry_run=True,
            protected_roots=protected,
        )
        assert merged["deleted"] >= 1
        assert not any(
            Path(r["path"]).parent == after
            for r in merged["results"]
            if r.get("ok")
        )


if __name__ == "__main__":
    test_ids()
    test_cross_scan_pid_and_protect()
    print("ok")
