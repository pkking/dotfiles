"""OS resource-containment regressions for the SDDM image child."""
from __future__ import annotations

import importlib.util
import json
import os
import resource
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

    def test_normalizer_keeps_probe_and_conversion_memory_budgets_separate(self) -> None:
        png = small_png()
        calls = []

        def bounded(argv, **kwargs):
            calls.append((list(argv), kwargs.copy()))
            return (0, b"16 8 1\n") if len(calls) == 1 else (0, png)

        with mock.patch.object(syncmod, "_bounded_run", side_effect=bounded):
            self.assertEqual(syncmod._normalize(png), png)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][calls[0][0].index("memory") + 1], "256MiB")
        self.assertEqual(calls[1][0][calls[1][0].index("memory") + 1], "512MiB")
        self.assertEqual(calls[1][0][calls[1][0].index("map") + 1], "512MiB")
        self.assertEqual(calls[1][0][calls[1][0].index("disk") + 1], "512MiB")
        self.assertEqual(calls[1][1]["max_output"], syncmod.MAX_SOURCE_BYTES)
        self.assertTrue(calls[1][1]["limit_fsize"])
        self.assertEqual(calls[1][1]["timeout"], syncmod.MAX_SECONDS + 2)
        self.assertEqual(syncmod.MAX_CHILD_AS_BYTES, 1024 * 1024 * 1024)
        self.assertEqual(syncmod.MAX_CHILD_CPU_SOFT_SECONDS, 8)
        self.assertEqual(syncmod.MAX_CHILD_CPU_HARD_SECONDS, 9)

    def test_native_5k_rgb_jpeg_normalizes_full_resolution_under_production_caps(self) -> None:
        magick = shutil.which("magick")
        self.assertIsNotNone(magick, "ImageMagick magick is required for the native 5K regression")
        with tempfile.TemporaryDirectory(prefix="sddm-normalize-5k-") as temp:
            os.chmod(temp, 0o700)
            original_bounded_run = syncmod._bounded_run

            def private_scratch(argv, **kwargs):
                command = list(argv)
                if "registry:temporary-path=/tmp" in command:
                    command[command.index("registry:temporary-path=/tmp")] = f"registry:temporary-path={temp}"
                return original_bounded_run(command, **kwargs)

            with mock.patch.object(syncmod, "_bounded_run", side_effect=private_scratch):
                # Create a copyright-free RGB PPM in a small-memory, CPU- and file-size-
                # bounded helper, then encode it with the unchanged production child bounds.
                ppm = Path(temp) / "synthetic.ppm"
                make_ppm = """import pathlib,sys
w,h=5127,2884
with pathlib.Path(sys.argv[1]).open('wb') as f:
 f.write(f'P6\\n{w} {h}\\n255\\n'.encode())
 for y in range(h):
  block=bytes(c for x in range(256) for c in ((x*37+y*13)&255,(x*17+y*29)&255,(x*7+y*53)&255))
  row=(block*((w*3+len(block)-1)//len(block)))[:w*3]
  f.write(row)
"""

                def fixture_limits():
                    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
                    resource.setrlimit(resource.RLIMIT_CPU, (4, 5))
                    resource.setrlimit(resource.RLIMIT_FSIZE, (48 * 1024 * 1024, 48 * 1024 * 1024))

                subprocess.run([sys.executable, "-c", make_ppm, str(ppm)], check=True,
                               timeout=10, preexec_fn=fixture_limits)
                source_command = [magick, "-limit", "time", "20", "-limit", "memory", "256MiB",
                                  "-limit", "map", "512MiB", "-limit", "disk", "512MiB",
                                  "-define", f"registry:temporary-path={temp}", f"ppm:{ppm}",
                                  "-colorspace", "sRGB", "-type", "TrueColor", "-quality", "90", "jpeg:-"]
                source_status, jpeg = syncmod._bounded_run(source_command, timeout=syncmod.MAX_SECONDS + 2,
                                                           max_output=syncmod.MAX_SOURCE_BYTES,
                                                           limit_fsize=True)
                self.assertEqual(source_status, 0)
                self.assertTrue(jpeg.startswith(b"\xff\xd8\xff"))
                self.assertLessEqual(len(jpeg), syncmod.MAX_SOURCE_BYTES)
                ppm.unlink()
                normalized = syncmod._normalize(jpeg)
                status, metadata = syncmod._bounded_run(
                    [magick, "identify", "-limit", "time", "20", "-limit", "memory", "256MiB",
                     "-limit", "map", "512MiB", "-limit", "disk", "512MiB", "-format",
                     "%w %h %n %m %[channels]", "PNG:-"], input_data=normalized,
                    timeout=syncmod.MAX_SECONDS, max_output=128)
                self.assertEqual(status, 0)
                self.assertEqual(metadata.decode().split(), ["5127", "2884", "1", "PNG", "srgb", "3.0"])
                self.assertLessEqual(len(normalized), syncmod.MAX_SOURCE_BYTES)
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_native_6k_rgb_jpeg_normalizes_at_512_and_reproduces_old_384_failure(self) -> None:
        magick = shutil.which("magick")
        self.assertIsNotNone(magick, "ImageMagick magick is required for the native 6K regression")
        with tempfile.TemporaryDirectory(prefix="sddm-normalize-6k-") as temp:
            os.chmod(temp, 0o700)
            original_bounded_run = syncmod._bounded_run

            def private_scratch(argv, **kwargs):
                command = list(argv)
                if "registry:temporary-path=/tmp" in command:
                    command[command.index("registry:temporary-path=/tmp")] = f"registry:temporary-path={temp}"
                return original_bounded_run(command, **kwargs)

            with mock.patch.object(syncmod, "_bounded_run", side_effect=private_scratch):
                ppm = Path(temp) / "synthetic.ppm"
                make_ppm = """import pathlib,sys
w,h=6048,3402
with pathlib.Path(sys.argv[1]).open('wb') as f:
 f.write(f'P6\\n{w} {h}\\n255\\n'.encode())
 for y in range(h):
  block=bytes(c for x in range(256) for c in ((x*37+y*13)&255,(x*17+y*29)&255,(x*7+y*53)&255))
  row=(block*((w*3+len(block)-1)//len(block)))[:w*3]
  f.write(row)
"""

                def fixture_limits():
                    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
                    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
                    resource.setrlimit(resource.RLIMIT_FSIZE, (72 * 1024 * 1024, 72 * 1024 * 1024))

                subprocess.run([sys.executable, "-B", "-c", make_ppm, str(ppm)], check=True,
                               timeout=20, preexec_fn=fixture_limits)
                source_command = [magick, "-limit", "time", "20", "-limit", "memory", "256MiB",
                                  "-limit", "map", "512MiB", "-limit", "disk", "512MiB",
                                  "-define", f"registry:temporary-path={temp}", f"ppm:{ppm}",
                                  "-colorspace", "sRGB", "-type", "TrueColor", "-quality", "85", "jpeg:-"]
                source_status, jpeg = original_bounded_run(source_command, timeout=syncmod.MAX_SECONDS + 2,
                                                           max_output=syncmod.MAX_SOURCE_BYTES, limit_fsize=True)
                self.assertEqual(source_status, 0)
                self.assertTrue(jpeg.startswith(b"\xff\xd8\xff"))
                self.assertLessEqual(len(jpeg), syncmod.MAX_SOURCE_BYTES)
                ppm.unlink()

                normalized = syncmod._normalize(jpeg)
                status, metadata = original_bounded_run(
                    [magick, "identify", "-limit", "time", "20", "-limit", "memory", "256MiB",
                     "-limit", "map", "512MiB", "-limit", "disk", "512MiB", "-format",
                     "%w %h %n %m %[channels]", "PNG:-"], input_data=normalized,
                    timeout=syncmod.MAX_SECONDS, max_output=128)
                self.assertEqual(status, 0)
                self.assertEqual(metadata.decode().split(), ["6048", "3402", "1", "PNG", "srgb", "3.0"])
                self.assertLessEqual(len(normalized), syncmod.MAX_SOURCE_BYTES)

                def old_384_adapter(argv, **kwargs):
                    command = list(argv)
                    if "-limit" in command and "memory" in command:
                        index = command.index("memory") + 1
                        if command[index] == "512MiB":
                            command[index] = "384MiB"
                    return private_scratch(command, **kwargs)

                try:
                    with mock.patch.object(syncmod, "_bounded_run", side_effect=old_384_adapter):
                        legacy = syncmod._normalize(jpeg)
                    legacy_status = 0
                    self.assertTrue(legacy.startswith(b"\x89PNG\r\n\x1a\n"))
                except syncmod.SyncError:
                    legacy_status = 1
                version = subprocess.run([magick, "-version"], text=True, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, check=True, timeout=5).stdout
                if "HDRI" in version:
                    self.assertEqual(legacy_status, 1, "HDRI old-384 adapter must reproduce the bounded failure")
                print(f"fixture=synthetic 6048x3402 RGB JPEG input_bytes={len(jpeg)} new512=green old384_status={legacy_status}")
                self.assertEqual(list(Path(temp).iterdir()), [])

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
