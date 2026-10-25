# General AWS application permission profile

`render.py` prepares a general cross-service application provisioner profile for one shared commercial AWS account, across regions. It makes no AWS requests or changes. An independently authorized administrator validates and installs the profile; application tasks then use `factory-aws` for normal CLI operations or `factory-aws --exec` for trusted SDK/IaC tools under the same bounded role. Selecting another application service does not require extending a short service allowlist.

## Private preparation

Retain the original runner DNS policy, permissions boundary, bootstrap policy and role trust as decoded JSON documents with hashes. They are rollback inputs, not public source. Rerender from these originals rather than an already modified profile. Private configuration requires `account_id`, `runner_role`, `bootstrap_user`, `app_boundary_name`, `app_policy_name`, `protected_resource_arns`, `runner_managed_policy_count` and `runner_managed_policy_limit`. Policy names start with `EngineeringFactory` and differ. Counts come from actual IAM inventory and quota readback; do not assume a default quota. Protected resources are exact commercial-account ARNs, without user wildcards; IAM and DNS use their dedicated envelopes. The renderer also protects bucket children and Lambda versions/aliases when their parent is supplied.

```bash
python3 infra/aws/render.py \
  --config "$PRIVATE/config.json" \
  --baseline "$PRIVATE/original-dns-policy.json" \
  --boundary "$PRIVATE/original-boundary.json" \
  --bootstrap "$PRIVATE/original-bootstrap-policy.json" \
  --trust "$PRIVATE/original-runner-trust.json" \
  --output "$PRIVATE/proposed"
```

Use a mode-700 private parent directory. Output must not exist; rendering validates inputs and policy sizes before creating mode-700 output with mode-600 files. The review manifest records source/input hashes, actual policy sizes/digests, observed attachment quota and unresolved activation gates. No output grants authority.

## Permission model

The broad application grant excludes Route53 and domain administration, which have a separate restrictive grant. Explicit denies retain the original account, organization, billing and identity-administration families, TLS protection and known protected ARNs. Runner and bootstrap provisioning expiry remains; deployed role boundaries have no inherited factory-token expiry. App lifetime and revocation follow the project's lifecycle contract.

Project sessions carry canonical `factory:managed-by`, `factory:project-id`, `factory:environment`, plus derived AWS security tag `factory:s=<project UUID>-<environment>`. Canonical provenance remains the existing 13 fields; scope is an additional security discriminator; its compact internal key `factory:s` keeps the self-contained IAM boundary within AWS policy limits. Bootstrap/trust allow exactly these four session keys, require scope equality, and reject wildcard/path metacharacters and consecutive hyphens or the reserved environment component `r`. The session-name restriction stays on `sts:AssumeRole`; it is not copied to `sts:TagSession`, which lacks that [action-specific condition key](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sts.html). Both authorizations retain expiry/TLS and exact identity/target constraints. Runtime validation uses a canonical nonzero UUID and a safe environment. Resource names used by the known execution guards begin `factory-<scope>-r-`; the reserved `r` component separates environments such as `dev` and `dev-prod`. IAM roles, instance profiles and app-managed policies live under `/factory/<scope>/`.

Both runner and deployed boundaries contain their own IAM envelope: IAM outside those three typed paths is denied, every created role must carry the exact fixed application boundary, replacing it with another boundary or removing it is denied, and STS elevation/session flows are denied. The fixed central policies and runner/bootstrap/admin identities are outside the permitted paths. App/provisioner policies and role trust can vary within that envelope; arbitrary identity policies cannot exceed the fixed boundary. Before activation, inventory every existing `/factory/` role and verify the fixed boundary. An existing unbounded role in a permitted path would invalidate the `PassRole` invariant; a path alone is insufficient proof.

Deployed boundaries bind scope to the immutable role PrincipalArn and explicitly deny missing/mismatched canonical scope and unsafe scope values. IAM variable defaults make the negative comparison fail closed when canonical tags are absent. Changing session tags to another project/environment cannot change the role's path. Default role creation requires all 13 provenance request tags and the derived scope. The broad default `app-execution-policy.json` is a **provisioner** grant: do not attach it automatically to workload runtime roles. Give Lambda/ECS/other app roles their workload's minimal policies within the common boundary. Incoming trust should admit only the necessary service or reviewed provisioner; no general account/user trust.

