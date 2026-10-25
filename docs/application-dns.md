# Application DNS

Application DNS uses one explicitly approved public Route53 zone. The private `FACTORY_AWS_DNS_ZONE_ID` and `FACTORY_AWS_DNS_ZONE_NAME` pair survives activation, `factory-aws` CLI/trusted exec and the selected app's private registry. Neither variable is a credential or an authorization grant. Verify the returned zone ID, domain and `PrivateZone=false` together; an identity read or known zone ID does not establish write access. No account-wide discovery is required.

The opt-in [AWS profile](../infra/aws/README.md#dns-semantics-and-rollback) allows ordinary child hostnames outside exact protected core/supporting names and retained reserved subtrees. Core validation labels belong in that private protected inventory too. Changing it is administrator work under separately established scope. A protected parent can have new permitted children only after its blanket subtree protection was explicitly released. NS, SOA, DS, literal wildcard records, zone and registrar administration remain excluded. Source changes do not activate policies or release any subtree by themselves.

## Read, plan, create, reconcile

Select the app/project, verify installed runtime integrity, and establish the existing authorization for its hostname, values, public exposure and cost. Use new private operation paths for every native CLI call. The examples use a private mode-700 directory under the approved `FACTORY_PRIVATE_ROOT`, never a public checkout.

```bash
factory-aws --record "$PRIVATE/zone-read.jsonl" --output "$PRIVATE/zone.json" -- \
  route53 get-hosted-zone --id "$FACTORY_AWS_DNS_ZONE_ID"
factory-aws --record "$PRIVATE/records-before.jsonl" --output "$PRIVATE/before.json" -- \
  route53 list-resource-record-sets --hosted-zone-id "$FACTORY_AWS_DNS_ZONE_ID"
```

Keep full native AWS CLI auto-pagination. Do not use `--no-paginate`, `--max-items`, `--query` or partial output for the helper's record readback. Full zone reads stay private; retain only the selected record's evidence in the app's approved records. Do not publish unrelated DNS or validation-token inventory.

Prepare a mode-600 desired simple record JSON file with `Name`, `Type`, `TTL` and `ResourceRecords`. Use exact lowercase names; no wildcards, aliases or weighted/failover/routing policies. A generic example is:

```json
{"Name":"app.core.example.test.","Type":"CNAME","TTL":300,"ResourceRecords":[{"Value":"edge.example.net."}]}
```

```bash
factory-dns plan --zone "$PRIVATE/zone.json" --records "$PRIVATE/before.json" \
  --desired "$PRIVATE/desired.json" --source-commit "$APP_SOURCE_COMMIT" --run-id "$RUN_ID" \
  --batch "$PRIVATE/create.json" --receipt "$PRIVATE/plan.json"
```

`factory-dns` makes **no provider calls**. It checks the public-zone ID/name readback and produces one CREATE only when that name/type is absent. A matching record yields `reconciled-existing` and an empty batch; it grants no adoption or cleanup ownership. A conflicting value/TTL, CNAME collision, routing/alias record or unfinished pagination stops planning. The helper supports A, AAAA, CNAME, TXT, MX, CAA and SRV with TTL 60..86400; other permitted provider shapes use reviewed native CLI plans. It does not replace IAM, live ownership checks or provider validation.

For a new, authorized record, review the exact CREATE batch, persist intent and use the native CLI:

```bash
factory-aws --record "$PRIVATE/create-op.jsonl" --output "$PRIVATE/create-result.json" -- \
  route53 change-resource-record-sets --hosted-zone-id "$FACTORY_AWS_DNS_ZONE_ID" \
  --change-batch "file://$PRIVATE/create.json"
```

Read the change ID from the private response, wait for that exact change using native `route53 wait resource-record-sets-changed`, then obtain `get-change` and a fresh complete record-set readback with new operation paths. A wait returning successfully is not a replacement for retained readback. Verify them offline:

```bash
factory-dns verify --plan "$PRIVATE/plan.json" --zone "$PRIVATE/zone.json" \
  --records "$PRIVATE/after.json" --response "$PRIVATE/create-result.json" \
  --change "$PRIVATE/change-status.json" --receipt "$PRIVATE/verified.json"
```

Verification requires the same submitted change ID to be INSYNC and the exact expected name, type, TTL and values to exist. For a matching preexisting record, omit `--response`/`--change`; the verified receipt continues to mark it external. Receipts are operational evidence derived from supplied provider readbacks, not tamperproof IAM ownership. Preserve the native operation journals and their linkage; never edit receipts to claim ownership.

If a create times out, fails or has an unknown outcome, reconcile the existing change, exact record and app inventory before another write. Do not change CREATE to UPSERT or delete/recreate to recover. Existing-record updates require proven ownership or explicit adoption, an exact before/after diff and the already authorized update scope. The native CLI remains available; the helper does not impose a read-only wrapper or service allowlist.

## Durable ownership and cleanup

In this app's approved private records, persist zone ID/name, exact record name/type/values/TTL, project/environment, source commit/run, authorization, whether created or reused, native change ID/status and before/after evidence. Keep the zone pair in the app's `.factory/` provider configuration; link detailed DNS receipts and cleanup instructions from its own inventory/engineering contract. There is no central app registry. Do not publish private zone/provider details in a public app registry.

Route53 has no project tags on individual records. IAM enforces the approved zone, core exclusions, types and naming constraints; it cannot infer which app owns an otherwise permitted record from these files. A matching record is not ownership proof. Preserve external/shared records, and do not claim that tags or an app registry prevent cross-app DNS writes.

Cleanup requires authorization and must target only positively identified run-owned records. Re-read the exact record and compare it with the last known managed values, including TTL and routing fields. If it changed or ownership is uncertain, preserve it and report the conflict. Submit an exact DELETE only for a verified owned record; wait/read back its change and confirm absence. Preserve creation/deletion history. Never delete the zone, change nameservers or remove unrelated validation/core records.

For a custom application hostname, acceptance includes authoritative/public DNS resolution, hosting-provider domain readback, valid HTTPS, the backend's allowed origin and a real browser-to-API-to-data check on that hostname. DNS INSYNC alone is not application acceptance.
