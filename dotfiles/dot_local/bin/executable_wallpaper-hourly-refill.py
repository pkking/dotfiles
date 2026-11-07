#!/usr/bin/env python3
"""Safely acquire one Bing wallpaper into the ezwallpaper landscape pool."""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import urllib.parse
import urllib.request

MAX_BYTES = 20 * 1024 * 1024
KEEP = 12
API_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"
API_PATH = "/HPImageArchive.aspx"
IMAGE_PATH = re.compile(r"/th\?id=OHR\.[A-Za-z0-9_-]{1,100}_UHD\.jpg\Z")
OWNED_NAME = re.compile(r"bing-refill-[A-Za-z0-9_-]{1,80}\.jpg\Z")
MAX_WIDTH = 12000
MAX_HEIGHT = 8000
MAX_PIXELS = 40_000_000


def _valid_url(url: str, kind: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme == "https" and parsed.netloc == "www.bing.com"
                and parsed.hostname == "www.bing.com" and parsed.port is None
                and parsed.username is None and parsed.password is None
                and not parsed.fragment and
                ((kind == "api" and parsed.path == API_PATH and
                  parsed.query == "format=js&idx=0&n=1&mkt=en-US") or
                 (kind == "image" and bool(IMAGE_PATH.fullmatch(parsed.path + "?" + parsed.query)))))
    except ValueError:
        return False


