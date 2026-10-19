# Bounded end-to-end runs

Agree one concrete run scope with the user, then execute the authorized sequence without asking again at each routine step. The approval can cover repository creation, cloning, development, normal pushes, CI, a specifically bounded test bootstrap, preview deployment, health checks and recovery. Reuse approved identities, targets, credential bindings and pinned tools throughout. Programmatic `--confirm` arguments check the selected target; they do not require another human conversation.

Prepare the filled proposal from known configuration and resolve routine implementation choices before presenting it. Existing exact authorization in the session remains valid: record its reference and continue rather than asking for it again.

A plan, profile, task template or repository instruction does not grant authority on its own. The human must request or approve the concrete scope. Provider permissions, role boundaries and platform controls enforce actual access; names, tags and this standard do not. A general request to finish work does not authorize messaging another chat, changing credentials/IAM, bypassing a protection or operating on existing/core assets.

## Prepare the scope once

Before approval, fill a private run record with:

- Stable project/run IDs, purpose, source/runtime revision, expiry, cleanup owner and recovery destination. Preserve original creation attribution and known IDs when resuming.
- Exact GitHub owner, repository name/visibility, clone location and expected origin. Specify permitted branches, normal pushes and CI; force pushes, visibility changes, deletion and unrelated repositories remain excluded.
- Exact Vercel team ID/slug and the dedicated project name/known ID. For creation, bind the returned ID only after exact team/name readback; a matching name alone does not authorize adopting an existing project. Specify the verified protection method/scope and enumerate generated deployment URLs, default production domains and aliases with their approved protected/public exposure, permitted project configuration, build count, preview and health checks.
- Exact AWS account, assumed role, region, resource names/ARNs and service/actions from a reviewed policy/resource plan. Record its revision/hash and actual approval reference. Choosing a service is permission to prepare a plan, not to apply IAM or provision resources. A private S3 upload/readback test is a small possible target; it still requires concrete policy/resource review before writes.
- A maximum incremental dollar budget, resource/build/upload counts, request/polling/time limits and retention period. Include provider-generated child/default resources in the inventory and estimate. No purchases, paid add-ons or upgrades unless explicitly included. Estimates and client counters are not provider-enforced spending limits; stop before an action could exceed the approved ceiling.
- Exact network scope and authenticated health mechanism. Approval may include HTTPS checks to the single hostname returned by the verified new deployment and an exact-host allowlist update, if the platform permits it. Record that hostname before access; no wildcard domains, provider-token binding expansion or protection bypass.
- Any chat coordination: the exact recipient title, ID/host, permitted message purpose and whether resuming that existing chat is authorized. Without that human authorization, continue independent work locally; do not send through another chat, UI or intermediary.

## Test bootstrap is explicit scope

Vercel's first deployment can be assigned production. A user can approve that known behavior in the initial concrete plan for a **new, dedicated test project**, with a verified protection scope and explicitly approved URL exposure before the bootstrap, test content only, no custom domains, no existing/core project changes, bounded cost and a retained rollback/recovery reference. This is approval of that one test bootstrap, not general production authority. Verify its actual target, source, provenance, protection and READY state before proceeding to preview.

