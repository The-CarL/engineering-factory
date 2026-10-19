# Full-stack application contract

A full-stack request requires a usable frontend connected to real server/API execution. A static page, browser-only calculation, mocked response or unrelated provider connectivity check does not satisfy that request. Select the smallest suitable architecture for the product; installing a provider credential does not create a requirement to use that provider.

## Frontend and backend

- Define the user flow and frontend/server boundary before implementation: routes, methods, request/response schemas, status/error behavior, loading/empty/error states and version compatibility.
- Validate untrusted inputs on the server, constrain work and return useful errors without stack traces or secrets. Add authentication and enforce authorization at the server boundary when the product requires them; browser checks alone are insufficient.
- Keep credentials and privileged configuration server-only. Distinguish public build-time configuration from server runtime secrets; review bundling, logging, origin/CORS and session behavior for the chosen topology.
- Framework-native server endpoints are a suitable simple option when supported. Separate backends, provider-specific services or other targets need a product reason and current runtime/region/limit verification. Do not force a beta topology or AWS service.
- Add persistence only when requirements need durable state. If used, define ownership, schema/migrations, request/restart durability, authorization and restore behavior. Otherwise verify the actual stateless computation/integration response and document that contract.

## App-owned implementation and checks

Each independent app owns source, pinned dependencies/lockfiles, install/dev/test/typecheck/build/browser commands and CI/CD. Record actual commands and architecture decisions in its `ENGINEERING.md`; instruction seeds are not implementations of those commands or workflows. Factory validation does not run or certify app CI.

Use meaningful unit/API tests for server validation and error behavior, plus a real browser → API → data/response check of the requested user flow. Exclude execution credentials from untrusted code/tests. If persistence is required, prove write/read and required durability; if auth is required, prove permitted and denied access. Local mocks may isolate dependencies but cannot replace the deployed integration gate.

## Deployment and operation

Deploy compatible frontend/backend source and configuration to the agreed targets. Record exact commits/build identities, runtime/config revisions, API base URLs or relative-route behavior, required secret names, provider identities, protection/public exposure and actual health results. Keep values, provider resource IDs and inventories private under [provenance](provenance.md).

Own app CI/CD independently of factory execution credentials. Verify CI actually ran on the intended app commit, server routes execute on the chosen host, and the deployed browser flow reaches the intended server/data path. A READY deployment, login page or local success alone is insufficient.

A net-new Vercel project needs an explicitly scoped creation/protection/first-release path; the existing preview helper only handles a verified project with a READY production baseline. AWS writes need a reviewed project-specific role/service/resource/IaC profile; current identity reads do not provide that capability. Follow [first-deployment scope](bounded-runs.md#first-deployment-scope), [deployment](deployment.md) and [provider contracts](../docs/provider-workflows.md).

Document operation and fresh-task continuation: exact independent repo/origin, applicable instructions, commands, non-secret config names, private deployment/recovery references, rollback and any data migration/restore contract. Push source or export it privately and verify restoration before relying on another task. A new actor must clone and recheck the actual app; no compulsory chat handoff or new factory environment is needed.