Known execution reuse is bounded independently of `PassRole`: CloudFormation stack/change-set mutations, Lambda function mutations/invocations, ECS resources, CodeBuild builds, Step Functions and SSM documents/automation use project namespaces. ECS scheduling also requires the project cluster; Auto Scaling launch templates must select an explicit numbered version (immutable launch configurations remain available); Lambda event-source mappings require a project function. SSM interactive/command targets and Service Catalog products require matching `factory:s` tags, supplied and read back during creation. Existing core/privileged resources from the private inventory are explicitly denied (an exact ARN already covered by a global service Deny is not duplicated), including updates, reads, data access and deletion.

Some APIs cannot establish target ownership with documented authorization keys. State Manager associations, maintenance-window task registration/updates, Service Catalog unscoped constraint/provisioned-product reuse, and organization-wide deployment administration remain explicit control-plane restrictions. Auto Scaling `StartInstanceRefresh` cannot enforce the numbered-version condition and remains administrator-only; use a reviewed update/rolling strategy instead. Resource-less ECS task-definition deregistration is also blocked by its namespace guard; plan cleanup accordingly. Service-linked roles cannot carry this boundary: an administrator must prepare any missing service-linked role, rather than grant runtime unrestricted IAM creation. Existing service-linked roles are an activation inventory item.

## DNS semantics and rollback

`runner-dns-baseline.json` is the exact retained original, for rollback. `runner-dns-policy.json` is the proposed replacement, **not** the original policy plus another Allow. Keeping the original CREATE-only/outside-namespace Denies active would block the new contract.

Without a `dns` configuration, the renderer retains the previous factory-prefixed name contract and original subtree protections. Upgrading source alone does not release any reserved subtree. The opt-in application contract supports human-readable application names in the same exact approved public zone:

```json
{
  "dns": {
    "mode": "application-records-v1",
    "zone_id": "ZAPPROVEDZONE",
    "zone_name": "example.test",
    "protected_record_names": [
      "example.test", "core.example.test", "www.example.test",
      "_acme-challenge.example.test", "_acme-challenge.core.example.test"
    ],
    "release_protected_subtrees": ["*.core.example.test"]
  }
}
```

This is an addition to the private configuration above, not a complete config. The target must match the retained original zone/domain. Inventory actual core records and supporting certificate/domain-verification labels before activation. All original exact protected names must remain. Each released wildcard must be an original protected subtree whose parent remains exactly protected; omission retains that subtree. Add supporting names explicitly; the renderer cannot discover future hashed validation labels. Keep that inventory current when core DNS changes. The original inputs and `runner-dns-baseline.json` remain immutable rollback evidence.

The opt-in grant permits CREATE/UPSERT/DELETE for children of the approved zone outside that protected inventory. It never grants apex changes, other zones, NS/SOA/DS mutations, literal wildcard records, hosted-zone administration or registrar operations. Other provider-valid record types remain available. An all-values name/type check rejects an entire mixed batch containing a protected/out-of-zone name or a prohibited type. Missing name/type context fails closed. Exact parent protection does not reserve every child; a new application child can be permitted while its core parent stays protected. Route53 normalizes wildcard `*` as literal `\052`; the policy rejects that escape anywhere in a requested record name.

The inline DNS policy retains an explicit core-name Deny. To fit AWS's 6,144-character managed-policy limit without dropping any non-DNS guard, runner and delegated boundaries express equivalent core exclusion inside their **sole DNS Allow**, using `ForAllValues:StringNotLike`. Their broad `NotAction` grant excludes all Route53/domain actions. Therefore an additional identity Allow cannot reopen a protected name through either boundary. Positive child-zone matching already excludes apex; exact protected names covered by retained subtree patterns are deduplicated only in this boundary condition. The complete inventory remains in configuration and the inline denial. Review this complete identity/boundary combination, not an isolated Allow. The renderer fails before output when any document exceeds quota; added protected names may require a reviewed representation change.

