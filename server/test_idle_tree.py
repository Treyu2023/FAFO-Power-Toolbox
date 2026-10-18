"""Idle stop must treat the venv stub and the real interpreter as one server.

DIRT-1: the kill paths are covered with a fake psutil and a fake taskkill. Nothing here
starts, signals or kills a real process.
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launch_ops
from launch_ops import same_server_parent


def test_s1_venv_stub_matches_real_interpreter() -> None:
    parent = r"C:\toolbox\.venv\Scripts\pythonw.exe C:\toolbox\server\aitoolbox_server.py"
    child = r"C:\Python311\pythonw.exe C:\toolbox\server\aitoolbox_server.py"
    assert same_server_parent(parent, child)


def test_s2_watch_supervisor_matches_its_server() -> None:
    parent = r"C:\Python311\pythonw.exe C:\ext\explorer-meta\server.py --watch"
    child = r"C:\toolbox\.venv\Scripts\pythonw.exe C:\ext\explorer-meta\server.py"
    assert same_server_parent(parent, child)


def test_watchdog_and_tray_are_not_server_parents() -> None:
    child = r"C:\Python311\pythonw.exe C:\toolbox\server\aitoolbox_server.py"
    assert not same_server_parent(r"C:\Python311\pythonw.exe C:\toolbox\server\server_watchdog.py", child)
    assert not same_server_parent(r"C:\Python311\pythonw.exe C:\toolbox\server\tray_launcher.py", child)


def test_unrelated_python_is_not_the_same_server() -> None:
    parent = r"C:\pinokio\bin\miniconda\python.exe -u webui.py"
    child = r"C:\Python311\pythonw.exe C:\toolbox\server\aitoolbox_server.py"
    assert not same_server_parent(parent, child)


# --- DIRT-1: fake process table, fake psutil, fake taskkill (no real process is touched) ---
PY = r"C:\Python311\pythonw.exe"
VENV = r"C:\toolbox\.venv\Scripts\pythonw.exe"
S1 = r"C:\toolbox\server\aitoolbox_server.py"


class _Error(Exception):
    pass


class _NoSuchProcess(_Error):
    pass


class _AccessDenied(_Error):
    pass


class FakeWorld:
    """pid -> name, cmd (None = unreadable), ppid, alive; taskkill outcomes per pid."""

    def __init__(self, procs, me=1):
        self.procs = {pid: dict(name=n, cmd=c, ppid=pp, alive=True, create=pid * 10) for pid, (n, c, pp) in procs.items()}
        self.me = me
        self.calls = []          # taskkill argv lists
        self.kills = []          # POSIX proc.kill() pids
        self.rc = {}             # pid -> forced taskkill return code
        self.survive = set()     # taskkill says 0 but the process stays alive
        self.conns = []

    def psutil(self):
        world = self
        mod = types.ModuleType("psutil")
        mod.Error, mod.NoSuchProcess, mod.AccessDenied = _Error, _NoSuchProcess, _AccessDenied
        mod.CONN_LISTEN = "LISTEN"

        class Process:
            def __init__(self, pid):
                self.pid = int(pid)
                p = world.procs.get(self.pid)
                if not p or not p["alive"]:
                    raise _NoSuchProcess(pid)
                self._create = p["create"]

            def _p(self):
                p = world.procs.get(self.pid)
                if not p or not p["alive"] or p["create"] != self._create:
                    raise _NoSuchProcess(self.pid)
                return p

            def name(self):
                return self._p()["name"]

            def cmdline(self):
                cmd = self._p()["cmd"]
                if cmd is None:
                    raise _AccessDenied(self.pid)
                return cmd.split(" ")

            def ppid(self):
                return self._p()["ppid"]

            def parent(self):
                pp = self._p()["ppid"]
                try:
                    return Process(pp)
                except _NoSuchProcess:
                    return None

            def children(self, recursive=False):
                self._p()
                out, todo = [], [self.pid]
                while todo:
                    cur = todo.pop(0)
                    for pid, p in sorted(world.procs.items()):
                        if p["ppid"] == cur and p["alive"]:
                            out.append(Process(pid))
                            if recursive:
                                todo.append(pid)
                return out

            def is_running(self):
                try:
                    self._p()
                    return True
                except _NoSuchProcess:
                    return False

            def kill(self):
                self._p()
                world.kills.append(self.pid)
                world.procs[self.pid]["alive"] = False

        def wait_procs(procs, timeout=None):
            gone = [p for p in procs if not p.is_running()]
            return gone, [p for p in procs if p.is_running()]

        def net_connections(kind="inet"):
            return list(world.conns)

        def process_iter(attrs=None):
            for pid, p in sorted(world.procs.items()):
                if p["alive"]:
                    yield types.SimpleNamespace(info={"pid": pid, "name": p["name"], "cmdline": (p["cmd"] or "").split(" ") if p["cmd"] else []})

        mod.Process, mod.wait_procs, mod.net_connections, mod.process_iter = Process, wait_procs, net_connections, process_iter
        return mod

    def subprocess(self):
        world = self

        def run(argv, **kw):
            world.calls.append(list(argv))
            assert argv[0] == "taskkill" and "/T" not in argv, argv
            pid = int(argv[argv.index("/PID") + 1])
            rc = world.rc.get(pid)
            p = world.procs.get(pid)
            if rc is None:
                rc = 0 if p and p["alive"] else 128
            if rc == 0 and p and pid not in world.survive:
                p["alive"] = False
            return types.SimpleNamespace(returncode=rc, stdout=b"", stderr=b"")

        return types.SimpleNamespace(run=run, TimeoutExpired=TimeoutError, CREATE_NO_WINDOW=0x08000000)

    def alive(self):
        return sorted(pid for pid, p in self.procs.items() if p["alive"])


class patched:
    """Install the fake world into launch_ops for one test; restore everything afterwards."""

    def __init__(self, world, windows=True):
        self.world, self.windows = world, windows

    def __enter__(self):
        self.saved = (sys.modules.get("psutil", None), "psutil" in sys.modules, launch_ops.subprocess,
                      launch_ops.IS_WINDOWS, launch_ops.os.getpid, launch_ops.os.kill, launch_ops._KILL_CONFIRM_SEC)
        sys.modules["psutil"] = self.world.psutil()
        launch_ops.subprocess = self.world.subprocess()
        launch_ops.IS_WINDOWS = self.windows
        launch_ops.os.getpid = lambda: self.world.me

        def no_real_kill(*a, **k):
            raise AssertionError("os.kill must not be called")

        launch_ops.os.kill = no_real_kill
        launch_ops._KILL_CONFIRM_SEC = 0
        return self.world

    def __exit__(self, *exc):
        mod, had, sp, win, getpid, kill, sec = self.saved
        if had:
            sys.modules["psutil"] = mod
        else:
            sys.modules.pop("psutil", None)
        launch_ops.subprocess, launch_ops.IS_WINDOWS, launch_ops._KILL_CONFIRM_SEC = sp, win, sec
        launch_ops.os.getpid, launch_ops.os.kill = getpid, kill
        return False


def s1_tree():
    """tray 10 -> S1 venv stub 20 -> S1 interpreter 21 -> ffmpeg 30, and things S1 started:
    watchdog 40 (-> its own S2 41), tray 50, vault launcher 60 -> vault 61 (-> vault http 62),
    an unreadable child 70 (-> 71), and a git clone 80."""
    return FakeWorld({
        10: ("pythonw.exe", PY + r" C:\toolbox\server\tray_launcher.py", 2),
        20: ("pythonw.exe", VENV + " " + S1, 10),
        21: ("pythonw.exe", PY + " " + S1, 20),
        30: ("ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe -i a.mp4 b.mp4", 21),
        40: ("pythonw.exe", PY + r" C:\toolbox\server\server_watchdog.py --loop", 21),
        41: ("pythonw.exe", PY + r" C:\ext\explorer-meta\server.py", 40),
        50: ("pythonw.exe", PY + r" C:\toolbox\server\tray_launcher.py", 21),
        60: ("powershell.exe", r"powershell -File C:\toolbox\System Tools\ImagineTracker\Launch-ImagineVault.ps1", 21),
        61: ("pythonw.exe", PY + r" -u C:\toolbox\System Tools\ImagineTracker\ImagineVault.py --watch", 60),
        62: ("pythonw.exe", PY + r" -u C:\toolbox\System Tools\ImagineTracker\ImagineVault.py", 61),
        70: ("svc.exe", None, 21),
        71: ("helper.exe", r"C:\x\helper.exe", 70),
        80: ("git.exe", r"git clone https://example.invalid/r.git", 21),
    })


def test_tree_root_climbs_venv_stub_and_stops_at_tray() -> None:
    with patched(s1_tree()):
        assert launch_ops._server_tree_root(21) == 20


def test_tree_root_stops_at_watchdog_non_python_and_unreadable_parent() -> None:
    w = FakeWorld({
        5: ("pythonw.exe", PY + r" C:\toolbox\server\server_watchdog.py", 2),
        6: ("pythonw.exe", PY + " " + S1, 5),
        7: ("explorer.exe", r"C:\Windows\explorer.exe", 2),
        8: ("pythonw.exe", PY + " " + S1, 7),
        9: ("pythonw.exe", None, 2),
        11: ("pythonw.exe", PY + " " + S1, 9),
    })
    with patched(w):
        assert launch_ops._server_tree_root(6) == 6
        assert launch_ops._server_tree_root(8) == 8
        assert launch_ops._server_tree_root(11) == 11


def test_kill_tree_spares_watchdog_tray_vault_and_unreadable_subtrees() -> None:
    with patched(s1_tree()) as w:
        killed = launch_ops._kill_pid_tree(20)
        assert sorted(killed) == [20, 21, 30, 60, 80], killed
        assert w.alive() == [10, 40, 41, 50, 61, 62, 70, 71], w.alive()
        assert all("/T" not in c for c in w.calls)
        assert [int(c[2]) for c in w.calls][:2] == [20, 21]          # parents first
        rep = launch_ops._LAST_KILL_REPORT
        assert sorted(rep["protected"]) == [40, 41, 50, 61, 62, 70, 71] and rep["failed"] == []


def test_kill_tree_refuses_protected_unreadable_self_and_bad_root() -> None:
    w = s1_tree()
    w.procs[90] = dict(name="pythonw.exe", cmd=None, ppid=2, alive=True, create=900)
    with patched(w):
        assert launch_ops._kill_pid_tree(10) == []                  # tray
        assert launch_ops._kill_pid_tree(40) == []                  # watchdog
        assert launch_ops._kill_pid_tree(61) == []                  # vault
        assert launch_ops._kill_pid_tree(90) == []                  # unreadable command line
        assert launch_ops._kill_pid_tree(1) == []                   # this process
        assert launch_ops._kill_pid_tree(0) == [] and launch_ops._kill_pid_tree("x") == []
        assert launch_ops._kill_pid_tree(12345) == []               # already gone
        assert w.calls == [] and 90 in w.alive()


def test_taskkill_failure_is_not_reported_as_killed() -> None:
    w = s1_tree()
    w.rc[30] = 1                                                    # access denied on ffmpeg
    with patched(w):
        killed = launch_ops._kill_pid_tree(20)
        assert 30 not in killed and 30 in w.alive()
        assert launch_ops._LAST_KILL_REPORT["failed"] == [30]


def test_taskkill_zero_but_still_alive_is_not_confirmed() -> None:
    w = s1_tree()
    w.survive.add(21)
    with patched(w):
        killed = launch_ops._kill_pid_tree(20)
        assert 21 not in killed and 21 in w.alive() and 20 in killed


def test_process_already_gone_counts_as_gone_without_a_stale_pid_kill() -> None:
    w = s1_tree()
    with patched(w):
        import psutil  # the fake
        procs_before = psutil.Process(20).children(recursive=True)
        assert procs_before
        w.procs[80]["alive"] = False                                # git clone ends before the kill
        w.procs[80] = dict(name="notepad.exe", cmd=r"C:\notepad.exe", ppid=2, alive=True, create=1)  # PID reused
        killed = launch_ops._kill_pid_tree(20)
        assert 80 not in [int(c[2]) for c in w.calls] and 80 in w.alive()
        assert 80 not in killed


def test_posix_path_uses_process_kill_not_taskkill() -> None:
    with patched(s1_tree(), windows=False) as w:
        killed = launch_ops._kill_pid_tree(20)
        assert sorted(killed) == [20, 21, 30, 60, 80] and w.calls == []
        assert sorted(w.kills) == [20, 21, 30, 60, 80]


def test_self_inside_the_tree_is_killed_last() -> None:
    w = s1_tree()
    w.me = 21                                                       # called from inside S1 itself
    with patched(w):
        launch_ops._kill_pid_tree(20)
        assert int(w.calls[-1][2]) == 21


def test_no_psutil_means_no_kill() -> None:
    w = s1_tree()
    with patched(w):
        sys.modules["psutil"] = None                                # import psutil -> ImportError
        assert launch_ops._kill_pid_tree(20) == []
        assert launch_ops.stop_listener_on_port(18765, "127.0.0.87") == []
        assert w.calls == []


def _conn(ip, port, pid, status="LISTEN"):
    return types.SimpleNamespace(status=status, laddr=types.SimpleNamespace(ip=ip, port=port), pid=pid)


def test_stop_listener_honours_host_hint() -> None:
    w = s1_tree()
    w.procs[95] = dict(name="python.exe", cmd=PY + r" C:\other\aitoolbox_server.py", ppid=2, alive=True, create=950)
    w.conns = [_conn("10.0.0.5", 18765, 95), _conn("127.0.0.87", 18765, 21), _conn("127.0.0.87", 18765, 21, "ESTABLISHED")]
    with patched(w):
        killed = launch_ops.stop_listener_on_port(18765, "127.0.0.87")
        assert sorted(killed) == [20, 21, 30, 60, 80], killed
        assert 95 in w.alive() and 40 in w.alive() and 61 in w.alive() and 10 in w.alive()


def test_stop_listener_accepts_wildcard_and_loopback_listeners() -> None:
    w = FakeWorld({20: ("pythonw.exe", VENV + " " + S1, 2), 21: ("pythonw.exe", PY + " " + S1, 20)})
    w.conns = [_conn("0.0.0.0", 18765, 21)]
    with patched(w):
        assert sorted(launch_ops.stop_listener_on_port(18765, "127.0.0.87")) == [20, 21]


def test_stop_meta_tree_kills_watch_pair_and_spares_vault() -> None:
    w = FakeWorld({
        10: ("pythonw.exe", PY + r" C:\toolbox\server\tray_launcher.py", 2),
        30: ("python.exe", PY + r" C:\ext\explorer-meta\server.py --watch", 10),
        31: ("pythonw.exe", VENV + r" C:\ext\explorer-meta\server.py", 30),
        61: ("pythonw.exe", PY + r" -u C:\toolbox\System Tools\ImagineTracker\ImagineVault.py --watch", 2),
    })
    w.conns = [_conn("127.0.0.1", 8765, 31)]
    saved = launch_ops._localappdata
    with tempfile.TemporaryDirectory(prefix="dirt1-test-") as tmp:
        launch_ops._localappdata = lambda: Path(tmp)
        try:
            with patched(w):
                killed = launch_ops._stop_meta_tree()
            assert sorted(killed) == [30, 31], killed
            assert w.alive() == [10, 61]
            assert (Path(tmp) / "FAFO" / "ExplorerMeta" / "stop.flag").read_text(encoding="utf-8") == "stop\n"
        finally:
            launch_ops._localappdata = saved


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"ok ({len(tests)} tests)")
