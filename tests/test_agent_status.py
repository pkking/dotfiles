"""Mock-/proc tests for the privacy-preserving agent status collector."""
import importlib.util
import json
import os
import tempfile
import tomllib
import unittest
import subprocess
from pathlib import Path
from unittest import mock

SCRIPT = (Path(__file__).resolve().parents[1] /
          "dotfiles/dot_local/bin/executable_agent-status-collect.py")
spec = importlib.util.spec_from_file_location("agent_status_collector", SCRIPT)
collector = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(collector)


class ProcFixture:
    def __init__(self, root: Path):
        self.root = root

    def add(self, pid: int, name: str, ppid: int = 1, *, exe: str | None = None,
            cmdline: str = "", comm_name: str | None = None) -> None:
        proc = self.root / str(pid)
        proc.mkdir()
        (proc / "comm").write_text(comm_name or name, encoding="utf-8")
        (proc / "stat").write_text(f"{pid} (fixture (comm)) S {ppid} 0 0\n",
                                    encoding="ascii")
        os.symlink(exe or f"/usr/bin/{name}", proc / "exe")
        # Deliberately contains tempting strings and credential-shaped data. The
        # collector must not need or inspect this file.
        (proc / "cmdline").write_text(cmdline, encoding="utf-8")
        (proc / "environ").write_text("API_KEY=fixture-secret", encoding="utf-8")


