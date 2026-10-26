# Architecture

The shared factory core is independent of the AI client and execution host. Codex, Claude Code or another client loads the same project rules; the selected host supplies shell, tools, credentials and network access. Codex Cloud is one documented host profile. A reusable execution environment supports independent application repositories. Each product chooses its own architecture, runtime, checks and hosting. Static sites, APIs/services, full-stack apps, workers/jobs and other workloads share the factory's operating capabilities without sharing application source or deployment state.

```text
Phone or desktop -> task in the reusable factory environment
                      |
                      +-> independent app repositories
                            product-specific source, components and runtime
                            app-owned checks, CI/CD, hosting and operations
Private approved execution identities -> exact operations / provider boundaries
```

The public factory contains shared standards, local instruction templates and focused helpers. Carlo supplies an existing repository or creates it manually from an offline brief; repository cloning verifies targets and origins. Instruction seeding adds three files with usable shared rules and pinned factory references. The app agent performs implementation and relevant provider CLI/API/IaC work. [Application design](../standards/application-design.md) guides component and verification choices.

Apps use independent origins and ignored `workspaces/OWNER/REPO` clones. Keep application source, credentials and private inventory outside public factory source. AI clients receive shared AGENTS/ENGINEERING rules and any required thin client entrypoint through [instruction seeding](new-project.md#repository-and-instructions); each client still needs its own installation/authentication/instruction-loading proof.

## Execution and ownership boundaries

The agent acts as Carlo's build manager: brainstorm and co-design together, then autonomously carry the agreed vision through implementation, verification and agreed hosting within authorized scope. The conversation and order of work adapt to the project. Available tools, configured environments and shared standards support that responsibility; Carlo supplies product direction and consequential decisions. The agent resolves uncertainty by asking, inferring or explicitly postponing, checks feasibility early and owns progress through completion. The app's engineering record preserves decisions and delivery state across sessions. See [conversational delivery](../standards/conversational-delivery.md) and [phone acceptance](mobile-workflow.md#conversational-delivery-acceptance). Helper checks alone do not establish this experience.

Public source, task execution, private credential injection, app CI/CD and each selected provider target are separate trust domains. Connector access alone does not establish CLI write permissions. Task operations exclude core/unrelated assets; intended provider policies should enforce that boundary. Actual token access can be broader and must be recorded in private reviewed [access exceptions](../standards/security.md#access-exceptions). Names, tags and no-delete flags do not establish hard isolation.

Use only the providers the app needs. AWS operations use reviewed bounded roles/service/resource/region/IaC profiles; identity reads do not prove provisioning. Projects selecting Vercel follow its [project/initial-release contract](provider-workflows.md#new-vercel-project-and-initial-release); the preview helper remains conditional on its protected-project and production-baseline guards. Use the [access matrix](access-matrix.md), [infrastructure](../standards/infrastructure.md) and [bounded scope](../standards/bounded-runs.md) for relevant operations.

A private project record maps stable identity to exact repository/provider/deployment IDs. [Provenance](../standards/provenance.md) records creation/current source/run attribution and child resources. Apps own CI/CD and its authentication independently of factory execution credentials.

## Runtime, continuation and evidence

A published factory environment supplies reusable setup. A fresh task/actor may receive a fresh VM; make app source durable via authorized Git push/private export and verify restoration. A later task uses the same environment, clones the exact app, reads its operating contract and reconciles private resource/recovery references.

[Runtime standards](../standards/runtime.md) distinguish save/publication/fresh-instance acceptance. Verify the environment capabilities actually claimed with authorized representative operations; keep each provider transport and permission result separate. App acceptance verifies its own workload and operating contract, independently of factory checks. Keep operator-specific failures and private inventory out of public source. See [setup](setup.md) and [phone operation](mobile-workflow.md).

## Design rationale and history

The [decision register](design/README.md) preserves the agreed factory direction and clearly marks proposed/deferred changes. The [history index](history/README.md) records the GitHub credential-routing and repository-protection investigations, Cloud execution/runtime failures, AWS/DNS lessons, and the first full application lifecycle. It separates reported live outcomes, inspected source fixes, unverified activation and unresolved work. App-specific inventories and raw evidence remain in app-owned approved records.
