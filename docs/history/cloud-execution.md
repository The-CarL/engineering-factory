# Cloud execution and runtime lessons

Recorded 2026-10-26 from the October setup reports. These observations describe distinct incidents; a single root cause for all edit, start, networking and authorization failures was not established.

## Readiness has several layers

| Layer | What was observed | Lesson |
|---|---|---|
| Environment configuration | A control plane reported connected/current revisions, ready bindings and allowed provider hosts while shell connectivity still failed. | “Configured” is evidence about configuration, not working execution. |
| Shell network execution | Even a public unauthenticated GitHub request failed with `PermissionError errno=1` before credential evaluation. | This did not establish an invalid token or provider permission denial. |
| Dispatch / approval / execution | One network-enabled call stayed pending for roughly 16 minutes despite a 45-second shell timeout, eventually carrying an “aborted by user” label. | A shell timeout does not bound time before dispatch. That label alone did not prove Carlo deliberately cancelled or that navigation caused it. No automatic-review rejection reason was supplied. |
| Provider authentication | GitHub returned an authenticated identity even for an invalid supplied token. | Network success and identity success did not establish credential routing. |
| Provider authorization | Different operations and transports had different results. | Reads do not prove creation, deployment, settings administration or deletion authority. |
| Application acceptance | Frontend hosting worked before the requested API/database integration did. | A live frontend or READY deployment was partial evidence, not end-to-end delivery. |

Settings repeatedly failed to start editing a Cloud environment. Replacement environments and publication were attempted, but neither the UI error's root cause nor a universal fix was established. Rebuilding is a consequential configuration action, not evidence that authentication or execution changed.

The factory now distinguishes these layers in [execution hosts](../execution-hosts.md), [runtime standards](../../standards/runtime.md) and [conversational delivery](../../standards/conversational-delivery.md). A network grant is requested only when the selected host requires and exposes that supported mechanism. There is **no universal network-grant-tool prerequisite**. Preserve the host's supported proxy/CA controls; do not silently change approval settings or evade a denial.

## Source, runtime and session drift

An early test used a checkout newer than the installed runtime; the installed AWS wrapper still admitted only identity and selected DNS reads. The requested general app environment could not be certified from that wrapper. A tooling restriction was initially confused with effective AWS permission, creating the wrong diagnosis.

Merged source, installed versioned release, activation, published snapshot where applicable, client instruction loading and fresh-session behavior are different rollout stages. Existing tasks and app instruction pins do not automatically acquire new factory guidance. Keep the actual revisions in private acceptance records.

Later source changes improved bootstrap, explicit tool paths, integrity manifests, host guidance and agent-neutral instruction seeding. They do not establish that every older environment or mobile session received those changes. Use [runtime commands](../runtime-commands.md) and [agent compatibility](../agent-compatibility.md) for current setup; this history is not a new installation script.

## Execution discipline

The repeated failure was not just technical: access diagnostics and retries consumed time without delivering the intended autonomous app workflow. The intended response is an early, proportional feasibility check, then execution through the agreed design using valid evidence. Do not turn setup probes into the product or ask again for already established authorization.

The current standard calls for short diagnostic budgets, supported timeouts, useful updates within a minute during active work, retaining running tool/session handles, and retries only after new evidence or a changed prerequisite. A pending handle must be resumed rather than duplicated. Unknown write outcomes require provider reconciliation before another write.

A local proxy also blocked loopback browser navigation during the successful app exercise. CI browser integration and hosted HTTPS checks were useful separate routes with different evidence boundaries. A proxy-issued TLS certificate did not describe the origin certificate; provider metadata supplied separate origin TLS evidence. See the [application retrospective](full-application-run.md).

**Acceptance remains contextual:** offline factory checks validate helpers and policy, app CI validates its tested boundaries, and a real hosted browser flow validates the actual deployment. The first full success did not certify every service, client, phone workflow or future environment.
