#!/bin/bash
# skillshare-chezmoi-sync.sh — snapshot ~/.config/skillshare/skills into the
# chezmoi dotfiles source, then commit and push.
#
# Triggered automatically after mutating skillshare commands by the shell
# wrapper (see ~/.zshrc / ~/.bashrc.d/skillshare-auto-sync.sh); also safe to
# run manually at any time. Idempotent: exits quietly when nothing changed.
#
# Env overrides (used by the isolated self-test):
#   SKILLSHARE_SYNC_SOURCE_DIR  chezmoi source dir (default: the real one)
#   SKILLSHARE_SYNC_NO_PUSH=1   skip the final git push

set -euo pipefail
export LC_ALL=C  # stable sort/comm collation

SKILLS_DIR="$HOME/.config/skillshare/skills"
SOURCE_DIR="${SKILLSHARE_SYNC_SOURCE_DIR:-$HOME/.local/share/chezmoi/dotfiles}"
SRC_REL="dot_config/skillshare/skills"
STATE_FILE="${SKILLSHARE_SYNC_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/skillshare-chezmoi-sync/fingerprint}"

[ -d "$SKILLS_DIR" ] || exit 0
[ -d "$SOURCE_DIR/$SRC_REL" ] || exit 0

# Fast path: skip the expensive chezmoi pipeline when the skills tree content
# is unchanged since the last successful sync (~2s vs ~30s for 600+ files).
fingerprint="$(cd "$SKILLS_DIR" && find . -name .git -prune -o -type f -print0 \
    | sort -z | xargs -0 -r sha256sum | sha256sum | cut -d' ' -f1)" || fingerprint=""
if [ -z "${SKILLSHARE_SYNC_FORCE:-}" ] && [ -f "$STATE_FILE" ] \
   && [ "$(cat "$STATE_FILE" 2>/dev/null)" = "$fingerprint" ]; then
    echo "skillshare→chezmoi: up to date"
    exit 0
fi

# GitHub API auth for chezmoi's template functions (avoids anonymous 403s).
if [ -z "${CHEZMOI_GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
    _gh_token="$(gh auth token 2>/dev/null || true)"
    [ -n "$_gh_token" ] && export CHEZMOI_GITHUB_TOKEN="$_gh_token"
    unset _gh_token
fi

# </dev/null: chezmoi subcommands (source-path notably) read stdin when it
# is not a TTY, which would hang the script in non-interactive contexts.
cz() { chezmoi --source "$SOURCE_DIR" "$@" </dev/null; }

# 1) Refresh changed and new files in the source snapshot.
if ! err="$(cz add "$SKILLS_DIR" 2>&1 >/dev/null)"; then
    echo "skillshare→chezmoi: chezmoi add failed:" >&2
    printf '%s\n' "$err" >&2
    exit 1
fi
# Surface non-noise diagnostics (gitleaks warnings and the known .git ignore
# notice are noisy on every run).
printf '%s\n' "$err" | grep -vE 'Detected a potential|warning: ignoring' >&2 || true

# 2) Forget source entries whose target file no longer exists.
# Note: managed lists directories too; find lists files only, so dir
# entries always show up here. Resolve them all in ONE batched chezmoi
# invocation (each chezmoi call costs ~4s of source-state parsing) and
# only delete entries that are files; empty dirs are swept in step 3.
mapfile -t orphans < <(comm -23 \
    <(cz managed "$SKILLS_DIR" | sort) \
    <(cd "$HOME" && find .config/skillshare/skills -name .git -prune -o -print | sort))

if [ "${#orphans[@]}" -gt 0 ]; then
    mapfile -t orphan_sources < <(\
        printf '%s\n' "${orphans[@]}" | sed "s|^|$HOME/|" \
        | xargs -r -d '\n' chezmoi --source "$SOURCE_DIR" source-path 2>/dev/null || true)
    for src in "${orphan_sources[@]}"; do
        [ -f "$src" ] && rm -f "$src"
    done
fi

# 3) Drop now-empty directories from the source tree.
find "$SOURCE_DIR/$SRC_REL" -depth -mindepth 1 -type d -empty -delete

# 4) Commit (skills paths only, so unrelated WIP never gets swept in).
cd "$SOURCE_DIR"
git add -A -- "$SRC_REL"
if git diff --cached --quiet -- "$SRC_REL" 2>/dev/null; then
    echo "skillshare→chezmoi: up to date"
    mkdir -p "$(dirname "$STATE_FILE")" && printf '%s\n' "$fingerprint" > "$STATE_FILE"
    exit 0
fi
git commit -q -m "chore(skillshare): auto-sync skills from local update"
echo "skillshare→chezmoi: committed $(git rev-parse --short HEAD)"
mkdir -p "$(dirname "$STATE_FILE")" && printf '%s\n' "$fingerprint" > "$STATE_FILE"

if [ -z "${SKILLSHARE_SYNC_NO_PUSH:-}" ]; then
    if git push --quiet 2>/dev/null; then
        echo "skillshare→chezmoi: pushed"
    else
        echo "skillshare→chezmoi: push failed (will retry on next sync)" >&2
    fi
fi
