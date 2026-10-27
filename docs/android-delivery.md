# Android build, signing and GitHub downloads

This is the agent-neutral Android delivery path for an existing app repository: co-design, build a standalone APK, host its backend when needed, sign, verify and publish the APK to GitHub Releases. Read the [Android standard](../standards/android.md). Public stores, iOS and a managed build provider are separate optional extensions.

## What this source implements

- [Signing helper](../scripts/android-sign.py): restore app-owned environment bindings into a temporary keystore, align/sign with the selected SDK and verify the result. It never generates/rotates a key.
- [Artifact helper](../scripts/android-artifact.py): verify package identity/version/SDKs, exact signing certificate, alignment and release flags; bind the retained APK to clean app Git source and prepare three download files.
- [Release helper](../scripts/android-release.py): use official gh with an explicit app/job credential, verify the existing repository/visibility/source, create a source tag and draft preview, upload missing files, download/compare all bytes and publish. Preserve operation evidence; matching complete repeats perform reads only.
- [Configuration template](../templates/android/release-config.json.tmpl) and [app CI reference](../templates/android/release.yml.tmpl): render and adapt these in the app repository. They are not active factory workflows and contain no app or live credentials.

The core runtime remains unchanged: no JDK/SDK/emulator is installed by factory setup, and no existing environment is republished by this source change. App setup selects the optional Android toolchain. Native APK building, real signing, app CI publication, phone installation and fresh-session updates require acceptance on an actual app; isolated helper tests do not establish them.

## Onboard an app

1. Settle the product, framework, devices/API levels, API/data hosting, distribution audience and budget. Reuse known answers and existing provider scope. Have Carlo supply/create the repository as usual.
2. Add shared agent instructions and record the Android contract in the app's ENGINEERING.md. Render the configuration template to .factory/android-release.json using the existing project UUID/environment, a stable application ID and enrolled certificate fingerprint. Commit the reviewed configuration. Choose exact Java/SDK/Gradle/dependency pins compatible with the app rather than copying a universal version.
3. Implement app-owned ci/setup-android.sh, ci/check-android.sh and ci/build-android-unsigned.sh. The build adapter receives an absolute output filename, creates its parent directory and produces one unsigned standalone release APK. Keep the Gradle wrapper and its checksum/verification metadata in app source. For native dependencies, include required ABIs and page-size/device compatibility.
4. SDK setup verifies official archive hashes, selected SDK components and licensed use; preserve reviewed pins and any prepared-image dependencies. Set ANDROID_HOME/JAVA_HOME for later CI steps using their supported mechanism. Do not rely on a hosted runner's changing default SDK. The helpers check the Java version, Build Tools/platform properties and executable hashes; those recorded hashes are not independent publisher authenticity.
5. Bootstrap signing once, verify secure recovery, then install app-specific secrets through an authorized channel. Repository-secret setup may need Carlo if the connector lacks that permission. This is a separate fact from code/PR access.
6. Render every template field, including a reviewed full factory commit, Java version and expected private/public visibility. Ignore .factory-tools/ and local Android outputs in the APP checkout. Commit actual adapters, lockfiles and the adapted workflow in the app. The general instruction seeder does not create them.
7. Run app checks/builds, the trusted release workflow, package verification and download readback. For an update, supply the recorded previous release and verify its contract. Complete native device/API/data acceptance before claiming delivery.

SDK/JDK installation can be performed by the authorized agent in the selected cloud host or by the app's CI setup. Reuse existing host permissions; do not recreate environments, add a read-only wrapper or invent a network-grant requirement to enable this profile.

## Signing bootstrap and custody

Generate the key once with Java keytool in a protected temporary directory, using interactive password input or an approved secret mechanism. Choose an app-specific alias and durable certificate validity, record the public fingerprint, and securely retain the keystore. Do not put passwords in shell arguments or logs, source shell environment files, or copy a keystore into the repo. Enroll the fingerprint independently before giving the signer its key.

The reference workflow expects these names:

| Binding | Contents |
|---|---|
| ANDROID_KEYSTORE_BASE64 | Base64-encoded keystore in a repository/environment secret; the helper bounds this input to 48 KiB. Encoding is not encryption. |
| ANDROID_KEYSTORE_PASSWORD | Keystore password, supplied only to the signing step. |
| ANDROID_KEY_PASSWORD | Private-key password, supplied only to the signing step. |
| ANDROID_KEY_ALIAS | Non-secret alias variable selecting the enrolled key. |

Keep a separate encrypted backup outside Actions secrets with Carlo's approved recovery owner/destination. Document retrieval and restore without publishing secret values. Do not create shared factory-wide signing credentials, reset a missing key or treat key deletion as routine cleanup. A larger keystore needs a deliberately reviewed secret-file retrieval adapter, not a public artifact or an increased unreviewed limit.

The signing helper passes passwords through the narrow child environment and Android's env password options. It does not pass the Base64 keystore or provider credentials to tools. Temporary key files are removed on normal completion/failure; abrupt host termination relies on the host's ephemeral-storage controls and must not be described as guaranteed secure erasure.

## Actual commands

Use a reviewed pinned factory checkout or app-owned audited copy of these helpers. These commands assume an already prepared app-specific SDK/JDK and approved secret bindings; they do not provision accounts or IAM.

