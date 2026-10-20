# Durable project continuity

The optional context backend uses one explicitly configured, dedicated **private GitHub repository**. It stores structured project identity and target configuration plus validated runtime journals/ownership receipts under per-project UUID namespaces. It never exports app source, arbitrary `ENGINEERING.md` text, environment dumps, requests, raw provider responses or credentials. App decisions and source remain in the app repository and must be committed/pushed through its normal workflow.

Configure `FACTORY_CONTEXT_REPOSITORY`, a private canonical `FACTORY_CONTEXT_DIRECTORY` inside `FACTORY_PRIVATE_ROOT`, and explicit `FACTORY_GITHUB_CREDENTIAL_SOURCE=factory-token`. Resolve/create that private repository only under approved owner/scope; these scripts do not provision it. Each remote use verifies exact repository identity/private visibility using the selected namespaced credential. Context history never runs hooks, CI, settings or commands; only strict-schema data is consumed. Keep the context repository private even if an app is public.

## Initialize or continue

After verifying and seeding an independent app, the seeder automatically initializes its context when the backend is configured. Existing differing app instructions still require deliberate integration. The equivalent direct command is:

```bash
factory-project init --repo OWNER/APP --app /canonical/app --environment development
. "$FACTORY_PRIVATE_ROOT/project.env"
```

Initialization generates/reuses a stable UUID and records the verified origin/branch/commit, environment and allowlisted target configuration. It does not adopt provider resources or invent app architecture. Activation selects that project for subsequent provider operations, eliminating repeated manual UUID/target composition.

In a new task, select only the known exact app repository:

```bash
factory-project open --repo OWNER/APP
. "$FACTORY_PRIVATE_ROOT/project.env"
```

Or configure `FACTORY_PROJECT_REPOSITORY` for startup; `runtime/start.py --environment-file ...` automatically restores that known project and includes its verified selections in activation. The backend verifies the app remotely, clones an absent independent checkout, and verifies any existing independent origin/source without resetting user work. A new clone selects the saved branch; an existing verified app may intentionally switch branches, and its next checkpoint records the current branch/commit while preserving dirty source. Unknown projects are refused rather than implicitly adopted. Conflicting project/account/role/owner/team selections stop restoration; use an explicit clean project selection. The saved AWS region is a default: an explicit valid per-operation region may override it within the already approved provider scope, without changing that saved default or granting a new region.


## Resource inventory

Record actual resource readback in a reviewed private strict-schema inventory, then register it with `factory-project inventory --repo OWNER/APP --app /canonical/app --inventory /private/inventory/resources.json`. The top-level fields are `schema: 1`, matching `project_id`, `environment` and `resources`. Each resource has exactly `provider` (AWS/Vercel/GitHub), `resource_id` (typed exact ARN/ID/repository), `resource_type`, `parent_id`, `backend_ref`, `run_id`, `source_commit`, `status` and `ownership` (managed/external). Parent/backend references are null or identify another typed resource in that inventory. An optional `url` is HTTPS without user info, query or fragment. Connection strings, credentials, arbitrary fields and raw provider responses are refused.

This preserves IDs, parent/backend relationships, safe deployment endpoints and source/run/status observations across tasks. Ownership is a recorded declaration, not an adoption grant; original creation receipts and provider evidence still matter. Agent-owned recording is explicit; the backend does not pretend response hashes reconstruct resource IDs. Apps must separately configure and protect encrypted remote IaC state; this inventory retains only a typed backend identity/reference, never the state payload or credentials.

The current bounded backend allows 128 resource entries per inventory (256 KiB), 256 artifact files and 4 MiB per project, 128 KiB project metadata, and 1,024 tracked files/64 MiB across the current context tree. Reaching a limit requires deliberate retention/store maintenance before further dependent work; this is not unlimited storage or automatic history pruning. Git history remains private and needs its own retention policy.

## Checkpoints and recovery

Selected-project runtime operations automatically preserve safe intent/completion/failure journals. Context-free identity reads and authorized new-repository bootstrap remain usable before project initialization; their evidence remains local until explicitly associated with a verified project. Vercel creation also checkpoints its ownership receipt and exact creation journal; relative paths and bytes are preserved so the original receipt digest remains valid after restore. No provider output file is uploaded. Run `factory-project checkpoint --repo OWNER/APP --app /canonical/app` after app source/branch changes; it records source identity without copying dirty files or claiming they are remotely durable.

Files, bytes, field sets, paths and hashes are bounded and validated; symlinks, Git directories, executable configuration, arbitrary sources and unknown fields are refused. Restore never overwrites differing local private artifacts or app work. Context commits use optimistic normal push with no force, auto-merge or automatic reset. A conflict, interrupted push or unknown outcome preserves local state for reconciliation. `factory-project reconcile` verifies the private remote, committed schema/artifact hashes and ancestry, then uses only a normal optimistic push and exact hash readback for a clean pending commit. Already-published commits need no duplicate push; dirty or divergent state stops without reset/force/auto-merge. A provider may already have completed when context publication fails: report persistence pending and reconcile the context Git commit/remote state, never replay that provider mutation just to repair continuity. Until remote checkpoint and fresh-task restoration actually pass, durability remains unverified.

This backend is operational continuity, not an authorization or tamperproof audit boundary. Provider scopes, task authorization, protected-asset controls and private access exceptions still govern every action.
