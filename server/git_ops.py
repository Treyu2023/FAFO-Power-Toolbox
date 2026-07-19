"""Git Repository Manager — discover, organize, pull/push/clone repos."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse

IS_WINDOWS = platform.system() == "Windows"
CONFIG_PATH = Path(__file__).parent / "git_config.json"
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
ProgressFn = Callable[[str, dict[str, Any] | None], None]

SKIP_DIR_NAMES = {
    "node_modules", ".npm", ".yarn", "vendor", ".venv", "venv", "__pycache__",
    ".cache", "AppData", "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information", ".nuget", "packages", "dist", "build",
    ".next", ".nuxt", "target", "Library", "Applications",
}
SKIP_PATH_PARTS = {".git/objects", ".git/lfs", "site-packages"}

_git_exe: str | None = None
_gh_desktop: str | None = None
_config_lock = threading.Lock()


def _profile_roots() -> list[str]:
    """Common dev folders, including OneDrive-redirected Desktop/Documents."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "OneDrive",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
        home / "source",
        home / "repos",
        home / "projects",
        home / "dev",
        home / "code",
        home / "GitHub",
        home / "src",
    ]
    if IS_WINDOWS:
        for var in ("USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
            extra = os.environ.get(var, "")
            if extra:
                candidates.append(Path(extra))
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            users = Path(f"{letter}:\\Users")
            if users.exists():
                candidates.append(users)
    seen: set[str] = set()
    roots: list[str] = []
    for p in candidates:
        try:
            resolved = str(p.resolve())
        except OSError:
            resolved = str(p)
        if resolved.lower() in seen:
            continue
        if p.exists():
            seen.add(resolved.lower())
            roots.append(resolved)
    return roots


def _default_config() -> dict[str, Any]:
    home = Path.home()
    roots = _profile_roots()
    clone = home / "repos"
    if not clone.exists():
        clone = home / "OneDrive" / "repos"
    return {
        "version": 1,
        "groups": [
            {"id": "default", "name": "All Repositories", "color": "#a78bfa", "order": 0},
            {"id": "pinned", "name": "Pinned", "color": "#fbbf24", "order": 1},
            {"id": "work", "name": "Work", "color": "#60a5fa", "order": 2},
            {"id": "personal", "name": "Personal", "color": "#34d399", "order": 3},
        ],
        "repos": {},
        "saved_urls": [],
        "scan_roots": roots,
        "clone_root": str(clone),
        "hidden_paths": [],
        "last_scan": None,
    }


def load_config() -> dict[str, Any]:
    with _config_lock:
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                base = _default_config()
                base.update({k: data[k] for k in data if k in base or k in ("repos", "saved_urls", "hidden_paths", "last_scan")})
                if "groups" not in data or not data["groups"]:
                    pass
                else:
                    base["groups"] = data["groups"]
                base["repos"] = data.get("repos", {})
                base["saved_urls"] = data.get("saved_urls", [])
                base["hidden_paths"] = [p.lower() for p in data.get("hidden_paths", [])]
                return base
            except (json.JSONDecodeError, OSError):
                pass
        return _default_config()


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    with _config_lock:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def find_git() -> str | None:
    global _git_exe
    if _git_exe and Path(_git_exe).exists():
        return _git_exe

    candidates: list[Path] = []
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            gh_root = Path(local) / "GitHubDesktop"
            if gh_root.exists():
                for git_exe in gh_root.glob("app-*/resources/app/git/cmd/git.exe"):
                    candidates.append(git_exe)
        candidates.extend([
            Path(r"C:\Program Files\Git\cmd\git.exe"),
            Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
        ])
    which = shutil.which("git")
    if which:
        candidates.insert(0, Path(which))

    for c in candidates:
        if c.exists():
            _git_exe = str(c)
            return _git_exe
    return None


def find_github_desktop() -> str | None:
    global _gh_desktop
    if _gh_desktop and Path(_gh_desktop).exists():
        return _gh_desktop
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            p = Path(local) / "GitHubDesktop" / "GitHubDesktop.exe"
            if p.exists():
                _gh_desktop = str(p)
                return _gh_desktop
    return None


def get_tooling() -> dict[str, Any]:
    git = find_git()
    gh = find_github_desktop()
    version = None
    if git:
        r = _run_git(["--version"], cwd=None, timeout=10)
        if r["ok"]:
            version = r["stdout"].strip()
    return {
        "git_path": git,
        "git_version": version,
        "github_desktop_path": gh,
        "github_desktop_available": gh is not None,
    }


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    git = find_git()
    if git and IS_WINDOWS:
        git_dir = str(Path(git).parent)
        env["PATH"] = git_dir + os.pathsep + env.get("PATH", "")
    return env


def _run_git(args: list[str], cwd: str | Path | None, timeout: int = 120) -> dict[str, Any]:
    git = find_git()
    if not git:
        return {"ok": False, "stdout": "", "stderr": "Git not found. Install Git or GitHub Desktop.", "code": -1}
    try:
        proc = subprocess.run(
            [git, *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_git_env(),
            creationflags=_CREATE_FLAGS,
            errors="replace",
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Git command timed out", "code": -1}
    except OSError as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "code": -1}


def normalize_url(url: str) -> str:
    u = url.strip()
    if not u:
        raise ValueError("URL is required")
    if re.match(r"^[\w.-]+/[\w.-]+$", u) and "://" not in u:
        u = f"https://github.com/{u}"
    if u.startswith("github.com/") or u.startswith("www.github.com/"):
        u = "https://" + u.lstrip("/")
    if not u.endswith(".git") and "github.com" in u and u.count("/") >= 4:
        pass
    return u


def parse_repo_name(url: str) -> str:
    u = normalize_url(url)
    path = urlparse(u).path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    name = path.split("/")[-1] if "/" in path else path
    return name or "repository"


def _repo_id(path: str) -> str:
    return str(Path(path).resolve()).lower()


def _should_skip_dir(name: str, full_path: str) -> bool:
    if name in SKIP_DIR_NAMES:
        return True
    low = full_path.lower()
    for part in SKIP_PATH_PARTS:
        if part in low.replace("\\", "/"):
            return True
    return False


def discover_repos(
    roots: list[str] | None = None,
    max_depth: int = 8,
    on_progress: ProgressFn | None = None,
) -> list[str]:
    cfg = load_config()
    search_roots = roots or cfg.get("scan_roots") or []
    found: set[str] = set()
    hidden = set(cfg.get("hidden_paths", []))

    def report(msg: str, extra: dict | None = None):
        if on_progress:
            on_progress(msg, extra)

    for root_str in search_roots:
        root = Path(root_str)
        if not root.exists():
            continue
        report(f"Scanning {root}…", {"root": str(root)})
        try:
            for dirpath, dirnames, _ in os.walk(root, topdown=True):
                depth = Path(dirpath).relative_to(root).parts if dirpath != str(root) else ()
                if len(depth) >= max_depth:
                    dirnames.clear()
                    continue
                if ".git" in dirnames:
                    repo_path = str(Path(dirpath).resolve())
                    rid = repo_path.lower()
                    if rid not in hidden:
                        found.add(repo_path)
                dirnames[:] = [
                    d for d in dirnames
                    if d != ".git" and not _should_skip_dir(d, os.path.join(dirpath, d))
                ]
        except (PermissionError, OSError) as e:
            report(f"Skipped {root}: {e}")

    for path_str in cfg.get("repos", {}):
        p = Path(path_str)
        if p.exists() and (p / ".git").exists():
            found.add(str(p.resolve()))

    result = sorted(found, key=str.lower)
    report(f"Found {len(result)} repositories", {"count": len(result)})
    return result


def get_repo_status(path: str, fetch_remote: bool = True) -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or not (p / ".git").exists():
        return {"path": path, "valid": False, "error": "Not a git repository"}

    branch_r = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], p)
    branch = branch_r["stdout"] if branch_r["ok"] else "unknown"

    remote_r = _run_git(["remote", "get-url", "origin"], p)
    remote_url = remote_r["stdout"] if remote_r["ok"] else ""

    dirty_r = _run_git(["status", "--porcelain"], p)
    dirty_count = len([ln for ln in dirty_r["stdout"].splitlines() if ln.strip()]) if dirty_r["ok"] else 0

    ahead, behind = 0, 0
    if remote_url and fetch_remote:
        _run_git(["fetch", "--quiet", "origin"], p, timeout=60)
        ab = _run_git(["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"], p)
        if ab["ok"]:
            parts = ab["stdout"].split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        else:
            ab2 = _run_git(["rev-list", "--left-right", "--count", "HEAD...@{u}"], p)
            if ab2["ok"]:
                parts = ab2["stdout"].split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])

    log_r = _run_git(["log", "-1", "--format=%s|%cr|%h"], p)
    last_msg, last_when, last_hash = "", "", ""
    if log_r["ok"] and "|" in log_r["stdout"]:
        parts = log_r["stdout"].split("|", 2)
        last_msg = parts[0]
        last_when = parts[1] if len(parts) > 1 else ""
        last_hash = parts[2] if len(parts) > 2 else ""

    state = "clean"
    if dirty_count:
        state = "dirty"
    elif ahead and behind:
        state = "diverged"
    elif ahead:
        state = "ahead"
    elif behind:
        state = "behind"

    return {
        "path": str(p.resolve()),
        "name": p.name,
        "valid": True,
        "branch": branch,
        "remote_url": remote_url,
        "dirty_count": dirty_count,
        "ahead": ahead,
        "behind": behind,
        "state": state,
        "last_commit": last_msg,
        "last_commit_when": last_when,
        "last_commit_hash": last_hash,
    }


