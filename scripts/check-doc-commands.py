#!/usr/bin/env python3
"""Check command documentation completeness and correctness.

For this chezmoi/mise repo:
- `mise run <task>` in docs → task must exist in mise.toml
- Task exists in mise.toml → should be documented in docs
- Referenced paths must exist
"""

import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]

DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
]

MISE_TOML = ROOT / "dotfiles" / "dot_config" / "mise.toml"

INLINE_CMD = re.compile(r"`(mise run [a-zA-Z0-9_.-]+)`")
MISE_RUN = re.compile(r"^mise run ([a-zA-Z0-9_.-]+)")


def load_mise_tasks() -> set[str]:
    """Parse mise.toml and return the set of defined task names."""
    if not MISE_TOML.exists():
        return set()

    data = tomllib.loads(MISE_TOML.read_text())
    tasks = data.get("tasks", {})
    return set(tasks.keys())


def extract_documented_tasks() -> set[str]:
    """Find all 'mise run <task>' references in docs. Returns set of task names."""
    tasks = set()
    for doc in DOCS:
        if not doc.exists():
            continue
        for line in doc.read_text().splitlines():
            # Match inline code blocks: `mise run <task>`
            for cmd in INLINE_CMD.findall(line):
                tasks.add(cmd.removeprefix("mise run ").strip())
            # Match standalone commands (e.g. in code blocks)
            m = MISE_RUN.match(line.strip())
            if m:
                tasks.add(m.group(1))
    return tasks


def check_undocumented_tasks(mise_tasks: set[str], documented: set[str]) -> list[str]:
    """Find mise tasks that exist but are not documented."""
    undocumented = mise_tasks - documented
    if undocumented:
        return [
            f"mise.toml: task '{t}' exists but is not documented in AGENTS.md/README.md"
            for t in sorted(undocumented)
        ]
    return []


def check_ghost_tasks(mise_tasks: set[str], documented: set[str]) -> list[str]:
    """Find tasks documented but don't exist in mise.toml."""
    ghosts = documented - mise_tasks
    if ghosts:
        return [
            f"docs: task '{t}' is documented but not found in mise.toml "
            f"(available: {', '.join(sorted(mise_tasks))})"
            for t in sorted(ghosts)
        ]
    return []


def check_referenced_paths() -> list[str]:
    """Check that important paths mentioned in docs actually exist."""
    errors = []
    critical_paths = [
        "dotfiles",
        "dotfiles/.chezmoiscripts",
        "dotfiles/dot_config",
    ]
    for rel in critical_paths:
        if not (ROOT / rel).exists():
            errors.append(f"Referenced path '{rel}' does not exist")
    return errors


def main():
    mise_tasks = load_mise_tasks()
    if not mise_tasks:
        print("WARN: Could not parse mise.toml, skipping task validation")
        return

    documented = extract_documented_tasks()
    errors = []

    # Forward: documented task must exist
    errors.extend(check_ghost_tasks(mise_tasks, documented))

    # Reverse: existing task should be documented
    errors.extend(check_undocumented_tasks(mise_tasks, documented))

    # Check critical paths
    errors.extend(check_referenced_paths())

    if errors:
        print("Documentation drift detected:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("doc command check passed")


if __name__ == "__main__":
    main()
