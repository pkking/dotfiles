# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **SYNC RULE**: This file and `AGENTS.md` MUST be kept in sync for the sections: Overview, Structure, Where to Look, Commands. When updating one, update the other. This file additionally contains RTK instructions and Claude Code-specific guidance.

<!-- ===== SYNCED SECTION (keep in sync with AGENTS.md) ===== -->

## OVERVIEW
A `chezmoi`-managed dotfiles repository defining a Linux development environment (KDE Plasma, Starship, Alacritty, Cosmic Term, tmux, zellij, Zsh/Bash) with multiple AI coding agents (Claude Code, OpenCode, Pi, Codex, Gemini CLI) all powered by Bitwarden secret injection via `mise` tasks.

## STRUCTURE
```
.
├── dotfiles/                          # Source configurations (maps to ~/)
│   ├── .chezmoiscripts/               # Lifecycle scripts (run_once_, run_onchange_, run_after_)
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
mise run bootstrap        # Bootstrap environment (languages first, then tools)
mise run claude           # Launch Claude Code (with BW secrets)
mise run oc               # Launch OpenCode (with BW secrets)
mise run pi               # Launch Pi (with BW secrets)
mise run codex            # Launch Codex CLI (with BW secrets)
mise run gemini           # Launch Gemini CLI (with BW secrets)
```

## Development Commands (Claude Code Specific)

### Dotfile Management (chezmoi)
- **Apply changes**: `chezmoi apply`
- **View diff**: `chezmoi diff`
- **Add new file**: `chezmoi add <path>`
- **Edit managed file**: `chezmoi edit <path>`
- **Re-manage/Update file**: `chezmoi re-add`

### OpenCode Skills Development
- **Initialize new skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_init_skill.py <name> --path <output-dir>`
- **Package skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_package_skill.py <skill-folder-path>`
- **Validate skill**: `python3 dot_config/opencode/skills/skill-creator/scripts/executable_quick_validate.py <skill-folder-path>`

<!-- /SYNCED SECTION -->

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
