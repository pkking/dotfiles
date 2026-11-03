"""Offline fixtures for PR readiness screening; no GitHub credentials or calls."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pr_intake.py"
spec = importlib.util.spec_from_file_location("pr_intake", SCRIPT)
intake = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(intake)

BODY = """## Problem
The existing CI only prints a GitHub event and cannot protect maintainers from invalid changes.

## Acceptance criteria
All proposed changes run automated tests, emit an exact-commit evidence report, and fail on regressions.

## Evidence
Ran python3 -B -m unittest discover -s tests -p test_*.py and checked the resulting CI receipt.

## Risks and limitations
Offline checks do not establish live Wayland behavior; deployment and visual validation remain manual.
"""


def event(*, body: str = BODY, title: str = "ci: enforce verifiable PR quality", draft: bool = False) -> dict:
    return {"number": 42, "pull_request": {
        "number": 42, "title": title, "body": body, "draft": draft,
        "head": {"sha": "a" * 40},
    }}


class PullRequestIntakeTests(unittest.TestCase):
    def test_complete_ready_pr_is_admitted(self) -> None:
        receipt = intake.evaluate(event())
        self.assertTrue(receipt["pass"], receipt["errors"])
        self.assertTrue(receipt["ready_for_review"])
        self.assertEqual(receipt["head_sha"], "a" * 40)

    def test_template_only_or_empty_pr_is_rejected(self) -> None:
        for body in ("", "## Problem\n<!-- describe -->\n## Acceptance criteria\n<!-- criteria -->\n"
                        "## Evidence\n<!-- tests -->\n## Risks and limitations\n<!-- risks -->"):
            with self.subTest(body=body):
                self.assertFalse(intake.evaluate(event(body=body))["pass"])

    def test_missing_evidence_is_a_failure(self) -> None:
        body = BODY.replace(
            "Ran python3 -B -m unittest discover -s tests -p test_*.py and checked the resulting CI receipt.",
            "TODO",
        )
        result = intake.evaluate(event(body=body))
        self.assertFalse(result["pass"])
        self.assertIn("evidence", "\n".join(result["errors"]))

    def test_missing_acceptance_is_a_failure(self) -> None:
        body = BODY.replace("All proposed changes run automated tests, emit an exact-commit evidence report, and fail on regressions.", "")
        self.assertFalse(intake.evaluate(event(body=body))["pass"])

    def test_draft_can_iterate_without_being_review_ready(self) -> None:
        result = intake.evaluate(event(body="", title="WIP", draft=True))
        self.assertTrue(result["pass"])
        self.assertFalse(result["ready_for_review"])
        self.assertTrue(result["errors"])

    def test_non_pr_event_fails_closed(self) -> None:
        self.assertFalse(intake.evaluate({"issue": {"title": "Not a PR"}})["pass"])

    def test_chinese_section_headings_are_supported(self) -> None:
        body = (BODY.replace("## Problem", "## 问题")
                .replace("## Acceptance criteria", "## 验收标准")
                .replace("## Evidence", "## 测试证据")
                .replace("## Risks and limitations", "## 风险与限制"))
        self.assertTrue(intake.evaluate(event(body=body))["pass"])


if __name__ == "__main__":
    unittest.main()
