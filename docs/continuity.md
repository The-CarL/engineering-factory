# Project-owned continuity

Each independent app owns its source, `ENGINEERING.md` decisions and a bounded `.factory/` registry in **that same repository**. There is no central tracking repository or fallback. Source merge/refresh does not install or publish a runtime snapshot; verify the installed release and required GitHub credential/write capability separately. Repository creation and the first app commit remain possible before registration.

## Initialize and continue

After creating/cloning the exact approved app, register its stable UUID and known planned targets before consequential provider writes:

```bash
factory-project init --repo OWNER/APP --app /canonical/app --environment development
. "$FACTORY_PRIVATE_ROOT/project.env"
```

The instruction seeder invokes registration when an installed runtime is selected; without a runtime it only seeds local instructions. Initialization works on an unborn branch with no default-branch record or initial commit. It verifies GitHub identity/owner membership, exact repository/visibility and independent fetch/push origins. It writes `.factory/project.json` with UUID, repository, environment, current branch/source observation, pinned factory standard references, publication policy and allowlisted target configuration. It never creates/adopts provider resources or chooses app architecture. Register resource readback after creation using the inventory command below.

On continuation, select that exact app:

```bash
factory-project open --repo OWNER/APP
. "$FACTORY_PRIVATE_ROOT/project.env"
```

A missing checkout is cloned only from the verified app. By default Git selects its remote default branch; use `--branch feature-name` for known unmerged work. Before initial checkout, only strict registry data is read; repository content is not executed. A repository without a registry stays unactivated and needs explicit initialization. Unknown or inaccessible repositories are refused. Existing branches, staged files and dirty app source are preserved; open does not fetch/reset/merge existing source or overwrite differing private evidence. Read the app's instructions and reconcile `ENGINEERING.md` after opening.

Startup also restores an explicitly selected `FACTORY_PROJECT_REPOSITORY` (and optional `FACTORY_PROJECT_APP`). Conflicting UUID/account/role/owner/team selections stop activation. Saved AWS region is a default; an explicit valid operation region may override it within existing approved scope. Registry metadata is mutable context, not an adoption grant, IAM boundary or tamperproof audit. Provider target/readback, creation evidence and task authorization remain required.

## Artifacts and confidentiality

A private app may register safe creation/operation journals, ownership receipts and typed resource inventory under `.factory/artifacts/`. The manifest records each relative path, kind and SHA256. Requests/results are represented by hashes, never raw payloads. Original creation journal/receipt bytes and relative layout are preserved when restored under `FACTORY_PRIVATE_ROOT`, so ownership digest checks still work. Unfinished/unknown operation evidence is retained and reported; reconcile the affected provider outcome before related writes, without replaying the original mutation.

A **public app** receives only a minimal registry: stable UUID/repo/environment, source/branch observations, safe factory standard references and public owner. Private account/team configuration, resource inventories and all operation/ownership artifacts are excluded. Automatic evidence stays local in the private root; an explicit confidential checkpoint fails clearly without modifying the public registry. There is no central fallback. Until reviewed project-owned protected/encrypted storage is configured for that evidence, confidential cross-task continuity is blocked. Keep any publishable storage alias/reference in the app's reviewed engineering contract; never expose account IDs/backend inventories merely because app source is public. Changing a private registry's visibility requires deliberate confidentiality/history review; the push guard also checks bounded public registry history.

Secrets, credential caches, raw provider responses, database contents and raw IaC state never belong in either registry profile. Configure encrypted IaC state in a project-owned protected backend and retain only typed backend references; encryption keys and state payloads stay outside Git. `.factory/` is not a place for executable configuration, hooks or CI. Strict schemas/size limits and known-credential rejection supplement source review and scanners; they do not prove an arbitrary string is nonsecret.

## Checkpoints, commits and recovery

Provider commands queue validated evidence in private `project-continuity/UUID/pending.json`, referencing original private files by path/digest. They do **not** modify the app registry, stage source, create commits or push after each command. At a logical delivery milestone:

```bash
factory-project checkpoint --repo OWNER/APP --app /canonical/app
```

This batches pending safe artifacts and updates only `.factory/`; it leaves the Git index untouched. For original pre-registration evidence, add explicit reviewed `--journal /private/bootstrap.jsonl` or `--ownership /private/receipt.json` inputs; no directory glob or arbitrary document export is supported. Review the registry and `ENGINEERING.md`, then deliberately commit selected app source plus registry/decisions through the app's normal feature branch and PR workflow. No helper stages arbitrary code or writes a hidden second repository. Checkpoint does not mean remote durability. Verify the exact pushed commit and required checks; uncommitted/unpushed files cannot be recovered on another host. Branch protections remain in force; do not merge without authorization.

After an unknown push outcome, `factory-project reconcile --repo OWNER/APP --app /canonical/app` checks the exact remote branch hash. If already published it does nothing; if the remote is an ancestor it performs a normal push/readback of the existing local commit. It never creates a commit, stages dirty files, force-pushes, resets, auto-merges divergence or replays provider work. Dirty app files are preserved and excluded from that push. A failed artifact checkpoint preserves original evidence for a corrected checkpoint; do not rerun provider creation just to repair persistence.

## Resource inventory and limits

Use `factory-project inventory --repo OWNER/APP --app /canonical/app --inventory /private/inventory/resources.json` for reviewed nonsecret resource registration. Top-level fields are `schema: 1`, matching `project_id`, `environment` and `resources`. Each resource has `provider` (AWS/Vercel/GitHub), `resource_id`, `resource_type`, `parent_id`, `backend_ref`, `run_id`, `source_commit`, `status` and `ownership` (managed/external). Parent/backend references are null or identify another typed resource in that inventory. Optional `url` is HTTPS without user info/query/fragment. Unknown fields, connection strings and raw responses are refused. An external/managed label records a declaration; it grants no adoption authority.

Limits per app: 128 resources/256 KiB per inventory, 256 artifact files/4 MiB total, and 128 KiB project metadata. Registry directory traversal is bounded to 1,024 entries; public publication history review is bounded to 128 registry-changing commits and otherwise stops for deliberate review. Reaching a limit requires retention/review before dependent work, not silent pruning. Symlinks, Git directories, arbitrary source paths and executable registry entries are refused. Each app owns its history/retention policy.

Legacy `FACTORY_CONTEXT_REPOSITORY` or `FACTORY_CONTEXT_DIRECTORY` settings now fail clearly. Remove them from activation/configuration; the runtime never accesses the old store. This change neither deletes an existing repository nor migrates its contents implicitly. Existing original evidence can be deliberately registered with its verified app; installation, credential grants, runtime publication and fresh-task acceptance remain separate gates.
