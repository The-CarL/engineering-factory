"""Behavior regressions for redaction, preview scoping, retry safety and recovery."""
import copy
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import base64
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "scripts/lib"))
from provider import ProviderError, Vercel, diagnostic, NoRedirect, gh_environment, gh, gh_clone

spec = importlib.util.spec_from_file_location("preview", SOURCE / "scripts/vercel-preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class DiagnosticTests(unittest.TestCase):
    def test_provider_messages_are_classified_never_echoed(self):
        synthetic = "ghp_" + "x" * 36
        for raw in (
            {"message": "Resource not accessible by personal access token " + synthetic},
            {"error": {"message": "bad credentials https://user:" + synthetic + "@private.invalid", "code": synthetic}},
            {"error": {"message": {"nested": synthetic}, "code": [synthetic]}},
        ):
            text = diagnostic("GitHub", 403, {"authorization": "Bearer " + synthetic,
                              "x-github-request-id": synthetic}, json.dumps(raw), synthetic)
            self.assertIn("HTTP 403", text)
            self.assertNotIn(synthetic, text)
            self.assertNotIn("private.invalid", text)
            self.assertNotIn("request_id", text)

    def test_real_vercel_request_id_format_is_retained(self):
        request_id = "iad1:sfo1::6dwdn-1792437742414-954c2c15d199"
        self.assertIn("request_id=" + request_id, diagnostic("Vercel", 400, {"x-vercel-id": request_id}))

    def test_vercel_400_retains_only_allowlisted_code_and_reason(self):
        raw = {"error": {"code": "invalid_engines_value", "message": "invalid_engines_value; npm; secret=hidden"}}
        text = diagnostic("Vercel", 400, body=json.dumps(raw))
        self.assertIn("HTTP 400", text)
        self.assertIn("code=invalid_engines_value", text)
        self.assertIn("unsupported package engines configuration", text)
        self.assertNotIn("hidden", text)

    def test_malformed_free_text_and_headers_do_not_escape(self):
        for raw in (b"<html>token=hidden</html>", b"{bad", b"[]", b"null", b"42"):
            text = diagnostic("Vercel", 403, {"x-vercel-id": "token-hidden\nforged"}, raw)
            self.assertNotIn("hidden", text)
            self.assertNotIn("forged", text)
            self.assertIn("provider detail withheld", text)

    def test_http_error_body_is_sanitized_and_not_retried(self):
        with patch.dict(os.environ, {"VERCEL_TOKEN": "placeholder-value"}, clear=True):
            api = Vercel()
        error = urllib.error.HTTPError("https://api.vercel.com", 400, "private reason", {},
                                      io.BytesIO(b'{"error":{"code":"invalid_target","message":"secret hidden"}}'))
        with patch.object(api.opener, "open", side_effect=error) as send:
            with self.assertRaises(ProviderError) as caught:
                api.request("POST", "/v13/deployments", {"name": "test"})
        self.assertEqual(send.call_count, 1)
        self.assertIn("code=invalid_target", str(caught.exception))
        self.assertNotIn("hidden", str(caught.exception))

    def test_transport_keeps_binding_out_of_argv_and_blocks_redirects(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return b'{"user":{"id":"test"}}'
        with patch.dict(os.environ, {"VERCEL_TOKEN": "network-secret-placeholder"}, clear=True):
            api = Vercel()
        with patch.object(api.opener, "open", return_value=Response()) as send:
            api.request("GET", "/v2/user")
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.vercel.com/v2/user")
        self.assertEqual(request.get_header("Authorization"), "Bearer network-secret-placeholder")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "x", {}, "https://hostile.invalid"))
        with self.assertRaises(ProviderError):
            api.request("GET", "https://hostile.invalid")


