# Engineering factory

A conversational engineering workspace where Carlo brings an idea, brainstorms and co-designs with the agent, and the agent acts as his build manager to realize the agreed vision. Using available tools, configured environments and shared standards, the agent owns planning, implementation, verification and agreed deployment, working autonomously within authorized scope. Discussion and execution adapt to the project. The shared instructions and provider tools are agent-neutral, with entrypoints for Codex and Claude Code and an explicit onboarding contract for other AI engineering clients. The selected execution host supports independent application repositories from phone or desktop where the client provides that access. Each project chooses its architecture, runtime, providers and verification from its product needs.

Start with [conversational delivery](standards/conversational-delivery.md) and [Create or continue an application](docs/new-project.md). The agent leads design, asks consequential questions early, infers routine details, explicitly postpones decisions that can wait, and owns delivery through relevant checks and hosting. The user should not have to supply a complete specification or discover blockers through repeated status requests. The factory supplies shared rules, focused helpers and provider contracts; apps own their implementation and operating records. Use an existing app repository, or have Carlo create it manually from the agent's brief before repository-dependent implementation. Automated repository creation is outside this factory workflow.

## Execution environment setup

Choose the AI client and execution host separately under [agent compatibility](docs/agent-compatibility.md) and [execution hosts](docs/execution-hosts.md). Codex Cloud is one documented host profile. On a supported Linux host using the managed factory runtime, install the operational provider tools by default. Local lint/tests are necessary and do not replace pinned GitHub/AWS/Vercel tooling. The onboarding agent verifies the exact factory origin, clean reviewed `main` commit and instructions, then runs one credential-free entry with that reviewed full SHA:

```bash
python3 runtime/setup.py --source-revision FULL_REVIEWED_COMMIT
```

The command verifies source, prepares pinned Node/npm and provider tools from a supported Linux Git/Python base, selects a private versioned release and writes activation. It does not auto-trust HEAD, configure personal credentials, install/authenticate an AI client or publish a host snapshot. Apply the generated activation to task commands and verify startup. Report missing credential/target, actual host network access, effective grants and real write/fresh-task gates explicitly; do not classify core AWS/Vercel runtime as optional or declare readiness from repository checks. See [actual setup/start commands](docs/runtime-commands.md#cloud-base-bootstrap-and-startup).

## Available capabilities

| Capability | Helper / ownership |
|---|---|
| App repository onboarding | `plan-repo.sh` prints a manual creation brief for Carlo; `clone-repo.sh` verifies and clones an existing repository. Private by default; no automatic repository creation. |
| Shared app instructions | `seed-project.py`: only AGENTS.md, CLAUDE.md and ENGINEERING.md in a verified independent clone; preserves differing user files. |
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

## Operating references

- [Setup and local helpers](docs/setup.md), [architecture](docs/architecture.md) and [phone operation](docs/mobile-workflow.md)
- [Conversational delivery](standards/conversational-delivery.md), [application design](standards/application-design.md), [bounded work](standards/bounded-runs.md) and [provider contracts](docs/provider-workflows.md)
- [Runtime installation and provider commands](docs/runtime-commands.md), [tool pins](runtime/pins.json) and [names-only Codex Cloud binding example](runtime/environment.example.json)
- [Security model](docs/security-model.md), [provider access design](docs/access-matrix.md) and [credential gate](docs/credential-checklist.md)
- [Project ownership/provenance](standards/provenance.md), [shared agent rules](AGENTS.md) and [AI client compatibility](docs/agent-compatibility.md) and [execution hosts](docs/execution-hosts.md)

Licensed under [MIT](LICENSE).
