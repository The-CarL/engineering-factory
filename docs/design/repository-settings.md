# Repository settings and automation

**Status: proposed / prerequisites unresolved, 2026-10-26.** This records the desired design after the [GitHub investigation](../history/github-authentication.md#repository-settings-and-protection). It does not implement a settings helper, activate protections, create an App, change a subscription or authorize an administrative credential.

## Desired outcome

Carlo supplies or manually creates a repository. The factory helps apply agreed repo defaults, adds appropriate CI and develops through PRs. Main requires the selected checks and normal PR process, rejects force pushes/deletion, and permits a deliberate human override only where the actual identity and protection mechanism can enforce that distinction.

The owner should not have to repeat every setting manually forever. A trusted setup path can be distinct from the ordinary build session without becoming a GitHub-hosted runner requirement. The execution location and effective authority must be selected and verified, not assumed.

## Requirements to resolve independently

| Requirement | Current evidence / design constraint |
|---|---|
| Feature availability | The inspected private repo returned a plan/visibility restriction for rulesets. Confirm entitlement for the actual owner/repo/feature; no plan change or public visibility change is assumed. |
| Trusted administrative setup | The effective connector omitted Administration; settings writes were not tested. Fine-grained Administration write also permits repository deletion. Keep setup scope exact and separately reviewed; do not leave its credential available to routine build code. |
| Distinct automation authority | An owner-specific bypass cannot distinguish manual Carlo from automation acting as Carlo. A repo-scoped App installation with no Administration/bypass is a candidate, not a proven adapter or selected solution. |
| Supported credential routing | The invalid-token controls failed in Cloud. Creating a different token/App does not establish that its identity reaches GitHub through the selected route. Current user-backed factory scripts need review before supporting installation tokens. |
| Concrete protection behavior | Choose rulesets or classic protection based on actual ownership, plan and actor support. Do not assume every mechanism exposes the same bypass actors. Preserve stronger existing/inherited rules. |
| Real CI | Add/run the app's meaningful workflows, observe exact successful check names and commit, then configure requirements. Basic PR/force-push/deletion protections can be considered before CI names exist. |

GitHub documents [repository settings](https://docs.github.com/en/rest/repos/repos#update-a-repository), [ruleset administration](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset), [protection behavior](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) and [App authentication modes](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app). Recheck current feature/permission details when implementing; this proposal is not a universal endpoint-permission matrix.

## Candidate division of responsibility

1. **Carlo:** creates/selects the repo and approves the desired settings and any consequential access/plan change. Until a trusted setup route exists, configures protections through owner access where available.
2. **Setup authority:** inspects existing/inherited controls, prepares a precise diff, applies approved settings to the exact repo, and reads back saved/effective configuration. Its administrative credential is unavailable to normal app execution.
3. **Development automation:** works only on approved repos through its demonstrated effective identity, with needed source/PR/CI permissions and no intended main-bypass or administrative authority.

This separation is a candidate security design. Lack of Administration alone does not prove a shared user credential cannot bypass; do not claim human-only override until the selected mechanism and effective identities are actually verified.

## Acceptance before calling this automated

Demonstrate the intended identities through the supported host path, establish entitlement, inspect existing rules, configure the reviewed profile with real check names, and read back effective settings. Verify enforcement without destructive probes against `main`; an isolated authorized branch/repo can be used where a behavior test is needed. Configuration readback and behavioral enforcement are separate evidence.

Keep exact owner/repo IDs, credential and routing diagnostics, permission exceptions and operation results in the appropriate private records. Stop on entitlement/authority/identity ambiguity; do not “fix” it by weakening rules, broadening the normal runtime PAT, switching repo visibility or granting general administrator bypass.
