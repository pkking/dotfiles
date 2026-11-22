# ezwallpaper local hourly rotation (proposal B)

This source-only integration rotates local images from the fixed
`ezwallpaper-mocha/landscape` and `portrait` pools using the pinned
`ezwallpaper` binary and Noctalia as the renderer. The managed relative symlink
at `~/.local/bin/ezwallpaper` is configured to target the pinned artifact
under `~/.local/lib/ezwallpaper/8fb4f1ba938bfb87f8be7a2cf0fd6ddf87fdefc2/`.
The source pin is the published, source-only v0.3.0 stable tag at exact commit
`8fb4f1ba938bfb87f8be7a2cf0fd6ddf87fdefc2` (no binary assets are attached).
This repository change does not build, install, or switch the live alias. Preserve
any existing `~/.local/lib/ezwallpaper/4e72605fe788f1c1da1cb9aeba103353df547838/`
(alpha.1) installation and the separately deployed prior candidate
`36aca9e0df5c3f21f22c42ae266006f2bbdb5413` unchanged for rollback until a
separately authorized deployment verifies the exact installed paths. The
symlink only provides a stable command name: it does not install the target,
verify its hash or trustworthiness, or provide a fallback. It uses the binary's
UTC-hour rotation bucket and runs hourly. It does not fetch, admit a download budget,
retain, garbage-collect, or delete images. The profile is schema v1 (`owner`
plus output `name`, `dir`, and `recursive`), based on the pinned binary's
recorded successful dry-run evidence.

## Scope and source/deployment distinction

This change adds a separate profile, preflight, service, and timer; it does not
enable units or run `chezmoi apply`. The repository already contains the
separately staged `ezwallpaper-rotation.{service,timer}` and
`ezwallpaper/rotation.json` integration. Do not enable both integrations:
B's preflight refuses the other integration when active or enabled. Reviewers
should treat B as a guarded alternative, not as another concurrent rotation
source. The managed Noctalia desktop template declares built-in wallpaper automation
disabled. B is an alternative opt-in ezwallpaper scheduler, not a concurrent
source: explicitly choose at most one of B's `ezwallpaper-rotate.{service,timer}`
or #91's `ezwallpaper-rotation.{service,timer}` pair, and keep native Noctalia
automation disabled. Any GUI override must also remain disabled before B can
be deployed under separate approval.

The current machine has the B runtime files and B timer enabled, with the old
daily service persistently masked and its timer stopped; this is a deployment
observation, not a claim that this source branch has been applied or that all
machines are in that state. The live Noctalia automation setting is disabled, consistent with the
checked-in template. No scheduler is enabled by this source-only change; a
deployment must explicitly choose at most one of the two guarded ezwallpaper
unit pairs. The working image pools are
local runtime assets and are not part of this change. In particular, the
`ezwallpaper-mocha` pools are not supplied here: prepare and validate real
landscape and portrait images separately before deployment. No user image
assets or host-specific paths are committed.

## Installation and enablement gates

Before a separately approved deployment, independently ensure the pinned
artifact is already installed and trusted at
`~/.local/lib/ezwallpaper/8fb4f1ba938bfb87f8be7a2cf0fd6ddf87fdefc2/bin/ezwallpaper`,
then render the profile and prepare both pools as real directories containing
regular local files. The source supplies only the stable relative alias; it
has no installer, hash verification, fallback, or image acquisition. The
service's non-executing `test -x ~/.local/bin/ezwallpaper` preflight fails
closed when the alias target is absent or non-executable. Before applying,
review a scoped `chezmoi diff` and resolve any existing canonical
`~/.local/bin/ezwallpaper` file/type conflict manually; do not apply unrelated
dirty source changes. After all gates are independently satisfied, an operator
may manually enable the B timer only under separate explicit deployment
authorization, after recording/backup, artifact and pool validation, and the
required GUI/runtime checks. Merging this source is not deployment: this change
itself never enables the timer and does not change the current runtime.

The preflight requires all of the following before every apply:

- The managed Noctalia automation flag is false and any GUI override does not
  enable automation. Persisted TOML is checked; the running process's reload
  state cannot be proven by this check.
- The graphical session variables `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and
  `DBUS_SESSION_BUS_ADDRESS` are present.
- Existing daily/hourly wallpaper and scene-follow units, as well as the
  separately staged `ezwallpaper-rotation` pair, are inactive and disabled or
  not found. One narrow exception permits `wallpaper-daily.service` only when
  persistently masked, with no queued job and inactive/dead or failed/failed;
  the paired daily timer must independently be loaded, inactive, and disabled.
  Runtime masks, unknown/ambiguous systemd responses, and missing or
  contradictory properties remain blocked.
- Both fixed pools are real non-symlink directories with regular local files;
  pool entries may not be symlinks.

The systemd checks are read-only point-in-time observations, not a lock or a
guarantee that another actor will not change unit/config state afterward. The
persistent mask blocks activation only while it remains in place. Preflight
cannot prove Noctalia has reloaded settings or that pixels are correct.
Deployment therefore requires a separate GUI/runtime check before enabling
the timer. It does not claim physical-display validation.

The service orders after `graphical-session.target`. Its user-manager process
must inherit the graphical session environment. `flock` takes a nonblocking
per-user runtime lock; concurrent attempts fail with exit 75. The command
uses the installed binary and profile with `rotate next --apply`, never
`--force`. `Persistent=false` prevents catch-up applies after downtime. This
is rotation only: it does not populate pools. Partial output changes may
occur before an upstream IPC/readback failure; the command does not promise a
two-output transaction or rollback. Service exit status and logs are
available through `systemctl --user status ezwallpaper-rotate.service` and
`journalctl --user -u ezwallpaper-rotate.service`; success does not prove
visual correctness.

## Validation and rollback notes

Offline tests exercise fail-closed configuration/systemd checks and the service
argument contract with mocks. `systemd-analyze verify` checks unit syntax in
an isolated root. Neither validates a real user manager, installed binary,
image assets, or display output. The actual binary may only be inspected with
help/dry-run during source validation; no setter, service start, or production
change is part of this work.

For a later independently approved deployment, first record file existence,
types, permissions, timer state, Noctalia automation values, alias target, and
wallpaper getters; render and review only the scoped managed-path diff. Stage
and verify a locally built executable from the exact stable source SHA at its
content-addressed path without overwriting prior installations. Keep existing
state, pools, units and alias untouched until separately authorized cutover.
Rollback must restore the managed integration, planner pin, and alias mapping
to the exact pre-change source revision (`4e72605fe788f1c1da1cb9aeba103353df547838`)
in one scoped change. Before any apply, separately verify the observed live
alias baseline; restore it to candidate `36aca9e0df5c3f21f22c42ae266006f2bbdb5413`
only if that exact executable is present and hash-verified. Do not delete the
stable or alpha installation, or change profiles, pools, state, timers, services,
Noctalia settings, or other ezwallpaper integrations. Never execute these steps
as part of source validation; each live action needs separate approval.

Related: #84 (not complete; this change does not implement acquisition,
asset provisioning, full migration, or display acceptance). No Issue comment
was posted as part of this candidate preparation.
