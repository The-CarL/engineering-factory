# Provider workflow contracts

Use official CLIs where their actual credential transport works. `gh api` is the GitHub CLI's authenticated REST interface; AWS CLI stays behind the approved role wrapper. The narrow Vercel REST helper is an explicit alternative when a network-secret placeholder fails native CLI validation. Neither an API success nor a mocked test certifies a different transport. Credentials and approved targets come from private configuration; no helper logs in, broadens permissions, changes IAM, or copies credentials to an app.

Use the versioned [runtime command paths](runtime-commands.md) for general provider operations. The AWS launcher forwards ordinary service reads/writes under verified assumed credentials and can run explicitly reviewed SDK/IaC tooling; its role permissions enforce effective scope. `factory-gh`/`factory-git` select one credential source. `factory-vercel` records a general project/config/deployment API operation; `vercel-preview.py` remains a separate narrower preview contract.

Use [project guidance](new-project.md) and [bounded project work](../standards/bounded-runs.md) to agree applicable consequential scope and execute routine work with minimal interactions. Select provider operations from the app's needs, include resource/budget limits and any chat-recipient authority, and preserve provider permissions/platform approvals.

See the [toolbox](toolbox.md) for provider responsibilities, native CLI/connector selection, Vercel organization/project pairing and Forge publication. Use the known exact DNS zone instead of requiring account-wide discovery.

## GitHub existing-repository onboarding and recovery

`plan-repo.sh` prints the approved owner/name, private-by-default visibility, description, empty-repository setup choices and expected unverified URL for Carlo. It is offline and writes nothing. Carlo supplies an existing repository or creates it manually, then returns its URL. `create-repo.sh` is a legacy alias for this brief; it never creates or clones, including when invoked with legacy `--confirm` flags.

