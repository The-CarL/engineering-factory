"""Project-owned registry flows using real isolated Git and synthetic provider identity."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import context
from provider import ProviderError
from runtime import Operation, base_env, digest

def wrapper(name):
    spec = importlib.util.spec_from_file_location('context_' + name, ROOT / 'scripts/runtime' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


github, aws = wrapper('github'), wrapper('aws')
project_cli = wrapper('project')


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git, self.real_run = shutil.which('git'), subprocess.run
        self.tools = {name: '/verified/' + name for name in ('aws', 'gh', 'python', 'node', 'npm', 'vercel')}
        self.tools['git'] = self.git
        self.token, self.target = uuid.uuid4().hex, 'fixture-owner/app'
        self.private, self.principal, self.membership = True, 'fixture-owner', 'active'
        self.published, self.calls, self.push_failure = [], [], None
        self.remote, self.app = self.root / 'app.git', self.root / 'app'
        self.git_run('init', '--bare', '--initial-branch=main', str(self.remote))
        self.git_run('init', '--initial-branch=main', str(self.app))
        self.git_run('-C', str(self.app), 'remote', 'add', 'origin', 'https://github.com/' + self.target + '.git')
        (self.app / 'source.txt').write_text('fixture application')
        self.git_run('-C', str(self.app), 'add', '.')
        self.git_run('-C', str(self.app), 'commit', '-m', 'fixture')
        self.git_run('-C', str(self.app), 'push', str(self.remote), 'HEAD:main')
        env = dict(FACTORY_PRIVATE_ROOT=str(self.root), FACTORY_GITHUB_OWNER='fixture-owner',
                   FACTORY_SOURCE_REPOSITORY='fixture-owner/factory', FACTORY_SOURCE_REVISION='a' * 40,
                   FACTORY_GITHUB_CREDENTIAL_SOURCE='factory-token', FACTORY_GITHUB_TOKEN=self.token,
                   GH_TOKEN='ambient-must-not-win')
        self.environ = patch.dict(os.environ, env, clear=True)
        self.environ.start(); self.addCleanup(self.environ.stop)
        mocked = patch.object(context.subprocess, 'run', side_effect=self.process)
        mocked.start(); self.addCleanup(mocked.stop)
        mocked = patch.object(context, 'run', side_effect=self.provider)
        mocked.start(); self.addCleanup(mocked.stop)

    def git_run(self, *args):
        result = self.real_run([self.git, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args],
                               env=base_env('/tmp'), capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def process(self, command, **kwargs):
        command = list(command)
        network_push = command[0] == self.git and 'push' in command and 'origin' in command
        if network_push:
            self.published.append(command.copy())
            if self.push_failure == 'before':
                return subprocess.CompletedProcess(command, 1, b'', b'fixture unavailable')
        clone = command[0] == self.git and 'clone' in command
        if command[0] == self.git:
            if any(value in command for value in ('fetch', 'push', 'ls-remote')) and 'origin' in command:
                command[command.index('origin')] = str(self.remote)
            if clone:
                url = 'https://github.com/' + self.target + '.git'
                self.assertIn(url, command)
                command[command.index(url)] = str(self.remote)
        result = self.real_run(command, **kwargs)
        if clone and result.returncode == 0:
            self.git_run('-C', command[-1], 'remote', 'set-url', 'origin', 'https://github.com/' + self.target + '.git')
        if network_push and self.push_failure == 'after':
            return subprocess.CompletedProcess(command, 1, b'', b'fixture lost response')
        return result

    def provider(self, command, env, provider, **kwargs):
        self.assertEqual(env.get('GH_TOKEN'), self.token)
        self.assertNotIn('FACTORY_GITHUB_TOKEN', env)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
        if command[0] == self.git:
            result = self.process(command, env=env, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        endpoint = command[-1]
        self.calls.append(endpoint)
        if endpoint == 'user':
            return json.dumps(dict(login=self.principal)).encode()
        if endpoint == 'user/memberships/orgs/fixture-owner':
            return json.dumps(dict(state=self.membership, organization=dict(login='fixture-owner'))).encode()
        if endpoint == 'repos/' + self.target:
            return json.dumps(dict(full_name=self.target, private=self.private, archived=False)).encode()
        raise ProviderError('Unknown fixture repository; absent or inaccessible')

    def initialize(self):
        data = context.checkpoint(self.target, self.app, initialize=True, environment='development', tools=self.tools)
        os.environ.update(context.values(data, self.app))
        return data

    def delivery(self):
        self.git_run('-C', str(self.app), 'add', '--', '.factory')
        self.git_run('-C', str(self.app), 'commit', '-m', 'Register project delivery')
        context.reconcile(self.tools, self.target, self.app)

    def journal(self, name='operations/write.jsonl', state='complete'):
        path = self.root / name
        path.parent.mkdir(mode=0o700, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        entries = [dict(time=now, state='intent', provider='AWS', source='a' * 40, request_sha256='b' * 64)]
        if state == 'complete':
            entries.append(dict(time=now, state=state, response_sha256='c' * 64, size=12))
        else:
            entries.append(dict(time=now, state=state, detail='Reconcile provider state before another mutation'))
        path.write_bytes(b''.join(json.dumps(event).encode() + b'\n' for event in entries))
        path.chmod(0o600)
        return path

    def fresh(self, branch=None):
        fresh = self.root / 'fresh'
        fresh.mkdir(mode=0o700)
        os.environ['FACTORY_PRIVATE_ROOT'] = str(fresh)
        os.environ.pop('FACTORY_PROJECT_APP', None)
        app = fresh / 'app'
        result = context.restore(self.target, app, self.tools, branch)
        return fresh, app, result

    def test_dns_zone_pair_persists_in_app_registry_and_restores_without_global_discovery(self):
        zone = dict(FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE', FACTORY_AWS_DNS_ZONE_NAME='example.test')
        os.environ.update(zone)
        data = self.initialize()
        self.assertTrue(all(data['config'].get(key) == value for key, value in zone.items()))
        self.delivery()
        for key in zone:
            os.environ.pop(key)
        _, _, restored = self.fresh()
        self.assertTrue(all(restored.get(key) == value for key, value in zone.items()))
        self.assertFalse(any('route53' in endpoint for endpoint in self.calls))

    def test_registration_batches_same_app_delivery_without_staging_dirty_code(self):
        (self.app / 'source.txt').write_text('preserve dirty source')
        before = self.git_run('-C', str(self.app), 'rev-parse', 'HEAD')
        initial = self.initialize()
        self.assertEqual(initial['repository'], self.target)
        self.assertEqual(initial['factory_source_repository'], 'fixture-owner/factory')
        self.assertEqual(self.git_run('-C', str(self.app), 'diff', '--cached'), b'')
        self.assertEqual(self.git_run('-C', str(self.app), 'rev-parse', 'HEAD'), before)
        self.assertFalse(self.published)
        self.delivery()
        self.assertEqual(len(self.published), 1)
        self.assertEqual((self.app / 'source.txt').read_text(), 'preserve dirty source')
        self.assertEqual(self.git_run('--git-dir=' + str(self.remote), 'show', 'main:source.txt'), b'fixture application')
        self.assertTrue(all('state' not in endpoint for endpoint in self.calls))

    def test_operation_queues_locally_then_checkpoint_and_fresh_clone_restore_exact_bytes(self):
        initial = self.initialize()
        record_path, output = self.root / 'operation.jsonl', self.root / 'raw.json'
        with patch.object(context, 'load', return_value=self.tools), redirect_stdout(io.StringIO()):
            operation = Operation(record_path, output, 'AWS', b'request must never enter Git')
            operation.finish(b'{"private_response":"not registered"}')
        local = json.loads((self.app / '.factory/project.json').read_bytes())
        self.assertEqual(local['artifacts'], {})
        self.assertEqual(set(context.pending(initial)), {'operation.jsonl'})
        self.assertFalse(self.published)
        context.checkpoint(self.target, self.app, tools=self.tools)
        self.assertEqual(context.pending(initial), {})
        self.delivery()
        expected = record_path.read_bytes()
        fresh, app, selected = self.fresh()
        self.assertEqual(selected['FACTORY_PROJECT_ID'], initial['project_id'])
        self.assertEqual((fresh / 'operation.jsonl').read_bytes(), expected)
        self.assertEqual((fresh / 'operation.jsonl').stat().st_mode & 0o777, 0o600)
        self.assertFalse((app / '.factory/artifacts/raw.json').exists())
        self.assertNotIn(b'private_response', expected)
        self.assertNotIn(b'request must never enter Git', expected)

    def test_public_app_minimal_registry_and_confidential_export_stays_local(self):
        self.private = False
        os.environ.update(FACTORY_AWS_ACCOUNT_ID='111122223333', FACTORY_VERCEL_TEAM_ID='team_fixture')
        initial = self.initialize()
        self.assertEqual(initial['publication'], 'public-minimal')
        self.assertEqual(set(initial['config']), {'FACTORY_GITHUB_OWNER'})
        original = (self.app / '.factory/project.json').read_bytes()
        path = self.journal()
        with patch.object(context, 'load', return_value=self.tools):
            context.automatic(path)
        with self.assertRaisesRegex(ProviderError, 'Public app confidential export blocked'):
            context.checkpoint(self.target, self.app, tools=self.tools)
        self.assertEqual((self.app / '.factory/project.json').read_bytes(), original)
        self.assertEqual(set(context.pending(initial)), {'operations/write.jsonl'})
        self.assertFalse((self.app / '.factory/artifacts').exists())
        self.delivery()  # Only the safe registry is committed; pending evidence stays private.
        self.assertNotIn(b'111122223333', self.git_run('--git-dir=' + str(self.remote), 'show', 'main:.factory/project.json'))

    def test_visibility_change_and_public_history_block_confidential_publication(self):
        os.environ['FACTORY_AWS_ACCOUNT_ID'] = '111122223333'
        initial = self.initialize()
        self.delivery()
        self.private = False
        with self.assertRaises(ProviderError):
            context.publication(self.tools, self.target, self.app)
        initial.update(publication='public-minimal', config={'FACTORY_GITHUB_OWNER': 'fixture-owner'})
        (self.app / '.factory/project.json').write_text(json.dumps(initial))
        self.git_run('-C', str(self.app), 'add', '.factory')
        self.git_run('-C', str(self.app), 'commit', '-m', 'Sanitize latest only')
        with self.assertRaises(ProviderError):
            context.publication(self.tools, self.target, self.app)
        self.assertEqual(len(self.published), 1)

    def test_feature_branch_restores_only_when_explicit_and_preserves_dirty_existing_app(self):
        self.initialize()
        self.git_run('-C', str(self.app), 'switch', '-c', 'feature')
        context.checkpoint(self.target, self.app, tools=self.tools)
        self.delivery()
        (self.app / 'source.txt').write_text('uncommitted feature')
        context.restore(self.target, self.app, self.tools)
        self.assertEqual(self.git_run('-C', str(self.app), 'branch', '--show-current').strip(), b'feature')
        self.assertEqual((self.app / 'source.txt').read_text(), 'uncommitted feature')
        _, app, _ = self.fresh('feature')
        self.assertEqual(self.git_run('-C', str(app), 'branch', '--show-current').strip(), b'feature')

    def test_init_before_initial_commit_and_no_remote_default_branch_record(self):
        empty = self.root / 'empty'
        self.git_run('init', '--initial-branch=feature', str(empty))
        self.git_run('-C', str(empty), 'remote', 'add', 'origin', 'https://github.com/' + self.target + '.git')
        data = context.checkpoint(self.target, empty, initialize=True, environment='development', tools=self.tools)
        self.assertIsNone(data['source_commit'])
        self.assertEqual(data['branch'], 'feature')
        self.assertFalse(self.published)

    def test_existing_repo_reads_before_registry_and_manual_creation_blocks(self):
        os.environ.update(FACTORY_PROJECT_REPOSITORY=self.target, FACTORY_PROJECT_APP=str(self.app))
        body = self.root / 'create.json'; body.write_text('{"name":"app","private":true}'); body.chmod(0o600)
        calls = []
        def response(command, env, provider, **kwargs):
            calls.append(command)
            if command[-1] == 'user': return b'{"login":"fixture-owner"}'
            return b'{"full_name":"fixture-owner/app","private":true}'
        args = argparse.Namespace(mode='gh', repo=self.target, visibility='private',
            command=['api', 'user/repos', '--method', 'POST', '--input', str(body)],
            record=str(self.root / 'create.jsonl'), output=str(self.root / 'result.json'))
        with patch.object(github, 'load', return_value=self.tools), patch.object(github, 'run', side_effect=response), \
             patch.object(context, 'preflight') as preflight, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ProviderError, 'Repository creation is manual'):
                github.execute(args)
            self.assertEqual(calls, [])
            args.command, args.record, args.output = ['api', 'repos/' + self.target], str(self.root / 'read.jsonl'), str(self.root / 'read.json')
            github.execute(args)
        preflight.assert_not_called()
        self.assertFalse(any('user/repos' in command for command in calls))
        self.assertTrue(any('repos/' + self.target in command for command in calls))
        self.assertFalse(self.published)

    def test_checkpoint_command_registers_explicit_pre_registration_journal_without_git_commit(self):
        self.initialize()
        path = self.journal('bootstrap.jsonl')
        before = self.git_run('-C', str(self.app), 'rev-parse', 'HEAD')
        with patch.object(project_cli, 'load', return_value=self.tools), patch.object(project_cli, 'write_environment'), \
             patch.object(sys, 'argv', ['factory-project', 'checkpoint', '--repo', self.target, '--app', str(self.app), '--journal', str(path)]), \
             redirect_stdout(io.StringIO()):
            project_cli.main()
        self.assertEqual((self.app / '.factory/artifacts/bootstrap.jsonl').read_bytes(), path.read_bytes())
        self.assertEqual(self.git_run('-C', str(self.app), 'rev-parse', 'HEAD'), before)
        self.assertFalse(self.published)

    def test_unknown_repo_missing_registry_and_cross_project_registry_are_not_adopted(self):
        with self.assertRaises(ProviderError): context.restore('fixture-owner/unknown', self.root / 'unknown', self.tools)
        self.assertFalse((self.root / 'unknown').exists())
        with self.assertRaisesRegex(ProviderError, 'no registered project'): context.restore(self.target, self.app, self.tools)
        data = self.initialize(); data['repository'] = 'fixture-owner/other'
        (self.app / '.factory/project.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ProviderError, 'another app'): context.restore(self.target, self.app, self.tools)
        self.assertNotIn('repos/fixture-owner/other', self.calls)

    def test_stale_central_configuration_fails_without_any_remote_use(self):
        for key in ('FACTORY_CONTEXT_REPOSITORY', 'FACTORY_CONTEXT_DIRECTORY'):
            os.environ[key] = 'stale'
            with self.assertRaisesRegex(ProviderError, 'Central context storage'): self.initialize()
            del os.environ[key]
        self.assertFalse(self.calls)

    def test_wrong_identity_origin_target_conflict_and_symlinks_preserve_files(self):
        self.principal, self.membership = 'fixture-agent', 'pending'
        with self.assertRaises(ProviderError): self.initialize()
        self.membership = 'active'; self.initialize()
        self.git_run('-C', str(self.app), 'remote', 'set-url', '--push', 'origin', 'https://github.com/fixture-owner/other.git')
        with self.assertRaises(ProviderError): context.restore(self.target, self.app, self.tools)
        self.git_run('-C', str(self.app), 'remote', 'set-url', '--push', 'origin', 'https://github.com/' + self.target + '.git')
        os.environ['FACTORY_PROJECT_ID'] = str(uuid.uuid4())
        with self.assertRaises(ProviderError): context.restore(self.target, self.app, self.tools)
        os.environ.pop('FACTORY_PROJECT_ID')
        link = self.app / '.factory/linked'; link.symlink_to(self.root)
        with self.assertRaises(ProviderError): context.restore(self.target, self.app, self.tools)
        self.assertTrue(link.is_symlink())

    def test_pending_unknown_outcomes_restore_without_replaying_provider_work(self):
        self.initialize()
        path = self.journal(state='failed-or-unknown')
        context.checkpoint(self.target, self.app, [(path, 'journal')], tools=self.tools)
        self.delivery()
        error = io.StringIO()
        with redirect_stderr(error): fresh, _, _ = self.fresh()
        self.assertEqual((fresh / 'operations/write.jsonl').read_bytes(), path.read_bytes())
        self.assertIn('reconcile', error.getvalue())
        self.assertTrue(all(endpoint == 'user' or endpoint.startswith('repos/') for endpoint in self.calls))

    def test_changed_pending_evidence_and_arbitrary_fields_are_rejected(self):
        initial = self.initialize(); path = self.journal()
        with patch.object(context, 'load', return_value=self.tools): context.automatic(path)
        path.write_bytes(b'changed raw data')
        with self.assertRaises(ProviderError): context.checkpoint(self.target, self.app, tools=self.tools)
        self.assertEqual((self.app / '.factory/project.json').read_bytes(), json.dumps(initial, sort_keys=True).encode() + b'\n')
        for content in (self.token.encode(), b'private notes', b'{"state":"complete","response":"raw"}\n'):
            path.write_bytes(content)
            with self.assertRaises((ProviderError, ValueError)): context.journal(path.read_bytes(), initial['project_id'])
        for name in ('../escape', '/absolute', 'operations/.git/config'):
            with self.assertRaises(ProviderError): context.relative(name)

    def test_unknown_push_result_reconcile_reads_hash_then_does_not_duplicate_push(self):
        self.initialize()
        self.git_run('-C', str(self.app), 'add', '.factory')
        self.git_run('-C', str(self.app), 'commit', '-m', 'Registry')
        self.push_failure = 'after'
        with self.assertRaises(ProviderError): context.reconcile(self.tools, self.target, self.app)
        self.assertEqual(len(self.published), 1)
        self.push_failure = None
        context.reconcile(self.tools, self.target, self.app)
        self.assertEqual(len(self.published), 1)
        self.assertTrue(all('--force' not in command for command in self.published))

    def test_factory_git_push_preserves_dirty_feature_and_blocks_confidential_committed_registry(self):
        self.private = False
        initial = self.initialize()
        self.git_run('-C', str(self.app), 'switch', '-c', 'feature')
        context.checkpoint(self.target, self.app, tools=self.tools)
        self.git_run('-C', str(self.app), 'add', '.factory')
        self.git_run('-C', str(self.app), 'commit', '-m', 'Feature registry')
        (self.app / 'source.txt').write_text('dirty source stays local')
        args = argparse.Namespace(mode='git', repo=self.target, app=str(self.app), branch='feature', action='push',
            command=[], visibility='public', record=str(self.root / 'push.jsonl'), output=str(self.root / 'push-result.txt'))
        with patch.object(github, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(github, 'run', side_effect=self.provider), redirect_stdout(io.StringIO()):
            github.execute(args)
        self.assertEqual((self.app / 'source.txt').read_text(), 'dirty source stays local')
        self.assertEqual(self.git_run('-C', str(self.app), 'branch', '--show-current').strip(), b'feature')
        self.assertEqual(len(self.published), 1)
        safe = (self.app / '.factory/project.json').read_bytes()
        bad = dict(initial, publication='private', config=dict(initial['config'], FACTORY_AWS_ACCOUNT_ID='111122223333'))
        (self.app / '.factory/project.json').write_text(json.dumps(bad))
        self.git_run('-C', str(self.app), 'add', '.factory')
        self.git_run('-C', str(self.app), 'commit', '-m', 'Confidential fixture')
        (self.app / '.factory/project.json').write_bytes(safe)
        args.record, args.output = str(self.root / 'blocked.jsonl'), str(self.root / 'blocked.txt')
        with patch.object(github, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(github, 'run', side_effect=self.provider), self.assertRaises(ProviderError):
            github.execute(args)
        self.assertEqual(len(self.published), 1)

    def test_linked_worktree_publishes_its_own_branch_with_public_history_checks(self):
        self.private = False
        self.initialize()
        self.delivery()
        work = self.root / 'feature-worktree'
        self.git_run('-C', str(self.app), 'worktree', 'add', '-b', 'feature', str(work))
        self.assertTrue((work / '.git').is_file())
        os.environ['FACTORY_PROJECT_APP'] = str(work)
        context.checkpoint(self.target, work, tools=self.tools)
        self.git_run('-C', str(work), 'add', '.factory')
        self.git_run('-C', str(work), 'commit', '-m', 'Feature delivery')
        args = argparse.Namespace(mode='git', repo=self.target, visibility='public', command=[],
            action='push', app=str(work), branch='feature', record=str(self.root / 'push.jsonl'), output=str(self.root / 'push.txt'))
        with patch.object(github, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(github, 'run', side_effect=self.provider), redirect_stdout(io.StringIO()):
            github.execute(args)
        self.assertEqual(self.git_run('--git-dir=' + str(self.remote), 'rev-parse', 'feature').strip(),
                         self.git_run('-C', str(work), 'rev-parse', 'HEAD').strip())
        self.git_run('-C', str(self.app), 'config', 'extensions.worktreeConfig', 'true')
        self.git_run('-C', str(work), 'config', '--worktree', 'http.https://github.com/.extraheader', 'blocked')
        with self.assertRaises(ProviderError):
            context.app_identity(self.tools, work, self.target)

    def test_linked_worktree_rejects_shared_alternates_and_wrong_origin(self):
        work = self.root / 'feature-worktree'
        self.git_run('-C', str(self.app), 'worktree', 'add', '-b', 'feature', str(work))
        alternate = self.app / '.git/objects/info/alternates'
        alternate.parent.mkdir(parents=True, exist_ok=True)
        alternate.write_text(str(self.remote / 'objects') + '\n')
        with self.assertRaises(ProviderError):
            context.app_identity(self.tools, work, self.target)
        alternate.unlink()
        self.git_run('-C', str(self.app), 'remote', 'set-url', 'origin', 'https://github.com/fixture-owner/other.git')
        with self.assertRaises(ProviderError):
            context.app_identity(self.tools, work, self.target)

    def test_vercel_cli_organization_pair_restores_and_conflicts_fail_closed(self):
        os.environ.update(FACTORY_VERCEL_TEAM_ID='team_fixture', VERCEL_PROJECT_ID='prj_fixture')
        initial = self.initialize()
        self.assertEqual(os.environ['VERCEL_ORG_ID'], 'team_fixture')
        self.delivery()
        for key in ('VERCEL_PROJECT_ID', 'VERCEL_ORG_ID', 'FACTORY_VERCEL_TEAM_ID'):
            os.environ.pop(key, None)
        _, app, restored = self.fresh()
        self.assertEqual(restored['VERCEL_ORG_ID'], 'team_fixture')
        with patch.dict(os.environ, VERCEL_ORG_ID='team_other'), self.assertRaises(ProviderError):
            context.values(initial, app)
        initial['config']['VERCEL_ORG_ID'] = 'team_other'
        with self.assertRaises(ProviderError):
            context.record(initial)

    def test_native_inventory_ids_round_trip_and_reject_injected_values(self):
        initial = self.initialize()
        project = initial['project_id']
        identities = [
            ('AWS', 'apigateway:stage', '$default'),
            ('AWS', 'secretsmanager:secret', 'arn:aws:secretsmanager:us-east-1:111122223333:secret:rds!cluster-fixture'),
            ('AWS', 'lambda:version', 'arn:aws:lambda:us-east-1:111122223333:function:fixture:$LATEST'),
            ('Vercel', 'domain', 'fixture.example.test'),
            ('Vercel', 'certificate', 'cert_fixture-123'),
            ('Vercel', 'project', 'prj_fixture'),
        ]
        resources = [dict(provider=provider, resource_type=kind, resource_id=identity,
            parent_id=None, backend_ref=None, run_id='fixture', source_commit='d' * 40, status='ready', ownership='managed')
            for provider, kind, identity in identities]
        data = dict(schema=1, project_id=project, environment='development', resources=resources)
        inventory = self.root / 'native-inventory.json'
        inventory.write_text(json.dumps(data)); inventory.chmod(0o600)
        context.checkpoint(self.target, self.app, [(inventory, 'inventory')], tools=self.tools)
        self.delivery()
        fresh, _, _ = self.fresh()
        self.assertEqual(json.loads((fresh / 'native-inventory.json').read_bytes()), data)
        for provider, kind, invalid in (
            ('Vercel', 'project', 'fixture.example.test'),
            ('Vercel', 'domain', 'fixture.example.test?token=hidden'),
            ('Vercel', 'domain', '*.example.test'),
            ('Vercel', 'certificate', 'https://example.test/certificate'),
            ('AWS', 'apigateway:stage', '$default\nother'),
        ):
            item = dict(resources[0], provider=provider, resource_type=kind, resource_id=invalid)
            with self.subTest(provider=provider, kind=kind, invalid=invalid), self.assertRaises(ProviderError):
                context.inventory(json.dumps(dict(data, resources=[item])).encode(), project)
        with self.assertRaises(ProviderError):
            context.inventory(json.dumps(dict(data, resources=[dict(resources[0], resource_id=self.token)])).encode(), project)

    def test_inventory_and_ownership_restore_exact_layout_and_do_not_authorize_adoption(self):
        initial = self.initialize(); project = initial['project_id']; now = datetime.now(timezone.utc).isoformat()
        meta = dict(factoryProjectId=project, factoryEnvironment='development', factoryOwner='fixture-owner',
            factoryManagedBy='engineering-factory', factorySourceRepo=self.target, factorySourceCommit='d' * 40,
            factoryCreatedBy='fixture', factoryCreatedAt=now, factoryCreationRunId='fixture-run', factoryLastRunId='fixture-run',
            factoryLastSourceCommit='d' * 40, factoryProvenanceVersion='1', factoryExpiresAt='none')
        creation = self.journal()
        events = [dict(time=now, state='intent', provider='Vercel', source='a' * 40, request_sha256='b' * 64),
            dict(time=now, state='created-resource', team='team_fixture', project='prj_fixture', name='fixture', metadata=meta),
            dict(time=now, state='complete', response_sha256='c' * 64, size=12)]
        creation.write_bytes(b''.join(json.dumps(event).encode() + b'\n' for event in events))
        owner = self.root / 'owner.json'
        owner.write_text(json.dumps(dict(schema=1, factory_project_id=project, team_id='team_fixture', project_id='prj_fixture',
            project_name='fixture', metadata=meta, creation_record='operations/write.jsonl', creation_record_sha256=digest(creation.read_bytes()))))
        owner.chmod(0o600)
        inventory = self.root / 'inventory.json'
        inventory.write_text(json.dumps(dict(schema=1, project_id=project, environment='development', resources=[dict(
            provider='AWS', resource_id='arn:aws:s3:::fixture-state', resource_type='s3:bucket', parent_id=None, backend_ref=None,
            run_id='fixture-run', source_commit='d' * 40, status='ready', ownership='external')]))); inventory.chmod(0o600)
        context.checkpoint(self.target, self.app, [(owner, 'ownership'), (inventory, 'inventory')], tools=self.tools)
        self.delivery()
        expected = {str(path.relative_to(self.root)): path.read_bytes() for path in (creation, owner, inventory)}
        fresh, _, _ = self.fresh()
        for name, data in expected.items(): self.assertEqual((fresh / name).read_bytes(), data)
        self.assertEqual(json.loads((fresh / 'owner.json').read_bytes())['creation_record_sha256'], digest((fresh / 'operations/write.jsonl').read_bytes()))
        invalid = json.loads(inventory.read_bytes()); invalid['resources'][0]['connection_string'] = 'forbidden'
        with self.assertRaises(ProviderError): context.inventory(json.dumps(invalid).encode(), project)


    def test_aws_wrapper_restores_selected_targets_and_tags_before_assume_role(self):
        account, role, region = '111122223333', 'application-runner', 'eu-west-1'
        os.environ.update(FACTORY_AWS_ACCOUNT_ID=account, FACTORY_AWS_ROLE_NAME=role, FACTORY_AWS_REGION=region)
        initial = self.initialize()
        for key in ('FACTORY_AWS_ACCOUNT_ID', 'FACTORY_AWS_ROLE_NAME', 'FACTORY_AWS_REGION', 'FACTORY_PROJECT_ID', 'FACTORY_ENVIRONMENT'):
            del os.environ[key]
        os.environ.update(AWS_ACCESS_KEY_ID='ASIA' + uuid.uuid4().hex[:16].upper(), AWS_SECRET_ACCESS_KEY=uuid.uuid4().hex)
        secret, token, access = uuid.uuid4().hex, uuid.uuid4().hex * 2, 'ASIA' + uuid.uuid4().hex[:16].upper()
        calls = []
        session_arn = None
        def response(command, env, provider, **kwargs):
            nonlocal session_arn
            calls.append((command, env))
            if command[1:3] == ['sts', 'assume-role']:
                session = command[command.index('--role-session-name') + 1]
                session_arn = 'arn:aws:sts::' + account + ':assumed-role/' + role + '/' + session
                self.assertIn('Key=factory:project-id,Value=' + initial['project_id'], command)
                self.assertIn('Key=factory:environment,Value=development', command)
                self.assertIn('Key=factory:s,Value=' + initial['project_id'] + '-development', command)
                return json.dumps(dict(AssumedRoleUser=dict(Arn=session_arn), Credentials=dict(AccessKeyId=access,
                    SecretAccessKey=secret, SessionToken=token, Expiration=(datetime.now(timezone.utc) + timedelta(seconds=899)).isoformat()))).encode()
            if command[1:3] == ['sts', 'get-caller-identity']:
                return json.dumps(dict(Account=account, Arn=session_arn)).encode()
            self.assertEqual(env['AWS_SECRET_ACCESS_KEY'], secret)
            return b'{"accepted":true}'
        args = argparse.Namespace(command=['s3api', 'put-object', '--bucket', 'fixture-owned-resource', '--key', 'fixture'], exec=False,
            record=str(self.root / 'aws.jsonl'), output=str(self.root / 'aws-result.json'))
        with patch.object(aws, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(aws, 'run', side_effect=response), redirect_stdout(io.StringIO()):
            aws.execute(args)
        self.assertEqual(len(calls), 3)
        self.assertEqual(os.environ['FACTORY_PROJECT_ID'], initial['project_id'])
        self.assertEqual(os.environ['FACTORY_AWS_REGION'], region)
        os.environ['FACTORY_AWS_REGION'] = 'us-west-2'
        args.record, args.output = str(self.root / 'aws-second.jsonl'), str(self.root / 'aws-second-result.json')
        with patch.object(aws, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(aws, 'run', side_effect=response), redirect_stdout(io.StringIO()):
            aws.execute(args)
        self.assertEqual(calls[-1][1]['AWS_REGION'], 'us-west-2')
        saved = self.app / '.factory/project.json'
        self.assertEqual(json.loads(saved.read_bytes())['config']['FACTORY_AWS_REGION'], region)



if __name__ == '__main__':
    unittest.main()
