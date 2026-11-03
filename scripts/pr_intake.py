#!/usr/bin/env python3
"""Read-only PR readiness policy; never executes PR content or posts GitHub comments."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

REQUIRED = {
    "problem": (r"problem|goal|summary|purpose|what.*solv|背景|目的|问题|概要", 18),
    "acceptance": (r"acceptance|验收|验证标准|完成标准", 15),
    "evidence": (r"evidence|validation|testing|tests?|proof|verified ci|验证|测试|证据", 22),
    "risks": (r"risks?|limitations?|rollback|unverified|blockers?|风险|回滚|未验证|限制|影响", 12),
}
PLACEHOLDERS = re.compile(r"\b(todo|tbd|fill in|placeholder|to be added)\b|待补充|待填写|尚未填写", re.I)
HEADINGS = re.compile(r"(?m)^#{1,6}\s+([^\n]+)\s*$")
COMMENTS = re.compile(r"<!--.*?-->", re.S)
FENCES = re.compile(r"(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$")


def sections_from(body: str) -> list[tuple[str, str]]:
    """Extract content under Markdown headings; ignore instructions in comments/code."""
    cleaned = FENCES.sub("", COMMENTS.sub("", body))
    headings = list(HEADINGS.finditer(cleaned))
    return [(match.group(1).strip().casefold(),
             cleaned[match.end(): headings[index + 1].start() if index + 1 < len(headings) else len(cleaned)].strip())
            for index, match in enumerate(headings)]


def substantive(text: str, *, min_chars: int) -> bool:
    text = re.sub(r"(?m)^\s*[-*]\s*[^:\n]{1,65}:\s*$", "", text).strip()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return len(text) >= min_chars and not PLACEHOLDERS.search(text)


def evaluate(event: dict) -> dict:
    pr = event.get("pull_request")
    errors: list[str] = []
    if not isinstance(pr, dict):
        return {"pass": False, "ready_for_review": False, "errors": ["Not a pull_request event."]}
    draft = bool(pr.get("draft"))
    title = (pr.get("title") or "").strip()
    if len(title) < 12 or len(title) > 140 or re.fullmatch(r"(wip|draft|test|fix|update|tmp)[\s:!.-]*", title, re.I):
        errors.append("Use a specific PR title describing the behavior or outcome (12–140 characters).")
    body = (pr.get("body") or "").strip()
    if len(COMMENTS.sub("", body).strip()) < 100:
        errors.append("Describe the change in the PR body (at least 100 characters).")
    sections = sections_from(body)
    for kind, (pattern, min_chars) in REQUIRED.items():
        candidates = [content for heading, content in sections if re.search(pattern, heading, re.I)]
        if not any(substantive(content, min_chars=min_chars) for content in candidates):
            errors.append(f"Add a substantive '{kind}' section (see the PR template); empty placeholders do not count.")
    # Drafts are explicitly not sent for review. A green result here means WIP is allowed,
    # NOT that the draft is ready for maintainer review or can be merged.
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_request_number": pr.get("number") or event.get("number"),
        "head_sha": (pr.get("head") or {}).get("sha", ""),
        "draft": draft,
        "ready_for_review": not draft and not errors,
        "pass": draft or not errors,
        "errors": errors,
        "explanation": ("Draft: not eligible for maintainer review." if draft else
                        "Ready for automated quality checks." if not errors else
                        "Not ready for maintainer review; correct the listed omissions."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = evaluate(json.loads(args.event_file.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = "PASS" if receipt["pass"] else "FAIL"
    print(f"PR intake: {status}; ready_for_review={receipt['ready_for_review']}; head={receipt.get('head_sha','')}")
    for error in receipt["errors"]:
        print(" - " + error)
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
