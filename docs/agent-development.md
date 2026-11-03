# Automated agent development and PR evidence

This repository adopts bounded OpenClaw-style practices: offline tests, PR checks, a stable merge gate, run-level evidence artifacts, and explicit proof limits. It does not install OpenClaw or copy its project-specific CI.

## Development lifecycle

1. A maintainer writes a concrete Issue with observable acceptance criteria and applies the `agent:implement` label. Alternatively, dispatch `Agent Issue Implementation` with an open issue number; it must have that label.
2. The read-only generation job checks out the default branch and gives Codex a temporary workspace and issue text. The agent cannot publish to GitHub.
3. A trusted patch policy rejects restricted paths, secret/encrypted files, changes to CI guardrails, oversized diffs, and symlinks. Offline checks must pass before a patch artifact is emitted.
4. A separate publisher downloads the patch, reapplies and validates it, reruns offline tests, then uses a short-lived GitHub App token to open/update a **draft** PR. It never merges.
5. Every PR runs `PR Quality Evidence`. Logs, `receipt.json`, and `report.md` identify the pull-request head SHA, actually tested checkout SHA, and the checks performed. Require the `quality-gate` check to pass before merging.
6. Reviewers examine automated proof and any desktop, hardware, or visual acceptance evidence. Offline tests do not establish correct behavior in a real desktop session.

## One-time repository setup

- Add Actions secret `OPENAI_API_KEY` for [openai/codex-action](https://github.com/openai/codex-action).
- Install a minimally scoped GitHub App on this repository with Contents read/write and Pull requests read/write. Add Actions variable `AGENT_APP_ID` and secret `AGENT_APP_PRIVATE_KEY`. The publisher receives its token only after verification. Do not expose it to Codex.
- Ensure the relevant repository setting permits GitHub Actions to create pull requests.
- Create the Issue label `agent:implement`.
- Configure a `master` branch ruleset: require `quality-gate`, require independent review, dismiss stale approvals, disallow bypass, and protect workflow/policy changes via CODEOWNERS. **This PR does not configure repository administration settings.**

## Validation scope and limitations

`python3 -B scripts/ci_quality.py` runs all `tests/test_*.py` Python tests, wallpaper configuration contracts, documentation checks and a diff integrity check. `workflow-sanity` runs checksum-verified actionlint against every Actions workflow. The receipt contains result, command, duration, log path, exact checked-out revision, PR head revision, and workflow run identifiers. A failed check exits nonzero; the report does not silently turn red into green.

The workflow never runs `chezmoi apply`, installs services, reads age identities, or accesses a live graphical desktop. Evidence artifacts are retained for 30 days; retain links or exports separately if longer evidence retention is required.

**Limits:** Automated testing cannot guarantee defect-free software. Automatic PR publication is dormant until API credentials/App configuration are supplied; remote failed-CI auto-repair is not yet implemented. Agent changes to protected control-plane files are disallowed, and independent human approval remains necessary. Treat the agent's assertions as hypotheses, not acceptance evidence.

References: [OpenClaw CI](https://github.com/openclaw/openclaw/blob/main/docs/ci.md), [OpenClaw PR evidence template](https://github.com/openclaw/openclaw/blob/main/.github/pull_request_template.md), [GitHub required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).
