# Security model

## Public harness, private authority

This repo may be read or forked publicly. It contains no live accounts, credentials, state, or private endpoints. Configuration names are public; their values and provider permissions live outside Git. Ignore rules, scanner checks, and instructions reduce mistakes but cannot enforce least privilege on a process holding broad credentials.

Use provider-enforced scopes and exact approved targets. The intended AWS design uses bounded factory roles in the existing account with protected core assets excluded; verify actual effective policies before claiming that boundary. GitHub core content and Vercel core projects must also be outside runtime write scope. The [access matrix](access-matrix.md) documents unresolved scope choices and required effective-policy tests. Before a write, verify identity/target for that selected provider and operation: GitHub owner/repository, Vercel team/project or AWS role/account/region as applicable, plus allowed operations, expiry, budget, revocation owner and rollback. Record redacted evidence rather than raw auth diagnostics. Secrets must not appear in command arguments, logs, tests, PRs, artifacts, or shell tracing. Untrusted repository code must not run with an identity more powerful than its approved task.

Actions runs on pull requests and pushes with `contents: read`, credential persistence disabled, and no cloud/admin secrets. The required job performs lint, tests, policy checks, and content-aware scanning of source/history; full SHA-pinned GitHub-owned checkout and hash-pinned binaries avoid a third-party action allowlist dependency. Review changes to control-plane files and scanner configuration carefully; repository administrators ultimately control enforcement.

## Attribution and shared-account protection

The [provenance standard](../standards/provenance.md) requires stable project/environment IDs, supported creation tags/deployment metadata, exact source/run attribution and private append-only inventory events. Preserve original history and record all created/changed objects, child/untaggable exceptions and cleanup ownership. Tags identify assets; they do not alone authorize mutation. Protect ownership tags from change and prohibit claiming core assets through retagging.

AWS permissions must cover direct and indirect execution, prevent self-escalation and exclude account controls. GitHub repository deletion restrictions do not prevent file removal through commits. Vercel team tokens cover all team projects; project scoping is not a guarantee of deployment-only access. No policy or token has been created or validated by these documents.

## Administrative verification snapshot

On **2026-10-19**, repository setup verified [protect-main](https://github.com/The-CarL/engineering-factory/settings/rules/25404390) active on `main`: PRs and resolved conversations required; `Validate factory repo` required from GitHub Actions; force pushes/deletion blocked; no bypass actors; zero required approvals. CODEOWNERS is advisory until a required code-owner review policy is enabled.

Actions default token permissions were read-only; PR creation/approval by Actions disabled; GitHub-owned actions allowed and full commit SHA pinning enforced. Dependabot alerts/security updates, secret scanning, and push protection were enabled. This is a dated administrative snapshot, not a guarantee enforced by these Markdown files; recheck live settings when policy changes or before relying on them.

## Credential and deployment gates

Credential issuance/injection, environment save/publish/fresh-task acceptance, provider CLI/API reads, effective permission validation and live writes are separate gates. Keep their actual status in private release evidence rather than infer one from another. Follow [runtime contracts and session discipline](../standards/runtime.md). See [the checklist](credential-checklist.md). Existing local user sessions are not a mandate to reuse them in automation. Connectors and Cloud CLIs have independent authentication.

App deployments should use native integration or per-app CI roles with narrow OIDC trust where supported. Do not export the factory's execution credentials into app GitHub secrets. Production promotion, deletion, expanded scope, and changes to IAM, organization settings, billing, or DNS need exact user authorization and a reviewable plan.

## Explicit access exceptions

Use the private [access exception register](../standards/security.md#access-exceptions) when actual authority exceeds the intended standard. Record owner approval, effective actions/resources, remaining core exposure, compensating controls, expiry/review/remediation and evidence. No-delete flags, names/tags, wrapper allowlists and agent instructions cannot establish core exclusion. An exception records exposure without expanding authorized task scope or permitting weakened controls.

## Incident and unknown outcomes

On suspected exposure, stop sensitive execution and revoke/rotate via the credential owner. Assess public history, logs, artifacts, and downstream access before an approved cleanup. Never merely delete the visible line and assume the secret safe.

On a timeout or failed mutation, inspect remote state and identity first. Scripts may leave a successfully created repo even when cloning fails; rerun with the same target and visibility. Do not delete repositories/resources, force-push, change visibility, or relax policy as automatic recovery. A stale local lock needs inspection before removal.