def list_repos(refresh: bool = False) -> dict[str, Any]:
    cfg = load_config()
    paths = discover_repos()
    repos_meta = cfg.get("repos", {})

    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(get_repo_status, p, False): p for p in paths}
        for fut in as_completed(futures):
            try:
                st = fut.result()
                if not st.get("valid"):
                    continue
                rid = _repo_id(st["path"])
                meta = repos_meta.get(rid, {})
                st["id"] = rid
                st["group_id"] = meta.get("group_id", "default")
                st["order"] = meta.get("order", 999)
                st["pinned"] = meta.get("pinned", False)
                st["notes"] = meta.get("notes", "")
                st["saved_url"] = meta.get("saved_url") or st.get("remote_url", "")
                statuses.append(st)
            except Exception:
                continue

    statuses.sort(key=lambda r: (not r.get("pinned"), r.get("order", 999), r.get("name", "").lower()))
    return {
        "repos": statuses,
        "groups": cfg.get("groups", []),
        "saved_urls": cfg.get("saved_urls", []),
        "clone_root": cfg.get("clone_root", ""),
        "scan_roots": cfg.get("scan_roots", []),
        "last_scan": cfg.get("last_scan"),
        "count": len(statuses),
    }


def organize_repo(path: str, group_id: str | None = None, order: int | None = None,
                  pinned: bool | None = None, notes: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    rid = _repo_id(path)
    meta = cfg["repos"].setdefault(rid, {"path": str(Path(path).resolve())})
    if group_id is not None:
        meta["group_id"] = group_id
    if order is not None:
        meta["order"] = order
    if pinned is not None:
        meta["pinned"] = pinned
    if notes is not None:
        meta["notes"] = notes
    save_config(cfg)
    return {"ok": True, "id": rid}


def hide_repo(path: str) -> dict[str, Any]:
    cfg = load_config()
    rid = _repo_id(path)
    if rid not in cfg["hidden_paths"]:
        cfg["hidden_paths"].append(rid)
    cfg["repos"].pop(rid, None)
    save_config(cfg)
    return {"ok": True}


def save_groups(groups: list[dict]) -> dict[str, Any]:
    cfg = load_config()
    cfg["groups"] = groups
    save_config(cfg)
    return {"ok": True, "groups": groups}


def add_saved_url(url: str, name: str = "", group_id: str = "default") -> dict[str, Any]:
    norm = normalize_url(url)
    repo_name = name or parse_repo_name(norm)
    cfg = load_config()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "url": norm,
        "name": repo_name,
        "group_id": group_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_cloned": None,
        "clone_path": None,
    }
    existing = next((u for u in cfg["saved_urls"] if u["url"] == norm), None)
    if existing:
        return {"ok": True, "saved_url": existing, "existing": True}
    cfg["saved_urls"].insert(0, entry)
    save_config(cfg)
    return {"ok": True, "saved_url": entry}


