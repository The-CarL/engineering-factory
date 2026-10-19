# Credential and environment readiness gate

**No credentials, Cloud environment, live repositories or deployments are created by this checklist.** Phase 3 includes GitHub, Vercel and AWS identity preparation. Proceed only when concrete private targets, effective permissions and operations are approved. The [access matrix](access-matrix.md) is the proposed boundary, not a configured control.

## Decisions to record privately before issuance

| Provider | Required decisions/config names | Scope and proof |
|---|---|---|
| GitHub | `FACTORY_GITHUB_OWNER`; user-backed automation identity; selected app repositories; provisioning method; private default | Exclude core/factory-control writes; withhold repository deletion permission; verify creation permission and new-repo coverage separately from content-write scope. |
| Vercel | `FACTORY_VERCEL_TEAM_ID`, `FACTORY_VERCEL_TEAM_SLUG`; existing project or approved provisioning target; app-specific `VERCEL_PROJECT_ID` | Project token for an existing app where supported; team token only when every reachable project is approved. Verify expiry, roles, plan/cost and preview limits. |
| AWS | `FACTORY_AWS_ACCOUNT_ID`, `FACTORY_AWS_REGION`, `FACTORY_AWS_ROLE_NAME`; approved services/actions/resources; protected core inventory | Dedicated factory role(s) in the existing account; exact region/resource/namespace bounds, protected ownership tags, no initial IAM writes or broad role delegation; effective-policy simulation and disposable scope tests. |

For each identity record owner, purpose, exact actions/resources, expiry, injection/environment scope, revocation/rotation, cost limits and redacted evidence. Do not substitute broad personal access when an operation fails. No new GitHub organization, Vercel team/subscription, IAM policy or credential is authorized by this checklist.

GitHub repository deletion and file deletion are different permissions: omitting `delete_repo` on a classic token or `Administration: write` on a fine-grained runtime token does not stop content writes. Exclude core repositories entirely from runtime write scope. Review `Repository creation: write` availability/coverage and whether provisioning needs a separate step. Selected repositories are not a name-prefix filter. Current scripts require user-backed `GET /user` and organization membership inventory; App installation tokens need a reviewed adapter. See the [provider-specific decisions](access-matrix.md).

Before AWS issuance, approve a service-specific policy design from the private protected inventory; account isolation is not available. Review resource-level/tag support, indirect execution and role-passing escalation paths. The initial role must not modify IAM, its own trust/policies/boundary, core assets or account controls. An identity read cannot prove these restrictions.

Before any provider writes, create the private stable project record and provenance inventory described in [the provenance standard](../standards/provenance.md). Verify every deployment path supports metadata or an explicitly reviewed equivalent mapping. Credentials must not grant the ability to claim existing/core assets through retagging.

## Add values outside Git

- Enter secret values directly into the approved Codex vault/environment controls; never into chat, PRs, or `.env.example`. Non-secret target config is also private deployment metadata; keep actual IDs out of this public foundation.
- `GH_TOKEN` is the GitHub CLI's documented environment mechanism; `VERCEL_TOKEN` avoids exposing tokens in CLI arguments. Confirm exact installed CLI support and version before use. Do not `gh auth login --with-token` or persist token files unless that storage is explicitly approved.
- For AWS, prefer a supported short-lived role/session provider. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` are possible session variable names, not an instruction to create a long-lived IAM key. Cloud OIDC connections are Enterprise by-request; verify availability first. Locally signed API requests require real compatibility testing with the chosen secret mechanism.
- Cloud environment variables are readable by task processes. Domain-scoped network secrets substitute over HTTPS 443 without a raw process/file value; they are useful only where the CLI/request supports that flow. Personal-vault credentials must be scoped to the selected environment. [Official configuration guide](https://learn.chatgpt.com/docs/environments/cloud-environments#configure-environment-variables-and-network-secrets).
- Set approved network domains and egress policy for package/tool installation, GitHub clones/API, Vercel API/build flows, and AWS endpoints only as needed. Test support; do not assume arbitrary network access or that a connector grants CLI access.

## Cloud and live acceptance order

1. Review/merge the foundation with required checks passing, then approve the access/provenance design and private target inventory for all three providers.
2. Decide GitHub owner/identity and provisioning versus ongoing scope, Vercel project/team scope, and the AWS same-account bounded role design. Approve expiry, cost limits and exact test operations; issue/inject only reviewed credentials. Do not widen permissions to satisfy a script.
3. Create one factory-linked Cloud environment, verify pinned tools (including AWS CLI), network and each secret mechanism, save and publish. [Setup entry points](setup.md#codex-cloud-gate-not-performed-by-foundation-setup).
4. Start a fresh task; run provider identity/target preflight. Validate effective scopes separately using non-destructive simulation where available and authorized disposable allowed/denied tests; never attempt destructive operations on core assets.
5. Complete the [first phone-only app proof, second-task continuation and recovery proof](mobile-workflow.md). Gate each write on exact approved targets; record project/resource/deployment IDs, source/run metadata and verified HTTPS results privately.
6. Configure app-owned CI/CD through native integration or narrowly trusted OIDC. Verify provenance on that actual deployment path; do not copy the factory's credentials into apps.
7. If a service-specific AWS deployment proof is selected, separately approve its small IaC plan, private state, cost, provenance, rollback/retry and cleanup. AWS identity validation is part of Phase 3 even if this deployment proof runs after the GitHub/Vercel phone proof. DNS remains a separate authorization.

Until these gates pass, Cloud environment, credential compatibility, effective permissions, cross-repo execution, mobile operation and deployment remain unverified.
