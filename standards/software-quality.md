# Software quality

- Select the simplest stack that meets the task; record important choices and constraints in the app repository. The factory does not require a framework, language, or hosting provider.
- Keep modules cohesive and interfaces explicit. Validate inputs at trust boundaries; return actionable errors without credentials or private payloads.
- Pin runtimes, dependency versions, and lockfiles. Use repeatable install/build commands. Verify downloaded executable artifacts against reviewed hashes or signatures.
- Run formatting, lint, type checks where relevant, and the tests that exercise changed behavior. Treat newly introduced warnings and security findings as failures or document a narrow reviewed exception.
- Keep PRs focused. Describe the trigger, changed behavior, tests, operational effect, rollback, and any unresolved limitation. Obtain the repository's required checks before merge.
- For user interfaces, verify key interactions, accessibility, and supported screen sizes. For APIs, verify validation, error behavior, authentication boundaries, and contract compatibility.
- Apps own their source, CI, dependencies, instructions, and deploy configuration. Factory improvements should remain reusable without coupling app histories.
- Version generic runtime installers, wrappers and checks as reviewable source, with private target data separate; document snapshot dependence versus empty-image bootstrap and verify fresh-task integrity. Follow [runtime standards](runtime.md).
- Keep shared agent instructions single-source and entrypoints concise. Review client-specific instruction discovery/configuration and verify real loading separately; see [Codex/Claude Code compatibility](../docs/agent-compatibility.md).
