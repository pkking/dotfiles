#!/usr/bin/env python3
"""Reproducible, offline, non-deploying PR validation with an evidence receipt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("python-tests", (sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v")),
    ("wallpaper-contract", (sys.executable, "-B", "scripts/test-ezwallpaper-rotation-contract.py", "-v")),
    ("doc-entrypoints", ("bash", "scripts/check-doc-entrypoints.sh")),
    ("doc-commands", (sys.executable, "-B", "scripts/check-doc-commands.py")),
    ("whitespace-and-conflicts", ("git", "diff", "--check", "HEAD^", "HEAD")),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".ci-evidence", help="Output directory")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    for name, command in CHECKS:
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, errors="replace", timeout=240,
                                    check=False)
            code = result.returncode
            log = result.stdout
        except (subprocess.TimeoutExpired, OSError) as exc:
            code, log = 124, f"{type(exc).__name__}: {exc}\n"
        elapsed = round(time.monotonic() - started, 2)
        (output / f"{name}.log").write_text(log, encoding="utf-8")
        print(f"{name}: {'PASS' if code == 0 else 'FAIL'} ({elapsed}s); {output / (name + '.log')}", flush=True)
        if code:
            print(log[-8000:], file=sys.stderr, flush=True)
        checks.append({"name": name, "command": list(command), "exit_code": code,
                       "duration_seconds": elapsed, "log": f"{name}.log"})

    tested = subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, capture_output=True,
                            text=True, check=False).stdout.strip()
    receipt = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.getenv("GITHUB_REPOSITORY", "local"),
        "pr_head_sha": os.getenv("PR_HEAD_SHA", ""),
        "tested_checkout_sha": tested,
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", ""),
        "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
        "pass": all(x["exit_code"] == 0 for x in checks),
        "checks": checks,
        "limitations": ["offline checks only", "no desktop session or hardware acceptance", "no chezmoi apply"],
    }
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# PR quality evidence", "", f"Result: **{'PASS' if receipt['pass'] else 'FAIL'}**",
             f"PR head: `{receipt['pr_head_sha'] or 'local'}`", f"Tested checkout: `{tested}`",
             f"Run: `{receipt['workflow_run_id'] or 'local'}` (attempt {receipt['workflow_run_attempt'] or 'local'})",
             "", "| Check | Result | Duration | Log |", "|---|---|---:|---|"]
    for x in checks:
        lines.append(f"| {x['name']} | {'PASS' if x['exit_code'] == 0 else 'FAIL'} | {x['duration_seconds']}s | `{x['log']}` |")
    lines += ["", "**Not established:** live desktop behavior, visual appearance, real device activation, or `chezmoi apply`.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
