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
