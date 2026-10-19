# Secure development

- Keep public source separate from private execution identities. Default new repos to private. Review publishing separately; changing visibility is not a retry strategy.
- Use least privilege, target-scoped identities, short expiry, and revocation/rotation procedures. Prefer GitHub Apps or fine-grained access and short-lived AWS roles when suitable. Verify actual product/account support before choosing a credential mechanism.
- Exclude core resources/repos/projects from runtime mutation scope, including updates and content replacement. Repository-delete restrictions, tags and project names alone do not provide this boundary. Review effective service/resource permissions and role delegation; see [the access design](../docs/access-matrix.md).
- Protect project ownership tags and creation attribution from removal/change. Prohibit claiming existing assets through retagging. Apply [provenance](provenance.md), private inventory and provider audit correlation; mutable metadata is not an authorization boundary or tamperproof audit log.
- Never log secrets or pass token literals in command arguments. Use documented CLI environment/credential providers. Do not upload raw provider diagnostics, environment dumps, full auth responses, or state to PRs.
- Treat generated code and dependencies as untrusted. Review code before running it with credentials. Run untrusted PR checks with a read-only GitHub token and no cloud/admin secrets; do not use `pull_request_target` to execute PR code.
- Pin Actions to full commit SHAs and downloaded tools to reviewed versions and hashes. Content-aware scanning supplements provider push protection; filenames alone cannot detect a secret in ordinary source.
- Review scanner suppressions narrowly. Do not allowlist broad paths, whole histories, or live values to get CI green. On exposure, revoke first, assess logs/history/artifacts, then remediate under an approved plan.
- Provider permissions enforce the boundary. AGENTS instructions, preflight scripts, default-private flags, and cost estimates guide behavior but cannot contain a compromised process with an overpowered identity.

## Access exceptions

The intended standard excludes core assets from runtime mutation scope. If effective access is broader, record the actual gap in a private reviewed exception register before relying on that identity. Do not describe intended exclusions as configured controls. The register must contain:

- Exception reference, credential/role purpose, owner approval and approved task scope.
- Effective actions/resources and evidence, including remaining core-asset exposure and indirect authority.
- Compensating controls and their limits, expiry/review date, remediation owner/plan and verification evidence.

Keep actual approvals, IDs and policies outside public Git. An exception documents accepted exposure; it does not authorize extra work, broaden a task or weaken controls. Stricter task scope continues to apply. No-delete flags, names/tags, agent instructions and wrapper allowlists do not establish core exclusion. Review [credential transport and AWS session discipline](runtime.md) separately from effective permissions.
