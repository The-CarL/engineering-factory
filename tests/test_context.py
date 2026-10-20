"""Real local Git persistence/restore with fake network identity and no provider calls."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import argparse
import importlib.util
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


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git = shutil.which('git')
        self.real_run = subprocess.run
        self.tools = {name: '/verified/' + name for name in ('aws', 'gh', 'python', 'node', 'npm', 'vercel')}
        self.tools['git'] = self.git
        self.token = uuid.uuid4().hex
        self.target = 'fixture-owner/app'
        self.private = True
        self.principal = 'fixture-owner'
        self.membership = 'active'
        self.published = []
        self.store_remote = self.root / 'state.git'
        self.app_remote = self.root / 'app.git'
        for remote in (self.store_remote, self.app_remote):
            self.git_run('init', '--bare', '--initial-branch=main', str(remote))
        self.app = self.root / 'app'
        self.git_run('init', '--initial-branch=main', str(self.app))
        self.git_run('-C', str(self.app), 'remote', 'add', 'origin', 'https://github.com/' + self.target + '.git')
        (self.app / 'source.txt').write_text('fixture application source')
        self.git_run('-C', str(self.app), 'add', '.')
        self.git_run('-C', str(self.app), 'commit', '-m', 'fixture')
        self.git_run('-C', str(self.app), 'push', str(self.app_remote), 'HEAD:main')
        self.environ = patch.dict(os.environ, dict(FACTORY_PRIVATE_ROOT=str(self.root), FACTORY_GITHUB_OWNER='fixture-owner',
            FACTORY_SOURCE_REPOSITORY='fixture-owner/factory', FACTORY_SOURCE_REVISION='a' * 40,
            FACTORY_GITHUB_CREDENTIAL_SOURCE='factory-token', FACTORY_GITHUB_TOKEN=self.token,
            GH_TOKEN='ambient-must-not-win', FACTORY_CONTEXT_REPOSITORY='fixture-owner/state',
            FACTORY_CONTEXT_DIRECTORY=str(self.root / 'context-cache')), clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.patch_run = patch.object(context.subprocess, 'run', side_effect=self.process)
        self.patch_run.start()
        self.addCleanup(self.patch_run.stop)
        self.patch_api = patch.object(context, 'run', side_effect=self.provider)
        self.patch_api.start()
        self.addCleanup(self.patch_api.stop)

    def git_run(self, *args):
        result = self.real_run([self.git, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                                *args], env=base_env('/tmp'), capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def process(self, command, **kwargs):
        command = list(command)
        if command[0] == self.git:
            # Exercise real Git; only replace the network transport with an isolated bare repository.
            if any(value in command for value in ('fetch', 'push', 'ls-remote')) and 'origin' in command:
                if 'push' in command:
                    self.published.append(command.copy())
                command[command.index('origin')] = str(self.store_remote)
        return self.real_run(command, **kwargs)

    def provider(self, command, env, provider, **kwargs):
        self.assertEqual(env.get('GH_TOKEN'), self.token)
        self.assertNotIn('FACTORY_GITHUB_TOKEN', env)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
        if 'clone' in command:
            command = [str(self.app_remote) if value == 'https://github.com/' + self.target + '.git' else value for value in command]
            result = self.real_run(command, env=env, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.git_run('-C', command[-1], 'remote', 'set-url', 'origin', 'https://github.com/' + self.target + '.git')
            return result.stdout
        endpoint = command[-1]
        if endpoint == 'user':
            return json.dumps(dict(login=self.principal)).encode()
        if endpoint == 'user/memberships/orgs/fixture-owner':
            return json.dumps(dict(state=self.membership, organization=dict(login='fixture-owner'))).encode()
        if endpoint == 'repos/fixture-owner/state':
            size = bool(self.git_run('--git-dir=' + str(self.store_remote), 'show-ref', '--heads') if (self.store_remote / 'refs/heads/main').exists() else b'')
            return json.dumps(dict(full_name='fixture-owner/state', private=self.private, archived=False, default_branch='main', size=int(size))).encode()
        if endpoint == 'repos/' + self.target:
            return json.dumps(dict(full_name=self.target, private=False)).encode()
        self.fail('Unexpected provider endpoint')

    def initialize(self):
        result = context.checkpoint(self.target, self.app, initialize=True, environment='development', tools=self.tools)
        os.environ.update(FACTORY_PROJECT_ID=result['project_id'], FACTORY_ENVIRONMENT='development',
                          FACTORY_PROJECT_REPOSITORY=self.target, FACTORY_PROJECT_APP=str(self.app))
        return result

    def journal(self, name='operations/write.jsonl'):
        path = self.root / name
        path.parent.mkdir(mode=0o700, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        events = [dict(time=now, state='intent', provider='AWS', source='a' * 40, request_sha256='b' * 64),
                  dict(time=now, state='complete', response_sha256='c' * 64, size=12)]
        path.write_bytes(b''.join(json.dumps(event, sort_keys=True).encode() + b'\n' for event in events))
        path.chmod(0o600)
        return path

    def test_fresh_task_restores_private_journal_and_exact_project_without_handoff_file(self):
        initial = self.initialize()
        journal = self.journal()
        context.checkpoint(self.target, self.app, [(journal, 'journal')], tools=self.tools)
        expected = journal.read_bytes()
        fresh = self.root / 'fresh'
        fresh.mkdir(mode=0o700)
        os.environ.update(FACTORY_PRIVATE_ROOT=str(fresh), FACTORY_CONTEXT_DIRECTORY=str(fresh / 'context-cache'))
        del os.environ['FACTORY_PROJECT_APP']
        restored_app = fresh / 'app'
        values = context.restore(self.target, restored_app, self.tools)
        self.assertEqual(values['FACTORY_PROJECT_ID'], initial['project_id'])
        restored = fresh / 'operations/write.jsonl'
        self.assertEqual(restored.read_bytes(), expected)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)
        self.assertEqual((restored_app / 'source.txt').read_text(), 'fixture application source')
        self.assertTrue(self.published)
        self.assertTrue(all('--force' not in command for command in self.published))


    def test_actual_github_bootstrap_and_context_free_read_work_before_project_init(self):
        body = self.root / 'create.json'
        body.write_text('{"name":"app","private":true}')
        body.chmod(0o600)
        calls = []
        def response(command, env, provider, **kwargs):
            calls.append(command)
            if command[-1] == 'user':
                return b'{"login":"fixture-owner"}'
            if 'user/repos' in command:
                return b'{"full_name":"fixture-owner/app","private":true}'
            return b'{"full_name":"fixture-owner/app","private":true}'
        args = argparse.Namespace(mode='gh', repo=self.target, command=['api', 'user/repos', '--method', 'POST', '--input', str(body)],
            visibility='private', record=str(self.root / 'create.jsonl'), output=str(self.root / 'create-result.json'))
        with patch.object(github, 'load', return_value=self.tools), patch.object(github, 'run', side_effect=response), \
             patch.object(context, 'restore') as restore, redirect_stdout(io.StringIO()):
            github.execute(args)
            args.command = ['api', 'repos/' + self.target]
            args.record, args.output = str(self.root / 'read.jsonl'), str(self.root / 'read-result.json')
            github.execute(args)
        restore.assert_not_called()
        self.assertTrue(any('user/repos' in command for command in calls))
        self.assertEqual(len(self.published), 0)

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
                self.assertIn('Key=factory:scope,Value=' + initial['project_id'] + '-development', command)
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
        saved = Path(os.environ['FACTORY_CONTEXT_DIRECTORY']) / 'projects' / initial['project_id'] / 'project.json'
        self.assertEqual(json.loads(saved.read_bytes())['config']['FACTORY_AWS_REGION'], region)


    def test_feature_branch_push_and_pr_preserve_dirty_app_source(self):
        self.initialize()
        self.git_run('-C', str(self.app), 'switch', '-c', 'feature')
        dirty = self.app / 'source.txt'
        dirty.write_text('preserve uncommitted application work')
        def response(command, env, provider, **kwargs):
            if command[0] == self.tools['gh']:
                if command[-1] == 'user':
                    return b'{"login":"fixture-owner"}'
                if command[1] == 'api':
                    return json.dumps(dict(full_name=self.target, private=False)).encode()
                return b'https://github.com/fixture-owner/app/pull/1\n'
            command = list(command)
            if 'push' in command:
                command[command.index('origin')] = str(self.app_remote)
            result = self.real_run(command, env=env, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        args = argparse.Namespace(mode='git', repo=self.target, app=str(self.app), branch='feature', action='push',
            command=[], visibility='public', record=str(self.root / 'push.jsonl'), output=str(self.root / 'push-result.txt'))
        body = self.root / 'pr-body.txt'
        body.write_text('Reviewed fixture change')
        body.chmod(0o600)
        with patch.object(github, 'load', return_value=self.tools), patch.object(context, 'load', return_value=self.tools), \
             patch.object(github, 'run', side_effect=response), redirect_stdout(io.StringIO()):
            github.execute(args)
            args.mode, args.record, args.output = 'gh', str(self.root / 'pr.jsonl'), str(self.root / 'pr-result.txt')
            args.command = ['pr', 'create', '--head', 'feature', '--title', 'Fixture change', '--body-file', str(body)]
            github.execute(args)
        self.assertEqual(dirty.read_text(), 'preserve uncommitted application work')
        self.assertEqual(self.git_run('--git-dir=' + str(self.app_remote), 'rev-parse', 'feature').strip(),
                         self.git_run('-C', str(self.app), 'rev-parse', 'HEAD').strip())
        record_path = Path(os.environ['FACTORY_CONTEXT_DIRECTORY']) / 'projects' / os.environ['FACTORY_PROJECT_ID'] / 'project.json'
        self.assertEqual(json.loads(record_path.read_bytes())['branch'], 'feature')

    def test_nonsecret_resource_inventory_restores_ids_references_and_safe_urls(self):
        initial = self.initialize()
        bucket = 'arn:aws:s3:::fixture-state'
        function = 'arn:aws:lambda:eu-west-1:111122223333:function:fixture'
        resources = [dict(provider='AWS', resource_id=bucket, resource_type='s3:bucket', parent_id=None, backend_ref=None,
                          run_id='fixture-run', source_commit='d' * 40, status='ready', ownership='managed'),
                     dict(provider='AWS', resource_id=function, resource_type='lambda:function', parent_id=None, backend_ref=bucket,
                          run_id='fixture-run', source_commit='d' * 40, status='ready', ownership='managed', url='https://fixture.example/')]
        data = dict(schema=1, project_id=initial['project_id'], environment='development', resources=resources)
        path = self.root / 'inventory/resources.json'
        path.parent.mkdir(mode=0o700)
        path.write_text(json.dumps(data) + '\n')
        path.chmod(0o600)
        expected = path.read_bytes()
        context.checkpoint(self.target, self.app, [(path, 'inventory')], tools=self.tools)
        path.unlink()
        context.restore(self.target, self.app, self.tools)
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(context.inventory(expected, initial['project_id'])['resources'][1]['backend_ref'], bucket)
        for field, value in [('connection_string', 'untrusted'), ('url', 'https://fixture.example/?token=unreviewed'),
                             ('resource_id', 'postgresql://fixture-user:' + uuid.uuid4().hex + '@fixture.invalid/database')]:
            invalid = json.loads(json.dumps(data))
            invalid['resources'][1][field] = value
            with self.assertRaises(ProviderError):
                context.inventory(json.dumps(invalid).encode(), initial['project_id'])
        self.assertEqual(len(self.published), 2)


    def test_context_inventory_and_ownership_share_reserved_environment_validation(self):
        initial = self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        meta = dict(factoryProjectId=initial['project_id'], factoryEnvironment='development', factoryOwner='fixture-owner',
                    factoryManagedBy='engineering-factory', factorySourceRepo=self.target, factorySourceCommit='d' * 40,
                    factoryCreatedBy='fixture', factoryCreatedAt=now, factoryCreationRunId='fixture-run',
                    factoryLastRunId='fixture-run', factoryLastSourceCommit='d' * 40,
                    factoryProvenanceVersion='1', factoryExpiresAt='none')
        context.metadata(meta)
        inventory = dict(schema=1, project_id=initial['project_id'], environment='development', resources=[dict(
            provider='AWS', resource_id='fixture-owned-resource', resource_type='s3:bucket', parent_id=None, backend_ref=None,
            run_id='fixture-run', source_commit='d' * 40, status='ready', ownership='managed')])
        for environment in ('r', 'r-blue', 'prod-r', 'prod-r-blue', 'prod--blue', 'prod-'):
            changed = dict(initial, environment=environment)
            with self.assertRaises(ProviderError):
                context.record(changed)
            inventory['environment'] = environment
            with self.assertRaises(ProviderError):
                context.inventory(json.dumps(inventory).encode(), initial['project_id'])
            meta['factoryEnvironment'] = environment
            with self.assertRaises(ProviderError):
                context.metadata(meta)
        self.assertEqual(len(self.published), 1)

    def test_context_owner_requires_own_identity_or_active_org_membership(self):
        self.principal, self.membership = 'fixture-agent', 'pending'
        with self.assertRaises(ProviderError):
            self.initialize()
        self.assertEqual(len(self.published), 0)
        self.membership = 'active'
        self.initialize()
        self.assertEqual(len(self.published), 1)

    def test_store_private_visibility_and_explicit_namespaced_source_required(self):
        self.private = False
        with self.assertRaises(ProviderError):
            self.initialize()
        self.assertFalse(self.published)
        self.private = True
        os.environ['FACTORY_GITHUB_CREDENTIAL_SOURCE'] = 'cli'
        with self.assertRaises(ProviderError):
            context.Store(self.tools)

    def test_new_repository_cannot_reuse_another_project_namespace(self):
        initial = self.initialize()
        original_target = self.target
        self.target = 'fixture-owner/second-app'
        self.git_run('-C', str(self.app), 'remote', 'set-url', 'origin', 'https://github.com/' + self.target + '.git')
        with self.assertRaises(ProviderError):
            context.checkpoint(self.target, self.app, initialize=True, environment='development', tools=self.tools)
        stored = Path(os.environ['FACTORY_CONTEXT_DIRECTORY']) / 'projects' / initial['project_id'] / 'project.json'
        self.assertEqual(json.loads(stored.read_bytes())['repository'], original_target)
        self.assertEqual(len(self.published), 1)

    def test_unknown_project_no_adoption_or_app_clone(self):
        self.initialize()
        destination = self.root / 'unknown'
        with self.assertRaises(ProviderError):
            context.restore('fixture-owner/unknown', destination, self.tools)
        self.assertFalse(destination.exists())

    def test_context_never_exports_arbitrary_document_response_secret_or_executable_config(self):
        initial = self.initialize()
        for value in (b'{"state":"complete","response":"raw provider response"}\n', self.token.encode(), b'private notes'):
            source = self.root / 'operations/unsafe.jsonl'
            source.parent.mkdir(mode=0o700, exist_ok=True)
            source.write_bytes(value)
            source.chmod(0o600)
            with self.assertRaises((ProviderError, ValueError)):
                context.checkpoint(self.target, self.app, [(source, 'journal')], tools=self.tools)
        initial['config']['FACTORY_AWS_EXECUTABLE'] = '/untrusted/program'
        with self.assertRaises(ProviderError):
            context.record(initial)
        self.assertEqual(len(self.published), 1)

    def test_target_conflict_and_existing_artifacts_are_preserved(self):
        initial = self.initialize()
        journal = self.journal()
        context.checkpoint(self.target, self.app, [(journal, 'journal')], tools=self.tools)
        journal.write_bytes(b'preserve later local work')
        with self.assertRaises(ProviderError):
            context.restore(self.target, self.app, self.tools)
        self.assertEqual(journal.read_bytes(), b'preserve later local work')
        journal.unlink()
        os.environ['FACTORY_PROJECT_ID'] = str(uuid.uuid4())
        with self.assertRaises(ProviderError):
            context.restore(self.target, self.app, self.tools)
        self.assertFalse(journal.exists())
        self.assertNotEqual(initial['project_id'], os.environ['FACTORY_PROJECT_ID'])

    def test_symlink_sources_and_traversal_paths_rejected_before_publication(self):
        self.initialize()
        original = self.journal()
        link = self.root / 'operations/link.jsonl'
        link.symlink_to(original)
        with self.assertRaises(ProviderError):
            context.checkpoint(self.target, self.app, [(link, 'journal')], tools=self.tools)
        for name in ('../escape', '/absolute', 'operations/.git/config', 'operations/../../escape'):
            with self.assertRaises(ProviderError):
                context.relative(name)
        self.assertEqual(len(self.published), 1)

    def test_store_rejects_remote_executable_or_hook_tree_before_checkout(self):
        self.initialize()
        cache = Path(os.environ['FACTORY_CONTEXT_DIRECTORY'])
        hook = cache / '.github/workflows/untrusted.yml'
        hook.parent.mkdir(parents=True)
        hook.write_text('never execute')
        self.git_run('-C', str(cache), 'add', '.')
        self.git_run('-C', str(cache), 'commit', '-m', 'malicious fixture')
        self.git_run('-C', str(cache), 'push', str(self.store_remote), 'HEAD:main')
        fresh = self.root / 'new-cache'
        os.environ['FACTORY_CONTEXT_DIRECTORY'] = str(fresh)
        with self.assertRaises(ProviderError):
            context.restore(self.target, self.app, self.tools)
        self.assertFalse((fresh / '.github').exists())


    def test_automatic_operation_checkpoint_excludes_raw_result_and_blocks_unknown_selection(self):
        self.initialize()
        record_path, output = self.root / 'automatic.jsonl', self.root / 'raw-result.json'
        with patch.object(context, 'load', return_value=self.tools), redirect_stdout(io.StringIO()):
            operation = Operation(record_path, output, 'AWS', b'not persisted request')
            operation.finish(b'{"private_response":"not exported"}')
        folder = Path(os.environ['FACTORY_CONTEXT_DIRECTORY']) / 'projects' / os.environ['FACTORY_PROJECT_ID']
        saved = json.loads((folder / 'project.json').read_bytes())
        self.assertEqual(set(saved['artifacts']), {'automatic.jsonl'})
        self.assertNotIn(b'private_response', (folder / 'artifacts/automatic.jsonl').read_bytes())
        self.assertFalse((folder / 'artifacts/raw-result.json').exists())
        os.environ['FACTORY_PROJECT_REPOSITORY'] = 'fixture-owner/unknown'
        os.environ.pop('FACTORY_PROJECT_APP')
        with patch.object(context, 'load', return_value=self.tools), self.assertRaises(ProviderError):
            Operation(self.root / 'never.jsonl', self.root / 'never.json', 'AWS', b'request')
        self.assertFalse((self.root / 'never.jsonl').exists())

    def test_ownership_receipt_restores_original_relative_layout_and_digest(self):
        initial = self.initialize()
        project = initial['project_id']
        now = datetime.now(timezone.utc).isoformat()
        meta = dict(factoryProjectId=project, factoryEnvironment='development', factoryOwner='fixture-owner',
                    factoryManagedBy='engineering-factory', factorySourceRepo=self.target, factorySourceCommit='d' * 40,
                    factoryCreatedBy='fixture', factoryCreatedAt=now, factoryCreationRunId='fixture-run',
                    factoryLastRunId='fixture-run', factoryLastSourceCommit='d' * 40,
                    factoryProvenanceVersion='1', factoryExpiresAt='none')
        events = [dict(time=now, state='intent', provider='Vercel', source='a' * 40, request_sha256='b' * 64),
                  dict(time=now, state='created-resource', team='team_fixture', project='prj_fixture', name='fixture', metadata=meta),
                  dict(time=now, state='complete', response_sha256='c' * 64, size=12)]
        creation = self.root / 'operations/create.jsonl'
        creation.parent.mkdir(mode=0o700)
        creation.write_bytes(b''.join(json.dumps(item).encode() + b'\n' for item in events))
        creation.chmod(0o600)
        owner = self.root / 'ownership/vercel.json'
        owner.parent.mkdir(mode=0o700)
        owner.write_text(json.dumps(dict(schema=1, factory_project_id=project, team_id='team_fixture', project_id='prj_fixture',
                        project_name='fixture', metadata=meta, creation_record='operations/create.jsonl', creation_record_sha256=digest(creation.read_bytes()))) + '\n')
        owner.chmod(0o600)
        expected = {str(path.relative_to(self.root)): path.read_bytes() for path in (owner, creation)}
        context.checkpoint(self.target, self.app, [(owner, 'ownership')], tools=self.tools)
        for path in (owner, creation):
            path.unlink()
        context.restore(self.target, self.app, self.tools)
        for name, data in expected.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        receipt = json.loads(owner.read_bytes())
        self.assertEqual(receipt['creation_record_sha256'], digest((self.root / receipt['creation_record']).read_bytes()))

    def test_push_failure_retains_committed_checkpoint_and_blocks_blind_retry(self):
        self.initialize()
        journal = self.journal()
        original = context.Store.git
        def failed(store, *args, **kwargs):
            if args[0] == 'push':
                raise ProviderError('fixture push failed')
            return original(store, *args, **kwargs)
        with patch.object(context.Store, 'git', failed), self.assertRaises(ProviderError):
            context.checkpoint(self.target, self.app, [(journal, 'journal')], tools=self.tools)
        cache = Path(os.environ['FACTORY_CONTEXT_DIRECTORY'])
        saved = (cache / 'projects' / os.environ['FACTORY_PROJECT_ID'] / 'artifacts/operations/write.jsonl').read_bytes()
        with self.assertRaises(ProviderError):
            context.checkpoint(self.target, self.app, tools=self.tools)
        self.assertEqual(saved, journal.read_bytes())
        self.assertEqual(len(self.published), 1)
        context.reconcile(self.tools)
        self.assertEqual(len(self.published), 2)
        context.reconcile(self.tools)
        self.assertEqual(len(self.published), 2)
        self.assertTrue(all('--force' not in command for command in self.published))


if __name__ == '__main__':
    unittest.main()
