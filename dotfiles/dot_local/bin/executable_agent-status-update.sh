#!/usr/bin/env bash
# Optional periodic aggregate export; does not configure or reload Noctalia.
set -euo pipefail
exec /usr/bin/python3 -B "$HOME/.local/bin/agent-status-collect.py" \
  --toml-output "$HOME/.local/state/agent-status/status.toml"
