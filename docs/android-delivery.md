# Android build, signing and GitHub downloads

This is the agent-neutral Android delivery design for an existing app repository: co-design, build a standalone APK, host its backend when needed, then deliver either an explicitly unsigned artifact for later signing or a verified signed APK through GitHub Releases. Read the [Android standard](../standards/android.md). Public stores, iOS and a managed build provider are separate optional extensions.

## What this source implements

- [Signing helper](../scripts/android-sign.py): restore app-owned environment bindings into a temporary keystore, align/sign with the selected SDK and verify the result. It never generates/rotates a key.
- [Artifact helper](../scripts/android-artifact.py): verify package identity/version/SDKs, exact signing certificate, alignment and release flags; bind the retained signed APK to clean app Git source and prepare three download files.
- [Release helper](../scripts/android-release.py): use official gh with an explicit app/job credential, verify the existing repository/visibility/source, create a source tag and draft preview, upload missing files, download/compare all bytes and publish. Preserve operation evidence; matching complete repeats perform reads only.
- [Configuration template](../templates/android/release-config.json.tmpl) and [app CI reference](../templates/android/release.yml.tmpl): render and adapt these in the app repository. They are signed-only references, are not active factory workflows and contain no app or live credentials.

| Accepted MVP direction | Current implementation boundary |
|---|---|
| Build and retain an unsigned APK independently of signing; optionally publish an unsigned handoff. | App-owned build adapter required. Existing artifact/release helpers require a signed APK and enrolled fingerprint; they do not package/publish unsigned bundles. |
| Initialize an app-owned Secrets Manager secret on the first signed build and reuse it afterward. | Guidance only: no factory secret-creation/retrieval adapter is provided. The current signing helper consumes environment bindings, and the workflow example obtains those from GitHub secrets. |
| Verify and publish signed APKs to the existing app repository. | Helpers and a reference workflow exist; actual app commands, trusted credential transport and device acceptance still need implementation/verification in that app. |

The core runtime remains unchanged: no JDK/SDK/emulator is installed by factory setup, and no existing environment is republished by this source change. App setup selects the optional Android toolchain. Native APK building, real signing, app CI publication, phone installation and fresh-session updates require acceptance on an actual app; isolated helper tests do not establish them.

## Onboard an app

1. Settle the product, framework, devices/API levels, API/data hosting, distribution audience, budget and unsigned/signed delivery milestone. Reuse known answers and existing provider scope. Have Carlo supply/create the repository as usual.
2. Add shared agent instructions and record the Android contract in the app's ENGINEERING.md. Record application ID, versions and exact compatible Java/SDK/Gradle/dependency pins. An unsigned milestone needs no signing secret or certificate enrollment. For the current signed helpers, render .factory/android-release.json with the existing project UUID/environment and enrolled public certificate fingerprint, then commit the reviewed configuration. Do not invent a fingerprint to satisfy its signed-only schema.
3. Implement app-owned ci/setup-android.sh, ci/check-android.sh and ci/build-android-unsigned.sh. The build adapter receives an absolute output filename, creates its parent directory and produces one unsigned standalone release APK. Keep the Gradle wrapper and its checksum/verification metadata in app source. For native dependencies, include required ABIs and page-size/device compatibility.
4. SDK setup verifies official archive hashes, selected SDK components and licensed use; preserve reviewed pins and any prepared-image dependencies. Set ANDROID_HOME/JAVA_HOME for later CI steps using their supported mechanism. Do not rely on a hosted runner's changing default SDK. The helpers check the Java version, Build Tools/platform properties and executable hashes; those recorded hashes are not independent publisher authenticity.
5. For a signed milestone, implement the app-owned Secrets Manager bootstrap/retrieval adapter below using existing authorized access. Reuse the app's enrolled key; create one only for a confirmed first enrollment. For an unsigned milestone, skip all signing-secret operations and provide an explicitly unsigned artifact/handoff adapter instead.
6. Render applicable template fields, including a reviewed full factory commit, Java version and expected private/public visibility. Ignore .factory-tools/ and local Android outputs in the APP checkout. Commit actual adapters, lockfiles and the adapted workflow in the app. The general instruction seeder does not create them. The existing reference workflow is signed-only and must be adapted for Secrets Manager or unsigned delivery.
7. Run app checks/builds and the selected artifact/publication path. For signed delivery, perform package/signature verification, download readback and native device/API/data acceptance; for updates, restore the prior release and check continuity. For unsigned delivery, verify retained bytes, source/build attribution and download readback if published, and state that installation/signing remain pending.

SDK/JDK installation can be performed by the authorized agent in the selected cloud host or by the app's CI setup. Reuse existing host permissions; do not recreate environments, add a read-only wrapper or invent a network-grant requirement to enable this profile. The agent owns the app adapters and routine setup; bring Carlo only consequential missing decisions or concrete actions beyond available authority.

## Signing bootstrap and custody

