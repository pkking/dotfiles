# WAAAGH's Linux Dev Env

## What's in this repo

### Desktop & Terminal
- [x] DE: [KDE Plasma](https://kde.org/) configs
- [x] Terminal: [Alacritty](https://alacritty.org/) + [Cosmic Term](https://github.com/pop-os/cosmic-term) configs
- [x] Terminal multiplexer: [tmux](https://github.com/tmux/tmux) configs
- [x] Terminal multiplexer: [zellij](https://zellij.dev/) (auto-installed)
- [x] Shell prompt: [Starship](https://starship.rs/) configs
- [x] Shell: [Zsh](https://zsh.org/) (with [Oh My Zsh](https://ohmyz.sh/)) + [Bash](https://www.gnu.org/software/bash/)
- [x] File manager: [Yazi](https://yazi-rs.github.io/) (auto-installed)
- [x] Font: monospace font set to [Monaspace Nerd Fonts](https://monaspace.githubnext.com/) (auto-installed)

### AI Coding Agents (all via Bitwarden secret injection)
- [x] [Claude Code](https://github.com/anthropics/claude-code) — `mise run cc`
- [x] [OpenCode](https://opencode.ai) — `mise run oc`
- [x] [Pi](https://github.com/anthropics/pi) — `mise run pi`
- [x] [Codex CLI](https://github.com/openai/codex) — `mise run codex`
- [x] [Gemini CLI](https://ai.google.dev/gemini-api/docs/cli) — `mise run gemini`

### Dev Tools (managed by [mise](https://mise.jdx.dev/))
- [x] Languages: Python 3.13, Node 24, Go, Rust (latest)
- [x] Package managers: [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/)
- [x] CLI tools: [k9s](https://k9scli.io/), [ripgrep](https://github.com/BurntSushi/ripgrep), [GitHub CLI](https://cli.github.com/), [rtk](https://github.com/anthropics/rtk)
- [x] Web: [vibe-kanban](https://github.com/nickhould/vibe-kanban), [@termly-dev/cli](https://github.com/termly-dev/cli)
- [x] Skills: [skillshare](https://github.com/runkids/skillshare) for cross-tool AI skill sync

### Dotfile management: [chezmoi](https://www.chezmoi.io/)
- [x] External tools auto-installed: mise, oh-my-zsh, monaspace fonts, alacritty desktop entry, skillshare, lazyssh, yazi, zellij
- [x] Encryption: age-encrypted files for personal tokens

### Other
- [x] Agent configs: GSD (`~/.gsd`), Pi (`~/.pi`)
- [x] Rust: Cargo config (`~/.cargo`)
- [x] X11: `~/.Xresources`, `~/.xinitrc`, `~/.xprofile`
- [x] SSH & OpenClaw (private dirs)

## Screenshot

![](./screen.png)

## How to install

### Quick start

- Install `git` and `fontconfig` which are used in the process below

For Debian/Ubuntu users:

```bash
apt install git fontconfig zsh curl
apt install cmake g++ pkg-config libfontconfig1-dev libxcb-xfixes0-dev libxkbcommon-dev python3
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b $HOME/.local/bin
```

- Then initialize and apply the configuration:

```bash
chezmoi init pkking
chezmoi apply
```

~~Install tmux plugins by pressing `Ctrl + a` and `Shift+i`~~

Now all `tmux plugins` will be installed on a new machine due to [this tip](https://github.com/tmux-plugins/tpm/blob/master/docs/automatic_tpm_installation.md)

### Handle sensitive data

- Encrypt a file with sensitive data:

```bash
chezmoi add --encrypt <path to file>
```

- Re-encrypt all files when adding a new public key:

```bash
chezmoi re-add --encrypt
```

Feel free to email me or create an issue.

Have fun :)