class _SameEndpointRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _valid_url(newurl, self.kind):
            raise ValueError("refusing unsafe redirect destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, limit: int = MAX_BYTES) -> bytes:
    kind = "api" if url == API_URL else "image"
    if not _valid_url(url, kind):
        raise ValueError("refusing unexpected request URL")
    request = urllib.request.Request(url, headers={"User-Agent": "wallpaper-refill/1"})
    opener = urllib.request.build_opener(_SameEndpointRedirect(kind))
    with opener.open(request, timeout=20) as response:
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("response empty or exceeds size limit")
    return data


def decode_image(fd: int) -> None:
    # Resource limits apply before decoding; output dimensions are checked after decode.
    result = subprocess.run(
        ["identify", "-regard-warnings", "-limit", "memory", "128MiB",
         "-limit", "map", "256MiB", "-limit", "disk", "512MiB",
         "-limit", "area", "40MP", "-limit", "thread", "2",
         "-format", "%w %h", f"/proc/self/fd/{fd}"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, timeout=15, pass_fds=(fd,))
    match = re.fullmatch(r"\s*(\d+)\s+(\d+)\s*", result.stdout)
    if not match:
        raise ValueError("image dimensions unavailable")
    width, height = map(int, match.groups())
    if width < 1 or height < 1 or width > MAX_WIDTH or height > MAX_HEIGHT or width * height > MAX_PIXELS:
        raise ValueError("image dimensions exceed limits")


def _open_directory(path: Path, create: bool = False) -> int:
    """Open every component without following symlinks, optionally creating it."""
    absolute = path.absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in absolute.parts[1:]:
            if component in ("", ".", ".."):
                raise ValueError("unsafe directory path")
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, 0o700, dir_fd=fd)
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _child_dir(parent_fd: int, name: str, create: bool = False) -> int:
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def _verify_data_dir(path: Path, fd: int) -> None:
    current = _open_directory(path)
    try:
        opened = os.fstat(fd)
        named = os.fstat(current)
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError("data directory path was replaced")
    finally:
        os.close(current)


def _verify_named_dir(parent_fd: int, name: str, fd: int) -> None:
    opened = os.fstat(fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
        raise ValueError("directory path was replaced")


def _read_owned(fd: int) -> list[str]:
    names = []
    for name in os.listdir(fd):
        if not OWNED_NAME.fullmatch(name):
            continue
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("unsafe owned image entry")
        names.append(name)
    return names


def _acquire_instance_lock() -> socket.socket:
    """Hold a Linux per-UID abstract socket name independent of filesystem paths."""
    lock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        lock.bind(f"\0dotfiles-wallpaper-hourly-refill.{os.getuid()}")
    except OSError as exc:
        lock.close()
        if exc.errno == errno.EADDRINUSE:
            raise RuntimeError("another refill is running") from exc
        raise
    return lock


def acquire(data_dir: Path, fetcher=fetch, decoder=decode_image) -> Path:
    data_dir = Path(data_dir).absolute()
    data_fd = _open_directory(data_dir, create=True)
    try:
        wallpapers_fd = _child_dir(data_fd, "wallpapers", create=True)
        landscape_fd = pool_fd = None
        try:
            landscape_fd = _child_dir(wallpapers_fd, "landscape", create=True)
            pool_fd = _child_dir(landscape_fd, "hourly-refill", create=True)
            # Linux abstract AF_UNIX namespace is kernel-owned and unaffected by
            # replacement of any filesystem ancestor. Keep it for the full run.
            lock = _acquire_instance_lock()
            try:
                return _acquire_locked(data_dir, data_fd, wallpapers_fd, landscape_fd, pool_fd, fetcher, decoder)
            finally:
                lock.close()
        finally:
            if pool_fd is not None:
                os.close(pool_fd)
            if landscape_fd is not None:
                os.close(landscape_fd)
            os.close(wallpapers_fd)
    finally:
        os.close(data_fd)


def _acquire_locked(data_dir: Path, data_fd: int, wallpapers_fd: int, landscape_fd: int,
                    pool_fd: int, fetcher, decoder) -> Path:
    entries = _read_owned(pool_fd)
    if len(entries) >= KEEP:
        raise RuntimeError("owned image pool is full; remove an old owned image manually")
    payload = json.loads(fetcher(API_URL))
    images = payload.get("images")
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        raise ValueError("Bing response has no image")
    urlbase = images[0].get("urlbase")
    if not isinstance(urlbase, str) or not re.fullmatch(r"/th\?id=OHR\.[A-Za-z0-9_-]{1,100}", urlbase):
        raise ValueError("unexpected Bing image path")
    image_url = "https://www.bing.com" + urlbase + "_UHD.jpg"
    image = fetcher(image_url)
    if len(image) > MAX_BYTES or not image.startswith(b"\xff\xd8\xff"):
        raise ValueError("download is not a bounded JPEG")
    day_id = images[0].get("startdate", "")
    if not re.fullmatch(r"\d{8}", day_id):
        raise ValueError("unexpected Bing image date")
    name = f"bing-refill-{day_id}.jpg"
    try:
        os.stat(name, dir_fd=pool_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("destination already exists")

    temp_name = f".refill-{os.getpid()}-{os.urandom(8).hex()}.tmp"
    _verify_data_dir(data_dir, data_fd)
    _verify_named_dir(data_fd, "wallpapers", wallpapers_fd)
    _verify_named_dir(wallpapers_fd, "landscape", landscape_fd)
    _verify_named_dir(landscape_fd, "hourly-refill", pool_fd)
    fd = os.open(temp_name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                 0o600, dir_fd=pool_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(image)
            stream.flush()
            os.fsync(fd)
        decoder(fd)
        _verify_data_dir(data_dir, data_fd)
        _verify_named_dir(data_fd, "wallpapers", wallpapers_fd)
        _verify_named_dir(wallpapers_fd, "landscape", landscape_fd)
        _verify_named_dir(landscape_fd, "hourly-refill", pool_fd)
        os.close(fd)
        fd = -1
        # No overwrite: a racing creator causes failure rather than replacing its file.
        os.link(temp_name, name, src_dir_fd=pool_fd, dst_dir_fd=pool_fd, follow_symlinks=False)
        os.unlink(temp_name, dir_fd=pool_fd)
        os.fsync(pool_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=pool_fd)
        except FileNotFoundError:
            pass
    return data_dir / "wallpapers" / "landscape" / "hourly-refill" / name


def main() -> int:
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    try:
        result = acquire(data_home)
    except Exception as exc:
        print(f"wallpaper-hourly-refill: {type(exc).__name__}: refill failed", file=sys.stderr)
        return 1
    print(f"wallpaper-hourly-refill: published {result.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
