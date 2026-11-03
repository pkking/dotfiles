# PR quality gate

## Scope

Development agents operate **outside GitHub Actions**. This repository does not dispatch coding agents, generate patches, publish branches, or merge pull requests. CI exists to make low-quality or invalid PRs visible before maintainer review.

## Review intake

Every non-draft PR must have a specific title and substantive sections covering **problem**, **acceptance criteria**, **evidence**, and **risks or limitations**. Blank PR templates fail `pr-intake`. The check is deterministic, read-only, and reports specific omissions in the Actions summary and a 30-day JSON artifact. It does not comment on PRs, add labels, or request reviewers.

Drafts may omit sections while work is in progress, but are not deemed ready for maintainer review; switching a PR to ready-for-review triggers the intake check again. The format requirement is a triage mechanism, **not proof that the author's statements are true**.

## Independent evidence

After intake passes, `offline-validation` executes the repository's Python regression tests, wallpaper configuration contracts, documentation checks and diff validation. `workflow-sanity` runs checksum-verified `actionlint` on authored workflows. Both are required for `quality-gate`. On failure or cancellation, the gate fails.

Logs, `receipt.json`, and `report.md` are uploaded as `quality-evidence-<run-id>-<attempt>`. The receipt includes the PR head SHA, tested checkout SHA (normally GitHub's synthetic merge commit), actual commands, result codes, and limitations. The workflow runs on a read-only token and never executes `chezmoi apply`, accesses personal secrets, or changes a live desktop. Real UI/desktop acceptance requires separate evidence; offline checks cannot prove it.

## Maintainer workflow

1. Ignore drafts and PRs with failed intake or failed quality checks.
2. Inspect the check summaries and machine evidence for green PRs.
3. Require focused regression tests or explicit justification, and live/visual evidence when the affected behavior cannot be validated in CI.
4. Perform independent review of code, security-sensitive changes, and operational consequences.
5. Merge only after the required checks and approvals.

This does not prevent GitHub from notifying a maintainer when a PR is first created. It prevents automatic review requests and supplies a cheap readiness filter. There is **no automated PR closure** based on heuristics.

## Repository administration

Configure an enforced `master` ruleset requiring `quality-gate` and independent approval. Protect workflow and intake-policy changes through CODEOWNERS; `@pkking` alone cannot provide a second independent approval on their own PR. Disable bypass where appropriate. The PR cannot itself prove that these settings are active.

References: [GitHub required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