```bash
python3 /absolute/factory/scripts/android-sign.py --unsigned /absolute/build/unsigned.apk --config /absolute/app/.factory/android-release.json --sdk-root /absolute/android-sdk --java-home /absolute/jdk --output /absolute/build/signed.apk

python3 /absolute/factory/scripts/android-artifact.py --source /absolute/app --config /absolute/app/.factory/android-release.json --apk /absolute/build/signed.apk --sdk-root /absolute/android-sdk --java-home /absolute/jdk --output /absolute/new-bundle
```

For an update, append --previous-manifest /absolute/previous/release.json to artifact preparation. This checks project/environment/application/signing identity and an increased version code; actual update installation/data preservation is a separate test. The previous record must come from the reconciled app release, not an arbitrary file. Passing no previous manifest means update continuity has not been checked.

The output directory contains app.apk, release.json and SHA256SUMS. It must be new and its parent must already exist. Keep outputs outside source or ignored. The helper reads clean Git HEAD/origins and records branch/author, tool versions/hashes, certificate fingerprint and APK bytes. It refuses debug/test-only/split builds and unsupported manifest output. It neither compiles the app nor proves that arbitrary input bytes were built from that source; the reviewed build job supplies that assertion.

For publication, give the official pinned gh path and an explicit GH_TOKEN belonging to this app/job through the environment:

```bash
python3 /absolute/factory/scripts/android-release.py --bundle /absolute/new-bundle --repo OWNER/REPO --visibility private --tag android-v0.1.0 --source-commit FULL_APP_COMMIT_SHA --gh /absolute/pinned/bin/gh --record /absolute/private/new-release-operation.jsonl
```

The helper uses an isolated gh config and preserves required proxy/CA variables. It never logs tokens or falls back to cached personal auth. The intended CI path uses the workflow's ephemeral GITHUB_TOKEN as GH_TOKEN; it does not import FACTORY_GITHUB_TOKEN. The package job has read-only repository permission; only the publish job requests contents: write. Signing secrets are provided only to the signing step. Both jobs use reviewed source; changing a release workflow can change its authority, so this is not an independent approval boundary.

The current factory-gh wrapper accepts scoped REST/PR commands, not release uploads. This standalone CI helper provides the dedicated native release path. It is not a PAT-routing workaround and does not broaden cloud connector grants. Use it in another host only under that host's verified approved credential/target contract.

## Failure, records and recovery

The publisher verifies that the exact source commit exists remotely. Its MVP supports lightweight source tags; it preserves and rejects annotated/conflicting tags rather than rewriting them. A missing tag may be created. Existing releases must match the exact source/manifest marker and preview mode; unrelated releases are not adopted. No asset is clobbered or deleted.

Draft-aware lookup resolves the exact pending tag through GraphQL and then reads its numeric release ID; REST by-tag lookup alone covers published releases. A matching partial draft can be continued with the original unchanged bundle and a new operation-record filename. The helper uploads only missing files and reads back every remote byte. A failed/unknown mutation is not retried inside the call. An incomplete/corrupt published release is a blocker; do not silently repair it. Preserve failed records and reconcile exact state before invoking again. GitHub/API enforcement remains separate from these software checks.

Keep app-owned records of release tag/URL, source/workflow run and release actor, APK checksum/signer/version, artifact retention, backend compatibility, actual installation/update/data results, costs and blockers. Keep private operational details out of public download metadata. The JSONL operation record is useful safe evidence but is not automatically inserted into the typed factory registry; checkpoint it deliberately under the app's confidentiality rules.

The referenced workflow uses manual dispatch on the default branch and serializes releases. The agent chooses the next tag and known prior release from app records. It can initiate routine already-authorized releases when that workflow-dispatch permission is actually available; otherwise report the concrete missing capability. Do not assume basic code access grants dispatch, secret setup or release write permission.

GitHub Releases stores the download; the API/database runs at its selected host. Private repo downloads require authorized GitHub access. Initial sideloading needs the phone's installation consent, and future updates are downloaded/installed manually in this MVP. A native app does not receive website-style updates when backend code changes. Check applicable developer verification before wider distribution.

## Device acceptance

Use a real device or supported emulator with the relevant API/ABI. Verify the shipped APK installs/opens without a dev server, core navigation/input/accessibility, applicable permissions, lifecycle interruptions, error/retry and the real API/data flow. Close/reopen and, when relevant, restart the process/phone. For the next release, install over the old app and verify important data without uninstalling it. Continue from a fresh session and prove the same key/source/resource identity can be recovered.

Record which checks were automated, manually observed, blocked or not run. A browser-rendered mobile page does not establish native acceptance. Retiring downloads/backend/signing material requires Carlo's [comprehensive cleanup approval](../standards/cleanup.md); installed copies cannot be recalled by deleting a GitHub release.

## Primary references

- [Android command-line builds](https://developer.android.com/build/building-cmdline), [SDK manager](https://developer.android.com/tools/sdkmanager), [signing](https://developer.android.com/studio/publish/app-signing), [APK verification](https://developer.android.com/tools/apksigner) and [versioning](https://developer.android.com/studio/publish/versioning).
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [workflow tokens](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) and [secret storage](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
- [Android distribution](https://developer.android.com/distribute/marketing-tools/alternative-distribution) and [developer verification](https://developer.android.com/developer-verification).
