#!/usr/bin/env python3
"""Offline contract tests for the optional niri/Noctalia chezmoi rotation files.

Never loads user state, launches a process, accesses the network, or changes
any desktop. Uses only Python's standard library.
"""
from __future__ import annotations

import configparser
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "dotfiles/dot_config/ezwallpaper/rotation.json.tmpl"
SERVICE = ROOT / "dotfiles/dot_config/systemd/user/ezwallpaper-rotation.service"
TIMER = ROOT / "dotfiles/dot_config/systemd/user/ezwallpaper-rotation.timer"
DOC = ROOT / "docs/niri-noctalia.md"


def read_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


class RotationContractTests(unittest.TestCase):
    def test_profile_schema_and_real_pool_isolation(self) -> None:
        template = PROFILE.read_text(encoding="utf-8")
        self.assertEqual(template.count("{{ .chezmoi.homeDir }}"), 2)
        data = json.loads(template.replace("{{ .chezmoi.homeDir }}", "/home/test"))
        self.assertEqual((data["schema_version"], data["owner"]), (1, "ezwallpaper"))
        self.assertEqual(len(data["outputs"]), 2)
        by_name = {item["name"]: item for item in data["outputs"]}
        self.assertEqual(set(by_name), {"DP-1", "HDMI-A-1"})
        self.assertEqual(by_name["DP-1"]["dir"], "/home/test/.local/share/wallpapers/landscape")
        self.assertEqual(by_name["HDMI-A-1"]["dir"], "/home/test/.local/share/wallpapers/portrait")
        for item in by_name.values():
            self.assertEqual(set(item), {"name", "dir", "recursive", "follow_symlinks"})
            self.assertTrue(item["recursive"])
            self.assertFalse(item["follow_symlinks"])
            self.assertFalse("REPLACE_ME" in item["dir"])

    def test_service_uses_explicit_noctalia_and_no_renderer_management(self) -> None:
        unit = read_unit(SERVICE)
        self.assertEqual(unit["Service"]["Type"], "oneshot")
        self.assertEqual(unit["Service"]["NoNewPrivileges"], "true")
        command = unit["Service"]["ExecStart"]
        self.assertEqual(
            command,
            "%h/.local/bin/ezwallpaper rotate next --profile "
            "%h/.config/ezwallpaper/rotation.json "
            "--rotation-backend noctalia --apply --json",
        )
        source = SERVICE.read_text(encoding="utf-8")
        for required in (
            "test -x %h/.local/bin/ezwallpaper",
            "test -d %h/.local/share/wallpapers/landscape",
            "test -d %h/.local/share/wallpapers/portrait",
        ):
            self.assertIn(required, source)
        for forbidden in ("sudo", "pkill ", "swaybg -i", "mpvpaper ", "curl ", "wget "):
            self.assertNotIn(forbidden, command)

    def test_timer_not_automatically_installed_or_enabled(self) -> None:
        unit = read_unit(TIMER)
        self.assertEqual(unit["Timer"]["OnCalendar"], "hourly")
        self.assertEqual(unit["Timer"]["Persistent"], "true")
        self.assertEqual(unit["Timer"]["Unit"], "ezwallpaper-rotation.service")
        self.assertEqual(unit["Install"]["WantedBy"], "timers.target")
        paths = (
            ROOT / "dotfiles/dot_config/systemd/user/timers.target.wants",
            ROOT / "dotfiles/dot_config/systemd/user/symlink_timers.target.wants",
        )
        for path in paths:
            self.assertFalse(path.exists(), "do not pre-enable a user timer via chezmoi")

    def test_docs_disclose_deployment_conflicts_and_missing_refill(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        for required in (
            "wallpaper-daily",
            "wallpaper-hourly",
            "beautify-scene-follow",
            "chezmoi diff",
            "Noctalia",
            "systemctl --user enable --now ezwallpaper-rotation.timer",
            "not automatically",
            "two distinct",
        ):
            self.assertIn(required, doc)


if __name__ == "__main__":
    unittest.main()
