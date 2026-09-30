#!/usr/bin/env python3
"""Static LAN share for the Phone Launcher.

Serves an allowlist of HTML/JS/CSS/assets on 0.0.0.0 (default :18780).
Does NOT bind the loopback API (127.0.0.87:18765). Does NOT serve
server/, Scripts/, private apps, DBs, or secrets.

  python server/phone_static.py
  python server/phone_static.py --port 18780 --bind 0.0.0.0
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 18780
DEFAULT_BIND = "0.0.0.0"

EXACT = {
    "index.html",
    "404.html",
    "Phone Launcher.html",
    "Toolbox Launcher.html",
    "Drawing Board.html",
    "Typing Assistant Trainer.html",
    "LetterKey.html",
    "Bloodmoon Survivor.html",
    "Empire Seed.html",
    "Solar System Debris Tracker.html",
    "Songforge.html",
    "manifest.webmanifest",
    "sw.js",
    "VERSION",
}

PREFIXES = (
    "shared/",
    "assets/tool-icons/",
    "assets/typing-campaign-sprites/",
    "Verifone Tools/",
    "Accounting Tools and calculators/",
    "AI Creator/",
    "Tech Quest/",
    "Video Tools/",
    "Image tools/",
    "Progress Map/",
)

BLOCK_SUFFIX = (
    ".bak",
    ".bak-encoding",
    ".db",
    ".py",
    ".pyc",
    ".ps1",
    ".bat",
    ".vbs",
    ".env",
    ".log",
)

BLOCK_PREFIX = (
    "server/",
    "scripts/",
    "private/",
    "business tax preparedness/",
    "investor portal.html",
    "data/",
    "reports/",
    "logs/",
    "backups/",
    "verifonelibrary/",
    "snapshots/",
    "mcps/",
    ".git/",
    ".venv/",
    ".grok/",
)


def _norm(rel: str) -> str:
    rel = unquote(rel).replace("\\", "/").lstrip("/")
    if rel in ("", "."):
        return "index.html"
    return rel


def allowed(rel: str) -> bool:
    rel = _norm(rel)
    low = rel.lower()
    if ".." in rel.split("/"):
        return False
    if low.startswith(BLOCK_PREFIX):
        return False
    if low.endswith(BLOCK_SUFFIX) or ".bak-" in low:
        return False
    if rel in EXACT:
        return True
    return any(rel.startswith(p) or rel.startswith(p.replace(" ", "%20")) for p in PREFIXES)


def lan_ips() -> list[str]:
    found: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in found and not ip.startswith("127."):
                found.append(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip not in found and not ip.startswith("127."):
            found.insert(0, ip)
    except OSError:
        pass
    # Prefer RFC1918 first
    def score(ip: str) -> int:
        if ip.startswith("192.168."):
            return 0
        if ip.startswith("10."):
            return 1
        if ip.startswith("172."):
            return 2
        return 9

    found.sort(key=score)
    return found


def version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def mime_for(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".webmanifest"):
        return "application/manifest+json"
    if name.endswith(".js"):
        return "text/javascript; charset=utf-8"
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".svg"):
        return "image/svg+xml"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    guess, _ = mimetypes.guess_type(str(path))
    return guess or "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    server_version = "FAFOPhoneStatic/1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _phone_lan_json(self) -> bytes:
        port = self.server.server_address[1]
        urls = [
            f"http://{ip}:{port}/Phone%20Launcher.html"
            for ip in lan_ips()
        ]
        payload = {
            "ok": True,
            "version": version(),
            "port": port,
            "bind": self.server.server_address[0],
            "urls": urls,
            "launcher": "Phone Launcher.html",
            "note": "Static HTML only. Loopback API stays on 127.0.0.87:18765.",
        }
        return json.dumps(payload, indent=2).encode("utf-8")

    def _resolve(self, rel: str) -> Path | None:
        rel = _norm(rel)
        if not allowed(rel):
            return None
        candidate = (ROOT / rel).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            return None
        if candidate.is_file():
            return candidate
        return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        rel = _norm(parsed.path)
        if rel in ("phone-lan.json", "api/phone-lan.json"):
            self._send(200, self._phone_lan_json(), "application/json; charset=utf-8")
            return
        path = self._resolve(rel)
        if path is None:
            body = (ROOT / "404.html").read_bytes() if (ROOT / "404.html").is_file() else b"Not found\n"
            self._send(404, body, "text/html; charset=utf-8")
            return
        self._send(200, path.read_bytes(), mime_for(path))

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()


def main() -> int:
    ap = argparse.ArgumentParser(description="FAFO Phone Launcher static LAN share")
    ap.add_argument("--bind", default=os.environ.get("FAFO_PHONE_BIND", DEFAULT_BIND))
    ap.add_argument("--port", type=int, default=int(os.environ.get("FAFO_PHONE_PORT", DEFAULT_PORT)))
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.bind, args.port), Handler)
    urls = [f"http://{ip}:{args.port}/Phone%20Launcher.html" for ip in lan_ips()]
    def out(msg: str) -> None:
        print(msg, flush=True)

    out("FAFO Phone LAN  static HTML only  (API stays on 127.0.0.87:18765)")
    out(f"  bind {args.bind}:{args.port}")
    if urls:
        out("  phone URLs:")
        for u in urls:
            out(f"    {u}")
    else:
        out("  no LAN IPv4 found — connect the PC to Wi-Fi")
    out(f"  local http://127.0.0.1:{args.port}/Phone%20Launcher.html?share=1")
    out("  Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
