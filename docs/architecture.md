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

This is a harness, not a universal app generator. Stack choice and app scaffolding follow each task. Provider-specific provisioning stays outside the initial scripts until scopes and acceptance evidence exist.

## Verification state

The foundation adds local/mock validation. Cloud environment creation, credential mechanism compatibility, live repository creation permissions, live CLI target checks, Vercel deployment, second-task mobile continuation, and recovery proof remain **unverified**. AWS is an optional later proof. See [setup](setup.md), [credential gate](credential-checklist.md), and [mobile acceptance](mobile-workflow.md).
