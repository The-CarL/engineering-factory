# Versioned Cloud runtime and command paths

The runtime supplies general provider commands for selected application workloads. It installs no application, CI workflow, IAM grant or environment binding. Provider permissions, exact task scope and action-time controls remain the boundary; runtime commands do not authorize operations or make core resources safe by naming them.

## Diagnose the executing snapshot

Run `python3 runtime/diagnose.py` before troubleshooting a saved snapshot. It needs no configured runtime or credentials and makes no network requests by default. It reports missing source selectors/manifest/private root, the declared GitHub credential source and namespaced binding presence without values, then attempts source/runtime integrity verification in a credential-free child bounded to 10 seconds. A missing binding or selector is configuration evidence, not a provider permission decision. GitHub diagnosis requires no AWS configuration.

Use `python3 runtime/diagnose.py --network` only when the task's internet access is approved. This adds one unauthenticated fixed GitHub API HTTPS request, preserving inherited approved proxy/CA settings and TLS verification, refusing redirects and forwarding no provider tokens. The URL timeout is 4 seconds and the network child deadline is 6 seconds; DNS/socket stalls are contained by the child deadline. Results distinguish OS permission denial, DNS, TLS, proxy-tunnel/connection failure, HTTP response and timeout. An HTTP response proves neither GitHub authentication nor write access; transport failure does not establish that HTTP/authentication was reached.

