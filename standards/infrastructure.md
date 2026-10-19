# Infrastructure and cost

- Use a dedicated sandbox account/team/project and an explicitly approved region. No production, organization administration, IAM escalation, DNS, billing, destructive changes, or cross-account access without exact authorization.
- Define reproducible infrastructure as code when appropriate; choose Terraform, CDK, CloudFormation, or the target repo's established tool. Pin provider/plugin/tool versions and lockfiles. Never commit live state or variable secrets.
- Before apply, review the exact target, plan/diff, resource count, estimated recurring and one-time cost, public exposure, allowed services, rollback, and cleanup owner. Planning can read remote APIs; it is not universally offline or a permission check.
- Bound execution in provider policy: scoped roles, permissions boundaries/session constraints where available, region/service/resource restrictions, and explicit denial of escalation/destruction outside scope. Validate the real policy separately.
- Define tags/labels where supported: `project`, `environment`, `owner`, `managed-by`, and `expires-at` for temporary resources. Use non-sensitive values. Where tags are unavailable, keep the same ownership and expiry metadata in the app's deployment record.
- Set a user-approved budget/alert recipient and usage limits before billable tests. Budget alerts often notify after usage rather than prevent it; use service quotas and provider-enforced limits as well. Do not create a budget subscription or email alert without authorization.
- Track resource IDs privately, deployment ownership, expiry/cleanup date, and restore procedures. Never auto-destroy resources after an ambiguous failed apply. Read state first and reconcile with the approved plan.
