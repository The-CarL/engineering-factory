# Credential and environment readiness gate

**Stop here after the foundation PR is reviewed. No credentials, Cloud environment, live repos, or deployments are created by this checklist.** Proceed only when the user authorizes the concrete targets/operations. GitHub/Vercel go first; AWS can wait.

## Decisions to record privately before issuance

| Provider | Required decisions/config names | Scope and proof |
|---|---|---|
| GitHub | `FACTORY_GITHUB_OWNER`; automation identity; repository naming policy; private default | Approved owner only; create/push/PR permissions actually required; determine GitHub App/fine-grained token capabilities and repository-creation limits. An identity read or token label does not prove these permissions. |
| Vercel | `FACTORY_VERCEL_TEAM_ID`, `FACTORY_VERCEL_TEAM_SLUG`; dedicated sandbox project/naming; app-specific `VERCEL_PROJECT_ID` when known | Approved sandbox team/project, preview only, deployment limits, allowed integration actions; inspect the linked project in the app directory before consequential actions. |
| AWS (optional) | `FACTORY_AWS_ACCOUNT_ID`, `FACTORY_AWS_REGION`, `FACTORY_AWS_ROLE_NAME`; approved services/resources | Dedicated sandbox assumed role, expiry, bounded IAM/trust/region/service permissions, no escalation or production, user-approved cost ceiling and alerts/quotas. Identity checks do not validate these bounds. |

For each identity: record creator/owner, purpose, exact actions/resources, expiry, where injected, which environment receives it, revocation/rotation method, and redacted evidence. Check provider capabilities at issuance; a fine-grained token or team token may not support the planned operation/scope. The initial scripts require a user-backed `gh` identity (`GET /user` and, for organizations, user membership inventory); a GitHub App installation token does not work as-is. Evaluate a dedicated automation user with an appropriately scoped token, or add a reviewed App adapter later. Use stronger isolation or narrower operations if needed, rather than broadening access by default.

## Add values outside Git

- Enter secret values directly into the approved Codex vault/environment controls; never into chat, PRs, or `.env.example`. Non-secret target config is also private deployment metadata; keep actual IDs out of this public foundation.
- `GH_TOKEN` is the GitHub CLI's documented environment mechanism; `VERCEL_TOKEN` avoids exposing tokens in CLI arguments. Confirm exact installed CLI support and version before use. Do not `gh auth login --with-token` or persist token files unless that storage is explicitly approved.
- For AWS, prefer a supported short-lived role/session provider. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` are possible session variable names, not an instruction to create a long-lived IAM key. Cloud OIDC connections are Enterprise by-request; verify availability first. Locally signed API requests require real compatibility testing with the chosen secret mechanism.
- Cloud environment variables are readable by task processes. Domain-scoped network secrets substitute over HTTPS 443 without a raw process/file value; they are useful only where the CLI/request supports that flow. Personal-vault credentials must be scoped to the selected environment. [Official configuration guide](https://learn.chatgpt.com/docs/environments/cloud-environments#configure-environment-variables-and-network-secrets).
- Set approved network domains and egress policy for package/tool installation, GitHub clones/API, Vercel API/build flows, and AWS endpoints only as needed. Test support; do not assume arbitrary network access or that a connector grants CLI access.

## Cloud and live acceptance order

1. Review/merge the foundation with required checks passing.
2. Agree on GitHub owner/identity and Vercel sandbox scopes, expiry, billing bounds, and allowed test writes. Issue/inject only those credentials.
3. Create one factory-linked Cloud environment, verify pinned tool installation, network and secret compatibility, save and publish. [Setup entry points](setup.md#codex-cloud-gate-not-performed-by-foundation-setup).
4. Start a fresh task; run provider preflight. Inspect provider policy/scope separately; perform only the bounded operations authorized for the test.
5. Complete the [first phone-only app proof, second-task continuation, and recovery proof](mobile-workflow.md), recording source commit and verified HTTPS result without secrets.
6. Configure app-owned CI/CD through native integration or narrowly trusted OIDC; do not copy the factory's credentials into apps.
7. If requested later, scope AWS separately before issuing/injecting an AWS identity and running a minimal bounded IaC proof. Include private state, estimated cost, tags, rollback, expiry/cleanup, and DNS as a separate authorization.

Until these gates pass, Cloud environment, live CLI access, write permissions, cross-repo execution, mobile operation, and deployment remain unverified.
