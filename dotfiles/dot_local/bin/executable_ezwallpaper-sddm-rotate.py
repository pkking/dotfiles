#!/usr/bin/env python3
"""Rotate ezwallpaper, then publish SDDM cache under the canonical flock."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
from typing import NoReturn

PUBLISH_TIMEOUT_SECONDS = 10.0


class WrapperError(RuntimeError):
    """Raised when the wrapper cannot prove its lock contract."""


def _owner_fd() -> int:
    """Return the validated inherited canonical lock descriptor."""
    uid = os.getuid()
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}"))
    try:
        runtime_stat = runtime.lstat()
        if (not stat.S_ISDIR(runtime_stat.st_mode) or runtime_stat.st_uid != uid
                or stat.S_IMODE(runtime_stat.st_mode) != 0o700):
            raise WrapperError("runtime directory is not a user-owned 0700 directory")
        expected = runtime / "ezwallpaper-rotate.lock"
        lock_stat = expected.lstat()
        if (not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != uid
                or lock_stat.st_mode & 0o022):
            raise WrapperError("canonical rotation lock has unsafe type, owner, or write permissions")
        for item in Path("/proc/self/fd").iterdir():
            try:
                fd = int(item.name)
                opened = os.fstat(fd)
                link = os.readlink(item)
            except (ValueError, OSError):
                continue
            if (link == str(expected) and stat.S_ISREG(opened.st_mode)
                    and (opened.st_dev, opened.st_ino) == (lock_stat.st_dev, lock_stat.st_ino)):
                # A separate open description must be unable to acquire the lock;
                # this proves the inherited descriptor is not merely a lock file.
                probe = os.open(expected, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    try:
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return fd
                    else:
                        fcntl.flock(probe, fcntl.LOCK_UN)
                finally:
                    os.close(probe)
        raise WrapperError("canonical flock descriptor proof missing")
    except OSError as exc:
        raise WrapperError("canonical rotation lock is unavailable or unsafe") from exc


def _kill_group_and_reap(proc: subprocess.Popen[object]) -> None:
    """Stop all publisher descendants and reap the publisher process."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def _warn_cleanup(fd: int) -> None:
    """Ask the installed publisher to remove its fixed pending file."""
    script = Path(__file__).with_name("sddm-wallpaper-sync.py")
    code = (
        "import importlib.util; "
        f"s=importlib.util.spec_from_file_location('sddm_sync', {str(script)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.cleanup_after_abort()"
    )
    try:
        subprocess.run([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       close_fds=True, pass_fds=(fd,), timeout=2, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ezwallpaper-sddm-rotate: pending-file cleanup failed: {exc}", file=sys.stderr)


def _signal_exit(signum: int, _frame: object) -> NoReturn:
    raise _Termination(signum)


class _Termination(BaseException):
    def __init__(self, signum: int):
        self.signum = signum


def main() -> int:
    try:
        owner_fd = _owner_fd()
    except WrapperError as exc:
        print(f"ezwallpaper-sddm-rotate: {exc}", file=sys.stderr)
        return 1

    home = Path.home()
    command = [str(home / ".local/bin/ezwallpaper"), "rotate", "next", "--profile",
               str(home / ".config/ezwallpaper/rotation-profile.json"), "--apply"]
    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"ezwallpaper-sddm-rotate: rotation could not start: {exc}", file=sys.stderr)
        return 1
    if result.returncode:
        return result.returncode

    script = Path(__file__).with_name("sddm-wallpaper-sync.py")
    code = (
        "import importlib.util; "
        f"s=importlib.util.spec_from_file_location('sddm_sync', {str(script)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.publish_after_owner_success()"
    )
    proc: subprocess.Popen[bytes] | None = None
    old_handlers = {sig: signal.signal(sig, _signal_exit) for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
    try:
        try:
            proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                                    close_fds=True, pass_fds=(owner_fd,), start_new_session=True)
            proc.wait(timeout=PUBLISH_TIMEOUT_SECONDS)
            if proc.returncode:
                print(f"ezwallpaper-sddm-rotate: cache publication failed ({proc.returncode})", file=sys.stderr)
        except subprocess.TimeoutExpired:
            if proc is not None:
                _kill_group_and_reap(proc)
            print("ezwallpaper-sddm-rotate: cache publication timed out; rotation remains successful", file=sys.stderr)
            _warn_cleanup(owner_fd)
        except (OSError, _Termination) as exc:
            if proc is not None:
                _kill_group_and_reap(proc)
            _warn_cleanup(owner_fd)
            if isinstance(exc, _Termination):
                signal.signal(exc.signum, signal.SIG_DFL)
                signal.raise_signal(exc.signum)
            print(f"ezwallpaper-sddm-rotate: cache publication could not run: {exc}", file=sys.stderr)
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
