# Engineering factory

Use one reusable Codex Cloud environment to build and continue independent **frontend + real backend** projects. This public factory supplies operating instructions, standards and focused helpers; each app owns its source, stack, commands, CI/CD and deployments. It does not generate a universal sample application.

Start with [Build a new project](docs/new-project.md), including its copyable project prompt, and the [full-stack contract](standards/full-stack.md). Agree one concrete initial scope, then execute routine create/clone/develop/push/CI/deploy/verify steps without repeated prompts or a compulsory chat handoff.

## What is shipped

| Capability | Helper / ownership |
|---|---|
| Private GitHub creation and independent clone | `create-repo.sh` / `clone-repo.sh`: explicit target, inventory/origin/visibility checks and recovery; offline dry-run available. |
| Shared app instructions | `seed-project.py`: only AGENTS.md, CLAUDE.md and ENGINEERING.md in a verified independent clone; preserves differing user files. |
| Provider identity checks and GitHub source selection | `preflight.sh` and reviewed transport helpers; reads do not prove create/push/deploy permissions. |
| Vercel REST preview | `vercel-preview.py`: authorized deployment POST/poll with exact protected project, verified READY production baseline, source and provenance guards. It does not create/link a new project or perform its first release. |
| Private recovery integrity | `recovery-manifest.py`: hashes/verification for selected files; no durable export or restore is performed for you. |
| App implementation and CI/CD | Agent-owned work in the app repo: suitable frontend/server stack, meaningful commands/tests, actual app CI and reviewed provider CLI/API/IaC deployment. |

Apps live in separate ignored `workspaces/OWNER/REPO` clones with their own origins. No app source, private provider inventory, credential values or generated deployments belong in the factory. All infrastructure/Vercel work requires stable project/source/run provenance and private readback.

```bash
./scripts/install-check-tools.sh
make check
./scripts/preflight.sh --offline
```

Factory checks require no provider credentials and establish offline behavior only. Accept each environment's actual GitHub create/clone/push credential transport, Vercel CLI/API path and initial release, and any selected AWS write profile separately. Follow the [new Vercel project contract](docs/provider-workflows.md#new-vercel-project-and-initial-release) through official tools; the narrower preview helper does not automate that path. Reusable Cloud operation, app CI/deployed full-stack behavior and fresh-task continuation require real evidence recorded privately; installing credentials does not select a backend service.

## Operating references

- [Setup and local helpers](docs/setup.md), [architecture](docs/architecture.md) and [phone continuation](docs/mobile-workflow.md)
- [Bounded runs](standards/bounded-runs.md), [provider contracts](docs/provider-workflows.md) and [runtime acceptance](standards/runtime.md)
- [Security model](docs/security-model.md), [provider access design](docs/access-matrix.md) and [credential gate](docs/credential-checklist.md)
- [Project ownership/provenance](standards/provenance.md), [shared agent rules](AGENTS.md) and [Codex/Claude compatibility](docs/agent-compatibility.md)

Licensed under [MIT](LICENSE).
