# Setup

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

Use a shell environment with explicit, approved configuration. `.env.example` is a names-only checklist; it is not a shell script and nothing automatically loads `.env`. Do not paste credentials into commands or `source` files downloaded from another repository.

```bash
export FACTORY_GITHUB_OWNER='approved-owner'
./scripts/create-repo.sh approved-owner/my-app --dry-run
./scripts/create-repo.sh approved-owner/my-app --confirm approved-owner/my-app
./scripts/clone-repo.sh approved-owner/my-app
cd workspaces/approved-owner/my-app
```

The exact owner/repo confirmation is the caller's deliberate creation request. Use `--visibility public` only with authorization to publish; the default is private. Cloning existing public/internal repos requires the matching `--visibility`. The scripts use `GET /user` and user-backed owner/membership inventory, then explicit REST creation through `gh api`; see [provider workflow contracts](provider-workflows.md). They require a user-backed GitHub CLI identity; GitHub App installation tokens are not supported without a reviewed adapter. The scripts accept GitHub.com only and require the approved personal owner to match the authenticated user, or active membership for an organization. A successful complete visible repository inventory precedes creation; inaccessible private repositories may still be hidden, so creation can safely fail with a name conflict. Failed auth, network, or malformed inventory aborts without creation.

Workspace owner/repo path components are canonicalized to lowercase because GitHub names are case-insensitive. Paths are anchored to the script's factory checkout, independent of current directory. Quote paths containing spaces. Run app Git commands from its printed checkout path; never from the factory root. Existing matching clones are verified but not pulled/reset. Clone failures remove only the temporary partial clone; a retry reuses the already created repo. Existing mismatched paths/origins/visibility and symlinks fail closed. A local per-repo lock prevents simultaneous script runs; inspect active processes and paths before manually removing a stale `.REPO.lock`. Do not run concurrent untrusted processes against these directories; path checks are operational safeguards, not an OS sandbox.

### Optional namespaced GitHub binding

The default remains stock gh credential selection. If an explicitly reviewed private Cloud binding uses `FACTORY_GITHUB_TOKEN`, set the non-secret `FACTORY_GITHUB_CREDENTIAL_SOURCE` to `factory-token` and use the factory helpers' selected child environment for API/clone and normal Git pushes. Missing bindings fail without fallback. Follow the [source selection contract](provider-workflows.md#explicit-github-credential-source) for exact environment/domain scope, read-only verification, per-command Git configuration and separate live transport gates. Changing the binding or credential source needs its own authorized scope; adding this option does not configure or certify it.

## Read-only provider checks (later, with approved identities)

```bash
./scripts/preflight.sh --provider github
./scripts/preflight.sh --provider vercel
./scripts/preflight.sh --provider aws
```

Checks are provider-specific so missing AWS tools/config do not block GitHub/Vercel work. GitHub checks identity and owner inventory reads, Vercel checks principal and exact team ID under the explicit team slug, AWS checks an assumed role/account and explicit region. The public Vercel preflight invokes `whoami --format json --scope ... --non-interactive`; validate this exact contract and injection transport against the pinned executable. Unsupported flags/output or client-side token rejection fail closed. A direct API identity/team read is separate evidence and does not make this CLI gate pass. No provider response, token, email, or account ID is printed. AWS account/role validation uses the commercial `aws` partition; other partitions require a reviewed extension.

For a network-secret transport rejected by the native CLI, explicitly select `--vercel-transport api` for the separate reviewed REST identity/team gate. The [preview adapter](provider-workflows.md#vercel-preview-adapter) requires an existing protected project, verified production baseline, private reviewed request, exact committed source and operation journal. Native CLI failure remains recorded. A project-scoped token may deny these user/team APIs; review a narrower contract rather than broadening credentials.

These checks do not verify repo creation/push, project deployment, service permissions, enforced limits, or budget. No universal provider dry-run exists; `--dry-run` in our repo scripts is an offline plan only. Immediately before native Vercel CLI actions, resolve the app's linked project with `vercel project inspect --non-interactive` and confirm the intended team/project. The REST adapter checks its explicit IDs through provider reads. Preflight does not link or deploy.

## Runtime source and release acceptance

Follow [runtime standards](../standards/runtime.md) for generic installer/wrapper/check source in Git, private target configuration, pinned artifacts and a retained-files manifest. State whether the release needs a prepared snapshot or supports empty-image bootstrap; prove retained dependencies, integrity and startup in a fresh task. Existing private helpers are not migrated by these docs. Track per-provider transport, real CLI/API contracts and effective permissions separately; see the dated regression examples rather than assuming a mock preflight proves compatibility.

## Codex Cloud gate (not performed by foundation setup)

First review/merge the foundation and complete the [credential checklist](credential-checklist.md), [provider access design](access-matrix.md), and private [project/provenance record](../standards/provenance.md). GitHub, Vercel and AWS identity preparation are all included; each live write still needs its bounded scope approved. Use the [current Cloud environment guide](https://learn.chatgpt.com/docs/environments/cloud-environments) as the source of truth. From **Work in > Cloud > Select environment > Create environment**, or **Settings > Codex Cloud > Environments**, create the single environment linked to this factory. Prepare versioned reviewed install/start source with pinned Git/gh/Python/Node/npm/Vercel/AWS and any selected IaC versions, required network domains, and the credential transport verified for each actual CLI/API path. Test setup, save, and publish only within the user's authorized scope. For an existing environment, inspect its recorded revision and pending job first; do not create a replacement or duplicate publication as recovery.

Cloud environment variables are directly readable by task processes. Network secrets use domain-scoped HTTPS port-443 substitution for setup/tasks instead of placing raw values into process/files; a CLI must support the mechanism and locally signed AWS requests may need a different supported flow. Personal vault scope must be restricted to the selected environment. Cloud OIDC short-lived cloud connections are available by request for Enterprise; do not assume this account has them. See [environment variables and network secrets](https://learn.chatgpt.com/docs/environments/cloud-environments#configure-environment-variables-and-network-secrets).

Saving configuration is not publication. Check the existing publish job to completion and retain the last confirmed release; queued, stale and failed jobs remain unaccepted. Start a **new task** after confirmed publication to verify the intended revision, retained-file integrity/startup, read-only identities/targets, separate app clone filesystem access, network access, and approved capability tests. Record [private release evidence](../standards/runtime.md#release-evidence-and-recovery) and remaining gates. Local Chrome configuration does not validate managed Cloud browser execution. Record the actual supported headless or UI browser mechanism and its end-to-end evidence separately. Complete both phone tasks and recovery proof before declaring the architecture working.
