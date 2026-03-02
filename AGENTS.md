# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-06
**Branch:** main

## OVERVIEW
A `chezmoi`-managed dotfiles repository defining a Linux development environment (KDE Plasma, Starship, Alacritty) and custom OpenCode skills ecosystem.

## STRUCTURE
```
.
├── dotfiles/              # Source configurations (maps to ~/)
│   ├── .chezmoiscripts/   # Lifecycle scripts (run_once_, run_onchange_)
│   └── dot_config/        # Maps to ~/.config (Mise, Alacritty, OpenCode skills)
└── .chezmoiroot           # Root pointer for chezmoi
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/Edit Skills | `dotfiles/dot_config/opencode/skills/` | Use `skill-creator` scripts |
| Change CLI Tools | `dotfiles/dot_config/mise.toml` | Managed by `mise` |
| Modify Setup Scripts | `dotfiles/.chezmoiscripts/` | Idempotent bash scripts |
| Update Templates | `dotfiles/.chezmoidata.toml` & `*.tmpl` | Go-style templating |

## CONVENTIONS
- **Chezmoi**: Never apply automatically without explicit request. Always verify with `chezmoi diff`.
- **Python Scripts**: PEP 8, Google-style docstrings, `snake_case`, type hints recommended.
- **Bash Scripts**: Idempotent execution (`set -e`), output status via `echo`.
- **Secrets**: Injected dynamically via Bitwarden CLI (`bw`) via `mise` tasks. Do not hardcode.

## ANTI-PATTERNS (THIS PROJECT)
- **Hardcoding secrets** (Use `bw` integration)
- **Running `chezmoi apply` blindly**
- **Ignoring idempotency** in `.chezmoiscripts`

## UNIQUE STYLES
- Environment relies heavily on `mise` for tool management and `chezmoi` for dotfiles.

## COMMANDS
```bash
chezmoi apply    # Apply changes
chezmoi diff     # View diff
chezmoi add <p>  # Add new file
chezmoi edit <p> # Edit managed file
mise install     # Install tools
```