class AgentStatusTests(unittest.TestCase):
    def test_only_exact_supported_executable_names_are_classified(self):
        for name, expected in (("claude", "claude"), ("opencode", "opencode"),
                               ("codex", "codex"), ("agy", "agy"),
                               ("antigravity", "agy"), ("pi", "pi")):
            self.assertEqual(collector.classify(name), expected)
        for name in ("node", "python", "grep", "shell", "claude-helper", "my-claude"):
            self.assertIsNone(collector.classify(name))

    def test_mock_proc_counts_unique_same_tool_trees_and_supported_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(100, "claude")
            proc.add(101, "claude", 100)       # same CLI process tree, not double counted
            proc.add(102, "codex", 101)         # different tool in tree remains separate
            proc.add(103, "pi")
            proc.add(104, "opencode")
            proc.add(105, "agy")
            proc.add(106, "node", cmdline="claude --token fixture-secret")
            proc.add(107, "grep", cmdline="grep claude")
            proc.add(108, "python3", cmdline="agent-status-collect.py --token fixture-secret")
            proc.add(109, "node", comm_name="node", cmdline="opencode secret")
            counts = collector.scan(root, os.getuid())
        self.assertEqual(counts, {"claude": 1, "opencode": 1, "codex": 1,
                                  "agy": 1, "pi": 1})
        result = {"total": sum(counts.values()), "counts": counts}
        self.assertEqual(result["total"], 5)
        self.assertNotIn("fixture-secret", json.dumps(result))

    def test_ancestry_walks_through_unsupported_process_and_keeps_separate_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(100, "claude")
            proc.add(101, "bash", 100)
            proc.add(102, "claude", 101)
            proc.add(103, "claude")  # unrelated tree must remain distinct
            counts = collector.scan(root, os.getuid())
        self.assertEqual(counts["claude"], 2)

    def test_same_uid_ancestry_cycle_terminates_and_different_tools_remain_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(110, "claude", 111)
            proc.add(111, "claude", 110)
            proc.add(112, "codex", 110)
            counts = collector.scan(root, os.getuid())
        self.assertEqual(counts["claude"], 1)
        self.assertEqual(counts["codex"], 1)

    def test_disappearing_and_permission_denied_proc_metadata_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(200, "claude")
            proc.add(201, "pi")
            original = Path.read_text

            def read_with_races(path, *args, **kwargs):
                if path == root / "201" / "stat":
                    raise FileNotFoundError("disappeared fixture")
                if path == root / "200" / "comm":
                    raise PermissionError("inaccessible fixture")
                return original(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", read_with_races):
                counts = collector.scan(root, os.getuid())
        self.assertEqual(counts["claude"], 0)
        self.assertEqual(counts["pi"], 0)

    def test_foreign_uid_pid_is_not_counted_or_used_as_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(210, "claude")
            proc.add(211, "bash", 210)
            proc.add(212, "claude", 211)
            original = Path.stat

            def foreign_owner(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                if path == root / "211":
                    return type("Stat", (), {"st_uid": os.getuid() + 1})()
                return result

            with mock.patch.object(Path, "stat", foreign_owner):
                counts = collector.scan(root, os.getuid())
        self.assertEqual(counts["claude"], 2)

    def test_malformed_stat_is_skipped_without_claiming_it_tests_a_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = ProcFixture(root)
            proc.add(220, "claude")
            broken = root / "221"
            broken.mkdir()
            (broken / "comm").write_text("pi\\n", encoding="utf-8")
            (broken / "stat").write_text("bad stat", encoding="ascii")
            os.symlink("/usr/bin/pi", broken / "exe")
            counts = collector.scan(root, os.getuid())
        self.assertEqual(counts["claude"], 1)
        self.assertEqual(counts["pi"], 0)

    def test_process_table_enumeration_failure_is_an_error_not_false_zero(self):
        with self.assertRaises(RuntimeError):
            collector.scan(Path("/path/that/does/not/exist"), os.getuid())

    def test_toml_escaping_and_schema(self):
        self.assertEqual(collector.toml_string('a"b\\c\nd\x01'),
                         '"a\\"b\\\\c\\nd\\u0001"')
        self.assertEqual(tomllib.loads("value = " + collector.toml_string("x\x01"))["value"],
                         "x\x01")
        counts = dict.fromkeys(collector.TOOLS, 0)
        counts["pi"] = 2
        rendered = collector.render_toml(counts)
        self.assertNotIn("fixture-secret", rendered)
        data = tomllib.loads(rendered)
        self.assertEqual(data["agent_status"]["total"], 2)
        self.assertEqual(data["agent_status"]["counts"]["pi"], 2)
        self.assertEqual(data["agent_status"]["description"], "2 个运行中 · pi ×2")

    def test_atomic_output_is_private_and_failure_keeps_last_good_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "status.toml"
            target.write_text("old", encoding="utf-8")
            collector.atomic_write(target, collector.render_toml(dict.fromkeys(collector.TOOLS, 0)))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            parsed = tomllib.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(parsed["agent_status"]["total"], 0)
            old = target.read_text(encoding="utf-8")
            with mock.patch.object(collector.os, "replace", side_effect=OSError("fixture")):
                with self.assertRaises(OSError):
                    collector.atomic_write(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), old)
            self.assertEqual(list(Path(tmp).glob(".status.toml.*")), [])

    def test_update_script_honors_custom_xdg_state_home_with_spaces(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "dotfiles/dot_local/bin/executable_agent-status-update.sh").read_text()
        self.assertIn('state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}', script)
        self.assertIn('"$state_home/agent-status/status.toml"', script)
        with tempfile.TemporaryDirectory(prefix="agent status ") as tmp:
            home = Path(tmp) / "home with spaces"
            xdg = Path(tmp) / "state dir with spaces"
            home.mkdir()
            command = 'state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}; printf "%s" "$state_home/agent-status/status.toml"'
            result = subprocess.run(["bash", "-c", command], check=True, text=True,
                                    capture_output=True, env={**os.environ, "HOME": str(home),
                                                              "XDG_STATE_HOME": str(xdg)})
            self.assertEqual(result.stdout, str(xdg / "agent-status/status.toml"))

    def test_unit_timeout_and_absolute_chezmoi_exec_path_are_explicit(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "dotfiles/dot_config/systemd/user/agent-status.service").read_text()
        timer = (root / "dotfiles/dot_config/systemd/user/agent-status.timer").read_text()
        self.assertIn("TimeoutStartSec=15s", service)
        self.assertIn("ExecStart=%h/.local/bin/agent-status-update.sh", service)
        self.assertIn("OnUnitActiveSec=60s", timer)
        self.assertNotIn("WantedBy=", service)

    def test_cli_emits_aggregate_json_and_toml_only_from_fixture_proc(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proc"
            root.mkdir()
            ProcFixture(root).add(300, "claude")
            output = Path(tmp) / "status.toml"
            with mock.patch.object(collector.os, "getuid", return_value=os.getuid()):
                from contextlib import redirect_stdout
                from io import StringIO
                stdout = StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(collector.main(["--proc-root", str(root)]), 0)
                result = json.loads(stdout.getvalue())
                self.assertEqual(result["counts"]["claude"], 1)
                self.assertEqual(collector.main(["--proc-root", str(root),
                                                  "--toml-output", str(output)]), 0)
            self.assertEqual(tomllib.loads(output.read_text())["agent_status"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
