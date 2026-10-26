# Factory design decisions

Recorded 2026-10-26. This register preserves the intent behind the current factory and identifies proposals that are **not implemented**. It is not an application inventory or authority to change providers. Read [history and unresolved work](../history/README.md) for evidence, failed approaches and rollout limits; follow the linked standards for current operations.

## Accepted direction

| ID | Decision and rationale | Canonical guidance |
|---|---|---|
| D1 | **Agent as co-architect and build manager.** Understand purpose, users and experience, investigate the relevant architecture concerns, recommend proportionate tradeoffs/phases and preserve reasoning. Carlo steers consequential choices; the agent owns routine engineering through verified delivery within agreed authority. | [Product co-architecture](../../standards/product-architecture.md), [conversational delivery](../../standards/conversational-delivery.md) |
| D2 | **Manual repository creation, automated development.** Use a supplied repo or propose owner/name/visibility/description for Carlo to create. This contains the observed managed-auth creation problem without broader credentials or a permanent retry loop. Verify access afterward. | [New project](../new-project.md), [GitHub history](../history/github-authentication.md) |
| D3 | **App-owned continuity.** App source, decisions, inventories and recovery references belong to that app's repo/approved private storage. A fresh session discovers the app from those records. No central factory-state repository. | [Continuity](../continuity.md), [provenance](../../standards/provenance.md) |
| D4 | **Choose hosting from product needs.** GitHub owns source/CI/CD; Vercel is a frontend option; AWS can host any suitable component. Credentials do not mandate provider use, a fixed stack or an unrelated marketplace onboarding. | [Toolbox](../toolbox.md), [application design](../../standards/application-design.md) |
| D5 | **Autonomy with actual provider boundaries.** Broad app capability must coexist with protected core/account assets and exact authorized targets. Names/tags/prompts do not prove isolation. A wrapper limit, IAM deny and host execution failure need different remedies. | [Access matrix](../access-matrix.md), [security](../../standards/security.md), [AWS history](../history/aws-and-dns.md) |
| D6 | **DNS independent of hosting.** Select app/service names during design inside the approved public zone, excluding protected names/subtrees. Supply and verify the exact zone instead of requiring global discovery. Preserve core DNS/delegation. | [Application DNS](../application-dns.md) |
| D7 | **Evidence at the claimed boundary.** Local helpers, CI, transport identity, provider writes and hosted user/data flows establish different facts. Real handlers must perform the behavior integration tests claim. | [Testing](../../standards/testing.md), [runtime](../../standards/runtime.md) |
| D8 | **Explicit comprehensive cleanup.** Prepare all resource/data/retention/DNS/publication effects; Carlo reviews and approves the exact plan before execution. Do not infer disposability or impose a universal lifecycle. | [Cleanup](../../standards/cleanup.md), [run retrospective](../history/full-application-run.md) |
| D9 | **Forge awareness and referenced visual styles.** Consider publication when agreed and use current site/Forge GitHub source as design references. Adapt to the app; do not copy a second canonical design system into the factory or mandate identical UI/hosting. | [Forge](../forge.md), [design references](../design-references.md) |
| D10 | **Client-neutral core, verified host adapters.** Shared standards work through Codex, Claude Code or another client's actual instruction loader. Client, execution host and app hosting are separate choices, each requiring relevant proof. | [Agent compatibility](../agent-compatibility.md), [execution hosts](../execution-hosts.md) |
| D11 | **Versioned source and honest rollout.** Merged guidance is distinct from installed activation, any host snapshot and fresh-session acceptance. Record actual revisions; environment rebuilds are not a substitute for identifying the failed layer. | [Runtime](../../standards/runtime.md), [Cloud history](../history/cloud-execution.md) |

## Proposed and continuing work

| ID | State | Direction / reopening trigger |
|---|---|---|
| D12 | **Proposed; no settings mutation or new identity authorized by this record.** | [Repository settings and automation](repository-settings.md): Carlo creates the repo, a trusted setup path applies agreed settings, and routine automation cannot exercise Carlo-only bypass. Resolve entitlement and effective actor/transport first. |
| D13 | **Reopened by Carlo, 2026-10-26; shared guidance added.** | [Product co-architecture](../../standards/product-architecture.md) develops the previously deferred design work with broad review lenses, contextual follow-ups, explicit tradeoffs and useful phases. No fixed ceremony, stack or lifecycle taxonomy is selected; more specific workflow/tooling remains a future design decision. |

## Changing a decision

Record the date, concrete evidence or user direction, revised decision and affected standards. Keep the old rationale accessible with a superseding link. For an operational fix, identify source implementation separately from live activation and acceptance. Preserve unresolved facts as unresolved; a workaround need not become a permanent architectural rule.
