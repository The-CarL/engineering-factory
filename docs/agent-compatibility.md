# Codex and Claude Code compatibility

Use [AGENTS.md](../AGENTS.md) as this repository's shared operating instructions. [CLAUDE.md](../CLAUDE.md) imports it with `@AGENTS.md`; keep Claude-specific text minimal. Detailed standards remain separate documents, read when applicable. Aim to keep each instruction entrypoint under 200 lines and avoid duplicate rules.

## Instruction discovery

Checked against official documentation on **2026-10-19**:

- Codex builds its instruction chain at session startup. Global `AGENTS.override.md` takes precedence over global `AGENTS.md`; project discovery runs from root to working directory, choosing at most one override, `AGENTS.md` or configured fallback per directory. Closer guidance takes precedence; the default combined limit is 32 KiB. A Markdown link does not automatically import its target. See [OpenAI instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
- Claude `@path` imports resolve relative to the containing file, with up to four hops. Avoid cycles and imports outside the repository. Native `AGENTS.md` fallback requires Claude Code 2.1.277+ and no relevant project/ancestor `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md`; user and managed instructions do not suppress it. Availability can vary by version/provider; the bridge avoids relying on fallback. The root bridge therefore does not automatically load nested `AGENTS.md` rules. Add a matching nested Claude bridge when needed, or verify current Project instructions settings; confirm loaded Memory files with `/context`. See [Claude memory and imports](https://code.claude.com/docs/en/memory).

When instructions change, start a fresh session and verify the intended sources in the selected client and directory. Resolve conflicting local/global guidance before consequential work. User authorization and host safety constraints still apply; imported documents cannot expand task scope. Instruction files provide context, not enforced IAM or sandbox boundaries.

## Working in an independent app

Start either agent in the exact app checkout and working directory. Confirm its Git origin, branch, commit and dirty files, then read that app's applicable instructions and standards. Factory instructions are not automatically inherited across separate clones. Preserve the app's conventions; explicitly carry only relevant factory requirements into its approved workflow. Check any ancestor instructions exposed by the chosen filesystem layout and client.

Before switching agents, prepare a compact handoff containing the repository identity, working directory, branch/commit, changed files and preserved user work, tests/results, approved scope, unresolved questions, and private references to pending operations. Reconcile those operations before retrying. Do not include credentials, raw auth responses or private provider details in public handoffs. A receiving agent must recheck identity/targets before external actions.

## Configuration and acceptance

Reviewed shared project settings may live in `.claude/settings.json`; personal changes belong in ignored `.claude/settings.local.json` or `CLAUDE.local.md`. Personal `~/.claude` auth/config and Codex personal configuration are not portable Cloud state. See [Claude settings scopes](https://code.claude.com/docs/en/settings). Do not blanket-ignore shared `.claude` or `.codex` configuration.

Review each client's permission, sandbox, MCP, hook, skill and authentication configuration on the actual host; schemas and authorization do not transfer automatically. Keep shared defaults repository-scoped. Do not change personal/global configuration or enable approval/sandbox bypass defaults merely to align tools; expressly authorized host/auth setup remains a separate gate. Keep tool/model choices task-specific.

This bridge establishes documentation compatibility. Installing either CLI, authenticating it, changing a live environment and running billable agent smoke tests are separate explicit gates. When authorized, verify real instruction loading, relevant nested rules and normal checks in a fresh session for each pinned client/host. Follow [runtime acceptance](../standards/runtime.md); documentation alone proves none of those runtime capabilities.
