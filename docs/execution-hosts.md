# Execution hosts

Choose the AI client, execution host and application hosting independently. The client loads instructions and operates tools; the execution host supplies the shell, filesystem, credentials and network policy; AWS, Vercel or another selected provider hosts the application. A client can operate an approved local or remote host when it exposes the required tools. Codex Cloud is one documented execution profile.

## Shared execution contract

- Load the selected checkout's `AGENTS.md`, applicable standards and the app's `ENGINEERING.md` through the client's verified instruction mechanism. Follow [AI client compatibility](agent-compatibility.md); preserve shared rules when switching agents.
- Provide an actual shell/tool path and record supported host capabilities. The managed provider-runtime installer requires Linux x86_64, glibc >=2.28, Git >=2.39 and Python >=3.10. Foundation lint/tests separately support macOS arm64 and Linux x86_64. Client-neutral instructions do not make the managed installer portable to every OS; use a supported execution host for it.
- From a clean approved factory checkout, run `python3 runtime/setup.py --source-revision FULL_REVIEWED_COMMIT`, using the reviewed full pin. Configure approved private paths and apply the generated activation to actual task commands. The installer prepares provider tooling, not an AI client, model subscription, permission grant or host publication.
- Supply approved credential bindings and exact targets through the host's supported secret mechanism. Verify each real CLI/API transport. A vault name or network-secret placeholder from another host is not a portable credential. Do not copy personal client authentication or broaden raw-token exposure to make a migration work.
- Use ordinary permitted network execution. Request a per-action grant only when the actual host policy requires one and exposes a supported mechanism. Do not invent a universal grant prerequisite. A domain allowlist alone does not prove socket access; a control denying execution still requires an authorized host remedy. Preserve proxy/CA trust and platform protections.
- Keep app source, decisions and safe resource evidence durable in its own repository. Configure private artifacts and IaC state through approved app-owned storage. Reconcile unfinished operations before resuming from another client or fresh filesystem.

## Host-specific setup

**Codex Cloud:** the [Codex Cloud setup section](setup.md#codex-cloud-gate-not-performed-by-foundation-setup), [credential checklist](credential-checklist.md) and [names-only binding example](../runtime/environment.example.json) describe this profile's install/start hooks, secrets and publication. Saving, publishing and fresh-task snapshot acceptance are distinct for that host. Those controls are not prerequisites for other AI clients or execution hosts.

**Other execution hosts:** map the same runtime commands, configuration names, scoped credentials, network policy and private storage to the host's documented mechanisms. A client exposing shell execution on a supported host can operate the provider tools without a Codex environment. Verify its actual capabilities; do not assume a particular AI app exposes cloud secrets, a browser, MCP, containers or unrestricted networking. The repository does not install or configure every client's native settings automatically. No publication step is required unless the selected host actually uses one.

## Record actual compatibility

For each client/host used, retain the client version, loaded instruction sources, repository and runtime revisions, actual tool/credential transport, effective targets/permissions and relevant checks. Use authorized task evidence for any claimed provider writes, application behavior and continuation. Mark untested capabilities explicitly; passing factory tests or documenting a host does not certify a live client integration. Client permissions, skills, hooks, MCP configuration and authentication need deliberate mapping and do not transfer automatically.
