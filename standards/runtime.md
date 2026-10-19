# Reusable execution runtime

This standard governs environment installers, wrappers, startup checks and releases. It specifies acceptance requirements; adding it does not certify an existing private runtime or migrate private helpers into this repository. Apply [security](security.md), [testing](testing.md) and [provenance](provenance.md) alongside it.

## Source and portability

- Version generic, reviewed installer/wrapper/check source in Git. Keep credentials, exact provider targets, private inventories and operation evidence outside public Git. Link each private configuration/release to its reviewed source commit.
- Pin tools and dependencies; retain lockfiles and reviewed archive hashes or signature requirements. Verify trusted signer identity, signature validity and expiry where signatures are used. Never bypass an integrity gate to finish setup.
- Declare whether a release depends on a prepared filesystem snapshot or supports bootstrap from an empty image. A saved snapshot is not proof of an empty-image install. Record base/runtime versions, required platform capabilities and external dependencies.
- Maintain a private retained-files manifest with relative paths, versions, hashes, source linkage and required permissions for executable/configuration artifacts. Do not include secret values. A fresh task must verify retained dependencies, integrity and startup behavior rather than assume setup reruns or task files survive.

## Credential transport contracts

For every pinned provider tool, record the supported CLI/API path and actual injection transport, then test them together under approved read-only scope. Distinguish raw process credentials from HTTPS network-secret placeholders: client token validation or local request signing can require behavior that substitution cannot provide. Executable presence, a mock, or connector login proves neither transport compatibility nor authentication.

Keep separate results for native CLI and direct API requests. Vercel REST success does not establish native Vercel CLI compatibility. Use a reviewed narrow adapter when needed; do not expose raw credentials, widen scopes or bypass controls merely to satisfy an existing script. Authentication changes require their own authorization.

## Contracts and fail-fast gates

Test meaningful behavior against the real pinned executable and expected output schema as well as isolated mocks. Check required subcommands, flags, pagination and parsing, not just version/executable presence. Validate exact target and flag mappings offline before a provider call. Run shared trust/integrity gates, startup, identity/target reads and authorized capability tests sequentially; a failed prerequisite stops dependent operations.

Classify failures separately: sandbox command or Unix-socket denial; network/egress policy; provider authentication; provider permissions; target mismatch; CLI flag/output/schema mismatch. Do not reinterpret one as another or loosen effective controls as recovery. A provider-specific failure blocks that provider's dependent operations; independently validated providers may continue within approved scope. A shared trust/integrity failure blocks all provider work.

## AWS sessions

The intended bootstrap identity is assume-only into exact approved roles, with no general service authority. Review its effective policy separately from the runtime role. Immediately verify the assumed role, account, region and session identity/expiry before service actions; reject unexpected principals or targets.

Request the shortest supported, approved session and keep temporary credentials in memory or the required child environment. Do not write credential caches, persist sessions or pass secrets in argv. No broad-personal-credential or unrestricted raw-CLI fallback is allowed. A client request for 900 seconds is not a provider-enforced maximum; verify effective IAM, trust, boundary and session policies and the returned expiry separately. Wrapper command allowlists are not IAM boundaries. DNS record writes require separately scoped approval even when hosted-zone reads succeed.

## Release evidence and recovery

Maintain a private release record linked to the source commit and [environment provenance](provenance.md#environment-build-artifacts). Include the environment/snapshot revision or observed publish job ID, base/tool versions, retained-file hashes, startup/readiness results, each provider's exact identity/target read and separate CLI/API result, and remaining permission/write/deployment gates. Keep actual IDs private and retain only redacted diagnostics/evidence.

Saving configuration, publishing a snapshot and accepting a fresh instance are separate states. Poll/reconcile the existing publish job; queued, stale or failed jobs are not completed releases. Preserve the last confirmed release and its recovery reference. After an unknown outcome inspect known jobs/revisions before retrying; do not create duplicate jobs or credentials. Revalidate a fresh task against the intended published revision before advancing acceptance. Read-only success proves neither write permissions, denied behavior, deployment nor mobile continuation.

## Dated regression examples

Private setup observations reported on **2026-10-19** motivate these checks. They are version/transport-specific regressions, not permanent vendor behavior or certification of the public scripts.

| Observed contract | Required regression check |
|---|---|
| Vercel 64.5.0 accepted `--json` and deprecated `--format json`, but rejected the injected network-secret representation in token validation before HTTP; REST principal/exact-team reads used the same binding successfully | Record API and native CLI results separately; a JSON flag change alone does not repair credential transport |
| AWS CLI 2.38.1 used `get-hosted-zone --id` versus `list-resource-record-sets --hosted-zone-id` | Fail offline on each wrapper command/flag/target mismatch |
| GPG public-key import in a restricted fresh VM could not start an agent because its Unix socket could not bind | Where no agent is needed, verify `--no-autostart` with normal exit, trusted fingerprint, expiry, `GOODSIG` and `VALIDSIG` gates intact |
| The base `gh` lacked `--slurp` | Check required CLI capabilities before invoking scripts that depend on them |
