# Architecture

The factory is a public, reusable engineering harness: instructions, standards, safe repository scripts, and credential-free validation. The intended operating model is **one permanent Codex Cloud environment rooted in this repository and many independent app repositories**.

```text
Phone -> Codex Cloud task -> factory instructions + tools
                               |
                               +-> workspaces/OWNER/APP-A -> independent GitHub repo -> app-owned CI/CD
                               +-> workspaces/OWNER/APP-B -> independent GitHub repo -> app-owned CI/CD
Private execution identity ----+    (explicitly approved provider targets)
```

The diagram is a target design, not evidence that Cloud permits every required filesystem/network/credential operation. A published environment provides the reusable setup; each task runs in an isolated VM. Cloud's prepared filesystem snapshot/repository refresh does not imply runtime workspaces survive between tasks, or that installation reruns for each task. The second-task proof therefore reclones the app by exact GitHub identity.

The factory never stores application source or credentials in its history. Apps have independent origins, branches, CI, deployment configuration, and resource ownership. Scripts place apps in ignored `workspaces/OWNER/REPO`; they never commit, push, modify visibility, reset, or update existing checkouts. Repository creation is explicit, private by default, and recoverable if cloning fails.

Trust boundaries are public source; task execution; private credential/vault injection; GitHub ownership/repository permissions; Vercel team/project; AWS role/account/region; and app CI/CD. Authentication at one boundary does not grant another. GitHub connectors do not sign in `gh`, and Vercel/AWS connectors do not populate Cloud CLI credentials.

## Ownership and execution boundaries

Phase 3 prepares GitHub, Vercel and AWS identities. AWS uses dedicated bounded factory role(s) in the existing account, with explicit protected-resource exclusions; a separate AWS account is not assumed. GitHub runtime writes exclude core repositories, and Vercel project/team scope must exclude core projects. Provisioning and ongoing work may use different identities. The [access matrix](access-matrix.md) distinguishes intended policy from controls still awaiting configuration and proof.

Every managed object belongs to one stable project/environment. A private project record maps that identity to exact provider resources, repository and deployment IDs. The [provenance standard](../standards/provenance.md) defines AWS tags, Vercel deployment metadata, creation/source/run attribution and append-only operation events. Preserve original creation history; verify child resources and native Git deployment paths explicitly. The public factory stores the schema, never the private inventory. Provenance supports ownership and recovery; provider policies enforce the boundary.

[Runtime standards](../standards/runtime.md) extend provenance to environment installers, wrappers, retained dependencies and published snapshots. Generic reviewed source belongs in Git; private targets and release evidence remain outside it. Record snapshot dependence versus empty-image bootstrap. Save, publish and fresh-instance acceptance are distinct; reconcile pending jobs and preserve the last confirmed release.

[Codex and Claude Code](agent-compatibility.md) share the factory's `AGENTS.md` through a thin Claude import. Each client still needs its own reviewed host configuration and instruction-loading proof. Independent app clones use their own instructions and conventions; the factory does not automatically become their instruction ancestor.

This is a harness, not a universal app generator. Stack choice and app scaffolding follow each task. Provider-specific provisioning stays outside the initial scripts until scopes and acceptance evidence exist.

## Verification state

Repository checks establish local/mock behavior only. Track actual environment publication/fresh-task readiness, credential transport, provider CLI/API reads, effective permissions, write/deployment proof and second-task mobile/recovery acceptance independently in private release evidence. Read-only success cannot complete the later gates. These public documents do not publish a live environment status or certify either agent CLI. AWS same-account identity preparation and permission validation are part of Phase 3; a service-specific deployment proof is separately selected and authorized. See [setup](setup.md), [credential gate](credential-checklist.md), and [mobile acceptance](mobile-workflow.md).