class GitHubCredentialSourceTests(unittest.TestCase):
    def test_default_and_explicit_cli_preserve_stock_sources(self):
        original = {"GH_TOKEN": "stock-primary", "GITHUB_TOKEN": "stock-secondary",
                    "FACTORY_GITHUB_TOKEN": "unused-namespaced", "GH_CONFIG_DIR": "/private/approved-gh",
                    "GH_DEBUG": "api", "DEBUG": "1", "GIT_TRACE_CURL": "1"}
        for mode in (None, "cli"):
            values = dict(original)
            if mode is not None:
                values["FACTORY_GITHUB_CREDENTIAL_SOURCE"] = mode
            with patch.dict(os.environ, values, clear=True):
                child = gh_environment()
                self.assertEqual(child["GH_TOKEN"], "stock-primary")
                self.assertEqual(child["GITHUB_TOKEN"], "stock-secondary")
                self.assertEqual(child["GH_CONFIG_DIR"], "/private/approved-gh")
                self.assertNotIn("FACTORY_GITHUB_TOKEN", child)
                for key in ("GH_DEBUG", "DEBUG", "GIT_TRACE_CURL"):
                    self.assertNotIn(key, child)
                self.assertEqual(os.environ["FACTORY_GITHUB_TOKEN"], "unused-namespaced")
        with patch.dict(os.environ, {"FACTORY_GITHUB_TOKEN": "unused-namespaced"}, clear=True):
            self.assertNotIn("GH_TOKEN", gh_environment())

    def test_factory_mode_selects_only_namespaced_binding_without_parent_mutation(self):
        selected = "ghp_" + "x" * 36
        values = {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "factory-token", "FACTORY_GITHUB_TOKEN": selected,
                  "GH_TOKEN": "competing-primary", "GITHUB_TOKEN": "competing-secondary",
                  "GH_ENTERPRISE_TOKEN": "competing-enterprise", "GITHUB_ENTERPRISE_TOKEN": "competing-enterprise-other"}
        with patch.dict(os.environ, values, clear=True):
            child = gh_environment()
            self.assertEqual(child["GH_TOKEN"], selected)
            self.assertEqual(list(child.values()).count(selected), 1)
            for key in ("FACTORY_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
                self.assertNotIn(key, child)
            self.assertEqual(dict(os.environ), values)

    def test_unknown_mode_or_missing_binding_stops_before_api_and_clone_spawn(self):
        cases = [
            {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "private-invalid-mode"},
            {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "factory-token", "GH_TOKEN": "forbidden-fallback"},
            {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "factory-token", "FACTORY_GITHUB_TOKEN": "  ", "GITHUB_TOKEN": "forbidden-fallback"},
        ]
        for values in cases:
            for operation in (lambda: gh(["user"]), lambda: gh_clone("owner/repo", "/private/clone")):
                with patch.dict(os.environ, values, clear=True), patch("provider.subprocess.run") as spawn:
                    with self.assertRaises(ProviderError) as caught:
                        operation()
                    spawn.assert_not_called()
                    self.assertNotIn("private-invalid-mode", str(caught.exception))
                    self.assertNotIn("forbidden-fallback", str(caught.exception))

    def test_both_helpers_select_child_env_without_token_in_arguments_or_output(self):
        selected = "ghp_" + "x" * 36
        values = {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "factory-token", "FACTORY_GITHUB_TOKEN": selected,
                  "GH_TOKEN": "competing", "GITHUB_TOKEN": "other", "GH_DEBUG": "api", "DEBUG": "1",
                  "GIT_TRACE": "/private/trace", "GIT_TRACE_CURL": "1", "GIT_CURL_VERBOSE": "1"}
        stdout, stderr = io.StringIO(), io.StringIO()
        result = subprocess.CompletedProcess([], 0, stdout=b"{}", stderr=b"")
        with patch.dict(os.environ, values, clear=True), patch("provider.subprocess.run", return_value=result) as spawn:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(gh(["user"]), b"{}")
                gh_clone("owner/repo", "/private/clone")
            self.assertEqual(spawn.call_count, 2)
            for call in spawn.call_args_list:
                self.assertEqual(call.kwargs["env"]["GH_TOKEN"], selected)
                for key in ("GH_DEBUG", "DEBUG", "GIT_TRACE", "GIT_TRACE_CURL", "GIT_CURL_VERBOSE", "GITHUB_TOKEN", "FACTORY_GITHUB_TOKEN"):
                    self.assertNotIn(key, call.kwargs["env"])
                self.assertNotIn(selected, " ".join(call.args[0]))
            self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")

    def test_cli_failure_never_echoes_selected_or_competing_values(self):
        selected = "ghp_" + "x" * 36
        result = subprocess.CompletedProcess([], 1, stdout=b"", stderr=("bad credentials " + selected).encode())
        with patch.dict(os.environ, {"FACTORY_GITHUB_CREDENTIAL_SOURCE": "factory-token", "FACTORY_GITHUB_TOKEN": selected,
                                     "GH_TOKEN": "competing-primary", "GITHUB_TOKEN": "competing-secondary"}, clear=True):
            with patch("provider.subprocess.run", return_value=result) as spawn:
                with self.assertRaises(ProviderError) as caught:
                    gh(["user"])
                self.assertEqual(spawn.call_count, 1)
        self.assertIn("credentials rejected", str(caught.exception))
        for value in (selected, "competing-primary", "competing-secondary"):
            self.assertNotIn(value, str(caught.exception))


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.project = {"id": "prj_Test", "accountId": "team_Test", "name": "hello",
                        "ssoProtection": {"deploymentType": "all"},
                        "targets": {"production": {"id": "dpl_Baseline", "readyState": "READY"}}}
        self.preview = {"id": "dpl_Test", "projectId": "prj_Test", "target": None,
                        "readyState": "READY", "url": "hello-abc.vercel.app"}
        self.post_failure = None

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/v2/user":
            return {"user": {"id": "user_Test"}}
        if path.startswith("/v2/teams/"):
            return {"id": "team_Test", "slug": "test-team"}
        if path.startswith("/v9/projects/"):
            return copy.deepcopy(self.project)
        if path.startswith("/v13/deployments/dpl_Baseline"):
            return {"id": "dpl_Baseline", "projectId": "prj_Test", "target": "production", "readyState": "READY"}
        if method == "POST":
            if self.post_failure:
                raise self.post_failure
            self.preview["meta"] = copy.deepcopy(payload["meta"])
            return {"id": "dpl_Test"}
        return copy.deepcopy(self.preview)

    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]


