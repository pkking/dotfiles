# Optional Noctalia palette for Alacritty

The Alacritty config imports the managed Rose Pine theme first, then
`~/.config/alacritty/themes/noctalia.toml`. Alacritty merges later imports over
earlier ones, so Noctalia colors take precedence when the generated file exists.
Alacritty 0.17 skips a missing import and keeps the earlier theme; it emits an
`info`-level “Config import not found” message (so this is not strictly silent).

The Noctalia desktop template opts into the built-in `alacritty` template. On
Noctalia 5.2.1, its built-in catalog renders the palette to
`$XDG_CONFIG_HOME/alacritty/themes/noctalia.toml`. No host-generated palette is
checked in. The palette follows Noctalia's current theme; if Noctalia or its
built-in template is unavailable, Alacritty continues with Rose Pine.

To use the integration, apply/manage the provided Noctalia desktop config and
allow Noctalia's built-in theme-template service to generate its output; no
manual theme download or palette copy is needed. To opt out, remove `noctalia.toml`
from Alacritty's `general.import` list. Changing the Alacritty import order
changes precedence.
