#!/usr/bin/env python3
"""Safely acquire one Bing wallpaper into the ezwallpaper landscape pool."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 20 * 1024 * 1024
KEEP = 12
API_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"
OWNED_NAME = re.compile(r"bing-refill-[A-Za-z0-9_-]{1,80}\.jpg\Z")


def fetch(url: str, limit: int = MAX_BYTES) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "wallpaper-refill/1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname != "www.bing.com":
            raise ValueError("refusing unexpected response host")
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("response empty or exceeds size limit")
    return data


def decode_image(path: Path) -> None:
    # ImageMagick's identify fully decodes the file; no renderer is invoked.
    subprocess.run(["identify", "-regard-warnings", str(path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=15)


def acquire(data_dir: Path, fetcher=fetch, decoder=decode_image) -> Path:
    pool = data_dir / "wallpapers" / "landscape" / "hourly-refill"
    if pool.is_symlink():
        raise ValueError("refusing symlinked refill directory")
    pool.mkdir(parents=True, exist_ok=True)
    if pool.resolve() != pool.absolute():
        raise ValueError("refill directory escaped configured pool")
    lock_path = data_dir / "wallpapers" / ".hourly-refill.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_symlink():
        raise ValueError("refusing symlinked lock file")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another refill is running") from exc
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
        target = pool / name
        manifest = pool / ".wallpaper-hourly-refill.json"
        if target.is_symlink():
            raise ValueError("refusing symlinked destination")
        if target.exists():
            try:
                known = json.loads(manifest.read_text()) if manifest.exists() and not manifest.is_symlink() else []
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("invalid ownership manifest") from exc
            if not isinstance(known, list) or name not in known:
                raise ValueError("refusing to replace an unowned destination")
        if not target.exists():
            fd, temp_name = tempfile.mkstemp(prefix=".refill-", suffix=".tmp", dir=pool)
            temp = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(image)
                    stream.flush()
                    os.fsync(stream.fileno())
                decoder(temp)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        _retain(pool, target)
        return target


def _retain(pool: Path, newest: Path) -> None:
    manifest = pool / ".wallpaper-hourly-refill.json"
    if manifest.is_symlink():
        raise ValueError("refusing symlinked ownership manifest")
    try:
        entries = json.loads(manifest.read_text()) if manifest.exists() else []
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid ownership manifest") from exc
    if not isinstance(entries, list) or any(
        not isinstance(name, str) or not OWNED_NAME.fullmatch(name) for name in entries
    ):
        raise ValueError("invalid ownership manifest entries")
    names = set(entries)
    names.add(newest.name)
    ordered = sorted(names, reverse=True)
    keep = ordered[:KEEP]
    for name in ordered[KEEP:]:
        old = pool / name
        if old.is_symlink():
            raise ValueError("refusing symlinked owned image")
        if old.is_file():
            old.unlink()
    fd, temp_name = tempfile.mkstemp(prefix=".manifest-", dir=pool)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(keep, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, manifest)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    try:
        result = acquire(data_home)
    except Exception as exc:
        # Never print URLs, response bodies, or proxy configuration.
        print(f"wallpaper-hourly-refill: {type(exc).__name__}: refill failed", file=sys.stderr)
        return 1
    print(f"wallpaper-hourly-refill: published {result.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
