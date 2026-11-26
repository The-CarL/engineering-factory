# Engineering factory

A conversational engineering workspace where Carlo brings an idea, brainstorms and co-designs with the agent, and the agent acts as his co-architect and build manager to realize the agreed vision. Using available tools, configured environments and shared standards, the agent owns planning, implementation, verification and agreed deployment, working autonomously within authorized scope. Discussion and execution adapt to the project. The shared instructions and provider tools are agent-neutral, with entrypoints for Codex and Claude Code and an explicit onboarding contract for other AI engineering clients. The selected execution host supports independent application repositories from phone or desktop where the client provides that access. Each project chooses its architecture, runtime, providers and verification from its product needs.

Start with [product co-architecture](standards/product-architecture.md), [conversational delivery](standards/conversational-delivery.md) and [Create or continue an application](docs/new-project.md). The agent leads design, asks consequential questions early, infers routine details, explicitly postpones decisions that can wait, and owns delivery through relevant checks and hosting. The user should not have to supply a complete specification or discover blockers through repeated status requests. The factory supplies shared rules, focused helpers and provider contracts; apps own their implementation and operating records. Use an existing app repository, or have Carlo create it manually from the agent's brief before repository-dependent implementation. Automated repository creation is outside this factory workflow.

## Execution environment setup

Choose the AI client and execution host separately under [agent compatibility](docs/agent-compatibility.md) and [execution hosts](docs/execution-hosts.md). Codex Cloud is one documented host profile. On a supported Linux host using the managed factory runtime, install the operational provider tools by default. Local lint/tests are necessary and do not replace pinned GitHub/AWS/Vercel tooling. The onboarding agent verifies the exact factory origin, clean reviewed `main` commit and instructions, then runs one credential-free entry with that reviewed full SHA:

```bash
python3 runtime/setup.py --source-revision FULL_REVIEWED_COMMIT
```

