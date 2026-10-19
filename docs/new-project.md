# Create or continue an application

Use the reusable factory environment for independent applications. Describe the product outcome; the agent derives the architecture, implementation, checks and hosting work from that need and the approved private configuration. Static sites, APIs, services, full-stack apps, workers and other workloads can use different components and providers.

## Product scope and decisions

Apply the [application design standard](../standards/application-design.md). Choose the smallest suitable supported architecture, runtime and hosting. Add a user interface, server/API, persistence, authentication, queues or schedules when the product needs them. Record decisions and actual operating commands in the app's `ENGINEERING.md`.

Prepare consequential operations from known configuration under [bounded project work](../standards/bounded-runs.md): exact repository/visibility, selected provider targets, public exposure, permissions, cost limits and recovery. The agent fills these details rather than asking the user to complete a universal form. Existing exact authorization persists. An initial approval can cover routine implementation, repository, CI and hosting work together; ask only for missing consequential scope, an actual change or required action-time approval. Routine choices and independent authorized work can continue. Another chat is optional and requires human authorization for its recipient/purpose.

## Repository and instructions

Use `create-repo.sh` for an authorized new repository or `clone-repo.sh` for an existing one. Private is the default; use the approved visibility and branch workflow. Verify the exact independent Git root and fetch/push origin. Keep app source and provider state out of the factory.

The local instruction helper seeds shared rules for Codex and Claude plus an app-owned engineering contract. Run it from reviewed committed factory source using the canonical absolute app path:

```bash
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --dry-run
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --confirm approved-owner/my-app
```

It writes only `AGENTS.md`, `CLAUDE.md` and `ENGINEERING.md`. Local Git checks reject factory targets, linked worktrees, unsafe origins and symlinks; all outputs are checked before writes. Matching repeats are no-ops; differing existing instructions require deliberate integration. The helper/templates/application standard must match a committed factory revision. It generates no app/CI code, executes no hooks and performs no authentication or network calls.

## Implementation, hosting and evidence

Implement the requested product in its own repository. Pin relevant dependencies and tooling, maintain app-owned checks/CI and use reviewed app-owned CI authentication. Keep secrets out of source, client bundles and logs, and factory execution credentials out of app CI. Choose the order of work from actual dependencies and risks.

Use the selected provider's official tools and [contracts](provider-workflows.md) with exact targets, provenance, limits and operation recovery. For a project selecting Vercel, its [new-project/initial-release path](provider-workflows.md#new-vercel-project-and-initial-release) includes saved protection and explicit initial-release scope; the preview helper requires an existing READY production baseline. AWS operations need an appropriate reviewed role/service/resource/IaC profile. Installed credentials or identity reads do not establish deployment permission.

Verify the workload's real outcome and failure behavior in the intended runtime. Browser interaction is relevant to a UI; request/response checks to an API; execution, retry and output checks to a job. Verify component integration, authorization and durability where applicable. Keep app acceptance separate from factory environment capability checks, with exact source/configuration/deployment evidence and private inventory.

Make source durable through authorized Git push or approved private export with restore verification. A later task uses the same environment, clones the saved app identity, reads local instructions/commands, restores approved private configuration and reconciles existing resources before changes. Record operational and recovery details; do not assume workspace files survive a fresh task.

## Product-outcome prompt

```text
Use the engineering factory to build [PRODUCT OUTCOME AND WHO IT SERVES].
Create or use an independent app repository with the approved visibility and branch
workflow. Choose suitable architecture, runtime, hosting and meaningful checks from
the product needs and existing private configuration. Record actual commands and
operations in the app. Prepare any missing consequential scope together; reuse prior
authorization and carry routine work through implementation, relevant verification,
CI and agreed hosting with minimal interruptions. Keep source isolated, secrets private,
provenance and recovery complete. Report what works and any remaining blockers.
```
