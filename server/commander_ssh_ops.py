"""
Commander maint SSH helpers — Manager password reset (resetpw manager).

Secrets stay on this PC only:
  - Fleet maint user/password: %LOCALAPPDATA%\\FAFO\\fleet-tech-defaults.json
  - Optional per-site override in Liferaft credentials (sshUser / sshPassword)

Does NOT commit passwords to git. API responses may include the one-time temp
Manager password from resetpw — browser should not log it; Liferaft stores
intentionally after reset.

Typical flow (field SOP):
  1) LAN to Commander, Help Desk login enabled + token if required
  2) SSH as maint
  3) resetpw manager  → console prints temporary Manager password
  4) Config Client login with temp password → forced change to letter+base
     (e.g. A6652990). Then update Liferaft letter + last-change date.

We automate (1–3) and Liferaft bookkeeping for (4). Setting the final Manager
password inside Sapphire still requires the Config Client forced-change UI
(or equivalent) — there is no safe public CLI for that step on all bases.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fleet_tech_ops as fleet
import site_profile_ops as sprof

log = logging.getLogger("fafo.commander_ssh")

# Never write passwords into this logger at INFO
_REDACT = re.compile(r"(password|passwd|pwd)\s*[:=]\s*\S+", re.I)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(s: str) -> str:
    return _REDACT.sub(r"\1=***", s or "")


def _find_plink() -> Path | None:
    for p in (
        Path(r"C:\Program Files\PuTTY\plink.exe"),
        Path(r"C:\Program Files (x86)\PuTTY\plink.exe"),
        shutil.which("plink"),
    ):
        if not p:
            continue
        path = Path(p)
        if path.is_file():
            return path
    return None


def _try_paramiko(
    host: str,
    port: int,
    username: str,
    password: str,
    command: str,
    timeout: float = 45.0,
) -> dict[str, Any]:
    try:
        import paramiko
    except ImportError:
        return {"ok": False, "engine": "paramiko", "error": "paramiko not installed"}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    t0 = time.time()
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
            banner_timeout=timeout,
            auth_timeout=timeout,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        # Some resetpw prompts need a newline on stdin
        try:
            stdin.write("\n")
            stdin.flush()
        except Exception:
            pass
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return {
            "ok": code == 0 or bool(out.strip()),
            "engine": "paramiko",
            "exitCode": code,
            "stdout": out,
            "stderr": err,
            "ms": round((time.time() - t0) * 1000),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "engine": "paramiko",
            "error": str(e),
            "ms": round((time.time() - t0) * 1000),
        }
    finally:
        try:
            client.close()
        except Exception:
            pass


def _try_plink(
    host: str,
    port: int,
    username: str,
    password: str,
    command: str,
    timeout: float = 45.0,
) -> dict[str, Any]:
    plink = _find_plink()
    if not plink:
        return {"ok": False, "engine": "plink", "error": "plink.exe not found"}
    t0 = time.time()
    # -batch: no interactive prompts; host key auto-store first time needs -hostkey or accept
    cmd = [
        str(plink),
        "-ssh",
        f"{username}@{host}",
        "-P",
        str(port),
        "-pw",
        password,
        "-batch",
        command,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
        # Host key not cached
        if "host key is not cached" in (out + err).lower() or "cannot confirm" in (out + err).lower():
            # Retry accepting key via echo y (plink -batch fails without cache)
            cmd2 = [
                str(plink),
                "-ssh",
                f"{username}@{host}",
                "-P",
                str(port),
                "-pw",
                password,
                command,
            ]
            proc = subprocess.run(
                cmd2,
                input="y\n",
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            out = proc.stdout or ""
            err = proc.stderr or ""
        return {
            "ok": proc.returncode == 0 or bool(out.strip()),
            "engine": "plink",
            "exitCode": proc.returncode,
            "stdout": out,
            "stderr": err,
            "ms": round((time.time() - t0) * 1000),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "engine": "plink", "error": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "engine": "plink", "error": str(e)}


def run_remote_command(
    host: str,
    *,
    port: int = 22,
    username: str | None = None,
    password: str | None = None,
    command: str = "help",
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Run one command over SSH using fleet/site maint credentials."""
    host = (host or "").strip()
    if not host:
        raise ValueError("host required")
    shell = fleet.shell_for_site(host=host, site_password=password, site_user=username, site_port=port)
    user = (username or shell.get("username") or "maint").strip()
    pwd = password if password is not None else (shell.get("password") or "")
    port = int(port or shell.get("port") or 22)
    if not pwd:
        raise ValueError(
            "No maint SSH password — set fleet-tech-defaults on this PC or Liferaft sshPassword"
        )

    # Prefer paramiko (no password on process cmdline), then plink
    res = _try_paramiko(host, port, user, pwd, command, timeout=timeout)
    if not res.get("ok") and res.get("error") == "paramiko not installed":
        res = _try_plink(host, port, user, pwd, command, timeout=timeout)
    elif not res.get("ok") and "paramiko" in (res.get("engine") or ""):
        # try plink as fallback
        alt = _try_plink(host, port, user, pwd, command, timeout=timeout)
        if alt.get("ok") or alt.get("stdout"):
            res = alt

    res["host"] = host
    res["port"] = port
    res["username"] = user
    res["command"] = command
    # Never echo password
    res["passwordUsed"] = bool(pwd)
    return res


