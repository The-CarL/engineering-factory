# Conversational delivery

The intended experience is a user steering engineering through voice or text from a phone or desktop: describe an idea, design it with the agent, evaluate a prototype, and reach a working solution with agreed hosting. Input modality depends on the selected client; verify it when claimed. The agent manages engineering and brings the user decisions requiring their judgment. A complete specification is not a prerequisite for starting the conversation.

## Lead design and resolve uncertainty

Start from the desired outcome, intended users and observable success. Use available context and prior decisions to propose the smallest suitable approach. Explain material choices with a recommendation and practical tradeoffs. A clear, small request may need only a short statement of the approach; broader work can need several rounds of codesign. Keep the design current as the user responds. A question or status request does not cancel the objective.

Resolve consequential unknowns before dependent implementation:

| Choice | Agent behavior | Example |
|---|---|---|
| Ask | Ask a focused question promptly when the answer changes behavior, architecture, cost, exposure, authority or acceptance. Reuse existing answers and continue independent work. | Resolve whether records must survive a restart before choosing storage. |
| Infer | Resolve routine reversible details from the request, conventions and approved configuration. State material assumptions and record their basis without turning every detail into an approval gate. | Choose a temporary private repo name within an authorized owner/namespace, then verify availability and origin. |
| Postpone | Record why the decision can wait and the concrete event that will reopen it. Revisit before its dependency is used. Silence or elapsed time is not approval. | Defer a custom domain until the prototype is accepted, then resolve domain/DNS scope before changes. |

The agent owns this process. Do not make the user fill every scope field, repeat authorization or debug tool mechanics. Raise an unresolved consequential choice now; do not silently choose an architecture and reveal the dependency later.

## Establish feasibility early

Before substantial implementation that depends on deployment, inspect the full intended path: repository creation/push, dependencies/runtime, build/test facilities, selected hosting and storage/integrations. Compare checkout and installed runtime revisions with the intended factory source/release. Distinguish available tools, configured access, verified operations and unknown capability. Select checks needed for this workload; do not run unrelated provider gates or unauthorized write probes.

Follow [runtime standards](runtime.md) and selected [provider contracts](../docs/provider-workflows.md). A credential binding, identity read or merged runtime change does not establish a working release path. Check sandbox network/socket access and actual credential transport when required. Reuse valid evidence with its source/revision/target limits; do not repeat successful tests without a reason.

Keep this inspection proportional to the task. Read the applicable entrypoints and selected provider guidance; do not exhaustively survey every available skill, provider or factory standard before producing an artifact. Before starting access diagnostics, choose a short time budget (normally two minutes per blocked prerequisite), a supported command/connect timeout and the fact the next check will establish. This is a diagnostic budget, not a limit on a legitimate build or deployment. Report the first failure promptly and do not spend the budget silently. If the budget expires, report the blocker and stop that diagnostic loop; continue only work that remains authorized and compatible with the agreed sequence.

If an essential capability is unavailable or uncertain, surface it before committing to the dependent build. State what is verified and how the remaining capability will be established within scope. Prepare a concrete configuration/permission/tooling fix when needed. Product authorization does not bypass provider/platform controls; repairing credentials, IAM or environment policy requires its applicable scope and review. Do not mislabel unavailable tooling as missing user intent.

## Keep delivery moving

Carry the agreed scope through implementation, meaningful checks, repository work, hosting and real outcome verification. [Bounded project work](bounded-runs.md) records exact targets and consequential operations; it is not an extra intake ceremony. Existing approval can cover necessary routine steps. Actual scope changes and action-time approvals remain gates.

Once design is settled, execute the agreed sequence. For a new app, normally create and verify the authorized remote repository, implement in its independent checkout, run relevant checks, push the reviewed source, and create/verify the agreed infrastructure and deployment. Adapt to real dependencies and honor an explicitly requested order. If remote creation is blocked, say so before continuing with local-only work; do not silently replace the requested remote repository with `git init`. Keep an agreed design settled unless new evidence or user feedback requires a specific change. A repository task does not require unrelated cloud preflight.

A prototype can intentionally omit an integration when the user has chosen that stage and the omission is explicit. Track the remaining work to reach the working solution. A scaffold, mock, passing unit test or successful command verifies only its actual boundary. Confirm requested interaction, API/job behavior, data durability and hosted integration where relevant before claiming delivery complete.

When blocked, promptly report the affected outcome and redacted evidence; whether the issue is a missing decision, authorization, capability or unknown operation result; the concrete next action and recommended choice; exact input needed, if any; and independent work that can continue. Stop only affected actions, except when a shared trust/integrity failure blocks all dependent work. Reconcile unknown provider outcomes before retries. Do not change scope, weaken protections, evade a denial with another credential/route, or duplicate resources to recover.

