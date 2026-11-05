"""Offline contract checks for the managed Noctalia desktop config."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "dotfiles/dot_config/noctalia/desktop.toml.tmpl"


class NoctaliaDesktopContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chezmoi = shutil.which("chezmoi")
        if cls.chezmoi is None:
            raise unittest.SkipTest("chezmoi is required to render the template")
        rendered = subprocess.run(
            [cls.chezmoi, "execute-template", "--init=false"],
            input=TEMPLATE.read_bytes(),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        cls.config = tomllib.loads(rendered.decode("utf-8"))
        cls.rendered_text = rendered.decode("utf-8")

    def test_wallpaper_scheduler_is_explicitly_opt_in_and_disabled_here(self) -> None:
        self.assertEqual(self.config["wallpaper"]["automation"]["enabled"], False)
        asset_guidance = (ROOT / "docs/mocha-wallpaper-assets.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("must\nremain disabled", asset_guidance)
        self.assertIn("at most one", asset_guidance)
        self.assertNotIn("users may explicitly\nset its managed `enabled` flag to true", asset_guidance)
        transitions = ["fade", "wipe", "disc", "stripes", "zoom", "honeycomb"]
        self.assertEqual(self.config["wallpaper"]["transition"], transitions)
        self.assertEqual(self.config["lockscreen"]["transition"], transitions)
        self.assertTrue(self.config["wallpaper"]["per_monitor_directories"])

    def test_builtin_theme_import_is_preserved(self) -> None:
        templates = self.config["theme"]["templates"]
        self.assertTrue(templates["enable_builtin_templates"])
        self.assertEqual(templates["builtin_ids"], ["alacritty"])

    def test_verified_lock_screen_widgets_and_exclusions(self) -> None:
        widgets = self.config["lockscreen_widgets"]["widget"]
        self.assertEqual(widgets["portrait-clock"]["settings"]["clock_style"], "analog")
        self.assertEqual(widgets["portrait-sysmon"]["settings"]["display"], "graph")
        self.assertNotIn("plugins", self.config)
        self.assertNotIn("location", self.config.get("weather", {}))
        self.assertNotIn("Shanghai", self.rendered_text)

    def test_template_paths_render_without_unexpanded_chezmoi_markers(self) -> None:
        self.assertNotIn("{{", self.rendered_text)
        self.assertNotIn("}}", self.rendered_text)
        self.assertIn(str(Path.home()), self.rendered_text)

    @unittest.skipUnless(shutil.which("noctalia"), "Noctalia validator is not installed")
    def test_installed_noctalia_validator_accepts_rendered_config(self) -> None:
        version = subprocess.run(
            ["noctalia", "--version"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if "5.2.1" not in version:
            self.skipTest(f"expected pinned Noctalia 5.2.1 validator, got {version!r}")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "desktop.toml"
            path.write_text(self.rendered_text, encoding="utf-8")
            subprocess.run(
                ["noctalia", "config", "validate", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
