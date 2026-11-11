"""Hermetic tests for the SDDM wallpaper sync safety contracts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
spec = importlib.util.spec_from_file_location("sddm_wallpaper_sync", SCRIPT)
assert spec and spec.loader
syncmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syncmod)


def png(width: int = 2, height: int = 2) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    raw = b"".join(b"\0" + b"\xff\x00\x00\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PolicyTests(unittest.TestCase):
    def test_disabled_policy_returns_without_external_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.json"
            path.write_text(json.dumps({"schema_version": 1, "enabled": False, "profile": "~/p",
                                        "state": "~/s", "landscape_pool": "~/pool"}))
            self.assertTrue(syncmod.sync(path).startswith("disabled:"))

    def test_policy_rejects_unknown_fields_and_boolean_schema_integer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.json"
            base = {"schema_version": 1, "enabled": True, "profile": "~/p", "state": "~/s", "landscape_pool": "~/pool"}
            for patch in ({"extra": 1}, {"schema_version": True}):
                path.write_text(json.dumps(base | patch))
                with self.subTest(patch=patch), self.assertRaises(syncmod.SyncError):
                    syncmod._load_policy(path)

    def test_duplicate_json_keys_rejected(self) -> None:
        with self.assertRaises(syncmod.SyncError):
            syncmod._unique_object([("a", 1), ("a", 2)])


class SourceTests(unittest.TestCase):
    def test_only_direct_child_with_exact_committed_raw_sha_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pool = Path(temp) / "pool"
            pool.mkdir()
            image = png()
            source = pool / "wall.png"
            source.write_bytes(image)
            cid = "sha256:" + hashlib.sha256(image).hexdigest()
            data, _ = syncmod._source_snapshot(source, pool, os.getuid(), cid)
            self.assertEqual(data, image)
            with self.assertRaises(syncmod.SyncError):
                syncmod._source_snapshot(source, pool, os.getuid(), "sha256:" + "0" * 64)
            nested = pool / "nested"
            nested.mkdir()
            other = nested / "wall.png"
            other.write_bytes(image)
            with self.assertRaises(syncmod.SyncError):
                syncmod._source_snapshot(other, pool, os.getuid(), cid)

    def test_symlink_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pool = Path(temp) / "pool"
            pool.mkdir()
            image = png()
            target = Path(temp) / "outside.png"
            target.write_bytes(image)
            link = pool / "link.png"
            link.symlink_to(target)
            cid = "sha256:" + hashlib.sha256(image).hexdigest()
            with self.assertRaises(syncmod.SyncError):
                syncmod._source_snapshot(link, pool, os.getuid(), cid)

    def test_real_png_normalizes_and_corrupt_file_is_rejected(self) -> None:
        normalized = syncmod._normalize(png())
        self.assertTrue(normalized.startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaises(syncmod.SyncError):
            syncmod._normalize(b"\x89PNG\r\n\x1a\nnot an image")


class PublishTests(unittest.TestCase):
    def test_success_atomically_publishes_single_fixed_mode_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            directory_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertEqual(syncmod._write_atomic(directory_fd, b"normalized-png", os.getuid(), os.getgid()), "published")
            finally:
                os.close(directory_fd)
            current = destination / "current.png"
            self.assertEqual(current.read_bytes(), b"normalized-png")
            self.assertEqual(current.stat().st_mode & 0o777, 0o640)
            self.assertEqual([item.name for item in destination.iterdir()], ["current.png"])

    def test_precommit_failure_preserves_last_good_and_cleans_only_own_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "cache"
            destination.mkdir()
            (destination / "current.png").write_bytes(b"last-good")
            def fail() -> None:
                raise syncmod.SyncError("injected precommit failure")
            directory_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaises(syncmod.SyncError):
                    syncmod._write_atomic(directory_fd, b"new", os.getuid(), os.getgid(), fail)
            finally:
                os.close(directory_fd)
            self.assertEqual((destination / "current.png").read_bytes(), b"last-good")
            self.assertEqual([p.name for p in destination.iterdir()], ["current.png"])

    def test_canonical_owner_lock_descriptor_is_validated_and_reacquirable(self) -> None:
        import fcntl
        wrapper_path = SCRIPT.with_name("executable_ezwallpaper-sddm-rotate.py")
        wrapper_spec = importlib.util.spec_from_file_location("sddm_rotate_wrapper", wrapper_path)
        assert wrapper_spec and wrapper_spec.loader
        wrapper = importlib.util.module_from_spec(wrapper_spec)
        wrapper_spec.loader.exec_module(wrapper)
        with tempfile.TemporaryDirectory() as temp:
            os.environ["XDG_RUNTIME_DIR"] = temp
            lock_path = Path(temp) / "ezwallpaper-rotate.lock"
            lock_path.touch(mode=0o600)
            first = os.open(lock_path, os.O_RDWR)
            second = os.open(lock_path, os.O_RDWR)
            try:
                fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(wrapper._owner_fd(), first)
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(first)
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.close(second)
            self.assertFalse(any(p.name == "\\\\0sddm-wallpaper-sync-" + str(os.getuid()) for p in Path(temp).iterdir()))

    def test_state_schema_rejects_unknown_output_names_and_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            good = {"schema_version": 1, "profile": "/profile", "outputs": {
                "DP-1": {"schema_version": 1, "last_epoch": 1, "last_content_id": "sha256:" + "a" * 64}}}
            for state in (good | {"outputs": good["outputs"] | {"UNKNOWN": {}}},
                          good | {"outputs": {"DP-1": good["outputs"]["DP-1"] | {"future": True}}}):
                path.write_text(json.dumps(state))
                os.utime(path, None)
                with self.assertRaises(syncmod.SyncError):
                    syncmod._state_identity(path, "/profile", os.getuid())


if __name__ == "__main__":
    unittest.main()
