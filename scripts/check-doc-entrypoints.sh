#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[ -f "$ROOT/AGENTS.md" ] || fail "AGENTS.md is missing"
[ -f "$ROOT/CLAUDE.md" ] || fail "CLAUDE.md is missing"

first_non_empty_line="$(grep -v '^[[:space:]]*$' "$ROOT/CLAUDE.md" | head -n 1 || true)"

if [ "$first_non_empty_line" != "@AGENTS.md" ]; then
  fail "CLAUDE.md must start with '@AGENTS.md'. Do not duplicate AGENTS.md content."
fi

# Warn if CLAUDE.md seems to duplicate agent instructions
dup_sections="Overview|Structure|Where to Look|Commands|Conventions|Anti-Patterns|Unique Styles"
if grep -Eiq "^#{1,3} ($dup_sections)" "$ROOT/CLAUDE.md"; then
  echo "WARN: CLAUDE.md seems to duplicate common agent instructions."
  echo "      Keep common content in AGENTS.md; keep only Claude-specific rules in CLAUDE.md."
fi

echo "doc entrypoint check passed"
