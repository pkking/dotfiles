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
from unittest import mock
import zlib

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
spec = importlib.util.spec_from_file_location("sddm_wallpaper_sync", SCRIPT)
assert spec and spec.loader
syncmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syncmod)
from sddm_rotation_fixtures import PROFILE_OUTPUTS, content_id, state_json as producer_state


def png(width: int = 2, height: int = 2) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    raw = b"".join(b"\0" + b"\xff\x00\x00\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PolicyTests(unittest.TestCase):
    def test_pinned_producer_dual_output_receipt_accepts_metadata_but_returns_only_dp1(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            state = producer_state("/private-fixture/profile", portrait_first=True)
            path.write_text(json.dumps(state))
            epoch, image_id, _inode = syncmod._state_identity(
                path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS)
            )
            self.assertEqual(epoch, 17)
            self.assertEqual(image_id, state["outputs"]["DP-1"]["last_content_id"])
            self.assertNotEqual(image_id, state["outputs"]["HDMI-A-1"]["last_content_id"])

    def test_secondary_options_may_be_null_or_output_may_be_sparse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            base = producer_state("/private-fixture/profile")
            expected = base["outputs"]["DP-1"]["last_content_id"]
            option_cases = ((None, None), (None, content_id("secondary-id")),
                            (17, None), (17, content_id("secondary-id")))
            for epoch, image_id in option_cases:
                state = json.loads(json.dumps(base))
                state["outputs"]["HDMI-A-1"]["last_epoch"] = epoch
                state["outputs"]["HDMI-A-1"]["last_content_id"] = image_id
                path.write_text(json.dumps(state))
                with self.subTest(epoch=epoch, image_id=image_id):
                    self.assertEqual(syncmod._state_identity(
                        path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS)
                    )[1], expected)
            sparse = json.loads(json.dumps(base))
            del sparse["outputs"]["HDMI-A-1"]
            path.write_text(json.dumps(sparse))
            self.assertEqual(syncmod._state_identity(
                path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS)
            )[1], expected)

    def test_primary_requires_ack_and_present_secondary_options_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            base = producer_state("/private-fixture/profile")
            invalid = []
            for field in ("last_epoch", "last_content_id"):
                invalid.append(("primary-null-" + field,
                                base | {"outputs": base["outputs"] | {
                                    "DP-1": base["outputs"]["DP-1"] | {field: None}}}))
            bad_epochs = (True, False, -1, 2**64, "17")
            for epoch in bad_epochs:
                invalid.append(("secondary-epoch-" + repr(epoch), base | {"outputs": base["outputs"] | {
                    "HDMI-A-1": base["outputs"]["HDMI-A-1"] | {"last_epoch": epoch}}}))
            for image_id in (True, "bad", "SHA256:" + "a" * 64):
                invalid.append(("secondary-id-" + repr(image_id), base | {"outputs": base["outputs"] | {
                    "HDMI-A-1": base["outputs"]["HDMI-A-1"] | {"last_content_id": image_id}}}))
            secondary = base["outputs"]["HDMI-A-1"]
            invalid.extend((
                ("secondary-missing-option-key", base | {"outputs": base["outputs"] | {
                    "HDMI-A-1": {key: value for key, value in secondary.items() if key != "last_epoch"}}}),
                ("secondary-unknown-key", base | {"outputs": base["outputs"] | {
                    "HDMI-A-1": secondary | {"future": 1}}}),
                ("secondary-bool-schema", base | {"outputs": base["outputs"] | {
                    "HDMI-A-1": secondary | {"schema_version": True}}}),
            ))
            for label, state in invalid:
                path.write_text(json.dumps(state))
                with self.subTest(case=label), self.assertRaises(syncmod.SyncError):
                    syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))

    def test_dual_output_receipt_rejects_undeclared_output_and_malformed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            good = producer_state("/private-fixture/profile")
            invalid = []
            invalid.append(good | {"outputs": good["outputs"] | {"DP-2": good["outputs"]["DP-1"]}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"future": 1}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"remaining": ["bad"]}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"cycle": True}}})
            invalid.append(good | {"outputs": {"HDMI-A-1": good["outputs"]["HDMI-A-1"]}})
            invalid.append(good | {"schema_version": True})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"schema_version": True}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"last_content_id": "bad"}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"remaining": [content_id("dup"), content_id("dup")]}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"remaining": [content_id(str(i)) for i in range(4097)]}}})
            invalid.append(good | {"outputs": good["outputs"] | {"DP-1": good["outputs"]["DP-1"] | {"cycle": 2**64}}})
            for state in invalid:
                path.write_text(json.dumps(state))
                with self.subTest(state=state), self.assertRaises(syncmod.SyncError):
                    syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))

    def test_profile_output_names_are_strict_and_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            profile = {"schema_version": 1, "owner": "ezwallpaper", "outputs": [
                {"name": "DP-1", "dir": "/private-fixture/landscape"},
                {"name": "HDMI-A-1", "dir": "/private-fixture/portrait"},
            ]}
            path.write_text(json.dumps(profile))
            self.assertEqual(syncmod._profile_output_names(path, os.getuid()), frozenset(PROFILE_OUTPUTS))
            for invalid in (profile | {"future": False},
                            profile | {"outputs": [{**profile["outputs"][0], "name": "DP-2"}, profile["outputs"][1]]},
                            profile | {"outputs": [profile["outputs"][0], profile["outputs"][0]]},
                            profile | {"outputs": [{**profile["outputs"][0], "recursive": 1}, profile["outputs"][1]]}):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(syncmod.SyncError):
                    syncmod._profile_output_names(path, os.getuid())
            literal_backslash_x00 = profile | {"outputs": [
                {**profile["outputs"][0], "dir": "/private-fixture/literal\\x00"}, profile["outputs"][1]
            ]}
            path.write_text(json.dumps(literal_backslash_x00))
            self.assertEqual(syncmod._profile_output_names(path, os.getuid()), frozenset(PROFILE_OUTPUTS))
            actual_nul_profiles = (
                profile | {"outputs": [profile["outputs"][0], {
                    **profile["outputs"][1], "dir": "/private-fixture/" + chr(0) + "portrait"
                }]},
                profile | {"outputs": [profile["outputs"][0], {
                    **profile["outputs"][1], "name": "HDMI" + chr(0) + "-A-1"
                }]},
            )
            for nul_profile in actual_nul_profiles:
                encoded = json.dumps(nul_profile)
                self.assertIn("\\u0000", encoded)
                path.write_text(encoded)
                with self.subTest(profile=encoded), mock.patch.object(
                    syncmod, "_open_anchored", wraps=syncmod._open_anchored
                ) as opened, self.assertRaises(syncmod.SyncError):
                    syncmod._profile_output_names(path, os.getuid())
                opened.assert_called_once_with(path, os.getuid(), directory=False)

    def test_valid_empty_cycle_zero_queue_and_shared_cross_output_ids_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            state = producer_state("/private-fixture/profile")
            state["outputs"]["DP-1"]["remaining"] = []
            state["outputs"]["DP-1"]["cycle"] = 0
            state["outputs"]["HDMI-A-1"]["last_content_id"] = state["outputs"]["DP-1"]["last_content_id"]
            path.write_text(json.dumps(state))
            self.assertEqual(syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))[1],
                             state["outputs"]["DP-1"]["last_content_id"])

    def test_duplicate_state_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text('{"schema_version":1,"profile":"/private-fixture/profile",'
                            '"outputs":{"DP-1":{},"DP-1":{}}}')
            with self.assertRaises(syncmod.SyncError):
                syncmod._state_identity(path, "/private-fixture/profile", os.getuid(), set(PROFILE_OUTPUTS))
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
            good = producer_state("/profile")
            for state in (good | {"outputs": good["outputs"] | {"DP-2": good["outputs"]["DP-1"]}},
                          good | {"outputs": {"DP-1": good["outputs"]["DP-1"] | {"future": True}}}):
                path.write_text(json.dumps(state))
                os.utime(path, None)
                with self.assertRaises(syncmod.SyncError):
                    syncmod._state_identity(path, "/profile", os.getuid(), set(PROFILE_OUTPUTS))


if __name__ == "__main__":
    unittest.main()
