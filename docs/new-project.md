# Build a new frontend and backend project

Use one permanent factory environment to create and operate many independent apps. The factory supplies repository safety, instruction seeding, standards and provider/recovery helpers. The agent implements each app's frontend, real backend, commands, CI/CD and reviewed deployment path in that app's own repository. It does not commit app code or provider state into this factory.

## One scope, then execute

Start in the factory environment and prepare one concrete [bounded scope](../standards/bounded-runs.md) from the user's request and approved private configuration: exact repo/provider targets, initial release/public exposure, required services/permissions, cost/request limits, provenance and recovery. Reuse existing exact authorization and resolve routine implementation choices without another approval. No chat handoff is required. Message another chat only if the human authorized that exact recipient/purpose.

Within that scope, continue create → clone → develop → push/CI → deploy → browser/API verification without per-step questions. Ask only for unresolved consequential scope changes or required action-time approval, with the concrete diff/target prepared. Provider controls and actual permissions still apply; a task prompt or successful read is not a write grant.

## Workflow

1. **Verify the environment and target.** Check the recorded factory/runtime revision, retained tools, selected credential source, approved owner/team/account/region and provider operations. Fix or report actual capability blockers before a mutation; do not silently substitute credentials. Choose the backend for the product: a supported framework's server endpoints may keep frontend/API together; a separate backend or AWS needs an appropriate reviewed profile. Persistence is optional unless the product requires it.
2. **Create the independent private repo and seed instructions.** Use `create-repo.sh OWNER/REPO --dry-run`, then the approved confirmed creation. Verify the standalone checkout, fetch/push origins and expected visibility. From the factory run the local instruction helper below. It creates only `AGENTS.md`, `CLAUDE.md` and `ENGINEERING.md`; it generates no app/server code, dependency setup or CI workflow. Both agents receive local shared rules plus commit-pinned factory references. Existing differing instructions require deliberate integration, not overwriting.
3. **Implement the app-owned contract.** Choose a suitable stack, pin dependencies and commit lockfiles. Fill `ENGINEERING.md` with actual install/dev/test/typecheck/build/browser commands, API/data/auth/config decisions and operational/resume details. Implement the frontend and a real server/API backend used by it. Validate server inputs and errors, keep secrets server-only, and add auth/persistence when required. Follow [full-stack standards](../standards/full-stack.md).
4. **Push and verify independent CI.** Commit only in the app repository. Use normal pushes and the app's approved branch workflow. Implement app-owned CI with the relevant checks and safe pinned actions; do not reuse factory validation as app CI or copy factory execution credentials into it. Verify the actual check run and source commit; create/clone/push permission and Git credential transport are separate gates.
5. **Deploy the agreed frontend/backend targets.** Use reviewed provider CLI/API/IaC operations with exact identity/target checks and required provenance. Follow the [new Vercel project contract](provider-workflows.md#new-vercel-project-and-initial-release) for protected creation/readback, app source/CI/configuration and explicitly authorized first deployment: Vercel may classify it as production. This is normal agent-owned app/provider work; the shipped preview helper does not implement it and blocks without a verified READY production baseline. Include it in the initial concrete scope or prepare it for approval; never relabel a production result as preview. AWS or another backend target needs actual reviewed service permissions and deployment tooling, not merely installed credentials or STS reads.
6. **Verify and preserve the result.** Exercise the deployed browser → real API → processing/data → visible response, including relevant errors/auth and required persistence. Check compatible frontend/backend source, exact deployment/target/protection, project/run metadata and private inventory. Push source or use an approved private export with restore verification before ending. Record actual health/CI/recovery evidence and blockers; a local hash, READY status or login page alone is insufficient.

```bash
# Run from the reviewed committed factory source; use a canonical absolute app path.
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --dry-run
python3 scripts/seed-project.py \
  --app /absolute/path/to/independent-app \
  --repo approved-owner/my-app --confirm approved-owner/my-app
```

The seed helper uses local Git reads only, rejects factory targets/linked worktrees, unsafe origins and symlinks, prechecks all outputs and preserves existing differing files. Matching repeated seeds are no-ops. It requires the helper/templates/full-stack standard to match a committed factory revision; a changed seed revision may require deliberate integration with existing app instructions. It executes no hooks/builds and does not authenticate, push, deploy or grant access.

## Later fresh-task continuation

Use the same factory environment and exact saved app identity with `clone-repo.sh`. Do not assume prior workspace files survive. Read the app's instructions and `ENGINEERING.md`, restore approved private configuration through the established mechanism, run its commands and reconcile known deployments/resources before making a change. Preserve project identity and original provenance. This is ordinary continuation of the app, not a mandatory transfer to another chat or a new environment.

## Readiness evidence

Offline factory checks establish local behavior, not a working reusable Cloud release. Verify GitHub create/clone/push and actual credential provenance; namespaced source selection does not by itself resolve a permission failure. Native Vercel CLI token representation is a separate compatibility gate; REST success does not pass it. New-project creation/protection/initial release are agent/provider operations using the documented contract, not automated by the preview helper. AWS writes require the chosen app's reviewed profile and actual deployment tooling; identity reads do not establish that capability. Keep operator-specific failures and publication/fresh-task, app CI, deployed full-stack and durable continuation evidence private. Do not treat an unaccepted environment as ready or a prior operator's failure as a permanent property of every installation.

## Copyable project prompt

Fill private scope values from known configuration and present any unresolved consequential choices together. This prompt becomes authorization only when the human requests/approves its concrete scope; it does not create provider permissions.

```text
Use the engineering factory to build a net-new frontend + real server/API backend
for [PRODUCT / USER FLOW] in one independent private repository [OWNER/REPO].
Use the existing factory environment and approved runtime/tools/credentials.
Choose the smallest suitable supported stack. Do not force AWS or persistence;
use persistence/auth when the product requires them, and verify those boundaries.

Prepare one concrete initial scope using the approved private configuration:
repo/origin/branches [TARGETS]; frontend/backend deployment targets [TARGETS];
required service/action/resource/region profile [PROFILE OR NONE]; project/run
provenance; protection and exact URL/public exposure; initial-release/first Vercel
production-classified deployment [EXPLICIT INCLUDED SCOPE OR EXCLUDED];
budget/resource/build/request/time limits [LIMITS]; recovery destination [PRIVATE REF].
Reuse exact prior authorization. Ask only for missing consequential scope or required
action-time approval, after preparing the concrete plan. No compulsory chat handoff.
Other-chat coordination [NONE / EXACT HUMAN-AUTHORIZED RECIPIENT AND PURPOSE].

After that scope is authorized, execute create/clone, local instruction seeding,
frontend/backend development, meaningful app tests/typecheck/build/browser checks,
normal push and independent app CI/CD, agreed deployment and real deployed
browser -> API -> data/response verification without repeated routine prompts.
Fill the app's ENGINEERING.md with actual commands, architecture, config names,
operating/rollback/recovery and fresh-task resume details. Keep app source and
provider state out of the factory. Keep server secrets out of source/client bundles/logs;
keep factory execution credentials out of app CI and use its reviewed app-owned authentication.

Verify exact source/deployment compatibility, protection, provenance and private
inventory. Reconcile failures without duplicate mutations or broader credentials.
Make source durable via authorized Git push/private export and verify restoration.
Report actual gates, URLs privately, CI/health/recovery evidence and unresolved limits;
do not claim full-stack or environment acceptance from local mocks/provider reads.
```
