# Application design and operation

Choose architecture from the product's users, behavior, constraints and operating needs. Define the outcome and acceptance criteria before selecting components. Use a suitable supported stack and provider; a project may be a static site, frontend, API/service, full-stack app, worker/job or another workload. Choose each component's hosting and any DNS approach during codesign, recording intentionally deferred choices and their triggers. Vercel can host a frontend when the design calls for it; AWS or another approved provider can also do so. Available integrations do not dictate the architecture. Components and verification apply when relevant to that product.

## Visual direction

For UI work, consider [Carlo's personal-site and Forge design references](../docs/design-references.md) before recommending visual direction. Their repositories own the documented styles; read the current tokens and relevant components, and use the rendered sites when layout/behavior needs confirmation. Recommend the reference or adaptation that fits the app and Carlo's stated preferences. Preserve existing app conventions unless a redesign is requested; a backend-only task does not need visual-reference research.

Keep the chosen direction and reviewed reference/source in the app's `ENGINEERING.md`. Translate it into app-owned styling appropriate to its stack and interaction needs. Validate accessibility, responsive behavior, relevant UI states, supported themes and reduced motion. Referencing these sites does not require their framework, hosting, branding, page structure or publication workflow. See the reference guide for source locations and adoption details.

## Architecture and boundaries

Lead codesign under [conversational delivery](conversational-delivery.md). Resolve consequential unknowns before dependent implementation, state material inferred assumptions and record deferred decisions with triggers. Establish feasibility for the intended build/test/hosting/integration path early. Maintain the design and remaining work as a prototype becomes a working solution; do not silently substitute a local or mocked result for agreed acceptance.

- Select only required components: interface, server/API, storage, authentication, queues, schedules or integrations. Record their responsibilities, data flow, runtime/region/limit support and important tradeoffs in the app's `ENGINEERING.md`.
- For interacting components, define input/output schemas, errors, ownership and source/configuration compatibility. A full-stack app needs its interface and server integration verified; an API or worker can operate without a browser interface.
- Validate untrusted input at the relevant boundary, constrain resource use and return safe errors. Enforce authentication/authorization where required. Keep credentials and privileged configuration in trusted execution, with a clear distinction between public configuration and secrets.
- If durable data is required, define schema/migrations, ownership, authorization, retention, restore and required durability. For jobs/events, define execution, idempotency/retry, output and failure handling appropriate to the workload.

## App-owned implementation and checks

Each independent app owns its source, relevant dependency/tool pins and lockfiles, commands and any CI/CD. Choose automation appropriate to its validation and release needs. Record the actual install, development, validation, packaging or execution commands that apply. Typecheck, build, browser and API commands are used when the chosen stack/workload needs them; the instruction seed does not implement these commands or workflows.

Test meaningful behavior and failure modes under [testing standards](testing.md). Verify the real product outcome with workload-appropriate evidence: rendered content and interactions for a UI, request/response and access boundaries for an API, execution/output/retry for a job, and component integration when present. Test required data durability and recovery. Local mocks can isolate dependencies but cannot certify the hosted integration. Factory validation does not run or certify app CI.

Keep factory execution credentials out of app CI. Use its reviewed app-owned authentication and least-privilege permissions, and verify actual checks run on the intended source. Untrusted code/tests must not receive privileged execution credentials.

## Hosting and operations

Choose deployment targets and processes for the product. Use reviewed provider CLI/API/IaC operations, explicit target/identity checks, cost limits, [provenance](provenance.md) and private resource inventory. Provider installation and identity reads do not establish write capabilities. Provider-specific contracts apply only to projects using that provider; see [deployment](deployment.md) and [provider workflows](../docs/provider-workflows.md).

Record the relevant source/build identities, runtime/configuration revisions, dependencies, secret names/private references, protection or public exposure, operational checks and actual results. When multiple components deploy independently, verify compatible versions and interfaces. Define monitoring, rollback, retry, data migration/restore and cleanup ownership appropriate to the app.

Maintain a continuation contract: exact independent repository/origin, applicable instructions, actual commands, non-secret configuration names and private hosting/recovery references. Push source or export privately and verify restoration before relying on a fresh task. Reconcile known resources and outstanding operations before another mutation.
