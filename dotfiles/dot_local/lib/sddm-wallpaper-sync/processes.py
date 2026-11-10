"""Linux child-process containment for the SDDM wallpaper tools."""
from __future__ import annotations

import contextlib
import ctypes
import errno
import os
from pathlib import Path
import signal
import time
from collections.abc import Iterator

_PR_GET_CHILD_SUBREAPER = 37
_PR_SET_CHILD_SUBREAPER = 36
_libc = ctypes.CDLL(None, use_errno=True)


class CleanupError(RuntimeError):
    """The bounded cleanup could not confirm that all scoped children exited."""


def _subreaper_flag() -> bool:
    value = ctypes.c_int()
    if _libc.prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(value), 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return bool(value.value)


def _set_subreaper(enabled: bool) -> None:
    if _libc.prctl(_PR_SET_CHILD_SUBREAPER, int(enabled), 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _direct_children() -> set[int]:
    """Return direct child PIDs for every thread in this process."""
    result: set[int] = set()
    for path in Path('/proc/self/task').glob('*/children'):
        try:
            result.update(int(pid) for pid in path.read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            continue
    return result


def _reap_scoped(baseline: set[int], deadline: float) -> None:
    """Kill/reap children adopted since entry, iterating across a bounded tree."""
    remaining: set[int] = set()
    while time.monotonic() < deadline:
        current = _direct_children() - baseline
        if not current and not remaining:
            return
        remaining.update(current)
        progressed = False
        for pid in tuple(remaining):
            try:
                waited, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                remaining.discard(pid)
                progressed = True
                continue
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                if exc.errno == errno.ECHILD:
                    remaining.discard(pid)
                    progressed = True
                    continue
                raise
            if waited == pid:
                remaining.discard(pid)
                progressed = True
                continue
            # waitpid returned 0: this exact PID is still our unreaped child,
            # so it cannot have been reused for an unrelated process.
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass
        if not progressed:
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    unresolved = _direct_children() - baseline
    if unresolved or remaining:
        raise CleanupError(f"scoped child cleanup deadline expired ({len(unresolved | remaining)} children remain)")


@contextlib.contextmanager
def subreaper_scope(cleanup_seconds: float = 1.0) -> Iterator[None]:
    """Adopt and clean this sequential command's new orphaned descendants.

    Existing direct children are recorded and never waited for or signalled.
    Linux subreaper state is process-local and restored to its prior value.
    """
    previous = _subreaper_flag()
    baseline = _direct_children()
    _set_subreaper(True)
    try:
        yield
    finally:
        try:
            _reap_scoped(baseline, time.monotonic() + max(0.0, cleanup_seconds))
        finally:
            _set_subreaper(previous)
