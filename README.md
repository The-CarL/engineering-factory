# Engineering factory

A public engineering harness for one reusable Codex Cloud environment and many independent repositories, operated from a phone. It provides instructions, standards, safe repository workflows, and credential-free CI. Apps own their source and deployments; the factory is not a universal app generator.

## Start here

- [Architecture and current verification state](docs/architecture.md)
- [Local setup and repository scripts](docs/setup.md)
- [Security model](docs/security-model.md) and [provider access design](docs/access-matrix.md)
- [Mandatory project ownership and provenance](standards/provenance.md)
- [Credential and Cloud readiness gate](docs/credential-checklist.md)
- [Phone-only acceptance tests](docs/mobile-workflow.md)
- [Agent instructions](AGENTS.md) and [engineering standards](standards/software-quality.md)

```bash
./scripts/install-check-tools.sh
make check
./scripts/preflight.sh --offline
```

Validation needs no GitHub, Vercel, or AWS credentials. Tool downloads use official releases and pinned SHA256 hashes. See setup for supported platforms and prerequisites.

Repository creation defaults to private and requires an explicit owner/repo confirmation. Clones live in ignored `workspaces/OWNER/REPO`, with origin/visibility checks and safe retry. `--dry-run` is an offline plan with no provider calls or writes.

The foundation does not create credentials, Cloud environments, infrastructure, or deployments. **Cloud, live provider permissions, and the two-task phone workflow remain unverified** until their acceptance gates pass. Phase 3 prepares GitHub, Vercel and same-account bounded AWS identities. All infrastructure and Vercel work requires stable project identity, source/run metadata and private inventory. Public code contains configuration names only; private identities and provider-enforced boundaries belong outside Git.

Licensed under [MIT](LICENSE).
