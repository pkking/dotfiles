# Mocha wallpaper source configuration

The Noctalia template points its default and DP-1 wallpaper to the supplied
3840×2160 landscape PNG, and HDMI-A-1 to the separately composed 2160×3840
portrait PNG. Per-monitor browsing directories use the same pools. These are
source configuration and assets only; this change does not run `chezmoi apply`,
change a live session, or start/enable a timer.

The upstream template's `[wallpaper.automation] enabled = false` remains
unchanged. With automation off and no separately selected scheduler, the
wallpapers remain static; the supplied one-image-per-orientation pools do not
provide distinct candidates for rotation. Users who want Noctalia's native
automation can explicitly set `enabled = true` in their managed configuration.

Rotation alternatives are separate and opt-in. PR #92's
`ezwallpaper-rotation` integration uses the `ezwallpaper-mocha` pools, while
local rotation B (PR #95, documented in
[`ezwallpaper-rotation-b.md`](ezwallpaper-rotation-b.md)) targets the separate
`~/.local/share/wallpapers/{landscape,portrait}` pools. Neither profile nor
timer is added or enabled by this asset/config change, and the two schedulers
must not run together. B also requires a compatible
`~/.local/bin/ezwallpaper` executable and at least two distinct validated
regular files in each configured pool; neither that private/local binary nor
additional runtime images are supplied here. An operator selecting B must
review scoped `chezmoi diff`, establish B as the sole rotation owner, deploy its
files separately, verify the pools and session prerequisites, and ensure
Noctalia's managed automation and any GUI override are off. Only after B's
preflight/other-unit checks pass may the operator run
`systemctl --user enable --now ezwallpaper-rotate.timer`. This command is not
part of applying this change. Do not assume either ezwallpaper timer is usable
with these images until its profile pool has enough distinct validated files.
If no rotation controller is deliberately deployed, the supplied wallpaper
configuration remains static; users can instead explicitly opt into Noctalia's
native automation.

The B preflight is a point-in-time guard, not a lock against later config or
unit changes, and cannot prove the running Noctalia process reloaded settings
or that rendered pixels are correct. No live setter, service, timer, reload,
or apply was run while preparing this source change.
