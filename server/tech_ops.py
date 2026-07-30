"""
High-impact field-tech helpers for Commander Site Console.

1) Password rotation dashboard — which sites are due / overdue
2) Dead-Manager playbook — per-site recovery card (letter, SSH, who to call)
3) Connectivity preflight — ping / ports / CGILink before you waste time
4) Field pack — one-click SITE-INFO + recovery pack under the backup folder
"""
from __future__ import annotations

import json
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import commander_live as cl
import fleet_tech_ops as fleet
import site_info_ops as site_info
import site_profile_ops as sprof
import survey_share_ops as share
import verifone_ops as vf

OTP_CHEAT_CARD = {
    "configOtp": {
        "title": "Config OTP (Config Client / Journal / Import-Export)",
        "when": "CGILink returns OTPRequired, or secure Config Client actions.",
        "steps": [
            "On the register sales screen: CSR Functions",
            "Maintenance Menu",
            "Generate / Config OTP (often option 10 or 11)",
            "Select Yes",
            "Read the 4-digit code from the register and/or Commander face",
            "Enter it promptly in the login box — codes expire",
        ],
        "phoneAssist": "Phone Assist → Register/CSR → Generate Config OTP",
    },
    "cSiteOtp": {
        "title": "C-Site / Central OTP (different system)",
        "when": "Cloud onboarding / C-Site link — NOT the same as Config OTP.",
        "steps": [
            "Generated in C-Site portal / email for the site operator",
            "Used to link Commander Central / C-Site — not for Manager login",
        ],
    },
    "helpDeskToken": {
        "title": "Help Desk login (SSH / maint shell)",
        "when": "Before PuTTY maint session on many Base 55+ sites.",
        "steps": [
            "On Commander: enable Help Desk login",
            "Enter the visit token from help desk / Verifone process",
            "Then SSH as maint (fleet secret on this PC)",
        ],
        "phoneAssist": "Phone Assist → SSH / resetpw",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def password_rotation_dashboard(*, days_warn: int = 14) -> dict[str, Any]:
    """
    Scan all Liferaft master profiles for Manager letter-cycle due dates.
    Most impactful morning view: overdue + due within days_warn.
    """
    listed = sprof.list_master_profiles()
    rows: list[dict[str, Any]] = []
    for item in listed.get("profiles") or []:
        # list_master_profiles returns rows with groupKey; load full for credentials
        gk = item.get("groupKey")
        if not gk:
            continue
        try:
            prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
        except Exception:
            continue
        cred = prof.get("credentials") or {}
        if (cred.get("passwordScheme") or "letter_cycle") != "letter_cycle":
            continue
        status = sprof.password_status_summary(cred)
        days = status.get("passwordDaysLeft")
        overdue = bool(status.get("passwordOverdue"))
        # include all with a date, or with a letter set
        if not status.get("lastPasswordChangeAt") and not status.get("letter") and not cred.get("configClientPassword"):
            continue
        band = "unknown"
        if overdue:
            band = "overdue"
        elif days is not None and days <= 0:
            band = "overdue"
        elif days is not None and days <= 7:
            band = "urgent"
        elif days is not None and days <= days_warn:
            band = "soon"
        elif days is not None:
            band = "ok"
        elif status.get("lastPasswordChangeAt"):
            band = "unknown"
        else:
            band = "no_date"

        ident = prof.get("identity") or {}
        cmd = prof.get("commander") or {}
        rows.append(
            {
                "groupKey": gk,
                "displayName": ident.get("displayName") or ident.get("storeName") or item.get("displayName") or gk,
                "customer": ident.get("customer") or item.get("customer") or "",
                "siteId": ident.get("siteId") or item.get("siteId") or "",
                "hostIp": cmd.get("hostIp") or (prof.get("network") or {}).get("lanIp") or item.get("hostIp") or "",
                "letter": status.get("letter") or "",
                "base": status.get("base") or "",
                "nextLetter": status.get("nextLetter") or "",
                "nextPasswordPreview": status.get("nextPasswordPreview") or "",
                "passwordDaysLeft": days,
                "passwordOverdue": overdue,
                "lastPasswordChangeAt": (status.get("lastPasswordChangeAt") or "")[:10],
                "nextPasswordDueAt": (status.get("nextPasswordDueAt") or "")[:10],
                "statusText": status.get("statusText") or "",
                "band": band,
                "hasPassword": bool(cred.get("configClientPassword")),
            }
        )

    order = {"overdue": 0, "urgent": 1, "soon": 2, "no_date": 3, "unknown": 4, "ok": 5}
    rows.sort(key=lambda r: (order.get(r["band"], 9), r.get("passwordDaysLeft") if r.get("passwordDaysLeft") is not None else 9999, (r.get("displayName") or "").lower()))

    summary = {
        "overdue": sum(1 for r in rows if r["band"] == "overdue"),
        "urgent": sum(1 for r in rows if r["band"] == "urgent"),
        "soon": sum(1 for r in rows if r["band"] == "soon"),
        "no_date": sum(1 for r in rows if r["band"] == "no_date"),
        "ok": sum(1 for r in rows if r["band"] == "ok"),
        "totalTracked": len(rows),
        "daysWarn": days_warn,
    }
    action = [r for r in rows if r["band"] in {"overdue", "urgent", "soon", "no_date"}]
    return {
        "ok": True,
        "summary": summary,
        "actionRequired": action,
        "all": rows,
        "generatedAt": _utc_now(),
        "message": (
            f"{summary['overdue']} overdue · {summary['urgent']} ≤7d · {summary['soon']} ≤{days_warn}d · "
            f"{summary['no_date']} missing change date · {summary['ok']} OK"
        ),
    }


def dead_manager_playbook(
    *,
    group_key: str | None = None,
    export_id: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    """Per-site card: recover when Manager password is unknown / locked out."""
    prof: dict[str, Any] = {}
    gk = None
    try:
        if group_key or export_id:
            gk = sprof.resolve_group_key(group_key, export_id)
            prof = sprof.get_master_profile(group_key=gk, export_id=export_id, merge_sources=True)
    except Exception:
        prof = {}

    cred = (prof or {}).get("credentials") or {}
    cmd = (prof or {}).get("commander") or {}
    net = (prof or {}).get("network") or {}
    em = (prof or {}).get("emergency") or {}
    ident = (prof or {}).get("identity") or {}
    status = sprof.password_status_summary(cred)

    host_ip = (host or cred.get("sshHost") or cmd.get("hostIp") or net.get("lanIp") or "").strip()
    shell = fleet.shell_for_site(
        host=host_ip or None,
        site_password=cred.get("sshPassword") or None,
        site_user=cred.get("sshUser") or None,
        site_port=int(cred["sshPort"]) if cred.get("sshPort") else None,
    )

    letter = status.get("letter") or cred.get("passwordLetter") or ""
    base = status.get("base") or cred.get("passwordBase") or ""
    next_letter = status.get("nextLetter") or ""
    next_pw = status.get("nextPasswordPreview") or ""
    known_pw = bool(cred.get("configClientPassword"))

    steps = [
        {
            "id": "try_known",
            "title": "Try known Manager password from Liferaft",
            "detail": (
                f"User: {cred.get('configClientUser') or 'Manager'} · "
                f"Letter {letter or '—'} · base {base or '—'} · "
                + ("password is stored in Liferaft" if known_pw else "no password stored — skip")
            ),
            "when": known_pw,
        },
        {
            "id": "otp",
            "title": "If OTP required — Config OTP from register",
            "detail": "CSR Functions → Maintenance → Generate/Config OTP (4-digit). Not C-Site OTP.",
            "when": True,
        },
        {
            "id": "ssh_reset",
            "title": "SSH resetpw manager (this PC fleet maint secret)",
            "detail": (
                f"Host {host_ip or '—'} · user {shell.get('username') or 'maint'} · "
                f"`resetpw manager` → temp password → Config Client force-change to "
                f"{next_pw or (letter and base and (letter + base)) or 'letter+base'}."
            ),
            "when": bool(host_ip),
            "tool": "Site Console → Overview → resetpw manager",
        },
        {
            "id": "helpdesk",
            "title": "Enable Help Desk login + token on Commander first if SSH fails",
            "detail": cred.get("sshHelpDeskNotes") or shell.get("helpDeskLogin") or "",
            "when": True,
        },
        {
            "id": "call_site",
            "title": "Call site contact / owner for Manager password",
            "detail": (
                f"{ident.get('contactName') or ''} {ident.get('contactPhone') or ident.get('phone') or ''} "
                f"· after hours: {em.get('escalation') or 'see Liferaft emergency'}"
            ).strip(),
            "when": True,
        },
        {
            "id": "document",
            "title": "After recovery — document",
            "detail": "Set letter + last-change date in Liferaft · Confirm final password · Write SITE-INFO.md",
            "when": True,
        },
    ]

    dont = [
        "Don't spray random letter+base guesses (lockouts / noise).",
        "Don't power-cycle Commander as a password fix.",
        "Don't share temp passwords in email/ticket bodies — Liferaft / SITE-INFO local only.",
        em.get("knownGotchas") or "",
    ]
    dont = [d for d in dont if d]

    return {
        "ok": True,
        "groupKey": gk,
        "displayName": ident.get("displayName") or ident.get("storeName") or gk,
        "hostIp": host_ip,
        "manager": {
            "user": cred.get("configClientUser") or "Manager",
            "hasPassword": known_pw,
            "letter": letter,
            "base": base,
            "nextLetter": next_letter,
            "nextPasswordPreview": next_pw,
            "daysLeft": status.get("passwordDaysLeft"),
            "overdue": status.get("passwordOverdue"),
            "statusText": status.get("statusText"),
            "lastChange": (status.get("lastPasswordChangeAt") or "")[:10],
        },
        "ssh": {
            "host": host_ip,
            "port": shell.get("port") or 22,
            "user": shell.get("username") or "maint",
            "hasFleetPassword": bool(shell.get("password")),
            "resetCmd": "resetpw manager",
        },
        "contacts": {
            "phone": ident.get("phone") or "",
            "contactName": ident.get("contactName") or "",
            "contactPhone": ident.get("contactPhone") or "",
            "helpDesk": ident.get("helpDesk") or "",
            "escalation": em.get("escalation") or "",
            "lastTech": em.get("lastTechOnSite") or "",
            "whatBreaksFirst": em.get("whatBreaksFirst") or "",
        },
        "otpCard": OTP_CHEAT_CARD,
        "steps": steps,
        "doNot": dont,
        "message": "Dead-Manager playbook — try Liferaft password → OTP → SSH resetpw → call site → document.",
    }


def _tcp_open(host: str, port: int, timeout: float = 1.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def connectivity_preflight(host: str, *, username: str = "Manager", password: str = "") -> dict[str, Any]:
    """
    Quick LAN preflight before Journal / IE / SSH.
    Ping + common ports + optional CGILink validate if password provided.
    """
    host = (host or "").strip()
    if not host:
        raise ValueError("host required")

    t0 = time.time()
    checks: list[dict[str, Any]] = []

    # TCP ping substitute on ports
    for port, label in ((80, "HTTP :80"), (443, "HTTPS :443"), (22, "SSH :22"), (8080, "Alt :8080")):
        t1 = time.time()
        open_ = _tcp_open(host, port, timeout=1.0)
        checks.append(
            {
                "id": f"tcp_{port}",
                "label": label,
                "ok": open_,
                "ms": round((time.time() - t1) * 1000),
                "detail": "open" if open_ else "closed / filtered",
            }
        )

    # Lightweight reachability: TCP 80 or 7; optional OS ping
    try:
        t1 = time.time()
        # Prefer tcp_probe helper if present
        pr = cl.tcp_probe(host, 80, timeout=1.0) if hasattr(cl, "tcp_probe") else {"open": _tcp_open(host, 80)}
        checks.insert(
            0,
            {
                "id": "reach",
                "label": "Host reach (:80 probe)",
                "ok": bool(pr.get("open")),
                "detail": "responded" if pr.get("open") else "no response",
                "ms": round((time.time() - t1) * 1000),
            },
        )
    except Exception as e:  # noqa: BLE001
        checks.insert(0, {"id": "reach", "label": "Host reach", "ok": None, "detail": str(e)})

    http80 = next((c for c in checks if c["id"] == "tcp_80"), {})
    lan_guess = "unknown"
    if http80.get("ok") and next((c for c in checks if c["id"] == "tcp_22"), {}).get("ok"):
        lan_guess = "likely_store_lan_or_full_access"
    elif http80.get("ok"):
        lan_guess = "web_ok_check_if_payment_isolated"
    elif next((c for c in checks if c["id"] == "tcp_22"), {}).get("ok"):
        lan_guess = "ssh_only_unusual"
    else:
        lan_guess = "no_commander_ports_wrong_vlan_or_offline"

    login = None
    if password:
        try:
            login = cl.sapphire_cgi_link(
                host,
                "validate",
                params={"user": username or "Manager", "passwd": password},
                timeout=8.0,
            )
            checks.append(
                {
                    "id": "cgilink",
                    "label": "CGILink validate",
                    "ok": bool(login.get("cookie")),
                    "detail": (
                        "session cookie OK"
                        if login.get("cookie")
                        else (login.get("faultMessage") or login.get("faultCode") or "no cookie")
                    ),
                    "otpRequired": bool(login.get("otpRequired")),
                }
            )
        except Exception as e:  # noqa: BLE001
            checks.append({"id": "cgilink", "label": "CGILink validate", "ok": False, "detail": str(e)})

    tips = []
    if lan_guess == "no_commander_ports_wrong_vlan_or_offline":
        tips.append("No :80/:22 — confirm laptop is on store LAN (not guest Wi‑Fi / payment-only NIC).")
    if lan_guess == "web_ok_check_if_payment_isolated":
        tips.append("Web open; if SSH fails, Help Desk login may be required or SSH firewalled.")
    if any(c.get("id") == "cgilink" and c.get("otpRequired") for c in checks):
        tips.append("OTP required — Phone Assist → CSR → Config OTP.")
    if any(c.get("id") == "cgilink" and c.get("ok") is False and password for c in checks):
        tips.append("Credentials rejected — try Liferaft letter/base or SSH resetpw manager.")

    ok_any = any(c.get("ok") for c in checks if c.get("id", "").startswith("tcp"))
    return {
        "ok": ok_any,
        "host": host,
        "checks": checks,
        "lanGuess": lan_guess,
        "tips": tips,
        "ms": round((time.time() - t0) * 1000),
        "otpCard": OTP_CHEAT_CARD["configOtp"],
        "message": f"Preflight {host}: {'reachable' if ok_any else 'not reachable on common ports'}",
    }


def build_field_pack(
    site_key: str,
    *,
    group_key: str | None = None,
    include_redacted_share: bool = True,
    seed_layout_if_empty: bool = True,
) -> dict[str, Any]:
    """
    One-click field pack into the backup folder:
      SITE-INFO.md, dead-manager playbook, OTP card, password status,
      optional redacted share pack, layout seed.
    """
    row = vf.get_site(site_key)
    if not row:
        raise FileNotFoundError("Site export not found")
    export_path = Path(row["path"])
    pack_dir = export_path / "survey" / "field-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = pack_dir / f"field_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # 1) SITE-INFO
    info = site_info.write_site_info_md(site_key, also_seed_layout=seed_layout_if_empty)
    # copy SITE-INFO into pack as well
    src_md = Path(info["path"])
    dest_md = folder / "SITE-INFO.md"
    if src_md.is_file():
        dest_md.write_text(src_md.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(str(dest_md))

    # 2) Dead manager playbook
    play = dead_manager_playbook(group_key=group_key, export_id=site_key)
    play_path = folder / "DEAD-MANAGER-PLAYBOOK.json"
    play_path.write_text(json.dumps(play, indent=2), encoding="utf-8")
    written.append(str(play_path))
    play_md = folder / "DEAD-MANAGER-PLAYBOOK.md"
    play_md.write_text(_playbook_to_md(play), encoding="utf-8", newline="\n")
    written.append(str(play_md))

    # 3) OTP cheat card
    otp_path = folder / "OTP-CHEAT-CARD.md"
    otp_path.write_text(_otp_card_md(), encoding="utf-8", newline="\n")
    written.append(str(otp_path))

    # 4) Password status snippet
    pwd_path = folder / "PASSWORD-STATUS.json"
    pwd_path.write_text(
        json.dumps(play.get("manager") or {}, indent=2),
        encoding="utf-8",
    )
    written.append(str(pwd_path))

    # 5) Optional redacted share
    share_res = None
    if include_redacted_share:
        try:
            share_res = share.export_share_pack(site_key, mode="redacted", include_photos=False)
            if share_res.get("path"):
                written.append(str(share_res["path"]))
        except Exception as e:  # noqa: BLE001
            share_res = {"ok": False, "error": str(e)}

    # 6) README
    readme = folder / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# Field pack — {play.get('displayName') or site_key}",
                "",
                f"Generated: {_utc_now()}",
                "",
                "Local / USB only if SITE-INFO contains passwords.",
                "",
                "## Contents",
                "- `SITE-INFO.md` — users, Manager days, network, equipment, SSH",
                "- `DEAD-MANAGER-PLAYBOOK.md` — recovery order",
                "- `OTP-CHEAT-CARD.md` — Config vs C-Site vs Help Desk",
                "- `PASSWORD-STATUS.json` — letter / days left snapshot",
                "- Redacted survey pack path (if built) — review before email",
                "",
                "## Tools on laptop",
                "- Site Console → Overview (resetpw, SITE-INFO, preflight)",
                "- Phone Assist Navigator (CSR / Veeder TLS / SSH scripts)",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    written.append(str(readme))

    return {
        "ok": True,
        "folder": str(folder),
        "files": written,
        "siteInfo": {"path": info.get("path"), "counts": info.get("counts"), "passwordStatus": info.get("passwordStatus")},
        "playbook": {"displayName": play.get("displayName"), "hostIp": play.get("hostIp")},
        "share": share_res,
        "message": f"Field pack written under {folder}",
    }


def _playbook_to_md(play: dict[str, Any]) -> str:
    m = play.get("manager") or {}
    ssh = play.get("ssh") or {}
    lines = [
        f"# Dead-Manager playbook — {play.get('displayName') or ''}",
        "",
        f"Host: `{play.get('hostIp') or '—'}`",
        "",
        "## Manager status",
        f"- User: {m.get('user')}",
        f"- Letter: **{m.get('letter') or '—'}** · base `{m.get('base') or '—'}`",
        f"- Days left: **{m.get('daysLeft') if m.get('daysLeft') is not None else '—'}** ({m.get('statusText') or ''})",
        f"- Next: {m.get('nextPasswordPreview') or '—'}",
        f"- Password in Liferaft: {'yes' if m.get('hasPassword') else 'no'}",
        f"- Last change: {m.get('lastChange') or '—'}",
        "",
        "## SSH",
        f"- `{ssh.get('user')}@{ssh.get('host')}:{ssh.get('port')}`",
        f"- Fleet maint password on this PC: {'yes' if ssh.get('hasFleetPassword') else 'no'}",
        f"- Command: `{ssh.get('resetCmd')}`",
        "",
        "## Steps",
    ]
    for i, s in enumerate(play.get("steps") or [], 1):
        if s.get("when") is False:
            continue
        lines.append(f"{i}. **{s.get('title')}** — {s.get('detail')}")
        if s.get("tool"):
            lines.append(f"   - Tool: {s['tool']}")
    lines.extend(["", "## Do not", ""])
    for d in play.get("doNot") or []:
        lines.append(f"- {d}")
    lines.append("")
    return "\n".join(lines)


def _otp_card_md() -> str:
    lines = ["# OTP / token cheat card", ""]
    for key, card in OTP_CHEAT_CARD.items():
        lines.append(f"## {card.get('title')}")
        lines.append(f"_When:_ {card.get('when')}")
        lines.append("")
        for s in card.get("steps") or []:
            lines.append(f"- {s}")
        if card.get("phoneAssist"):
            lines.append(f"- Phone Assist: {card['phoneAssist']}")
        lines.append("")
    return "\n".join(lines)


def log_call_outcome(
    group_key: str | None = None,
    export_id: str | None = None,
    *,
    summary: str,
    what_failed: str = "",
    resolved: bool = False,
) -> dict[str, Any]:
    """Append a quick after-call note to Liferaft emergency block."""
    gk = sprof.resolve_group_key(group_key, export_id)
    prof = sprof.get_master_profile(group_key=gk, merge_sources=False)
    em = prof.setdefault("emergency", {})
    stamp = _utc_now()[:16].replace("T", " ")
    line = f"[{stamp}] {'RESOLVED' if resolved else 'OPEN'}: {summary}"
    if what_failed:
        line += f" | failed: {what_failed}"
    prev = (em.get("liferaftNotes") or "").strip()
    em["liferaftNotes"] = (line + ("\n" + prev if prev else "")).strip()
    if what_failed and not em.get("whatBreaksFirst"):
        em["whatBreaksFirst"] = what_failed
    if resolved:
        em["lastVisitDate"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prof["emergency"] = em
    sprof.save_master_profile(gk, prof)
    return {"ok": True, "groupKey": gk, "note": line, "message": "Call outcome logged to Liferaft emergency notes"}