The preferred MVP store is one app-owned AWS Secrets Manager secret containing a Base64 keystore, keystore/private-key passwords and key alias in an encrypted JSON payload. Encoding is not encryption. Keep it within provider and adapter size limits; the current signing helper limits the encoded keystore binding to 48 KiB. Never put secret payloads in source, command arguments, logs, workflow artifacts, raw IaC state in Git or downloadable metadata.

Use this state-aware flow only when signed delivery is selected and credential creation/access is already authorized:

1. Resolve the known enrollment and private secret reference. Existing enrollment means retrieve that exact identity and verify its recorded certificate fingerprint. AccessDenied, missing enrolled material, an unexpected version/fingerprint or an unknown prior creation outcome stops signing and triggers reconciliation/recovery; none means "generate a replacement."
2. For an app confirmed never enrolled, serialize initial enrollment and reconcile any existing app-owned secret before generation. Generate once with Java keytool in a protected temporary directory, with an app-specific alias, suitable certificate validity and approved password input. Do not pass passwords as shell arguments.
3. Create the secret in the existing approved factory namespace with the project's required ownership/provenance tags, including readable project/repository attribution. Record the exact ARN/version privately. Use supported idempotency and reconcile interrupted/concurrent creates before generating or writing again; never overwrite an unrelated secret.
4. Read back the stored keystore, verify it against the generated public fingerprint, arrange the separate encrypted recovery copy and retain durable enrollment records. Commit the public fingerprint in reviewed app configuration before using the current signed helpers. A failed persistence/readback/recovery step prevents first signed publication.
5. Later signed builds retrieve the enrolled secret, verify the fingerprint, restore the keystore only for signing and remove temporary files afterward. Preserve the original unsigned APK/checksum and record its relationship to the signed APK/checksum. Secret updates must preserve the enrolled identity; automatic signing-key rotation is disabled.

Provisioning and routine signing have different needs: initial create/tag access does not require every subsequent build to create secrets. Restrict GetSecretValue to the exact app secret for trusted signing identities; account for KMS decrypt permissions when a customer-managed key is used. Verify applicable IAM/role boundaries rather than assuming a tag or role name grants access. Do not give the Android client or ordinary backend role access to signing material. Prefer short-lived app-owned CI authentication where available; never copy factory bootstrap keys into app CI. New IAM, trust or credential scope needs separate authorization if not already agreed.

Maintain a separate encrypted recovery copy with Carlo's approved owner/destination, and document retrieval/restore privately without publishing values. Key custody survives VM/backend replacement. Do not use a shared factory-wide signing key or delete signing material as routine compute cleanup. Explicit key migration, retention and deletion decisions must account for installed apps and future updates.

### Existing helper transport

An app-owned Secrets Manager retrieval adapter can supply these existing bindings only to the trusted signing process. No such adapter is currently shipped. The reference workflow uses GitHub secrets for these bindings and does not implement the preferred Secrets Manager flow; adapt it deliberately before use.

| Binding | Contents |
|---|---|
| ANDROID_KEYSTORE_BASE64 | Base64-encoded keystore; the current helper bounds this input to 48 KiB. |
| ANDROID_KEYSTORE_PASSWORD | Keystore password, supplied only to the signing step. |
| ANDROID_KEY_PASSWORD | Private-key password, supplied only to the signing step. |
| ANDROID_KEY_ALIAS | Alias selecting the enrolled key; the alias alone is not secret. |

If retaining the GitHub-secret transport by an explicit app decision, verify repository/environment-secret setup authority separately from code/PR access. Neither that transport nor Secrets Manager protects against trusted workflow code with permission to retrieve the key. Apply the repository protections actually available and do not claim an independent signing approval boundary.

The signing helper passes passwords through the narrow child environment and Android's env password options. It does not pass the Base64 keystore or provider credentials to tools. Temporary key files are removed on normal completion/failure; abrupt host termination relies on the host's ephemeral-storage controls and must not be described as guaranteed secure erasure.

## Existing signed-helper commands

Use a reviewed pinned factory checkout or app-owned audited copy of these helpers. These commands assume a prepared app-specific SDK/JDK, committed signed-release configuration and approved secret bindings; they do not create/retrieve Secrets Manager secrets, provision IAM or support unsigned publication.

```bash
python3 /absolute/factory/scripts/android-sign.py --unsigned /absolute/build/unsigned.apk --config /absolute/app/.factory/android-release.json --sdk-root /absolute/android-sdk --java-home /absolute/jdk --output /absolute/build/signed.apk

python3 /absolute/factory/scripts/android-artifact.py --source /absolute/app --config /absolute/app/.factory/android-release.json --apk /absolute/build/signed.apk --sdk-root /absolute/android-sdk --java-home /absolute/jdk --output /absolute/new-bundle
```

For an update, append --previous-manifest /absolute/previous/release.json to artifact preparation. This checks project/environment/application/signing identity and an increased version code; actual update installation/data preservation is a separate test. The previous record must come from the reconciled app release, not an arbitrary file. Passing no previous manifest means update continuity has not been checked.

