# Prepare readable provenance metadata

Use the [provenance standard](../standards/provenance.md) for the canonical mapping and ownership rules. The offline helper adds six readable labels to a private provenance record and prepares provider payloads from the app's clean committed source. It performs no network requests, provider writes, IAM updates or resource adoption.

From reviewed factory source, after preparing the existing base provenance record:

```bash
python3 scripts/provenance-metadata.py \
  --input "$PRIVATE/base-provenance.json" \
  --source /canonical/app \
  --project-name "Example Notes" \
  --mode create \
  --output "$PRIVATE/prepared-provenance"
```

The input and new output directory must be under the canonical mode-700 `FACTORY_PRIVATE_ROOT`; the input is mode 600. The helper checks exact app Git root, credential-free GitHub origin against `factorySourceRepo`, clean source and HEAD against `factoryLastSourceCommit`. It reads Git's author display name, not email, and never authenticates or fetches from GitHub.

Output directory/files are mode 700/600 and are never overwritten:

| File | Use |
|---|---|
| `provenance.json` | The existing 13 fields plus all six readable fields, using the canonical Vercel/private-record names. |
| `aws-tag-map.json` | AWS tag-key/value map for reviewed service parameters accepting maps. |
| `aws-tags.json` | AWS `Key`/`Value` list for reviewed service parameters accepting lists. Both AWS formats also contain derived `factory:s`. |

Pass the appropriate file through the actual service's reviewed tag parameter or IaC resource tags and perform provider readback. These files do not automatically inject tags into every AWS call, propagate to child resources, or prove that a service accepts the shape/characters. Do not use changing run/commit fields as global default tags that update unrelated resources. Do not put private payloads into Git.

## Creation and updates

For `--mode create`, original/latest commits and run IDs must already be initialized together. Original and latest branch/author labels start from the same source facts. The project display name is supplied deliberately; the repository short name comes from `factorySourceRepo`.

For `--mode update`, pass the resource's existing provenance with its latest source commit/run already updated for the actual change. The helper preserves original commit, actor, time, run, repo name, branch and author; it refreshes only latest branch/author and the selected current project label. Known original attribution cannot be overwritten or stripped.

Legacy records without the readable extension remain valid. Enriching one locally leaves unavailable original branch/author as `unknown`, even if today's checkout has a branch/author. Do not fabricate history or infer a branch from commit membership. Establish any historical backfill separately from trustworthy evidence. This helper does not retag deployed resources or rewrite old ownership receipts/journal hashes.

A detached checkout is labeled `detached`; the exact commit is still recorded. If a verified source ref or author requires a provider-safe display alias, use `--branch-label` / `--author-label` and retain the mapping in approved private app records. Git author names are self-asserted attribution, distinct from the authenticated deploy actor in `factoryCreatedBy`.

## Safety and compatibility

Readable labels use bounded Unicode letters/numbers, spaces and common tag punctuation; emails, URLs, control characters and known credential values are rejected. Do not silently truncate or sanitize into ambiguous names. Some AWS resources have stricter character/tag limits; review them before applying. [AWS tag character guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html).

This is an additive extension to provenance version 1. Runtime Vercel, preview and continuity readers accept either the original exact 13 fields or all 19 fields; partial extensions and unknown keys are rejected. New resources use all six readable fields, while historical records retain their original bytes. Existing deployments need a separately reviewed metadata update/backfill if desired.

The four STS session keys and IAM policy requirements remain unchanged. Readable labels are for navigation and attribution; authorization still uses stable project/environment scope and existing provider boundaries. Updating this source does not install it into older runtimes automatically.
