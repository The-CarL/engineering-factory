# Security model

## Public harness, private authority

This repo may be read or forked publicly. It contains no live accounts, credentials, state, or private endpoints. Configuration names are public; their values and provider permissions live outside Git. Ignore rules, scanner checks, and instructions reduce mistakes but cannot enforce least privilege on a process holding broad credentials.

Use provider-enforced scopes and dedicated sandbox targets. Verify an exact GitHub owner, Vercel team/project, AWS role/account/region, allowed operations, expiry, budget, revocation owner, and rollback before any write. Record redacted evidence rather than raw auth diagnostics. Secrets must not appear in command arguments, logs, tests, PRs, artifacts, or shell tracing. Untrusted repository code must not run with an identity more powerful than its approved task.

Actions runs on pull requests and pushes with `contents: read`, credential persistence disabled, and no cloud/admin secrets. The required job performs lint, tests, policy checks, and content-aware scanning of source/history; full SHA-pinned GitHub-owned checkout and hash-pinned binaries avoid a third-party action allowlist dependency. Review changes to control-plane files and scanner configuration carefully; repository administrators ultimately control enforcement.

## Administrative verification snapshot

On **2026-10-19**, repository setup verified [protect-main](https://github.com/The-CarL/engineering-factory/settings/rules/25404390) active on `main`: PRs and resolved conversations required; `Validate factory repo` required from GitHub Actions; force pushes/deletion blocked; no bypass actors; zero required approvals. CODEOWNERS is advisory until a required code-owner review policy is enabled.

Actions default token permissions were read-only; PR creation/approval by Actions disabled; GitHub-owned actions allowed and full commit SHA pinning enforced. Dependabot alerts/security updates, secret scanning, and push protection were enabled. This is a dated administrative snapshot, not a guarantee enforced by these Markdown files; recheck live settings when policy changes or before relying on them.

## Credential and deployment gates

Credential issuance/injection, Cloud environment creation/publishing, provider writes, and live acceptance are separate upcoming gates. See [the checklist](credential-checklist.md). Existing local user sessions are not a mandate to reuse them in automation. Connectors and Cloud CLIs have independent authentication.

App deployments should use native integration or per-app CI roles with narrow OIDC trust where supported. Do not export the factory's execution credentials into app GitHub secrets. Production promotion, deletion, expanded scope, and changes to IAM, organization settings, billing, or DNS need exact user authorization and a reviewable plan.

## Incident and unknown outcomes

On suspected exposure, stop sensitive execution and revoke/rotate via the credential owner. Assess public history, logs, artifacts, and downstream access before an approved cleanup. Never merely delete the visible line and assume the secret safe.

On a timeout or failed mutation, inspect remote state and identity first. Scripts may leave a successfully created repo even when cloning fails; rerun with the same target and visibility. Do not delete repositories/resources, force-push, change visibility, or relax policy as automatic recovery. A stale local lock needs inspection before removal.
