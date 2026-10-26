# GitHub authentication, creation and repository protection

Recorded 2026-10-26. The authentication observations below came from Cloud diagnostic reports, principally October 23; the repository-protection inspection was subsequently reported in the same investigation. They were not rerun for this document.

## Credential selection versus effective authentication

The reported controls used the official pinned `gh`, an empty temporary `GH_CONFIG_DIR`, only the intended token input, disabled prompts/debug tracing and no CLI response caching. Proxy and CA settings were preserved. Local credential selection was compared in memory without printing the credential.

| Observation | What it establishes | What it does not establish |
|---|---|---|
| `gh` selected the supplied PAT locally. | Local input selection worked. | The managed request path delivered that PAT unchanged to GitHub. |
| A deliberately invalid token received authenticated REST `GET /user` and GraphQL `viewer` responses as Carlo. | The effective authenticated response did not follow the supplied credential control. | Which internal component supplied/changed authentication, or the precise substitution mechanism. |
| Both invalid-token and PAT responses had connector-associated OAuth client metadata and the same short expiration, inconsistent with the saved PAT expiration. | Additional evidence of a routing discrepancy associated with the connector. | Complete proof of the internal architecture or permission set. |
| Direct Python requests with an explicit PAT Authorization header also received connector-associated metadata and a creation denial. | Switching away from `gh` did not resolve the observed discrepancy. | That GitHub rejects PATs generally, or that every host behaves this way. |
| `POST /user/repos` returned 403; readback found no created repository. | The attempted creation was not confirmed; the effective route denied it. | That the saved PAT itself lacked creation permission, or that normal operations on an existing repo were unavailable. |

The control failure is stronger evidence than a successful identity read: a valid-looking identity did not prove the credential source. Neither `gh auth token` nor an explicit HTTP header can certify authentication after a managed intermediary. Connector IDs and expiry were diagnostic correlations, not a discovery of the exact injection layer.

**Decision:** stop expanding credentials or repeatedly changing clients to retry creation. Carlo supplies an existing repository or manually creates one from the agent's owner/name/visibility/description brief; the factory then verifies access and uses the normal development workflow. [PR #12](https://github.com/The-CarL/engineering-factory/pull/12) established that source contract. See [new-project guidance](../new-project.md#repository-and-instructions).

This is a factory workflow choice in response to the observed host behavior. GitHub's [repository creation API](https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user) remains a separate platform capability. Manual creation does not automatically give the connector access to the new repo.

**Still unresolved:** the responsible managed routing component and a supported way to prove an alternative credential reaches GitHub. Do not bypass managed networking or broaden a PAT as an assumed repair. Preserve detailed request evidence privately if platform support investigates.

## Repository settings and protection

A later inspection of a private personal-account repository found:

- `main` existed and branch metadata reported `protected: false`.
- Classic protection details returned 403, “Resource not accessible by integration.”
- Ruleset/effective-rule reads returned a private-repository upgrade/visibility restriction.
- No workflow, run, check or status existed yet, so no CI check name had been verified.
- The effective route identified Carlo with connector-associated authentication, including when an invalid credential was supplied. The connector's declared permissions omitted Administration.

**No settings writes or bypass tests were performed.** Failed reads did not certify the absence of all protections. Carlo's repository-admin label did not establish the connector's settings-write permission. The response exposed a feature-entitlement restriction, not the account's exact subscription plan.

Three independent requirements emerged:

1. **Feature entitlement:** the chosen protection feature must be available for the repository's visibility and owner plan. A token cannot unlock an unavailable subscription feature. See [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) and [rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
2. **Setup authority:** relevant settings endpoints require administrative permission. For fine-grained credentials, both [repository updates](https://docs.github.com/en/rest/repos/repos#update-a-repository) and [repository deletion](https://docs.github.com/en/rest/repos/repos#delete-a-repository) require Administration write. Granting it to routine automation has a larger effect than enabling branch protection.
3. **Enforcement identity:** “only Carlo's deliberate manual actions may bypass” cannot be established merely by naming Carlo when automation also acts as Carlo. Actual bypass behavior depends on the chosen protection mechanism and effective actor; it was not tested.

A GitHub App **installation** actor differs from an App user token acting on a user's behalf; [GitHub's authentication modes](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app) explain the distinction. A separate, repo-scoped installation without Administration or bypass is a possible development identity, not an implemented solution. It cannot perform administrative setup without separate authority, and its authentication still needs a supported host route. Current factory scripts expect a user-backed identity; installation-token support needs an adapter review.

**Current workaround:** after manually creating a repo, Carlo can configure protections through trusted owner access when the feature is available. This can happen after creation, rather than as a creation-time-only setting. The factory can add real CI first, then require observed check names; basic protection and CI requirements need not be conflated.

**Desired future:** Carlo creates the repo; a separately authorized setup path configures agreed standards; ordinary automation develops under enforceable limits. The [repository-settings proposal](../design/repository-settings.md) preserves this goal without claiming it is working today.

## Lessons that apply beyond this incident

- Credential presence, local selection, effective identity, repository access, endpoint permission, subscription entitlement and enforcement are separate facts.
- Omission of repository-deletion permission does not prevent content removal through ordinary commits with Contents write.
- A human-only bypass is a security property to verify, not a label to put in a prompt. Withholding Administration alone is not proof that a shared identity cannot bypass.
- A fresh repo having no CI is an onboarding task, not a reason to invent required status-check names.
- Do not recreate Cloud environments, rotate tokens or grant broader permissions as an unchanged retry strategy for this routing discrepancy.
