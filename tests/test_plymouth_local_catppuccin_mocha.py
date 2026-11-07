"""Offline integrity checks for the vendored Catppuccin Plymouth source."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
THEME_DIR = (
    REPO_ROOT
    / "dotfiles/dot_local/share/beautify/plymouth-local-catppuccin-mocha"
)
EXPECTED_REPOSITORY = "https://github.com/catppuccin/plymouth"
EXPECTED_REVISION = "198eba2071d80e4a23b8f51a5859e8f4acf8de6c"
EXPECTED_LICENSE_HASH = "814096d2c34cc216c624738a49356f32b7237733b4f7edb0685f4e50ef5074ba"


class PlymouthThemeSourceTest(unittest.TestCase):
    """Validate attribution metadata and all source file digests offline."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest_path = THEME_DIR / "source-manifest.toml"
        cls.manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    def test_manifest_identifies_pinned_upstream_and_license(self) -> None:
        self.assertEqual(self.manifest["repository"], EXPECTED_REPOSITORY)
        self.assertEqual(self.manifest["revision"], EXPECTED_REVISION)
        self.assertEqual(self.manifest["license"], "MIT")
        self.assertEqual(self.manifest["license_sha256"], EXPECTED_LICENSE_HASH)

    def test_manifest_file_hashes_match_regular_files(self) -> None:
        files = self.manifest["files"]
        self.assertEqual(len(files), 11)
        for relative_path, expected_hash in files.items():
            with self.subTest(file=relative_path):
                path = Path(relative_path)
                self.assertFalse(path.is_absolute())
                self.assertEqual(len(path.parts), 1, "manifest path must be a basename")
                target = THEME_DIR / path
                self.assertFalse(target.is_symlink(), "manifest target must not be a symlink")
                self.assertTrue(target.is_file(), f"missing source file: {relative_path}")
                actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                self.assertEqual(actual_hash, expected_hash)

    def test_mit_notice_hash_matches_manifest(self) -> None:
        license_file = THEME_DIR / "LICENSE"
        self.assertTrue(license_file.is_file())
        actual_hash = hashlib.sha256(license_file.read_bytes()).hexdigest()
        self.assertEqual(actual_hash, self.manifest["license_sha256"])
        self.assertIn("Copyright (c) 2021 Catppuccin", license_file.read_text())
        self.assertIn("MIT License", license_file.read_text())

    def test_only_manifested_assets_and_theme_descriptor_are_present(self) -> None:
        expected = set(self.manifest["files"]) | {
            "LICENSE",
            "source-manifest.toml",
            "local-catppuccin-mocha.plymouth",
        }
        actual = {path.name for path in THEME_DIR.iterdir()}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
