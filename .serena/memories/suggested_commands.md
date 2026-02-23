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
