# Setup

Start with [Create or continue an application](new-project.md). This page prepares factory tools and repository/instruction capabilities. Each app chooses its architecture/runtime/providers and owns implementation, relevant checks, CI/CD and hosting/operations.

## Local foundation checks (no provider credentials)

Prerequisites: Bash 3.2+, Git, Python 3.9+, curl, tar, and make. The tool installer supports macOS arm64 and Linux x86_64; it downloads official ShellCheck 0.10.0 and Gitleaks 8.24.3 binaries, verifies reviewed SHA256 hashes, and installs only into ignored `.cache/tools`. It never installs global tools. Unsupported platforms fail explicitly and need a reviewed checksum entry.

```bash
cd /absolute/path/to/engineering-factory
./scripts/install-check-tools.sh
make check
./scripts/preflight.sh --offline
```

`make check` requires the pinned versions, runs shell syntax/ShellCheck, repository policy, isolated mocked workflows, a synthetic scanner detection test, a scan of the current non-ignored source, and reachable Git history. CI uses the same command with full history. The default preflight inventories tools and never authenticates. Git/gh/Python are needed for GitHub workflows; Node/npm/Vercel for Vercel work; AWS CLI for Phase 3 AWS identity and policy validation. Terraform/CDK are optional and stack-specific. Provider CLIs are deliberately not installed by the validation-tool script; record and pin their reviewed versions in the environment release manifest. These checks do not install or authenticate Codex or Claude Code; see [agent compatibility](agent-compatibility.md).

## Repository workflows (after the credential gate)

Use an existing repository or prepare a concise creation brief for Carlo and ask for its URL. Do not attempt automated repository creation. Resolve the exact target from the approved owner/namespace and ask promptly when owner, visibility or consequential scope remains unresolved; follow [conversational delivery](../standards/conversational-delivery.md).

Use a shell environment with explicit, approved configuration. `.env.example` is a names-only checklist; it is not a shell script and nothing automatically loads `.env`. Do not paste credentials into commands or `source` files downloaded from another repository.

```bash
export FACTORY_GITHUB_OWNER='approved-owner'
./scripts/plan-repo.sh approved-owner/my-app --description "A short app description."
# Carlo creates the repository manually and returns its URL.
./scripts/clone-repo.sh approved-owner/my-app
cd workspaces/approved-owner/my-app
```

Carlo supplies an existing app repository or creates it manually using the brief. `plan-repo.sh` is offline; it needs only the approved owner/target and optional description. `create-repo.sh` is a compatibility alias for the same brief and performs no creation or clone. Use `--visibility public` only within approved publishing scope; private is default. Cloning an existing public/internal repo requires the matching `--visibility`. Clone checks use `GET /user` and user-backed owner/membership inventory; GitHub App installation tokens are not supported without a reviewed adapter. A successful complete visible inventory, matching visibility and independent origin are required before clone. A repository missing from inventory may be absent or inaccessible; ask Carlo for the specific creation/access action without attempting a POST or cycling credentials.

Workspace owner/repo path components are canonicalized to lowercase because GitHub names are case-insensitive. Paths are anchored to the script's factory checkout, independent of current directory. Quote paths containing spaces. Run app Git commands from its printed checkout path; never from the factory root. Existing matching clones are verified but not pulled/reset. Clone failures remove only the temporary partial clone; a retry reuses the already created repo. Existing mismatched paths/origins/visibility and symlinks fail closed. A local per-repo lock prevents simultaneous script runs; inspect active processes and paths before manually removing a stale `.REPO.lock`. Do not run concurrent untrusted processes against these directories; path checks are operational safeguards, not an OS sandbox.

### Optional namespaced GitHub binding

