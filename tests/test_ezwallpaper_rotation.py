"""Safety tests for the opt-in hourly ezwallpaper source integration."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "dotfiles/dot_local/bin/executable_ezwallpaper-rotation-preflight.py"
SERVICE = ROOT / "dotfiles/dot_config/systemd/user/ezwallpaper-rotate.service"


class RotationSafetyTests(unittest.TestCase):
    """Exercise fail-closed preflight and service contract with test doubles."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config_home = self.home / ".config"
        self.state_home = self.home / ".local/state"
        mask_path = self.config_home / "systemd/user/wallpaper-daily.service"
        mask_path.parent.mkdir(parents=True)
        mask_path.symlink_to("/dev/null")
        self.noctalia = self.config_home / "noctalia"
        self.noctalia.mkdir(parents=True)
        self.base_config = self.noctalia / "desktop.toml"
        self.base_config.write_text(
            "[wallpaper.automation]\nenabled = false\n", encoding="utf-8"
        )
        self.pools = self.home / ".local/share/wallpapers/ezwallpaper-mocha"
        for name in ("landscape", "portrait"):
            pool = self.pools / name
            pool.mkdir(parents=True)
            (pool / "seed.png").write_bytes(b"fixture only")
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        systemctl = fake_bin / "systemctl"
        systemctl.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "operation = sys.argv[2]\n"
            "unit = next((arg for arg in sys.argv[3:] if not arg.startswith('-')), '')\n"
            "if operation == 'is-active':\n"
            "    raise SystemExit(0 if unit == os.getenv('MOCK_ACTIVE') else 3)\n"
            "if operation == 'show':\n"
            "    if unit == os.getenv('MOCK_SHOW_ERROR_UNIT'):\n"
            "        print(os.getenv('MOCK_SHOW_ERROR', 'systemd unavailable'), file=sys.stderr)\n"
            "        raise SystemExit(int(os.getenv('MOCK_SHOW_EXIT', '1')))\n"
            "    if unit == os.getenv('MOCK_SHOW_EMPTY_UNIT'):\n"
            "        raise SystemExit(0)\n"
            "    overrides = __import__('json').loads(os.getenv('MOCK_SHOW', '{}')).get(unit, {})\n"
            "    defaults = {\n"
            "        'wallpaper-daily.service': {'LoadState':'loaded','ActiveState':'failed','SubState':'failed','UnitFileState':'masked','Job':''},\n"
            "        'wallpaper-daily.timer': {'LoadState':'loaded','ActiveState':'inactive','SubState':'dead','UnitFileState':'disabled','Triggers':'wallpaper-daily.service'},\n"
            "    }\n"
            "    props = [arg.split('=',1)[1] for arg in sys.argv[3:] if arg.startswith('--property=')]\n"
            "    omitted = os.getenv('MOCK_SHOW_OMIT_PROPERTY', '') if unit == 'wallpaper-daily.service' else ''\n"
            "    duplicated = os.getenv('MOCK_SHOW_DUPLICATE_PROPERTY', '') if unit == 'wallpaper-daily.service' else ''\n"
            "    for name in props:\n"
            "        if name == omitted: continue\n"
            "        value = str(overrides.get(name, defaults.get(unit, {}).get(name, 'loaded' if name == 'LoadState' else 'inactive')))\n"
            "        print(name + '=' + value)\n"
            "        if name == duplicated: print(name + '=' + value)\n"
            "    raise SystemExit(0)\n"
            "if operation == 'is-enabled':\n"
            "    if os.getenv('MOCK_ENABLE_SLEEP'):\n"
            "        import time; time.sleep(float(os.environ['MOCK_ENABLE_SLEEP']))\n"
            "    if os.getenv('MOCK_ENABLE_OVERRIDE') == '1' and unit == os.getenv('MOCK_ENABLE_UNIT', 'wallpaper-daily.service'):\n"
            "        output = os.getenv('MOCK_ENABLE_OUTPUT', '')\n"
            "        if output: print(output)\n"
            "        error = os.getenv('MOCK_ENABLE_STDERR', '')\n"
            "        if error: print(error, file=sys.stderr)\n"
            "        raise SystemExit(int(os.getenv('MOCK_ENABLE_EXIT', '1')))\n"
            "    if unit == 'wallpaper-daily.service': print('masked'); raise SystemExit(1)\n"
            "    if unit == 'wallpaper-daily.timer': print('disabled'); raise SystemExit(1)\n"
            "    enabled = unit == os.getenv('MOCK_ENABLED')\n"
            "    print('enabled' if enabled else 'disabled')\n"
            "    raise SystemExit(0 if enabled else 1)\n"
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )
        systemctl.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.config_home),
            XDG_STATE_HOME=str(self.state_home),
            PATH=f"{fake_bin}:{os.environ['PATH']}",
            WAYLAND_DISPLAY="wayland-test",
            XDG_RUNTIME_DIR=str(self.home / "runtime"),
            DBUS_SESSION_BUS_ADDRESS="unix:path=/test/bus",
            MOCK_ACTIVE="",
            MOCK_ENABLED="",
            MOCK_ENABLE_OVERRIDE="0",
        )

    def preflight(self, env=None):
        return subprocess.run(
            [sys.executable, str(PREFLIGHT)],
            text=True,
            capture_output=True,
            env=env or self.env,
            check=False,
            timeout=10,
        )

    def test_preflight_accepts_disabled_automation_and_inactive_conflicts(self):
        result = self.preflight()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("safe to attempt", result.stdout)

    def test_is_enabled_requires_explicit_safe_state_and_matching_exit(self):
        cases = (
            ("", "1", "", False),  # historical bug: ambiguous empty output
            ("disabled", "1", "systemd unavailable", False),
            ("disabled", "0", "", False),  # conflicting exit/state
            ("unknown", "1", "", False),
            ("not-found", "4", "", True),
            ("disabled", "1", "", True),
            ("static", "2", "", False),
            ("indirect", "3", "", False),
            ("generated", "0", "", False),
            ("enabled", "0", "", False),
        )
        for output, exit_code, stderr, accepted in cases:
            with self.subTest(output=output, exit_code=exit_code, stderr=stderr):
                env = self.env.copy()
                env.update(MOCK_ENABLE_OVERRIDE="1", MOCK_ENABLE_UNIT="wallpaper-hourly.timer",
                           MOCK_ENABLE_OUTPUT=output, MOCK_ENABLE_EXIT=exit_code,
                           MOCK_ENABLE_STDERR=stderr)
                result = self.preflight(env)
                self.assertEqual(result.returncode == 0, accepted, result.stderr)

    def test_daily_service_requires_persistent_mask_and_idle_disabled_timer(self):
        for active_state, sub_state, load_state in (
            ("inactive", "dead", "masked"), ("failed", "failed", "loaded")
        ):
            with self.subTest(service=(active_state, sub_state, load_state)):
                env = self.env.copy()
                env["MOCK_SHOW"] = json.dumps({
                    "wallpaper-daily.service": {
                        "LoadState": load_state, "ActiveState": active_state,
                        "SubState": sub_state,
                    }
                })
                result = self.preflight(env)
                self.assertEqual(result.returncode, 0, result.stderr)

        cases = (
            ({"wallpaper-daily.service": {"UnitFileState": "static"}}, "static is refused"),
            ({"wallpaper-daily.service": {"UnitFileState": "masked-runtime"}}, "runtime mask refused"),
            ({"wallpaper-daily.service": {"ActiveState": "active", "SubState": "running"}}, "active service"),
            ({"wallpaper-daily.service": {"Job": "42"}}, "queued start"),
            ({"wallpaper-daily.service": {"Job": "0"}}, "nonempty zero is not the observed no-job encoding"),
            ({"wallpaper-daily.timer": {"ActiveState": "active", "SubState": "waiting"}}, "active timer"),
            ({"wallpaper-daily.timer": {"UnitFileState": "enabled"}}, "enabled timer"),
            ({"wallpaper-daily.timer": {"UnitFileState": "masked"}}, "masked timer cannot replace service mask"),
            ({"wallpaper-daily.timer": {"LoadState": "not-found"}}, "missing timer"),
        )
        for overrides, label in cases:
            with self.subTest(label=label):
                env = self.env.copy()
                env["MOCK_SHOW"] = json.dumps(overrides)
                result = self.preflight(env)
                self.assertNotEqual(result.returncode, 0, label)

        env = self.env.copy()
        env.update(MOCK_ENABLE_OVERRIDE="1", MOCK_ENABLE_UNIT="wallpaper-daily.service",
                   MOCK_ENABLE_OUTPUT="masked", MOCK_ENABLE_EXIT="0")
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0, "contradictory is-enabled rc")

        env = self.env.copy()
        env.update(MOCK_ENABLE_OVERRIDE="1", MOCK_ENABLE_UNIT="wallpaper-daily.service",
                   MOCK_ENABLE_OUTPUT="masked-runtime", MOCK_ENABLE_EXIT="1")
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0, "runtime mask")

        # systemctl show emits Job= for a present property with no queued job.
        env = self.env.copy()
        env["MOCK_SHOW"] = json.dumps({"wallpaper-daily.service": {"Job": ""}})
        result = self.preflight(env)
        self.assertEqual(result.returncode, 0, result.stderr)

        # The parser must preserve empty values without treating omission as empty.
        env = self.env.copy()
        env["MOCK_SHOW_OMIT_PROPERTY"] = "Job"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0, "missing Job property")
        self.assertIn("incomplete systemd properties", result.stderr)

        env = self.env.copy()
        env["MOCK_SHOW_DUPLICATE_PROPERTY"] = "Job"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0, "duplicate Job property")
        self.assertIn("unexpected or duplicate systemd property", result.stderr)

        env = self.env.copy()
        env["MOCK_SHOW_EMPTY_UNIT"] = "wallpaper-daily.service"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot establish systemd properties", result.stderr)

        env = self.env.copy()
        env["MOCK_SHOW_ERROR_UNIT"] = "wallpaper-daily.timer"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot establish systemd properties", result.stderr)

        env = self.env.copy()
        env["MOCK_ACTIVE"] = "wallpaper-daily.service"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting unit is active", result.stderr)

        env = self.env.copy()
        env["MOCK_ENABLE_OVERRIDE"] = "1"
        env["MOCK_ENABLE_OUTPUT"] = "masked"
        env["MOCK_ENABLE_EXIT"] = "1"
        mask_path = self.config_home / "systemd/user/wallpaper-daily.service"
        mask_path.unlink()
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0, "missing persistent user mask link")

    def test_other_legacy_units_cannot_use_mask_exception(self):
        env = self.env.copy()
        env["MOCK_ENABLE_OVERRIDE"] = "1"
        env["MOCK_ENABLE_OUTPUT"] = "masked"
        env["MOCK_ENABLE_EXIT"] = "1"
        env["MOCK_ENABLE_OVERRIDE"] = "1"
        env["MOCK_ENABLE_UNIT"] = "beautify-scene-follow.timer"
        env["MOCK_ENABLE_OUTPUT"] = "masked"
        env["MOCK_ENABLE_EXIT"] = "1"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot establish enablement", result.stderr)

    def test_is_enabled_timeout_fails_closed(self):
        env = self.env.copy()
        env["MOCK_ENABLE_SLEEP"] = "6"
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot inspect user systemd state", result.stderr)

    def test_preflight_rejects_enabled_base_or_gui_automation(self):
        self.base_config.write_text(
            "[wallpaper.automation]\nenabled = true\n", encoding="utf-8"
        )
        result = self.preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("automation is enabled", result.stderr)

        self.base_config.write_text(
            "[wallpaper.automation]\nenabled = false\n", encoding="utf-8"
        )
        override = self.state_home / "noctalia/settings.toml"
        override.parent.mkdir(parents=True)
        override.write_text(
            "[wallpaper.automation]\nenabled = true\n", encoding="utf-8"
        )
        result = self.preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GUI override enables automation", result.stderr)

    def test_preflight_rejects_conflicts_missing_graphics_and_invalid_pools(self):
        for variable, unit in (
            ("MOCK_ACTIVE", "wallpaper-daily.timer"),
            ("MOCK_ENABLED", "beautify-scene-follow.timer"),
            ("MOCK_ACTIVE", "ezwallpaper-rotation.service"),
            ("MOCK_ENABLED", "ezwallpaper-rotation.timer"),
        ):
            env = self.env.copy()
            env[variable] = unit
            result = self.preflight(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflicting unit", result.stderr)

        env = self.env.copy()
        env.pop("WAYLAND_DISPLAY")
        result = self.preflight(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("graphical session environment missing", result.stderr)

        (self.pools / "landscape").rename(self.pools / "landscape-real")
        (self.pools / "landscape").symlink_to(self.pools / "landscape-real")
        result = self.preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("real directory", result.stderr)

        (self.pools / "landscape").unlink()
        (self.pools / "landscape-real").rename(self.pools / "landscape")
        target = self.pools / "portrait" / "linked.png"
        target.symlink_to(self.pools / "portrait" / "seed.png")
        result = self.preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported symlinks", result.stderr)

    def test_service_runs_mock_binary_with_apply_but_never_force(self):
        lines = SERVICE.read_text(encoding="utf-8").splitlines()
        exec_line = next(line for line in lines if line.startswith("ExecStart="))
        command = shlex.split(exec_line.removeprefix("ExecStart="))
        self.assertEqual(command[0], "/usr/bin/flock")
        pin_index = next(
            i for i, item in enumerate(command)
            if item.endswith("/bin/ezwallpaper")
        )
        self.assertEqual(
            command[pin_index + 1:pin_index + 4],
            ["rotate", "next", "--profile"],
        )
        self.assertIn("--apply", command)
        self.assertNotIn("--force", command)

        log = self.home / "mock-binary-argv.json"
        fake_binary = self.home / "mock-ezwallpaper"
        fake_binary.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "open(os.environ['MOCK_BINARY_LOG'], 'w').write(json.dumps(sys.argv[1:]))\n"
            "raise SystemExit(int(os.getenv('MOCK_BINARY_EXIT', '0')))\n",
            encoding="utf-8",
        )
        fake_binary.chmod(0o755)
        command[pin_index] = str(fake_binary)
        command = [
            item.replace("%h", str(self.home)).replace(
                "%t", str(self.home / "runtime")
            ) for item in command
        ]
        (self.home / "runtime").mkdir()
        self.env["MOCK_BINARY_LOG"] = str(log)
        result = subprocess.run(
            command, text=True, capture_output=True, env=self.env,
            check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(log.read_text(encoding="utf-8"))
        self.assertEqual(args[:3], ["rotate", "next", "--profile"])
        self.assertIn("--apply", args)
        self.assertNotIn("--force", args)
        self.assertEqual(args[args.index("--profile") + 1],
                         str(self.home / ".config/ezwallpaper/rotation-profile.json"))

        self.env["MOCK_BINARY_EXIT"] = "17"
        failed = subprocess.run(
            command, text=True, capture_output=True, env=self.env,
            check=False, timeout=10,
        )
        self.assertEqual(failed.returncode, 17)


if __name__ == "__main__":
    unittest.main()
