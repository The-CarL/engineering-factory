# Full application build and cleanup retrospective

Recorded 2026-10-26 from Carlo's supplied technical replay of the first complete Your Move exercise. This is a redacted **reported run**, not fresh provider verification. App source, exact resource identities, raw evidence and cleanup approval belong in the app's own records.

## What the run established

The app used React/Vite on Vercel, API Gateway HTTP API to Lambda, and private Aurora PostgreSQL through the RDS Data API. Browser storage supported game resume; PostgreSQL held shared history. Request IDs and versioned SQL handled retries/concurrent moves.

After recovery and a CORS fix, hosted browser checks reportedly passed keyboard play, completed games, refresh/resume, duplicate/stale requests, score counts and mobile layout. Separate database queries matched the browser-completed rows. Custom DNS, Forge publication and comprehensive teardown were subsequently exercised.

These were app choices, not a factory template or mandatory stack. Aurora pause settings, Lambda concurrency, API throttling and log retention were configured workload controls, not measured billing or hard dollar caps. No single measured end-to-end build duration was reconstructed.

## Design and onboarding

The agent initially started a different hosted PostgreSQL onboarding flow and asked Carlo to accept its terms; Carlo corrected the requirement to AWS PostgreSQL. No alternative database was provisioned. Available integrations should serve the agreed architecture, not silently replace it or trigger unrelated terms/credential setup.

Carlo manually created the repository, as the factory now requires. The factory should propose the repository details early, verify the returned repo and then own routine implementation. The desired workflow remains autonomous delivery after consequential decisions; manual creation is not a reason for repeated setup ceremonies.

The [toolbox](../toolbox.md) now states the available roles clearly: GitHub for VCS/CI/CD, Vercel as an optional frontend host, AWS for any suitable component, and Forge as an agreed publication destination. Broader product/design flow remains deferred; [conversational delivery](../../standards/conversational-delivery.md) supports flexible brainstorming and co-design today.

## Integration and test parity

The first live browser test failed even after health/score API checks passed. API Gateway forwarded `OPTIONS` to the default Lambda route, where the real handler returned 404. The local browser fixture had answered preflight itself and masked the missing behavior.

The app added a real 204 preflight response without database access, removed the fixture shortcut and added regression coverage before redeployment. The lesson is to route integration tests through the actual handler for the behavior being claimed. Passing implementation-shaped mocks can conceal a missing production path.

Proxy restrictions also made local loopback browser testing unavailable. Browser integration in CI used the real handler with embedded PostgreSQL; hosted browser tests then exercised the actual public deployment and cloud database. Those are complementary evidence, not interchangeable proofs. See [testing standards](../../standards/testing.md).

## Tooling friction and reusable fixes

| Run finding | Resulting factory status |
|---|---|
| Vercel connector team-scope denial, while the configured native CLI credential worked. | [Toolbox](../toolbox.md) distinguishes credential transports. A failed/uncertain write still needs reconciliation before switching routes. |
| Native Vercel CLI rejected a selected project without `VERCEL_ORG_ID`. | [PR #15](https://github.com/The-CarL/engineering-factory/pull/15) derives the verified org from recorded team when appropriate and rejects conflicting values. |
| Public Forge target rejected by private-default GitHub visibility checks. | Explicit target visibility remains required; public target authority must be verified rather than inferred. |
| A Forge feature worktree conflicted with helpers assuming only an independent clone / directory `.git`. | PR #15 supports verified linked app worktrees and common Git storage locking while retaining origin/config/confidentiality checks. |
| Typed inventory rejected native IDs such as API `$default`, an RDS secret identifier shape, domain names and certificate IDs. | PR #15 expanded the typed schema and export/restore coverage; strict secret/ownership validation remains. |
| Transient custom-domain fetch failure, non-executable teardown helper, Vercel status-line parser mismatch. | Reported app-local corrections. Shared promotion remains unverified; see O5 in the [history index](README.md#unresolved-and-deferred-work). |
| Earlier Vercel credential test created/read back a project, but an omitted `publicSource` failed the wrapper assertion. | Separate unresolved compatibility issue, O4. Creation success must not be erased by a later validation failure or blindly retried. |

PR #15 also added clearer tooling, cleanup and publication guidance. A merged fix is not proof an older runtime or existing app seed received it. The [AWS investigation](aws-and-dns.md) records the separate prepared IAM correction and actual stack recovery.

## Publication and comprehensive cleanup

The Forge listing and screenshot were published. The first cleanup removed the Live link and marked the entry retired but left its source article and screenshot, so the card/article remained visible. A follow-up removed both files and verified the production listing absent and article/image URLs returning 404.

**Lesson:** decide whether Carlo wants an archive or complete removal, include every publication asset in that exact plan, and verify production. A source PR, retired label or removed link alone does not establish removal. Forge/site source and live behavior must both be considered.

Infrastructure cleanup first required a reviewed change to database deletion protection and snapshot retention. The reported result removed all stack resources plus the separately managed app role/policy, and checked for retained databases/backups/secrets, workloads, logs, network children and DNS. Vercel project/deployment/aliases returned absent. A system-managed certificate could not be deleted through that endpoint and remained a provider-controlled record; shared assets and source repositories were preserved.

Deletion accepted is not deletion complete. The recorded cleanup interval was about 25 minutes, including roughly 15 minutes from stack-deletion acceptance to confirmation; it was not a measured full-build duration or proof of zero billing. Report provider-managed remnants and any unknown cost implications honestly.

The resulting [cleanup standard](../../standards/cleanup.md) requires a comprehensive, detailed plan reviewed and approved by Carlo before execution, including data/retention, external children, DNS and publications. Build authorization, an expiry tag or the original demo purpose is not cleanup approval. [Forge guidance](../forge.md) documents publication and retirement/removal choices.

## What success did not prove

The run demonstrated one reported architecture and its lifecycle after fixes. It did not prove every fresh Cloud session, GitHub credential route, IAM update, client, service or application design works. Keep source changes, actual activation and live acceptance separate. The factory should reuse this learning without turning Tic Tac Toe, Vercel hosting, Aurora or disposable demo cleanup into universal product requirements.
