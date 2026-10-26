# AWS autonomy, IAM recovery and DNS

Recorded 2026-10-26. Historical live observations are reported outcomes from the October investigations; source status below was inspected for this record. No provider policy or DNS change was made while writing it.

## Application authority and core protection

The requirement was broad autonomous application work in an existing shared AWS account, across suitable services and regions, while protecting the personal site, Forge, their core DNS/supporting infrastructure and major account/security settings. Starting with no application grants or a read-only wrapper did not meet that requirement.

The resulting design uses dedicated runtime authority, a reviewed general application service grant, project IAM paths and fixed application boundaries, explicit protected-resource inventory and account/core exclusions. It does not impose one app stack or a small universal service list. See the [access matrix](../access-matrix.md), [AWS profile](../../infra/aws/README.md) and [infrastructure standard](../../standards/infrastructure.md).

Broad service access in a shared account is **not** proof of universal “new resources only” isolation. AWS resource/tag conditions and tag-on-create support differ by action; some resources are untaggable and deployment services execute indirectly. Creation provenance, current ownership, protected mutations, IAM/PassRole, CloudFormation execution and the complete effective policy require review together. Names or instructions alone do not create an IAM boundary.

## Role lookup and CloudFormation recovery

The first full app run reached a partial failed stack after database/network resources had been created. CloudFormation encountered an explicit `iam:GetRole` deny and warned about `iam:GetRolePolicy`, even though the template already specified the intended project role path and fixed application boundary.

Investigation found path-qualified role reads allowed in simulation and corresponding root-name reads denied by the runner boundary's IAM namespace. The original evaluated resource/context was unavailable. A pre-creation named-role lookup resolving without a stored path remained a **hypothesis**, not a reconstructed authorization trace. Adding an Allow alone cannot defeat an explicit Deny.

The app eventually recovered under existing authority by creating a scoped execution role directly and referencing it from the **same** stack. Failed-resource cleanup deleted that first externally supplied role during recovery; a later coordinated recreation/update succeeded and preserved the database/network. No central IAM policy was changed to obtain that reported success.

**Reusable lesson:** decide who owns a resource before switching between stack-managed and external creation. A stack failure is not permission to delete/recreate stateful infrastructure or race its cleanup. Reconcile stack events and actual role/function existence before retrying. See [deployment standards](../../standards/deployment.md).

### Prepared source correction, not proven live resolution

[PR #15](https://github.com/The-CarL/engineering-factory/pull/15) merged a paired correction:

- The runner boundary admits the exact account/current-project root-name role pattern for lookup.
- The runner identity policy explicitly denies every action except `iam:GetRole` and `iam:GetRolePolicy` on that same pattern.
- Normal project-path IAM and delegated application boundaries retain their existing contract.

The **pair** limits the exception to two reads. The boundary exception alone is not read-only. Apply the identity mutation deny first and verify it before expanding the boundary; roll back the boundary first before removing the guard. Full details and the activation contract remain in [the AWS profile](../../infra/aws/README.md#application-autonomy-and-role-lookup-compatibility).

The review reported 53 matching effective-policy simulation cases and no Access Analyzer ERROR findings; existing broad-grant warnings remained for combined-policy review. These are simulation/static evidence, not the original request trace or live application acceptance. **Activation of this correction is not established by this history.** A successful scoped absence check may return `NoSuchEntity`; it need not return a role to show the read was authorized.

AWS managed-policy size limits also constrained the patch. A smaller equivalent representation must retain the complete protection semantics; dropping an unrelated deny to fit a policy is not an acceptable shortcut.

## DNS discovery, names and hosting

A prior full-stack app worked on its Vercel hostname but could not discover its Route53 zone through `ListHostedZonesByName`. At that point no DNS write had been attempted: a discovery denial was not evidence of a write denial.

The later DNS rollout used an explicit approved public zone name/ID pair and direct zone readback instead of global discovery. [PR #13](https://github.com/The-CarL/engineering-factory/pull/13) records the source change; the subsequent handoff reported policy activation and a working custom-domain browser/API/database save-and-refresh flow. That historical result does not establish today's DNS or permission state.

The adjusted namespace permits ordinary app/service child names outside exact protected names and reserved subtrees. The domain apex, personal-site/Forge core names and supporting validation records remain protected. A protected parent may have app children only where its blanket subtree reservation was explicitly released. The live private inventory, not an example hostname in a prompt, determines actual exclusions.

NS, SOA, DS, literal wildcard records, zone/delegation and registrar administration remain outside the application grant. Application record changes use reviewed exact values and CREATE-first planning; an existing matching record is not automatic adoption or cleanup ownership. Route53 records do not carry project tags, so per-record attribution belongs in the app's approved inventory. See [application DNS](../application-dns.md) for the authoritative contract and helper limits.

**DNS does not select the hosting provider.** An approved app child can route to Vercel, an AWS frontend/API or another agreed endpoint. Vercel need not host the frontend, and Route53 can remain authoritative without moving nameservers. Backend names are selected during app design under the same protected-name contract, not assigned a special provider-specific namespace.

Propagation, Vercel ownership verification, certificate provisioning, HTTPS and browser behavior are separate checks. In the successful run a single CNAME was sufficient and transient HTTPS provisioning later completed; that does not guarantee every future domain requires exactly one record or the same wait.
