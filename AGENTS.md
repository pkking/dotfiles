# PROJECT KNOWLEDGE BASE

**Generated:** 2026-06-04
**Branch:** main

## OVERVIEW
A `chezmoi`-managed dotfiles repository defining a Linux development environment (KDE Plasma, Starship, Alacritty, Cosmic Term, tmux, zellij, Zsh/Bash) with multiple AI coding agents (Claude Code, OpenCode, Pi, Codex, Gemini CLI) all powered by Bitwarden secret injection via `mise` tasks.

## STRUCTURE
```
.
├── dotfiles/                          # Source configurations (maps to ~/)
│   ├── .chezmoiscripts/               # Lifecycle scripts (run_once_, run_onchange_)
│   ├── dot_config/                    # Maps to ~/.config
│   │   ├── alacritty/                 # Alacritty terminal config
│   │   ├── chezmoi/                   # Chezmoi settings
│   │   ├── cosmic/                    # Cosmic Term config
│   │   ├── environment.d/             # Environment variables
│   │   ├── fontconfig/                # Font configuration
│   │   ├── mise/                      # Mise plugins & settings
│   │   ├── opencode/                  # OpenCode config + skills
│   │   ├── plasma-workspace/          # KDE Plasma workspace scripts
│   │   ├── skillshare/                # Cross-tool AI skill sync
│   │   ├── mise.toml                  # Tool versions + Bitwarden tasks
│   │   └── starship.toml              # Starship prompt config
│   ├── dot_gsd/agent/                 # GSD agent settings
│   ├── dot_pi/agent/                  # Pi agent settings
│   ├── dot_cargo/                     # Rust Cargo config
│   ├── private_dot_ssh/               # SSH config (private)
│   ├── private_dot_openclaw/          # OpenClaw config (private)
│   ├── dot_bashrc.d/                  # Bash script snippets
│   ├── dot_bashrc                     # Bash config
│   ├── dot_zshrc                      # Zsh config (Oh My Zsh)
│   ├── dot_tmux.conf                  # tmux config (with TPM)
│   ├── dot_Xresources                 # X11 resources
│   ├── dot_xinitrc                    # X session startup
│   ├── dot_xprofile                   # X profile
│   ├── dot_locale.conf                # Locale settings
│   ├── dot_pip.conf                   # pip config
│   ├── dot_uv.toml                    # uv config
│   ├── dot_gitconfig.tmpl             # Git config (templated)
│   └── .chezmoiexternal.toml.tmpl     # External tool auto-install definitions
├── .chezmoiroot                       # Root pointer for chezmoi
├── .chezmoi.yaml.tmpl                 # Chezmoi config template
└── .chezmoignore                      # Ignore patterns
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/Edit Skills | `dotfiles/dot_config/opencode/skills/` | Use `skill-creator` / skillshare sync |
| Change CLI Tools | `dotfiles/dot_config/mise.toml` | Managed by `mise` |
| Modify Setup Scripts | `dotfiles/.chezmoiscripts/` | Idempotent bash scripts |
| Update Templates | `.chezmoidata.toml`, `*.tmpl`, `.chezmoiexternal.toml.tmpl` | Go-style templating |
| Add External Tools | `.chezmoiexternal.toml.tmpl` | Auto-download on apply |
| AI Agent Config | `dotfiles/dot_pi/agent/`, `dotfiles/dot_gsd/agent/` | Encrypted auth + settings |
| Bitwarden Tasks | `dotfiles/dot_config/mise.toml` | `[tasks.claude]`, `[tasks.oc]`, `[tasks.pi]`, etc. |

## CONVENTIONS
- **Chezmoi**: Never apply automatically without explicit request. Always verify with `chezmoi diff`.
- **Python Scripts**: PEP 8, Google-style docstrings, `snake_case`, type hints recommended.
- **Bash Scripts**: Idempotent execution (`set -e`), output status via `echo`.
- **Secrets**: Injected dynamically via Bitwarden CLI (`bw`) via `mise` tasks. Do not hardcode.
- **mise tasks**: All AI agents launch via `mise run <name>` which handles BW unlock + secret injection.

## ANTI-PATTERNS (THIS PROJECT)
- **Hardcoding secrets** (Use `bw` integration via mise tasks)
- **Running `chezmoi apply` blindly**
- **Ignoring idempotency** in `.chezmoiscripts`

## UNIQUE STYLES
- Environment relies on `mise` for tool management and `chezmoi` for dotfiles
- All AI coding agents (claude, opencode, pi, codex, gemini) share a common Bitwarden secret injection pattern
- External tools (mise, fonts, yazi, zellij, etc.) auto-installed via `.chezmoiexternal.toml.tmpl`
- Chinese mirrors configured for Rust (`rsproxy.cn`), Python/uv (`tuna.tsinghua.edu.cn`), and `GOTOOLCHAIN=local`
- LiteLLM proxy used for Anthropic→Gemini routing (`ANTHROPIC_BASE_URL=http://127.0.0.1:4000`)

## COMMANDS
```bash
chezmoi apply             # Apply changes
chezmoi diff              # View diff
chezmoi add <path>        # Add new file
chezmoi edit <path>       # Edit managed file
chezmoi add --encrypt <p> # Add encrypted file

mise install              # Install all managed tools
mise run claude           # Launch Claude Code (with BW secrets)
mise run oc               # Launch OpenCode (with BW secrets)
mise run pi               # Launch Pi (with BW secrets)
mise run codex            # Launch Codex CLI (with BW secrets)
mise run gemini           # Launch Gemini CLI (with BW secrets)
```
