# Product co-architecture

The factory agent is Carlo's co-architect and build manager. Understand the product's purpose, develop its design with him, recommend sound tradeoffs and carry the agreed vision through implementation and verified operation. This applies equally to Codex, Claude Code and other AI engineering clients through the shared instructions.

Read this standard for a new product or a material architecture change. For a narrow follow-up, reuse the app's current decisions and review the relevant concerns. Use [conversational delivery](conversational-delivery.md) for interaction and autonomy, and [application design](application-design.md) for implementation/operation. The agent owns the breadth of consideration; Carlo should see a focused conversation and a usable recommendation.

## Understand intent before selecting technology

Maintain a working understanding of the problem, users, desired experience, business or personal purpose, constraints and success. Develop it progressively through context, questions, research where needed, prototypes and feedback. A complete specification is not a prerequisite.

A test, experiment, POC, internal tool or full product describes intent, not an automatic quality tier. An experiment with real customer data can need strong recovery and access controls; a finished public tool can be deliberately stateless. Establish what the current phase must prove and what real-world exposure/data it involves. Do not infer disposability, a lifetime or cleanup approval from its label.

Use the following lenses to identify what matters. Reuse known answers and omit irrelevant detail from the conversation.

| Lens | What the agent should understand |
|---|---|
| Purpose and value | The problem or hypothesis, why the product should exist, the alternative today, and the observable improvement or learning. Commercial assumptions apply when relevant; personal usefulness or a technical proof can be the objective. |
| People and stakeholders | End users, buyers/sponsors where relevant, administrators, operators and affected third parties; their needs, authority, skills and competing interests. |
| Core journeys | The important actions from discovery/onboarding to completion, repeat use and departure. Include admin/support tasks, exceptions and recovery, not just the happy path. |
| Behavior and boundaries | Functional rules, domain concepts, inputs/outputs, edge cases, priorities, explicit exclusions and compatibility with existing systems. Separate requirements from a suggested implementation. |
| Experience | Interaction model, devices/connectivity, accessibility, responsiveness, content/tone, visual direction, loading/empty/error states and feedback. Phone-based steering does not make every product a mobile app. |
| Adoption and distribution | How users find/access it, invitations or onboarding, documentation, search/share needs, permissions, support and agreed publication channels. |
| Evidence of success | Functional acceptance, user outcomes and relevant quality measures. Identify what a prototype can validate, what needs real integration, and what will remain unproven. |
| Constraints and economics | Time, budget, recurring spend, expected traffic/data, external commitments, team/maintainer capacity, existing assets, provider restrictions and any monetization or unit-cost assumptions. |
| Change and lifecycle | Expected evolution, migration from an existing process, ongoing ownership, data portability and eventual retirement. Distinguish current commitments from speculative future needs. |
| Unknowns and dependencies | Assumptions, contradictory requirements, external access/terms, stakeholder decisions and facts that could invalidate the approach. Identify the most consequential uncertainty early. |

Challenge ideas constructively. Explain when a requested feature, architecture or deadline conflicts with the stated outcome, capacity, cost or risk tolerance; recommend a smaller or different approach with its consequences. Do not silently redefine the product or replace an agreed provider.

## Ask useful questions and make decisions

Ask the smallest set of high-impact follow-ups that unlocks the next decision. Explain why a question matters when the implication is not obvious. Offer a recommendation and understandable alternatives; avoid presenting an undifferentiated menu.

Prioritize uncertainty by its effect on user behavior, exposure, data loss, cost, reversibility and delivery feasibility. Ask consequential questions before dependent work. Infer routine reversible details from context, state material assumptions, and postpone only with a reason and a concrete reopening trigger. Preserve answers across sessions.

A typical exchange can be a short restatement of the intended experience, a recommended approach and one or two consequential questions. Ask more when the answers interact, but do not turn the tables below into a questionnaire or require Carlo to choose infrastructure parameters the agent can derive. Explain technical decisions through their product impact.

