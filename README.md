# Engineering factory

A conversational engineering workspace for going from an idea through collaborative design and a prototype to a tested, working solution and agreed deployment, using voice or text from a phone or desktop. One reusable Codex Cloud environment supports independent application repositories. Each project chooses its architecture, runtime, providers and verification from its product needs.

Start with [conversational delivery](standards/conversational-delivery.md) and [Create or continue an application](docs/new-project.md). The agent leads design, asks consequential questions early, infers routine details, explicitly postpones decisions that can wait, and owns delivery through relevant checks and hosting. The user should not have to supply a complete specification or discover blockers through repeated status requests. The factory supplies shared rules, focused helpers and provider contracts; apps own their implementation and operating records.

## Available capabilities

| Capability | Helper / ownership |
|---|---|
| GitHub repository creation and clone | `create-repo.sh` / `clone-repo.sh`: explicit target, inventory/origin/visibility checks and recovery; private by default, offline dry-run available. |
| Shared app instructions | `seed-project.py`: only AGENTS.md, CLAUDE.md and ENGINEERING.md in a verified independent clone; preserves differing user files. |
| Provider identity and credential-source checks | `preflight.sh` and reviewed transport helpers; reads do not prove write permissions. |
| Versioned execution runtime | `runtime/install.py` / `start.py`: Linux prepared-host tool pins and integrity manifest; `factory-aws`, `factory-gh`, `factory-git`, `factory-vercel` command paths for approved operations. |
| Vercel hosting operations | Reviewed official CLI/REST contracts for projects selecting Vercel. `vercel-preview.py` supports authorized previews with a protected exact project, verified READY production baseline, source/provenance checks and operation recovery. |
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
- [Runtime installation and provider commands](docs/runtime-commands.md), [tool pins](runtime/pins.json) and [names-only environment design](runtime/environment.example.json)
- [Security model](docs/security-model.md), [provider access design](docs/access-matrix.md) and [credential gate](docs/credential-checklist.md)
- [Project ownership/provenance](standards/provenance.md), [shared agent rules](AGENTS.md) and [Codex/Claude compatibility](docs/agent-compatibility.md)

Licensed under [MIT](LICENSE).
