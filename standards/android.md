# Android applications and APK delivery

Apply [product co-architecture](product-architecture.md) and [application design](application-design.md) to Android products. Agree the delivery milestone: an unsigned APK handed off for later signing, or a signed standalone application installed on an Android device, integrated with its backend when needed. Unsigned APKs are not installable. Source and product records belong to the app repository; shared guidance and focused helpers belong to the factory. These rules apply to every selected AI client.

## Product and architecture

Choose Kotlin/native, React Native or another supported framework from the product's needs and plausible evolution. Android support does not require a particular UI framework, Expo/EAS, a web frontend, a database or a fixed AWS stack. Host APIs/data independently of the ephemeral development environment. Native applications are untrusted clients: embedded API configuration is readable, and AWS credentials, database passwords and signing secrets must stay out of the APK.

Consider supported devices/API levels, touch/navigation/back behavior, keyboard and screen sizes, accessibility, theme/contrast, permissions and denial/revocation, deep links and authentication where relevant. Design for interrupted requests, offline/error/retry behavior, background/foreground transitions, process death and local data lifecycle. Decide offline persistence/sync rather than adding it to every app. Mobile installations can outlive a backend deployment: define compatible API/schema evolution, app updates and any minimum-client-version policy.

For a UI, consult the current personal-site/Forge design references and adapt them to native interaction. References do not require web components or a copied visual system. Keep distribution audience, repository visibility, supported platforms/architectures and installation expectations in the app's engineering contract.

## Build host and app-owned commands

An Android build can run on a prepared Linux host; an emulator requires additional capabilities and must not be assumed available in every cloud session. Select SDK/JDK/build resources early and report actual support. Reuse the execution host's network/proxy/CA policy. Do not introduce a universal network-grant prerequisite or silently change host permissions.

The optional Android profile is app-owned: pin the compatible JDK, Android Gradle Plugin, Gradle wrapper/distribution checksum, SDK command-line tools, platform/Build Tools, and NDK/dependency versions when needed. Review official download hashes and licenses, retain dependency locks/verification where supported, and record prepared-image dependencies. Setup installs only the selected components and verifies them in a fresh session. The core factory installer does not install an Android SDK or JDK.

Define actual app commands for setup, checks, unsigned packaging, optional signing, package verification and release. The agent implements framework-specific adapters in the app; templates are references, not a generator. Ordinary builds/tests and an agreed unsigned handoff must not require signing credentials or contact signing-secret storage. A standalone signed APK must run without a development server or the previous agent VM.

## Signing identity and secrets

For the MVP, prefer one app-owned AWS Secrets Manager secret containing the keystore, passwords and alias. Initialize it once during the first authorized signed build, or enroll an existing app key; later signed builds retrieve the same identity. This is durable app infrastructure, independent of a particular VM or backend deployment. Base64 can encode the keystore inside a secret payload; it is not encryption.

Resolve the app's enrollment record before generating anything. An app confirmed never enrolled can create its first key within authorized credential scope. Persist the secret with the project's standard ownership/provenance tags in the approved namespace, read it back and verify its public certificate fingerprint, and retain the enrollment/recovery records before signing or publication. Reconcile concurrent or uncertain creation outcomes before another generation attempt. A missing, inaccessible or inconsistent enrolled secret blocks signing; it does not authorize a new identity. Do not enable automatic rotation of signing material.

Record the public certificate SHA-256 fingerprint in reviewed app configuration; keep exact secret ARN/version, access and recovery details in approved private app records. Restrict retrieval to the trusted signing identity and exact app secret, including applicable KMS permissions. The installed Android client and ordinary backend runtime do not receive it. Tags provide attribution, not proof of access isolation. Separate first-enrollment create/tag authority from routine retrieval where supported; never broaden IAM implicitly or copy factory execution credentials into app CI.

Maintain a separate encrypted recovery copy and documented owner/retrieval procedure. Never commit the keystore/passwords, upload them as workflow artifacts or include them in release files. A deliberate signing-key migration needs its own compatibility/recovery design. Retain the same application/signing identity for ordinary updates and increase the version code.

