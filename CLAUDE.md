# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Dotfile Management (chezmoi)
- **Apply changes**: `chezmoi apply`
- **View diff**: `chezmoi diff`
- **Add new file**: `chezmoi add <path>`
- **Edit managed file**: `chezmoi edit <path>`
- **Re-manage/Update file**: `chezmoi re-add`

### Toolchain & Environment (mise)
- **Bootstrap environment**: `mise run bootstrap`
- **Install tools**: `mise install`
- **Launch OpenCode**: `mise run opencode` (Injects Bitwarden secrets)

### OpenCode Skills Development
- **Initialize new skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_init_skill.py <name> --path <output-dir>`
- **Package skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_package_skill.py <skill-folder-path>`
- **Validate skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_quick_validate.py <skill-folder-path>`

## High-Level Architecture

### Repository Structure
This is a **chezmoi** dotfiles repository with a custom layout.
- `.chezmoiroot`: Points to the `dotfiles/` directory as the root of the source state.
- `dotfiles/`: Contains the actual configuration source files using chezmoi's naming convention (e.g., `dot_config` -> `~/.config`).
- `dotfiles/.chezmoiscripts/`: Contains lifecycle scripts (`run_once_*`, `run_onchange_*`, `run_after_*`) for automated installation and configuration.

### Tooling & Configuration
- **Mise**: Used for managing language runtimes (`python`, `node`, `go`, `rust`, `bun`) and CLI tools. Config is at `dotfiles/dot_config/mise.toml`.
- **OpenCode**: A specialized environment with "Skills" located in `dotfiles/dot_config/opencode/skills/`.
- **Secret Management**: Integration with **Bitwarden CLI (`bw`)** is used via mise tasks to inject credentials into applications.
- **Starship**: Shell prompt configuration.
- **Alacritty/Cosmic**: Terminal configurations.

### Templating & Data
- Files ending in `.tmpl` use Go-style templating.
- Data variables are defined in:
  - `dotfiles/.chezmoidata.toml` (static data)
  - `.chezmoi.yaml.tmpl` (dynamic/prompt-based data)
- Common template variables include `.email`, `.name`, and `.china_mirror`.
