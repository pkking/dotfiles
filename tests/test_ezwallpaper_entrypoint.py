"""Offline contract tests for the pinned ezwallpaper command alias."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PIN = "4e72605fe788f1c1da1cb9aeba103353df547838"
ALIAS_SOURCE = ROOT / "dotfiles/dot_local/bin/symlink_ezwallpaper"
INTEGRATION = ROOT / "dotfiles/dot_config/ezwallpaper/integration.json.tmpl"
PLANNER = ROOT / "dotfiles/dot_local/bin/executable_ezwallpaper-plan.py"
SERVICE = ROOT / "dotfiles/dot_config/systemd/user/ezwallpaper-rotate.service"
DOC = ROOT / "docs/ezwallpaper-rotation-b.md"


class PinnedEntrypointTests(unittest.TestCase):
    """Check source mapping, relative resolution and fail-closed service gate."""

    def test_chezmoi_maps_alias_to_stable_entrypoint(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            result = subprocess.run(
                [
                    "chezmoi", "--source", str(ROOT),
                    "--destination", str(home), "--source-path", "target-path",
                    "dotfiles/dot_local/bin/symlink_ezwallpaper",
                ],
                text=True, capture_output=True, check=False, timeout=10,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                Path(result.stdout.strip()), home / ".local/bin/ezwallpaper"
            )

    def test_relative_alias_forwards_exact_argv_and_exit_status(self):
        relative_target = ALIAS_SOURCE.read_text(encoding="utf-8").strip()
        self.assertEqual(
            relative_target,
            f"../lib/ezwallpaper/{PIN}/bin/ezwallpaper",
        )
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            target = home / ".local/lib/ezwallpaper" / PIN / "bin/ezwallpaper"
            target.parent.mkdir(parents=True)
            log = home / "argv.json"
            target.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "open(os.environ['MOCK_LOG'], 'w', encoding='utf-8').write(\n"
                "    json.dumps(sys.argv[1:]))\n"
                "raise SystemExit(int(os.environ['MOCK_EXIT']))\n",
                encoding="utf-8",
            )
            target.chmod(0o755)
            entrypoint = home / ".local/bin/ezwallpaper"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.symlink_to(relative_target)
            self.assertEqual(entrypoint.resolve(strict=True), target)
            args = ["rotate", "next", "space and 'quotes'", "semi;colon", "*", ""]
            env = {
                **os.environ,
                "HOME": str(home),
                "MOCK_LOG": str(log),
                "MOCK_EXIT": "23",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                [str(entrypoint), *args], env=env, check=False, timeout=10
            )
            self.assertEqual(result.returncode, 23)
            self.assertEqual(json.loads(log.read_text(encoding="utf-8")), args)

    def test_alias_missing_or_nonexecutable_fails_test_x(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            target = home / ".local/lib/ezwallpaper" / PIN / "bin/ezwallpaper"
            target.parent.mkdir(parents=True)
            entrypoint = home / ".local/bin/ezwallpaper"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.symlink_to(f"../lib/ezwallpaper/{PIN}/bin/ezwallpaper")

            def test_x():
                return subprocess.run(
                    ["/usr/bin/test", "-x", str(entrypoint)],
                    check=False, timeout=10,
                ).returncode

            self.assertEqual(
                test_x(), 1, "absent target must fail executable check"
            )
            target.write_text("fixture only\n", encoding="utf-8")
            target.chmod(0o644)
            self.assertEqual(
                test_x(), 1, "non-executable target must fail check"
            )

    def test_pin_contract_and_unit_preflight_order(self):
        integration = INTEGRATION.read_text(encoding="utf-8")
        planner = PLANNER.read_text(encoding="utf-8")
        self.assertIn(
            f".local/lib/ezwallpaper/{PIN}/bin/ezwallpaper", integration
        )
        self.assertIn(f'PIN = "{PIN}"', planner)
        self.assertEqual(integration.count(PIN), 1)
        self.assertEqual(planner.count(PIN), 1)

        lines = SERVICE.read_text(encoding="utf-8").splitlines()
        start = next(
            i for i, line in enumerate(lines)
            if line.startswith("ExecStartPre=")
        )
        self.assertEqual(
            lines[start],
            "ExecStartPre=/usr/bin/test -x %h/.local/bin/ezwallpaper",
        )
        self.assertEqual(
            lines[start + 1],
            "ExecStartPre=%h/.local/bin/ezwallpaper-rotation-preflight.py",
        )
        command = next(line for line in lines if line.startswith("ExecStart="))
        self.assertNotIn("--force", command)
        self.assertNotIn("curl", command)
        self.assertNotIn("wget", command)
        self.assertNotIn("enable", command)
        doc = DOC.read_text(encoding="utf-8")
        for expected in (
            "does not install the target", "verify its hash",
            "fails\nclosed", "file/type conflict",
            "does not change the current runtime",
        ):
            self.assertIn(expected, doc)


if __name__ == "__main__":
    unittest.main()
