"""Real Linux subreaper lifecycle checks for SDDM child commands."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SOURCE = Path(__file__).parents[1] / "dotfiles/dot_local/lib/sddm-wallpaper-sync/processes.py"
spec = importlib.util.spec_from_file_location("sddm_processes_test", SOURCE)
assert spec and spec.loader
processes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processes)


def gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


class SubreaperTests(unittest.TestCase):
    def _wait_gone(self, pids: list[int]) -> None:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not all(gone(pid) for pid in pids):
            time.sleep(0.01)
        self.assertTrue(all(gone(pid) for pid in pids), f"surviving PIDs: {[pid for pid in pids if not gone(pid)]}")

    def test_timeout_reaps_parent_child_and_grandchild_and_restores_flag(self) -> None:
        pidfile = Path(tempfile.mktemp())
        before = processes._subreaper_flag()
        program = ("import pathlib,subprocess,sys,time\n"
                   "grand=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                   f"pathlib.Path({str(pidfile)!r}).write_text(str(grand.pid))\n"
                   "time.sleep(30)\n")
        started = time.monotonic()
        spawned: list[subprocess.Popen[bytes]] = []
        original_popen = subprocess.Popen
        def track_popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            spawned.append(child)
            return child
        with self.assertRaisesRegex(Exception, "timed out"), mock.patch.object(subprocess, "Popen", side_effect=track_popen):
            # Keep the process hierarchy depth: bounded_run owns the parent,
            # this program is its child, and grandchild is spawned by that child.
            import importlib.util
            writer_path = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
            writer_spec = importlib.util.spec_from_file_location("sddm_writer_process_test", writer_path)
            writer = importlib.util.module_from_spec(writer_spec); writer_spec.loader.exec_module(writer)
            writer._bounded_run([sys.executable, "-c", program], timeout=0.25, max_output=64)
        pids = [child.pid for child in spawned] + [int(pidfile.read_text())]
        self._wait_gone(pids)
        self.assertTrue(all(child.stdout is None or child.stdout.closed for child in spawned))
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(processes._subreaper_flag(), before)
        pidfile.unlink(missing_ok=True)

    def test_scope_preserves_preexisting_child_and_restores_subreaper_flag(self) -> None:
        baseline = subprocess.Popen(["sleep", "30"])
        before = processes._subreaper_flag()
        try:
            with processes.subreaper_scope(cleanup_seconds=0.25):
                pass
            self.assertIsNone(baseline.poll())
            self.assertEqual(processes._subreaper_flag(), before)
        finally:
            baseline.terminate(); baseline.wait(timeout=2)

    def test_stdout_overflow_kills_descendant_and_closes_pipe(self) -> None:
        import importlib.util
        writer_path = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
        writer_spec = importlib.util.spec_from_file_location("sddm_writer_overflow_test", writer_path)
        writer = importlib.util.module_from_spec(writer_spec); writer_spec.loader.exec_module(writer)
        pidfile = Path(tempfile.mktemp())
        program = ("import os,pathlib,subprocess,sys,time\n"
                   "grand=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                   f"pathlib.Path({str(pidfile)!r}).write_text(str(grand.pid))\n"
                   "os.write(1,b'x'*4096)\ntime.sleep(30)\n")
        spawned: list[subprocess.Popen[bytes]] = []
        original_popen = subprocess.Popen
        def track_popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            spawned.append(child)
            return child
        with self.assertRaisesRegex(Exception, "output exceeded"), mock.patch.object(subprocess, "Popen", side_effect=track_popen):
            writer._bounded_run([sys.executable, "-c", program], timeout=3, max_output=32)
        self._wait_gone([child.pid for child in spawned] + [int(pidfile.read_text())])
        self.assertTrue(all(child.stdout is None or child.stdout.closed for child in spawned))
        pidfile.unlink(missing_ok=True)

    def test_nonzero_exit_reaps_new_background_descendant(self) -> None:
        import importlib.util
        writer_path = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
        writer_spec = importlib.util.spec_from_file_location("sddm_writer_nonzero_test", writer_path)
        writer = importlib.util.module_from_spec(writer_spec); writer_spec.loader.exec_module(writer)
        pidfile = Path(tempfile.mktemp())
        program = ("import pathlib,subprocess,sys\n"
                   "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                   f"pathlib.Path({str(pidfile)!r}).write_text(str(child.pid))\n"
                   "raise SystemExit(7)\n")
        status, output = writer._bounded_run([sys.executable, "-c", program], timeout=3, max_output=32)
        self.assertEqual((status, output), (7, b""))
        self._wait_gone([int(pidfile.read_text())])
        pidfile.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
