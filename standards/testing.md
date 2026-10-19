# Testing

- Test observable behavior and meaningful failure modes. Use unit tests for logic, isolated integration tests for tool/API boundaries, and end-to-end tests for critical user journeys.
- No live provider writes, paid resources, real credentials, or global auth stores in ordinary tests. Mock CLIs, isolate HOME/config, and fail on unexpected calls. Verify that dry-run and failure paths make no mutations.
- Cover wrong identity/target, expired auth/network errors, interrupted work, retries, visibility, local checkout/origin mismatches, and preservation of existing files for automation scripts.
- Separate tool availability, authentication, read capability, write permission, and actual deployment verification in reports. A mock does not validate a real CLI's current flags or provider policy.
- Use deterministic fixtures and temp directories; clean up only paths owned by the test. Keep synthetic secrets generated at runtime so public fixtures do not resemble usable credentials.
- Run `make check` for this factory. CI must run the same checks under the required `Validate factory repo` job. A failure blocks merge; do not change a required check to a shallow pass.
- Validate permission boundaries and provenance separately from identity checks: review policies, simulate where supported, then use only authorized disposable positive/negative tests. Never attempt destructive denial tests against core assets. Verify every actual deployment path supplies project/environment/source/run attribution through readback and inventory; account for child/untaggable resources and retries. Missing attribution fails deployment acceptance.
- Document acceptance tests that require later authorization. The Cloud/mobile proof must create an independent private repo, deploy a small preview, continue it from a second task, and demonstrate safe retry.
