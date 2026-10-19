#!/usr/bin/env python3
"""Prepare an exact S3 test policy offline. Never grants or applies permissions."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

TAG_KEYS = ("project-id", "environment", "owner", "managed-by", "source-repo", "source-commit",
            "created-by", "created-at", "creation-run-id", "last-run-id", "last-source-commit",
            "provenance-version", "expires-at")
TAGS = tuple("factory:" + name for name in TAG_KEYS)
OMITTED_OBJECT_TAGS = ("factory:last-run-id", "factory:last-source-commit", "factory:expires-at")
OBJECT_TAGS = tuple(key for key in TAGS if key not in OMITTED_OBJECT_TAGS)
# Reviewed commercial CreateBucket LocationConstraint values. Deliberately omit
# us-east-1: re-creating an owned bucket there has legacy ACL-reset behavior.
REGIONS = set("af-south-1 ap-east-1 ap-east-2 ap-northeast-1 ap-northeast-2 ap-northeast-3 "
              "ap-south-1 ap-south-2 ap-southeast-1 ap-southeast-2 ap-southeast-3 ap-southeast-4 "
              "ap-southeast-5 ap-southeast-6 ap-southeast-7 ca-central-1 ca-west-1 eu-central-1 "
              "eu-central-2 eu-north-1 eu-south-1 eu-south-2 eu-west-1 eu-west-2 eu-west-3 "
              "il-central-1 me-central-1 me-south-1 mx-central-1 sa-east-1 us-east-2 us-west-1 us-west-2".split())
READ_ACTIONS = ["s3:GetBucketLocation", "s3:GetBucketTagging", "s3:GetBucketPublicAccessBlock",
                "s3:GetBucketOwnershipControls", "s3:GetEncryptionConfiguration", "s3:GetBucketVersioning",
                "s3:ListBucket", "s3:GetObject", "s3:GetObjectTagging"]
MAX_POLICY_CHARS = 6144


class PlanError(Exception):
    """Only fixed, value-free diagnostics are placed in this exception."""


def require(condition, message):
    if not condition:
        raise PlanError(message)


def exact_keys(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), "Missing or forbidden plan fields")


def filled(value):
    return isinstance(value, str) and not re.search(
        r"(?i)(?:^|[-_./])fill(?:[-_./]|$)|todo|tbd|change.?me|replace.?me|placeholder|unfilled|required|unset|example|dummy|bucket[-_]name|object[-_]key|account[-_]id|role[-_]name", value)


def alias(value):
    return (filled(value) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value)
            and not re.search(r"(?i)ghp_|github_pat_|AKIA|ASIA|bearer|token|secret|password", value)
            and not re.fullmatch(r"\d{12}", value))


def repository_alias(value):
    if alias(value):
        return True
    parts = value.split("/") if isinstance(value, str) else []
    return len(parts) == 2 and len(parts[0]) <= 39 and all(alias(part) for part in parts)


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value),
            "Timestamps must be filled UTC values with second precision")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise PlanError("Invalid UTC timestamp value") from None


def validate(plan, now):
    exact_keys(plan, {"version", "status", "account_id", "role_name", "region", "bucket", "object_key",
                      "bucket_tags", "object_tag_exception", "limits"})
    require(type(plan["version"]) is int and plan["version"] == 1 and plan["status"] == "prepare-only",
            "Only version 1 prepare-only plans are supported")
    require(isinstance(plan["account_id"], str) and re.fullmatch(r"[0-9]{12}", plan["account_id"])
            and len(set(plan["account_id"])) > 1 and plan["account_id"] not in ("123456789012", "111122223333"),
            "An exact non-placeholder 12-digit account is required")
    require(alias(plan["role_name"]) and len(plan["role_name"]) <= 64, "An exact non-placeholder role name is required")
    require(isinstance(plan["region"], str) and plan["region"] in REGIONS, "Region must be a reviewed commercial region other than us-east-1")
    bucket = plan["bucket"]
    require(filled(bucket) and re.fullmatch(r"factory-[a-z0-9][a-z0-9-]{0,54}[a-z0-9]", bucket)
            and 3 <= len(bucket) <= 63 and not bucket.endswith(("-s3alias", "--ol-s3", "--x-s3", "--table-s3")),
            "An exact factory-prefixed DNS-safe bucket name is required")
    key = plan["object_key"]
    require(filled(key) and 1 <= len(key) <= 256 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", key)
            and all(part not in ("", ".", "..") for part in key.split("/")), "An exact non-wildcard object key is required")
    tags = plan["bucket_tags"]
    exact_keys(tags, TAGS)
    for name in TAGS:
        if name in ("factory:source-commit", "factory:last-source-commit"):
            require(isinstance(tags[name], str) and re.fullmatch(r"[a-f0-9]{40}", tags[name]) and tags[name] != "0" * 40, "Exact source commits must be filled non-null 40-hex values")
        elif name not in ("factory:created-at", "factory:expires-at"):
            valid = repository_alias(tags[name]) if name == "factory:source-repo" else alias(tags[name])
            require(valid and plan["account_id"] not in tags[name], "Tag values must be filled non-secret aliases without account IDs")
    require(tags["factory:environment"] in ("test", "sandbox", "preview")
            and tags["factory:managed-by"] == "engineering-factory" and tags["factory:provenance-version"] == "1",
            "Invalid test provenance mapping")
    require(tags["factory:creation-run-id"] == tags["factory:last-run-id"]
            and tags["factory:source-commit"] == tags["factory:last-source-commit"],
            "New resource creation/latest attribution must match; updates/adoption are unsupported")
    created, expires = timestamp(tags["factory:created-at"]), timestamp(tags["factory:expires-at"])
    require(created <= now + timedelta(minutes=5) and created < expires and expires > now
            and expires - created <= timedelta(days=7), "Expiry must be future, bounded to seven days, and consistent with creation")
    exception = plan["object_tag_exception"]
    exact_keys(exception, {"review_reference", "retained_metadata"})
    require(alias(exception["review_reference"]) and isinstance(exception["retained_metadata"], list)
            and len(exception["retained_metadata"]) == 3 and all(isinstance(item, str) for item in exception["retained_metadata"])
            and set(exception["retained_metadata"]) == set(OMITTED_OBJECT_TAGS),
            "Declare the private ten-object-tag exception and all three parent/inventory metadata fields")
    limits = plan["limits"]
    exact_keys(limits, {"buckets", "objects", "object_max_bytes", "requests", "incremental_usd"})
    require(type(limits["buckets"]) is int and limits["buckets"] == 1
            and type(limits["objects"]) is int and limits["objects"] == 1
            and type(limits["object_max_bytes"]) is int and 1 <= limits["object_max_bytes"] <= 1048576
            and type(limits["requests"]) is int and 1 <= limits["requests"] <= 25
            and type(limits["incremental_usd"]) in (int, float) and math.isfinite(limits["incremental_usd"])
            and 0 < limits["incremental_usd"] <= 1, "Test limits exceed the one-bucket/one-object/1-MiB/25-request/$1 preparation scope")


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def render(plan, now):
    validate(plan, now)
    bucket = "arn:aws:s3:::" + plan["bucket"]
    obj = bucket + "/" + plan["object_key"]
    tags = plan["bucket_tags"]
    object_tags = {key: tags[key] for key in OBJECT_TAGS}
    expiry = {"aws:CurrentTime": tags["factory:expires-at"]}
    region = {"aws:RequestedRegion": plan["region"]}
    owned = dict(region, **{"s3:ResourceAccount": plan["account_id"]})
    def statement(sid, actions, resources, equals, keys=None):
        condition = {"DateLessThan": dict(expiry), "StringEquals": equals}
        if keys:
            name, values = keys
            condition["ForAllValues:StringEquals"] = {name: list(values)}
        return {"Sid": sid, "Effect": "Allow", "Action": actions, "Resource": resources, "Condition": condition}
    bucket_values = {"aws:RequestTag/" + key: tags[key] for key in TAGS}
    object_values = {"s3:RequestObjectTag/" + key: object_tags[key] for key in OBJECT_TAGS}
    policy = {"Version": "2012-10-17", "Statement": [
        statement("CreateTaggedBucket", "s3:CreateBucket", bucket,
                  dict(region, **{"s3:LocationConstraint": plan["region"]}, **bucket_values), ("aws:TagKeys", TAGS)),
        statement("TagBucket", "s3:TagResource", bucket,
                  dict(region, **bucket_values), ("aws:TagKeys", TAGS)),
        statement("ReadResources", list(READ_ACTIONS), [bucket, obj], dict(owned)),
        statement("CreateProbeOnce", "s3:PutObject", obj,
                  dict(owned, **{"s3:if-none-match": "*", "s3:x-amz-server-side-encryption": "AES256"}, **object_values),
                  ("s3:RequestObjectTagKeys", OBJECT_TAGS)),
        statement("TagProbe", "s3:PutObjectTagging", obj,
                  dict(owned, **object_values), ("s3:RequestObjectTagKeys", OBJECT_TAGS))]}
    raw = compact(policy)
    require(len(raw.decode("utf-8")) <= MAX_POLICY_CHARS, "Rendered managed policy exceeds 6144 characters; do not broaden or drop constraints to fit")
    return policy, raw, object_tags


def source_reference():
    path = Path(__file__).resolve()
    content = path.read_bytes()
    source = {"path": "scripts/s3-policy-plan.py", "sha256": hashlib.sha256(content).hexdigest(),
              "git_commit": None, "revision_status": "uncommitted-or-unavailable"}
    env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    try:
        head = subprocess.check_output(["git", "-C", str(path.parent), "rev-parse", "HEAD"], env=env, stderr=subprocess.PIPE).decode().strip()
        saved = subprocess.check_output(["git", "-C", str(path.parent), "show", head + ":scripts/s3-policy-plan.py"], env=env, stderr=subprocess.PIPE)
        if re.fullmatch(r"[a-f0-9]{40}", head) and saved == content:
            source.update(git_commit=head, revision_status="committed")
    except (OSError, subprocess.CalledProcessError):
        pass
    return source


def review_manifest(plan, raw, config_hash, source):
    tags = plan["bucket_tags"]
    return {"status": "PREPARE_ONLY_NOT_AUTHORIZED", "version": 1,
            "renderer_source": source, "config_sha256": config_hash,
            "application_source_commit": tags["factory:source-commit"],
            "policy_sha256": hashlib.sha256(raw).hexdigest(), "policy_characters": len(raw.decode("utf-8")),
            "policy_utf8_bytes": len(raw), "managed_policy_character_limit": MAX_POLICY_CHARS,
            "installation": "customer-managed-policy-review-required; no installation performed",
            "target_role": "arn:aws:iam::" + plan["account_id"] + ":role/" + plan["role_name"],
            "region": plan["region"], "bucket_arn": "arn:aws:s3:::" + plan["bucket"],
            "object_arn": "arn:aws:s3:::" + plan["bucket"] + "/" + plan["object_key"],
            "bucket_tags": dict(tags), "object_tags": {key: tags[key] for key in OBJECT_TAGS},
            "object_metadata_exception": {"declared_review_reference": plan["object_tag_exception"]["review_reference"],
                "review_verified": False, "object_tag_count": 10,
                "retained_in_parent_and_private_inventory": {key: tags[key] for key in OMITTED_OBJECT_TAGS}},
            "limits": dict(plan["limits"]), "limits_enforced_by_this_policy": False,
            "unresolved_gates": ["human approval of exact IAM/resource scope and metadata exception",
                "active role/baseline/boundary readback and effective permission validation",
                "TLS, account, IAM/delegation and core/DNS restrictions inherited from unchanged boundary",
                "IAM Access Analyzer/service-model/condition-key validation and authorized simulation",
                "managed-policy attachment quota, private control-plane provenance and administration review",
                "pinned AWS wrapper model, exact create flags/tags, conditional upload and limit enforcement",
                "approved regional S3/STS egress and credential transport",
                "exact resource absence/ownership checks, private defaults and live tag/data/hash readback"],
            "ci_or_live_execution_verified": False}


def no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "Duplicate JSON fields are not accepted")
        obj[key] = value
    return obj


def prepare(config, output, now):
    require(not config.is_symlink() and config.is_file() and not config.stat().st_mode & 0o077
            and not config.parent.stat().st_mode & 0o077 and config.stat().st_size <= 32768,
            "Input must be a private regular JSON file (600) in a private directory (700)")
    require(output.parent.is_dir() and not output.parent.stat().st_mode & 0o077,
            "Output parent must be a private directory (700)")
    raw_config = config.read_bytes()
    plan = json.loads(raw_config, object_pairs_hook=no_duplicates)
    _, raw, _ = render(plan, now)
    manifest = review_manifest(plan, raw, hashlib.sha256(raw_config).hexdigest(), source_reference())
    manifest["config_reference"] = {"path": str(config.resolve()), "sha256": manifest["config_sha256"]}
    # New directory and exclusive files: never overwrite prior reviewed artifacts.
    output.mkdir(mode=0o700)
    for name, content in (("policy.json", raw), ("review.json", json.dumps(manifest, indent=2, sort_keys=True).encode())):
        descriptor = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.plan, args.output_dir, datetime.now(timezone.utc))
    print("PREPARE ONLY: private policy and review manifest written; no authorization, API calls or IAM/resource changes.")


if __name__ == "__main__":
    try:
        main()
    except PlanError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print("ERROR: Invalid private plan or output; existing artifacts preserved. No provider changes.", file=sys.stderr)
        sys.exit(1)
