# Android applications and APK delivery

Apply [product co-architecture](product-architecture.md) and [application design](application-design.md) to Android products. The delivery target is a standalone, signed application installed on an Android device, integrated with its agreed backend when needed. Source and product records belong to the app repository; shared guidance and focused helpers belong to the factory. These rules apply to every selected AI client.

## Product and architecture

Choose Kotlin/native, React Native or another supported framework from the product's needs and plausible evolution. Android support does not require a particular UI framework, Expo/EAS, a web frontend, a database or a fixed AWS stack. Host APIs/data independently of the ephemeral development environment. Native applications are untrusted clients: embedded API configuration is readable, and AWS credentials, database passwords and signing secrets must stay out of the APK.

Consider supported devices/API levels, touch/navigation/back behavior, keyboard and screen sizes, accessibility, theme/contrast, permissions and denial/revocation, deep links and authentication where relevant. Design for interrupted requests, offline/error/retry behavior, background/foreground transitions, process death and local data lifecycle. Decide offline persistence/sync rather than adding it to every app. Mobile installations can outlive a backend deployment: define compatible API/schema evolution, app updates and any minimum-client-version policy.

For a UI, consult the current personal-site/Forge design references and adapt them to native interaction. References do not require web components or a copied visual system. Keep distribution audience, repository visibility, supported platforms/architectures and installation expectations in the app's engineering contract.

## Build host and app-owned commands

An Android build can run on a prepared Linux host; an emulator requires additional capabilities and must not be assumed available in every cloud session. Select SDK/JDK/build resources early and report actual support. Reuse the execution host's network/proxy/CA policy. Do not introduce a universal network-grant prerequisite or silently change host permissions.

The optional Android profile is app-owned: pin the compatible JDK, Android Gradle Plugin, Gradle wrapper/distribution checksum, SDK command-line tools, platform/Build Tools, and NDK/dependency versions when needed. Review official download hashes and licenses, retain dependency locks/verification where supported, and record prepared-image dependencies. Setup installs only the selected components and verifies them in a fresh session. The core factory installer does not install an Android SDK or JDK.

Define actual app commands for setup, checks, unsigned packaging, signing, package verification and release. The agent implements the framework-specific adapters in the app; templates are references, not a generator. Run ordinary builds/tests without provider or signing credentials. A standalone APK must run without a development server or the previous agent VM.

## Signing identity and secrets

Create/enroll one durable signing identity per app within authorized credential scope; do not create a key on every build. Keep the keystore and passwords in approved app-owned secret storage, with a separate encrypted recovery copy and a documented owner/retrieval procedure. Never commit them, upload them as workflow artifacts or include them in release files. Base64 is a transport encoding, not encryption.

Record the public certificate SHA-256 fingerprint in the reviewed app configuration. Sign with Android's native tools and verify the exact output against the enrolled fingerprint, package ID/version/SDK requirements and release flags. Debug/test-only builds are not release acceptance. Retain the same application/signing identity for ordinary updates and increase the version code; a deliberate signing-key migration needs its own compatibility/recovery design.

Trusted release jobs may restore keys temporarily. Restrict secrets to the signing step and separate read-only building from release publication. A job or workflow with secret access can sign an update; these are not hardware-backed or immutable approval boundaries. Protect/review release code according to actual repository capabilities, and do not claim enforcement that the account/connector cannot provide. Never copy factory execution credentials into app CI. Verify secret-setup authority separately; a connector's code-write permission does not prove permission to configure Actions secrets.

## GitHub distribution

Use GitHub Releases for APK downloads; GitHub Packages is for supported dependency registries. Carlo supplies or manually creates the app repository under existing onboarding guidance. Prefer private distribution initially unless broader exposure is agreed. Private release access follows repository access. A signed APK does not bypass device installation consent or applicable Android developer-verification requirements.

The supported preview bundle contains exactly an APK, a non-secret release manifest and checksums. Tie it to the existing project/environment, readable project/repository/source attribution, app ID, version, SDK/toolchain, signer fingerprint and exact committed source. Review fields before public distribution. Capture release/job/actor and backend compatibility in appropriate app records; a Git author is not the authenticated release actor. Do not embed raw provider inventory or secrets in downloadable metadata.

App CI uses its explicit repository-scoped job credential with the permissions needed for the actual release. GitHub Actions authentication is separate from the cloud agent's managed GitHub route. A new helper does not fix or bypass that route's authentication substitution. Stop the affected action on an effective permission failure.

Publish to one exact repository/visibility, source and tag. Use a draft for initial uploads; read back all asset bytes before making the preview visible. Preserve conflicting tags/assets/releases and uncertain outcomes. Never use clobber/delete/recreate as automatic recovery. Reconcile a matching partial draft without duplicating writes. Published build bytes remain unchanged by convention; the helper is not a provider-enforced immutable release boundary.

## Acceptance and continuation

Separate source/tool tests, app CI, signature/package verification, release-byte readback, emulator/device behavior and live backend acceptance. A helper-generated manifest asserts which source was built; package inspection alone cannot independently prove source-to-binary correspondence. A checksum verifies bytes, not publisher identity or app correctness. Pin and review the build workflow, and retain its source/job evidence.

Verify the important journeys on a real Android device or a validated emulator: install/launch, input/navigation/accessibility, applicable permissions and interruptions, API/data writes, close/reopen persistence and error/retry behavior. Backend tests or mobile browser screenshots do not certify the native app. Label manual-device evidence honestly; never claim the agent operated a physical phone without that capability.

For updates, compare the prior verified release contract, increase version code and install over the previous app without silently uninstalling it. Verify important local/server data survives. Repeat from a fresh authorized session using durable source/signing references and reconcile existing releases/resources. Keep app, backend, release assets and operating records independent of the old VM.

Cleanup follows [Carlo's reviewed approval](cleanup.md). Include downloads/tags where authorized, build artifacts/caches, backend/data, publications, costs and signing-key retention. Removing an APK download does not uninstall existing copies; account for active clients and retained keys/data before retiring a backend.