def remove_saved_url(url_id: str) -> dict[str, Any]:
    cfg = load_config()
    cfg["saved_urls"] = [u for u in cfg["saved_urls"] if u.get("id") != url_id]
    save_config(cfg)
    return {"ok": True}


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    for key in ("scan_roots", "clone_root", "groups"):
        if key in patch:
            cfg[key] = patch[key]
    save_config(cfg)
    return {"ok": True, "config": cfg}


def pull_repo(path: str) -> dict[str, Any]:
    r = _run_git(["pull", "--ff-only"], path, timeout=180)
    if not r["ok"] and "no tracking information" in r["stderr"].lower():
        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
        if branch["ok"]:
            r = _run_git(["pull", "origin", branch["stdout"]], path, timeout=180)
    status = get_repo_status(path)
    return {"ok": r["ok"], "output": r["stdout"] or r["stderr"], "repo": status}


def push_repo(path: str) -> dict[str, Any]:
    r = _run_git(["push"], path, timeout=180)
    if not r["ok"] and "no upstream" in r["stderr"].lower():
        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
        if branch["ok"]:
            r = _run_git(["push", "-u", "origin", branch["stdout"]], path, timeout=180)
    status = get_repo_status(path)
    return {"ok": r["ok"], "output": r["stdout"] or r["stderr"], "repo": status}


