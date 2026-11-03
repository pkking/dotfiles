"""Regression checks for credential separation in agent development workflow."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/agent-implement.yml"


class AgentWorkflowIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  generate:\n", text)
        self.assertIn("\n  verify:\n", text)
        self.assertIn("\n  publish:\n", text)
        self.generate = text.split("\n  generate:\n", 1)[1].split("\n  verify:\n", 1)[0]
        self.verify = text.split("\n  verify:\n", 1)[1].split("\n  publish:\n", 1)[0]
        self.publish = text.split("\n  publish:\n", 1)[1]

    def test_privileged_credentials_only_in_clean_publisher(self) -> None:
        for job in (self.generate, self.verify):
            self.assertNotIn("AGENT_APP_PRIVATE_KEY", job)
            self.assertNotIn("AGENT_APP_ID", job)
            self.assertNotIn("create-github-app-token", job)
            self.assertNotIn("create-pull-request", job)
        self.assertIn("permissions: {}", self.verify)
        self.assertIn("permissions: {}", self.publish)
        self.assertIn("needs: [verify]", self.publish)
        self.assertIn("if: needs.verify.result == 'success'", self.publish)

    def test_verification_promotes_digest_bound_artifact(self) -> None:
        self.assertIn("agent-candidate-", self.generate)
        self.assertIn("agent-candidate-", self.verify)
        self.assertIn('python3 -B scripts/ci_quality.py', self.verify)
        self.assertIn("agent-verified-", self.verify)
        self.assertIn("sha256sum", self.verify)
        self.assertIn("steps.seal.outputs.patch_sha256", self.verify)

    def test_publisher_never_runs_agent_modified_code(self) -> None:
        self.assertIn("agent-verified-", self.publish)
        self.assertNotIn("agent-candidate-", self.publish)
        self.assertIn("needs.verify.outputs.patch_sha256", self.publish)
        self.assertIn("needs.verify.outputs.base_sha", self.publish)
        self.assertIn("sha256sum -c verified.patch.sha256", self.publish)
        self.assertIn("git apply --check", self.publish)
        self.assertIn("git config --local core.hooksPath /dev/null", self.publish)
        # Publisher may execute fixed shell commands and audited Actions; never project tests.
        for forbidden in ("scripts/ci_quality.py", "scripts/agent_patch_policy.py",
                          "python3 -B", "unittest", "pip install", "npm install",
                          "bash scripts/"):
            self.assertNotIn(forbidden, self.publish)
        self.assertLess(self.publish.index("sha256sum -c"),
                        self.publish.index("Mint short-lived publisher token"))
        self.assertLess(self.publish.index("git apply --check"),
                        self.publish.index("Mint short-lived publisher token"))
        self.assertIn("peter-evans/create-pull-request@v8", self.publish)


if __name__ == "__main__":
    unittest.main()
