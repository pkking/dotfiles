# PROJECT KNOWLEDGE BASE

**Generated:** 2026-06-27
**Branch:** master

> **SYNC RULE**: This file and `CLAUDE.md` MUST be kept in sync for the sections: Overview, Structure, Where to Look, Commands. When updating one, update the other. CLAUDE.md additionally contains RTK instructions and Claude Code-specific guidance.

## OVERVIEW
A `chezmoi`-managed dotfiles repository defining a Linux development environment (KDE Plasma, Starship, Alacritty, Cosmic Term, tmux, zellij, Zsh/Bash) with multiple AI coding agents (Claude Code, OpenCode, Pi, Codex, Antigravity CLI) all powered by Bitwarden secret injection via `mise` tasks.

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
| Bitwarden Tasks | `dotfiles/dot_config/mise.toml` | `[tasks.cc]`, `[tasks.oc]`, `[tasks.pi]`, etc. |

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
- All AI coding agents (claude, opencode, pi, codex, agy) share a common Bitwarden secret injection pattern
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
mise run cc               # Launch Claude Code (with BW secrets)
mise run oc               # Launch OpenCode (with BW secrets)
mise run ocacp            # Launch OpenCode ACP mode (stdio-to-ws bridge, with BW secrets)
mise run pi               # Launch Pi (with BW secrets)
mise run codex            # Launch Codex CLI (with BW secrets)
mise run agy              # Launch Antigravity CLI (with BW secrets)
```

## ISSUE CHECKPOINTS
- **Resume**: For Issue-driven work, read the Issue and local checkpoint; reconcile discrepancies before continuing.
- **Triggers**: Checkpoint at implementation/review milestones, blocker or authorization changes, and handoff. Coalesce unchanged progress rather than commenting after every tool call.
- **Authorization**: Resolve permission to post checkpoint comments separately from push/PR/merge/deployment permissions. Clarify ambiguous local-only scope; a checkpoint rule grants no remote-write permission.
- **Content**: Record status, branch/exact commit, observed checks and evidence scope, remaining gaps, next action and approval gates. Distinguish local from pushed/deployed work and reported from independently verified results. Exclude secrets and unnecessary machine-specific details.
- **Ownership**: The lead agent reconciles subagent results and owns Issue synchronization; a completed workflow or local documentation commit is not a published checkpoint.
- **Publication**: When authorized, append a checkpoint, preserve history, and update completion checkboxes only against actual acceptance. Read the comment back and record its URL locally.
- **Handoff gate**: Before reporting a milestone complete or handing off, save the local checkpoint and provide either the verified Issue-comment URL or an explicit **Issue not synchronized** notice with the authorization/error blocker and recovery point. Do not silently defer synchronization or treat posting failure as implementation failure.

## DELEGATION AND CONTEXT
- Delegate every repository implementation change—including code, config, scripts, tests, documentation, and agent rules—to subagents; there is no small-change exception. The main session owns overall design, task scope, authorization, orchestration, reconciliation, checkpoints, and final communication. It may perform bounded, read-only verification, but must not implement through shell writes or another workaround.
- Run every implementation and review subagent explicitly on `openai/gpt-6-luna`; the main session uses `gpt-6.1-sol` for overall design and orchestration. If the required subagent model is unavailable, report the blocker; do not fall back to another model or implement in the main session.
- Partition delegated work by task in private branches or worktrees, and preserve pre-existing dirty files. Keep main-session context bounded to relevant excerpts, diff stats, exact commit/worktree status, and concise gate results. Delegate bulk investigation, review, and log reading; retain full outputs and evidence as files, with paths and digests, and request targeted details only for decisions. Avoid routine full-source, transcript, or log dumps.
- Require each handoff to be at most 400 words and state: scope/files and commit or uncommitted status; checks with exit codes/counts; findings, risks, and approval needs; next action; evidence paths. Summaries do not replace verification: distinguish reported results from checks independently verified by the main session and do not overclaim.
- Save a durable local checkpoint before handoff or compaction. For Issue-driven work, follow **ISSUE CHECKPOINTS** above.