The factory does not attempt `gh repo create`, REST/GraphQL repository creation, template generation or forks. The low-level creation helper and runtime creation routes reject those operations. Creation is not an acceptance probe or a reason to request a broader token. Once the target is supplied, `clone-repo.sh` verifies user-backed identity/owner membership, complete visible inventory, exact visibility and independent fetch/push origins before cloning. A missing inventory entry means not visible, not proven absent; ask Carlo to create it if needed or make the existing repository accessible. Actual clone, push, PR and CI capabilities still need their own verification. See [the manual onboarding sequence](new-project.md#repository-and-instructions).

Provider failures retain only a bounded HTTP status, allowlisted code, fixed reason classification and recognized provider request-ID syntax. Arbitrary messages, response bodies, stderr, headers and URLs are withheld, including messages containing embedded credentials. Unknown details remain withheld rather than treated as a permission diagnosis. Never enable verbose HTTP logging to investigate credentials.

If Carlo reports that he created the repository but it is not visible, inspect the exact target and actual access read-only. Do not infer absence, retry creation or broaden credentials. A failed clone preserves the existing remote target; retry only after the failed prerequisite changes. No delete/recreate recovery is provided. Cloning still uses official `gh repo clone`; failures retain conservative classifications without Git stderr or verbose HTTP tracing. Identity/REST success does not prove clone/push credential transport. Run the authorized real clone and push gates separately; do not substitute a personal login or broaden credentials to recover.

### Explicit GitHub credential source

Repository creation is manual. Credential-source selection controls what the local process receives; it cannot guarantee that a managed Cloud request path uses that same credential. Record effective access to the supplied repository separately. If a deliberately invalid credential still authenticates, stop credential-routing diagnosis and retain redacted evidence; do not cycle tokens or assume a local script changes managed authentication.

`FACTORY_GITHUB_CREDENTIAL_SOURCE` is a non-secret selector. Direct helpers default to `cli`; generated runtime activation explicitly defaults to `factory-token`:

| Mode | Child credential source |
|---|---|
| Unset or `cli` | Stock gh selection, including standard environment variables and approved CLI configuration. |
| `factory-token` | Require `FACTORY_GITHUB_TOKEN`; helpers map it to `GH_TOKEN` in their subprocesses. Runtime activation exports it as both `GH_TOKEN` and `GITHUB_TOKEN` for native tools in the activated shell. |

In helpers, an unknown mode or absent/blank namespaced binding fails before spawning either `gh api` or `gh repo clone`. Their factory subprocess environment removes competing `GITHUB_TOKEN` and enterprise-token variables; it never falls back to them. Helpers do not forward the original namespaced variable as an extra secret or change their parent environment. Values are never put in arguments, files or diagnostics. Both helper modes suppress Git/gh debug traces. Stock gh's documented [environment precedence](https://cli.github.com/manual/gh_help_environment) still applies in `cli` mode; an explicitly selected source must not be changed to escape a failure.

Before selecting `factory-token` in Cloud, obtain authorization to configure a private `FACTORY_GITHUB_TOKEN` binding for the exact approved environment and GitHub API/Git domain recipients. Reuse the reviewed token/scope if appropriate; do not create a credential, change a binding or widen domains merely because this option exists. Configure only the non-secret selector as `factory-token`. This code does not modify a Cloud environment, vault, provider token or stored gh configuration. Apply the generated [runtime activation](runtime-commands.md#cloud-base-bootstrap-and-startup) to actual task commands so native gh and conventional SDK token variables use the selected binding. Its runtime expansion never serializes the binding. Missing/blank bindings make sourcing fail with both aliases set to nonempty invalid values, preventing ambient/cached gh fallback even when the failure is ignored. Explicit `cli` activation preserves stock credential selection.

Before another existing-repository access/push attempt, verify the selected source read-only through the same pinned executable and actual transport: approved identity/owner inventory, selector/binding name and safe provider metadata such as expiry where available. Keep those facts private; do not dump headers, token values or auth configuration. A mismatch between intended settings and observed metadata leaves the cause unresolved. A namespace change is a candidate source-isolation measure, not proof that a 403 is fixed; existing-repository writes remain unverified until their real operation gates pass; creation remains manual.

For normal authorized HTTPS Git pushes, the reviewed runner must pass `env=gh_environment()` from `scripts/lib/provider.py` to its subprocess, using the verified app checkout, exact origin and approved normal refspec. Use per-command Git settings `-c credential.https://github.com.helper=` followed by `-c 'credential.https://github.com.helper=!gh auth git-credential'` to select gh without persisting configuration or chaining another credential store. This follows [gh's authenticated Git command pattern](https://github.com/cli/cli/blob/trunk/git/client.go) and [Git's helper reset contract](https://git-scm.com/docs/gitcredentials). Capture/classify failures; do not run the credential helper directly or print its output. Do not use login, `auth setup-git`, a token URL, SSH or another credential store as a fallback. Review any existing Git authentication headers/helper settings before the operation, without exposing values.

The selector controls the subprocess source; it does not prove Git's HTTPS/credential-helper or network-secret encoding behavior. API, clone and push need separate live transport evidence within the same approved recipients. Do not broaden token/domain scope or silently switch credentials when one path fails.

## Vercel read-only transport gates

```bash
./scripts/preflight.sh --provider vercel --vercel-transport cli
./scripts/preflight.sh --provider vercel --vercel-transport api
```

For a CLI-capable factory, use the explicitly approved personal **Only me** direct secret `VERCEL_TOKEN` environment design in [the credential checklist](credential-checklist.md#add-values-outside-git); approved task code can read its raw value. A REST-only network-secret binding is a separate alternative, not a native CLI solution. No `--token` secret argv, shim or silent transport switch is permitted.

The default remains the native CLI gate. The API gate uses `GET /v2/user` and `GET /v2/teams/ID`, verifies the exact approved team ID/slug and reports REST separately. It sends the existing `VERCEL_TOKEN` binding only to `https://api.vercel.com`; redirects are refused. A project-scoped token may not permit these reads. Stop and review a narrower identity contract instead of broadening the token or silently switching credentials.

## New Vercel project and initial release

The app agent performs this work through existing official CLI/REST tools. Include creation, first-release classification, protection/exposure, builds, limits and app CI/CD in the initial concrete scope. The preview helper below automates a narrower operation.

1. Verify the selected identity/team and exact project inventory; privately record creation intent, stable project/run/source identity, reviewed configuration and recovery limits. An existing same-name project or unknown previous outcome requires reconciliation, not adoption or another POST.
2. Create the new exact project with reviewed settings. The official [Create Project API](https://vercel.com/docs/rest-api/projects/create-a-new-project) is `POST /v11/projects` with explicit `teamId`; it supports `ssoProtection: {"deploymentType": "all"}`, `publicSource: false` and app build/runtime settings. Verify availability and the intended exposure before acting. Read back returned project ID, name, owner, saved protection and source visibility. Retain the project provenance mapping privately where no native metadata field exists. Stop on mismatch; never upgrade a plan or weaken protection automatically.
3. Prepare the app's tested commit, independent CI result, supported runtime/install configuration and approved server secret references. Omit optional `gitRepository` initially unless source-linked build triggers are explicitly included and their exact initial source, exposure and provenance are ready. Do not let linking or a default build bypass those gates; enable ongoing Git/CI deployment only under the app's reviewed contract.
4. Perform the explicitly scoped initial release through the reviewed native CLI or [deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment). Record intent before mutation and attach required source/run metadata. Read back actual target, project, source, READY state, generated/default/custom domains and aliases, saved protection and authenticated health. A first production-classified release must be within scope; never call it preview. Reconcile failures without duplicate mutation retries.
5. Verify the app's expected hosted behavior and private inventory/recovery. Once a READY production baseline is verified, use the preview path for subsequent preview work. Preserve [per-URL protection evidence](https://vercel.com/docs/deployment-protection) and source/configuration identity.

Tool installation, credentials and read-only checks do not establish these write/CI/health gates. Keep a particular environment's unresolved transport or permission failures in its private acceptance record.

### Vercel protection scope

Read exact API modes and current/legacy UI labels together. `prod_deployment_urls_and_all_previews` can be labeled `(Legacy) Standard Protection`; current Standard Protection distinguishes production custom domains, while legacy modes cover production aliases differently. Do not infer generated/default domain protection from “Standard.” Follow the [current protection reference](https://vercel.com/docs/deployment-protection) and saved settings/per-URL evidence. Enumerate deployment URLs, default production domains and custom domains/aliases. Public exposure must be approved; prepare a concrete alternative if intended protection is unavailable rather than automatically upgrading or weakening it.

The first deployment can be production-classified even when production was not requested. Include that exact initial-release scope before mutation. Preview-only scope blocks without a verified READY production baseline; a failed first deployment is insufficient. Flags such as `--skip-domain` do not establish classification or baseline readiness. The preview adapter below checks its narrower contract and does not perform a first release.

## Vercel preview adapter

`python3 scripts/vercel-preview.py deploy` accepts a reviewed private JSON request and a clean independent app clone. It supports small non-git deployments with inline files, not project creation, linking, production, promotion, custom environments, environment-variable changes or protection changes. Costs and write authorization must already cover the exact project and build. `--confirm` is a deliberate target check, not an IAM boundary or new authorization.

Before POST it verifies the principal, exact team/project ownership/name, existing Vercel Authentication protection and a **READY production baseline**, including that deployment's actual project and target. Vercel assigns the first deployment of a project to production even when production was not requested; a failed first deployment is insufficient baseline evidence. Preview-only scope therefore blocks a project without that verified baseline. A separately reviewed explicit initial release can be explicitly included in the initial bounded scope; if omitted, prepare it for approval before proceeding. The preview helper does not perform that first release; do not use `target: "preview"`, staging aliases or metadata as a workaround. See Vercel's [first-deployment clarification](https://github.com/vercel/vercel/pull/17206) and [v13 API contract](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).

The request may contain only `name`, `project`, `files`, `meta`, `projectSettings` and `gitMetadata`. Include exactly the 13 [provenance metadata keys](../standards/provenance.md#required-metadata-mapping); environment must be `preview`. `gitMetadata` contains only the exact `commitSha` and `dirty: false`. Omit `target` and branch hints. All inline files must equal the entire tracked file set and object bytes at the clone's clean HEAD; base64 is supported for binary content. Symlinks, submodules, duplicate/traversal paths and credential-file paths are rejected. This conservative small-app path also rejects tracked `.env.example` files; an app needing an excluded tracked file requires a reviewed adapter extension, not deleting or renaming source to bypass the gate. Scan the source for secrets and review build/install settings before preparing the request; byte equality does not prove the source is safe to execute or publish.

```bash
# Private files/directories must already have permissions 600/700 respectively.
python3 scripts/vercel-preview.py deploy \
  --source /absolute/path/to/independent-app-clone \
  --request /private/operations/preview-request.json \
  --record /private/operations/preview-operation.jsonl \
  --confirm "${FACTORY_VERCEL_TEAM_ID}/${VERCEL_PROJECT_ID}"
```

The operation journal stores UTC events, request digest, source/run identity, exact provider IDs and the verified deployment hostname; keep it outside public Git. Intent is flushed before the single POST. Unknown/rejected outcomes without an ID block another POST for that operation; reconcile provider inventory privately first. With a known ID, repeating the same request/record only reads and polls. A changed request cannot reuse the record. Do not delete the journal to retry blindly.

Authentication being enabled is not a claim that every production domain is protected. Verify [actual protection scope and per-URL coverage](#vercel-protection-scope) within the [approved release scope](../standards/bounded-runs.md#first-deployment-scope); public domains require explicit scope. The helper neither upgrades protection nor changes the plan.

After creation, the helper reads the deployment's exact project, `target: null` (preview), metadata/source and terminal state, then checks project protection again at READY. A missing target, production/staging target, mismatch, build error or timeout fails acceptance. It preserves known identities and never deletes, cancels, promotes or repeats a deployment to recover. It records the hostname privately without granting network access to it.

Client tool pins and remote build tools are different contracts. A provider-controlled build can use newer Node/npm or build CLI versions than the local runtime. Verify the app's supported `engines`, package-manager declaration and install command against the actual remote build log; do not require the remote npm version to equal a local CLI pin unless the reviewed install mechanism supplies that version. Keep lockfile/install reproducibility and record observed remote versions. An `EBADENGINE` or `invalid_engines_value` is a build configuration failure, not evidence that a token lacks deployment permission.

## Workload provider scope

Select services and hosting under [application design](../standards/application-design.md). AWS operations use the reviewed general application role profile, workload IaC plan, wrapper/tooling, provenance and workload acceptance. Service selection does not itself require extending a service allowlist; provider-specific authorization limits still require review. Existing AWS reads do not establish deployment capability. Implement and verify each selected workload through its reviewed provider path.

## Recovery snapshots and deployed acceptance

Preserve source bundles/archives, private inventories and a snapshot of operation evidence before changing a retained run. The helper hashes only explicitly selected files; it does not export, upload, encrypt, scan or grant durable storage. Use a private root directory (700), keep the manifest private (600), retain its digest independently, then copy artifacts to approved private durable storage and verify them again from the restored copy. Source bundles still require Git bundle/ref verification when restored. A local manifest alone is not durable recovery proof.

A fresh Cloud actor may receive a workspace without prior task files. Before ending a run, push source to its authorized private Git origin or export source/history and private recovery artifacts to an approved durable destination, then verify restoration in a fresh location. A summary or a hash of a workspace-local bundle does not transfer those bytes. If push/export or restoration is unavailable, retain what can be preserved and report durable recovery as blocked; do not report completion from local hashes or assume a later actor inherits the filesystem.

```bash
python3 scripts/recovery-manifest.py create \
  --root /private/recovery-snapshot --manifest /private/recovery-snapshot/manifest.json \
  --commit REVIEWED_FULL_SOURCE_COMMIT source.bundle source.tar.gz project.json operations.snapshot.jsonl
python3 scripts/recovery-manifest.py verify \
  --root /private/restored-snapshot --manifest /private/restored-snapshot/manifest.json
```

Manifest creation is exclusive; it cannot silently overwrite the original hashes after tampering. Freeze/copy an append-only log before hashing it: later appends to the live log correctly invalidate that old manifest. Verification compares relative paths, sizes, modes and SHA256 and rejects symlink/path escapes. It does not establish authenticity if an attacker can replace both files and hashes.

READY establishes a deployment state. Include relevant exact-host egress/operational access in scope; platform action-time confirmation still applies. Bind only verified workload hosts and keep provider-token recipients restricted to approved APIs. Preserve protection and use an approved authenticated check path. Verify actual source/build identity and hosted behavior appropriate to the workload, with private inventory/provenance. A login page or provider inventory read does not establish application behavior. For AWS, verify the selected service's operation/readback through the bounded role wrapper; STS/DNS reads do not prove other writes. Report capability and workload results independently and retain partial resources for reconciliation.