Set private `FACTORY_AWS_DNS_ZONE_ID` and `FACTORY_AWS_DNS_ZONE_NAME` together in the reusable environment and retain them in the selected app's registry. Verify their public-zone pairing using `GetHostedZone`; do not require account-wide hosted-zone discovery. See [application DNS operations](../../docs/application-dns.md) for CREATE-first tooling, readback, ownership and cleanup. Route53 records do not support per-record project tag enforcement. Permitted application records share a DNS write envelope: project ownership remains an operational inventory check, not an IAM guarantee. No core record is mutated to test a denial.

## What the profile cannot guarantee

A shared-account broad service grant is not universal new-resources-only ABAC. AWS varies in resource/tag/condition support; services not covered by known execution guards may permit operations on preexisting resources absent from the protected inventory. The private discovery coverage, residual exposure and access exception must be reviewed before activation and kept current. Tags/names and task instructions are provenance/operating controls where IAM does not enforce them. Do not claim all 13 creation tags or their immutability are universally IAM-enforced across services. Preserve original provenance in the private append-only inventory and verify resource ownership before each mutation.

## Administrator activation and acceptance

1. Compare the current policies/trust with retained originals; inspect protected/privileged resource inventory, service-linked roles, existing Auto Scaling groups/launch templates, factory-path role boundaries and discovery coverage. Protect sensitive data and indirect execution, not just deletions. Confirm actual managed-policy attachment and version quotas.
2. Validate all documents with Access Analyzer (`IDENTITY_POLICY`; trust uses `RESOURCE_POLICY` / `AWS::IAM::AssumeRolePolicyDocument`). Simulate complete identity + boundary combinations for runner, bootstrap and delegated roles. Cover normal cross-service creation/IaC, wrong/missing boundary, central-policy edits, core/other-project resources, stored-role CloudFormation, wrong ECS cluster, scope overrides/missing tags, expiry/TLS, and the selected DNS contract: permitted application CREATE/UPSERT/DELETE/validation children versus exact core/supporting names, retained subtrees, other zones, NS/SOA/DS, wildcards and mixed batches.
   Broad `NotAction` grants can produce PassRole/service-linked-role analyzer warnings. Review the complete explicit IAM path Deny and fixed boundary together: a grant alone is unsafe; reserved service-linked-role paths are outside the envelope. Retain warning findings and the effective-policy rationale rather than claiming zero findings.
3. Confirm actual service context and STS scope equality/override behavior. Simulator limitations for literal IAM `${*}`, `${?}` and `${$}` must remain explicit; do not label substitute tests as exact-policy proof. [IAM defaults and negative comparisons](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html) explain the fail-closed scope guard. `sts:*` denies session elevation; [GetCallerIdentity still requires no permission even under explicit denial](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html).
4. Review the exact policy diff and activation order. Install the fixed app boundary/provisioner policy and **one** runner identity managed policy (`runner-app-1.json`), replace the runner boundary and DNS inline policy, then update bootstrap/trust. Boundary changes apply before grants. Keep current versions and original attachments for rollback; never expose a temporary allow-only configuration. Apply full factory provenance to these control-plane artifacts too.
5. Read back/hash-check all documents, default versions, boundaries, attachment counts and trust. Validate actual role assumption and selected allowed operations only on authorized new resources; retain the app's private recovery/source evidence. Source tests and policy simulation do not establish live rights or deployment readiness. Access Analyzer and simulation can accept resource forms rejected by the live IAM policy parser: require actual policy materialization/readback before claiming activation, then perform the STS/service-context checks. Resource ARN vendors must be literal service names; region/resource wildcards remain deliberate.

Managed documents must each fit 6,144 characters and the bootstrap user's complete inline aggregate must fit its 2,048-character quota. The renderer refuses excess policy size or lack of one attachment slot; it never drops guards to fit. Adding protected ARNs may require a reviewed design change if the boundary reaches its limit. Rollback restores the original boundary, DNS inline policy, bootstrap/trust and previous attachments; preserve app data and evidence.

Review against the current [service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/service-reference.html), [IAM boundary evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html), [CloudFormation stored service-role behavior](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html), [Systems Manager target semantics](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_CreateAssociation.html), and [IAM quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html).
