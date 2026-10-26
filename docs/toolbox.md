# Factory toolbox

Use these capabilities to realize Carlo's agreed app design. Choose the components the app needs; available credentials do not require using every provider. This guide describes tools and architectural defaults, not a new design ceremony.

| Service | Purpose and design guidance | Operating route |
|---|---|---|
| GitHub | Home for each app's source, infrastructure definitions, engineering record, PRs and CI/CD. Carlo supplies an existing repo or manually creates one from the agent's proposed details. | Official `gh` and Git, including `factory-gh` / `factory-git` for explicit credential selection and operation evidence. Verify visibility explicitly for a public target. Repository creation is manual. |
| Vercel | A convenient frontend hosting option with previews and custom domains. Select it when it fits the design; AWS can also host the frontend. | Official Vercel CLI or reviewed REST operations through `factory-vercel`. A connector is useful when its actual team scope supports the operation. Verify native CLI and connector credentials separately. |
| AWS | Available for any suitable component: frontend, API, database, storage, queues, workers or other infrastructure. Select services from the product's needs. | Native AWS CLI through `factory-aws`, or explicitly trusted SDK/IaC execution under the same assumed role. Broad application permissions retain the reviewed core-resource, DNS and account protections. |
| Forge | Carlo's usual public app catalog and write-up destination. Include publication when agreed. | A separate change/PR in the [Forge repository](https://github.com/The-CarL/carloperottino-forge), following its current instructions and the [publication guide](forge.md). |

Apps own CI/CD definitions and release history. Use provider-native integration or reviewed app-owned authentication; do not copy factory execution credentials into CI. Successful source publication and a passing CI run do not establish a live release.

## Visual design references

For apps with a UI, consider the documented [personal-site and Forge styles](design-references.md). Their current source owns the tokens and examples; recommend an adaptation suitable for the app. This visual reference is independent of provider selection and Forge publication.

## Resolve targets and reuse them

Keep verified repository/visibility, provider owner/team/account/region, project identity, public DNS zone pair, selected credential transport and configuration names in the app's appropriate records. Private provider IDs and secrets do not belong in public source. Restore the selected app's records on continuation; reconcile actual provider state before a mutation.

For Vercel CLI work, use the verified team ID as `VERCEL_ORG_ID` alongside `VERCEL_PROJECT_ID`. The project registry derives this organization value from its recorded factory team when a project is selected, and rejects a conflicting organization. An API or connector success does not prove the native CLI transport works. A failed mutation needs reconciliation before switching transports; never submit the same uncertain write twice.

For Route53, use the configured exact public zone name/ID and verify their pairing with a direct zone read. Global hosted-zone discovery is unnecessary when the target is known. DNS selects routing independently of application hosting; see [application DNS](application-dns.md).

For Git operations, an app starts in an independent clone. A linked worktree of that app can be used for a feature or Forge change: verify its Git root, shared storage, exact origins, visibility and checked-out branch. Shared worktree configuration and public-registry confidentiality checks still apply. A factory worktree is not an application repository.

## Tools and evidence

The [runtime commands](runtime-commands.md) document concrete entrypoints; [provider contracts](provider-workflows.md) cover their operational checks. Prefer a verified supported route for the target. Preserve the selected identity, permissions, provenance and operation records across tool choices; a different route is not a way around an access denial.

Use installed pinned tools where provided. Resolve an integration requirement before initiating marketplace onboarding or accepting new terms; an AWS PostgreSQL requirement does not authorize a different hosted database. Capability checks should establish the facts needed by the actual app work, without unrelated disposable write probes.
