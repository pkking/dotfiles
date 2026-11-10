"""Fault regressions for bounded decoding and fixed-name publication."""
from __future__ import annotations

import base64
import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
spec = importlib.util.spec_from_file_location("sddm_wallpaper_sync_faults", SCRIPT)
assert spec and spec.loader
syncmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syncmod)

JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAACAAMDAREAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAVAQEBAAAAAAAAAAAAAAAAAAAHCf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/ADoDFU3/2Q==")


class DecoderFaultTests(unittest.TestCase):
    def test_real_jpeg_fixture_normalizes(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "fixture.jpg"
            subprocess.run(["magick", "-size", "3x2", "xc:red", "-quality", "85", str(fixture)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            output = syncmod._normalize(fixture.read_bytes())
        self.assertTrue(output.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_fake_decoder_output_is_generation_bounded_and_missing_tool_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fakebin = Path(temp) / "bin"
            fakebin.mkdir()
            tool = fakebin / "magick"
            tool.write_text("#!/bin/sh\npython3 -c 'import sys; sys.stdout.buffer.write(b\"x\"*1000000)'\n")
            tool.chmod(0o700)
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = str(fakebin) + os.pathsep + old_path
            try:
                with self.assertRaises(syncmod.SyncError):
                    syncmod._bounded_run(["magick"], timeout=2, max_output=1024)
            finally:
                os.environ["PATH"] = old_path
            os.environ["PATH"] = str(Path(temp) / "missing")
            try:
                with self.assertRaises(syncmod.SyncError):
                    syncmod._normalize(JPEG)
            finally:
                os.environ["PATH"] = old_path

    def test_bad_multiformat_and_apng_signatures_rejected(self) -> None:
        for payload in (b"GIF89a" + b"x" * 64, b"II*\x00" + b"x" * 64,
                        b"\x89PNG\r\n\x1a\n" + b"acTL" + b"x" * 32):
            with self.subTest(prefix=payload[:8]), self.assertRaises(syncmod.SyncError):
                syncmod._normalize(payload)


class StateFaultTests(unittest.TestCase):
    def test_wrong_profile_schema_bool_epoch_stale_and_future_state_rejected(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            ack = {"schema_version": 1, "last_epoch": 7, "last_content_id": "sha256:" + "a" * 64}
            base = {"schema_version": 1, "profile": "/profile", "outputs": {"DP-1": ack}}
            cases = [base | {"profile": "/other"}, base | {"schema_version": True},
                     {"schema_version": 1, "profile": "/profile", "outputs": {"DP-1": ack | {"last_epoch": True}}}]
            for state in cases:
                path.write_text(json.dumps(state))
                os.utime(path, None)
                with self.subTest(state=state), self.assertRaises(syncmod.SyncError):
                    syncmod._state_identity(path, "/profile", os.getuid())
            path.write_text(json.dumps(base))
            os.utime(path, (1, 1))
            with self.assertRaises(syncmod.SyncError):
                syncmod._state_identity(path, "/profile", os.getuid())
            os.utime(path, (time.time() + 60, time.time() + 60))
            with self.assertRaises(syncmod.SyncError):
                syncmod._state_identity(path, "/profile", os.getuid())


class OwnerLockFaultTests(unittest.TestCase):
    def test_owner_lock_accepts_inherited_0644_and_requires_held_flock(self) -> None:
        import fcntl
        with tempfile.TemporaryDirectory() as temp:
            old_runtime = os.environ.get("XDG_RUNTIME_DIR")
            os.environ["XDG_RUNTIME_DIR"] = temp
            lock = Path(temp) / "ezwallpaper-rotate.lock"
            lock.touch(mode=0o644)
            os.chmod(lock, 0o644)
            fd = os.open(lock, os.O_RDWR)
            try:
                with self.assertRaises(syncmod.SyncError):
                    syncmod._require_owner_lock()
                fcntl.flock(fd, fcntl.LOCK_EX)
                syncmod._require_owner_lock()
            finally:
                os.close(fd)
                if old_runtime is None:
                    os.environ.pop("XDG_RUNTIME_DIR", None)
                else:
                    os.environ["XDG_RUNTIME_DIR"] = old_runtime


class PendingFaultTests(unittest.TestCase):
    def test_safe_fixed_pending_is_recovered_but_unsafe_pending_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            pending = directory / syncmod.PENDING_NAME
            pending.write_bytes(b"stale")
            os.chmod(pending, 0o640)
            os.chown(pending, os.getuid(), os.getgid())
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                syncmod._remove_pending(fd, os.getuid(), os.getgid())
                self.assertFalse(pending.exists())
                pending.write_bytes(b"unsafe")
                os.chmod(pending, 0o600)
                with self.assertRaises(syncmod.SyncError):
                    syncmod._write_atomic(fd, b"new", os.getuid(), os.getgid())
            finally:
                os.close(fd)
            self.assertEqual(pending.read_bytes(), b"unsafe")

    def test_file_fsync_failure_preserves_old_and_directory_fsync_reports_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            current = directory / "current.png"
            current.write_bytes(b"old exact")
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            original_fsync = syncmod.os.fsync
            try:
                syncmod.os.fsync = lambda _fd: (_ for _ in ()).throw(OSError("injected file fsync"))
                with self.assertRaises(syncmod.SyncError):
                    syncmod._write_atomic(fd, b"new", os.getuid(), os.getgid())
                self.assertEqual(current.read_bytes(), b"old exact")
                self.assertEqual({p.name for p in directory.iterdir()}, {"current.png"})

                calls = 0
                def fail_directory_fsync(target: int) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError("injected directory fsync")
                    original_fsync(target)
                syncmod.os.fsync = fail_directory_fsync
                with self.assertRaisesRegex(syncmod.SyncError, "COMMITTED"):
                    syncmod._write_atomic(fd, b"new committed", os.getuid(), os.getgid())
                self.assertEqual(current.read_bytes(), b"new committed")
                self.assertEqual({p.name for p in directory.iterdir()}, {"current.png"})
            finally:
                syncmod.os.fsync = original_fsync
                os.close(fd)

    def test_rename_fault_preserves_exact_last_good_and_cleans_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            current = directory / "current.png"
            current.write_bytes(b"exact old image bytes")
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            original_replace = syncmod.os.replace
            try:
                syncmod.os.replace = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected rename"))
                with self.assertRaises(syncmod.SyncError):
                    syncmod._write_atomic(fd, b"new image", os.getuid(), os.getgid())
            finally:
                syncmod.os.replace = original_replace
                os.close(fd)
            self.assertEqual(current.read_bytes(), b"exact old image bytes")
            self.assertEqual({p.name for p in directory.iterdir()}, {"current.png"})


if __name__ == "__main__":
    unittest.main()
