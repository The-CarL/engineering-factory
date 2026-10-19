# Setup

## Local foundation checks (no provider credentials)

Prerequisites: Bash 3.2+, Git, Python 3.9+, curl, tar, and make. The tool installer supports macOS arm64 and Linux x86_64; it downloads official ShellCheck 0.10.0 and Gitleaks 8.24.3 binaries, verifies reviewed SHA256 hashes, and installs only into ignored `.cache/tools`. It never installs global tools. Unsupported platforms fail explicitly and need a reviewed checksum entry.

```bash
cd /absolute/path/to/engineering-factory
./scripts/install-check-tools.sh
make check
./scripts/preflight.sh --offline
```

`make check` requires the pinned versions, runs shell syntax/ShellCheck, repository policy, isolated mocked workflows, a synthetic scanner detection test, a scan of the current non-ignored source, and reachable Git history. CI uses the same command with full history. The default preflight inventories tools and never authenticates. Git/gh/Python are needed for GitHub workflows; Node/npm/Vercel for Vercel work; AWS CLI for the optional AWS flow. Terraform/CDK are optional and stack-specific. Provider CLIs are deliberately not installed by the validation-tool script; record and pin their reviewed versions in the later Cloud setup.

## Repository workflows (after the credential gate)

Use a shell environment with explicit, approved configuration. `.env.example` is a names-only checklist; it is not a shell script and nothing automatically loads `.env`. Do not paste credentials into commands or `source` files downloaded from another repository.

```bash
export FACTORY_GITHUB_OWNER='approved-owner'
./scripts/create-repo.sh approved-owner/my-app --dry-run
./scripts/create-repo.sh approved-owner/my-app --confirm approved-owner/my-app
./scripts/clone-repo.sh approved-owner/my-app
cd workspaces/approved-owner/my-app
```

The exact owner/repo confirmation is the caller's deliberate creation request. Use `--visibility public` only with authorization to publish; the default is private. Cloning existing public/internal repos requires the matching `--visibility`. The initial scripts use `GET /user` and user-backed owner/membership inventory. They require a user-backed GitHub CLI identity; GitHub App installation tokens are not supported without a reviewed adapter. The scripts accept GitHub.com only and require the approved personal owner to match the authenticated user, or active membership for an organization. A successful complete visible repository inventory precedes creation; inaccessible private repositories may still be hidden, so creation can safely fail with a name conflict. Failed auth, network, or malformed inventory aborts without creation.

Workspace owner/repo path components are canonicalized to lowercase because GitHub names are case-insensitive. Paths are anchored to the script's factory checkout, independent of current directory. Quote paths containing spaces. Run app Git commands from its printed checkout path; never from the factory root. Existing matching clones are verified but not pulled/reset. Clone failures remove only the temporary partial clone; a retry reuses the already created repo. Existing mismatched paths/origins/visibility and symlinks fail closed. A local per-repo lock prevents simultaneous script runs; inspect active processes and paths before manually removing a stale `.REPO.lock`. Do not run concurrent untrusted processes against these directories; path checks are operational safeguards, not an OS sandbox.

## Read-only provider checks (later, with approved identities)

```bash
./scripts/preflight.sh --provider github
./scripts/preflight.sh --provider vercel
./scripts/preflight.sh --provider aws
```

Checks are provider-specific so missing AWS tools/config do not block GitHub/Vercel work. GitHub checks identity and owner inventory reads, Vercel checks principal and exact team ID under the explicit team slug, AWS checks an assumed role/account and explicit region. Vercel requires a CLI supporting `whoami --format json --scope ... --non-interactive`; unsupported output/flags fail closed. No provider response, token, email, or account ID is printed. AWS account/role validation uses the commercial `aws` partition; other partitions require a reviewed extension.

These checks do not verify repo creation/push, project deployment, service permissions, enforced limits, or budget. No universal provider dry-run exists; `--dry-run` in our repo scripts is an offline plan only. Immediately before Vercel actions, resolve the app's linked project with `vercel project inspect --non-interactive` and confirm the intended team/project. Preflight does not link or deploy.

## Codex Cloud gate (not performed by foundation setup)

First review/merge the foundation and complete the [credential checklist](credential-checklist.md). Use the [current Cloud environment guide](https://learn.chatgpt.com/docs/environments/cloud-environments) as the source of truth. From **Work in > Cloud > Select environment > Create environment**, or **Settings > Codex Cloud > Environments**, create the single environment linked to this factory. Prepare a reviewed install/start configuration with pinned Git/gh/Python/Node/npm/Vercel and optional AWS/IaC versions, required network domains, and the credential mechanism verified for each CLI. Test setup, save, and publish only within the user's authorized scope.

Cloud environment variables are directly readable by task processes. Network secrets use domain-scoped HTTPS port-443 substitution for setup/tasks instead of placing raw values into process/files; a CLI must support the mechanism and locally signed AWS requests may need a different supported flow. Personal vault scope must be restricted to the selected environment. Cloud OIDC short-lived cloud connections are available by request for Enterprise; do not assume this account has them. See [environment variables and network secrets](https://learn.chatgpt.com/docs/environments/cloud-environments#configure-environment-variables-and-network-secrets).

Start a **new task** after publishing to verify the published environment, read-only identities/targets, separate app clone filesystem access, network access, and approved capability tests. Cloud browser/computer use is currently unsupported; local Chrome configuration does not validate Cloud execution. Complete both phone tasks and recovery proof before declaring the architecture working.
