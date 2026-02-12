export PATH=$PATH:$HOME/.local/bin:$HOME/.nix-profile/bin
# mise
eval "$(mise activate bash --shims)"
# starship
eval "$(starship init bash)"

if command -v nvim >/dev/null 2>&1; then
    alias vi='nvim'
    alias vim='nvim'
    export EDITOR='nvim'
else
    export EDITOR='vi'
fi
