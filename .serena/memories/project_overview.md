This project is a **chezmoi** dotfiles repository for a Linux development environment.
It manages configurations for KDE Plasma, Starship, Alacritty, and various CLI tools.
It also includes a custom **OpenCode** skills development environment.

### Tooling & Configuration
- **Mise**: Used for managing language runtimes (`python`, `node`, `go`, `rust`, `bun`) and CLI tools. Config is at `dotfiles/dot_config/mise.toml`.
- **OpenCode**: A specialized environment with "Skills" located in `dotfiles/dot_config/opencode/skills/`.
- **Secret Management**: Integration with **Bitwarden CLI (`bw`)** is used via mise tasks to inject credentials into applications.
- **Starship**: Shell prompt configuration.
- **Alacritty/Cosmic**: Terminal configurations.
- **Chezmoi**: Dotfile management.

### Repository Structure
- `.chezmoiroot`: Points to the `dotfiles/` directory as the root of the source state.
- `dotfiles/`: Contains the actual configuration source files using chezmoi's naming convention (e.g., `dot_config` -> `~/.config`).
- `dotfiles/.chezmoiscripts/`: Contains lifecycle scripts (`run_once_*`, `run_onchange_*`, `run_after_*`) for automated installation and configuration.
