"""Offline behavior tests: mocked providers, real local Git, isolated auth stores."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
REAL_GIT = shutil.which("git")
REAL_PYTHON = shutil.which("python3")
MOCK = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = Path(os.environ["MOCK_STATE"])
state = json.loads(state_path.read_text())
with Path(os.environ["MOCK_LOG"]).open("a") as log:
    log.write(json.dumps([name, args]) + "\n")

def stop():
    print("PRIVATE_PROVIDER_DIAGNOSTIC_MUST_NOT_LEAK", file=sys.stderr)
    sys.exit(1)

def save():
    state_path.write_text(json.dumps(state))

if name == "git":
    # Real Git checks local repo structure; no network-capable command may escape.
    if any(arg in ("clone", "fetch", "push", "pull", "ls-remote") for arg in args):
        stop()
    os.execv(os.environ["REAL_GIT"], [os.environ["REAL_GIT"]] + args)
if name == "gh":
    if os.environ.get("GH_HOST") != "github.com":
        stop()
    if args[:1] == ["api"]:
        if "--hostname" not in args or args[args.index("--hostname") + 1] != "github.com":
            stop()
        if state.get("api_failure"):
            stop()
        endpoint = next((arg for arg in args[1:] if arg == "user" or arg.startswith(("users/", "user/", "orgs/"))), "")
        if "--method" in args and args[args.index("--method") + 1] == "POST":
            state["creates"] = state.get("creates", 0) + 1
            state["create_endpoint"] = endpoint
            payload = json.load(sys.stdin)
            state["create_payload"] = payload
            expected = "user/repos" if state.get("owner_type", "User") == "User" else "orgs/example-owner/repos"
            if endpoint != expected or "--input" not in args or "--include" not in args:
                save()
                stop()
            target = "example-owner/" + payload["name"]
            visibility = "private" if payload["private"] else "public"
            if not state.get("create_failure") or state.get("create_failure_after_write"):
                state.setdefault("repos", []).append({"full_name": target, "visibility": visibility})
            save()
            if state.get("create_failure"):
                print("HTTP/2.0 403 Forbidden\r\nx-github-request-id: ABCD:123456:ABCD12:123456:12345678\r\n\r\n" + json.dumps({"message": "Resource not accessible by personal access token PRIVATE_PROVIDER_DIAGNOSTIC_MUST_NOT_LEAK"}))
                stop()
            print("HTTP/2.0 201 Created\r\ncontent-type: application/json\r\n\r\n" + json.dumps({"full_name": target, "private": payload["private"]}))
        elif endpoint == "user":
            print(state.get("identity", "example-owner"))
        elif endpoint.startswith("users/"):
            print(state.get("owner_type", "User"))
        elif endpoint.startswith("user/memberships/"):
            print(state.get("membership", "active"))
        elif endpoint.startswith(("user/repos?", "orgs/")):
            if state.get("inventory_failure"):
                stop()
            if "--paginate" not in args or "--slurp" not in args or "per_page=10" not in endpoint:
                stop()
            if state.get("malformed_inventory"):
                print('{"error":"unexpected"}')
            else:
                print(json.dumps([[], state.get("repos", [])]))
        else:
            stop()
    elif args[:2] == ["repo", "clone"]:
        state["clones"] = state.get("clones", 0) + 1
        save()
        target, path = args[2:4]
        Path(path).mkdir(parents=True)
        if state.get("clone_failure"):
            (Path(path) / "partial.txt").write_text("interrupted")
            print(state.get("clone_diagnostic", ""), file=sys.stderr)
            stop()
        git = os.environ["REAL_GIT"]
        subprocess.run([git, "init", "--quiet", path], check=True)
        origin = state.get("clone_origin", "https://github.com/" + target + ".git")
        subprocess.run([git, "-C", path, "remote", "add", "origin", origin], check=True)
    else:
        stop()
elif name == "vercel":
    if args != ["whoami", "--format", "json", "--scope", "sandbox-team", "--non-interactive"] or state.get("vercel_failure"):
        stop()
    print(json.dumps(state.get("vercel_response", {"username": "automation", "team": {"id": "team_Approved", "slug": "sandbox-team"}})))
elif name == "aws":
    if args != ["sts", "get-caller-identity", "--region", "us-east-1", "--query", "Arn", "--output", "text", "--no-cli-pager"] or state.get("aws_failure"):
        stop()
    print(state.get("aws_arn", "arn:aws:sts::000000000000:assumed-role/SandboxRole/test-session"))
else:
    # node/npm/terraform/cdk are inventory stubs; executing them is unexpected.
    stop()
'''


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory behavior ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.factory = self.base / "factory checkout"
        self.factory.mkdir()
        shutil.copytree(SOURCE / "scripts", self.factory / "scripts")
        shutil.copyfile(SOURCE / ".gitignore", self.factory / ".gitignore")
        self.bin = self.base / "mock-bin"
        self.bin.mkdir()
        for name in ("gh", "git", "vercel", "aws", "node", "npm", "terraform", "cdk"):
            path = self.bin / name
            path.write_text(MOCK)
            path.chmod(0o755)
        # Explicit allowlist excludes ALL inherited provider credentials and Git settings.
        home = self.base / "home"
        home.mkdir()
        self.state_path = self.base / "state.json"
        self.log = self.base / "calls.jsonl"
        self.env = {
            "PATH": str(self.bin) + os.pathsep + str(Path(REAL_PYTHON).parent) + os.pathsep + "/usr/bin:/bin",
            "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
            "GH_CONFIG_DIR": str(home / "gh"), "AWS_CONFIG_FILE": str(home / "aws-config"),
            "AWS_SHARED_CREDENTIALS_FILE": str(home / "aws-credentials"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GH_HOST": "hostile.invalid", "GH_PROMPT_DISABLED": "1", "CI": "true",
            "REAL_GIT": REAL_GIT, "MOCK_STATE": str(self.state_path), "MOCK_LOG": str(self.log),
            "FACTORY_GITHUB_OWNER": "example-owner",
            "FACTORY_VERCEL_TEAM_ID": "team_Approved", "FACTORY_VERCEL_TEAM_SLUG": "sandbox-team",
            "FACTORY_AWS_ACCOUNT_ID": "000000000000", "FACTORY_AWS_REGION": "us-east-1",
            "FACTORY_AWS_ROLE_NAME": "SandboxRole",
        }
        self.write_state({"repos": []})
        self.local_git("init", "--quiet", str(self.factory))
        self.checkout = self.factory / "workspaces/example-owner/demo"

    def local_git(self, *args):
        return subprocess.run([REAL_GIT, *args], env=self.env, capture_output=True, text=True, check=True)

    def write_state(self, state):
        self.state_path.write_text(json.dumps(state))

    def state(self):
        return json.loads(self.state_path.read_text())

    def update(self, **kwargs):
        state = self.state()
        state.update(kwargs)
        self.write_state(state)

    def existing(self, visibility="private", target="example-owner/demo"):
        self.update(repos=[{"full_name": target, "visibility": visibility}])

    def run_script(self, script, *args, ok=True):
        result = subprocess.run(["/bin/bash", str(self.factory / "scripts" / script), *args],
                                cwd=self.base, env=self.env, capture_output=True, text=True)
        self.assertNotIn("PRIVATE_PROVIDER_DIAGNOSTIC_MUST_NOT_LEAK", result.stdout + result.stderr)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_no_mutations(self):
        self.assertEqual(self.state().get("creates", 0), 0)
        self.assertEqual(self.state().get("clones", 0), 0)
        self.assertFalse(self.checkout.exists())

    def create(self, *args, **kwargs):
        return self.run_script("create-repo.sh", "example-owner/demo", "--confirm", "example-owner/demo", *args, **kwargs)

    def clone(self, *args, **kwargs):
        return self.run_script("clone-repo.sh", "example-owner/demo", *args, **kwargs)

    def test_create_private_then_retry_preserves_dirty_checkout(self):
        self.create()
        self.assertTrue((self.checkout / ".git").is_dir())
        dirty = self.checkout / "local-change.txt"
        dirty.write_text("do not reset")
        self.create()
        self.assertEqual(dirty.read_text(), "do not reset")
        self.assertEqual(self.state()["creates"], 1)
        self.assertEqual(self.state()["clones"], 1)
        self.assertEqual(self.state()["repos"][0]["visibility"], "private")
        self.assertEqual(self.state()["create_endpoint"], "user/repos")
        self.assertEqual(self.state()["create_payload"], {"name": "demo", "private": True})
        self.assertFalse(any(call[1][:2] == ["repo", "create"] for call in self.calls()))

    def test_existing_remote_is_reused_without_create(self):
        self.existing()
        self.create()
        self.assertEqual(self.state().get("creates", 0), 0)
        self.assertEqual(self.state()["clones"], 1)

    def test_clone_existing_private(self):
        self.existing()
        self.clone()
        self.assertTrue((self.checkout / ".git").is_dir())
        self.assertEqual(self.state().get("creates", 0), 0)

    def test_public_requires_explicit_matching_visibility(self):
        self.existing("public")
        self.clone(ok=False)
        self.assert_no_mutations()
        self.clone("--visibility", "public")

    def test_create_public_is_explicit(self):
        self.create("--visibility", "public")
        self.assertEqual(self.state()["repos"][0]["visibility"], "public")

    def test_existing_visibility_mismatch_aborts(self):
        self.existing("public")
        self.create(ok=False)
        self.assert_no_mutations()

    def test_missing_repo_clone_aborts_without_create(self):
        self.clone(ok=False)
        self.assert_no_mutations()

    def test_create_requires_exact_confirmation(self):
        self.run_script("create-repo.sh", "example-owner/demo", ok=False)
        self.run_script("create-repo.sh", "example-owner/demo", "--confirm", "other/repo", ok=False)
        self.assert_no_mutations()
        self.assertFalse(any(call[0] == "gh" for call in self.calls()))

    def test_dry_runs_do_not_call_providers_or_write(self):
        self.run_script("create-repo.sh", "example-owner/demo", "--dry-run")
        self.clone("--dry-run")
        self.assert_no_mutations()
        self.assertFalse((self.factory / "workspaces").exists())
        self.assertFalse(any(call[0] != "git" for call in self.calls()))

    def test_bad_target_and_owner_fail_before_provider_calls(self):
        for target in ("other-owner/demo", "example-owner/../demo", "example-owner/..", "example-owner/.",
                       "example-owner/demo.git", "-bad/demo", "example-owner/demo/extra", "demo"):
            self.run_script("create-repo.sh", target, "--dry-run", ok=False)
        self.assert_no_mutations()
        self.assertFalse(any(call[0] == "gh" for call in self.calls()))

    def test_auth_failure_never_means_absence(self):
        self.update(api_failure=True)
        self.create(ok=False)
        self.assert_no_mutations()

    def test_inventory_network_failure_never_means_absence(self):
        self.update(inventory_failure=True)
        self.create(ok=False)
        self.assert_no_mutations()

    def test_malformed_inventory_never_means_absence(self):
        self.update(malformed_inventory=True)
        self.create(ok=False)
        self.assert_no_mutations()

    def test_malformed_inventory_entries_never_trigger_create(self):
        for entry in ("invalid", {}, {"full_name": "example-owner/demo"},
                      {"full_name": 123, "visibility": "private"}):
            self.update(repos=[entry])
            self.create(ok=False)
            self.assert_no_mutations()

    def test_wrong_personal_identity_aborts(self):
        self.update(identity="different-user")
        self.create(ok=False)
        self.assert_no_mutations()

    def test_active_org_membership_allows_visible_inventory(self):
        self.update(owner_type="Organization")
        self.create()
        self.assertTrue(self.checkout.is_dir())
        self.assertEqual(self.state()["create_endpoint"], "orgs/example-owner/repos")

    def test_inactive_org_membership_aborts(self):
        self.update(owner_type="Organization", membership="pending")
        self.create(ok=False)
        self.assert_no_mutations()

    def test_create_error_does_not_attempt_clone(self):
        self.update(create_failure=True)
        result = self.create(ok=False)
        self.assertIn("HTTP 403", result.stderr)
        self.assertIn("token cannot access this resource", result.stderr)
        self.assertIn("request_id=ABCD:123456:ABCD12:123456:12345678", result.stderr)
        self.assertEqual(self.state()["creates"], 1)
        self.assertEqual(self.state().get("clones", 0), 0)
        self.assertFalse(self.checkout.exists())

    def test_create_lost_response_reconciles_and_retry_does_not_post(self):
        self.update(create_failure=True, create_failure_after_write=True)
        self.create(ok=False)
        self.assertEqual(self.state()["creates"], 1)
        self.assertFalse(self.checkout.exists())
        self.create()
        self.assertEqual(self.state()["creates"], 1)
        self.assertTrue(self.checkout.exists())

    def test_failed_clone_cleans_partial_and_retry_reuses_remote(self):
        self.update(clone_failure=True)
        self.create(ok=False)
        self.assertFalse(self.checkout.exists())
        owner = self.checkout.parent
        self.assertEqual(list(owner.iterdir()), [])
        self.update(clone_failure=False)
        self.create()
        self.assertEqual(self.state()["creates"], 1)
        self.assertEqual(self.state()["clones"], 2)
        self.assertFalse((self.checkout / "partial.txt").exists())

    def test_clone_auth_failure_is_classified_without_private_git_output(self):
        synthetic = "ghp_" + "x" * 36
        self.existing()
        self.update(clone_failure=True, clone_diagnostic="fatal: Authentication failed for https://user:" + synthetic + "@github.com/private/repo")
        result = self.clone(ok=False)
        self.assertIn("Git credentials rejected", result.stderr)
        self.assertNotIn(synthetic, result.stderr + result.stdout)
        self.assertNotIn("/private/repo", result.stderr + result.stdout)
        self.assertFalse(self.checkout.exists())

    def test_wrong_cloned_origin_does_not_publish_checkout(self):
        self.existing()
        self.update(clone_origin="https://github.com/unexpected/repo.git")
        self.clone(ok=False)
        self.assertFalse(self.checkout.exists())
        self.assertEqual(list(self.checkout.parent.iterdir()), [])

    def test_wrong_existing_origin_aborts_preserving_files(self):
        self.existing()
        self.clone()
        self.local_git("-C", str(self.checkout), "remote", "set-url", "origin", "https://github.com/other/repo.git")
        dirty = self.checkout / "work.txt"
        dirty.write_text("keep")
        self.clone(ok=False)
        self.assertEqual(dirty.read_text(), "keep")
        self.assertEqual(self.state()["clones"], 1)

    def test_wrong_push_url_aborts(self):
        self.existing()
        self.clone()
        self.local_git("-C", str(self.checkout), "remote", "set-url", "--push", "origin", "https://github.com/other/repo.git")
        self.clone(ok=False)
        self.assertEqual(self.state()["clones"], 1)

    def test_case_changes_reuse_canonical_workspace(self):
        self.existing()
        self.clone()
        self.run_script("clone-repo.sh", "Example-Owner/DEMO")
        self.assertEqual(self.state()["clones"], 1)
        self.assertEqual([path.name for path in (self.factory / "workspaces").iterdir()], ["example-owner"])

    def test_symlink_paths_fail_without_provider_mutation(self):
        external = self.base / "external"
        external.mkdir()
        (self.factory / "workspaces").symlink_to(external, target_is_directory=True)
        self.create(ok=False)
        self.assert_no_mutations()
        self.assertEqual(list(external.iterdir()), [])

    def test_repository_symlink_fails(self):
        self.checkout.parent.mkdir(parents=True)
        external = self.base / "external"
        external.mkdir()
        self.checkout.symlink_to(external, target_is_directory=True)
        self.create(ok=False)
        self.assertEqual(self.state().get("creates", 0), 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_nonrepo_existing_directory_preserved(self):
        self.existing()
        self.checkout.mkdir(parents=True)
        marker = self.checkout / "keep.txt"
        marker.write_text("keep")
        self.clone(ok=False)
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual(self.state().get("clones", 0), 0)

    def test_nonignored_workspace_aborts(self):
        (self.factory / ".gitignore").write_text("")
        self.create(ok=False)
        self.assert_no_mutations()

    def test_stale_lock_is_preserved_and_blocks_clone(self):
        self.existing()
        self.checkout.parent.mkdir(parents=True)
        lock = self.checkout.parent / ".demo.lock"
        lock.mkdir()
        self.clone(ok=False)
        self.assertTrue(lock.exists())
        self.assertEqual(self.state().get("clones", 0), 0)

    def test_offline_preflight_never_calls_providers(self):
        self.run_script("preflight.sh", "--offline", "--provider", "aws")
        self.assertEqual(self.calls(), [])

    def test_default_preflight_is_tool_only(self):
        self.run_script("preflight.sh")
        self.assertEqual(self.calls(), [])

    def test_github_preflight_is_read_only(self):
        self.run_script("preflight.sh", "--provider", "github")
        self.assert_no_mutations()

    def test_github_only_does_not_require_aws_vercel(self):
        (self.bin / "aws").unlink()
        (self.bin / "vercel").unlink()
        self.run_script("preflight.sh", "--provider", "github")
        self.assertFalse(any(call[0] in ("aws", "vercel") for call in self.calls()))

    def test_vercel_preflight_correct_team(self):
        result = self.run_script("preflight.sh", "--provider", "vercel")
        self.assertNotIn("automation", result.stdout)
        self.assertIn("UNVERIFIED", result.stdout)
        self.assert_no_mutations()

    def test_vercel_wrong_team_or_unreadable_identity_fails(self):
        for response in ({"username": "x", "team": {"id": "team_Wrong"}}, {"loggedIn": False}, {"team": {"id": "team_Approved"}}):
            self.update(vercel_response=response)
            self.run_script("preflight.sh", "--provider", "vercel", ok=False)
        self.update(vercel_failure=True)
        self.run_script("preflight.sh", "--provider", "vercel", ok=False)

    def test_aws_preflight_role_account_region(self):
        result = self.run_script("preflight.sh", "--provider", "aws")
        self.assertNotIn("000000000000", result.stdout)
        self.assertIn("UNVERIFIED", result.stdout)

    def test_aws_wrong_account_role_or_root_fails(self):
        for arn in ("arn:aws:sts::111111111111:assumed-role/SandboxRole/x", "arn:aws:sts::000000000000:assumed-role/Admin/x", "arn:aws:iam::000000000000:root"):
            self.update(aws_arn=arn)
            self.run_script("preflight.sh", "--provider", "aws", ok=False)

    def test_aws_conflicting_region_fails_before_api(self):
        self.env["AWS_REGION"] = "us-west-2"
        self.run_script("preflight.sh", "--provider", "aws", ok=False)
        self.assertFalse(any(call[0] == "aws" for call in self.calls()))

    def test_missing_provider_configuration_fails(self):
        for provider, key in (("github", "FACTORY_GITHUB_OWNER"), ("vercel", "FACTORY_VERCEL_TEAM_ID"), ("aws", "FACTORY_AWS_ACCOUNT_ID")):
            value = self.env.pop(key)
            self.run_script("preflight.sh", "--provider", provider, ok=False)
            self.env[key] = value


class SecretScannerTests(unittest.TestCase):
    def test_detects_runtime_synthetic_secret_in_innocuous_file_and_redacts(self):
        scanner = SOURCE / ".cache/tools/gitleaks"
        self.assertTrue(scanner.is_file(), "Run scripts/install-check-tools.sh before tests")
        with tempfile.TemporaryDirectory(prefix="factory-scanner-") as temp:
            path = Path(temp)
            # Construct a non-live test value at runtime; no usable fixture is committed.
            synthetic = "ghp_" + "9aB2cD3eF4gH5iJ6kL7mN8pQ1rS0tU2vW3xY"
            (path / "ordinary-notes.txt").write_text("github_token = " + synthetic + "\n")
            result = subprocess.run([str(scanner), "dir", str(path), "--config", str(SOURCE / ".gitleaks.toml"),
                                     "--gitleaks-ignore-path", str(path), "--ignore-gitleaks-allow",
                                     "--redact=100", "--no-banner", "--exit-code", "42", "--verbose"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
            self.assertNotIn(synthetic, result.stdout + result.stderr)
            self.assertIn("ordinary-notes.txt", result.stdout + result.stderr)
