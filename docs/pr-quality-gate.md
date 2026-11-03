# PR review gate

This repository follows the risk separation in [OpenClaw's PR review flow](https://docs.openclaw.ai/reference/pull-request-review-flow). Development agents are external. GitHub Actions **do not** launch development, generate patches, request reviews, post bot comments, close PRs, or merge.

## Two independent, enforceable signals

1. **`pr-context-evidence` — trusted Barnacle-style screen.** A `pull_request_target` workflow checks out **`github.workflow_sha`**, the trusted workflow revision, never the contributor's branch. It only reads the PR event's title/body/draft/head, and does not run PR code. It evaluates an authored `What Problem This Solves` and `Evidence` section. Empty boilerplate, no concrete problem, and future-tense CI promises without completed proof fail. Acceptance criteria and risks are useful advisory signals, not arbitrary hard requirements. A CI/test/docs/refactor-only PR lacking a linked issue receives an advisory maintainer-context warning. Drafts may iterate; they are **not ready for review**. The decision is emitted as a machine-readable artifact and a commit status on the **exact PR head**. No labels, bot comments, auto-closure or auto-review requests.
2. **`quality-gate` — actual code checks.** The separate `pull_request` workflow runs offline Python tests, wallpaper contracts, docs checks, and actionlint against the candidate, using a read-only token and no secrets. Logs, `receipt.json` and `report.md` capture tested checkout SHA, PR head SHA, commands, durations, failures and limits. Failures/skips cannot satisfy `quality-gate`. It never runs `chezmoi apply`.

A positive context check means the **author supplied plausible problem context and evidence**; it does **not** establish that the stated tests ran or prove correctness. Only actual CI results provide independent test evidence, and they still cannot establish a real desktop/visual result. The two signals MUST NOT substitute for each other.

## Maintainer review

- Consider only ready-for-review PRs with green `pr-context-evidence` and `quality-gate`, plus any applicable independent review, security or visual requirements.
- Verify that proof matches the feature: relevant production-path tests, command output/CI artifacts, before/after screenshots for visual behavior, or redacted reproduction evidence. A mock of the wrong boundary is not acceptance proof.
- For claimed local autoreview or ClawSweeper reports, require tool, reviewed base/head (or local snapshot), effective coverage, outcome and remaining findings. These are **self-reported**; a version/hash is not an attestation. Refresh stale review when relevant code or base changes.
- Keep the PR description current and batch fixes before requesting another hosted review. Do not repeatedly summon review on each push.
- Maintainers retain merge authority. A positive AI review is advisory and never independent approval.

**Not implemented:** OpenClaw's hosted **ClawSweeper** AI review queue, Barnacle inactivity/closure lifecycle, review comments, and author-open-PR count/diff classification. Those require separate trusted services/permissions and must not be misrepresented as present. This CI implements the useful deterministic intake and independent test-proof parts without running a coding agent.

## Repository setup and activation

After merging this workflow to the **default branch**, configure required `pr-context-evidence` (commit status) and `quality-gate` (Actions check) on `master`, plus independent approvals/CODEOWNERS for security-sensitive changes. The new `pull_request_target` workflow cannot run from an unmerged PR branch; its unit tests and actionlint run on this PR, but the live trusted-gate trigger only exists once installed on `master`. `@pkking` alone is not an independent reviewer for their own PR. Repository settings require separate administration.

References:
- https://docs.openclaw.ai/reference/pull-request-review-flow
- https://docs.openclaw.ai/ci/watching-runs
- https://github.com/openclaw/openclaw/blob/main/.github/workflows/real-behavior-proof.yml
- https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target
