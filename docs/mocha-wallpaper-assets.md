# Mocha wallpaper source configuration

The Noctalia template points its default and DP-1 wallpaper to the supplied
3840×2160 landscape PNG, and HDMI-A-1 to the separately composed 2160×3840
portrait PNG. Per-monitor browsing directories use the same pools. These are
source configuration and assets only; this change does not run `chezmoi apply`,
change a live session, or start/enable a timer.

The upstream template's `[wallpaper.automation] enabled = false` remains
unchanged. Native Noctalia wallpaper automation stays disabled; this project
configuration does not offer it as an alternative scheduler. With no
separately selected ezwallpaper scheduler, the wallpapers remain static. The
supplied one-image-per-orientation pools do not provide distinct candidates
for rotation.

Rotation alternatives are separate and opt-in. PR #92's
`ezwallpaper-rotation` integration uses the `ezwallpaper-mocha` pools. Local
rotation B (PR #95, documented in
[`ezwallpaper-rotation-b.md`](ezwallpaper-rotation-b.md)) has a path mismatch:
its profile template currently points to
`~/.local/share/wallpapers/{landscape,portrait}`, but its preflight guard is
hard-coded to require real directories at
`~/.local/share/wallpapers/ezwallpaper-mocha/{landscape,portrait}`. Changing
the profile alone does not make the guard support arbitrary pool paths; both
the profile's candidate paths and the guard's fixed paths must satisfy their
respective checks. Neither profile nor timer is added or enabled by this
asset/config change, and the two ezwallpaper schedulers must not run together.
B additionally requires a compatible `~/.local/bin/ezwallpaper` executable,
valid distinct candidates for rotation, and the session/config/unit safeguards;
neither that private/local binary nor additional runtime images are supplied
here. An operator selecting B must resolve the path contract, review scoped
`chezmoi diff`, establish B as the sole rotation owner, deploy its files
separately, verify the pools and session prerequisites, and ensure Noctalia's
managed automation and any GUI override are off before separately enabling B.
This change does not enable B or run its timer.

Scheduler ownership is deliberately limited to the two opt-in ezwallpaper
integrations: choose and explicitly enable at most one of #91
`ezwallpaper-rotation` or #95 `ezwallpaper-rotate`; never run them together.
Both are initially disabled, and native Noctalia wallpaper automation must
remain disabled, including any GUI override, whether neither or one scheduler
is selected. If no ezwallpaper scheduler is deliberately deployed, this
supplied one-image-per-orientation configuration remains static. This is
source guidance only: it does not deploy or enable a scheduler. The asset
provenance/license boundary above is unchanged; no third-party images are
bundled or implied.

The B preflight is a point-in-time guard, not a lock against later config or
unit changes, and cannot prove the running Noctalia process reloaded settings
or that rendered pixels are correct. No live setter, service, timer, reload,
or apply was run while preparing this source change.