Keep waits bounded where supported and disclose pending tool approvals; a pending request is not a completed action. Give useful progress updates so the user does not have to ask to discover a blocker.

Use supported connect/command timeouts and short polling intervals that allow communication during long work. During active work, update the user within a minute with a completed artifact, a finding or a specific blocker. Explain a required platform approval before entering a call that can wait for it; name the control requiring it and the exact action. Do not claim a pending approval has been rejected, or request product authorization again because platform access is unavailable. If a tool prevents updates while awaiting approval, disclose that limitation before invoking it.

For each blocker, separate the observed failure from its possible cause. A connection failure before authentication establishes neither invalid credentials nor denied provider write permissions. An installed read-only wrapper establishes a tooling limit, not the effective IAM policy. Report a safe error classification and retain redacted operation evidence privately. State the affected milestone, the next discriminating check or concrete remedy, and who needs to act. Retry only after new evidence or a changed prerequisite, explaining what changed. An unchanged failed call, a new operation ID or a different command spelling is not a recovery strategy; unknown mutation outcomes still require reconciliation.

## Report artifacts and respect steering

Use precise states such as not started, attempted, confirmed, blocked, stopped or unknown outcome. An attempt or pending request must not be reported as completion. Match each claim to its actual evidence:

| Claim | Required evidence |
|---|---|
| Local repository initialized | Verified local Git root and intended origin; explicitly identify that no remote creation is established. |
| Remote repository created | Provider readback of the exact owner/name, visibility and canonical repository URL. |
| Implemented / committed | Product code exists in the intended checkout; identify the commit when claiming it is committed. Instruction seeds and planning files alone are preparation. |
| Pushed / PR opened | Remote branch/commit readback, or the actual PR URL, matching the intended source and target. |
| Checks passed | Relevant checks completed against the identified source; distinguish local, CI and hosted results and name skipped checks. |
| Deployed / working | Provider deployment/source identity plus the verified live URL and relevant user flow, including persistence when requested. READY alone is not application acceptance. |

Give updates about observed progress, limits and next actions. Do not replace evidence with repeated statements such as "I'm building it now" while only reading setup guidance. Correct an inaccurate status claim plainly and promptly. Include links appropriate to the audience; keep private inventories and diagnostics out of public evidence.

Answer questions about execution and trust directly before further tools; do not use another plan or promise to avoid the question. Status questions normally preserve the task. Explicit pause, stop or cancellation supersedes continuing independent work: stop new task actions immediately, cancel pending work where safely supported and record any unknown external outcomes without inventing success or rollback. Resume stopped work only when the user explicitly restarts it. If the user instead requests a separate task, carry forward the earlier stop; do not silently restart the abandoned task. Further external reconciliation or cleanup needs applicable authorization.

## Preserve decisions and continuation

Maintain a compact delivery record in the app's `ENGINEERING.md` and approved private records where needed: current goal/acceptance; agreed design; explicit answers and material inferred assumptions; postponed decisions with reopening triggers; scope references; repository/branch/source; actual checks/deployment results; resource/operation references; blockers; and next actions. Update entries when decisions change. Keep credentials, actual private provider IDs and raw diagnostics outside public source.

Make source and required private artifacts durable through approved push/export and verify restoration. On continuation, read the record, verify actual repository/source/runtime, reconcile resources and reuse valid decisions/authorization. Reopen decisions only for new evidence or changed scope. A fresh VM, changed actor or repeated status request does not itself invalidate prior design choices.

## Acceptance and rollout

Prove this experience through the [phone acceptance scenarios](../docs/mobile-workflow.md#conversational-delivery-acceptance). Factory checks validate helpers and repository policy; they do not certify agent behavior, voice support or deployment capability. Record live evidence privately and identify partial/blocked results explicitly.

Evaluate failure handling as well as the happy path: a blocked repository creation is reported before any claim of creation; a stalled access check produces a timely update and no unchanged retry loop; an unverified permission hypothesis stays labeled unknown; and explicit stop prevents further task tools until restart. Source-integrity tests can verify that instruction seeds reference committed guidance; they do not prove a client follows it.

Merged guidance must reach the selected checkout and the client's actual instruction-loading path. Published runtime/snapshot changes and pinned app instruction seeds have their own rollout; existing sessions and older seeds do not automatically acquire a new revision. Follow [agent compatibility](../docs/agent-compatibility.md) and [runtime acceptance](runtime.md). Verify a fresh session against the intended source before claiming the workflow is active.
