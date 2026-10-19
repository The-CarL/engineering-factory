# Mobile acceptance workflow

These are future acceptance tests after reviewed foundation, approved credentials, and published environment. No live writes are part of `make check`. Keep brief redacted evidence in the task or app record: environment version, target alias, source commit, PR/check status, deployment URL/status, observed behavior, and recovery outcome. Do not put raw tokens, account IDs, or provider diagnostics in the factory.

## First phone task

1. From the phone, start a new Codex Cloud task in the single factory-linked environment. Confirm published setup, tool versions, auth/approved targets, provider permissions and cost bounds. Connector success and a local browser session are insufficient.
2. Plan an explicitly approved independent **private** app repo; run `create-repo.sh OWNER/REPO --dry-run`, then the confirmed creation. Check the printed independent checkout/origin. Verify Cloud can access the separate clone and necessary GitHub/Vercel endpoints.
3. Follow app instructions and relevant factory standards. Build a minimal app with meaningful tests; commit only in its own repo, push a branch, and open its PR. Ensure app-owned CI is independent of factory secrets.
4. Link/configure only the approved Vercel sandbox project under deliberate authorization. In the app directory inspect its resolved project/team; stop on missing/mismatched links. Deploy an authorized preview; verify deployment status, source commit, HTTPS response, and expected app behavior.
5. Record the result and known limits. Do not promote production, add domains/DNS, change billing, or provision AWS implicitly.

## Second phone task

1. Start a separate new task using the **same** published factory environment. Do not assume previous VM workspaces survive.
2. Use the exact saved repo identity with `clone-repo.sh OWNER/REPO`; verify private-repo access, isolated origin/path and applicable app instructions.
3. Make a small visible change, run app checks, push a PR/change under the app's workflow, and verify the preview/redeployment reflects the new source commit over HTTPS.
4. Confirm both tasks worked without creating a new Cloud environment or copying secrets between repos. A browser/computer automation step is not a supported Cloud capability today; use deployment/API/HTTP checks available to the task and phone.

## Recovery proof

- Repeat create/clone for the same repo and visibility: no duplicate repo, no changed origin, no reset/pull of existing files. Check dirty local work remains intact.
- Interrupt/fail cloning after creation, then retry the exact target: remote repo is reused and partial local clones are removed. In a real test use a controlled local failure; do not revoke broad accounts or induce destructive outages.
- For deployment timeout, inspect existing project/deployment state and commit before retrying; demonstrate no duplicate project or unintended production deployment. Repository retry safety does not prove deployment retry safety.
- Record cleanup ownership and expiry of any test resources. Cleanup itself must remain within the approved deletion scope.

## Optional AWS proof

Separately approve a sandbox role/account/region and bounded IaC plan. Verify enforced policy, cost ceiling/alerts/quotas, private state, tags/expiry, a small deploy and health check, rollback/retry, and approved cleanup. DNS is a separate decision. Defer this proof if AWS is not needed for the initial GitHub/Vercel workflow.