def fetch_repo(path: str) -> dict[str, Any]:
    r = _run_git(["fetch", "--all", "--prune"], path, timeout=120)
    status = get_repo_status(path)
    return {"ok": r["ok"], "output": r["stdout"] or r["stderr"], "repo": status}


def clone_repo(url: str, target_dir: str | None = None, group_id: str = "default",
               on_progress: ProgressFn | None = None) -> dict[str, Any]:
    norm = normalize_url(url)
    name = parse_repo_name(norm)
    cfg = load_config()
    base = Path(target_dir or cfg.get("clone_root") or Path.home() / "repos")
    base.mkdir(parents=True, exist_ok=True)
    dest = base / name
    if dest.exists() and (dest / ".git").exists():
        status = get_repo_status(str(dest))
        organize_repo(str(dest), group_id=group_id)
        saved = add_saved_url(norm, name, group_id)
        for u in cfg.get("saved_urls", []):
            if u["url"] == norm:
                u["last_cloned"] = datetime.now(timezone.utc).isoformat()
                u["clone_path"] = str(dest)
                save_config(cfg)
                break
        return {"ok": True, "path": str(dest), "existing": True, "repo": status, "saved_url": saved.get("saved_url")}

    if on_progress:
        on_progress(f"Cloning {name}…", {"url": norm, "dest": str(dest)})

    parent = dest.parent
    r = _run_git(["clone", norm, str(dest)], parent, timeout=600)
    if not r["ok"]:
        raise RuntimeError(r["stderr"] or r["stdout"] or "Clone failed")

    rid = _repo_id(str(dest))
    cfg = load_config()
    cfg["repos"][rid] = {
        "path": str(dest.resolve()),
        "group_id": group_id,
        "saved_url": norm,
        "order": 0,
        "pinned": False,
    }
    for u in cfg.get("saved_urls", []):
        if u["url"] == norm:
            u["last_cloned"] = datetime.now(timezone.utc).isoformat()
            u["clone_path"] = str(dest)
            break
    else:
        cfg["saved_urls"].insert(0, {
            "id": str(uuid.uuid4())[:8],
            "url": norm,
            "name": name,
            "group_id": group_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "last_cloned": datetime.now(timezone.utc).isoformat(),
            "clone_path": str(dest),
        })
    cfg["last_scan"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)

    status = get_repo_status(str(dest))
    if on_progress:
        on_progress(f"Cloned {name}", {"path": str(dest)})
    return {"ok": True, "path": str(dest), "repo": status}


def init_repo(path: str, group_id: str = "default") -> dict[str, Any]:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    if (p / ".git").exists():
        status = get_repo_status(str(p))
        return {"ok": True, "path": str(p), "existing": True, "repo": status}

    r = _run_git(["init"], p)
    if not r["ok"]:
        raise RuntimeError(r["stderr"] or "git init failed")

    cfg = load_config()
    rid = _repo_id(str(p))
    cfg["repos"][rid] = {"path": str(p.resolve()), "group_id": group_id, "order": 0}
    save_config(cfg)
    status = get_repo_status(str(p))
    return {"ok": True, "path": str(p), "repo": status}


def open_folder(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Path not found")
    folder = str(p if p.is_dir() else p.parent)
    if IS_WINDOWS:
        os.startfile(folder)
    else:
        subprocess.Popen(["xdg-open", folder])
    return {"ok": True}


def open_github_desktop(path: str) -> dict[str, Any]:
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError("Path not found")
    gh = find_github_desktop()
    if gh:
        norm = str(p).replace("\\", "/")
        uri = f"github-windows://openRepo/{quote(norm, safe='/:@')}"
        if IS_WINDOWS:
            os.startfile(uri)
        else:
            subprocess.Popen(["open", uri])
        return {"ok": True, "method": "github-windows-uri"}
    raise RuntimeError("GitHub Desktop not installed")


def scan_and_merge(on_progress: ProgressFn | None = None) -> dict[str, Any]:
    paths = discover_repos(on_progress=on_progress)
    cfg = load_config()
    for path in paths:
        rid = _repo_id(path)
        if rid not in cfg["repos"]:
            cfg["repos"][rid] = {"path": path, "group_id": "default", "order": 999}
    cfg["last_scan"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)
    return {"ok": True, "found": len(paths), "last_scan": cfg["last_scan"]}