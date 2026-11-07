"""Hermetic tests for the opt-in wallpaper acquisition job."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "dotfiles/dot_local/bin/executable_wallpaper-hourly-refill.py"
spec = importlib.util.spec_from_file_location("wallpaper_refill", SCRIPT)
refill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refill)


def fake_fetch(url):
    if url == refill.API_URL:
        return json.dumps({"images": [{"urlbase": "/th?id=OHR.TestImage", "startdate": "20261105"}]}).encode()
    if url == "https://www.bing.com/th?id=OHR.TestImage_UHD.jpg":
        return b"\xff\xd8\xfffake-image"
    raise AssertionError(f"unexpected URL: {url}")


class RefillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "home" / ".local" / "share"
        self.pool = self.data / "wallpapers/landscape/hourly-refill"

    def tearDown(self):
        self.temp.cleanup()

    def test_success_is_atomic_and_never_calls_renderer(self):
        decoder = mock.Mock()
        with mock.patch("subprocess.run", side_effect=AssertionError("renderer invoked")):
            result = refill.acquire(self.data, fake_fetch, decoder)
        self.assertEqual(result.read_bytes(), b"\xff\xd8\xfffake-image")
        self.assertFalse((self.pool / ".wallpaper-hourly-refill.json").exists())
        decoder.assert_called_once()
        self.assertFalse(list(self.pool.glob("*.tmp")))

    def test_decode_and_temp_fsync_failures_publish_nothing(self):
        self.pool.mkdir(parents=True)
        prior = self.pool / "unrelated.jpg"
        prior.write_bytes(b"keep")
        with self.assertRaises(RuntimeError):
            refill.acquire(self.data, fake_fetch, mock.Mock(side_effect=RuntimeError("bad image")))
        self.assertEqual(prior.read_bytes(), b"keep")
        self.assertEqual(list(self.pool.iterdir()), [prior])
        with mock.patch.object(refill.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                refill.acquire(self.data, fake_fetch, mock.Mock())
        self.assertEqual(list(self.pool.iterdir()), [prior])

    def test_network_failure_preserves_existing_pool(self):
        self.pool.mkdir(parents=True)
        existing = self.pool / "existing-wallpaper.jpg"
        existing.write_bytes(b"keep")
        def unavailable(_url):
            raise TimeoutError("offline fixture")
        with self.assertRaises(TimeoutError):
            refill.acquire(self.data, unavailable, mock.Mock())
        self.assertEqual(existing.read_bytes(), b"keep")
        self.assertEqual(list(self.pool.iterdir()), [existing])

    def test_redirect_is_rejected_before_a_second_request(self):
        requests = []
        handler = refill._SameEndpointRedirect("api")
        class FakeOpener:
            def open(self, request, timeout):
                requests.append(request.full_url)
                handler.redirect_request(request, None, 302, "Found", {}, "https://evil.example/steal")
        with mock.patch.object(refill.urllib.request, "build_opener", return_value=FakeOpener()):
            with self.assertRaises(ValueError):
                refill.fetch(refill.API_URL)
        self.assertEqual(requests, [refill.API_URL])

    def test_redirect_ports_userinfo_and_bad_paths_are_refused(self):
        handler = refill._SameEndpointRedirect("image")
        request = refill.urllib.request.Request("https://www.bing.com/th?id=OHR.Test_UHD.jpg")
        for url in ("https://www.bing.com:444/th?id=OHR.Test_UHD.jpg",
                    "https://user@www.bing.com/th?id=OHR.Test_UHD.jpg",
                    "https://www.bing.com/other", "http://www.bing.com/th?id=OHR.Test_UHD.jpg"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, url)
        self.assertTrue(refill._valid_url("https://www.bing.com/th?id=OHR.Test_UHD.jpg", "image"))

    def test_invalid_provider_path_is_rejected_before_image_fetch(self):
        calls = []
        def hostile(url):
            calls.append(url)
            if url == refill.API_URL:
                return b'{"images":[{"urlbase":"/other","startdate":"20261105"}]}'
            raise AssertionError("bad image URL fetched")
        with self.assertRaises(ValueError):
            refill.acquire(self.data, hostile, mock.Mock())
        self.assertEqual(calls, [refill.API_URL])

    def test_directory_replacement_race_fails_without_writing_through_symlink(self):
        elsewhere = Path(self.temp.name) / "elsewhere"
        elsewhere.mkdir()
        def replace_during_fetch(url):
            if url == refill.API_URL:
                return json.dumps({"images": [{"urlbase": "/th?id=OHR.TestImage", "startdate": "20261105"}]}).encode()
            moved = self.pool.with_name("hourly-refill-original")
            self.pool.rename(moved)
            self.pool.symlink_to(elsewhere, target_is_directory=True)
            return b"\xff\xd8\xfffake-image"
        with self.assertRaises(ValueError):
            refill.acquire(self.data, replace_during_fetch, mock.Mock())
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertEqual(list(self.pool.with_name("hourly-refill-original").iterdir()), [])

    def test_abstract_lock_survives_wallpapers_parent_replacement(self):
        entered_fetch = threading.Event()
        release_fetch = threading.Event()
        first_errors = []
        calls = []

        def blocked_fetch(url):
            calls.append(url)
            if url == refill.API_URL:
                return fake_fetch(url)
            entered_fetch.set()
            if not release_fetch.wait(timeout=5):
                raise TimeoutError("test did not release first invocation")
            return fake_fetch(url)

        def first_invocation():
            try:
                refill.acquire(self.data, blocked_fetch, mock.Mock())
            except Exception as exc:
                first_errors.append(exc)

        first = threading.Thread(target=first_invocation)
        first.start()
        self.assertTrue(entered_fetch.wait(timeout=5), "first invocation did not reach network")
        wallpapers = self.data / "wallpapers"
        wallpapers.rename(self.data / "wallpapers-original")
        wallpapers.mkdir()

        second_fetch = mock.Mock(side_effect=AssertionError("network called while lock held"))
        second_decoder = mock.Mock(side_effect=AssertionError("decoder called while lock held"))
        with self.assertRaisesRegex(RuntimeError, "another refill is running"):
            refill.acquire(self.data, second_fetch, second_decoder)
        second_fetch.assert_not_called()
        second_decoder.assert_not_called()

        release_fetch.set()
        first.join(timeout=5)
        self.assertFalse(first.is_alive(), "first invocation did not finish")
        self.assertEqual(len(first_errors), 1)
        self.assertIsInstance(first_errors[0], ValueError)
        self.assertEqual(calls, [refill.API_URL, "https://www.bing.com/th?id=OHR.TestImage_UHD.jpg"])

        # Closing on the error path releases the kernel-owned namespace name.
        self.assertEqual(refill.acquire(self.data, fake_fetch, mock.Mock()).read_bytes(),
                         b"\xff\xd8\xfffake-image")

    def test_parent_symlink_is_rejected(self):
        real = Path(self.temp.name) / "real"
        real.mkdir()
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(OSError):
            refill.acquire(alias, fake_fetch, mock.Mock())

    def test_full_pool_fails_closed_without_deleting_or_manifest_mutation(self):
        self.pool.mkdir(parents=True)
        names = [f"bing-refill-202601{i:02}.jpg" for i in range(1, refill.KEEP + 1)]
        for name in names:
            (self.pool / name).write_bytes(b"old")
        before = {p.name: p.read_bytes() for p in self.pool.iterdir()}
        with self.assertRaises(RuntimeError):
            refill.acquire(self.data, fake_fetch, mock.Mock())
        self.assertEqual({p.name: p.read_bytes() for p in self.pool.iterdir()}, before)

    def test_dimension_ceiling_and_decoder_dependency_failure(self):
        with mock.patch.object(refill.subprocess, "run", return_value=mock.Mock(stdout="20000 100")):
            with self.assertRaises(ValueError):
                refill.decode_image(0)
        with mock.patch.object(refill.subprocess, "run", side_effect=FileNotFoundError("identify")):
            with self.assertRaises(FileNotFoundError):
                refill.decode_image(0)
        with mock.patch.object(refill.subprocess, "run", return_value=mock.Mock(stdout="8000 5000")) as run:
            refill.decode_image(0)
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertIn("40MP", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
