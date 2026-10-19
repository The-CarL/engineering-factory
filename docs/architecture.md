# Architecture

One permanent factory environment supports many independent frontend/backend repositories. Start with the [new-project workflow](new-project.md): each request chooses a suitable app stack and real server/API boundary, then owns its implementation, tests, CI/CD, deployment and later continuation.

```text
Phone or desktop -> task in the reusable factory environment
                      |
                      +-> independent app A repo -> frontend -> real API/server -> data/response
                      |     app-owned CI/CD       compatible deployment targets
                      +-> independent app B repo -> its own stack, CI/CD and targets
Private approved execution identities -> exact operations / provider boundaries
```

The public factory holds shared standards, instruction templates and focused helpers. Repository creation/cloning checks targets and origins; local seeding adds only three instruction/contract files with usable shared rules and a pinned factory revision. It generates no app or CI code. The agent performs app-owned implementation and reviewed CLI/API/IaC work under the initial scope. The Vercel REST helper performs authorized previews only after its production-baseline guard; the app agent performs project creation/protection/first release through the documented official provider path.

Apps use independent origins and ignored `workspaces/OWNER/REPO` clones. The factory never holds application source, credentials or private inventories. Codex/Claude receive the app's local AGENTS/CLAUDE/ENGINEERING rules through deliberate [instruction seeding](new-project.md#workflow), not automatic ancestry. Each client still needs its own installation/authentication/instruction-loading proof.

Choose backend hosting for the product. Framework-native server endpoints can keep frontend/API together when suitable; a separate backend, persistence or AWS requires a reason and actual supported deployment/profile. AWS credentials and read-only identity checks do not implement backend provisioning. A full-stack request is accepted only after the real browser → API → data/response flow works with compatible source/configuration.

## Execution and ownership boundaries

Public source, task execution, private credential injection, GitHub owner/repository, Vercel team/project, AWS role/account/region and app CI/CD are separate trust domains. Connectors do not authenticate Cloud CLIs. Task operations must exclude core/unrelated assets; intended provider policies should enforce that boundary. Actual token access can be broader, and must be recorded in private reviewed [access exceptions](../standards/security.md#access-exceptions), not described as hard isolation from names, tags or no-delete flags.

AWS uses reviewed bounded roles in the existing account when selected; separate-account access is not assumed. Every selected service/action/resource/region/IaC profile needs actual validation. Use the [access matrix](access-matrix.md), [infrastructure](../standards/infrastructure.md) and [bounded scope](../standards/bounded-runs.md). Accept the selected backend through its deployed data path.

A private project record maps stable identity to exact repo/provider/deployment IDs. [Provenance](../standards/provenance.md) records creation/current source/run attribution and child resources; metadata is not an IAM boundary. Apps own CI/CD and its credential design independently of the factory's execution credentials.

## Runtime, continuation and evidence

A published factory environment is reusable setup, not durable app storage. A fresh task/actor may receive a fresh VM; installation/snapshots do not prove old workspaces survive. Make source durable via authorized Git push/private export and verify restoration. A later task uses the same environment, reclones the exact app, reads its local operating contract and reconciles private deployment/recovery references. No compulsory other-chat handoff or per-app environment is needed.

[Runtime standards](../standards/runtime.md) distinguish save/publication/fresh-instance acceptance and retain source/hash/release evidence. Local/mock tests prove only their reported behavior. Verify each installation's GitHub creation/clone/push credential source, actual Vercel transport and [new-project/initial-release execution](provider-workflows.md#new-vercel-project-and-initial-release), and any selected AWS service write profile. Keep operator-specific failures private. Independently verify app CI, deployed full-stack behavior, private inventory and fresh-task continuation before claiming readiness. See [setup](setup.md) and [mobile acceptance](mobile-workflow.md).
