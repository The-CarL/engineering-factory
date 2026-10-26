# Factory history and lessons

Recorded **2026-10-26** from the October setup investigations, Cloud test reports and first complete application build/cleanup. This is a redacted engineering retrospective, not a fresh provider audit. The linked source changes were inspected when this record was written; historical live outcomes below are attributed to the reported run.

Use this area to understand why the factory works this way and avoid repeating failed approaches. Current instructions remain in [AGENTS.md](../../AGENTS.md), [standards](../../standards/) and the operating guides. [Design decisions](../design/README.md) records the resulting choices and proposals. These records grant no permission to change providers, credentials, plans or applications.

## Learning index

| # | Learning | Record |
|---|---|---|
| 1 | A PAT selected locally may not be the credential GitHub receives through a managed route. Changing `gh` to Python did not resolve the observed discrepancy. | [GitHub authentication](github-authentication.md#credential-selection-versus-effective-authentication) |
| 2 | Repository creation, normal development, settings administration, feature entitlement and human-only bypass are different capabilities. | [GitHub settings](github-authentication.md#repository-settings-and-protection) |
| 3 | Network allowlists, shell execution, credential bindings, provider permissions and application success require different evidence. Rebuilding an environment does not prove any of them. | [Cloud execution](cloud-execution.md) |
| 4 | A merged checkout is not necessarily the installed runtime, published snapshot or instruction revision used by a fresh session. | [Runtime drift](cloud-execution.md#source-runtime-and-session-drift) |
| 5 | AWS app autonomy needs real application grants plus core/account protections; a read-only wrapper is not the intended permission model. Explicit denies and indirect execution need review together. | [AWS permissions](aws-and-dns.md#application-authority-and-core-protection) |
| 6 | IAM named-role reads and failed CloudFormation recovery exposed a gap even with the intended role path and application boundary. Source repair and live activation are separate. | [IAM lookup and recovery](aws-and-dns.md#role-lookup-and-cloudformation-recovery) |
| 7 | A known exact public DNS zone avoids unnecessary global discovery. DNS ownership and allowed names are independent of Vercel/AWS hosting. | [DNS](aws-and-dns.md#dns-discovery-names-and-hosting) |
| 8 | A test fixture answered CORS preflight that the real Lambda did not implement. Local/CI success did not establish the hosted browser flow. | [Full application run](full-application-run.md#integration-and-test-parity) |
| 9 | Tool routes, worktrees and native identifiers must agree with real provider behavior. Some helper fixes are merged; others remain local or unresolved. | [Tooling lessons](full-application-run.md#tooling-friction-and-reusable-fixes) |
| 10 | Cleanup includes retained data, external roles, DNS and public content, and requires Carlo's reviewed approval. A retired link is not a removed publication. | [Cleanup](full-application-run.md#publication-and-comprehensive-cleanup) |
| 11 | Apps own their records. The factory is a general build-manager workspace with optional providers and referenced design styles, not a central app registry or fixed demo pipeline. | [Design decisions](../design/README.md) |

## Unresolved and deferred work

These are dated findings, not claims that every current environment still fails. Update a row with new evidence when its prerequisite changes; do not repeat the same experiment indefinitely.

| ID | State on 2026-10-26 | What closes it |
|---|---|---|
| O1 | **Unresolved:** managed GitHub requests authenticated despite an invalid supplied credential; the responsible internal component is unproven. | Supported routing inspection or a supported transport whose credential isolation is demonstrated. Keep repository creation manual meanwhile. |
| O2 | **Proposed / blocked:** automatic repo settings with human-only bypass has no accepted, proven identity/entitlement/setup path. Settings writes were not tested in the latest inspection. | Resolve private-repo entitlement, actual administrative transport and distinct automation authority, then review and verify the chosen protection mechanism. [Design proposal](../design/repository-settings.md). |
| O3 | **Merged source; activation unverified here:** paired IAM role-lookup correction. | Separately authorized activation in the documented safe order, followed by the affected application operation under the runner. Simulations alone do not close it. |
| O4 | **Open compatibility issue:** Vercel project creation/readback succeeded, but the wrapper rejected an omitted `publicSource` field. | Review the provider response contract and implement meaningful validation/reconciliation without treating omission as proof of the desired setting or retrying creation blindly. |
| O5 | **App-local fixes, promotion unverified:** teardown helper executable permission, Vercel HTTP status parsing and bounded domain-fetch retries. | Locate the actual code, reproduce the relevant defect, and promote only fixes needed by shared tooling with appropriate checks. Do not claim these all landed in the factory. |
| O6 | **Per-host acceptance required:** repeated environment edit/start failures had no established common cause. Newer merged guidance does not prove a refreshed runtime or fresh-session access. | Verify the intended revision and real app path on the selected host/client. Preserve dated evidence and do not call repository checks environment acceptance. |
| O7 | **Reopened by Carlo, 2026-10-26:** the previously deferred product/design work now has shared [co-architecture guidance](../../standards/product-architecture.md). | Adopt the standard through the real client instruction path and verify proportionate product/design judgment and continuation. More specific workflow/tooling remains undecided; no mandatory wizard or lifecycle taxonomy is introduced. |

## Maintaining this record

Add a dated entry when a failure changes a design or exposes a reusable gap. Include the observed behavior, interpretation limits, decision, source fix if any, activation status and next discriminating action. Preserve an earlier observation when adding a later resolution; a successful workaround does not erase the original failure.

Link canonical standards instead of maintaining another operational manual. Distinguish **reported live evidence**, **inspected source**, **simulation**, **proposal** and **unverified rollout**. A merged PR establishes source history, not provider activation or current runtime behavior.

Keep credentials, credential suffixes, account/team/zone/resource identifiers, private repository details and raw diagnostic payloads out of this public history. Detailed logs, inventories, authorization records and application evidence stay in the relevant app's approved records. This area is not a replacement for app-owned continuity or a central project-tracking repository.
