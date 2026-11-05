# Niri + Noctalia desktop presentation

`dotfiles/dot_config/noctalia/desktop.toml.tmpl` is the managed Noctalia 5.2.1
TOML configuration for the Tokyo Night palette and the current two-output
presentation. It keeps the built-in Alacritty theme template import, bar and
per-monitor layout, six schema-validated wallpaper/lockscreen transitions, an
analog portrait clock and CPU graph, lockscreen widgets, idle behavior,
notification placement, and OSD placement. Home-directory paths are rendered
by chezmoi. Connector names and lockscreen widget geometry are machine-specific;
review them before adopting this config on different displays.

The settings are checked by the pinned Noctalia 5.2.1 config validator as well
as the offline template/TOML contract test. Static validation does not verify a
live session, PAM unlock, monitor hotplug, or actual display appearance.

## Wallpaper scheduler authority

Noctalia's native `[wallpaper.automation]` remains **disabled**. The merged
`ezwallpaper-rotation` profile and opt-in systemd units are the only wallpaper
rotation scheduler in this configuration. Their presence does not enable them;
activation and deployment remain explicit user actions. No other timer, hook, or
service should call a wallpaper setter while that scheduler is in use. Noctalia
continues to render wallpapers selected by ezwallpaper.

The Noctalia wallpaper directories and per-output defaults in this template
are presentation settings, not a second rotation policy. Weather is disabled
and no location is configured; this avoids silently replacing the upstream
location default with an unconfirmed local-city value.

## Deliberately excluded agent widget

The candidate native `lcr/agent-status` Noctalia plugin, its manifest, widget
configuration, and IPC/refresh hooks are not included. Its presumed plugin API
and manifest contract could not be verified against pinned Noctalia 5.2.1
primary-source evidence. The merged `#99` agent collector/services are retained
without modification; no compatibility with the excluded widget is implied.
Do not add only part of the plugin integration or enable its hooks until the
pinned plugin API and collector data contract are independently verified.

## Offline validation

From the repository root:

```sh
chezmoi execute-template --init=false \
  < dotfiles/dot_config/noctalia/desktop.toml.tmpl \
  > /tmp/noctalia-desktop.toml
noctalia config validate /tmp/noctalia-desktop.toml
python3 -m unittest discover -s tests -p 'test_noctalia_desktop_contract.py' -v
```

The validator reads the rendered temporary file and does not apply config or
contact a running Noctalia session. The test renders the template, parses TOML,
checks the scheduler/theme/plugin/location contracts, and invokes the validator
only when the installed version reports 5.2.1. These checks make no live
wallpaper changes and do not install or enable any service.
