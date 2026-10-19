# Provider access design

This is the Phase 3 target design. No credentials, policies, teams or live permission tests are implemented by these documents. Record exact private identifiers and approve operations before issuance. GitHub, Vercel and AWS identity preparation are all in Phase 3; each live write remains a separate bounded gate.

| Provider | Allowed target design | Protected boundary | Pending decisions and evidence |
|---|---|---|---|
| AWS | Dedicated factory role(s) in the existing account; exact approved regions, service/actions and project resource namespaces | Existing/core resources and account administration excluded; no implicit IAM, organization, billing, security, shared DNS/network or cross-account authority | Private protected-resource inventory; service-specific policy/ABAC review; policy simulation plus disposable allowed/denied checks |
| GitHub | Selected factory-managed app repositories for ordinary development; separately bounded repository creation if needed | Core repositories and factory control files outside runtime write scope; repository deletion permission withheld | User-backed identity supported by current scripts; exact token creation permissions and coverage of new repositories; safe content/provisioning scope |
| Vercel | Approved project-scoped token for an existing app; team-scoped provisioning only if all reachable projects are approved | Core projects excluded from the execution identity | Verify team/project token options, roles, expiry, plan/cost; choose sandbox team or separately controlled provisioning |

## AWS: shared account, separate authority

The account is shared with existing infrastructure. Use a dedicated role, never the user's broad personal credentials. Start with an explicit service/action/resource/region allowlist, reserved project namespaces, and an explicit protected-resource inventory. Deny protected mutations as supported, covering updates, replacement, data writes and deletion. A blanket `Delete*` deny does not prevent overwrites or account changes and is not a complete policy.

Review authorization support for every API: resource ARN constraints, request/resource tag conditions, tag-on-create and untaggable/child resources differ across services. Tags plus a name prefix alone do not safely confine an all-service role. Block the factory from retagging existing/core assets into its namespace or removing/changing protected ownership tags. Do not adopt assets without separate authorization. Apply the [provenance standard](../standards/provenance.md).

Initially permit no IAM writes, self-policy/permissions-boundary/trust modification, broad `sts:AssumeRole`, or `iam:PassRole`. If a later approved service needs delegation, allow only exact preapproved role ARNs, appropriate service conditions and bounded execution-role permissions. Tag conditions do not reliably constrain `iam:PassRole`. Scope CloudFormation stack operations and execution roles too; indirect deployment must not escape the caller's approved boundary.

Prepare actual policy JSON only after the account, regions, services, resource inventory and operations are approved. Review effective policies, boundaries/session constraints and resource policies; explicit denies override allows. Validate with non-destructive simulation where supported, then separately authorized disposable resources for positive/negative tests. Never probe a core asset by attempting a destructive operation. [AWS tag conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_tags.html), [policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html).

## GitHub: deletion versus content writes

A classic token can omit `delete_repo`, blocking the repository deletion endpoint. Ordinary fine-grained runtime credentials should omit `Administration: write`, the permission required by that endpoint. This does not protect files: `Contents: write` permits commits that remove or replace content. Core repositories must be excluded from write scope, rather than relying on an instruction not to delete them. Do not grant all-personal-repository write access by default. [Deletion permissions](https://docs.github.com/en/rest/repos/repos#delete-a-repository), [token scoping](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

Repository creation and ongoing work may require separate credentials or an explicitly controlled provisioning step. The current creation endpoint documents `Repository creation: write` as an alternative to administration permission; verify dashboard availability and new-repository coverage before choosing the exact credential. Selected-repository scopes are not arbitrary name-prefix filters. No new organization or identity is created by this design. [Creation permissions](https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user).

Current scripts require a user-backed `GET /user` identity and organization user membership inventory; App installation tokens need a reviewed adapter. Read the public factory without giving runtime credentials authority to rewrite its controls. Provider scopes and repository protections remain separate controls.

## Vercel: scope before convenience

Resource scoping is a token setup choice: choose the approved team or project and expiry, then verify installed CLI support and live readback. Availability, roles and any subscription cost need checking before setup; no new team or subscription is approved here.

A team-scoped token reaches all projects in that team. It is unsuitable when core projects in the same team must be excluded. A project-scoped token denies access to other projects and user/team resources, but cannot provision unrelated projects. Automatic project creation therefore needs an isolated approved team or a separate bounded provisioning decision. A new sandbox team is an option, not a requirement already accepted by the user. Resource scope does not guarantee deployment-only or no-delete permissions inside the authorized project. [Vercel token scopes](https://vercel.com/docs/accounts/access-tokens).

Project-scoped tokens deny user/team-level requests, so the current `whoami`/team-based preflight may not work with them. If needed, implement and review a narrow exact-project-read adapter before credential acceptance. Do not broaden a token to satisfy the existing script. No adapter is implemented in this documentation change.

Map each Vercel project and deployment to the stable factory project ID through verified deployment metadata and the private inventory. Vercel does not need AWS-style project tags to satisfy [provenance](../standards/provenance.md), but every actual deployment path must preserve the association.
