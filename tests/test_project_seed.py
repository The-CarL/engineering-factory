"""Offline local-Git isolation and collision tests for instruction seeding."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory seed ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(self.base),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_TERMINAL_PROMPT": "0"}
        self.factory = self.base / "factory"
        (self.factory / "scripts").mkdir(parents=True)
        (self.factory / "standards").mkdir()
        shutil.copyfile(SOURCE / "scripts/seed-project.py", self.factory / "scripts/seed-project.py")
        shutil.copyfile(SOURCE / "standards/application-design.md", self.factory / "standards/application-design.md")
        shutil.copyfile(SOURCE / "standards/conversational-delivery.md", self.factory / "standards/conversational-delivery.md")
        shutil.copytree(SOURCE / "templates", self.factory / "templates")
        (self.factory / ".gitignore").write_text("workspaces/\n__pycache__/\n")
        self.initialize(self.factory, "https://github.com/factory-owner/engineering-harness.git")
        self.local_git(self.factory, "add", ".")
        self.local_git(self.factory, "commit", "--quiet", "-m", "committed factory fixture")
        self.revision = self.local_git(self.factory, "rev-parse", "HEAD").stdout.strip()
        self.app = self.base / "independent app"
        self.app.mkdir()
        self.initialize(self.app, "https://github.com/fixture-owner/new-app.git")
        (self.app / "existing.txt").write_text("preserve user work")
        self.local_git(self.app, "add", "existing.txt")
        self.local_git(self.app, "commit", "--quiet", "-m", "app fixture")
        self.head = self.local_git(self.app, "rev-parse", "HEAD").stdout

    def local_git(self, path, *args):
        return subprocess.run([GIT, "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                              env=self.env, text=True, capture_output=True, check=True)

    def initialize(self, path, origin):
        self.local_git(path, "init", "--quiet")
        self.local_git(path, "remote", "add", "origin", origin)

    def run_seed(self, *extra, path=None, repo="fixture-owner/new-app", confirm=True):
        args = [sys.executable, str(self.factory / "scripts/seed-project.py"), "--app", str(path or self.app), "--repo", repo]
        if confirm:
            args += ["--confirm", repo]
        return subprocess.run(args + list(extra), env=self.env, capture_output=True, text=True)

    def assert_outputs_absent(self, path=None):
        self.assertTrue(all(not (path or self.app).joinpath(name).exists() for name in ("AGENTS.md", "CLAUDE.md", "ENGINEERING.md")))

    def test_independent_repo_seed_records_target_and_committed_factory_source(self):
        result = self.run_seed()
        self.assertEqual(result.returncode, 0, result.stderr)
        agent = (self.app / "AGENTS.md").read_text()
        engineering = (self.app / "ENGINEERING.md").read_text()
        self.assertIn("fixture-owner/new-app", agent)
        self.assertIn("https://github.com/fixture-owner/new-app.git", agent)
        self.assertIn(self.revision, agent)
        self.assertIn("/blob/" + self.revision + "/standards/application-design.md", engineering)
        self.assertTrue((self.app / "CLAUDE.md").read_text().startswith("@AGENTS.md\n"))
        self.assertNotIn("{{", agent + engineering)
        self.assertEqual(self.local_git(self.app, "rev-parse", "HEAD").stdout, self.head)
        self.assertEqual({path.name for path in self.app.iterdir()}, {".git", "existing.txt", "AGENTS.md", "CLAUDE.md", "ENGINEERING.md"})

    def test_repeat_is_noop_and_dry_run_writes_nothing(self):
        self.assertEqual(self.run_seed("--dry-run", confirm=False).returncode, 0)
        self.assert_outputs_absent()
        self.assertEqual(self.run_seed(confirm=False).returncode, 1)
        self.assert_outputs_absent()
        self.assertEqual(self.run_seed().returncode, 0)
        before = {name: ((self.app / name).read_bytes(), (self.app / name).stat().st_mtime_ns) for name in ("AGENTS.md", "CLAUDE.md", "ENGINEERING.md", "existing.txt")}
        self.assertEqual(self.run_seed().returncode, 0)
        self.assertEqual(self.run_seed("--dry-run").returncode, 0)
        self.assertEqual(before, {name: ((self.app / name).read_bytes(), (self.app / name).stat().st_mtime_ns) for name in before})

    def test_foreign_push_or_credential_origin_rejects_without_outputs(self):
        for origin in ("https://github.com/other/repo.git", "https://user:private-token@github.com/fixture-owner/new-app.git", "https://github.com/fixture-owner/new-app.git?token=private"):
            self.local_git(self.app, "remote", "set-url", "origin", origin)
            result = self.run_seed()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("private-token", result.stderr)
            self.assert_outputs_absent()
        self.local_git(self.app, "remote", "set-url", "origin", "https://github.com/fixture-owner/new-app.git")
        self.local_git(self.app, "remote", "set-url", "--push", "origin", "https://github.com/other/repo.git")
        self.assertNotEqual(self.run_seed().returncode, 0)
        self.assert_outputs_absent()

    def test_factory_root_or_another_factory_clone_is_rejected(self):
        self.assertNotEqual(self.run_seed(path=self.factory, repo="factory-owner/engineering-harness").returncode, 0)
        self.local_git(self.app, "remote", "set-url", "origin", "https://github.com/factory-owner/engineering-harness.git")
        self.assertNotEqual(self.run_seed(repo="factory-owner/engineering-harness").returncode, 0)
        self.assert_outputs_absent()

    def test_linked_worktree_and_subdirectory_rejected(self):
        worktree = self.base / "linked app"
        self.local_git(self.app, "worktree", "add", "--quiet", "-b", "fixture-linked", str(worktree))
        self.assertNotEqual(self.run_seed(path=worktree).returncode, 0)
        self.assert_outputs_absent(worktree)
        subdir = self.app / "nested"
        subdir.mkdir()
        self.assertNotEqual(self.run_seed(path=subdir).returncode, 0)
        self.assert_outputs_absent(subdir)

    def test_symlink_app_ancestor_output_and_path_escape_rejected(self):
        linked = self.base / "linked"
        linked.symlink_to(self.app, target_is_directory=True)
        self.assertNotEqual(self.run_seed(path=linked).returncode, 0)
        parent_link = self.base / "parent-link"
        parent_link.symlink_to(self.base, target_is_directory=True)
        self.assertNotEqual(self.run_seed(path=parent_link / self.app.name).returncode, 0)
        self.assertNotEqual(self.run_seed(path=self.app / ".." / self.app.name).returncode, 0)
        untouched = self.base / "untouched"
        untouched.write_text("keep")
        (self.app / "ENGINEERING.md").symlink_to(untouched)
        self.assertNotEqual(self.run_seed().returncode, 0)
        self.assertFalse((self.app / "AGENTS.md").exists())
        self.assertEqual(untouched.read_text(), "keep")

    def test_partial_output_collision_preserves_all_existing_files(self):
        existing = self.app / "ENGINEERING.md"
        existing.write_text("user contract")
        before = existing.stat().st_mtime_ns
        self.assertNotEqual(self.run_seed().returncode, 0)
        self.assertNotEqual(self.run_seed("--dry-run").returncode, 0)
        self.assertEqual(existing.read_text(), "user contract")
        self.assertEqual(existing.stat().st_mtime_ns, before)
        self.assertFalse((self.app / "AGENTS.md").exists())
        self.assertFalse((self.app / "CLAUDE.md").exists())
        self.assertEqual((self.app / "existing.txt").read_text(), "preserve user work")

    def test_dirty_factory_contributor_cannot_claim_committed_revision(self):
        template = self.factory / "templates/project/AGENTS.md.tmpl"
        template.write_text(template.read_text() + "\nchanged\n")
        self.assertNotEqual(self.run_seed().returncode, 0)
        self.assert_outputs_absent()

    def test_dirty_or_missing_delivery_standard_cannot_claim_committed_guidance(self):
        standard = self.factory / "standards/conversational-delivery.md"
        original = standard.read_text()
        for content in (original + "\nUncommitted delivery change\n", None):
            with self.subTest(content="missing" if content is None else "modified"):
                if content is None:
                    standard.unlink()
                else:
                    standard.write_text(content)
                self.assertNotEqual(self.run_seed().returncode, 0)
                self.assertNotEqual(self.run_seed("--dry-run").returncode, 0)
                self.assert_outputs_absent()
                self.assertEqual((self.app / "existing.txt").read_text(), "preserve user work")
                standard.write_text(original)

    def test_nested_apps_require_ignored_workspace_and_have_no_factory_changes(self):
        for name, accepted in (("app-not-ignored", False), ("workspaces/fixture-owner/app", True)):
            app = self.factory / name
            app.mkdir(parents=True)
            self.initialize(app, "https://github.com/fixture-owner/new-app.git")
            result = self.run_seed(path=app)
            self.assertEqual(result.returncode, 0 if accepted else 1, result.stderr)
            if not accepted:
                self.assert_outputs_absent(app)
        self.assertEqual(self.local_git(self.factory, "rev-parse", "HEAD").stdout.strip(), self.revision)

    def test_interrupted_staging_write_leaves_no_partial_instruction_outputs(self):
        spec = importlib.util.spec_from_file_location("seed_fixture", self.factory / "scripts/seed-project.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = Path.write_bytes
        def interrupted(path, content):
            original(path, content[:7])
            raise OSError("synthetic write interruption")
        with patch.object(Path, "write_bytes", interrupted):
            with self.assertRaises(module.SeedError):
                module.seed(self.app, "fixture-owner/new-app", "fixture-owner/new-app")
        self.assert_outputs_absent()
        self.assertFalse(list(self.app.glob(".factory-seed-*")))
        self.assertEqual((self.app / "existing.txt").read_text(), "preserve user work")
