"""Readable provenance from real isolated Git, with legacy recovery and no provider writes."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import context
from provider import METADATA, ProviderError, preserve_creation_metadata, validate_metadata_shape

spec = importlib.util.spec_from_file_location('provenance_metadata', ROOT / 'scripts/provenance-metadata.py')
provenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provenance)


class ReadableProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='factory readable ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.app = self.root / 'app'
        self.app.mkdir()
        self.env = dict(PATH=os.environ.get('PATH', os.defpath), GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull, FACTORY_PRIVATE_ROOT=str(self.root))
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        self.git('init', '--quiet')
        self.git('remote', 'add', 'origin', 'https://github.com/fixture-owner/hello-cloud.git')
        self.git('config', 'user.name', 'Carlo Example')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.app / 'app.txt').write_text('first version')
        self.git('add', 'app.txt')
        self.git('commit', '--quiet', '-m', 'first version')
        self.git('branch', '-M', 'feat/hello-world')
        self.commit = self.git('rev-parse', 'HEAD')
        self.meta = dict(factoryProjectId=str(uuid.uuid4()), factoryEnvironment='development',
            factoryOwner='carlo', factoryManagedBy='engineering-factory',
            factorySourceRepo='fixture-owner/hello-cloud', factorySourceCommit=self.commit,
            factoryCreatedBy='factory-runner', factoryCreatedAt=datetime.now(timezone.utc).isoformat(),
            factoryCreationRunId='first-run', factoryLastRunId='first-run',
            factoryLastSourceCommit=self.commit, factoryProvenanceVersion='1', factoryExpiresAt='none')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.app), *args], env=self.env,
                              check=True, capture_output=True, text=True).stdout.rstrip('\n')

    def prepare(self, **changes):
        args = dict(meta=self.meta, source=self.app, project_name='Hello Cloud', mode='create')
        args.update(changes)
        return provenance.prepare(**args)

    def test_create_uses_repo_branch_and_git_author_without_changing_executor(self):
        meta, tags = self.prepare()
        self.assertEqual(meta['factoryRepoName'], 'hello-cloud')
        self.assertEqual(meta['factorySourceBranch'], 'feat/hello-world')
        self.assertEqual(meta['factorySourceAuthor'], 'Carlo Example')
        self.assertEqual(meta['factoryCreatedBy'], 'factory-runner')
        self.assertEqual(tags['factory:project-name'], 'Hello Cloud')
        self.assertEqual(tags['factory:source-repo'], 'fixture-owner/hello-cloud')
        self.assertEqual(tags['factory:last-source-author'], 'Carlo Example')
        self.assertEqual(tags['factory:s'], self.meta['factoryProjectId'] + '-development')
        self.assertFalse(any('@' in value for value in meta.values()))
        self.assertEqual({key: meta[key] for key in METADATA}, self.meta)
        context.metadata(meta)

    def test_update_keeps_original_branch_author_and_changes_latest_only(self):
        original, _ = self.prepare()
        self.git('checkout', '--quiet', '-b', 'fix/second-version')
        self.git('config', 'user.name', 'Jamie Builder')
        (self.app / 'app.txt').write_text('second version')
        self.git('add', 'app.txt')
        self.git('commit', '--quiet', '-m', 'second version')
        update = dict(original, factoryLastSourceCommit=self.git('rev-parse', 'HEAD'), factoryLastRunId='second-run')
        current, _ = self.prepare(meta=update, mode='update')
        self.assertEqual(current['factorySourceBranch'], 'feat/hello-world')
        self.assertEqual(current['factorySourceAuthor'], 'Carlo Example')
        self.assertEqual(current['factoryLastSourceBranch'], 'fix/second-version')
        self.assertEqual(current['factoryLastSourceAuthor'], 'Jamie Builder')
        preserve_creation_metadata(current, original)
        for key in ('factorySourceBranch', 'factorySourceAuthor', 'factoryRepoName'):
            with self.subTest(key=key), self.assertRaises(ProviderError):
                preserve_creation_metadata(dict(current, **{key: 'rewritten'}), original)
        with self.assertRaises(ProviderError):
            preserve_creation_metadata({key: current[key] for key in METADATA}, original)

    def test_legacy_metadata_remains_valid_and_backfill_does_not_invent_creation_labels(self):
        context.metadata(self.meta)
        enriched, _ = self.prepare(mode='update')
        self.assertEqual(enriched['factorySourceBranch'], 'unknown')
        self.assertEqual(enriched['factorySourceAuthor'], 'unknown')
        self.assertEqual(enriched['factoryLastSourceAuthor'], 'Carlo Example')
        preserve_creation_metadata(enriched, self.meta)

    def test_closed_extension_rejects_partial_labels_email_urls_controls_and_wrong_repo(self):
        valid, _ = self.prepare()
        invalid = [dict(self.meta, factoryProjectName='Hello Cloud'), dict(valid, unexpected='extra'),
                   dict(valid, factoryRepoName='unrelated')]
        invalid += [dict(valid, factorySourceAuthor=value) for value in
                    ('name@example.invalid', 'https://example.test', 'Name\nOther', ' Name', 'a' * 257)]
        for data in invalid:
            with self.subTest(keys=sorted(data)), self.assertRaises(ProviderError):
                validate_metadata_shape(data)

    def test_incompatible_labels_require_explicit_alias_and_secrets_are_never_emitted(self):
        self.git('branch', '-m', 'feat/percent%label')
        with self.assertRaises(ProviderError):
            self.prepare()
        meta, _ = self.prepare(branch_label='feat/percent-label', author_label='Carlo Example')
        self.assertEqual(meta['factorySourceBranch'], 'feat/percent-label')
        secret = uuid.uuid4().hex
        with patch.dict(os.environ, FACTORY_GITHUB_TOKEN=secret), self.assertRaises(ProviderError):
            self.prepare(project_name=secret, branch_label='feat/percent-label')

        # Distinct Git refs must not collapse through implicit Unicode normalization.
        with patch.object(provenance, 'source_facts',
                          return_value=(self.commit, 'feat/cafe\u0301', 'Carlo Example')):
            with self.assertRaises(ProviderError):
                self.prepare()
            aliased, _ = self.prepare(branch_label='feat/cafe')
            self.assertEqual(aliased['factorySourceBranch'], 'feat/cafe')

    def test_wrong_source_dirty_work_and_mismatched_commit_fail_before_output(self):
        with self.assertRaises(ProviderError):
            self.prepare(meta=dict(self.meta, factoryLastSourceCommit='a' * 40))
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/app.git')
        with self.assertRaises(ProviderError):
            self.prepare()
        self.git('remote', 'set-url', 'origin', 'https://github.com/fixture-owner/hello-cloud.git')
        (self.app / 'app.txt').write_text('uncommitted work')
        with self.assertRaises(ProviderError):
            self.prepare()
        self.assertEqual((self.app / 'app.txt').read_text(), 'uncommitted work')

    def test_detached_head_is_labeled_honestly(self):
        self.git('checkout', '--quiet', '--detach', 'HEAD')
        meta, _ = self.prepare()
        self.assertEqual(meta['factorySourceBranch'], 'detached')
        self.assertEqual(meta['factorySourceCommit'], self.commit)

    def test_private_payload_files_match_and_existing_output_is_preserved(self):
        source = self.root / 'input.json'
        source.write_text(json.dumps(self.meta))
        source.chmod(0o600)
        output = self.root / 'prepared'
        args = argparse.Namespace(input=str(source), source=self.app, project_name='Hello Cloud',
                                  mode='create', branch_label=None, author_label=None, output=str(output))
        with redirect_stdout(io.StringIO()) as messages:
            provenance.execute(args)
        self.assertNotIn('Carlo Example', messages.getvalue())
        meta = json.loads((output / 'provenance.json').read_text())
        tags = json.loads((output / 'aws-tag-map.json').read_text())
        self.assertEqual({entry['Key']: entry['Value'] for entry in json.loads((output / 'aws-tags.json').read_text())}, tags)
        self.assertEqual(tags['factory:source-author'], meta['factorySourceAuthor'])
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        before = {file.name: file.read_bytes() for file in output.iterdir()}
        self.assertTrue(all(file.stat().st_mode & 0o777 == 0o600 for file in output.iterdir()))
        with self.assertRaises(ProviderError):
            provenance.execute(args)
        self.assertEqual(before, {file.name: file.read_bytes() for file in output.iterdir()})


if __name__ == '__main__':
    unittest.main()
