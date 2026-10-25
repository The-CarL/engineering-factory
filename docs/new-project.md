# Create or continue an application

Use the reusable factory environment for independent applications. Carlo brings the vision and co-designs with the agent; the agent acts as his build manager and owns turning the agreed outcome into a working solution. Use available tools, configured environments and shared standards to plan and execute autonomously within authorized scope. Adapt the discussion and order of work to the project. Static sites, APIs, services, full-stack apps, workers and other workloads can use different components and providers.

## Product scope and decisions

Lead the conversation under [conversational delivery](../standards/conversational-delivery.md): propose an approach and observable success, ask about consequential unknowns before dependent work, infer routine reversible choices and postpone only with an explicit reopening trigger. Reuse context and prior answers. The product-outcome prompt below is an optional example; a voice or text idea can start codesign without it.

Apply the [application design standard](../standards/application-design.md). Choose the smallest suitable supported architecture, runtime and hosting. Add a user interface, server/API, persistence, authentication, queues or schedules when the product needs them. Record decisions and actual operating commands in the app's `ENGINEERING.md`.

Prepare consequential operations from known configuration under [bounded project work](../standards/bounded-runs.md): exact repository/visibility, selected provider targets, public exposure, permissions, cost limits and recovery. The agent fills these details rather than asking the user to complete a universal form. Existing exact authorization persists. An initial approval can cover routine implementation, repository, CI and hosting work together; ask only for missing consequential scope, an actual change or required action-time approval. Routine choices and independent authorized work can continue. Another chat is optional and requires human authorization for its recipient/purpose.

## Repository and instructions

Check the intended repository/build/test/hosting/data path and actual source/runtime revisions early, before substantial dependent implementation. Surface missing capabilities or decisions with evidence and a concrete next action. Continue independent work and identify partial prototypes accurately; a local scaffold cannot establish the requested hosted integration.

Establish the repository during codesign: use an existing independent app repository supplied by Carlo, or propose the details for him to create it manually. The agent does not create GitHub repositories through the CLI, REST, GraphQL, a template or a fork. Repository creation permission is not a factory prerequisite. Private is the default; a public repository needs explicit publishing scope. Keep app source and provider state out of the factory.

If no existing repository is supplied:

1. Propose the owner from approved configuration, a suitable name, a concise product description and private visibility. Treat the name and expected URL as unverified until provider readback; missing access is not proof that a name is available.
2. Give Carlo one concise brief: open [GitHub New repository](https://github.com/new), select that owner/name/visibility, enter the description, and leave README, .gitignore and license initialization unchecked for a new empty app repository. Preserve any content if he supplies an already initialized repository.
3. Ask Carlo to create it and return its repository URL. This is an expected manual prerequisite, not a token failure or a request to expand permissions. Continue agreed independent design/planning; pause cloning, app initialization, pushes and dependent deployments until the target exists and is accessible. Do not substitute a local-only app or another repository silently.
4. Once Carlo supplies the URL or confirms the agreed target, verify the exact GitHub owner/name, visibility and actual access, then use `clone-repo.sh`. If the repo is not visible, distinguish not-created from not-accessible and ask only for the missing creation/access action. Do not retry creation, cycle credentials or assume new-repo connector access.

The offline helper prints the brief without credentials, provider calls or filesystem writes:

```bash
./scripts/plan-repo.sh approved-owner/my-app \
  --description "A short description of the application."
# After Carlo creates it and supplies the target:
./scripts/clone-repo.sh approved-owner/my-app
```

`create-repo.sh` is retained only as a compatibility alias for the offline brief; even its legacy `--confirm` argument performs no creation or clone. Factory GitHub runtime commands also reject repository creation. Existing-repository content, branch, PR and CI work remains supported within approved scope.

Before repository-dependent implementation, verify the existing remote repository and independent clone's Git root and fetch/push origins. Share the canonical URL as verified only after provider readback confirms owner/name and visibility; an expected creation URL is a proposal. Then seed instructions, implement and verify the product. Existing empty repositories are valid: the agent prepares the first commit and app-owned CI within approved scope. Local initialization and seeded instructions do not establish remote publication or implemented product code. Follow the diagnostic budget, evidence and stop/restart rules in [conversational delivery](../standards/conversational-delivery.md).

The local instruction helper seeds shared rules for Codex and Claude plus an app-owned engineering contract. Run it from reviewed committed factory source using the canonical absolute app path:

```bash
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --dry-run
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --confirm approved-owner/my-app
```

Its instruction outputs are `AGENTS.md`, `CLAUDE.md` and `ENGINEERING.md`. Local Git checks reject factory targets, linked worktrees, unsafe origins and symlinks; all outputs are checked before writes. Matching instruction repeats preserve files; differing existing instructions require deliberate integration. The helper, templates, application standard and conversational-delivery standard must match a committed factory revision. It generates no app/CI code and executes no hooks. Without an installed runtime it performs no network calls; with a selected installed runtime it also registers the verified app in that same repo's `.factory/` directory, even before its first commit. Dry-run remains offline. Apply generated project activation for [durable continuity](continuity.md).

## Implementation, hosting and evidence

Implement the requested product in its own repository. Pin relevant dependencies and tooling, maintain app-owned checks/CI and use reviewed app-owned CI authentication. Keep secrets out of source, client bundles and logs, and factory execution credentials out of app CI. Choose the order of work from actual dependencies and risks.

Use the selected provider's official tools and [contracts](provider-workflows.md) with exact targets, provenance, limits and operation recovery. For a project selecting Vercel, its [new-project/initial-release path](provider-workflows.md#new-vercel-project-and-initial-release) includes saved protection and explicit initial-release scope; the preview helper requires an existing READY production baseline. AWS operations need an appropriate reviewed role/service/resource/IaC profile. Installed credentials or identity reads do not establish deployment permission.

Verify the workload's real outcome and failure behavior in the intended runtime. Browser interaction is relevant to a UI; request/response checks to an API; execution, retry and output checks to a job. Verify component integration, authorization and durability where applicable. Keep app acceptance separate from factory environment capability checks, with exact source/configuration/deployment evidence and private inventory.

Make source durable through authorized Git push or approved private export with restore verification. A later task uses the same environment, clones the saved app identity, reads local instructions/commands, restores approved private configuration and reconciles existing resources before changes. Record operational and recovery details; do not assume workspace files survive a fresh task.

Keep the goal, decisions/assumptions, deferred decisions and triggers, scope references, validation/deployment state, blockers and next actions in the app's delivery record. A receiving session reuses these decisions and verifies current state before resuming.

## Product-outcome prompt

```text
Use the engineering factory to build [PRODUCT OUTCOME AND WHO IT SERVES].
Use the existing independent app repository I provide. If none is provided, propose
its owner, name, private visibility and description, then ask Carlo to create it
manually and return its URL. Verify the repository and access before dependent work.
Use the approved branch workflow. Choose suitable architecture, runtime, hosting and meaningful checks from
the product needs and existing private configuration. Record actual commands and
operations in the app. Prepare any missing consequential scope together; reuse prior
authorization and carry routine work through implementation, relevant verification,
CI and agreed hosting with minimal interruptions. Keep source isolated, secrets private,
provenance and recovery complete. Report what works and any remaining blockers.
```
