# Bounded end-to-end runs

Agree one concrete scope for the requested frontend/backend project, then execute authorized routine steps without repeated approval. It can cover repository creation, cloning, instruction seeding, app development, normal pushes, independent CI/CD, an explicit initial release, preview deployment, browser/API verification and recovery. Reuse approved identities, targets, credential bindings and pinned tools. Programmatic `--confirm` arguments check a target, not another human conversation.

Prepare the proposal from known configuration and resolve routine implementation choices first. Existing exact authorization in the session remains valid; record its reference instead of asking again. A plan/profile/template alone grants no authority. Provider permissions and platform controls enforce actual access; names, tags and instructions do not. The primary [new-project workflow and prompt](../docs/new-project.md) describe the user flow; this standard defines the scope fields.

## Prepare the scope once

Keep actual values in a private project/run record:

- Product/user flow and real frontend/backend contract, selected workload, source/runtime revision, stable project/run IDs, cleanup owner and recovery destination.
- Exact GitHub owner/repository/visibility, independent path/origin, allowed branches, normal pushes and CI/CD operations. No force push, deletion, visibility changes or unrelated repositories by implication.
- Exact deployment provider targets and initial-release scope, including Vercel team/project name/known ID where used. Bind a new returned ID only after exact name/ownership readback; matching names do not authorize adopting existing assets.
- Actual protection method/API mode/current UI label and generated/default/custom domain or alias coverage, with explicit public exposure. No wildcard egress, provider-token recipient expansion, protection bypass or paid upgrade by implication.
- Selected backend workload/services and exact AWS/other account/role/region/resources/actions/IaC profile, if needed. Installing credentials does not select a workload or authorize service writes. Review actual policy changes before granting/applying them; current reads do not establish deployment capability.
- Incremental budget, resource/build/request/polling/time limits and retention. Include child/default resources and costs. Estimates/counters are not hard provider spending limits; stop before an action could exceed scope.
- Exact approved network/health mechanisms. A scope may cover HTTPS checks and permitted exact-host egress for the single verified deployment hostname; record it before access, keep provider tokens bound to approved APIs, and retain required action-time approval.
- Any other-chat coordination: exact recipient title/ID/host, purpose and resume authority from the human. Otherwise continue here; a general request to finish does not authorize messaging another chat or using an intermediary.

## First-deployment scope

A new Vercel project's first deployment can be classified as production. The initial concrete scope may explicitly authorize that initial app release in a new dedicated project, with intended content, exact protection/public exposure, bounded cost and recovery/rollback criteria. This is not general production-promotion authority or permission to change existing/core projects. Verify actual source, target, saved protection, domain coverage, provenance and READY state.

Read exact API modes and current/legacy UI labels together. `prod_deployment_urls_and_all_previews` can be labeled `(Legacy) Standard Protection`; current Standard Protection distinguishes production custom domains, while legacy modes cover production aliases differently. Do not infer generated/default domain protection from “Standard.” Follow the [current protection reference](https://vercel.com/docs/deployment-protection) and actual saved settings/per-URL evidence. Any public URL must be in the approved scope; unverified full protection requires a concrete reviewed alternative, not an automatic upgrade or weakened setting.

The [preview helper](../docs/provider-workflows.md#vercel-preview-adapter) stays preview-only and requires a verified READY production baseline. Follow the [new-project/initial-release contract](../docs/provider-workflows.md#new-vercel-project-and-initial-release) with reviewed official CLI/REST operations; no extra factory bootstrap script or chat handoff is required. The helper does not automate or authorize those operations. Include their exact scope in the initial plan. If excluded, prepare the exact change before asking for approval. Flags such as `--skip-domain` do not prove target behavior or baseline readiness.

## Execute and recover

Within scope, perform local fixes, commits, normal pushes, CI waits, agreed provisioning/deployments and full-stack health checks autonomously. Verify identities/targets before provider actions; record intent and reconcile exact outcomes/provenance. Continue independent authorized gates when another is blocked.

A known terminal failed deployment may receive a bounded corrected attempt when included; keep its history and use a new operation record. Unknown outcomes require read-only reconciliation, not another create/deploy. Resume exact verified resources; never clear a journal or change a name to duplicate or adopt them. Preserve source and private inventory/recovery artifacts durably and verify restoration.

Ask only for an actual scope/limit/identity/target/core-exposure/production/credential/IAM/protection change, ambiguity unresolved by reads, or required action-time approval. Prepare the concrete diff/target and evidence first. A tool rejection blocks that action; explain its stated reason and continue unaffected work without using another route. No compulsory chat handoff or routine per-step approval follows from this standard.