The flushed `execution-start` marker precedes probes; separate probe markers and `child_started` distinguish observed process progress. Tool scheduling, action-time approval and OS process creation can occur before a child deadline can start, as described in the [Python subprocess contract](https://docs.python.org/3.12/library/subprocess.html#subprocess.run). A missing or delayed marker alone does not identify the cause. Preserve elapsed times and classifications without raw errors, secret values or environment dumps.

For a fresh published task, verify the **executing** checkout/reviewed revision, selected configuration and retained runtime integrity, then the selected provider's actual credential transport and effective grants. Source CI, a saved/published setting or an older snapshot's success cannot certify another task. A blocked or untested gate stays blocked or untested; do not start mutations to diagnose it.

## Prepared-host installation and startup

`runtime/pins.json` targets Linux x86_64 with prepared Git 2.52.0, Python 3.12.14, Node 24.19.0 and npm 11.9.0. The installer verifies those host versions, official gh 2.102.0 and AWS CLI 2.38.1 archive SHA256 pins, and the Vercel 64.5.0 npm lockfile. It uses credential-free child environments and `npm ci --ignore-scripts`; it does not bootstrap an empty OS, install host languages, run package hooks or retain download caches. Archive pins select the official distribution artifacts. Pin changes require independent hash/signature review against the publisher, including the official AWS signature.

Use a clean approved factory checkout and private configuration described by the names-only [environment design](../runtime/environment.example.json). `FACTORY_SOURCE_REPOSITORY` is the exact GitHub owner/repo; `FACTORY_SOURCE_REVISION` is a reviewed full commit. Setup can refresh only a clean exact HTTPS factory `main` checkout by fast-forward to that approved commit reachable from remote main. It never resets, switches branches, overwrites dirty files or chooses a newer revision implicitly.

For an initial checkout whose revision predates these runtime files, prepare a separate clean checkout at the reviewed commit using the host's approved Git path, verify its origin/commit and read its instructions before running this installer. The startup command becomes available in that checkout; it cannot upgrade source that does not contain it. Preserve an older or dirty checkout separately.

```bash
python3 runtime/start.py --refresh --source-only
python3 runtime/install.py --destination "$FACTORY_RUNTIME_DIRECTORY"
python3 runtime/start.py
```

Choose a new versioned runtime directory in ignored/private storage. Set `FACTORY_RUNTIME_MANIFEST` to its `manifest.json`, and put its `bin` directory on the task's PATH. Installation refuses to overwrite an existing directory. Startup and each command verify source revision/committed bytes, retained file hashes/modes/symlinks and tool executable hashes. A changed source revision needs a matching installed release; stale/missing artifacts stop execution. Hash manifests are integrity records, not independent authenticity if an attacker can replace both files and hashes. The prepared host, its system libraries and approved private configuration remain trusted inputs.

After refresh, read the current `AGENTS.md` and relevant standards before actions. Record source/runtime revision, setup/save/publication and fresh-task results separately. This source does not publish Cloud, modify personal bindings or certify the current live environment.

## Private operations

Set `FACTORY_PRIVATE_ROOT` to an existing canonical directory with mode 700. Inputs, output directories and operation evidence must stay there, outside public source (or in factory-ignored storage); JSON inputs and result/record files use mode 600. Each invocation requires a **new** output and operation record. Intent is flushed before the single operation; known credentials are rejected in command arguments and API payloads/results. Raw provider errors are withheld. Read results privately without copying credentials or inventories into chat/PRs.

An existing operation record blocks another mutation. Reconcile provider state after failure/timeout and use a deliberate new operation only when its outcome and scope permit it. Commands do not loop on mutations. AWS CLI retries are set to one attempt; trusted SDK/IaC tools also need their own reviewed retry/idempotency semantics. Results record command completion, not application acceptance.

## AWS role launcher

```bash
factory-aws --record /private/operations/aws-op.jsonl \
  --output /private/operations/aws-result.json -- SERVICE OPERATION [SERVICE OPTIONS]
```

The [STS AssumeRole contract](https://docs.aws.amazon.com/cli/latest/reference/sts/assume-role.html) supplies temporary credentials; [AWS environment precedence](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) explains the explicit child configuration. Private `FACTORY_AWS_ACCOUNT_ID`, `FACTORY_AWS_ROLE_NAME` and `FACTORY_AWS_REGION` select the exact commercial account/role/region for this operation. Bootstrap signing bindings (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN`) are used only for `sts assume-role`. Requested sessions default to 900 seconds and are limited by this launcher to 900..3600; IAM/trust policies govern actual grants and session limits. It verifies returned identity, expiry and a real `get-caller-identity` under assumed credentials before forwarding normal service **reads and writes**. There is no global read-only service allowlist.

Ambient profiles, config files, container/instance metadata, web identity, endpoint overrides and debug sources are excluded. CLI profile/region/endpoint/TLS/debug overrides, unsigned requests and alternate STS/auth flows are rejected. Bootstrap credentials never reach service children; assumed credentials remain in memory/child environments, with no credential cache, token output or fallback identity. The private role's IAM/resource policies still determine which service actions succeed.

For project context, set canonical nonzero UUID `FACTORY_PROJECT_ID` and validated `FACTORY_ENVIRONMENT` together. The role request supplies fixed `factory:managed-by=engineering-factory`, `factory:project-id`, `factory:environment` and derived `factory:scope=<UUID>-<environment>` session tags. Environments reject consecutive hyphens and the reserved component `r`; resource namespaces use `factory-<scope>-r-` to separate the environment from the resource suffix. This needs separately approved bootstrap `sts:TagSession` and compatible role trust/policies. Context-free preflight can omit both when IAM permits. Session tags do not grant actions or replace resource/deployment provenance.

The optional [AWS application permission profile](../infra/aws/README.md) renders a bounded reusable service/role policy set for administrator review. Rendering grants nothing; actual Access Analyzer validation, complete policy/boundary simulation, installation and real service-context verification are separate evidence. Its general cross-service grant supports selected workloads without a short service allowlist; review its protected inventory, fixed IAM boundary and documented authorization limits.

Trusted SDK/IaC tools can use the same verified role-only environment:

```bash
factory-aws --exec --record /private/operations/iac-op.jsonl \
  --output /private/operations/iac-result.txt -- /absolute/reviewed/tool [REVIEWED ARGUMENTS]
```

Privately configure `FACTORY_AWS_EXECUTABLE` and its exact `FACTORY_AWS_EXECUTABLE_SHA256`. Review the executable, arguments, source/dependencies, plan and credential handling before authorizing it. Exec mode is trusted execution, not an OS sandbox: the selected tool can use its session's effective authority. Its PATH includes the verified host tool directories for Node/Python/Git subprocesses. It receives validated project/environment/account/region names and optional exact same-account `FACTORY_AWS_APP_BOUNDARY_ARN` / `FACTORY_AWS_APP_POLICY_ARN` references. Prepare dependencies and private input configuration through their separately approved mechanisms; no unrelated provider tokens or ambient configuration are forwarded. It receives no bootstrap credentials or ambient profiles; stdout/stderr are captured and known credentials withheld. Never run untrusted code, credential printers or unreviewed hooks through it. App-specific IaC policies and inventories stay outside the public runtime.

## GitHub CLI and Git

```bash
factory-gh --repo OWNER/REPO --record /private/operations/gh-op.jsonl \
  --output /private/operations/gh-result.json -- api repos/OWNER/REPO
factory-gh --repo OWNER/REPO --record /private/operations/create-op.jsonl \
  --output /private/operations/create-result.json -- api user/repos --method POST \
  --input /private/operations/create-request.json
factory-gh --repo OWNER/REPO --record /private/operations/pr-op.jsonl \
  --output /private/operations/pr-result.txt -- pr create --head BRANCH --title TITLE \
  --body-file /private/operations/pr-body.txt
factory-git --repo OWNER/REPO --app /canonical/independent/app --action push \
  --branch BRANCH --record /private/operations/push-op.jsonl \
  --output /private/operations/push-result.txt
```

`factory-git` also supports `--action clone` into an absent path and `--action fetch --branch BRANCH`. Normal pushes use only the checked-out branch and exact HTTPS origin; no force/deletion/mirror, alternate remote, hooks or persistent credential setup. The pinned real gh/Git executables are called directly, avoiding shims/recursion. gh authentication uses [explicit source selection](provider-workflows.md#explicit-github-credential-source): Cloud should configure the reviewed `FACTORY_GITHUB_TOKEN` binding with selector `factory-token`. Missing bindings stop before identity requests. Default `cli` retains stock gh sources for deliberately configured hosts. No automatic login or broader fallback is provided.

The runner supports scoped REST operations, `repo create` and ordinary PR create/view/list/status/checks/diff/edit/ready commands; auth/token/config/extensions/editor/browser/debug and target overrides are rejected. PR creation requires an explicit same-owner `--head` branch, `--title` and private `--body-file`, avoiding implicit local Git history or templates from the factory directory. Address other PR operations by number/branch in the exact repository, without target URLs. Prefer explicit REST creation and the existing inventory/recovery-aware `create-repo.sh` for factory provisioning. The exact owner, user/org membership and repository/visibility are verified; private is default. Successful API auth does not prove Git credential transport or writes. Run their real accepted operations separately with the same binding and approved recipients.

These are software target checks, not token isolation. An all-repositories Contents token can still modify existing repository contents when used outside the approved path; withholding Administration does not remove that authority. Review actual scope and private access exceptions. Do not use the runtime to adopt core repositories implicitly.

## Vercel API operations

```bash
factory-vercel --project EXACT_PROJECT_NAME_OR_ID --method PATCH \
  --path /v9/projects/EXACT_PROJECT_ID --request /private/operations/request.json \
  --owner-record /private/operations/project-owner.json \
  --provenance /private/operations/provenance.json \
  --record /private/operations/vercel-op.jsonl --output /private/operations/vercel-result.json
```

This invokes the existing fixed `https://api.vercel.com` transport, refuses redirects and verifies the configured principal/team plus exact project/deployment ownership. It performs one explicit project/config/deployment operation and captures the response privately, without automatic mutation retries. Exact-target GET needs no ownership receipt. Mutations require matching `FACTORY_PROJECT_ID`/`FACTORY_ENVIRONMENT` and exactly the 13 [canonical provenance fields](../standards/provenance.md#required-metadata-mapping) in private JSON. Timestamps use UTC; `factoryExpiresAt: "none"` records approved nonexpiring retention. Values are declarations until actual source/readback/acceptance evidence establishes their claims.

For new-project `POST /v11/projects`, supply a new `--owner-record` path. Creation requires an exact absent name, private source, all-deployment protection and no automatic Git-linked build. Successful settings readback produces a private ownership receipt bound to factory UUID, team, project ID/name, original metadata and the creation journal digest. The canonical mapping remains in private inventory because project tags are unsupported. Returned IDs are retained before readback; a failed readback emits no ownership receipt and cannot silently retry.

All mutations of an existing project require that receipt and its intact successful creation evidence, with matching UUID/team/ID/name. Project and deployment changes preserve original creation attribution; new deployment requests include the exact canonical `meta` mapping. An existing name/prefix, team membership or metadata assertion alone does not allow mutation/adoption. Existing/core resources need separate explicit review; this runner implements no adoption path. Preserve receipts and creation journals durably together for later tasks.

The receipt is an operational software guard, not an IAM boundary or tamperproof proof. A broader team token retains its provider authority, including outside this runner; actual isolation needs provider scopes or a privately approved access exception. Review the [provider contract](provider-workflows.md#new-vercel-project-and-initial-release) for first-release classification, protected URLs and operational acceptance. API command completion does not mean READY or application health.

General deployment requests may carry an explicitly authorized initial/production release; the optional `vercel-preview.py` remains narrower and checks preview source bytes, production baseline, target and READY. Neither command is an app orchestrator. Native Vercel CLI and API credential transport are separate gates; an API path does not make native token validation pass.
