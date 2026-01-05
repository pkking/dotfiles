# WAAAGH's linux dev env

# WHAT WE GOT
- my i3wm config
- my awesome wm config
- my neovim/vim config and plugins
- powerline for vim, tmux
- nerd fonts

# SCREENSHOT
TBD

# HOW TO INSTALL

## Bootstrap
Install [chezmoi](https://www.chezmoi.io/install/) firstly
```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b $HOME/.local/bin
```

Then initialize and apply the configuration:
```bash
chezmoi init pkking
chezmoi apply
```

feel free to email me or commit a issue

have fun :)
