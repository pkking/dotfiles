"""Public behavior tests for the ezwallpaper policy planner."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "dotfiles/dot_local/bin/executable_ezwallpaper-plan.py"
PIN = "5f11267361aec1b4f847e24169701d0dd2e39f66"


def base_config(binary: str | None = None) -> dict[str, object]:
    """Return a valid integration configuration."""
    return {
        "schema_version": 1,
        "binary": binary or (
            f"{Path.home()}/.local/lib/ezwallpaper/{PIN}/bin/ezwallpaper"
        ),
        "interval_seconds": 1800,
        "pool_capacity_bytes": 500000000,
        "provider": {"name": "wallhaven", "purity": "sfw", "query": "nature"},
        "retention": {"mode": "capacity", "on_full": "stop"},
        "outputs": {
            "DP-1": {"pool": "~/.local/share/ezwallpaper/pools/landscape"},
            "HDMI-A-1": {"pool": "~/.local/share/ezwallpaper/pools/portrait"},
        },
    }


class PlannerCliTests(unittest.TestCase):
    """Exercise the public CLI boundary in isolated subprocesses."""

    def run_cli(
        self,
        config: dict[str, object],
        *args: str,
        home: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the CLI with a temporary config and optional isolated HOME."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            env = os.environ.copy()
            if home:
                env["HOME"] = str(home)
            return subprocess.run(
                [
                    sys.executable, str(CLI), "--config", str(path),
                    "--json", *args,
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
                timeout=10,
            )

    def test_valid_config_is_blocked_and_does_not_spawn_or_create_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            binary = home / ".local/lib/ezwallpaper" / PIN / "bin/ezwallpaper"
            config = base_config(str(binary))
            result = self.run_cli(config, home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["readiness"], "blocked")
            self.assertEqual(plan["interval_seconds"], 1800)
            self.assertEqual(plan["pool_capacity_bytes"], 500000000)
            self.assertEqual(
                plan["retention"], {"mode": "capacity", "on_full": "stop"}
            )
            self.assertFalse(plan["external_process_started"])
            self.assertFalse(binary.exists())
            self.assertFalse((home / ".local/share/ezwallpaper").exists())
            self.assertIn("retention_gc", plan["unsupported_capabilities"])
            self.assertEqual(
                set(plan["upstream_gaps"]),
                {
                    "schedule_idempotency", "retention_budget",
                    "streaming_download_limit",
                },
            )

    def test_interval_accepts_boundaries_and_rejects_invalid_values(self):
        for value in (1, 1799, 3601):
            with self.subTest(value=value):
                self.assertEqual(
                    self.run_cli(
                        {**base_config(), "interval_seconds": value}
                    ).returncode,
                    0,
                )
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                result = self.run_cli(
                    {**base_config(), "interval_seconds": value}
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("interval_seconds", result.stderr)

    def test_capacity_retention_accepts_only_supported_full_policies(self):
        for policy in ("stop", "delete_oldest"):
            config = base_config()
            config["retention"] = {"mode": "capacity", "on_full": policy}
            self.assertEqual(self.run_cli(config).returncode, 0)
        config = base_config()
        config["retention"] = {"mode": "capacity", "on_full": "ignore"}
        self.assertNotEqual(self.run_cli(config).returncode, 0)

    def test_capacity_budget_rejects_invalid_values(self):
        for value in (0, -1, True, 1.5, "500000000"):
            with self.subTest(value=value):
                config = {**base_config(), "pool_capacity_bytes": value}
                result = self.run_cli(config)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("pool_capacity_bytes", result.stderr)

    def test_time_mode_requires_age_and_capacity_upper_bound(self):
        valid = base_config()
        valid["retention"] = {
            "mode": "time", "on_full": "delete_oldest",
            "max_age_seconds": 86400,
        }
        result = self.run_cli(valid)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["retention"]["max_age_seconds"], 86400
        )
        missing_capacity = base_config()
        del missing_capacity["pool_capacity_bytes"]
        missing_capacity["retention"] = {
            "mode": "time", "on_full": "stop", "max_age_seconds": 60,
        }
        self.assertNotEqual(self.run_cli(missing_capacity).returncode, 0)
        invalid = (
            {"mode": "time", "on_full": "stop"},
            {"mode": "time", "on_full": "stop", "max_age_seconds": True},
            {
                "mode": "time", "on_full": "stop", "max_age_seconds": 60,
                "extra": 1,
            },
        )
        for retention in invalid:
            config = base_config()
            config["retention"] = retention
            self.assertNotEqual(self.run_cli(config).returncode, 0)

    def test_pool_paths_must_be_disjoint_and_stay_under_home(self):
        invalid = (
            "~", "~/..", "~/.local/share/ezwallpaper/pools/landscape/child",
        )
        for pool in invalid:
            config = base_config()
            config["outputs"]["HDMI-A-1"]["pool"] = pool
            self.assertNotEqual(self.run_cli(config).returncode, 0)

    def test_unknown_keys_are_rejected(self):
        config = base_config()
        config["unexpected"] = True
        self.assertNotEqual(self.run_cli(config).returncode, 0)

    def test_provider_uses_wallhaven_query_not_categories(self):
        config = base_config()
        self.assertEqual(self.run_cli(config).returncode, 0)
        config["provider"] = {
            "name": "wallhaven", "purity": "sfw", "categories": "nature",
        }
        self.assertNotEqual(self.run_cli(config).returncode, 0)

    def _write_fake_binary(self, path: Path) -> None:
        """Create a fake pinned executable that records its CLI seam."""
        source = '''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
open(os.environ["CALL_LOG"], "w").write(json.dumps(args))
profile = args[args.index("--profile") + 1]
open(os.environ["PROFILE_LOG"], "w").write(open(profile).read())
if os.environ.get("FAKE_EXIT") != "0":
    sys.exit(int(os.environ["FAKE_EXIT"]))
mode = os.environ.get("FAKE_RESULT")
if mode == "timeout":
    time.sleep(35)
if mode == "invalid":
    print("not json")
    sys.exit(0)
root = os.environ["POOL_ROOT"]
outputs = []
for name, directory in (("DP-1", "landscape"), ("HDMI-A-1", "portrait")):
    outputs.append({
        "output": name, "decision": "select",
        "path": os.path.join(root, directory, "image.jpg"),
        "content_id": "sha256:" + name, "epoch": 1,
        "applied_path_observed": mode == "applied",
        "visually_verified": mode == "verified",
        "reason": "preview_not_applied",
    })
data = {"schema_version": 1, "outputs": outputs}
if mode == "schema":
    data["schema_version"] = 2
if mode == "duplicate":
    data["outputs"][1]["output"] = "DP-1"
if mode == "wrong":
    data["outputs"][1]["output"] = "WRONG"
if mode == "missing":
    data["outputs"].pop()
if mode == "outside":
    data["outputs"][0]["path"] = "/tmp/outside.jpg"
print(json.dumps(data))
'''
        path.write_text(source, encoding="utf-8")
        path.chmod(0o755)

    def test_preview_uses_temporary_files_and_is_offline(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            binary = home / ".local/lib/ezwallpaper" / PIN / "bin/ezwallpaper"
            binary.parent.mkdir(parents=True)
            self._write_fake_binary(binary)
            pools = home / ".local/share/ezwallpaper/pools"
            for name in ("landscape", "portrait"):
                (pools / name).mkdir(parents=True)
            config = base_config(str(binary))
            config_file = home / "config.json"
            config_file.write_text(json.dumps(config), encoding="utf-8")
            call_log = home / "calls.json"
            env = os.environ.copy()
            env.update(
                HOME=str(home), CALL_LOG=str(call_log), POOL_ROOT=str(pools),
                PROFILE_LOG=str(home / "profile.json"),
                FAKE_RESULT="valid", FAKE_EXIT="0",
            )
            command = [
                sys.executable, str(CLI), "--config", str(config_file),
                "--preview", "--json",
            ]
            checked = subprocess.run(
                command[:4] + ["--json"],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertFalse(call_log.exists())

            result = subprocess.run(
                command, text=True, capture_output=True, env=env, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertTrue(plan["external_process_started"])
            self.assertFalse(
                plan["preview"]["outputs"][0]["visually_verified"]
            )
            args = json.loads(call_log.read_text(encoding="utf-8"))
            self.assertEqual(args[:2], ["rotate", "next"])
            self.assertIn("--dry-run", args)
            self.assertIn("--force", args)
            self.assertIn("--json", args)
            self.assertNotIn("--apply", args)
            self.assertNotIn("fetch", args)
            profile = Path(args[args.index("--profile") + 1])
            state = Path(args[args.index("--state") + 1])
            self.assertEqual(profile.parent, state.parent)
            self.assertTrue(
                profile.parent.name.startswith("ezwallpaper-preview-")
            )
            rendered_profile = json.loads(
                (home / "profile.json").read_text(encoding="utf-8")
            )
            self.assertEqual(rendered_profile["schema_version"], 1)
            self.assertEqual(rendered_profile["owner"], "ezwallpaper")
            self.assertTrue(all(
                output["recursive"] is False
                for output in rendered_profile["outputs"]
            ))
            self.assertFalse(profile.parent.exists())
            self.assertFalse((home / ".local/state/ezwallpaper").exists())

            production_state = (
                home / ".local/state/ezwallpaper/rotation-v1.json"
            )
            production_state.parent.mkdir(parents=True)
            production_state.write_text("keep", encoding="utf-8")
            failures = (
                ("nonzero", 3), ("invalid", 0), ("schema", 0),
                ("duplicate", 0), ("missing", 0), ("wrong", 0),
                ("outside", 0), ("applied", 0),
                ("verified", 0), ("timeout", 0),
            )
            for mode, exit_code in failures:
                with self.subTest(mode=mode):
                    env.update(FAKE_RESULT=mode, FAKE_EXIT=str(exit_code))
                    bad = subprocess.run(
                        command,
                        text=True,
                        capture_output=True,
                        env=env,
                        timeout=40,
                    )
                    self.assertNotEqual(bad.returncode, 0, mode)
                    self.assertNotIn("Traceback", bad.stderr)
                    self.assertEqual(
                        production_state.read_text(encoding="utf-8"), "keep"
                    )

    def test_invalid_pool_resolve_errors_are_clean_cli_diagnostics(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            config = base_config(
                f"{home}/.local/lib/ezwallpaper/{PIN}/bin/ezwallpaper"
            )
            config["outputs"]["DP-1"]["pool"] = "~/bad\u0000path"
            result = self.run_cli(config, home=home)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("ezwallpaper-plan:", result.stderr)

            (home / "loop-a").symlink_to(home / "loop-b")
            (home / "loop-b").symlink_to(home / "loop-a")
            config["outputs"]["DP-1"]["pool"] = "~/loop-a/pool"
            result = self.run_cli(config, home=home)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("ezwallpaper-plan:", result.stderr)

    def test_preview_missing_pool_fails_without_creating_it(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            config = base_config(
                f"{home}/.local/lib/ezwallpaper/{PIN}/bin/ezwallpaper"
            )
            result = self.run_cli(config, "--preview", home=home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("preview pool does not exist", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
