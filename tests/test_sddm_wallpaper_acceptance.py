"""Acceptance fault matrix for SDDM wallpaper publication boundaries.

All filesystem and process fixtures are private temporary objects.  The
production cache's root-owned ancestors are metadata-injected where needed;
this suite never accesses /var/cache for writing, invokes sudo, or contacts a
real desktop/service/tool.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_sddm-wallpaper-sync.py"
spec = importlib.util.spec_from_file_location("sddm_wallpaper_sync_acceptance", SCRIPT)
assert spec and spec.loader
syncmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syncmod)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
    "nXcAAAAASUVORK5CYII="
)


def state_json(profile: str = "/tmp/profile", epoch: int = 1) -> dict:
    return {"schema_version": 1, "profile": profile, "outputs": {"DP-1": {
        "schema_version": 1, "last_epoch": epoch,
        "last_content_id": "sha256:" + hashlib.sha256(PNG).hexdigest(),
    }}}


def fake_root_stat(mode: int = stat.S_IFDIR | 0o755, uid: int = 0, gid: int = 0):
    return SimpleNamespace(st_mode=mode, st_uid=uid, st_gid=gid)


class AtomicWriteAcceptanceTests(unittest.TestCase):
    def test_stream_write_enospc_preserves_exact_current_and_closes_fd(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            current = directory / "current.png"
            current.write_bytes(b"old bytes including exact sentinel\x00")
            dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            opened_fds: list[int] = []
            real_fdopen = os.fdopen

            class BrokenStream:
                def __init__(self, wrapped):
                    self.wrapped = wrapped
                    opened_fds.append(wrapped.fileno())
                def __enter__(self): return self
                def __exit__(self, *_args): self.wrapped.close()
                def write(self, _data): raise OSError(28, "injected ENOSPC during write")
                def flush(self): self.wrapped.flush()

            try:
                with mock.patch.object(syncmod.os, "fdopen", side_effect=lambda *a, **kw: BrokenStream(real_fdopen(*a, **kw))):
                    with self.assertRaisesRegex(syncmod.SyncError, "publication failed before commit"):
                        syncmod._write_atomic(dirfd, b"new candidate", os.getuid(), os.getgid())
                self.assertEqual(current.read_bytes(), b"old bytes including exact sentinel\x00")
                self.assertEqual({p.name for p in directory.iterdir()}, {"current.png"})
                with self.assertRaises(OSError): os.fstat(opened_fds[0])
            finally:
                os.close(dirfd)

    def test_abort_cleanup_accepts_fixed_pending_and_missing_cache_is_noop(self):
        for has_pending in (False, True):
            with self.subTest(has_pending=has_pending), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cache = root / "cache" / str(os.getuid())
                cache.mkdir(parents=True)
                os.chmod(cache, 0o2750)
                os.chown(cache, os.getuid(), os.getgid())
                current = cache / "current.png"
                current.write_bytes(b"good current")
                unknown = cache / "user-not-pending.txt"
                unknown.write_bytes(b"must remain")
                pending = cache / syncmod.PENDING_NAME
                if has_pending:
                    pending.write_bytes(b"fixed pending")
                    os.chmod(pending, 0o640)
                    os.chown(pending, os.getuid(), os.getgid())
                real_open_anchored = syncmod._open_anchored
                def anchor(path, uid, directory=False):
                    # cleanup's production parent contract is root-owned; use
                    # this private user-owned fixture while preserving nofollow
                    # descriptor traversal for every path component.
                    return real_open_anchored(path, os.getuid(), directory)
                with mock.patch.object(syncmod, "_require_owner_lock"), \
                     mock.patch.object(syncmod, "DESTINATION", cache), \
                     mock.patch.object(syncmod, "_open_anchored", side_effect=anchor), \
                     mock.patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=os.getgid())):
                    syncmod.cleanup_after_abort()
                self.assertEqual(current.read_bytes(), b"good current")
                self.assertEqual(unknown.read_bytes(), b"must remain")
                self.assertFalse(pending.exists())

    def test_abort_cleanup_is_noop_when_cache_parent_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-provisioned" / str(os.getuid())
            with mock.patch.object(syncmod, "_require_owner_lock"), mock.patch.object(syncmod, "DESTINATION", missing), \
                 mock.patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=os.getgid())):
                syncmod.cleanup_after_abort()
            self.assertFalse(missing.parent.exists())

    def test_abort_cleanup_rejects_unsafe_pending_without_removing_anything(self):
        for kind in ("symlink", "wronguid", "wronggid", "mode", "nlink", "directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); cache = root / "cache" / str(os.getuid()); cache.mkdir(parents=True)
                os.chmod(cache, 0o2750); os.chown(cache, os.getuid(), os.getgid())
                current = cache / "current.png"; current.write_bytes(b"current")
                pending = cache / syncmod.PENDING_NAME
                if kind == "symlink":
                    outside = root / "outside"; outside.write_bytes(b"do not unlink target"); pending.symlink_to(outside)
                elif kind == "directory":
                    pending.mkdir()
                else:
                    pending.write_bytes(b"untrusted")
                    os.chmod(pending, 0o600 if kind == "mode" else 0o640)
                    if kind == "nlink": os.link(pending, root / "hardlink")
                real_open_anchored = syncmod._open_anchored
                native_stat = syncmod.os.stat
                def anchor(path, uid, directory=False): return real_open_anchored(path, os.getuid(), directory)
                def injected_stat(path, *args, **kwargs):
                    result = native_stat(path, *args, **kwargs)
                    if path == syncmod.PENDING_NAME and kind in ("wronguid", "wronggid"):
                        return SimpleNamespace(st_mode=result.st_mode,
                                               st_uid=os.getuid() + 1 if kind == "wronguid" else result.st_uid,
                                               st_gid=os.getgid() + 1 if kind == "wronggid" else result.st_gid,
                                               st_nlink=result.st_nlink)
                    return result
                with mock.patch.object(syncmod, "_require_owner_lock"), mock.patch.object(syncmod, "DESTINATION", cache), \
                     mock.patch.object(syncmod, "_open_anchored", side_effect=anchor), \
                     mock.patch.object(syncmod.os, "stat", side_effect=injected_stat), \
                     mock.patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=os.getgid())):
                    with self.assertRaises(syncmod.SyncError): syncmod.cleanup_after_abort()
                self.assertEqual(current.read_bytes(), b"current")
                self.assertTrue(os.path.lexists(pending))
                if kind == "symlink": self.assertEqual((root / "outside").read_bytes(), b"do not unlink target")

    def test_publish_destination_rejects_static_parent_and_leaf_metadata_faults(self):
        original_stat = Path.stat
        destination_leaf = stat.S_IFDIR | 0o2750
        cases = (
            ("ancestor symlink", fake_root_stat(stat.S_IFLNK | 0o777)),
            ("ancestor wrong owner", fake_root_stat(uid=os.getuid() + 1)),
            ("ancestor writable", fake_root_stat(stat.S_IFDIR | 0o777)),
        )
        for label, parent_meta in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                leaf = Path(tmp) / "leaf"; leaf.mkdir(); os.chmod(leaf, 0o2750)
                def injected(path, *args, **kwargs):
                    if str(path) in ("/var", "/var/cache", "/var/cache/sddm-wallpaper-sync"):
                        return parent_meta
                    return original_stat(path, *args, **kwargs)
                with mock.patch.object(Path, "stat", injected):
                    with self.assertRaises(syncmod.SyncError): syncmod._destination_ok(leaf, os.getuid(), os.getgid())
        for label, mode, owner, group in (
            ("leaf symlink", "symlink", os.getuid(), os.getgid()),
            ("leaf non-directory", "file", os.getuid(), os.getgid()),
            ("leaf wrong uid", "dir", os.getuid() + 1, os.getgid()),
            ("leaf wrong gid", "dir", os.getuid(), os.getgid() + 1),
            ("leaf wrong mode", "dir", os.getuid(), os.getgid()),
        ):
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); leaf = root / "leaf"
                if mode == "symlink": leaf.symlink_to(root)
                elif mode == "file": leaf.write_text("not dir")
                else: leaf.mkdir()
                with mock.patch.object(Path, "stat", lambda path, *a, **kw: fake_root_stat() if str(path) in ("/var", "/var/cache", "/var/cache/sddm-wallpaper-sync") else original_stat(path, *a, **kw)):
                    if owner == os.getuid() + 1 or group == os.getgid() + 1:
                        # Test production ownership comparisons using metadata injection;
                        # do not chown arbitrary host files.
                        real_lstat = Path.lstat
                        def lstat(path, *a, **kw):
                            st = real_lstat(path, *a, **kw)
                            if path == leaf: return SimpleNamespace(st_mode=st.st_mode, st_uid=owner, st_gid=group)
                            return st
                        with mock.patch.object(Path, "lstat", lstat):
                            with self.assertRaises(syncmod.SyncError): syncmod._destination_ok(leaf, os.getuid(), os.getgid())
                    else:
                        with self.assertRaises(syncmod.SyncError): syncmod._destination_ok(leaf, os.getuid(), os.getgid())


class SourceAndGetterAcceptanceTests(unittest.TestCase):
    def test_source_pool_ancestor_symlink_and_cooperative_inode_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); real = root / "real"; real.mkdir(); (real / "wall.png").write_bytes(PNG)
            alias = root / "alias"; alias.symlink_to(real, target_is_directory=True)
            cid = "sha256:" + hashlib.sha256(PNG).hexdigest()
            with self.assertRaises((syncmod.SyncError, OSError)): syncmod._source_snapshot(alias / "wall.png", alias, os.getuid(), cid)
            pool = root / "pool"; pool.mkdir(); src = pool / "wall.png"; src.write_bytes(PNG)
            native_stat = syncmod.os.stat; changed = False
            def swap_after_open(path, *args, **kwargs):
                nonlocal changed
                if path == "wall.png" and kwargs.get("dir_fd") is not None and not changed:
                    result = native_stat(path, *args, **kwargs)
                    replacement = pool / "replacement"
                    replacement.write_bytes(PNG)
                    os.replace(replacement, src)
                    changed = True
                    return result
                return native_stat(path, *args, **kwargs)
            with mock.patch.object(syncmod.os, "stat", side_effect=swap_after_open):
                with self.assertRaises(syncmod.SyncError): syncmod._source_snapshot(src, pool, os.getuid(), cid)
            self.assertTrue(changed)

    def test_getter_empty_error_nonpath_and_path_contract(self):
        cases = ((0, b"", False), (1, b"/tmp/wall.png", False), (0, b"not-a-path", False),
                 (0, b"/tmp/wall.png\n/other.png", False), (0, b"/tmp/wall.png\n", True))
        for code, output, accepted in cases:
            with self.subTest(code=code, output=output):
                with mock.patch.object(syncmod, "_bounded_run", return_value=(code, output)):
                    if accepted: self.assertEqual(syncmod._getter(), "/tmp/wall.png")
                    else:
                        with self.assertRaises(syncmod.SyncError): syncmod._getter()

    def _publish_fixture(self, temp: str, getter_values: list[str], state_epochs: list[int] | None = None):
        root = Path(temp); home = root / "home"; home.mkdir()
        profile = home / "profile"; profile.write_text("owned profile fixture")
        state_path = home / "state.json"; state_path.write_text(json.dumps(state_json(str(profile))))
        pool = home / "pool"; pool.mkdir(); source = pool / "wall.png"; source.write_bytes(PNG)
        dest = root / "cache"; dest.mkdir(); (dest / "current.png").write_bytes(b"old-good")
        policy = root / "policy.json"
        policy.write_text(json.dumps({"schema_version": 1, "enabled": True, "profile": "~/profile", "state": "~/state.json", "landscape_pool": "~/pool"}))
        os.chmod(policy, 0o600)
        return home, profile, state_path, pool, source, dest, policy

    def test_readback_mismatch_after_decode_aborts_real_publish_and_preserves_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, _profile, _state, _pool, _source, dest, policy = self._publish_fixture(tmp, [])
            sequence = iter([str(home / "pool/wall.png"), str(home / "pool/other.png")])
            with mock.patch.object(syncmod.Path, "home", return_value=home), \
                 mock.patch.object(syncmod, "_getter", side_effect=lambda: next(sequence)), \
                 mock.patch.object(syncmod, "_normalize", return_value=b"normalized fake PNG bytes"), \
                 mock.patch.object(syncmod, "_destination_ok"):
                with self.assertRaisesRegex(syncmod.SyncError, "changed before publish"):
                    syncmod._publish(policy, dest, os.getuid(), os.getgid(), owner_completed=True)
            self.assertEqual((dest / "current.png").read_bytes(), b"old-good")
            self.assertFalse((dest / syncmod.PENDING_NAME).exists())

    def test_state_change_during_decode_aborts_real_publish_and_preserves_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, _profile, state_path, _pool, _source, dest, policy = self._publish_fixture(tmp, [])
            calls = 0
            original_identity = syncmod._state_identity
            def change_on_normalize(data):
                nonlocal calls
                calls += 1
                updated = state_json(str(home / "profile"), epoch=2)
                state_path.write_text(json.dumps(updated)); os.utime(state_path, None)
                return b"normalized fake PNG bytes"
            with mock.patch.object(syncmod.Path, "home", return_value=home), \
                 mock.patch.object(syncmod, "_getter", return_value=str(home / "pool/wall.png")), \
                 mock.patch.object(syncmod, "_normalize", side_effect=change_on_normalize), \
                 mock.patch.object(syncmod, "_destination_ok"):
                with self.assertRaises(syncmod.SyncError): syncmod._publish(policy, dest, os.getuid(), os.getgid(), owner_completed=True)
            self.assertGreaterEqual(calls, 1)
            self.assertEqual((dest / "current.png").read_bytes(), b"old-good")
            self.assertFalse((dest / syncmod.PENDING_NAME).exists())

    def test_source_bytes_change_during_decode_aborts_without_replacing_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, _profile, _state, _pool, source, dest, policy = self._publish_fixture(tmp, [])
            def mutate(_data):
                replacement = source.with_suffix(".new"); replacement.write_bytes(PNG + b"changed")
                os.replace(replacement, source)
                return b"normalized fake PNG bytes"
            with mock.patch.object(syncmod.Path, "home", return_value=home), \
                 mock.patch.object(syncmod, "_getter", return_value=str(source)), \
                 mock.patch.object(syncmod, "_normalize", side_effect=mutate), \
                 mock.patch.object(syncmod, "_destination_ok"):
                with self.assertRaises(syncmod.SyncError): syncmod._publish(policy, dest, os.getuid(), os.getgid(), owner_completed=True)
            self.assertEqual((dest / "current.png").read_bytes(), b"old-good")
            self.assertFalse((dest / syncmod.PENDING_NAME).exists())

    def test_portrait_first_state_publishes_only_dp1_and_unknown_never_reaches_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state_path = root / "state.json"
            # Portrait DP-2 is deliberately listed first. Strict schema grants
            # acknowledgement only to DP-1; unknown output sets fail closed.
            state_path.write_text(json.dumps({"schema_version": 1, "profile": "/profile", "outputs": {
                "DP-2": {"schema_version": 1, "last_epoch": 1, "last_content_id": "sha256:" + "a" * 64},
                "DP-1": {"schema_version": 1, "last_epoch": 2, "last_content_id": "sha256:" + "b" * 64},
            }}))
            with self.assertRaises(syncmod.SyncError): syncmod._state_identity(state_path, "/profile", os.getuid())
            valid = root / "valid.json"; valid.write_text(json.dumps(state_json("/profile")))
            identity = syncmod._state_identity(valid, "/profile", os.getuid())
            self.assertEqual(identity[0], 1)


class DecoderAcceptanceTests(unittest.TestCase):
    def test_valid_magic_for_all_non_png_jpeg_formats_is_rejected_before_decoder(self):
        formats = (b"GIF89a", b"II*\x00", b"MM\x00*", b"BM", b"\x00\x00\x01\x00", b"RIFFxxxxWEBP")
        for header in formats:
            with self.subTest(header=header), mock.patch.object(syncmod, "_bounded_run", side_effect=[(0, b"1 1 1\n"), (0, PNG)]) as decoder:
                try:
                    result = syncmod._normalize(header + b"valid-looking body")
                except syncmod.SyncError:
                    result = None
                self.assertEqual(decoder.call_count, 0, "unsupported magic must be rejected before decoder invocation")
                self.assertIsNone(result, "unsupported source magic must fail closed")

    def test_decoder_dimension_limit_is_enforced_using_process_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fakebin = Path(tmp) / "bin"; fakebin.mkdir(); tool = fakebin / "magick"
            tool.write_text("#!/usr/bin/env python3\nimport os,sys\nsys.stdout.write(os.environ['FAKE_IDENTIFY'])\n")
            tool.chmod(0o700)
            for metadata, expected in (("100000 100000 1\n", "pixel dimensions"), ("1 1 2\n", "multi-frame")):
                with self.subTest(metadata=metadata), mock.patch.dict(os.environ, {
                    "PATH": str(fakebin) + os.pathsep + os.environ.get("PATH", ""), "FAKE_IDENTIFY": metadata,
                }):
                    with self.assertRaisesRegex(syncmod.SyncError, expected): syncmod._normalize(PNG)

    def test_decoder_timeout_reaps_child_and_output_cap_keeps_old_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fakebin = root / "bin"; fakebin.mkdir(); pidfile = root / "child.pid"
            tool = fakebin / "magick"
            tool.write_text("#!/usr/bin/env python3\nimport os,subprocess,sys,time\n"
                            f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\nopen({str(pidfile)!r},'w').write(str(p.pid))\n"
                            "time.sleep(30)\n")
            tool.chmod(0o700)
            old = root / "current.png"; old.write_bytes(b"exact previous")
            with mock.patch.dict(os.environ, {"PATH": str(fakebin) + os.pathsep + os.environ.get("PATH", "")}):
                with self.assertRaises(syncmod.SyncError): syncmod._bounded_run([str(tool)], timeout=0.2, max_output=32)
            child_pid = int(pidfile.read_text())
            try:
                with self.assertRaises(ProcessLookupError): os.kill(child_pid, 0)
            finally:
                # On the known direct-child-only implementation the orphan can
                # survive the failure; ensure it never leaks from this test.
                try: os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError: pass

    def test_bounded_decoder_output_cap_preserves_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); overflow = root / "overflow.py"
            overflow.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(b'x' * (33 * 1024 * 1024))\n")
            overflow.chmod(0o700)
            old = root / "current.png"; old.write_bytes(b"exact previous")
            with self.assertRaises(syncmod.SyncError):
                syncmod._bounded_run([str(overflow)], timeout=5, max_output=32)
            self.assertEqual(old.read_bytes(), b"exact previous")

    def test_owner_completed_path_calls_actual_writer_even_when_service_state_irrelevant(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SourceAndGetterAcceptanceTests()
            home, _profile, _state, _pool, _source, dest, policy = fixture._publish_fixture(tmp, [])
            import fcntl
            runtime = Path(tmp) / "runtime"; runtime.mkdir()
            lock = runtime / "ezwallpaper-rotate.lock"; lock.touch(mode=0o600); os.chmod(lock, 0o600)
            lock_fd = os.open(lock, os.O_RDWR); fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self.addCleanup(os.close, lock_fd)
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(runtime)}), \
                 mock.patch.object(syncmod.Path, "home", return_value=home), \
                 mock.patch.object(syncmod, "_getter", return_value=str(home / "pool/wall.png")), \
                 mock.patch.object(syncmod, "_normalize", return_value=b"normalized image bytes"), \
                 mock.patch.object(syncmod, "_owner_success", side_effect=AssertionError("private owner proof must bypass historical ActiveState")), \
                 mock.patch.object(syncmod, "_destination_ok"):
                syncmod._require_owner_lock()
                result = syncmod._publish(policy, dest, os.getuid(), os.getgid(), owner_completed=True)
            self.assertEqual(result, "published")
            self.assertEqual((dest / "current.png").read_bytes(), b"normalized image bytes")
            self.assertEqual((dest / "current.png").stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
