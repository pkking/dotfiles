# Feed chezmoi's GitHub API calls with gh's token (nothing stored in plaintext).
# Avoids anonymous GitHub API rate limits (60/h per IP) that break
# gitHubLatestRelease / gitHubLatestTag templates in .chezmoiexternal.toml.tmpl.
if command -v gh >/dev/null 2>&1; then
    _gh_token="$(gh auth token 2>/dev/null)"
    [ -n "$_gh_token" ] && export CHEZMOI_GITHUB_TOKEN="$_gh_token"
    unset _gh_token
fi
