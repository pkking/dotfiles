# ezwallpaper integration policy (source-only, non-deploying)

The source configuration is `dotfiles/dot_config/ezwallpaper/integration.json.tmpl`.
The planner source is `dotfiles/dot_local/bin/executable_ezwallpaper-plan.py`;
neither establishes that a `~/.local/bin` installation exists. No deployment or
chezmoi apply is performed here.

Render the template for inspection with chezmoi:

```sh
chezmoi execute-template < dotfiles/dot_config/ezwallpaper/integration.json.tmpl > /tmp/ezwallpaper-integration.json
```

Then validate without spawning ezwallpaper:

```sh
python3 dotfiles/dot_local/bin/executable_ezwallpaper-plan.py \
  --config /tmp/ezwallpaper-integration.json --json
```

Offline preview can optionally invoke the configured pinned executable, but
only after configuration validation. It requires both configured pools to
already exist; it does not create them. Preview creates a temporary profile and
passes only a temporary state path to upstream:

```sh
python3 dotfiles/dot_local/bin/executable_ezwallpaper-plan.py \
  --config /tmp/ezwallpaper-integration.json --preview --json
```

The command is `rotate next --profile … --state … --dry-run --force --json`.
The temporary profile matches the current schema-v1 profile contract (`owner`
and output `name`, `dir`, `recursive: false`). Upstream dry-run does not create
the state or lock files. It never passes `--apply`, calls fetch, invokes a
renderer or service, uses sudo, or accesses production rotation state. The
temporary profile directory is removed when the CLI exits. Results report
selected local paths only; `visually_verified: false` means no visual
validation was performed.
Preview `--force` asks the upstream offline rotation planner to replan; it is
not a claim that arbitrary production rotation periods are idempotent.

The binary setting is constrained to a commit-specific installation path. This
path pin is not a runtime SHA-256 verification of the executable; verify the
installed artifact separately when trust in its contents is required.

Policy notes (configuration only, not active production behavior):

- Defaults are `interval_seconds: 1800` (30 minutes),
  `pool_capacity_bytes: 500000000` (500 decimal MB shared by both pools),
  and `retention: {"mode": "capacity", "on_full": "stop"}`.
- `stop` means stop acquiring new files, not stop rotating existing ones.
  `delete_oldest` is the requested opt-in alternative; this planner never
  deletes anything, and the old wallpaper directories are not managed by it.
- Wallhaven SFW filtering uses `purity: "sfw"`; `nature` is a query keyword
  (`query: "nature"`), not the API categories bitmask.
- `interval_seconds` is a positive integer policy value, not an enforced
  fetch schedule.
- Each output pool must be a dedicated, disjoint path below the home
  directory. Missing preview pools are errors, not auto-created locations.
- `pool_capacity_bytes` is always required, including in `time` retention
  mode. It remains a mandatory upper-bound policy value alongside a positive
  `retention.max_age_seconds`; neither policy is enforced here.
- `retention.mode` is `capacity` or `time`; `on_full` accepts `stop` or
  `delete_oldest` as requested policy only. No fetch scheduler, budget
  enforcement, retention GC, or on-full action is implemented.

The planner's regular mode validates only and never spawns a process. Valid
policy still reports `readiness: blocked`; this configuration does not enable
scheduling, downloading, retention, or desktop application.

## Upstream gaps

- Schedule idempotency and retry behavior: [#54 requirement discussion](https://github.com/pkking/ezwallpaper/issues/54#issuecomment-6321506337).
- Retention policy and budget: [#57 requirement discussion](https://github.com/pkking/ezwallpaper/issues/57#issuecomment-6321507997).
- Streaming download limits and staging budget: [#79](https://github.com/pkking/ezwallpaper/issues/79).

The JSON plan exposes these source links in `upstream_gaps` for consumers.
