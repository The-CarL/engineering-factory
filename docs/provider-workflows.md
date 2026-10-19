# Provider workflow contracts

Use official CLIs where their actual credential transport works. `gh api` is the GitHub CLI's authenticated REST interface; AWS CLI stays behind the approved role wrapper. The narrow Vercel REST helper is an explicit alternative when a network-secret placeholder fails native CLI validation. Neither an API success nor a mocked test certifies a different transport. Credentials and approved targets come from private configuration; no helper logs in, broadens permissions, changes IAM, or copies credentials to an app.

Use [bounded end-to-end runs](../standards/bounded-runs.md) to agree the concrete sequence once and execute routine steps with minimal interactions. The copyable prompt includes explicit resource/budget limits and chat-recipient authority; provider permissions and platform approvals still apply.

## GitHub creation and recovery

`create-repo.sh` keeps the complete owner inventory, visibility, exact confirmation and independent clone checks. It creates through `gh api --method POST` with JSON on stdin: `/user/repos` for the authenticated personal owner, `/orgs/OWNER/repos` for a verified organization member. The body explicitly sets `private`; the response and later inventory must agree with the target. It never substitutes a broader personal credential.

The original simple `gh repo create` path can use GraphQL. A 403 from that command does not prove the documented REST creation permission is missing. Record the actual transport and classified failure before deciding whether a permission change is needed. See the [GitHub REST creation contract](https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user) and [gh API manual](https://cli.github.com/manual/gh_api).

Provider failures retain only a bounded HTTP status, allowlisted code, fixed reason classification and recognized provider request-ID syntax. Arbitrary messages, response bodies, stderr, headers and URLs are withheld, including messages containing embedded credentials. Unknown details remain withheld rather than treated as a permission diagnosis. Never enable verbose HTTP logging to investigate credentials.

After a failed/unknown creation result, the script performs a fresh read-only inventory and stops without cloning or repeating POST. A subsequent deliberate invocation starts with inventory again and reuses an exact visible repository. A hidden target remains ambiguous; absence from inventory is not proof of global availability. No delete/recreate recovery is provided. Cloning still uses official `gh repo clone`; failures retain the same conservative classifications without Git stderr or verbose HTTP tracing. Identity/REST success does not prove clone/push credential transport. Run the authorized real clone and push gates separately; do not substitute a personal login or broaden credentials to recover.

## Vercel read-only transport gates

```bash
./scripts/preflight.sh --provider vercel --vercel-transport cli
./scripts/preflight.sh --provider vercel --vercel-transport api
```

The default remains the native CLI gate. The API gate uses `GET /v2/user` and `GET /v2/teams/ID`, verifies the exact approved team ID/slug and reports REST separately. It sends the existing `VERCEL_TOKEN` binding only to `https://api.vercel.com`; redirects are refused. A project-scoped token may not permit these reads. Stop and review a narrower identity contract instead of broadening the token or silently switching credentials.

## Vercel preview adapter

`python3 scripts/vercel-preview.py deploy` accepts a reviewed private JSON request and a clean independent app clone. It supports small non-git deployments with inline files, not project creation, linking, production, promotion, custom environments, environment-variable changes or protection changes. Costs and write authorization must already cover the exact project and build. `--confirm` is a deliberate target check, not an IAM boundary or new authorization.

Before POST it verifies the principal, exact team/project ownership/name, existing Vercel Authentication protection and a **READY production baseline**, including that deployment's actual project and target. Vercel assigns the first deployment of a project to production even when production was not requested; a failed first deployment is insufficient baseline evidence. Preview-only scope therefore blocks a project without that verified baseline. A separately reviewed protected test bootstrap can be explicitly included in the initial bounded run approval; if omitted, prepare it for approval before proceeding. The preview helper does not perform that bootstrap; do not use `target: "preview"`, staging aliases or metadata as a workaround. See Vercel's [first-deployment clarification](https://github.com/vercel/vercel/pull/17206) and [v13 API contract](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).

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

Authentication being enabled is not a claim that every production domain is protected. Verify the actual method/scope and enumerate deployment URLs, default production domains and aliases under the [bounded run plan](../standards/bounded-runs.md#test-bootstrap-is-explicit-scope); any public test domain requires explicit scope. See [Vercel protection scopes](https://vercel.com/docs/deployment-protection). The helper neither upgrades protection nor changes the plan.

After creation, the helper reads the deployment's exact project, `target: null` (preview), metadata/source and terminal state, then checks project protection again at READY. A missing target, production/staging target, mismatch, build error or timeout fails acceptance. It preserves known identities and never deletes, cancels, promotes or repeats a deployment to recover. It records the hostname privately without granting network access to it.

Client tool pins and remote build tools are different contracts. A provider-controlled build can use newer Node/npm or build CLI versions than the local runtime. Verify the app's supported `engines`, package-manager declaration and install command against the actual remote build log; do not require the remote npm version to equal a local CLI pin unless the reviewed install mechanism supplies that version. Keep lockfile/install reproducibility and record observed remote versions. An `EBADENGINE` or `invalid_engines_value` is a build configuration failure, not evidence that a token lacks deployment permission.

## Offline AWS permission preparation

Use the [S3 policy planner](s3-policy-plans.md) for a small exact-bucket/object proposal when that test is selected. It performs no AWS calls or writes, renders only private review files and leaves grant, boundary, service-model/wrapper, egress and actual data-path acceptance unresolved. Do not substitute its structural tests for IAM simulation or live proof.

## Recovery snapshots and deployed acceptance

Preserve source bundles/archives, private inventories and a snapshot of operation evidence before changing a retained run. The helper hashes only explicitly selected files; it does not export, upload, encrypt, scan or grant durable storage. Use a private root directory (700), keep the manifest private (600), retain its digest independently, then copy artifacts to approved private durable storage and verify them again from the restored copy. Source bundles still require Git bundle/ref verification when restored. A local manifest alone is not durable recovery proof.

```bash
python3 scripts/recovery-manifest.py create \
  --root /private/recovery-snapshot --manifest /private/recovery-snapshot/manifest.json \
  --commit REVIEWED_FULL_SOURCE_COMMIT source.bundle source.tar.gz project.json operations.snapshot.jsonl
python3 scripts/recovery-manifest.py verify \
  --root /private/restored-snapshot --manifest /private/restored-snapshot/manifest.json
```

Manifest creation is exclusive; it cannot silently overwrite the original hashes after tampering. Freeze/copy an append-only log before hashing it: later appends to the live log correctly invalidate that old manifest. Verification compares relative paths, sizes, modes and SHA256 and rejects symlink/path escapes. It does not establish authenticity if an attacker can replace both files and hashes.

READY is only the deployment gate. Include exact-host egress/health access in the initial bounded scope or obtain approval when needed; platform action-time confirmation still applies. Bind only the hostname returned by the verified deployment; keep provider-token domain binding restricted to the provider API. Preserve deployment protection and use an approved authenticated test path. Verify real HTTPS health/build identity, browser interaction, API/data path, exact source and private inventory/provenance. A protection login page, local-only tests or API inventory read is not app health. For AWS, separately verify the approved service's deployment and readback through the bounded role wrapper; STS/DNS reads cannot substitute for that write gate. Report each gate's result and retain partial resources for review instead of declaring end-to-end success from independent reads.
