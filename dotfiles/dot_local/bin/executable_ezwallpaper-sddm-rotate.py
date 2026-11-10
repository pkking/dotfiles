#!/usr/bin/env python3
"""Run canonical ezwallpaper rotation and publish while its flock remains held."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time


def _owner_fd() -> int:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    expected = runtime / "ezwallpaper-rotate.lock"
    try:
        target = expected.stat()
    except OSError as exc:
        raise RuntimeError("canonical rotation lock is unavailable") from exc
    if not stat.S_ISREG(target.st_mode) or target.st_uid != os.getuid() or target.st_mode & 0o077:
        raise RuntimeError("canonical rotation lock has unsafe ownership or mode")
    for item in Path("/proc/self/fd").iterdir():
        try:
            fd = int(item.name)
            opened = os.fstat(fd)
            link = os.readlink(item)
        except (ValueError, OSError):
            continue
        if link == str(expected) and stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) == (target.st_dev, target.st_ino):
            try:
                # On the inherited open-file-description this validates/retains
                # the exclusive lock; if flock was omitted it acquires it here.
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                continue
            return fd
    raise RuntimeError("canonical flock descriptor proof missing")


def main() -> int:
    try:
        _owner_fd()  # held until process exit; fail before invoking the rotator
    except RuntimeError as exc:
        print(f"ezwallpaper-sddm-rotate: {exc}", file=sys.stderr)
        return 1
    home = Path.home()
    command = [str(home / ".local/bin/ezwallpaper"), "rotate", "next", "--profile",
               str(home / ".config/ezwallpaper/rotation-profile.json"), "--apply"]
    result = subprocess.run(command, check=False)
    if result.returncode:
        return result.returncode

    script = Path(__file__).with_name("executable_sddm-wallpaper-sync.py")
    code = "import importlib.util; s=importlib.util.spec_from_file_location('sync', %r); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.publish_after_owner_success()" % str(script)
    proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 10
    try:
        status = proc.wait(timeout=max(0, deadline - time.monotonic()))
        if status:
            print(f"ezwallpaper-sddm-rotate: cache publication failed ({status})", file=sys.stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        print("ezwallpaper-sddm-rotate: cache publication timed out; rotation remains successful", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