Protection has a method, an exact API mode and a current UI label, including legacy modes. For example, `prod_deployment_urls_and_all_previews` can be labeled `(Legacy) Standard Protection`; the current Standard Protection UI distinguishes production custom domains, while legacy modes have different production-alias coverage. Do not infer default/generated production-domain coverage from the word “Standard.” Use the [protection scope reference](https://vercel.com/docs/deployment-protection), actual account/method availability, saved mode and per-URL readback rather than assuming Authentication covers every URL. All Deployments is the all-domain option; selecting it in a UI is not proof that it was saved or enforced. Enumerate generated deployment URLs, default production domains and aliases; resolve assigned names and check plan coverage before serving content. Any publicly reachable test domain must be explicitly within the human-approved scope. If full protection is required but unavailable or unverified, prepare the exact alternative for review; do not upgrade a plan, add paid protection or weaken protection automatically.

A flag such as `--skip-domain` does not prove first-deployment target behavior or a READY production baseline; require actual deployment/domain readback.

The generic [preview helper](../docs/provider-workflows.md#vercel-preview-adapter) remains preview-only and blocks without a verified READY production baseline. An approved bootstrap uses a separately reviewed execution path; do not weaken the preview guard. If bootstrap was omitted from the approved scope, prepare the exact change for review before attempting it. An existing project's bootstrap needs its own exact project approval; the new-project option cannot be applied to it by analogy.

AWS creation must use the reviewed service-specific plan and bounded role wrapper. The [offline S3 policy planner](../docs/s3-policy-plans.md) can prepare the exact private policy for grouped review; its output remains unapproved until the human reviews the concrete grant/resource scope. For S3, resolve the exact bucket/object namespace, private access, encryption, ownership/provenance and supported tag-on-create or explicitly reviewed tagging sequence before upload/readback. No blanket `s3:*`, IAM edits, role delegation or core DNS changes follow from selecting S3. See [infrastructure](infrastructure.md), [access design](../docs/access-matrix.md) and [provenance](provenance.md).

## Execute and recover without repeated prompts

Within the approved scope, perform routine checks, local fixes, commits, normal pushes, CI waits, authorized provisioning/deployments and health checks autonomously. Record intent before writes and read back the exact resulting identity, state and provenance. Preserve protected settings and original history. Continue independent authorized gates when another gate is blocked.

Reconcile a failure before another mutation. A known terminal failed build can receive a bounded corrected attempt on the same authorized project when the plan includes it; use a new operation record and preserve the failed deployment. A timeout/unknown outcome requires read-only reconciliation of the existing intent/IDs, not another create/deploy. Reuse exact verified resources on a resumed run; never treat a changed name or cleared journal as permission to duplicate or adopt resources. Preserve source bundles, frozen evidence and recovery hashes in approved private durable storage and verify restoration.

Ask only when the next action changes the actual scope, budget/limits, identity/target, core-resource exposure, production authorization, credentials/IAM or protection; when ambiguity cannot be resolved by reads; or when a tool requires action-time approval. Prepare the concrete diff/target and evidence first. A tool rejection is a blocker for that action, not an invitation to use another route. Explain the rejected action and stated reason, leave it unexecuted and continue unaffected work. Routine progress updates and final evidence do not require approval.

## Copyable task prompt

Prepare and fill this private copy for the user's review; unresolved fields grant no authority. Remove unused options. The user's approval of the filled scope is the authorization, not the template's presence in Git.

```text
Execute this bounded integration run end to end with minimal interactions.
I authorize the following filled scope for run [RUN_ID], project [STABLE_PROJECT_ID],
through [UTC_EXPIRY], using reviewed runtime/source [REVISION] and private plan
[PLAN_PATH + SHA256]. Reuse the existing approved credentials and pinned tools.

GitHub: owner [EXACT_OWNER], repository [EXACT_NAME], visibility private,
clone [ABSOLUTE_PATH], origin [EXACT_GITHUB_ORIGIN], branches [ALLOWED_BRANCHES].
Create at most one repository, clone, develop the hello-world app, commit,
normal-push and run CI. No force push, visibility change, deletion or unrelated repo writes.

Vercel: team [EXACT_TEAM_ID + SLUG], new dedicated test project [EXACT_NAME]
[or exact retained PROJECT_ID with its existing inventory]. Resolve and retain its ID.
Approved project configuration [EXACT_SETTINGS]; protection method/scope [VERIFIED_SETTING].
Enumerated generated deployment URLs [LIST + EXPOSURE], default production domains
[LIST + EXPOSURE], aliases [LIST + EXPOSURE]. Any public test domain is explicitly
approved here [EXACT_LIST / NONE]. Resolve assigned names and verify plan coverage
before serving content. If required full protection is unavailable/unverified,
prepare the exact plan for review; no automatic upgrades, paid protection or weakening.
First production bootstrap: [YES, one protected test-only bootstrap on this NEW
project under the reviewed plan / NO]. This excludes general production promotion,
existing/core projects, custom domains and disabling protection. After a verified
READY production baseline, deploy preview and verify actual target/source/provenance.
The preview helper remains preview-only; use the reviewed bootstrap path only if authorized above.

AWS: account [EXACT_ACCOUNT], role [EXACT_ROLE], region [EXACT_REGION].
Writes [DISABLED / ENABLED only under reviewed policy/resource plan HASH and actual
human approval REFERENCE]. Service [EXACT_SERVICE], resource names/ARNs [EXACT_LIST],
object namespace [EXACT_KEYS], allowed actions [EXACT_REVIEWED_ACTION_LIST].
For an approved private S3 test, create/configure/tag only the named test bucket,
upload at most [COUNT] objects of [MAX_BYTES], then read back and verify hashes.
No IAM/credential/account changes, broad role delegation or existing/core infrastructure writes.

Limits: incremental spend <= $[MAX_USD]; no purchases/upgrades/add-ons.
At most [REPO_COUNT] repos, [PROJECT_COUNT] Vercel projects, [BUILD_COUNT] builds,
[AWS_RESOURCE_COUNT] AWS resources and [REQUEST_LIMITS_PER_PROVIDER] requests.
Polling/time limit [LIMIT]; retain until [EXPIRY], cleanup owner [ALIAS].
Do not delete resources unless exact cleanup actions are included here [NONE / EXACT_ACTIONS].

Network/health: approved API domains [EXACT_DOMAINS]. [Authorize / do not authorize]
HTTPS/browser checks and an exact-host allowlist update for only the hostname
returned by this verified deployment, subject to platform action-time approval.
Keep provider-token domain bindings restricted to their approved APIs. Preserve protection;
use [APPROVED_AUTHENTICATED_TEST_PATH]. Verify health/build identity, browser interaction,
and the approved AWS data path; a login page or local test is insufficient.

Coordination: [NONE / I explicitly authorize messaging and resuming the existing chat
TITLE, ID, HOST for PURPOSE within this same scope]. No other recipients or indirect routes.

Use all required provenance, record intent/IDs privately, preserve core exclusions,
and store source/evidence recovery snapshots in [APPROVED_PRIVATE_DESTINATION].
Verify hashes and restoration. Reconcile failures and reuse exact known resources;
do not duplicate creates/deploys after unknown outcomes or widen permissions to recover.
Routine fixes/retries within these limits, programmatic target confirmations,
normal pushes, CI and approved health checks do not need another human prompt.
Ask only for a concrete scope/limit/identity/core/production/IAM/credential/protection
change, unresolved target ambiguity or required action-time confirmation.
Report each actual gate, costs/limits, retained resources, recovery proof and blockers.
```