The command verifies source, prepares pinned Node/npm and provider tools from a supported Linux Git/Python base, selects a private versioned release and writes activation. It does not auto-trust HEAD, configure personal credentials, install/authenticate an AI client or publish a host snapshot. Apply the generated activation to task commands and verify startup. Report missing credential/target, actual host network access, effective grants and real write/fresh-task gates explicitly; do not classify core AWS/Vercel runtime as optional or declare readiness from repository checks. See [actual setup/start commands](docs/runtime-commands.md#cloud-base-bootstrap-and-startup).

## Available capabilities

See the [toolbox](docs/toolbox.md) for what GitHub, Vercel, AWS and Forge provide and how to select their tools/targets. Use [cleanup standards](standards/cleanup.md) for a detailed plan that Carlo reviews and approves before execution.

| Capability | Helper / ownership |
|---|---|
| App repository onboarding | `plan-repo.sh` prints a manual creation brief for Carlo; `clone-repo.sh` verifies and clones an existing repository. Private by default; no automatic repository creation. |
| Shared app instructions | `seed-project.py`: only AGENTS.md, CLAUDE.md and ENGINEERING.md in a verified independent clone; preserves differing user files. |
| Android APK delivery | [Shared Android guidance](standards/android.md), optional app-owned toolchain/CI references, and signing/artifact/release helpers; actual native build/device acceptance remains app-specific. |
| Readable project/source metadata | `provenance-metadata.py`: offline verified Git branch/author and project/repo labels; private canonical metadata and AWS tag payloads, preserving creation history. |
| Provider identity and credential-source checks | `preflight.sh` and reviewed transport helpers; reads do not prove write permissions. |
| Versioned execution runtime | `runtime/setup.py` / `start.py`: supported-base bootstrap, pinned provider tools and integrity manifest; `factory-aws`, `factory-gh`, `factory-git`, `factory-vercel` command paths for approved operations. |
| Vercel hosting operations | Reviewed official CLI/REST contracts for projects selecting Vercel. `vercel-preview.py` supports authorized previews with a protected exact project, verified READY production baseline, source/provenance checks and operation recovery. |
| Durable project context | `factory-project`: app-owned `.factory/` registry, safe journals/receipts and typed inventory; batched checkpoints, verified same-app restore and normal branch publication. Public apps use a minimal confidential-data-free registry. |
| Private recovery integrity | `recovery-manifest.py`: hashes/verification for selected files; durable export/restore uses the project's approved destination. |
| Application engineering and hosting | Agent-owned work: suitable components, dependencies, relevant checks, independent CI/CD and reviewed provider CLI/API/IaC operations. |

Use the capabilities relevant to the project. Agree concrete consequential scope once, reuse existing authorization and proceed through routine work without repeated prompts. Providers, a browser, a server and persistent data are selected only when needed. See [bounded project work](standards/bounded-runs.md).

Apps live in separate ignored `workspaces/OWNER/REPO` clones with their own origins. Keep app source, private provider inventory, credential values and generated deployments out of the factory. Infrastructure and hosting changes require project/source/run provenance and private readback.

```bash
./scripts/install-check-tools.sh
make check
./scripts/preflight.sh --offline
```

Factory checks establish offline behavior. Accept the environment capabilities actually claimed through authorized live evidence: relevant credential transports, repository operations, hosting operations and fresh-task continuation. App CI and workload behavior require their own evidence. Keep operator-specific targets and results private.

## TODO: GitOps deployment for factory apps

Build a reusable CI/CD feature that takes an existing, accessible app repository from its first reviewed PR to a verified deployment. The setup should work across AI clients, and releases should run in GitHub Actions after the coding session ends.

- **Set up the factory once.** Establish GitHub Actions OIDC trust in AWS, encrypted and versioned Terraform state storage with locking and per-app/environment access, and a protected onboarding service. Give the service the authority to enroll approved repositories and deployment branches, configure scoped deployment roles, and set up provider access. Preserve the existing AWS account, personal-site and Forge infrastructure, protected DNS records, and the foundation itself.
- **Automate access for each app.** Actions uses its job token for repository operations and OIDC for temporary AWS credentials. Keep persistent credentials in AWS Secrets Manager. For apps that use Vercel, enroll a provisioning credential once so the service can create projects and issue and renew project-scoped credentials. Before enrollment, verify that the provisioning identity's effective access excludes core projects, including if token issuance requires full-account scope. Keep the provisioning credential accessible only to the onboarding service. Deployment jobs can retrieve only their own approved secrets. Generate app credentials during provisioning where supported and scope runtime access separately.
- **Design the rollout with Carlo.** Choose hosting, DNS, branch-to-environment mappings and delivery phases during app design. Default to `main` for production. Add a persistent `dev` environment or selected PR previews when useful. The agent prepares one or more reviewable PRs with app code, Terraform definitions and GitHub Actions workflows. Carlo reviews and merges from his phone.
- **Deploy on merge.** After checks pass, the pipeline provisions the app's infrastructure, deploys the workload, and creates approved app DNS and certificate-validation records in the existing Route 53 zone. Verify HTTPS and the applicable end-to-end behavior. Record the deployed commit, provider resources and provenance in the app's records. Subsequent merges update the same resources. Define recovery for partial releases and keep destructive changes subject to [cleanup review](standards/cleanup.md).

Acceptance requires a first deployment and a later PR-driven update with the coding session closed, without manual per-app secret entry, IAM setup or DNS console work.

## Operating references

- [History and lessons](docs/history/README.md), [unresolved findings](docs/history/README.md#unresolved-and-deferred-work) and [design decisions](docs/design/README.md)
- [Setup and local helpers](docs/setup.md), [architecture](docs/architecture.md) and [phone operation](docs/mobile-workflow.md)
- [Product co-architecture](standards/product-architecture.md), [conversational delivery](standards/conversational-delivery.md), [application design](standards/application-design.md), [personal-site/Forge design references](docs/design-references.md), [bounded work](standards/bounded-runs.md) and [provider contracts](docs/provider-workflows.md)
- [Runtime installation and provider commands](docs/runtime-commands.md), [tool pins](runtime/pins.json) and [names-only Codex Cloud binding example](runtime/environment.example.json)
- [Security model](docs/security-model.md), [provider access design](docs/access-matrix.md) and [credential gate](docs/credential-checklist.md)
- [Project ownership/provenance](standards/provenance.md), [shared agent rules](AGENTS.md) and [AI client compatibility](docs/agent-compatibility.md) and [execution hosts](docs/execution-hosts.md)

Licensed under [MIT](LICENSE).
