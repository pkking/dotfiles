"""Offline policy and trust-boundary regression tests for the PR context gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pr_intake.py"
spec = importlib.util.spec_from_file_location("pr_intake", SCRIPT)
intake = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(intake)

BODY = """## What Problem This Solves
The previous workflow only prints GitHub events and cannot protect maintainers from low-value PRs.

## Acceptance criteria
All proposed changes run focused regression tests, emit per-commit evidence, and fail if validation fails.

## Evidence
Ran python3 -B -m unittest discover -s tests -p test_*.py: PASS. CI report linked after completion.

## Risks and limitations
Offline tests do not establish live Wayland behavior; desktop validation is manual.
"""


def event(*, body: str = BODY, title: str = "ci: enforce verifiable PR quality", draft: bool = False) -> dict:
    return {"number": 42, "pull_request": {
        "number": 42, "title": title, "body": body, "draft": draft,
        "head": {"sha": "a" * 40},
    }}


class PullRequestIntakeTests(unittest.TestCase):
    def test_complete_pr_is_admitted_but_not_approved(self) -> None:
        receipt = intake.evaluate(event())
        self.assertTrue(receipt["pass"], receipt["errors"])
        self.assertTrue(receipt["ready_for_review"])
        self.assertEqual(receipt["head_sha"], "a" * 40)
        self.assertIn("NOT proof", receipt["explanation"])

    def test_empty_or_template_only_pr_is_rejected(self) -> None:
        for body in ("", "## What Problem This Solves\n<!-- fill in -->\n## Evidence\n<!-- tests -->"):
            with self.subTest(body=body):
                self.assertFalse(intake.evaluate(event(body=body))["pass"])

    def test_missing_evidence_is_failure(self) -> None:
        body = BODY.replace("Ran python3 -B -m unittest discover -s tests -p test_*.py: PASS. CI report linked after completion.", "TODO")
        result = intake.evaluate(event(body=body))
        self.assertFalse(result["pass"])
        self.assertIn("evidence", "\n".join(result["errors"]))

    def test_future_ci_promise_is_not_evidence(self) -> None:
        body = BODY.replace("Ran python3 -B -m unittest discover -s tests -p test_*.py: PASS. CI report linked after completion.",
                            "CI will run after this PR is created; results will be added when available.")
        result = intake.evaluate(event(body=body))
        self.assertFalse(result["pass"])

    def test_acceptance_and_risk_are_advisory(self) -> None:
        b = BODY.replace("## Acceptance criteria\nAll proposed changes run focused regression tests, emit per-commit evidence, and fail if validation fails.\n\n", "")
        b = b.replace("## Risks and limitations\nOffline tests do not establish live Wayland behavior; desktop validation is manual.\n", "")
        result = intake.evaluate(event(body=b))
        self.assertTrue(result["pass"], result["errors"])
        self.assertGreaterEqual(len(result["warnings"]), 2)

    def test_draft_can_iterate_but_not_request_review(self) -> None:
        result = intake.evaluate(event(body="", title="WIP", draft=True))
        self.assertTrue(result["pass"])
        self.assertFalse(result["ready_for_review"])

    def test_non_pr_event_fails_closed(self) -> None:
        self.assertFalse(intake.evaluate({"issue": {"title": "not a PR"}})["pass"])

    def test_chinese_section_headings(self) -> None:
        b = BODY.replace("## What Problem This Solves", "## 问题").replace("## Evidence", "## 测试证据")
        self.assertTrue(intake.evaluate(event(body=b))["pass"])

    def test_maintenance_only_missing_link_warns(self) -> None:
        result = intake.evaluate(event())
        self.assertTrue(any("Maintenance-only" in w for w in result["warnings"]))

    def test_workflow_reads_only_trusted_base_revision(self) -> None:
        workflow = (ROOT / ".github/workflows/pr-context-evidence.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("ref: ${{ github.workflow_sha }}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("pull_request.head.sha }}\n          persist-credentials", workflow)
        self.assertIn("statuses: write", workflow)
        self.assertNotIn("pull_request.head.ref", workflow)


if __name__ == "__main__":
    unittest.main()
