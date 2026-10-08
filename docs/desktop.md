# Optional Niri + Noctalia v5 desktop

This repository now **tracks configuration**, not system package installation or
the active login session. KDE Plasma and existing X11 files remain intact.

## Compatibility and ownership

- **Niri >= 25.11** is required for top-level `include "cfg/*.kdl"`.
- **Noctalia >= v5** is required for hand-managed `*.toml` configuration and
  `noctalia msg` actions. Do not reuse v4 `settings.json` or `qs ipc call`.
- The distribution's package manager is responsible for niri, Noctalia and
  required Wayland desktop services; package/bootstrap automation is not part
  of this PR. Alacritty is already defined in this dotfiles repository.
- Source state: `dotfiles/dot_config/niri/` and
  `dotfiles/dot_config/noctalia/`. These render to `~/.config/niri/` and
  `~/.config/noctalia/` on chezmoi apply.
- The Niri session starts Noctalia, **not KDE**. No login/session manager or
  default-session setting is changed by this baseline.

## Key bindings

| Key | Action |
| --- | --- |
| Super+Return | Alacritty terminal |
| Super+D | Noctalia launcher |
| Super+Shift+S | Noctalia settings |
| Super+Shift+Q | Noctalia session menu |
| Super+Alt+L | Noctalia lock |
| Super+Q | Close focused window |
| Super+Left / Right | Focus left / right column |
| Super+Ctrl+Left / Right | Move column |
| Super+R | Cycle column widths |
| Super+F | Fullscreen |
| Super+1..5 | Focus workspace 1..5 |
| Super+Ctrl+1..5 | Move column to workspace |
| Super+Shift+Escape | Show hotkeys |

`Mod` maps to `Super` on the real session and may map to `Alt` when nested.
Other bindings can be added to `cfg/binds.kdl` once tested.

## Machine-specific config without leaking hardware settings

The default templates do **not** assume that your connector is eDP-1,
HDMI-A-1, or any other name. Niri uses auto-detected outputs.

Inspect connectors inside a Niri session:

```sh
niri msg outputs
```

To opt in, set these data keys in the **machine-local** chezmoi config
(the config returned by `chezmoi doctor`), not in this public repo:

```yaml
data:
  desktop_niri_outputs: |
    output "REPLACE_WITH_ACTUAL_CONNECTOR" {
      scale 1.25
    }
  desktop_noctalia_machine: |
    [accessibility]
    ui_scale = 1.1
```

The examples are intentionally **not** active defaults. Run
`chezmoi data` to confirm the machine-local values, then
`chezmoi cat ~/.config/niri/cfg/outputs.kdl` and
`chezmoi cat ~/.config/noctalia/10-machine.toml` to inspect rendering.
The `10-machine.toml` file overrides `00-base.toml` at the same setting path.

## Safe apply and verification

```sh
# Review rendered configuration and changes first (read-only).
chezmoi diff
chezmoi cat ~/.config/niri/config.kdl
chezmoi cat ~/.config/niri/cfg/outputs.kdl
chezmoi cat ~/.config/noctalia/00-base.toml
chezmoi cat ~/.config/noctalia/10-machine.toml
chezmoi apply --dry-run --verbose

# Apply only after explicit approval, on a machine with a recovery session.
chezmoi apply

# Validate the actual deployed config, using installed compatible binaries.
niri validate
noctalia config validate
noctalia config export
```

**Important:** applying a modified config in an active Niri session can trigger
a hot reload. Run the read-only checks before applying, and keep KDE (or a TTY)
available as fallback. The next PR will add CI staging/rendering and validators;
these have **not** yet been executed on a real Niri session.

## GUI override drift

Noctalia loads configuration in this order:

1. Built-in defaults.
2. `~/.config/noctalia/*.toml` (sorted, including `00-base.toml` then
   `10-machine.toml`).
3. `~/.local/state/noctalia/settings.toml` (GUI/runtime-managed, highest
   priority).

Do **not** track the state file or erase it to force an Agent's preferred
values. Compare `noctalia config export` (merged user configuration) against
the managed files. Promote desired GUI changes into TOML after review, and
resolve state precedence explicitly.

## Recovery

If a config change blocks the Niri session, log into KDE or a TTY, inspect
`chezmoi diff` and the most recent Git changes, revert the offending managed
files, then validate and re-apply deliberately. Do not restart the login manager
or remove existing session files as a shortcut.

## Upstream implementation references

- Niri includes: https://niri-wm.github.io/niri/Configuration:-Include.html
- Niri key bindings: https://niri-wm.github.io/niri/Configuration:-Key-Bindings.html
- Noctalia v5 config: https://docs.noctalia.dev/noctalia/configuration/
- CachyOS niri baseline: https://github.com/CachyOS/cachyos-niri-noctalia
- Multi-machine chezmoi Noctalia ADR:
  https://github.com/anIcedAntFA/dotfiles/blob/main/docs/adr/0020-noctalia-v5-config-tracked-as-toml-base-plus-machine.md
- Modular Niri + Noctalia:
  https://github.com/ryan4yin/nix-config/tree/main/home/linux/gui
