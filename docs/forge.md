# Forge publication

Forge is Carlo's public project catalog and write-up site at [forge.carloperottino.com](https://forge.carloperottino.com/), maintained in the public [The-CarL/carloperottino-forge repository](https://github.com/The-CarL/carloperottino-forge). Consider it the usual publication destination when discussing delivery. Publication requires its agreed scope; it is not automatic for every app. The app repository remains authoritative for application source, infrastructure and operating records.

For app UI inspiration, use the [personal-site and Forge visual references](design-references.md). Forge's documented styles can inform an app without making publication or its hosting architecture mandatory.

## Work with the current site

Read Forge's current repository instructions, content schema, scripts and applicable publication skills before preparing a change. As inspected on 2026-10-26, entries are Markdown in `src/content/projects/`; app-specific assets conventionally live in `public/projects/SLUG/`. The `.agents/skills/new-project/SKILL.md` and `.claude/skills/new-project/SKILL.md` entrypoints describe a worktree-based draft scaffold. These are repository references, not authority to expand a factory task or publish without scope. Recheck current conventions rather than copying an old schema indefinitely.

Prepare a separate Forge branch/worktree from its independent clone, verify exact public visibility/origin, and follow its own dependency/build/CI process. The factory's Git paths support linked worktrees after checkout and target verification. Do not place an app's implementation in Forge or point its origin at the factory.

## Publish the agreed result

Collect the appropriate title, short description, date, tags/categories, write-up, screenshots and live/source links. The inspected schema supports `title`, `tagline`, `date`, optional `thumbnail`/`heroImage`, `draft`, and optional `links.live`, `links.github`, `links.blog`; read the current schema for full validation. Private source links, inventories, credentials and diagnostics need confidentiality review before inclusion in public content.

Keep draft status and claims accurate while the app is incomplete. Prepare a focused PR, run the site's checks and follow applicable merge/publication authorization. Verify the deployed listing, article, assets and outbound app links after release; a merged source change alone does not prove publication. Keep unrelated site content, hosting, core DNS and settings unchanged.

Record the Forge repository, entry/asset paths, PR/source references and production URLs with the app's durable records. Include the publication in future cleanup planning; this mapping is not a central app-state registry.

## Archive or remove

Follow [cleanup standards](../standards/cleanup.md): Carlo reviews and approves the detailed plan before cleanup. Explicitly distinguish retaining an archived article/card from removing the public presence. Retiring an app or dropping `links.live` can leave both article and images publicly available.

For approved removal, identify the exact owned entry and assets, check shared references, remove only that scope through the Forge workflow, and verify the production homepage, article URL and each asset URL. Preserve other projects and the app's source unless their removal is separately included. Record any caching/propagation delay and final observed result.
