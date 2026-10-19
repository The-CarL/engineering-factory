# Offline S3 test policy preparation

`scripts/s3-policy-plan.py` renders a **PREPARE ONLY** customer-managed-policy proposal and private review manifest. It uses Python's standard library and local Git source inspection, with no AWS CLI, SDK or API calls. It neither installs IAM permissions nor creates a bucket. A filled plan, successful renderer or passing unit test is not authorization, IAM simulation, effective-permission proof, CI acceptance or live-service proof.

Use it to prepare one grouped review of the exact private S3 upload/readback scope under [bounded runs](../standards/bounded-runs.md). Read the resulting policy and manifest before requesting a grant. Preserve the existing role baseline/boundary, trust, TLS/account restrictions, IAM/delegation exclusions and core/DNS protection; their actual contents and effective intersection must be verified separately. This renderer does not copy or replace them.

## Private input

Create a mode-600 JSON file in a mode-700 private directory outside public Git. The following is a schema example with deliberately rejected placeholders; fill a private copy from the concrete run plan. Do not commit actual account/resource IDs or approval records.

```json
{
  "version": 1,
  "status": "prepare-only",
  "account_id": "FILL_EXACT_ACCOUNT",
  "role_name": "FILL_EXACT_ROLE",
  "region": "us-east-2",
  "bucket": "factory-FILL_PROJECT_AND_UNIQUE_RUN",
  "object_key": "runs/FILL_RUN/probe.json",
  "bucket_tags": {
    "factory:project-id": "FILL_STABLE_PROJECT_ALIAS",
    "factory:environment": "test",
    "factory:owner": "FILL_OWNER_ALIAS",
    "factory:managed-by": "engineering-factory",
    "factory:source-repo": "FILL_REPO_ALIAS",
    "factory:source-commit": "FILL_EXACT_APPLICATION_COMMIT",
    "factory:created-by": "FILL_ACTOR_ALIAS",
    "factory:created-at": "FILL_UTC_TIMESTAMP",
    "factory:creation-run-id": "FILL_RUN_ALIAS",
    "factory:last-run-id": "FILL_SAME_RUN_ALIAS",
    "factory:last-source-commit": "FILL_SAME_APPLICATION_COMMIT",
    "factory:provenance-version": "1",
    "factory:expires-at": "FILL_UTC_EXPIRY"
  },
  "object_tag_exception": {
    "review_reference": "FILL_PRIVATE_REVIEW_REFERENCE",
    "retained_metadata": [
      "factory:last-run-id", "factory:last-source-commit", "factory:expires-at"
    ]
  },
  "limits": {
    "buckets": 1, "objects": 1, "object_max_bytes": 1048576,
    "requests": 25, "incremental_usd": 1
  }
}
```

Only these fields are accepted. Arbitrary actions, policy fragments, overwrite/delete options and claimed authorization/CI fields are rejected. Account IDs must be exact 12-digit strings; repeated-digit and common example account placeholders are rejected. Bucket names are exact lowercase DNS-safe `factory-` names, without dots or reserved bucket suffixes. The object is one exact safe relative key; wildcard/path escapes and obvious placeholders fail. These checks do not prove absence, ownership or exclusion of existing assets.

All 13 [canonical provenance values](../standards/provenance.md#required-metadata-mapping) are required. Use non-secret aliases (`factory:source-repo` also accepts a narrow `owner/repo` value, without a URL or credential), no account IDs in tags, filled 40-hex app commits and second-precision `YYYY-MM-DDTHH:MM:SSZ` timestamps. The new resource's creation/latest run and commit must match; adoption and updates to original attribution are unsupported. Expiry must be future, after creation and within seven days of creation. Test/sandbox/preview environments are supported; production is excluded. The reviewed commercial-region list deliberately excludes `us-east-1`, where [legacy owned-bucket recreation resets ACLs](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html).

S3 objects allow [at most ten tags](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-tagging.html). The proposal keeps ten fixed original-provenance tags on the object and all 13 on the parent bucket. The three omitted object tags must be declared in the private exception and retained with their values in parent/inventory mapping. The renderer records the supplied exception reference as **unverified**, not as approval; review that exception before a grant. It never claims all 13 tags fit on the object.

## Render and review

```bash
python3 scripts/s3-policy-plan.py \
  --plan /private/operations/filled-s3-plan.json \
  --output-dir /private/operations/new-s3-policy-review
```

The output directory must be new under an existing private parent. It and both files are created with permissions 700/600; existing artifacts are never overwritten. Stdout reports preparation only, without private target values or paths. Errors withhold supplied values. Read the files privately:

- `policy.json`: compact exact policy; SHA256 covers the bytes written, without a trailing newline.
- `review.json`: actual policy digest/character and UTF-8 byte counts, input hash, renderer file hash and matching Git revision where available, separate application commit, exact targets, 13/10-tag mapping, declared limits and unresolved gates. An uncommitted renderer is marked accordingly.

The five fixed statements allow only exact-bucket `CreateBucket` and `TagResource` with all 13 fixed request tags; approved read actions on the exact bucket/object ARNs; and exact-object `PutObject`/`PutObjectTagging`. Upload requires `If-None-Match: *`, AES256 and all ten fixed object tags. Retagging can only reapply those same ten values. Region/expiry conditions apply throughout; resource-account constraints apply to the read/object operations. No action/resource wildcard, delete, ACL/policy write, general configuration mutation, IAM or role delegation is emitted. The literal asterisk in the conditional-write value is not a resource wildcard.

The compact managed policy must fit the [6,144-character limit](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html); the renderer reports characters and UTF-8 bytes and fails rather than dropping constraints to fit. The role's separate 10,240-character aggregate inline-policy limit must account for all existing inline policies; do not assume another inline statement fits. Managed-policy creation/attachment still requires its own exact admin review, quota validation and all 13 control-plane provenance tags under the factory project, linked privately to the consuming app. The renderer emits no admin permissions or policy-install command.

Before any grant or service write, resolve the manifest's human approval, metadata-exception review, active IAM/boundary, Access Analyzer/authorized simulation, pinned service model/wrapper, exact create/tag/conditional upload arguments, egress, absence/ownership and live-readback gates. [Bucket tags on creation](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html) need the real pinned client/model contract verified; a local renderer is not that check. Never test a denial by attempting to damage core assets.

Object bytes, request counts and the $1 maximum are declared execution limits, not enforced by this IAM policy. The fixed policy only permits its exact request-tag values; it does not prove that a matching existing resource is safe to retag or that other attached policies cannot grant more. The wrapper/run controls must enforce them and verify private access, ownership, encryption, tag/data hashes and cost evidence before acceptance. Expiring permission does not remove retained resources or stop storage charges; cleanup remains separately scoped. Preserve private recovery artifacts and actual gate results; do not present a rendered proposal as an end-to-end pass.
