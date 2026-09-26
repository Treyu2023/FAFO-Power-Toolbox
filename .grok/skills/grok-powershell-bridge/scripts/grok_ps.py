#!/usr/bin/env python3
"""Client for the Grok Build <-> Grok PowerShell bridge."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def mailbox_meta_paths() -> list[Path]:
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA")
    paths: list[Path] = []
    if local:
        paths.append(Path(local) / "FAFO" / "GrokPsBridge" / "bridge.json")
    paths.append(home / ".grok" / "ps-bridge" / "bridge.json")
    return paths


def read_base_url() -> str:
    for path in mailbox_meta_paths():
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                bind = data.get("bind")
                if bind:
                    return str(bind).rstrip("/")
            except (OSError, json.JSONDecodeError):
                continue
    return "http://127.0.0.87:17321"


def request(method: str, url: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Bridge unreachable at {url}. Start Scripts/Start-GrokPsBridge.ps1 first. ({exc})"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Talk to Grok PowerShell from Grok Build")
    parser.add_argument("action", choices=["status", "say", "exec", "inbox", "ping"])
    parser.add_argument("payload", nargs="?", help="say text or exec command")
    parser.add_argument("--cwd")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--base-url")
    args = parser.parse_args()
    base = (args.base_url or read_base_url()).rstrip("/")

    if args.action in {"status", "ping"}:
        health = request("GET", f"{base}/health")
        if args.action == "ping":
            print(f"pong {health.get('bind')} pid={health.get('pid')}")
        else:
            print(json.dumps(health, indent=2))
        return 0
    if args.action == "say":
        if not args.payload:
            raise SystemExit("say requires a message")
        print(json.dumps(request("POST", f"{base}/say", {"from": "grok-build", "to": "grok-ps", "text": args.payload}), indent=2))
        return 0
    if args.action == "exec":
        if not args.payload:
            raise SystemExit("exec requires a command")
        body = {"from": "grok-build", "cmd": args.payload, "timeout_sec": args.timeout}
        if args.cwd:
            body["cwd"] = args.cwd
        print(json.dumps(request("POST", f"{base}/exec", body), indent=2))
        return 0
    if args.action == "inbox":
        print(json.dumps(request("GET", f"{base}/inbox?role=grok-build"), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
