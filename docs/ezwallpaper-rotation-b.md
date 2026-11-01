# ezwallpaper local hourly rotation (proposal B)

This source-only integration rotates local images from the fixed
`ezwallpaper-mocha/landscape` and `portrait` pools using the installed
`ezwallpaper` binary and Noctalia as the renderer. It uses the binary's UTC-hour
rotation bucket and runs hourly. It does not fetch, admit a download budget,
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
source. The Noctalia desktop template remains unchanged and still declares
built-in wallpaper automation enabled; B cannot be enabled until that source
configuration and any GUI override are manually migrated in a separately
approved deployment.

The current machine has the B runtime files and B timer enabled, with the old
daily service persistently masked and its timer stopped; this is a deployment
observation, not a claim that this source branch has been applied or that all
machines are in that state. The live Noctalia automation setting is disabled,
but the checked-in template still says enabled. The working image pools are
local runtime assets and are not part of this change. In particular, the
`ezwallpaper-mocha` pools are not supplied here: prepare and validate real
landscape and portrait images separately before deployment. No user image
assets or host-specific paths are committed.

## Installation and enablement gates

Before a separately approved deployment, install a compatible `ezwallpaper`
binary at `~/.local/bin/ezwallpaper`, render the profile, and prepare both
pools as real directories containing regular local files. The service does
not install the binary or acquire images. Review a scoped `chezmoi diff`; do
not apply unrelated dirty source changes. After all gates are independently
satisfied, an operator may manually enable the B timer. This change itself
never enables it.

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
types, permissions, timer state, Noctalia automation values, and wallpaper
getters. To roll back only B, stop/disable its timer if it was enabled and
remove only B's deployed profile, preflight, service, and timer after checking
they were absent or unchanged from the recorded baseline. Reload the user
manager. Do not remove pools or rotation state, unmask legacy units, restore
old timers, alter Noctalia settings, or touch the other ezwallpaper
integration as part of this narrow rollback. Each of those requires its own
review and approval.

Related: #84 (not complete; this change does not implement acquisition,
asset provisioning, full migration, or display acceptance). No Issue comment
was posted as part of this candidate preparation.
