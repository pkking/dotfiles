#!/usr/bin/env python3
"""Barnacle-style, read-only PR context/proof screening against trusted event metadata.

No checkout of contributor code, API writes, model calls, or PR comments here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

REQUIRED = {
    "problem": (r"what problem this solves|problem|goal|summary|purpose|what.*solv|背景|目的|问题|概要", 18),
    "evidence": (r"evidence|validation|testing|tests?|proof|verified ci|验证|测试|证据", 22),
}
ADVISORY = {
    "acceptance": (r"acceptance|验收|验证标准|完成标准", 15),
    "risks": (r"risks?|limitations?|rollback|unverified|blockers?|风险|回滚|未验证|限制|影响", 12),
}
PLACEHOLDERS = re.compile(r"\b(todo|tbd|fill in|placeholder|to be added)\b|待补充|待填写|尚未填写", re.I)
HEADINGS = re.compile(r"(?m)^#{1,6}\s+([^\n]+)\s*$")
COMMENTS = re.compile(r"<!--.*?-->", re.S)
FENCES = re.compile(r"(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$")
NO_PROOF_YET = re.compile(r"\b(?:ci pending|tests? pending|will run|will test|will add|not yet tested|coming soon)\b|稍后补充|待运行|尚未测试", re.I)
EVIDENCE_TYPES = re.compile(
    r"\b(?:ran|passed|failed|observed|reproduced|screenshot|recording|artifact|"
    r"logs?|https?://[^\s)]+|pytest|unittest|pre-commit|cargo test|git diff|"
    r"manual(?:ly)?(?: checked| tested)?|test results?|output|verified)\b|"
    r"已运行|已通过|已执行|观察到|截图|录屏|日志|复现|验证结果|测试结果|命令输出|人工测试", re.I)
MAINTENANCE = re.compile(r"^(?:docs?|test|refactor|ci|build|infra|chore)(?:\([^)]*\))?\s*:", re.I)
ISSUE_LINK = re.compile(r"(?:\b(?:fixes|closes|refs|references)\s+#\d+|"
                        r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/issues/\d+)", re.I)


def sections_from(body: str) -> list[tuple[str, str]]:
    """Ignore comments and code fences before extracting authored Markdown sections."""
    cleaned = FENCES.sub("", COMMENTS.sub("", body))
    headings = list(HEADINGS.finditer(cleaned))
    return [(match.group(1).strip().casefold(),
             cleaned[match.end(): headings[index + 1].start() if index + 1 < len(headings) else len(cleaned)].strip())
            for index, match in enumerate(headings)]


def substantive(text: str, *, min_chars: int) -> bool:
    cleaned = re.sub(r"(?m)^\s*[-*]\s*[^:\n]{1,65}:\s*$", "", text).strip()
    cleaned = re.sub(r"[\s\W_]+", "", cleaned, flags=re.UNICODE)
    return len(cleaned) >= min_chars and not PLACEHOLDERS.search(text)


def select(sections: list[tuple[str, str]], pattern: str) -> list[str]:
    return [content for heading, content in sections if re.search(pattern, heading, re.I)]


def evaluate(event: dict) -> dict:
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return {"pass": False, "ready_for_review": False, "errors": ["Not a PR event."], "warnings": []}

    draft = bool(pr.get("draft"))
    title = (pr.get("title") or "").strip()
    body = (pr.get("body") or "").strip()
    sections = sections_from(body)
    errors: list[str] = []
    warnings: list[str] = []

    if len(title) < 12 or len(title) > 140 or re.fullmatch(r"(wip|draft|test|fix|update|tmp)[\s:!.-]*", title, re.I):
        errors.append("Provide a specific title that describes the change (12–140 characters).")

    for kind, (pattern, min_chars) in REQUIRED.items():
        candidates = select(sections, pattern)
        if not any(substantive(content, min_chars=min_chars) for content in candidates):
            errors.append(f"Add an authored '{kind}' section with concrete context, not an empty template.")

    proof = "\n".join(select(sections, REQUIRED["evidence"][0]))
    if substantive(proof, min_chars=REQUIRED["evidence"][1]):
        if not EVIDENCE_TYPES.search(proof):
            errors.append("Evidence must name actual validation: a test/command and result, log, artifact, screenshot, or observation.")
        if NO_PROOF_YET.search(proof) and not re.search(
            r"\b(?:ran|passed|failed|observed|reproduced|screenshot|recording|artifact|"
            r"manual(?:ly)? tested|verified)\b|已运行|已通过|已执行|观察到|截图|录屏|复现|验证结果", proof, re.I
        ):
            errors.append("Planned or pending CI alone is not completed evidence.")
    for kind, (pattern, min_chars) in ADVISORY.items():
        if not any(substantive(content, min_chars=min_chars) for content in select(sections, pattern)):
            warnings.append(f"Add '{kind}' context to help maintainers assess scope and risks.")

    if MAINTENANCE.match(title) and not ISSUE_LINK.search(body):
        warnings.append("Maintenance-only change: link an issue or explain maintainer context; routine cleanup alone is not proof of value.")

    if re.search(r"clawsweeper|autoreview|local review", body, re.I):
        warnings.append("Local/AI review is self-reported. Name the tool, reviewed base/head, coverage, outcome and unresolved findings; required CI remains separate.")

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_request_number": pr.get("number") or event.get("number"),
        "head_sha": (pr.get("head") or {}).get("sha", ""),
        "draft": draft,
        "ready_for_review": not draft and not errors,
        "pass": draft or not errors,
        "errors": errors,
        "warnings": warnings,
        "explanation": ("Draft: not offered for maintainer review." if draft else
                        "Context and evidence supplied; this is NOT proof of correctness." if not errors else
                        "Insufficient problem context/evidence; fix before maintainer review."),
        "scope": "PR metadata only; no contributor code executed, no claim of AI review",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = evaluate(json.loads(args.event_file.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PR context: {'PASS' if receipt['pass'] else 'FAIL'}; ready={receipt['ready_for_review']}; head={receipt.get('head_sha', '')}")
    for key in ("errors", "warnings"):
        for item in receipt.get(key, []):
            print(f"{key}: {item}")
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
