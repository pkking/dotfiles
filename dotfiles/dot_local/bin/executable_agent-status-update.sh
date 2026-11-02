#!/usr/bin/env bash
# Optional periodic aggregate export; does not configure or reload Noctalia.
set -euo pipefail
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
exec /usr/bin/python3 -B "$HOME/.local/bin/agent-status-collect.py" \
  --toml-output "$state_home/agent-status/status.toml"