def parse_resetpw_output(text: str) -> dict[str, Any]:
    """
    Best-effort extract of temporary Manager password from resetpw manager output.
    Formats vary by base/version — capture common patterns without assuming one layout.
    """
    raw = text or ""
    candidates: list[str] = []
    # password: XXXX / new password is XXXX / Password = XXXX
    for pat in (
        r"(?i)(?:new\s+)?(?:manager\s+)?password\s*(?:is|=|:)\s*([^\s;,]+)",
        r"(?i)(?:temp(?:orary)?|temporary)\s+password\s*(?:is|=|:)\s*([^\s;,]+)",
        r"(?i)password\s+for\s+manager\s*(?:is|=|:)\s*([^\s;,]+)",
        r"(?i)reset\s+to\s+([A-Za-z0-9@#$%*_+\-.]{4,32})",
    ):
        for m in re.finditer(pat, raw):
            pw = m.group(1).strip().strip("\"'")
            if pw.lower() in {"manager", "user", "login", "the", "to", "for"}:
                continue
            if len(pw) >= 3:
                candidates.append(pw)
    # Unique preserve order
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return {
        "tempPassword": uniq[0] if uniq else None,
        "allCandidates": uniq[:5],
        "rawPreview": _redact(raw)[:2000],
    }


def reset_manager_password(
    host: str,
    *,
    port: int = 22,
    username: str | None = None,
    password: str | None = None,
    group_key: str | None = None,
    export_id: str | None = None,
    target_letter: str = "A",
    password_base: str | None = None,
    update_liferaft: bool = True,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    SSH as maint and run ``resetpw manager``.

    Returns temporary Manager password when parseable. Optionally stages Liferaft
    so after Config Client forced change the site should use target letter+base
    (default A + site base, e.g. A6652990).
    """
    host = (host or "").strip()
    if not host:
        raise ValueError("Commander host/IP required")

    # Resolve desired final password hint from liferaft
    master = {}
    gk = None
    try:
        if group_key or export_id:
            gk = sprof.resolve_group_key(group_key, export_id)
            master = sprof.get_master_profile(group_key=gk, export_id=export_id, merge_sources=True)
    except Exception:
        master = {}

    cred = (master or {}).get("credentials") or {}
    base = (password_base or cred.get("passwordBase") or "").strip()
    if not base and cred.get("configClientPassword"):
        parsed = sprof.parse_manager_password(cred.get("configClientPassword") or "")
        base = parsed.get("base") or ""
    letter = (target_letter or "A").strip().upper() or "A"
    if letter not in sprof._LETTER_ORDER:
        letter = "A"
    pos = (cred.get("passwordLetterPosition") or "leading").lower()
    target_pw = sprof.build_manager_password(base, letter, pos) if base else ""

    # Prefer site ssh overrides
    site_user = username or cred.get("sshUser") or None
    site_pass = password if password is not None else (cred.get("sshPassword") or None)
    site_port = int(cred.get("sshPort") or port or 22)
    if cred.get("sshHost") and not host:
        host = cred["sshHost"]

    remote = run_remote_command(
        host,
        port=site_port,
        username=site_user,
        password=site_pass if site_pass else None,
        command="resetpw manager",
        timeout=timeout,
    )
    combined = (remote.get("stdout") or "") + "\n" + (remote.get("stderr") or "")
    parsed = parse_resetpw_output(combined)

    liferaft_update = None
    if update_liferaft and gk:
        try:
            # Store temp password as current Config Client password so tech can log in;
            # note that forced change to target letter+base is still required on first login.
            note = (
                f"SSH resetpw manager @ {host} {_utc_now()[:19]}. "
                f"Complete forced change to {target_pw or (letter + base) or 'letter+base'} in Config Client, "
                f"then Rotate/set letter {letter} and last-change date."
            )
            temp = parsed.get("tempPassword")
            if temp:
                liferaft_update = sprof.set_manager_password(
                    gk,
                    temp,
                    mark_changed=False,  # not the final fleet password yet
                    scheme="letter_cycle",
                    note=note,
                    sync_live_profile=True,
                    changed_at=None,
                )
                # Keep base/letter target as notes on profile
                prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
                c = prof.get("credentials") or {}
                if base:
                    c["passwordBase"] = base
                c["passwordLetter"] = letter  # intended after force-change
                c["sshNotes"] = (
                    (c.get("sshNotes") or "")
                    + f"\n[{_utc_now()[:19]}] resetpw manager → temp issued; target final {target_pw or letter + base}."
                ).strip()
                # Stash intended final (not yet live until force-change)
                c["pendingManagerPassword"] = target_pw
                c["pendingManagerLetter"] = letter
                c["pendingManagerNote"] = (
                    "After Config Client forced change, confirm password matches pendingManagerPassword "
                    "then clear pending fields and set lastPasswordChangeAt."
                )
                prof["credentials"] = c
                sprof.save_master_profile(gk, prof)
            else:
                liferaft_update = {
                    "ok": False,
                    "message": "resetpw ran but temp password was not parsed — check raw output on secure screen",
                }
        except Exception as e:  # noqa: BLE001
            liferaft_update = {"ok": False, "error": str(e)}

    ok = bool(remote.get("ok") or parsed.get("tempPassword"))
    return {
        "ok": ok,
        "host": host,
        "port": site_port,
        "username": remote.get("username"),
        "engine": remote.get("engine"),
        "ms": remote.get("ms"),
        "exitCode": remote.get("exitCode"),
        "tempManagerPassword": parsed.get("tempPassword"),
        "parseCandidates": parsed.get("allCandidates") or [],
        "targetLetter": letter,
        "passwordBase": base,
        "targetManagerPassword": target_pw or None,
        "nextSteps": [
            "If Help Desk login is required and SSH failed: enable Help Desk + token on Commander, retry.",
            f"Log into Config Client as Manager with the temporary password"
            + (f" ({parsed.get('tempPassword')})" if parsed.get("tempPassword") else " (from raw output)."),
            "Commander will force a password change — set it to the target letter+base"
            + (f" → {target_pw}" if target_pw else " (e.g. A + site digits)."),
            "In Liferaft: confirm letter, set last-change date to today, clear pending fields.",
            "Do not commit temp passwords to git or email.",
        ],
        "helpDeskReminder": (
            "Many sites require Help Desk login enabled on the Commander before maint SSH works."
        ),
        "rawPreview": parsed.get("rawPreview") or _redact(combined)[:1500],
        "error": remote.get("error"),
        "liferaft": liferaft_update,
        "message": (
            (
                f"resetpw manager OK on {host}. Temp Manager password captured. "
                f"Complete forced change to {target_pw or 'letter+base'} in Config Client."
            )
            if parsed.get("tempPassword")
            else (
                f"SSH command finished on {host} but temp password was not auto-parsed. "
                "Check rawPreview securely, then finish Config Client forced change."
            )
            if ok
            else (
                remote.get("error")
                or "SSH reset failed — check host, LAN, Help Desk login, and maint password."
            )
        ),
    }


def confirm_manager_final_password(
    group_key: str | None = None,
    export_id: str | None = None,
    *,
    password: str | None = None,
    use_pending: bool = True,
    mark_changed: bool = True,
) -> dict[str, Any]:
    """
    After Config Client forced change, record final Manager password (e.g. A6652990)
    and clear pending fields / set last-change date.
    """
    gk = sprof.resolve_group_key(group_key, export_id)
    prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
    cred = prof.get("credentials") or {}
    pw = (password or "").strip()
    if not pw and use_pending:
        pw = (cred.get("pendingManagerPassword") or "").strip()
    if not pw:
        # build from letter+base
        letter = cred.get("pendingManagerLetter") or cred.get("passwordLetter") or "A"
        base = cred.get("passwordBase") or ""
        pos = cred.get("passwordLetterPosition") or "leading"
        pw = sprof.build_manager_password(base, letter, pos)
    if not pw:
        raise ValueError("password or pendingManagerPassword / base+letter required")

    res = sprof.set_manager_password(
        gk,
        pw,
        mark_changed=mark_changed,
        scheme="letter_cycle",
        note="Confirmed after SSH resetpw + Config Client forced change",
        sync_live_profile=True,
        changed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d") if mark_changed else None,
    )
    # clear pending
    prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
    cred = prof.get("credentials") or {}
    for k in ("pendingManagerPassword", "pendingManagerLetter", "pendingManagerNote"):
        cred.pop(k, None)
    prof["credentials"] = cred
    sprof.save_master_profile(gk, prof)
    status = sprof.password_status_summary(cred)
    return {
        "ok": True,
        "message": f"Manager password confirmed in Liferaft ({pw[0]}***). Days remaining recalculated.",
        "passwordLetter": res.get("letter"),
        "passwordBase": res.get("base"),
        "status": status,
        "liferaft": res,
    }


def ssh_capabilities() -> dict[str, Any]:
    has_paramiko = False
    try:
        import paramiko  # noqa: F401

        has_paramiko = True
    except ImportError:
        pass
    plink = _find_plink()
    fleet_d = fleet.get_defaults(include_password=False)
    return {
        "ok": True,
        "paramiko": has_paramiko,
        "plink": str(plink) if plink else None,
        "openssh": bool(shutil.which("ssh")),
        "recommendedEngine": "paramiko" if has_paramiko else ("plink" if plink else "none"),
        "fleetUser": (fleet_d.get("commanderShell") or {}).get("username"),
        "fleetHasPassword": bool((fleet_d.get("commanderShell") or {}).get("hasPassword")),
        "note": (
            "Install paramiko into the toolbox venv for best results "
            "(.venv pip install paramiko). PuTTY plink.exe also works."
        ),
    }
