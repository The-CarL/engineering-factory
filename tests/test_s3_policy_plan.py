"""Offline renderer invariants; these are not IAM simulation or provider proof."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("s3_plan", SOURCE / "scripts/s3-policy-plan.py")
s3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s3)
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def config(now=NOW):
    tags = {"factory:project-id": "flight-check", "factory:environment": "test", "factory:owner": "owner",
            "factory:managed-by": "engineering-factory", "factory:source-repo": "flight-check",
            "factory:source-commit": "a" * 40, "factory:created-by": "codex",
            "factory:created-at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "factory:creation-run-id": "run-01",
            "factory:last-run-id": "run-01", "factory:last-source-commit": "a" * 40,
            "factory:provenance-version": "1", "factory:expires-at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return {"version": 1, "status": "prepare-only", "account_id": "246813579024", "role_name": "factory-test-role",
            "region": "us-east-2", "bucket": "factory-flight-check-abc123", "object_key": "runs/run-01/probe.json",
            "bucket_tags": tags, "object_tag_exception": {"review_reference": "s3-object-tag-review-01",
                "retained_metadata": list(s3.OMITTED_OBJECT_TAGS)},
            "limits": {"buckets": 1, "objects": 1, "object_max_bytes": 1048576, "requests": 25, "incremental_usd": 1}}


class RendererTests(unittest.TestCase):
    def assert_rejected(self, change):
        plan = config()
        change(plan)
        with self.assertRaises(s3.PlanError):
            s3.render(plan, NOW)

    def test_exact_resources_actions_conditional_create_and_fixed_tags(self):
        plan = config()
        policy, raw, object_tags = s3.render(plan, NOW)
        self.assertEqual(len(policy["Statement"]), 5)
        bucket = "arn:aws:s3:::" + plan["bucket"]
        obj = bucket + "/" + plan["object_key"]
        actions = set()
        for statement in policy["Statement"]:
            actions.update([statement["Action"]] if isinstance(statement["Action"], str) else statement["Action"])
            resources = [statement["Resource"]] if isinstance(statement["Resource"], str) else statement["Resource"]
            self.assertTrue(set(resources) <= {bucket, obj})
            self.assertTrue(all("*" not in item and "?" not in item for item in resources))
            self.assertEqual(statement["Condition"]["DateLessThan"]["aws:CurrentTime"], plan["bucket_tags"]["factory:expires-at"])
            self.assertEqual(statement["Condition"]["StringEquals"]["aws:RequestedRegion"], "us-east-2")
        self.assertEqual(actions, set(s3.READ_ACTIONS) | {"s3:CreateBucket", "s3:TagResource", "s3:PutObject", "s3:PutObjectTagging"})
        self.assertFalse(any("Delete" in action or "*" in action or action.startswith("iam:") for action in actions))
        upload = next(item for item in policy["Statement"] if item["Action"] == "s3:PutObject")
        equals = upload["Condition"]["StringEquals"]
        self.assertEqual(equals["s3:if-none-match"], "*")
        self.assertEqual(equals["s3:x-amz-server-side-encryption"], "AES256")
        self.assertEqual(equals["s3:ResourceAccount"], plan["account_id"])
        self.assertEqual(len(object_tags), 10)
        retag = next(item for item in policy["Statement"] if item["Action"] == "s3:PutObjectTagging")
        for key, value in object_tags.items():
            self.assertEqual(retag["Condition"]["StringEquals"]["s3:RequestObjectTag/" + key], value)
        self.assertEqual(len(raw), len(raw.decode("utf-8")))
        self.assertLessEqual(len(raw), 6144)

    def test_bucket_key_account_and_region_cannot_broaden_scope(self):
        for field, values in {
            "bucket": ["*", "factory-test-*", "core-bucket", "factory-test--x-s3", "factory.dot.bucket", "factory-placeholder-123", "factory-fill-project", "factory-bucket-name", "factory-" + "x" * 64],
            "object_key": ["*", "runs/*", "/probe.json", "../probe", "runs/../probe", "runs//probe", "probe?", "${key}", "OBJECT_KEY", "runs/fill-run/probe.json", "runs/placeholder.json"],
            "account_id": ["123", "246813579024*", 123456789012, "000000000000", "111122223333", "123456789012", "١٢٣٤٥٦٧٨٩٠١٢", "[ACCOUNT_ID]"],
            "region": ["us-east-1", "us-madeup-1", "cn-north-1", "us-gov-west-1", "*"],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_rejected(lambda plan: plan.update({field: value}))

    def test_forbidden_policy_actions_overwrite_delete_and_authorization_fields(self):
        for field, value in (("actions", ["s3:*"]), ("Resource", "*"), ("overwrite", True),
                             ("delete_permissions", True), ("authorized", True), ("ci_verified", True)):
            self.assert_rejected(lambda plan: plan.update({field: value}))
        self.assert_rejected(lambda plan: plan.update(status="approved"))
        self.assert_rejected(lambda plan: plan.update(role_name="[ROLE]"))

    def test_provenance_missing_placeholders_secrets_and_original_changes_rejected(self):
        cases = [
            lambda plan: plan["bucket_tags"].pop("factory:owner"),
            lambda plan: plan["bucket_tags"].update({"extra": "value"}),
            lambda plan: plan["bucket_tags"].update({"factory:owner": "REQUIRED_OWNER"}),
            lambda plan: plan["bucket_tags"].update({"factory:owner": "FILL_OWNER_ALIAS"}),
            lambda plan: plan["bucket_tags"].update({"factory:owner": "ghp_" + "x" * 36}),
            lambda plan: plan["bucket_tags"].update({"factory:owner": "owner-246813579024"}),
            lambda plan: plan["bucket_tags"].update({"factory:environment": "production"}),
            lambda plan: plan["bucket_tags"].update({"factory:source-commit": "<NEW_COMMIT>"}),
            lambda plan: plan["bucket_tags"].update({"factory:source-commit": "0" * 40, "factory:last-source-commit": "0" * 40}),
            lambda plan: plan["bucket_tags"].update({"factory:last-source-commit": "b" * 40}),
            lambda plan: plan["bucket_tags"].update({"factory:last-run-id": "changed-run"}),
            lambda plan: plan["object_tag_exception"].update(retained_metadata=[]),
            lambda plan: plan["object_tag_exception"].update(review_reference="TODO"),
        ]
        for change in cases:
            self.assert_rejected(change)
        plan = config()
        plan["bucket_tags"].update({"factory:creation-run-id": "20261019182017-abcdef", "factory:last-run-id": "20261019182017-abcdef"})
        s3.render(plan, NOW)  # A timestamp in a run ID is not an AWS account ID.

    def test_owner_repo_provenance_is_supported_without_url_or_credentials(self):
        plan = config()
        plan["bucket_tags"]["factory:source-repo"] = "test-owner/probe-repo"
        policy, _, object_tags = s3.render(plan, NOW)
        self.assertEqual(object_tags["factory:source-repo"], "test-owner/probe-repo")
        self.assertEqual(policy["Statement"][0]["Condition"]["StringEquals"]["aws:RequestTag/factory:source-repo"], "test-owner/probe-repo")
        for value in ("https://github.com/owner/repo", "owner/repo/extra", "owner/ghp_" + "x" * 36, "owner-246813579024/repo"):
            self.assert_rejected(lambda plan: plan["bucket_tags"].update({"factory:source-repo": value}))

    def test_expired_unbounded_or_invalid_timestamps_rejected(self):
        for expires in ("2026-10-19T11:59:59Z", "2026-10-27T12:00:00Z", "2026-99-99T00:00:00Z", "[EXPIRY]", "2026-10-20"):
            self.assert_rejected(lambda plan: plan["bucket_tags"].update({"factory:expires-at": expires}))
        self.assert_rejected(lambda plan: plan["bucket_tags"].update({"factory:created-at": "2026-10-19T13:00:00Z"}))

    def test_request_budget_and_resource_limits_are_bounded(self):
        for key, value in (("buckets", 2), ("objects", 2), ("object_max_bytes", 1048577),
                           ("requests", 26), ("incremental_usd", 1.01), ("incremental_usd", float("nan")), ("requests", True)):
            self.assert_rejected(lambda plan: plan["limits"].update({key: value}))

    def test_policy_size_failure_does_not_drop_constraints(self):
        plan = config()
        for key in ("factory:project-id", "factory:owner", "factory:source-repo", "factory:created-by"):
            plan["bucket_tags"][key] = "x" * 80
        with self.assertRaisesRegex(s3.PlanError, "6144"):
            s3.render(plan, NOW)

    def test_hashes_and_manifest_are_deterministic_and_do_not_claim_proof(self):
        plan = config()
        first = s3.render(plan, NOW)[1]
        second = s3.render(copy.deepcopy(plan), NOW)[1]
        self.assertEqual(first, second)
        source = {"sha256": "b" * 64, "git_commit": "c" * 40}
        manifest = s3.review_manifest(plan, first, "d" * 64, source)
        self.assertEqual(manifest["policy_sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(manifest["renderer_source"]["git_commit"], "c" * 40)
        self.assertEqual(manifest["application_source_commit"], "a" * 40)
        self.assertFalse(manifest["ci_or_live_execution_verified"])
        self.assertFalse(manifest["object_metadata_exception"]["review_verified"])
        self.assertFalse(manifest["limits_enforced_by_this_policy"])
        self.assertEqual(len(manifest["bucket_tags"]), 13)
        self.assertEqual(len(manifest["object_tags"]), 10)
        self.assertEqual(set(manifest["object_metadata_exception"]["retained_in_parent_and_private_inventory"]), set(s3.OMITTED_OBJECT_TAGS))
        self.assertTrue(any("boundary" in gate for gate in manifest["unresolved_gates"]))


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.input = self.root / "private-plan.json"
        self.input.write_text(json.dumps(config()))
        self.input.chmod(0o600)
        self.output = self.root / "rendered"

    def test_private_outputs_exclusive_and_no_provider_calls(self):
        with patch.object(s3, "source_reference", return_value={"sha256": "b" * 64}):
            manifest = s3.prepare(self.input, self.output, NOW)
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
            for name in ("policy.json", "review.json"):
                self.assertEqual((self.output / name).stat().st_mode & 0o777, 0o600)
            raw = (self.output / "policy.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["policy_sha256"])
            with self.assertRaises(FileExistsError):
                s3.prepare(self.input, self.output, NOW)
            self.assertEqual(raw, (self.output / "policy.json").read_bytes())

    def test_invalid_or_public_input_creates_no_output(self):
        self.input.chmod(0o644)
        with self.assertRaises(s3.PlanError):
            s3.prepare(self.input, self.output, NOW)
        self.assertFalse(self.output.exists())
        self.input.chmod(0o600)
        self.input.write_text('{"version":1,"version":1}')
        with self.assertRaises(s3.PlanError):
            s3.prepare(self.input, self.output, NOW)
        self.assertFalse(self.output.exists())
        self.input.write_text(json.dumps(config()))
        self.root.chmod(0o755)
        with self.assertRaises(s3.PlanError):
            s3.prepare(self.input, self.output, NOW)

    def test_cli_does_not_echo_private_values_or_paths(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.input.write_text(json.dumps(config(now)))
        result = subprocess.run([sys.executable, str(SOURCE / "scripts/s3-policy-plan.py"), "--plan", str(self.input),
                                 "--output-dir", str(self.output)], capture_output=True, text=True,
                                env={"PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in (str(self.root), "246813579024", "factory-flight-check-abc123", "factory-test-role"):
            self.assertNotIn(value, result.stdout + result.stderr)
        self.assertIn("PREPARE ONLY", result.stdout)
        self.input.write_text(json.dumps(dict(config(now), account_id="private-invalid-account")))
        result = subprocess.run([sys.executable, str(SOURCE / "scripts/s3-policy-plan.py"), "--plan", str(self.input),
                                 "--output-dir", str(self.root / "invalid")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("private-invalid-account", result.stdout + result.stderr)
        self.assertFalse((self.root / "invalid").exists())
        self.input.write_text(json.dumps(dict(config(now), account_id="000000000000")))
        result = subprocess.run([sys.executable, str(SOURCE / "scripts/s3-policy-plan.py"), "--plan", str(self.input),
                                 "--output-dir", str(self.root / "zero-account")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("000000000000", result.stdout + result.stderr)
        self.assertFalse((self.root / "zero-account").exists())
