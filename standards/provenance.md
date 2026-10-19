# Project ownership and provenance

Every managed infrastructure resource, Vercel deployment and reusable environment build artifact must resolve to one stable project and environment. This is a deployment acceptance requirement, including previews, experiments, indirect/child resources, and retries. Metadata identifies ownership; [provider permissions](../docs/access-matrix.md) enforce access. Tags alone do not authorize a change.

## Project record before writes

Create a private project record with an immutable, non-sensitive `project_id`, human-readable alias, owner alias, source repository alias, allowed environments, approved provider targets, namespace, and cleanup owner. The ID survives repository/project renames and is never reused for another project. Give each operation a unique `run_id` and record the exact source commit before writing. Use UTC RFC 3339 timestamps. Do not put credentials, private URLs, personal emails, or account IDs into metadata.

Shared factory control-plane resources belong to the `engineering-factory` project; link consuming app project IDs without assigning the shared resource to each app. Existing/core dependencies remain external references with their known owner, not factory-created/adopted assets; do not retag them.

Keep actual account, role, repository, Vercel team/project and resource identifiers in private app/operations storage. The public factory contains this schema and placeholder examples only. Names should include the project alias and environment where supported, but names are not a substitute for exact provider ID readback.

## Required metadata mapping

Use this versioned mapping where the provider supports tags or deployment metadata. AWS tags are resource-specific; Vercel keys belong to the deployment `meta` object, not invented project tags or `vercel.json` fields.

| Meaning | AWS resource tag | Vercel deployment metadata |
|---|---|---|
| Stable project ID | `factory:project-id` | `factoryProjectId` |
| Environment | `factory:environment` | `factoryEnvironment` |
| Responsible owner alias | `factory:owner` | `factoryOwner` |
| Manager, value `engineering-factory` | `factory:managed-by` | `factoryManagedBy` |
| Source repository alias | `factory:source-repo` | `factorySourceRepo` |
| Exact creation source commit | `factory:source-commit` | `factorySourceCommit` |
| Creation actor/role alias | `factory:created-by` | `factoryCreatedBy` |
| Original creation time | `factory:created-at` | `factoryCreatedAt` |
| Original operation ID | `factory:creation-run-id` | `factoryCreationRunId` |
| Most recent change operation ID | `factory:last-run-id` | `factoryLastRunId` |
| Exact most recent change commit | `factory:last-source-commit` | `factoryLastSourceCommit` |
| Schema version, initially `1` | `factory:provenance-version` | `factoryProvenanceVersion` |
| Expiry for temporary resources | `factory:expires-at` | `factoryExpiresAt` |

Populate both original and latest fields on creation. Preserve original creation attribution on updates; append later actor/time/commit events to the private inventory. Update latest fields only for the resources actually changed. Do not inject a new run/commit globally through IaC default tags and thereby modify unrelated resources. An existing provider object must not be relabeled as newly created. Adoption needs separate explicit authorization and an event preserving its known history and any unknown fields.

## AWS creation and ownership

- Review every planned resource type for tag-on-create, resource-level IAM, ABAC conditions, tag limits, and child resource behavior. Support varies by service and action. Require tags during creation where supported; do not assume tags propagate to auto-created resources.
- If tag-on-create is unavailable, approve a narrowly scoped create/tag/readback sequence before use. If it cannot be performed safely within the role boundary, stop. A temporary tagging gap is an explicit reviewed exception, not a general fallback.
- Record untaggable resources by exact ID, type, stable logical ID, owning project/environment, and parent relationship in the private inventory. List each exception in the plan and acceptance evidence; parent tagging alone does not prove ownership or constrain IAM.
- Restrict tagging/untagging APIs so the factory cannot tag core/existing assets to claim ownership, transfer project ownership, or change/remove protected ownership and original-attribution tags. Policies must also enforce resource namespaces and action/resource/region allowlists; request tags alone are insufficient.
- Inspect the resulting provider tags and all child resources after apply. A successful IaC command or a tag in a plan is not readback evidence. See [AWS tag authorization](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_tags.html) and [infrastructure boundaries](infrastructure.md).

## Vercel deployment paths

