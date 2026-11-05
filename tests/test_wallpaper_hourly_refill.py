"""Hermetic tests for the opt-in wallpaper acquisition job."""
import importlib.util
import json
from pathlib import Path
import tempfile
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
        self.data = Path(self.temp.name)
        self.pool = self.data / "wallpapers/landscape/hourly-refill"

    def tearDown(self):
        self.temp.cleanup()

    def test_success_is_atomic_and_never_calls_renderer(self):
        decoder = mock.Mock()
        with mock.patch("subprocess.run", side_effect=AssertionError("renderer invoked")):
            result = refill.acquire(self.data, fake_fetch, decoder)
        self.assertEqual(result.read_bytes(), b"\xff\xd8\xfffake-image")
        self.assertEqual(json.loads((self.pool / ".wallpaper-hourly-refill.json").read_text()), [result.name])
        decoder.assert_called_once()
        self.assertFalse(list(self.pool.glob("*.tmp")))

    def test_decode_failure_keeps_existing_assets_and_publishes_nothing(self):
        self.pool.mkdir(parents=True)
        prior = self.pool / "unrelated.jpg"
        prior.write_bytes(b"keep")
        with self.assertRaises(RuntimeError):
            refill.acquire(self.data, fake_fetch, mock.Mock(side_effect=RuntimeError("bad image")))
        self.assertEqual(prior.read_bytes(), b"keep")
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

    def test_fetch_rejects_redirect_host_and_oversize_body(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://evil.example/image"
        response.read.return_value = b"x"
        with mock.patch.object(refill.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(ValueError):
                refill.fetch(refill.API_URL)
        response.geturl.return_value = refill.API_URL
        response.read.return_value = b"x" * 5
        with mock.patch.object(refill.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(ValueError):
                refill.fetch(refill.API_URL, limit=4)

    def test_invalid_provider_url_is_rejected(self):
        def hostile(url):
            if url == refill.API_URL:
                return b'{"images":[{"urlbase":"https://evil.example/image"}]}'
            raise AssertionError("hostile URL fetched")
        with self.assertRaises(ValueError):
            refill.acquire(self.data, hostile, mock.Mock())

    def test_manifest_retention_never_removes_unowned_files(self):
        self.pool.mkdir(parents=True)
        unrelated = self.pool / "wallhaven-user.jpg"
        unrelated.write_bytes(b"preserve")
        owned = [f"bing-refill-20260{i:04}.jpg" for i in range(1, 15)]
        for name in owned:
            (self.pool / name).write_bytes(b"owned")
        (self.pool / ".wallpaper-hourly-refill.json").write_text(json.dumps(owned))
        refill._retain(self.pool, self.pool / owned[-1])
        self.assertTrue(unrelated.exists())
        self.assertEqual(len(json.loads((self.pool / ".wallpaper-hourly-refill.json").read_text())), refill.KEEP)

    def test_nonblocking_lock_rejects_concurrent_run(self):
        lock_path = self.data / "wallpapers/.hourly-refill.lock"
        lock_path.parent.mkdir(parents=True)
        with lock_path.open("a") as lock, mock.patch.object(refill.fcntl, "flock", side_effect=BlockingIOError):
            with self.assertRaises(RuntimeError):
                refill.acquire(self.data, fake_fetch, mock.Mock())

    def test_symlink_pool_is_refused(self):
        base = self.data / "wallpapers/landscape"
        base.mkdir(parents=True)
        real = self.data / "elsewhere"
        real.mkdir()
        (base / "hourly-refill").symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            refill.acquire(self.data, fake_fetch, mock.Mock())


if __name__ == "__main__":
    unittest.main()