def payload():
    meta = {key: "test-value" for key in preview.METADATA}
    meta.update(factoryEnvironment="preview", factoryManagedBy="engineering-factory", factoryProvenanceVersion="1",
                factorySourceCommit="a" * 40, factoryLastSourceCommit="a" * 40)
    return {"name": "hello", "project": "prj_Test", "files": [{"file": "index.html", "data": "Hello"}],
            "meta": meta, "gitMetadata": {"commitSha": "a" * 40, "dirty": False}}


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        self.record = self.directory / "operations.jsonl"
        self.api = FakeAPI()
        self.payload = payload()

    def run_preview(self, **kwargs):
        with patch("builtins.print"):
            return preview.run_preview(self.api, "team_Test", "test-team", "prj_Test",
                                       self.payload, "digest", self.record, **kwargs)

    def test_preview_ready_exact_target_metadata_and_resume_never_redeploys(self):
        self.run_preview()
        self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)
        request = self.api.posts()[0]
        self.assertEqual(request[1], "/v13/deployments?teamId=team_Test")
        self.assertNotIn("target", request[2])
        self.assertNotIn("commitRef", request[2]["gitMetadata"])
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o600)
        self.assertIn('"hostname": "hello-abc.vercel.app"', self.record.read_text())

    def test_missing_or_failed_production_baseline_never_mutates(self):
        for targets in ({}, {"production": {"id": "dpl_Baseline", "readyState": "ERROR"}}):
            self.api.project["targets"] = targets
            with self.assertRaisesRegex(ProviderError, "Preview blocked"):
                self.run_preview()
            self.assertEqual(self.api.posts(), [])
            self.assertEqual(self.record.read_text(), "")

    def test_wrong_team_project_or_absent_protection_never_mutates(self):
        for key, bad in (("accountId", "team_Other"), ("id", "prj_Other"), ("name", "other"), ("ssoProtection", None)):
            api = FakeAPI()
            api.project[key] = bad
            self.api = api
            with self.assertRaises(ProviderError):
                self.run_preview()
            self.assertEqual(self.api.posts(), [])

    def test_unexpected_production_readback_fails_without_retry_or_delete(self):
        self.api.preview["target"] = "production"
        with self.assertRaisesRegex(ProviderError, "not preview"):
            self.run_preview()
        with self.assertRaisesRegex(ProviderError, "not preview"):
            self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)
        self.assertFalse(any(call[0] in ("DELETE", "PATCH") for call in self.api.calls))

    def test_source_metadata_mismatch_fails_acceptance(self):
        self.run_preview()
        self.api.preview["meta"]["factoryLastSourceCommit"] = "b" * 40
        with self.assertRaisesRegex(ProviderError, "provenance/source mismatch"):
            self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)

    def test_unknown_or_rejected_post_outcome_is_not_retried(self):
        self.api.post_failure = ProviderError("Vercel; HTTP 400; provider detail withheld")
        with self.assertRaises(ProviderError):
            self.run_preview()
        self.api.post_failure = None
        with self.assertRaisesRegex(ProviderError, "Prior mutation outcome unknown/rejected"):
            self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)

    def test_timeout_retains_id_and_resume_only_polls(self):
        self.api.preview["readyState"] = "BUILDING"
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.run_preview(wait_seconds=0)
        self.api.preview["readyState"] = "READY"
        self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)

    def test_changed_request_cannot_reuse_operation_record(self):
        self.run_preview()
        self.payload["meta"]["factoryLastRunId"] = "different-run"
        with self.assertRaisesRegex(ProviderError, "record/request mismatch"):
            self.run_preview()
        self.assertEqual(len(self.api.posts()), 1)

    def test_request_validation_blocks_target_branch_credentials_and_traversal(self):
        request = self.directory / "request.json"
        source = self.directory / "source"
        source.mkdir()
        (source / "index.html").write_text("Hello")
        env = {"PATH": os.defpath, "HOME": str(self.directory), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], env=env, stderr=subprocess.PIPE).decode().strip()
        git("init", "--quiet")
        git("add", "index.html")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "test source")
        commit = git("rev-parse", "HEAD")
        def valid_payload():
            data = payload()
            data["meta"]["factoryLastSourceCommit"] = commit
            data["gitMetadata"]["commitSha"] = commit
            data["meta"].update(factorySourceRepo="fixture-owner/app", factoryProjectName="Hello World",
                                factoryRepoName="app", factorySourceBranch="unknown", factorySourceAuthor="unknown",
                                factoryLastSourceBranch=git("branch", "--show-current"), factoryLastSourceAuthor="Test")
            return data
        for mutation in (
            lambda p: p.update(target="preview"),
            lambda p: p.update(env={"TOKEN": "secret"}),
            lambda p: p["gitMetadata"].update(commitRef="main"),
            lambda p: p["files"][0].update(file="../app.js"),
            lambda p: p["files"][0].update(file=".env.local"),
            lambda p: p["meta"].update(factoryEnvironment="production"),
        ):
            data = valid_payload()
            mutation(data)
            request.write_text(json.dumps(data))
            request.chmod(0o600)
            with self.assertRaises(ProviderError):
                preview.read_request(request, "prj_Test", source)
        request.write_text(json.dumps(valid_payload()))
        parsed, digest = preview.read_request(request, "prj_Test", source)
        self.assertEqual(parsed["project"], "prj_Test")
        self.assertEqual(len(digest), 64)
        for mutation in (
            lambda p: p["files"][0].update(data="substituted bytes"),
            lambda p: p["files"].append({"file": "extra.js", "data": "extra"}),
            lambda p: p["meta"].update(extra="not allowed"),
        ):
            data = valid_payload()
            mutation(data)
            request.write_text(json.dumps(data))
            with self.assertRaises(ProviderError):
                preview.read_request(request, "prj_Test", source)
        data = valid_payload()
        data["files"][0].update(data=base64.b64encode(b"Hello").decode(), encoding="base64")
        request.write_text(json.dumps(data))
        preview.read_request(request, "prj_Test", source)
        (source / "index.html").write_text("dirty bytes")
        with self.assertRaisesRegex(ProviderError, "clean"):
            preview.read_request(request, "prj_Test", source)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        (self.root / "source.bundle").write_bytes(b"committed source")
        (self.root / "project.json").write_text('{"project":"private target"}')

    def run_tool(self, command, *extra):
        return subprocess.run([sys.executable, str(SOURCE / "scripts/recovery-manifest.py"), command,
                              "--root", str(self.root), "--manifest", str(self.manifest), *extra],
                              capture_output=True, text=True, env={"PATH": os.defpath})

    def create(self):
        result = self.run_tool("create", "--commit", "a" * 40, "source.bundle", "project.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("private target", result.stdout + result.stderr)

    def test_recovery_hashes_restore_and_tamper_detection(self):
        self.create()
        self.assertEqual(self.manifest.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run_tool("verify").returncode, 0)
        (self.root / "source.bundle").write_bytes(b"different source")
        result = self.run_tool("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("different source", result.stdout + result.stderr)
        self.assertNotEqual(self.run_tool("create", "--commit", "b" * 40, "source.bundle").returncode, 0)

    def test_public_root_is_rejected(self):
        self.root.chmod(0o755)
        self.assertNotEqual(self.run_tool("create", "--commit", "a" * 40, "source.bundle").returncode, 0)
        self.assertFalse(self.manifest.exists())

    def test_symlink_traversal_and_duplicate_files_are_rejected(self):
        (self.root / "linked").symlink_to(self.root / "source.bundle")
        for names in (("linked",), ("../source.bundle",), ("source.bundle", "source.bundle")):
            result = self.run_tool("create", "--commit", "a" * 40, *names)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.manifest.exists())