Trusted signing steps may restore keys temporarily, then remove the local key files. Verify the exact signed output with native tools against the enrolled fingerprint, package ID/version/SDK requirements and release flags. Debug/test-only builds are not release acceptance. Review/protect trusted signing and publication code according to actual repository capabilities: a job with secret access can sign an update, and workflow conventions are not hardware-backed or immutable approval boundaries.

The existing factory signing/artifact/release helpers support signed APKs only. The reference workflow currently transports signing material through GitHub secrets; it does not implement Secrets Manager enrollment/retrieval or unsigned publication. Implement the selected app-owned adapter before claiming either path works. See the [delivery guide](../docs/android-delivery.md) for the implementation boundary and custody flow.

## GitHub distribution

Use GitHub Releases for APK downloads; GitHub Packages is for supported dependency registries. Carlo supplies or manually creates the app repository under existing onboarding guidance. Prefer private distribution initially unless broader exposure is agreed. Private release access follows repository access. A signed APK does not bypass device installation consent or applicable Android developer-verification requirements.

For an unsigned handoff, retain the original unsigned APK and checksum with source/build attribution, app ID/version/SDK requirements and an explicit unsigned status. Label downloads as requiring signing before installation; do not invent a certificate fingerprint or send them through the signed-only verifier. When signing follows, retain the unsigned input and its checksum privately or as an agreed artifact, and record its relationship to the separately checksummed signed output.

The supported signed preview bundle contains exactly an APK, a non-secret release manifest and checksums. Tie it to the existing project/environment, readable project/repository/source attribution, app ID, version, SDK/toolchain, signer fingerprint and exact committed source. Review fields before public distribution. Capture release/job/actor, unsigned-input lineage and backend compatibility in appropriate app records; a Git author is not the authenticated release actor. Do not embed raw provider inventory or secrets in downloadable metadata.

App CI uses its explicit repository-scoped job credential with the permissions needed for the actual release. GitHub Actions authentication is separate from the cloud agent's managed GitHub route. A new helper does not fix or bypass that route's authentication substitution. Stop the affected action on an effective permission failure.

Publish to one exact repository/visibility, source and tag. Use a draft for initial uploads; read back all asset bytes before making the preview visible. Preserve conflicting tags/assets/releases and uncertain outcomes. Never use clobber/delete/recreate as automatic recovery. Reconcile a matching partial draft without duplicating writes. Published build bytes remain unchanged by convention; the helper is not a provider-enforced immutable release boundary.

## Acceptance and continuation

Separate source/tool tests, app CI, signature/package verification, release-byte readback, emulator/device behavior and live backend acceptance. An unsigned milestone proves the agreed build/handoff checks only; record installation and signed-app acceptance as not performed. Signing access failures do not block an independently agreed unsigned milestone. Do not silently downgrade a requested signed delivery to unsigned.

A helper-generated manifest asserts which source was built; package inspection alone cannot independently prove source-to-binary correspondence. A checksum verifies bytes, not publisher identity or app correctness. Pin and review the build workflow, and retain its source/job evidence.

For installable delivery, verify important journeys on a real Android device or a validated emulator: install/launch, input/navigation/accessibility, applicable permissions and interruptions, API/data writes, close/reopen persistence and error/retry behavior. Backend tests or mobile browser screenshots do not certify the native app. Label manual-device evidence honestly; never claim the agent operated a physical phone without that capability.

For updates, compare the prior verified release contract, increase version code and install over the previous app without silently uninstalling it. Verify important local/server data survives. Repeat from a fresh authorized session using durable source/signing references and reconcile existing releases/resources. Keep app, backend, release assets and operating records independent of the old VM.

Cleanup follows [Carlo's reviewed approval](cleanup.md). Include downloads/tags where authorized, build artifacts/caches, backend/data, publications, costs and explicit signing-secret/backup retention. Removing a download does not uninstall existing copies. Do not automatically delete a key when retiring compute or a backend; account for installed clients and recovery before any approved deletion.