The output directory contains app.apk, release.json and SHA256SUMS. It must be new and its parent must already exist. Keep outputs outside source or ignored. The helper reads clean Git HEAD/origins and records branch/author, tool versions/hashes, certificate fingerprint and APK bytes. It refuses debug/test-only/split builds and unsupported manifest output. It neither compiles the app nor proves that arbitrary input bytes were built from that source; the reviewed build job supplies that assertion. Its current manifest does not record the unsigned input; retain that lineage in app-owned build/release evidence.

For publication, give the official pinned gh path and an explicit GH_TOKEN belonging to this app/job through the environment:

```bash
python3 /absolute/factory/scripts/android-release.py --bundle /absolute/new-bundle --repo OWNER/REPO --visibility private --tag android-v0.1.0 --source-commit FULL_APP_COMMIT_SHA --gh /absolute/pinned/bin/gh --record /absolute/private/new-release-operation.jsonl
```

The helper uses an isolated gh config and preserves required proxy/CA variables. It never logs tokens or falls back to cached personal auth. The intended CI path uses the workflow's ephemeral GITHUB_TOKEN as GH_TOKEN; it does not import FACTORY_GITHUB_TOKEN. The package job has read-only GitHub repository permission; only the publish job requests contents: write. Signing secrets are provided only to the signing step. Both jobs use reviewed source; changing a release workflow can change its authority, so this is not an independent approval boundary.

The current factory-gh wrapper accepts scoped REST/PR commands, not release uploads. This standalone CI helper provides the dedicated native release path. It is not a PAT-routing workaround and does not broaden cloud connector grants. Use it in another host only under that host's verified approved credential/target contract.

## Failure, records and recovery

The publisher verifies that the exact source commit exists remotely. Its MVP supports lightweight source tags; it preserves and rejects annotated/conflicting tags rather than rewriting them. A missing tag may be created. Existing releases must match the exact source/manifest marker and preview mode; unrelated releases are not adopted. No asset is clobbered or deleted.

Draft-aware lookup resolves the exact pending tag through GraphQL and then reads its numeric release ID; REST by-tag lookup alone covers published releases. A matching partial draft can be continued with the original unchanged bundle and a new operation-record filename. The helper uploads only missing files and reads back every remote byte. A failed/unknown mutation is not retried inside the call. An incomplete/corrupt published release is a blocker; do not silently repair it. Preserve failed records and reconcile exact state before invoking again. GitHub/API enforcement remains separate from these software checks.

Keep app-owned records of the selected unsigned/signed milestone, source/build/job/actor, retained unsigned checksum, signed checksum/certificate/version when applicable, release tag/URL, artifact retention, backend compatibility and actual installation/update/data results. Record signing enrollment state, private secret/version and recovery references without exposing values or confidential provider IDs publicly. The JSONL operation record is useful safe evidence but is not automatically inserted into the typed factory registry; checkpoint it deliberately under the app's confidentiality rules.

The referenced workflow uses manual dispatch on the default branch and serializes releases. The agent chooses the next tag and known prior release from app records. It can initiate routine already-authorized releases when that workflow-dispatch permission is actually available; otherwise report the concrete missing capability. Do not assume basic code access grants dispatch, secret setup or release write permission. A signing failure blocks the signed milestone; continue an independently agreed unsigned handoff without replacing the key or silently changing the requested outcome.

GitHub Releases stores the download; the API/database runs at its selected host. Private repo downloads require authorized GitHub access. Initial sideloading needs the phone's installation consent, and future updates are downloaded/installed manually in this MVP. A native app does not receive website-style updates when backend code changes. Check applicable developer verification before wider distribution.

## Device acceptance

Unsigned delivery records build/package checks and artifact integrity; it does not claim installation or signature acceptance. Once signed delivery is selected, use a real device or supported emulator with the relevant API/ABI. Verify the shipped APK installs/opens without a dev server, core navigation/input/accessibility, applicable permissions, lifecycle interruptions, error/retry and the real API/data flow. Close/reopen and, when relevant, restart the process/phone. For the next release, install over the old app and verify important data without uninstalling it. Continue from a fresh session and prove the same key/source/resource identity can be recovered.

Record which checks were automated, manually observed, blocked or not run. A browser-rendered mobile page does not establish native acceptance. Retiring downloads/backend/signing material requires Carlo's [comprehensive cleanup approval](../standards/cleanup.md); installed copies cannot be recalled by deleting a GitHub release.

## Primary references

- [Android command-line builds](https://developer.android.com/build/building-cmdline), [SDK manager](https://developer.android.com/tools/sdkmanager), [signing](https://developer.android.com/studio/publish/app-signing), [APK verification](https://developer.android.com/tools/apksigner) and [versioning](https://developer.android.com/studio/publish/versioning).
- [AWS Secrets Manager creation](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_CreateSecret.html) and [secret retrieval](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html).
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [workflow tokens](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) and [secret storage](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
- [Android distribution](https://developer.android.com/distribute/marketing-tools/alternative-distribution) and [developer verification](https://developer.android.com/developer-verification).
