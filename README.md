# WAAAGH's linux dev env

## Whats in this repo

- [x] my [i3wm](https://i3wm.org/) configs
- [x] my [neovim](https://neovim.io/) config and plugins
- [x] [starship](https://starship.rs/) configs
- [x] [tmux](https://github.com/tmux/tmux) configs
- [x] default monospace fontconfig using [monaspace](https://monaspace.githubnext.com/)
- [x] [dev tools](./dotfiles/dot_config/mise.toml) managed by [mise](https://mise.jdx.dev/)


## SCREENSHOT

TBD

## HOW TO INSTALL

### Quick start

- Install [chezmoi](https://www.chezmoi.io/install/)

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b $HOME/.local/bin
```

- Then initialize and apply the configuration:

```bash
chezmoi init pkking
chezmoi apply
```

feel free to email me or commit a issue

have fun :)
