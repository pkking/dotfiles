#!/usr/bin/env python3
"""Publish the acknowledged DP-1 wallpaper to a pre-provisioned SDDM cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

POLICY = Path.home() / ".config/sddm-wallpaper-sync/policy.json"
DESTINATION = Path("/var/cache/sddm-wallpaper-sync") / str(os.getuid())
OWNER_UNIT = "ezwallpaper-rotate.service"
MAX_POLICY = 16_384
MAX_STATE = 65_536
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SECONDS = 20
ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class SyncError(Exception):
    """A fail-closed validation or publication error."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SyncError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_file(path: Path, limit: int, uid: int) -> dict[str, Any]:
    fd, st = _open_anchored(path, uid, directory=False)
    try:
        if st.st_mode & 0o022 or st.st_size > limit:
            raise SyncError(f"unsafe or oversized file: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns):
            raise SyncError(f"file changed while reading: {path}")
    finally:
        os.close(fd)
    if len(raw) > limit:
        raise SyncError(f"oversized file: {path}")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SyncError(f"expected JSON object: {path}")
    return value


def _open_anchored(path: Path, expected_uid: int, directory: bool = False) -> tuple[int, os.stat_result]:
    """Open an absolute path component-by-component without following links."""
    path = path.expanduser()
    if not path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise SyncError("path must be canonical and absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:-1] if not directory else path.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if directory:
            st = os.fstat(fd)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != expected_uid:
                raise SyncError(f"not an owned directory: {path}")
            result_fd = fd
            fd = -1
            return result_fd, st
        name = path.name
        file_fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
        st = os.fstat(file_fd)
        os.close(fd)
        fd = -1
        if not stat.S_ISREG(st.st_mode) or st.st_uid != expected_uid:
            os.close(file_fd)
            raise SyncError(f"not an owned regular file: {path}")
        return file_fd, st
    finally:
        if fd >= 0:
            os.close(fd)


def _safe_path(path: Path, expected_uid: int, directory: bool = False) -> Path:
    """Validate through a no-follow dirfd walk; callers reopen by dirfd at use."""
    fd, _ = _open_anchored(path, expected_uid, directory)
    os.close(fd)
    return path.expanduser()


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = _json_file(path, MAX_POLICY, os.getuid())
    except FileNotFoundError as exc:
        raise SyncError(f"policy missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError("invalid policy JSON") from exc
    if not isinstance(policy, dict) or set(policy) != {"schema_version", "enabled", "profile", "state", "landscape_pool"}:
        raise SyncError("policy keys/schema mismatch")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise SyncError("unsupported policy schema")
    if type(policy["enabled"]) is not bool:
        raise SyncError("enabled must be boolean")
    for key in ("profile", "state", "landscape_pool"):
        if not isinstance(policy[key], str) or not policy[key] or "\x00" in policy[key]:
            raise SyncError(f"invalid policy {key}")
    return policy


def _bounded_run(argv: list[str], *, input_data: bytes | None = None, timeout: int,
                 max_output: int, limit_fsize: bool = False) -> tuple[int, bytes]:
    """Capture child stdout in a capped anonymous file, never an unbounded pipe."""
    import resource
    with tempfile.TemporaryFile() as output:
        def set_limits() -> None:
            # stdout is an anonymous regular file, so RLIMIT_FSIZE bounds bytes
            # at generation time rather than after unbounded pipe/file growth.
            cap = max(max_output, MAX_SOURCE_BYTES)
            resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.DEVNULL, close_fds=True,
                                   preexec_fn=set_limits)
            try:
                proc.communicate(input=input_data, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                proc.kill()
                proc.wait()
                raise SyncError("child process timed out") from exc
        except OSError as exc:
            raise SyncError(f"required tool unavailable: {argv[0]}") from exc
        size = os.fstat(output.fileno()).st_size
        if size > max_output:
            raise SyncError("child output exceeded configured bound")
        output.seek(0)
        return proc.returncode, output.read(max_output + 1)


def _owner_success() -> None:
    code, raw = _bounded_run(["systemctl", "--user", "show", OWNER_UNIT, "--property=Result", "--property=ExecMainStatus", "--property=ActiveState"], timeout=3, max_output=4096)
    if code != 0:
        raise SyncError("cannot verify wallpaper owner result")
    fields = dict(line.split("=", 1) for line in raw.decode("utf-8", "replace").splitlines() if "=" in line)
    if set(fields) != {"Result", "ExecMainStatus", "ActiveState"} or fields.get("Result") != "success" or fields.get("ExecMainStatus") != "0" or fields.get("ActiveState") != "inactive":
        raise SyncError("wallpaper owner did not complete successfully")


def _getter() -> str:
    code, raw = _bounded_run(["noctalia", "msg", "wallpaper-get", "DP-1"], timeout=5, max_output=4096)
    if code:
        raise SyncError("Noctalia wallpaper getter failed")
    value = raw.decode("utf-8", "replace").strip()
    if not value or "\n" in value or "\r" in value or not value.startswith("/"):
        raise SyncError("Noctalia returned no single absolute path")
    return value


def _state_identity(path: Path, profile: str, uid: int) -> tuple[int, str, int]:
    state = _json_file(path, MAX_STATE, uid)
    if set(state) != {"schema_version", "profile", "outputs"} or type(state.get("schema_version")) is not int or state["schema_version"] != 1 or state["profile"] != profile:
        raise SyncError("rotation state schema/profile mismatch")
    output = state.get("outputs")
    if not isinstance(output, dict) or set(output) != {"DP-1"}:
        raise SyncError("rotation state missing DP-1")
    entry = output["DP-1"]
    if not isinstance(entry, dict) or set(entry) != {"schema_version", "last_epoch", "last_content_id"} or type(entry.get("schema_version")) is not int or entry["schema_version"] != 1:
        raise SyncError("invalid DP-1 state")
    epoch, content_id = entry.get("last_epoch"), entry.get("last_content_id")
    if type(epoch) is not int or epoch <= 0 or not isinstance(content_id, str) or not ID_RE.fullmatch(content_id):
        raise SyncError("invalid DP-1 acknowledgement")
    st = path.stat()
    now = time.time()
    if st.st_mtime > now + 5 or now - st.st_mtime > 7 * 86400:
        raise SyncError("rotation state is stale or future-dated")
    return epoch, content_id, st.st_ino


def _source_snapshot(path: Path, pool: Path, uid: int, content_id: str) -> tuple[bytes, tuple[int, int, int, int]]:
    pool = pool.expanduser()
    candidate = path.expanduser()
    if not pool.is_absolute() or candidate.parent != pool or not candidate.is_absolute():
        raise SyncError("wallpaper is not a direct child of configured landscape pool")
    directory_fd, directory = _open_anchored(pool, uid, directory=True)
    try:
        if directory.st_uid != uid or not stat.S_ISDIR(directory.st_mode):
            raise SyncError("landscape pool changed while opening")
        before = os.stat(candidate.name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != uid:
            raise SyncError("wallpaper is not an owned regular file")
        if before.st_size <= 0 or before.st_size > MAX_SOURCE_BYTES:
            raise SyncError("wallpaper byte size outside bounds")
        fd = os.open(candidate.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
        try:
            fdst = os.fstat(fd)
            if (fdst.st_dev, fdst.st_ino) != (before.st_dev, before.st_ino):
                raise SyncError("wallpaper changed while opening")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(MAX_SOURCE_BYTES + 1)
        finally:
            os.close(fd)
        after = os.stat(candidate.name, dir_fd=directory_fd, follow_symlinks=False)
    finally:
        os.close(directory_fd)
    fingerprint = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if len(data) != before.st_size or fingerprint != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise SyncError("wallpaper changed during snapshot")
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")):
        raise SyncError("only PNG/JPEG source images are accepted")
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    if digest != content_id:
        raise SyncError("source bytes do not match committed wallpaper identity")
    return data, fingerprint


def _normalize(data: bytes) -> bytes:
    # Probe all frames first: accepting only [0] would silently publish one frame
    # from an animated/multipage input rather than rejecting it.
    if data.startswith(b"\x89PNG\r\n\x1a\n") and (b"acTL" in data or b"fcTL" in data):
        raise SyncError("animated PNG is not accepted")
    coder = "jpeg:-" if data.startswith(b"\xff\xd8\xff") else "png:-"
    try:
        probe_code, probe_data = _bounded_run(["magick", "identify", "-limit", "time", str(MAX_SECONDS), "-limit", "memory", "256MiB",
                            "-limit", "map", "512MiB", "-limit", "disk", "512MiB",
                            "-regard-warnings", "-format", "%w %h %n\\n", coder],
                           input_data=data, timeout=MAX_SECONDS, max_output=128)
    except SyncError as exc:
        raise SyncError("image frame probe failed or exceeded bounds") from exc
    if probe_code:
        raise SyncError("image frame probe failed or exceeded bounds")
    try:
        metadata = [tuple(int(part) for part in line.split()) for line in probe_data.splitlines()]
    except ValueError as exc:
        raise SyncError("invalid image frame metadata") from exc
    if not metadata or len(metadata) != 1 or len(metadata[0]) != 3:
        raise SyncError("multi-frame images are not accepted")
    width, height, frame_count = metadata[0]
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise SyncError("image pixel dimensions outside bounds")
    if frame_count != 1:
        raise SyncError("multi-frame images are not accepted")
    # Fixed ImageMagick executable, no shell, no user-controlled options, no delegates.
    command = ["magick", "-limit", "time", str(MAX_SECONDS), "-limit", "memory", "256MiB",
               "-limit", "map", "512MiB", "-limit", "disk", "512MiB", "-define", "registry:temporary-path=/tmp",
               coder.replace(":-", ":[0]"), "-auto-orient", "-strip", "-alpha", "remove", "-alpha", "off", "-resize", "8000x5000>", "PNG:-"]
    try:
        code, normalized = _bounded_run(command, input_data=data, timeout=MAX_SECONDS + 2,
                                        max_output=MAX_SOURCE_BYTES, limit_fsize=True)
    except SyncError as exc:
        raise SyncError("image normalization failed or timed out") from exc
    if code or not 0 < len(normalized) <= MAX_SOURCE_BYTES:
        raise SyncError("bounded image normalization failed")
    if not normalized.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SyncError("normalized image output is invalid")
    return normalized


def _destination_ok(destination: Path, uid: int, sddm_gid: int) -> None:
    # The root-owned base and parents must not be replaceable by the user.
    base = Path("/var/cache/sddm-wallpaper-sync")
    for parent in (Path("/var"), Path("/var/cache"), base):
        st = parent.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise SyncError(f"unsafe cache parent: {parent}")
    try:
        leaf = destination.lstat()
    except FileNotFoundError as exc:
        raise SyncError(f"configured cache is not provisioned: {destination}") from exc
    if not stat.S_ISDIR(leaf.st_mode) or stat.S_ISLNK(leaf.st_mode) or leaf.st_uid != uid or leaf.st_gid != sddm_gid or stat.S_IMODE(leaf.st_mode) != 0o2750:
        raise SyncError("cache leaf ownership/mode mismatch (expected uid:sddm 2750)")


PENDING_NAME = ".current.png.pending"


def _remove_pending(directory_fd: int, uid: int, sddm_gid: int) -> bool:
    try:
        st = os.stat(PENDING_NAME, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_gid != sddm_gid or stat.S_IMODE(st.st_mode) != 0o640 or st.st_nlink != 1:
        raise SyncError("unsafe fixed pending file")
    os.unlink(PENDING_NAME, dir_fd=directory_fd)
    return True


def _write_atomic(directory_fd: int, image: bytes, uid: int, sddm_gid: int, before_commit: Any = None) -> str:
    name = PENDING_NAME
    fd = -1
    created = False
    renamed = False
    try:
        _remove_pending(directory_fd, uid, sddm_gid)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=directory_fd)
        created = True
        os.fchown(fd, uid, sddm_gid)
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(image)
            stream.flush()
            os.fsync(fd)
        if before_commit:
            before_commit()
        os.replace(name, "current.png", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        renamed = True
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            raise SyncError("COMMITTED: new image is published but directory durability is uncertain") from exc
        return "published"
    except SyncError:
        raise
    except OSError as exc:
        if renamed:
            raise SyncError("COMMITTED: new image published; post-rename durability uncertain") from exc
        raise SyncError(f"publication failed before commit: {exc}") from exc
    finally:
        if created and not renamed and fd >= 0:
            try:
                owned = os.fstat(fd)
                current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if (owned.st_dev, owned.st_ino) == (current.st_dev, current.st_ino):
                    os.unlink(name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        if fd >= 0:
            os.close(fd)


def _publish_image(destination: Path, image: bytes, uid: int, sddm_gid: int, before_commit: Any = None) -> str:
    _destination_ok(destination, uid, sddm_gid)
    directory_fd, prior = _open_anchored(destination, uid, directory=True)
    try:
        opened = os.fstat(directory_fd)
        if (opened.st_dev, opened.st_ino) != (prior.st_dev, prior.st_ino):
            raise SyncError("cache directory changed while opening")
        return _write_atomic(directory_fd, image, uid, sddm_gid, before_commit)
    finally:
        os.close(directory_fd)


def cleanup_after_abort() -> None:
    """Remove only the fixed validated pending file while wrapper still owns flock."""
    _require_owner_lock()
    try:
        sddm_gid = __import__("grp").getgrnam("sddm").gr_gid
    except KeyError as exc:
        raise SyncError("sddm group is unavailable") from exc
    try:
        parent_fd, parent_stat = _open_anchored(DESTINATION.parent, 0, directory=True)
        leaf = DESTINATION.name
        leaf_stat = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(leaf_stat.st_mode) or leaf_stat.st_uid != os.getuid() or leaf_stat.st_gid != sddm_gid or stat.S_IMODE(leaf_stat.st_mode) != 0o2750:
            raise SyncError("cache leaf ownership/mode mismatch")
        leaf_fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if (os.fstat(leaf_fd).st_dev, os.fstat(leaf_fd).st_ino) != (leaf_stat.st_dev, leaf_stat.st_ino):
                raise SyncError("cache directory changed")
            _remove_pending(leaf_fd, os.getuid(), sddm_gid)
        finally:
            os.close(leaf_fd)
        os.close(parent_fd)
    except FileNotFoundError:
        return


def _publish(policy_path: Path, destination: Path, uid: int, sddm_gid: int | None) -> str:
    uid = os.getuid() if uid is None else uid
    if not policy_path.exists():
        raise SyncError(f"policy missing: {policy_path}")
    policy = _load_policy(policy_path)
    if not policy["enabled"]:
        return "disabled: no wallpaper or cache access performed"
    _owner_success()
    home = Path.home()
    profile = _safe_path(home / policy["profile"].removeprefix("~/"), uid)
    state_path = _safe_path(home / policy["state"].removeprefix("~/"), uid)
    pool = _safe_path(home / policy["landscape_pool"].removeprefix("~/"), uid, directory=True)
    profile_real = str(profile)
    state1 = _state_identity(state_path, profile_real, uid)
    source_path = Path(_getter())
    data, fingerprint = _source_snapshot(source_path, pool, uid, state1[1])
    normalized = _normalize(data)
    if _state_identity(state_path, profile_real, uid) != state1 or _getter() != str(source_path) or source_path.stat().st_ino != fingerprint[1]:
        raise SyncError("rotation/readback/source changed before publish")
    if sddm_gid is None:
        import grp
        try:
            sddm_gid = grp.getgrnam("sddm").gr_gid
        except KeyError as exc:
            raise SyncError("sddm group is unavailable") from exc
    # The fixed wrapper holds the canonical ezwallpaper flock through this
    # transaction; this final guard executes after temp fsync, immediately
    # before atomic rename.
    def verify_current() -> None:
        if _state_identity(state_path, profile_real, uid) != state1 or _getter() != str(source_path):
            raise SyncError("rotation changed before publication")
        current_bytes, current_fingerprint = _source_snapshot(source_path, pool, uid, state1[1])
        if current_fingerprint != fingerprint or current_bytes != data:
            raise SyncError("wallpaper bytes changed before publication")
    verify_current()
    return _publish_image(destination, normalized, uid, sddm_gid, verify_current)


def _require_owner_lock() -> None:
    """Require the canonical cooperative lock descriptor before publication."""
    import fcntl
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    expected = runtime / "ezwallpaper-rotate.lock"
    try:
        target = expected.lstat()
    except OSError as exc:
        raise SyncError("canonical owner lock is unavailable") from exc
    if not stat.S_ISREG(target.st_mode) or target.st_uid != os.getuid() or target.st_mode & 0o022:
        raise SyncError("canonical owner lock has unsafe ownership or mode")
    for entry in Path("/proc/self/fd").iterdir():
        try:
            fd = int(entry.name)
            opened = os.fstat(fd)
            if os.readlink(entry) != str(expected) or (opened.st_dev, opened.st_ino) != (target.st_dev, target.st_ino):
                continue
            probe = os.open(expected, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                else:
                    fcntl.flock(probe, fcntl.LOCK_UN)
            finally:
                os.close(probe)
        except (OSError, ValueError):
            continue
    raise SyncError("canonical owner flock proof missing")


def publish_after_owner_success() -> str:
    """Wrapper-only publication; require and retain the canonical owner flock."""
    _require_owner_lock()
    return _publish(POLICY, DESTINATION, os.getuid(), None)


def sync(policy_path: Path = POLICY, destination: Path = DESTINATION, uid: int | None = None,
         sddm_gid: int | None = None) -> str:
    """Standalone CLI is deliberately disabled; publication requires wrapper proof."""
    policy = _load_policy(policy_path)
    if not policy["enabled"]:
        return "disabled: no wallpaper or cache access performed"
    raise SyncError("enabled publication requires the canonical owner wrapper")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(sync())
        return 0
    except (SyncError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"sddm-wallpaper-sync: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