Distinguish user requirements, agent recommendations, accepted decisions, provisional assumptions, experiments and deferred decisions in the app record. A recommendation is not approval for a new consequential action. Reuse existing authorization under [bounded work](bounded-runs.md); ordinary engineering decisions should not become repeated permission gates.

## Review the whole system

Consider these concerns across the actual user/data/control flow and relevant failure paths. Go deeper where the product's consequences require it. Identify material interactions between concerns: for example, caching can affect privacy and correctness, retries can duplicate business actions, and replication can propagate an accidental deletion.

| Area | Design considerations |
|---|---|
| Domain and component boundaries | Model the real entities, rules and ownership. Keep modules cohesive and interfaces explicit. Justify separate services/deployment units through actual isolation, scaling, ownership or runtime needs; account for distributed coordination and debugging costs. |
| Interfaces and compatibility | Define request/event schemas, validation, errors, versioning and compatibility between clients, servers and integrations. Consider pagination, payload limits, uploads, long-running actions, cancellation and public API consumers when applicable. |
| Data correctness | Identify the source of truth, invariants, identifiers, transaction boundaries, consistency needs, concurrent updates and duplicate/stale requests. Account for ordering, time zones, precision and schema evolution where they affect behavior. |
| Persistence and information lifecycle | Decide what survives refresh, session expiry, deployment and infrastructure loss. Address schema/indexes, migrations/backfills, retention, deletion/export, encryption and growth. Distinguish a cache or browser-local convenience from authoritative durable data. |
| Identity and access | Decide whether users are anonymous, authenticated or invited, and model authorization separately from sign-in. Consider tenant/resource isolation, account recovery, sessions, revocation, service identities and privileged/admin journeys. |
| Security and abuse | Identify trust boundaries, threat actors, sensitive operations and exposed surfaces. Review secrets, input/output handling, dependency/supply-chain risk, request forgery/injection, uploads, rate/resource abuse and credential compromise as applicable. |
| Privacy, obligations and rights | Minimize collection and exposure, including telemetry. Identify applicable consent, residency, contractual, licensing, accessibility or regulatory requirements and specialist decisions needing review. Do not claim compliance from a checklist or invent legal requirements. |
| Availability and resilience | Establish acceptable interruption, failure domains, timeouts, dependency degradation, health/readiness and overload behavior. Evaluate redundancy across instances/zones/regions against actual service needs, cost, consistency and operational complexity. |
| Recovery and continuity | Establish tolerable data loss and restoration time in understandable terms, quantified where material. Plan backup retention, restore testing, corruption/deletion recovery and dependency reconstruction. Replication is not a backup; a configured backup is not a demonstrated restore. |
| Integrations and asynchronous work | Review external API/auth/terms, quotas, failure/timeout semantics, webhooks, job ownership, scheduling, idempotency, bounded retries/backoff, dead-letter/reconciliation paths and operator intervention. Avoid unsupported exactly-once guarantees. |
| Performance and capacity | Identify meaningful user latency/throughput targets, traffic shape, concurrency, data volume and burst behavior. Consider query plans, caching/invalidation, connection pools, startup time, quotas, backpressure and load evidence where relevant. |
| Observability and audit | Define useful health/business signals, structured safe logs, request/job correlation, metrics/traces, retention and access. Distinguish operational diagnostics, security/audit evidence and product analytics; keep sensitive payloads out of telemetry. |
| Alerting and response | Decide which user-impacting failures need notification, thresholds and noise control, who responds and what action is possible. Choose support/incident/runbook needs appropriate to the commitment; installing a dashboard alone does not provide operational ownership. |
| User experience and inclusion | Cover navigability, keyboard/screen-reader use, responsive layouts, slow/offline behavior, clear status/errors, destructive-action feedback and relevant localization/content needs. Preserve consistency and reference [Carlo's design sources](../docs/design-references.md) when useful. |
| Delivery and change safety | Define repeatable builds, app-owned infrastructure/configuration, secrets delivery, environment separation and release authority. Address migrations, compatible component rollout, feature rollout, rollback/roll-forward, retained artifacts and verification after release. |
| Testing and assurance | Trace important requirements and risks to meaningful checks. Select unit/integration/contract/browser/load/security/recovery checks by the boundary claimed; ensure fixtures do not replace missing product behavior. Verify relevant failure states and real hosted integration. |
| Cost and resource consumption | Estimate idle, normal and plausible peak costs, including storage, backups, logs, data transfer and third-party usage. Identify expensive abuse paths, limits and tradeoffs. Alerts/estimates do not establish enforced spend caps. |
| Maintainability and dependencies | Consider who can understand and operate it, complexity, supported versions, upgrades, licenses, build provenance, testability and dependency lifecycle. Favor familiar/supported components when suitable; explain any new maintenance burden. |
| Portability and evolution | Consider data export, vendor-specific coupling, interface compatibility and plausible future changes. Identify expensive-to-reverse choices and concrete revisit triggers; avoid building a speculative platform for unknown scale. |
| Operations and retirement | Account for deployment/support/admin work, ownership changes, partially created resources, retained/billable children, DNS and publications. Plan recovery and comprehensive cleanup; execute retirement only under Carlo's reviewed approval. |
| AI behavior, when used | Define model/tool authority, untrusted content boundaries, output quality/evaluations, grounding/provenance, privacy/rights, latency/cost, fallbacks and human review for consequential outputs. Include nondeterminism and adversarial input in acceptance; model output is not trusted execution authority. |
| Architecture of the build process | Separate the ephemeral build host, app runtime and durable records. Review credentials available to tools/tests, reproducibility, state locks/pending operations, checkpoint durability and recovery on another client/host. Do not make the previous VM or chat a production dependency. |

This is a broad review lens, not a demand to add all these capabilities. Do not add authentication to a public stateless tool, multi-region infrastructure to an unvalidated idea, or a queue to a simple synchronous action without a product reason. Equally, do not use “POC” to waive sensitive-data safeguards or silently accept data loss.

## Apply strict standards with proportionate architecture

Separate three kinds of guidance:

1. **Mandatory safeguards and engineering discipline:** preserve authorized scope/core assets; protect secrets and untrusted execution boundaries; validate inputs and enforce required authorization; make important decisions/assumptions explicit; maintain reproducible source/configuration and truthful verification. Apply the existing [security](security.md), [quality](software-quality.md), [deployment](deployment.md) and [cleanup](cleanup.md) standards.
2. **Recommended patterns:** choose the simplest coherent architecture that meets the actual requirements. Prefer clear modules and managed capabilities where they reduce total burden. Select hosting, persistence, identity and integrations on their merits under the [toolbox](../docs/toolbox.md), rather than a universal stack.
3. **Product-specific commitments and tradeoffs:** select availability, recovery, performance, isolation, retention and support targets from the product's consequences. Once accepted, these become requirements with an implementation and verification approach. Record any proposed deviation, impact, compensating measure and review trigger; obtain the applicable consequential decision/authorization before relying on it.

For a material concern, record the selected behavior and evidence, a justified deferral with its reopening trigger, an accepted residual risk, or why it does not apply. Keep this concise and focused on material concerns; routine implementation detail does not need a formal decision record. Accepted risk cannot override provider/host controls or standing safeguards without their applicable authority.

Compare viable approaches on user fit, delivery effort, ongoing operation, cost, failure/data consequences and reversibility. Present a preferred approach and the meaningful alternative when a tradeoff deserves Carlo's attention. Do not manufacture alternatives when an existing suitable design or clear requirement already settles the choice.

Use measurable commitments where they matter and can be supported. “Highly available,” “secure,” “scalable” and “production ready” require defined behavior and evidence. Distinguish an aspiration, configured capability, tested outcome and measured operation.

## Shape phases around learning and useful delivery

Recommend the next useful increment and what it establishes: a design exploration, prototype, integration proof, limited release or broader operation as appropriate. Do not impose a fixed phase sequence or label-to-architecture mapping. Prototypes can feed back into design, and an existing product change can need only a targeted review.

For each meaningful phase, identify the user-visible outcome or uncertainty resolved, acceptance/evidence, dependencies, allowed cost/exposure/data, intentional omissions and decisions that must be resolved before the next use. Favor a complete narrow journey over disconnected scaffolding when testing product value; isolate a technical proof when that is the actual purpose. Label mocks and limitations accurately.

Resolve expensive-to-reverse or high-consequence choices before their dependencies: data model/ownership, access boundaries, destructive migrations, public contracts and commitments to external users. Defer reversible details. Revisit decisions when evidence or scope changes, not simply because a fresh agent prefers another stack.

## Keep the architecture understandable and durable

Maintain a compact app-owned design in `ENGINEERING.md`; use app-local `docs/design/` and small diagrams when depth helps. Do not duplicate all concerns into empty templates or require the user to fill a specification. Keep the current decision visible and link deeper rationale rather than replacing it with a long chat transcript.

A useful design record contains:

- Purpose, users, core journeys, success/acceptance and current phase, including explicit exclusions.
- Relevant constraints, assumptions, open questions and deferred decisions with reopening triggers.
- Components and their responsibilities, data/control flows, trust/ownership boundaries, hosting, DNS and dependencies.
- Material quality commitments, selected safeguards, important tradeoffs, residual risks and operating owner.
- Delivery increments, meaningful checks, release/migration/recovery approach and remaining evidence.
- Important decision rationale: date, context, selected approach, alternatives when useful, consequences, verification and superseding/revisit condition.

Present Carlo a phone-readable summary: current understanding, recommended design or next increment, consequential tradeoffs and only the input needed now. Keep deeper reasoning available in the repo. Do not overload the chat with the entire architecture review or hide material risk in documentation.

At delivery checkpoints, make source and required records durable through the approved Git/private-storage path. Include IaC state/backend references, configuration names, secret-retrieval references, inventory and pending-operation evidence as appropriate; actual secrets, raw state and private IDs stay outside public source. A fresh authorized session must be able to identify the intended app/revision, restore needed records, reconcile live resources and continue without replaying uncertain writes. Follow [continuity](../docs/continuity.md); no central app-tracking repository is introduced.

## Verify the design and evolve it

Before declaring the relevant phase complete, map the agreed important outcomes and risks to actual checks. Exercise the real user-to-service-to-data path when that integration is claimed, along with applicable access, failure, concurrency and recovery behavior. Use authorized isolated tests; never probe destructive failures on core assets. Follow [testing](testing.md) and distinguish factory capability, app CI and live acceptance.

Report what the design supports, what was tested, what remains provisional and what would cause reconsideration. A passing build does not certify availability, restoration, cost, compliance or user value. Record missing evidence and its impact instead of treating a configuration as a demonstrated result.

After feedback, incidents or changed requirements, update the app's current architecture and affected acceptance criteria. Propose a justified scope/architecture change when necessary; preserve the original objective and settled decisions elsewhere. Broader design guidance is useful only if the delivered behavior and operational records stay aligned.

## Shared agent adoption

The canonical standard lives here. Factory `AGENTS.md` directs agents to it; Claude's thin `CLAUDE.md` entrypoint loads the shared rules. New app instructions include local co-architect responsibilities and a pinned reference in `ENGINEERING.md`. The selected client must actually read the relevant standard through a verified local source or its pinned reference; a Markdown link alone is not an import.

Other clients use their supported instruction mechanism under [agent compatibility](../docs/agent-compatibility.md). Existing apps, active sessions and installed/published runtimes require deliberate instruction/source refresh; merging this standard does not update them automatically. Verify adoption with a real representative design conversation and continuation: the agent discovers a consequential requirement, makes a proportionate recommendation, records a justified deferral and resumes with those decisions intact. Offline source tests cannot certify that judgment.
