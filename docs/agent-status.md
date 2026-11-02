# Agent status collector (optional aggregate interface)

This is a standalone, read-only process counter. It reports the number of top-level process trees whose executable or `/proc/<pid>/comm` is an exact supported CLI name: `claude`, `opencode`, `codex`, `agy`, `antigravity` (reported as `agy`), or `pi`. Descendants with the same tool are folded into the ancestor; a different supported tool under that tree is counted separately. The number is a process-tree estimate, not a count of interactive conversations or proof that a process was launched by `mise`.

For privacy it reads only process ownership, `comm`, `exe` symlink and `stat` metadata. It **never opens `cmdline` or `environ`**, never stores argv, prompts, cwd, environment, credentials or session content, and does not inspect agent files. Consequently agents presented as generic `node`, `python`, shell, or other wrapper processes are intentionally unsupported rather than guessed from arguments. Unsupported names are not counted. Processes that disappear or become inaccessible during a scan are skipped; failure to enumerate `/proc` or write output returns nonzero. The systemd oneshot has a 15-second runtime bound; an interrupted or failed write leaves the prior output intact.

## Use

`~/.local/bin/agent-status-collect.py` emits compact JSON to stdout by default:

```json
{"total":1,"counts":{"claude":1,"opencode":0,"codex":0,"agy":0,"pi":0}}
```

An optional aggregate TOML export can be written atomically with mode `0600`:

```sh
~/.local/bin/agent-status-collect.py --toml-output ~/.local/state/agent-status/status.toml
```

The output has `[agent_status]` with `title`, `description`, `total`, and `[agent_status.counts]` numeric entries for each supported name. Strings use TOML basic-string escaping. A same-directory temporary file, flush/fsync, and atomic replace prevent partial reads; failed collection/output does not publish a new result. Output is intentionally outside Noctalia's config directory and is only an optional consumer interface. This change does **not** install or configure a Noctalia widget, desktop field, hook, or hot reload.

## User units

The source includes `agent-status.service` and `agent-status.timer`. The timer is **not enabled automatically** and no chezmoi lifecycle script enables it. If an operator chooses to consume the optional periodic export, they can explicitly enable it after deploying and reviewing the unit; no unit was started, enabled, or reloaded as part of this change. The unit writes only `~/.local/state/agent-status/status.toml`, with private file permissions.

## Noctalia integration boundary

An untracked source snapshot contained a proposed `lcr/agent-status` manifest/Luau widget, but the user's `~/.local/share/noctalia/plugin` and `~/.local/share/noctalia/plugins` paths were absent, and its discovery/runtime behavior could not be verified. This PR deliberately excludes that plugin and every `desktop.toml.tmpl` change; it makes no claim that a widget integration works. A consumer can read the aggregate JSON/TOML contract independently. Any future widget should be validated against the installed Noctalia version and plugin discovery mechanism before being referenced by desktop configuration.

## Tests

Run `python3 -B tests/test_agent_status.py -v`. Tests use isolated fake `/proc` trees, never the real process table or agent sessions. They cover exact-name matching, same-tool ancestry de-duplication, unsupported/argv-shaped false positives, malformed/disappearing processes, enumeration errors, JSON/TOML schema and escaping, atomic/private output, and last-good preservation on write failure.