Resolve and record the exact team and project IDs, project name/alias and environment before each write. Associate the Vercel project with the stable factory project ID in the private project record; do not confuse it with Vercel's own project ID.

For CLI deployments use repeated `vercel deploy --meta KEY=value` options, populated from non-sensitive project/run metadata. The deployment creation API accepts a `meta` object. Read back the deployment ID, project link, source commit, target and metadata after creation; metadata filtering can help locate runs. See [CLI metadata](https://vercel.com/docs/cli/deploy#meta), [list filtering](https://vercel.com/docs/cli/list#meta), and [deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).

Validate every actual deployment path, including native Git integration and redeployments. CLI metadata is not automatically propagated by native Git builds. If a path cannot inject these keys, establish and verify a supported mechanism or explicitly reviewed equivalent private mapping from deployment ID to project/environment/run/commit and creation attribution before enabling it. Never silently omit provenance. Project settings and other non-deployment Vercel objects require exact-ID inventory records; do not assume AWS-style project tags exist.

## Private inventory and operation events

Maintain one per-project inventory plus append-only operation events in private app/operations storage with appropriate access and retention. Keep it outside the public factory. For every resource/deployment record:

- Exact provider target and resource/deployment IDs, resource type, stable logical ID, project/environment, and parent/stack relationships.
- Whether it was created, updated, adopted, or deleted; original creation attribution; current source commit/run/time and actor; approval or change reference.
- Current status and health/readback evidence, estimated cost, cleanup owner, expiry, and actual deletion time/result when deletion is later authorized.

Persist intent before writes and reconcile readback afterward. Preserve creation and deletion history; do not remove a record because its resource was removed. After partial failures/timeouts, reconcile all known IDs and operation events before retrying or reporting success. Do not create duplicates or claim ownership from a matching name/tag alone.

Correlate Git commits, deployment events and provider audit events (including CloudTrail where already available). Tags and local manifests are mutable unless separately protected; this standard does not make them tamperproof. Enabling new audit services or paid logging remains a separate authorized change.

## Environment build artifacts

Treat reviewed installers, wrappers, startup checks and prepared runtime snapshots as factory control-plane artifacts. Keep a private release manifest linking their exact source commit and configuration revision to the observed environment/snapshot revision or publish job, tool/base versions, retained-file hashes and startup/integrity results. Record provider identity/target reads and native CLI/API compatibility separately, along with approvals and outstanding write/deployment/mobile gates. Preserve original creation attribution and append later release/recovery events.

Record saved, publishing, published and fresh-instance-accepted states distinctly. Keep the last confirmed release and recovery reference; reconcile known jobs/revisions after timeouts rather than create duplicates. Public Git holds generic reviewed source and this schema; actual environment IDs, private paths/targets and operation evidence stay private. See [runtime release acceptance](runtime.md#release-evidence-and-recovery).

## Find everything belonging to a project

Start with the private inventory filtered by stable `project_id` and environment; it must include AWS, Vercel, child and untaggable resources plus historical deleted objects. For Vercel, use `vercel list --meta factoryProjectId=PROJECT_ID` under the approved scope, then read back exact deployment/project IDs and reconcile inventory. This finds deployments carrying that metadata, not every project setting or an alternate path that omitted it.

For AWS, reconcile approved regional service inventories and supported tag queries against the private records. The [Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/API_GetResources.html) can filter tagged resources in the selected region, but does not return untagged resources and does not replace service-specific discovery. A tag-query result alone is not a complete account inventory. Flag orphaned/mismatched objects and investigate before further writes; do not auto-adopt or delete them.

## Acceptance

1. Before writes: approved stable project record, bounded access design, exact target, source commit/run, and reviewed metadata support/exceptions for every planned resource and deployment path.
2. After writes: provider readback and inventory agree on every created/changed object, child resource, project/environment and source/run attribution; health checks pass. No unowned created resources may remain unaccounted for.
3. Verify permitted and denied behavior using policy simulation and authorized disposable controls. Do not test a denial by attempting to damage core assets. Record evidence separately from identity-only preflight.
4. Missing attribution, unknown ownership or an unreconciled partial failure fails deployment acceptance. Stop further writes and reconcile; cleanup requires its own approved scope.
