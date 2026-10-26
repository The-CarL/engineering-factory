# Cleanup planning and execution

Cleanup is a separate consequential operation. Prepare a comprehensive, detailed plan and have Carlo review and approve that exact scope before executing it. Build/deployment authorization, an expiry tag, an original demo label or a prior project's purpose is not cleanup approval. Do not assume an app is disposable or impose a universal lifetime, backup choice or lifecycle questionnaire.

## Prepare the reviewable plan

Reconcile the app repository's inventory with actual provider reads, stack state, child resources, DNS and publication records. Include partially created resources, externally managed dependencies, retained resources and uncertain past operations. Record ownership evidence and distinguish shared/core assets from this app's resources; names alone are insufficient.

Give Carlo the proposed outcome, exact private targets and a dependency-ordered action list. Cover the applicable items:

- App hosting: projects, deployments, aliases, custom domains, certificates, caches, uploaded assets and provider-controlled records.
- AWS: stacks and their effective deletion/retention policies, workloads, roles/policies, databases, networking, logs, secrets, storage, queues, schedules and orphaned child resources.
- Data: what will be deleted or preserved, snapshots/backups/retained automated backups, recovery options and irreversible effects. Any change to deletion protection or retention belongs in the plan.
- DNS: only the exact app-owned records, with current-value/ownership readback. Protect core records and shared zone/delegation settings.
- Forge or other publications: whether to keep an archive or remove the listing, article, screenshots and other owned assets, including the URLs that must disappear.
- Source, evidence and continuing costs: what remains, why it remains, its retention location and any known ongoing charges. Source repository deletion requires explicit scope.

State the order, cascade effects, known provider limitations, expected asynchronous waits, verification steps and recovery/rollback limits. State whether cost figures are estimates or actual observations. Reference the plan revision and approved resource set in the private operation record. Do not expose private IDs or credentials in a public PR.

## Execute the approved scope

After Carlo approves the plan, carry out its routine steps autonomously with the reviewed identity and exact targets. Preserve the approval reference. A changed or newly discovered consequential scope needs a revised plan and approval for the change; an unchanged routine step does not need repeated confirmation.

Respect stack ownership and dependencies. Review resource-level retention and deletion protection before requesting stack deletion. Account separately for resources managed outside a stack; do not assume a stack removes them. Reconcile uncertain outcomes before retrying, and preserve shared infrastructure and unrelated publications.

## Verify and close

Confirm provider terminal states and absence of each targeted resource, including billable retained children, snapshots/backups and secrets. A deletion request accepted is not proof of deletion. Inspect DNS and production publication URLs as well as source changes. Removing a Live link does not remove an article or image; verify each requested outcome.

Record each item as removed, deliberately retained, provider-managed, blocked or unknown, with redacted readback evidence. Explain provider-controlled remnants and their known cost implications without repeatedly attempting unsupported deletion. Preserve a cleanup record in the app's appropriate durable records, including approval, executed scope, results and any follow-up; do not discard the inventory merely because infrastructure is gone.