Direct helpers default to stock gh credential selection. Generated runtime activation defaults to `factory-token`; when sourced in the actual task shell it expands the reviewed `FACTORY_GITHUB_TOKEN` binding into `GH_TOKEN` and `GITHUB_TOKEN` for native gh/SDKs. It stores no credential values. Missing/blank bindings make sourcing fail clearly and prevent ambient/cached gh fallback, while setup and offline integrity checks remain credential-free. Explicit `cli` selection before activation generation preserves stock sources for approved local hosts. Follow the [source selection contract](provider-workflows.md#explicit-github-credential-source) for exact environment/domain scope, helper API/clone and normal Git pushes, read-only verification, per-command Git configuration and separate live transport gates. Regenerate and source activation after accepting the reviewed release. Changing the binding or credential source needs its own authorized scope; adding this option does not configure or certify it.

## Seed local app instructions

After creating/cloning an independent app, use reviewed committed factory source:

```bash
python3 scripts/seed-project.py --app /absolute/canonical/app-path --repo approved-owner/my-app --dry-run
python3 scripts/seed-project.py --app /absolute/canonical/app-path --repo approved-owner/my-app --confirm approved-owner/my-app
```

This helper verifies a standalone Git root, exact safe fetch/push origins and the committed helper/templates/application standard before writing only AGENTS.md, CLAUDE.md and ENGINEERING.md. Existing matching files are unchanged; any differing output stops all seeding for deliberate integration. It generates no app code, commands, CI or deploy tooling, and executes no hooks. Without a selected installed runtime it makes no provider calls. With that runtime, successful seeding also registers the verified app in its own `.factory/` directory; apply its generated project activation. Registration does not commit or push files. Dry-run remains offline and writes nothing. Local shared rules and pinned references serve both agents. See [project guidance](new-project.md).

## Read-only provider checks (later, with approved identities)

```bash
./scripts/preflight.sh --provider github
./scripts/preflight.sh --provider vercel
./scripts/preflight.sh --provider aws
```

Checks are provider-specific so missing AWS tools/config do not block GitHub/Vercel work. GitHub checks identity and owner inventory reads, Vercel checks principal and exact team ID under the explicit team slug, AWS checks an assumed role/account and explicit region. The public Vercel preflight invokes `whoami --format json --scope ... --non-interactive`; validate this exact contract and injection transport against the pinned executable. Unsupported flags/output or client-side token rejection fail closed. A direct API identity/team read is separate evidence and does not make this CLI gate pass. No provider response, token, email, or account ID is printed. AWS account/role validation uses the commercial `aws` partition; other partitions require a reviewed extension.

For a network-secret transport rejected by the native CLI, explicitly select `--vercel-transport api` for the separate reviewed REST identity/team gate. This establishes only REST capability. The CLI-capable design instead requires the explicitly approved personal direct `VERCEL_TOKEN` binding and a separate real native CLI check; see [credential transport](runtime-commands.md#vercel-credential-transport). The [preview adapter](provider-workflows.md#vercel-preview-adapter) requires an existing protected project, verified production baseline, private reviewed request, exact committed source and operation journal. Native CLI failure remains recorded. A project-scoped token may deny these user/team APIs; review a narrower contract rather than broadening credentials.

These checks do not verify access to a manually created app repository, clone/push/PR/CI, project deployment, service permissions, enforced limits, or budget. No universal provider dry-run exists; `--dry-run` in our repo scripts is an offline plan only. Immediately before native Vercel CLI actions, resolve the app's linked project with `vercel project inspect --non-interactive` and confirm the intended team/project. The REST adapter checks its explicit IDs through provider reads. Preflight does not link or deploy.

## Runtime source and release acceptance

Start snapshot troubleshooting with the [bounded offline diagnosis](runtime-commands.md#diagnose-the-executing-snapshot); add its fixed unauthenticated network probe only within approved internet scope. Record the executing source revision, configuration/integrity result and selected provider transport/grants separately. Passing source CI does not update a saved Cloud snapshot or establish deployment readiness.

The shipped [runtime installer/startup and provider launchers](runtime-commands.md) bootstrap a Linux x86_64 release from supported system Git/Python/glibc without preinstalled Node/npm. They install pinned provider tools without retained credentials and expose general AWS role-only reads/writes and trusted exec, explicit GitHub/Git credential selection and Vercel REST operations. Use its names-only private configuration and actual setup/start entries; this does not configure or publish Cloud automatically. Existing environments must accept the reviewed source/tool release and live grants/transports separately.

Follow [runtime standards](../standards/runtime.md) for generic installer/wrapper/check source in Git, private target configuration, pinned artifacts and a retained-files manifest. State whether the release needs a prepared snapshot or supports empty-image bootstrap; prove retained dependencies, integrity and startup in a fresh task. Track the selected provider transports, real CLI/API contracts and effective permissions separately; dated regression evidence and mocked preflight results do not certify another installation.

## Codex Cloud gate (not performed by foundation setup)

Review the foundation and complete the applicable [credential checklist](credential-checklist.md), [provider access design](access-matrix.md), and private [project/provenance record](../standards/provenance.md). Prepare the identities needed for the environment's claimed capabilities; each live write needs its approved scope. Use the [current Cloud environment guide](https://learn.chatgpt.com/docs/environments/cloud-environments) as the source of truth. From **Work in > Cloud > Select environment > Create environment**, or **Settings > Codex Cloud > Environments**, create the single environment linked to this factory when authorized. Prepare reviewed versioned install/start source with required pinned tools, network domains and credential transport verified for each selected CLI/API path. Test setup, save and publish within scope. For an existing environment, inspect its recorded revision and pending job first; do not create a replacement or duplicate publication as recovery.

Cloud environment variables are directly readable by task processes. Network secrets use domain-scoped HTTPS port-443 substitution for setup/tasks instead of placing raw values into process/files; a CLI must support the mechanism and locally signed AWS requests may need a different supported flow. Personal vault scope must be restricted to the selected environment. Cloud OIDC short-lived cloud connections are available by request for Enterprise; do not assume this account has them. See [environment variables and network secrets](https://learn.chatgpt.com/docs/environments/cloud-environments#configure-environment-variables-and-network-secrets).

Saving configuration is not publication. Check the existing publish job to completion and retain the last confirmed release; queued, stale and failed jobs remain unaccepted. Use a fresh task after confirmed publication to verify revision, retained-file integrity/startup and the capabilities claimed by that release. Select authorized representative operations for required identity/transport, repository, hosting, network and continuation capabilities. Record [private release evidence](../standards/runtime.md#release-evidence-and-recovery) and remaining gates separately from app acceptance. If browser capability is claimed, verify the actual Cloud mechanism; local Chrome configuration alone does not establish it. Verify recovery/continuation where claimed without prescribing an app type or deployment sequence.

## Versioned runtime and durable continuity

Use [Cloud-base bootstrap](runtime-commands.md#cloud-base-bootstrap-and-startup) to prepare pinned Node/npm and provider tools from a supported Git/Python Linux base. `runtime/setup.py` can reuse only an integrity-verified matching release and writes credential-free activation; apply it to task commands to avoid stale PATH wrappers or ambient GitHub credentials. Download/provider calls may require the host's supported narrow network execution grant in addition to allowed domains. Installation does not publish a snapshot or prove live writes.

[Project-owned continuity](continuity.md) keeps strict registry data and safe journals/ownership receipts in each app's own repository, alongside source and engineering decisions. Runtime evidence queues locally and is checkpointed/committed in batches at delivery milestones. Public app registries exclude confidential provider configuration and artifacts; blocked private evidence stays local without a central fallback. Merged source is not a published or activated Cloud runtime, and credential/write gates still require actual verification.
