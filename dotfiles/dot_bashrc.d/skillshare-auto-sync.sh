# Auto-sync skillshare skills into the chezmoi dotfiles source after any
# command that mutates the source. Sync script is a no-op when nothing
# changed, so over-triggering is harmless.
skillshare() {
    command skillshare "$@"
    local rc=$?
    case "$1" in
        init|install|uninstall|move|link|unlink|new|enable|disable|update|collect|extras|ui|commit|push|pull)
            if [ "$rc" -eq 0 ] \
               && [ -x "$HOME/.local/bin/skillshare-chezmoi-sync.sh" ] \
               && [[ " $* " != *" --dry-run "* && " $* " != *" -n "* ]]; then
                "$HOME/.local/bin/skillshare-chezmoi-sync.sh" || true
            fi
            ;;
    esac
    return "$rc"
}
