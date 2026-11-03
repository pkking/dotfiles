#!/usr/bin/env python3
"""Export a bounded, reviewable agent patch; never publish CI or secret changes."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ALLOWED = ("dotfiles/", "docs/", "scripts/", "tests/")
EXACT = {"README.md"}
PROTECTED = {"scripts/ci_quality.py", "scripts/agent_patch_policy.py"}
MAX_PATCH_BYTES = 1_000_000
MAX_FILES = 30


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(("git", *args), capture_output=True, check=check)


def validate_names(names: list[str]) -> None:
    if not names or len(names) > MAX_FILES:
        raise ValueError(f"Expected 1..{MAX_FILES} changed files; got {len(names)}")
    for name in names:
        parts = Path(name).parts
        if (name in PROTECTED or not (name in EXACT or name.startswith(ALLOWED))
                or name.endswith(".age") or any(p.startswith(("encrypted_", "private_")) for p in parts)
                or any(p in (".git", ".github", "..") for p in parts)):
            raise ValueError(f"Agent is not permitted to change {name!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    # intent-to-add makes new regular files visible in git diff, without staging content.
    run("add", "-N", "--", ".")
    changed = run("diff", "--name-only", "-z", "HEAD").stdout
    names = [s.decode("utf-8", errors="surrogateescape") for s in changed.split(b"\0") if s]
    validate_names(names)
    # A symlink might install actions on the user's workstation; require human review.
    modes = run("diff", "--summary", "HEAD").stdout.decode("utf-8", errors="replace")
    if "mode 120000" in modes:
        raise ValueError("Agent-created symlinks are disallowed")
    check = run("diff", "--check", "HEAD", check=False)
    if check.returncode:
        raise ValueError(check.stdout.decode(errors="replace") + check.stderr.decode(errors="replace"))
    patch = run("diff", "--binary", "HEAD").stdout
    if not patch or len(patch) > MAX_PATCH_BYTES:
        raise ValueError(f"Expected a nonempty patch <= {MAX_PATCH_BYTES} bytes")
    Path(args.output).write_bytes(patch)
    print(f"Exported {len(names)} files, {len(patch)} bytes: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(1) from exc
