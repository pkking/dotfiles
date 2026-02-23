# AGENTS.md

## 🚀 Project Overview
This is a **chezmoi** dotfiles repository for a Linux development environment. It manages configurations for KDE Plasma, Starship, Alacritty, and various CLI tools.
It also includes a custom **OpenCode** skills development environment.

## 🛠️ Build & Development Commands
This project uses `mise` for tool management and `chezmoi` for dotfile application.

### Core Commands
- **Apply changes**: `chezmoi apply` (Applies state to ~/)
- **View diff**: `chezmoi diff`
- **Add new file**: `chezmoi add <path>`
- **Edit file**: `chezmoi edit <path>`
- **Install tools**: `mise install`

### OpenCode Skills Development
Scripts are located in `dotfiles/dot_config/opencode/skills/skill-creator/scripts/`.

- **Create Skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_init_skill.py <name> --path <output-dir>`
- **Package Skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_package_skill.py <skill-folder-path>`
- **Validate Skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_quick_validate.py <skill-folder-path>`

### Testing
- No global test runner detected.
- Validate skills using the `executable_quick_validate.py` script.

## 🎨 Code Style & Conventions

### Python (Skill Scripts)
- **Style**: Standard PEP 8.
- **Docstrings**: Google-style module and function docstrings.
- **Type Hints**: Not strictly enforced in existing scripts, but recommended for new code.
- **Naming**: `snake_case` for functions and variables.
- **Shebang**: Use `#!/usr/bin/env python3`.

### Shell Scripts (`.chezmoiscripts`)
- **Shebang**: `#!/bin/bash`
- **Error Handling**: `set -e` (exit on error) recommended.
- **Output**: Use `echo` for status updates.
- **Idempotency**: Scripts should be safe to run multiple times (check if directory/file exists before creating).

### Chezmoi Templates (`.tmpl`)
- Use Go-style templating `{{ .variable }}`.
- Common variables: `.email`, `.name`.
- Use `.chezmoidata.toml` for static data.

## 📂 Repository Structure
- `.chezmoiroot`: Root pointer.
- `dotfiles/`: Source configurations (maps to `~`).
  - `dot_config/`: Maps to `~/.config`.
  - `.chezmoiscripts/`: Lifecycle scripts (`run_once_`, `run_onchange_`).

## 🤖 AI Agent Guidelines
- **Context**: You are working in a dotfiles repo. Changes here affect the user's system configuration.
- **Safety**:
  - **NEVER** run `chezmoi apply` automatically unless explicitly requested.
  - **ALWAYS** check `chezmoi diff` before confirming changes.
  - When creating skills, follow the `SKILL.md` template structure.
- **Secrets**: Use `bw` (Bitwarden) integration via `mise` tasks for secret injection. Do not hardcode secrets.

## 📝 Cursor/Copilot Rules
*(No specific .cursorrules or copilot instructions found. Follow standard best practices.)*
