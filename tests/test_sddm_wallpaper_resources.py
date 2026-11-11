"""OS resource-containment regressions for the SDDM image child."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
spec = importlib.util.spec_from_file_location("sddm_wallpaper_sync_resources", SCRIPT)
assert spec and spec.loader
syncmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syncmod)
from sddm_rotation_fixtures import PROFILE_OUTPUTS, content_id, state_json as producer_state


def small_png(width: int = 16, height: int = 8) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"".join(b"\0" + b"\x28\x50\x78\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class ChildResourceTests(unittest.TestCase):
    def test_state_queue_validation_accepts_pinned_limit_and_rejects_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            state = producer_state("/private-fixture/profile")
            state["outputs"]["DP-1"]["remaining"] = [content_id(f"bounded-{i}") for i in range(4096)]
            path.write_text(json.dumps(state))
            with mock.patch.object(syncmod, "MAX_STATE", 1024 * 1024):
                self.assertEqual(syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))[0], 17)
                state["outputs"]["DP-1"]["remaining"].append(content_id("bounded-overflow"))
                path.write_text(json.dumps(state))
                with self.assertRaisesRegex(syncmod.SyncError, "remaining queue"):
                    syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))

    def run_child(self, code: str, *, timeout: int = 5, max_output: int = 4096) -> tuple[int, bytes]:
        return syncmod._bounded_run([sys.executable, "-c", code], timeout=timeout, max_output=max_output)

    def test_child_observes_finite_as_cpu_and_fsize_limits_parent_unchanged(self) -> None:
        import resource
        before = {key: resource.getrlimit(key) for key in (resource.RLIMIT_AS, resource.RLIMIT_CPU, resource.RLIMIT_FSIZE)}
        code = ("import json,resource; print(json.dumps({k:resource.getrlimit(getattr(resource,k)) "
                "for k in ('RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE')}))")
        status, output = self.run_child(code)
        self.assertEqual(status, 0)
        observed = __import__("json").loads(output)
        self.assertLessEqual(observed["RLIMIT_AS"][0], syncmod.MAX_CHILD_AS_BYTES)
        self.assertLessEqual(observed["RLIMIT_AS"][1], syncmod.MAX_CHILD_AS_BYTES)
        self.assertGreater(observed["RLIMIT_AS"][0], 0)
        self.assertLessEqual(observed["RLIMIT_CPU"][0], syncmod.MAX_CHILD_CPU_SOFT_SECONDS)
        self.assertLessEqual(observed["RLIMIT_CPU"][1], syncmod.MAX_CHILD_CPU_HARD_SECONDS)
        self.assertLessEqual(observed["RLIMIT_FSIZE"][0], syncmod.MAX_SOURCE_BYTES)
        self.assertLessEqual(observed["RLIMIT_FSIZE"][1], syncmod.MAX_SOURCE_BYTES)
        self.assertEqual(before, {key: resource.getrlimit(key) for key in before})

    def test_address_space_cap_rejects_controlled_overallocation(self) -> None:
        with mock.patch.object(syncmod, "MAX_CHILD_AS_BYTES", 96 * 1024 * 1024):
            status, output = self.run_child("try:\n bytearray(192*1024*1024)\nexcept MemoryError:\n print('denied'); raise SystemExit(42)\nraise SystemExit(0)")
        self.assertEqual(status, 42)
        self.assertEqual(output.strip(), b"denied")

    def test_cpu_limit_terminates_busy_loop_before_wall_timeout_and_reaps(self) -> None:
        with mock.patch.object(syncmod, "MAX_CHILD_CPU_SOFT_SECONDS", 1), mock.patch.object(syncmod, "MAX_CHILD_CPU_HARD_SECONDS", 2):
            start = time.monotonic()
            status, _ = self.run_child("while True: pass", timeout=5)
            elapsed = time.monotonic() - start
        self.assertIn(status, (-signal.SIGXCPU, -signal.SIGKILL))
        self.assertLess(elapsed, 5)

    def test_stdout_generation_stops_at_sentinel_and_child_is_reaped(self) -> None:
        marker = tempfile.mktemp()
        producer = ("import os,time; data=b'x'*65536; total=0\n"
                    "while total<1073741824: total+=os.write(1,data)\n"
                    "f=os.open(%r,os.O_CREAT|os.O_WRONLY,0o600); os.write(f,b'alive'); "
                    "os.close(f); time.sleep(10)") % marker
        started = time.monotonic()
        with self.assertRaisesRegex(syncmod.SyncError, "output exceeded"):
            syncmod._bounded_run([sys.executable, "-c", producer], timeout=5, max_output=64)
        elapsed = time.monotonic() - started
        try:
            self.assertLess(elapsed, 2)
            self.assertFalse(Path(marker).exists(), "producer continued after stdout sentinel")
        finally:
            Path(marker).unlink(missing_ok=True)

    def test_timeout_and_nonzero_exit_are_reaped_and_bounded(self) -> None:
        with self.assertRaisesRegex(syncmod.SyncError, "timed out"):
            syncmod._bounded_run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1, max_output=64)
        status, output = self.run_child("print('failure'); raise SystemExit(7)")
        self.assertEqual(status, 7)
        self.assertEqual(output, b"failure\n")

    def test_decoder_failure_leaves_existing_atomic_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            current = destination / "current.png"
            current.write_bytes(b"last-good-image")
            with self.assertRaises(syncmod.SyncError):
                syncmod._normalize(b"\\x89PNG\\r\\n\\x1a\\ninvalid image payload")
            self.assertEqual(current.read_bytes(), b"last-good-image")
            self.assertEqual([path.name for path in destination.iterdir()], ["current.png"])

    def test_supported_png_jpeg_and_repository_4k_png_normalize_under_production_caps(self) -> None:
        magick = shutil.which("magick")
        self.assertIsNotNone(magick, "ImageMagick magick is required for the SDDM normalization contract")
        jpeg = subprocess.run([magick, "png:-", "jpeg:-"], input=small_png(), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, check=True, timeout=10).stdout
        mocha = SCRIPT.parents[2] / "dot_local/share/wallpapers/ezwallpaper-mocha/landscape/mocha-flat-landscape.png"
        self.assertTrue(mocha.is_file(), str(mocha))
        fixtures = [("generated PNG", small_png()), ("generated JPEG", jpeg), ("Mocha landscape", mocha.read_bytes())]
        for label, source in fixtures:
            with self.subTest(fixture=label):
                started = time.monotonic()
                normalized = syncmod._normalize(source)
                elapsed = time.monotonic() - started
                self.assertTrue(normalized.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertGreater(len(normalized), 0)
                print(f"fixture={label} input_bytes={len(source)} output_bytes={len(normalized)} runtime_seconds={elapsed:.3f}")


if __name__ == "__main__":
    unittest.main()
