"""Offline credential isolation, normal writes, exact targets and runtime integrity."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import hashlib
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
import runtime as guard
from provider import ProviderError


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


aws = module('runtime_aws', 'scripts/runtime/aws.py')
github = module('runtime_github', 'scripts/runtime/github.py')
vercel = module('runtime_vercel', 'scripts/runtime/vercel.py')
startup = module('runtime_start', 'runtime/start.py')
installer = module('runtime_install', 'runtime/install.py')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name).resolve()
        self.key = 'ASIA' + uuid.uuid4().hex[:16].upper()
        self.secret = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        self.session = uuid.uuid4().hex * 2
        self.bootstrap = uuid.uuid4().hex
        self.token = uuid.uuid4().hex
        self.env = dict(FACTORY_PRIVATE_ROOT=str(self.private), FACTORY_SOURCE_REVISION='a' * 40,
                        FACTORY_AWS_ACCOUNT_ID='111122223333', FACTORY_AWS_ROLE_NAME='application-runner',
                        FACTORY_AWS_REGION='eu-west-1', AWS_ACCESS_KEY_ID='bootstrap-key', AWS_SECRET_ACCESS_KEY=self.bootstrap,
                        FACTORY_GITHUB_OWNER='fixture-owner', FACTORY_GITHUB_CREDENTIAL_SOURCE='factory-token',
                        FACTORY_GITHUB_TOKEN=self.token, GH_TOKEN='competing', VERCEL_TOKEN='network-binding',
                        FACTORY_VERCEL_TEAM_ID='team_fixture', FACTORY_VERCEL_TEAM_SLUG='fixture-team')
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        self.tools = {name: '/verified/' + name for name in ('aws', 'gh', 'git', 'node', 'python', 'npm', 'vercel')}
        self.output = self.private / 'response.json'
        self.record = self.private / 'operation.jsonl'

    def args(self, **extra):
        return argparse.Namespace(record=str(self.record), output=str(self.output), **extra)

    def aws_run(self, command, env, provider, **kwargs):
        self.calls.append((command, dict(env)))
        if command[1:3] == ['sts', 'assume-role']:
            self.assertEqual(env['AWS_SECRET_ACCESS_KEY'], self.bootstrap)
            self.arn = 'arn:aws:sts::111122223333:assumed-role/application-runner/' + command[command.index('--role-session-name') + 1]
            return json.dumps(dict(AssumedRoleUser=dict(Arn=self.arn), Credentials=dict(AccessKeyId=self.key,
                SecretAccessKey=self.secret, SessionToken=self.session,
                Expiration=(datetime.now(timezone.utc) + timedelta(seconds=899)).isoformat()))).encode()
        self.assertEqual(env['AWS_SECRET_ACCESS_KEY'], self.secret)
        self.assertNotIn(self.bootstrap, env.values())
        if command[1:3] == ['sts', 'get-caller-identity']:
            return json.dumps(dict(Account='111122223333', Arn=self.arn)).encode()
        return b'{"accepted":true}'

    def execute_aws(self, command, execute=False, side_effect=None):
        self.calls = []
        with patch.object(aws, 'load', return_value=self.tools), patch.object(aws, 'run', side_effect=side_effect or self.aws_run), redirect_stdout(io.StringIO()):
            aws.execute(self.args(command=command, exec=execute))

    def test_aws_forwards_write_with_only_verified_assumed_credentials_and_tags(self):
        project = str(uuid.uuid4())
        os.environ.update(FACTORY_PROJECT_ID=project, FACTORY_ENVIRONMENT='development', FACTORY_AWS_SCOPE='untrusted-independent-override', AWS_PROFILE='personal',
                          AWS_ENDPOINT_URL='https://wrong.invalid', AWS_WEB_IDENTITY_TOKEN_FILE='/private/token',
                          AWS_CONTAINER_CREDENTIALS_FULL_URI='http://wrong.invalid', AWS_DATA_PATH='/untrusted',
                          GH_DEBUG='api', GIT_TRACE='1')
        self.execute_aws(['s3api', 'create-bucket', '--bucket', 'fixture-owned-resource'])
        assume, _, service = self.calls
        self.assertIn('Key=factory:project-id,Value=' + project, assume[0])
        self.assertIn('Key=factory:managed-by,Value=engineering-factory', assume[0])
        self.assertIn('Key=factory:s,Value=' + project + '-development', assume[0])
        self.assertNotIn('untrusted-independent-override', ' '.join(assume[0]))
        self.assertNotIn('FACTORY_AWS_SCOPE', service[1])
        self.assertEqual(service[0][1:3], ['s3api', 'create-bucket'])
        self.assertEqual(service[1]['AWS_SESSION_TOKEN'], self.session)
        for key in ('AWS_PROFILE', 'AWS_ENDPOINT_URL', 'AWS_WEB_IDENTITY_TOKEN_FILE', 'AWS_CONTAINER_CREDENTIALS_FULL_URI', 'AWS_DATA_PATH', 'GH_TOKEN', 'FACTORY_GITHUB_TOKEN', 'GH_DEBUG'):
            self.assertNotIn(key, service[1])
        self.assertEqual(service[1]['AWS_MAX_ATTEMPTS'], '1')
        self.assertEqual(os.environ['AWS_SECRET_ACCESS_KEY'], self.bootstrap)
        self.assertEqual(self.output.read_bytes(), b'{"accepted":true}')
        self.assertNotIn(self.secret, self.record.read_text())


    def test_canonical_scope_reserves_r_component_and_valid_resource_hyphens(self):
        project = '12345678-1234-1234-1234-123456789abc'
        for environment in ('development', 'prod-2', 'rds', 'r1', 'a' * 32):
            self.assertTrue(guard.valid_environment(environment))
            self.assertEqual(guard.project_scope(project, environment), project + '-' + environment)
        for environment in ('r', 'r-blue', 'prod-r', 'prod-r-blue', 'prod--blue', 'prod-', '-prod', 'Prod', 'a' * 33):
            self.assertFalse(guard.valid_environment(environment))
            with self.assertRaises(ProviderError):
                guard.project_scope(project, environment)
        for invalid in (project.upper(), project.replace('-', ''), project + '*', '00000000-0000-0000-0000-000000000000'):
            with self.assertRaises(ProviderError):
                guard.project_scope(invalid, 'development')

    def test_invalid_scope_environment_stops_before_assume_role_or_operation_record(self):
        os.environ['FACTORY_PROJECT_ID'] = str(uuid.uuid4())
        for environment in ('r', 'r-blue', 'prod-r', 'prod-r-blue', 'prod--blue', 'prod-'):
            os.environ['FACTORY_ENVIRONMENT'] = environment
            with self.assertRaises(ProviderError):
                self.execute_aws(['s3api', 'create-bucket', '--bucket', 'fixture-owned-resource'])
            self.assertEqual(self.calls, [])
            self.assertFalse(self.record.exists())

    def test_wrong_assumed_identity_blocks_service_and_does_not_fallback(self):
        def wrong(command, env, provider, **kwargs):
            result = self.aws_run(command, env, provider, **kwargs)
            if command[1:3] == ['sts', 'get-caller-identity']:
                return b'{"Account":"999900001111","Arn":"wrong"}'
            return result
        with self.assertRaises(ProviderError):
            self.execute_aws(['lambda', 'create-function'], side_effect=wrong)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.output.read_bytes(), b'')

    def test_aws_debug_abbreviations_alternate_roles_profiles_endpoints_block_before_assume(self):
        for command in (['sts', 'assume-role'], ['configure', 'list'], ['s3api', 'list-buckets', '--profi=x'],
                        ['s3api', 'list-buckets', '--endp', 'https://wrong.invalid'], ['s3', 'ls', '--debug'],
                        ['s3', 'ls', '--no-verify-ssl'], ['s3', 'ls', '--region', 'us-east-2']):
            with self.subTest(command=command), self.assertRaises(ProviderError):
                self.execute_aws(command)
            self.assertEqual(self.calls, [])
        self.assertFalse(self.record.exists())

    def test_trusted_exec_has_same_role_only_env_and_requires_exact_executable_hash(self):
        executable = self.private / 'trusted-tool'
        executable.write_text('reviewed executable')
        os.environ.update(FACTORY_AWS_EXECUTABLE=str(executable), FACTORY_AWS_EXECUTABLE_SHA256=guard.digest(executable.read_bytes()))
        self.execute_aws([str(executable), 'apply', 'reviewed-plan'], execute=True)
        self.assertEqual(self.calls[-1][0], [str(executable), 'apply', 'reviewed-plan'])
        self.assertEqual(self.calls[-1][1]['AWS_ACCESS_KEY_ID'], self.key)
        self.assertIn(str(Path(self.tools['node']).parent), self.calls[-1][1]['PATH'].split(os.pathsep))
        self.assertNotIn('VERCEL_TOKEN', self.calls[-1][1])
        self.assertNotIn('FACTORY_GITHUB_TOKEN', self.calls[-1][1])
        self.record.unlink()
        self.output.unlink()
        executable.write_text('changed')
        with self.assertRaises(ProviderError):
            self.execute_aws([str(executable)], execute=True)
        self.assertEqual(self.calls, [])

    def test_dns_zone_pair_forwarded_to_native_and_trusted_exec_without_other_secrets(self):
        zone = dict(FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE', FACTORY_AWS_DNS_ZONE_NAME='example.test')
        os.environ.update(zone)
        self.execute_aws(['route53', 'get-hosted-zone', '--id', 'ZEXAMPLE'])
        self.assertTrue(all(self.calls[-1][1].get(key) == value for key, value in zone.items()))
        self.record.unlink(); self.output.unlink()
        executable = self.private / 'trusted-dns-tool'
        executable.write_text('reviewed executable')
        os.environ.update(FACTORY_AWS_EXECUTABLE=str(executable), FACTORY_AWS_EXECUTABLE_SHA256=guard.digest(executable.read_bytes()))
        self.execute_aws([str(executable), 'plan'], execute=True)
        self.assertTrue(all(self.calls[-1][1].get(key) == value for key, value in zone.items()))
        self.assertNotIn('VERCEL_TOKEN', self.calls[-1][1])

    def test_incomplete_or_invalid_dns_zone_config_stops_before_assume_role(self):
        for values in (dict(FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE'),
                       dict(FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE', FACTORY_AWS_DNS_ZONE_NAME='*.example.test')):
            with patch.dict(os.environ, values), self.assertRaises(ValueError):
                self.execute_aws(['route53', 'get-hosted-zone', '--id', 'ZEXAMPLE'])
            self.assertFalse(self.calls)
            self.assertFalse(self.record.exists())

    def test_credentials_in_child_response_are_withheld_no_stdout_or_disk(self):
        def leak(command, env, provider, **kwargs):
            result = self.aws_run(command, env, provider, **kwargs)
            return self.secret.encode() if len(self.calls) == 3 else result
        with self.assertRaises(ProviderError):
            self.execute_aws(['s3api', 'list-buckets'], side_effect=leak)
        self.assertEqual(self.output.read_bytes(), b'')
        self.assertNotIn(self.secret, self.record.read_text())
        with patch('runtime.subprocess.run', return_value=subprocess.CompletedProcess([], 1, self.secret.encode(), self.secret.encode())), self.assertRaises(ProviderError) as failure:
            guard.run(['/verified/aws'], {}, 'AWS')
        self.assertNotIn(self.secret, str(failure.exception))

    def test_existing_operation_blocks_automatic_mutation_replay(self):
        self.execute_aws(['s3api', 'put-object', '--bucket', 'fixture', '--key', 'object'])
        with self.assertRaises(ProviderError):
            self.execute_aws(['s3api', 'put-object', '--bucket', 'fixture', '--key', 'object'])
        self.assertEqual(self.calls, [])

    def test_github_explicit_source_and_api_or_pr_target_gates(self):
        env = github.selected_env(self.private, 'fixture-owner/app')
        self.assertEqual(env['GH_TOKEN'], self.token)
        self.assertNotIn('FACTORY_GITHUB_TOKEN', env)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
        self.assertNotIn('VERCEL_TOKEN', env)
        with self.assertRaises(ProviderError):
            github.gh_command(['auth', 'token'], 'fixture-owner/app')
        for command in (['api', 'repos/other/core'], ['api', 'https://wrong.invalid'], ['pr', 'create', '-Rother/core'],
                        ['api', 'repos/fixture-owner/app', '--verbose']):
            with self.assertRaises(ProviderError):
                github.gh_command(command, 'fixture-owner/app')
        body = self.private / 'body.json'
        body.write_text('{"message":"Add readme","content":"SGVsbG8="}')
        body.chmod(0o600)
        command, payload = github.gh_command(['api', 'repos/fixture-owner/app/contents/README.md',
            '--method', 'PUT', '--input', str(body)], 'fixture-owner/app')
        self.assertIn('PUT', command)
        self.assertEqual(json.loads(payload)['message'], 'Add readme')

    def test_repository_creation_routes_stop_before_provider_calls(self):
        body = self.private / 'create.json'
        body.write_text('{"name":"app","private":true}')
        body.chmod(0o600)
        commands = [
            ['repo', 'create', 'fixture-owner/app', '--private'],
            ['api', 'user/repos', '--method', 'POST', '--input', str(body)],
            ['api', '/user/repos?test=1', '--method', 'POST', '--input', str(body)],
            ['api', 'orgs/fixture-owner/repos', '--method', 'POST', '--input', str(body)],
            ['api', 'repos/fixture-owner/app/generate', '--method', 'POST', '--input', str(body)],
            ['api', 'repos/fixture-owner/app/forks', '--method', 'POST', '--input', str(body)],
            ['api', 'repos/fixture-owner/app/generate/', '--method', 'POST', '--input', str(body)],
        ]
        app = self.private / 'app'
        (app / '.factory').mkdir(parents=True)
        (app / '.factory/project.json').write_text('{}')
        os.environ.update(FACTORY_PROJECT_REPOSITORY='fixture-owner/app', FACTORY_PROJECT_APP=str(app))
        for command in commands:
            with self.subTest(command=command), patch.object(github, 'load', return_value=self.tools), \
                 patch('context.preflight') as preflight, patch.object(github, 'run') as process, self.assertRaisesRegex(ProviderError, 'Repository creation is manual'):
                github.execute(self.args(mode='gh', repo='fixture-owner/app', command=command, visibility='private'))
            process.assert_not_called()
            preflight.assert_not_called()
        self.assertFalse(self.record.exists())
        self.assertFalse(self.output.exists())

    def test_namespaced_missing_github_binding_never_spawns_identity(self):
        del os.environ['FACTORY_GITHUB_TOKEN']
        with patch.object(github, 'load', return_value=self.tools), patch.object(github, 'run') as process, self.assertRaises(ProviderError):
            github.execute(self.args(mode='gh', repo='fixture-owner/app', command=['api', 'repos/fixture-owner/app'], visibility='private'))
        process.assert_not_called()

    def test_pr_uses_explicit_app_head_without_foreign_target_or_factory_history(self):
        body = self.private / 'pr-body.txt'
        body.write_text('Reviewed application change')
        body.chmod(0o600)
        command = ['pr', 'create', '--head', 'feature', '--title', 'Application change', '--body-file', str(body)]
        parsed, payload = github.gh_command(command, 'fixture-owner/app')
        self.assertEqual(parsed[-1], '-')
        self.assertEqual(payload, body.read_bytes())
        for command in (['pr', 'view', 'https://github.com/other/core/pull/1'],
                        ['pr', 'edit', '--add-label', 'reviewed', 'https://github.com/other/core/pull/1'],
                        ['pr', 'create', '--fill'], ['pr', 'view', '1', '-w'],
                        ['pr', 'create', '--head', 'other:feature', '--title', 'Change', '--body-file', str(body)],
                        ['pr', 'create', '--title', 'Change', '--body-file', str(body)]):
            with self.subTest(command=command), self.assertRaises(ProviderError):
                github.gh_command(command, 'fixture-owner/app')

    def test_git_normal_push_has_exact_origin_branch_helper_and_no_hooks(self):
        app = self.private / 'app'
        (app / '.git').mkdir(parents=True)
        responses = [b'https://github.com/fixture-owner/app.git\n', b'https://github.com/fixture-owner/app.git\n',
                     str(app).encode() + b'\n', b'core.repositoryformatversion\n', b'feature\n', b'feature\n']
        with patch.object(github, 'run', side_effect=responses):
            command, _ = github.git_command(self.tools, {}, self.args(app=str(app), branch='feature', action='push'), 'fixture-owner/app')
        self.assertEqual(command[-3:], ['push', 'origin', 'HEAD:refs/heads/feature'])
        self.assertIn('core.hooksPath=/dev/null', command)
        self.assertIn('credential.https://github.com.helper=!/verified/gh auth git-credential', command)
        for branch in ('+main', ':main', '--force', 'a..b'):
            with self.assertRaises(ProviderError):
                github.git_command(self.tools, {}, self.args(app=str(app), branch=branch, action='push'), 'fixture-owner/app')

    def metadata(self):
        project = str(uuid.uuid4())
        os.environ.update(FACTORY_PROJECT_ID=project, FACTORY_ENVIRONMENT='development')
        run_id = str(uuid.uuid4())
        meta = dict(factoryProjectId=project, factoryEnvironment='development', factoryOwner='fixture-owner',
                    factoryManagedBy='engineering-factory', factorySourceRepo='fixture-owner/app', factorySourceCommit='c' * 40,
                    factoryCreatedBy='fixture-runner', factoryCreatedAt=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),
                    factoryCreationRunId=run_id, factoryLastRunId=run_id, factoryLastSourceCommit='c' * 40,
                    factoryProvenanceVersion='1', factoryExpiresAt='none')
        path = self.private / 'provenance.json'
        path.write_text(json.dumps(meta))
        path.chmod(0o600)
        return path, meta

    def test_vercel_journaled_create_ownership_required_for_mutation_no_replay(self):
        calls = []
        class API:
            def request(inner, method, path, payload=None):
                calls.append((method, path, payload))
                if path == '/v2/user':
                    return dict(user=dict(id='user_fixture'))
                if '/teams/' in path:
                    return dict(id='team_fixture', slug='fixture-team')
                if path.startswith('/v9/projects?'):
                    return dict(projects=[])
                return dict(id='prj_fixture', name='fixture', accountId='team_fixture', publicSource=False,
                            ssoProtection=dict(deploymentType='all'))
        provenance, metadata = self.metadata()
        request = self.private / 'request.json'
        request.write_text('{"name":"fixture","publicSource":false,"ssoProtection":{"deploymentType":"all"}}')
        request.chmod(0o600)
        owner = self.private / 'owner.json'
        args = self.args(method='POST', project='fixture', path='/v11/projects', request=str(request),
                         provenance=str(provenance), owner_record=str(owner))
        with patch.object(vercel, 'load'), patch.object(vercel, 'Vercel', API), redirect_stdout(io.StringIO()):
            vercel.execute(args)
            receipt = json.loads(owner.read_bytes())
            self.assertEqual(receipt['metadata'], metadata)
            self.assertEqual(receipt['project_id'], 'prj_fixture')
            self.assertEqual(receipt['creation_record_sha256'], guard.digest(self.record.read_bytes()))
            request.write_text('{"buildCommand":"npm run build"}')
            args.method, args.project, args.path = 'PATCH', 'prj_fixture', '/v9/projects/prj_fixture'
            args.record, args.output = str(self.private/'patch.jsonl'), str(self.private/'patch.json')
            vercel.execute(args)
            with self.assertRaises(ProviderError):
                vercel.execute(args)
            self.assertEqual(sum(method == 'PATCH' for method, _, _ in calls), 1)
            args.record, args.output = str(self.private/'other.jsonl'), str(self.private/'other.json')
            args.owner_record = None
            with self.assertRaises(ProviderError):
                vercel.execute(args)
            args.owner_record = str(owner)
            self.record.write_bytes(self.record.read_bytes() + b'{}\n')
            with self.assertRaises(ProviderError):
                vercel.execute(args)
        self.assertEqual(sum(method == 'PATCH' for method, _, _ in calls), 1)
        self.assertEqual(owner.stat().st_mode & 0o777, 0o600)

    def test_vercel_failed_creation_readback_retains_id_without_ownership_or_duplicate_post(self):
        calls = []
        class API:
            def request(inner, method, path, payload=None):
                calls.append((method, path))
                if path == '/v2/user':
                    return dict(user=dict(id='user_fixture'))
                if '/teams/' in path:
                    return dict(id='team_fixture', slug='fixture-team')
                if path.startswith('/v9/projects?'):
                    return dict(projects=[])
                return dict(id='prj_fixture', name='fixture', accountId='team_fixture', publicSource=False,
                            ssoProtection=dict(deploymentType='preview'))
        provenance, _ = self.metadata()
        request = self.private / 'request.json'
        request.write_text('{"name":"fixture","publicSource":false,"ssoProtection":{"deploymentType":"all"}}')
        request.chmod(0o600)
        owner = self.private / 'owner.json'
        args = self.args(method='POST', project='fixture', path='/v11/projects', request=str(request),
                         provenance=str(provenance), owner_record=str(owner))
        with patch.object(vercel, 'load'), patch.object(vercel, 'Vercel', API):
            for _ in range(2):
                with self.assertRaises(ProviderError):
                    vercel.execute(args)
        self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)
        self.assertEqual(json.loads(self.output.read_bytes())['id'], 'prj_fixture')
        self.assertFalse(owner.exists())

    def test_installer_hash_and_host_version_fail_closed(self):
        artifact = self.private / 'archive'
        with patch.object(installer.urllib.request, 'urlopen', return_value=io.BytesIO(b'malformed archive')):
            with self.assertRaises(ProviderError):
                installer.download(dict(url='https://example.invalid/archive', sha256='0' * 64), artifact)
        with patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'v24.19.01\n', b'')):
            with self.assertRaises(ProviderError):
                installer.version(['node', '--version'], '24.19.0', {})

    def test_retained_runtime_detects_tampering_extra_files_modes_and_source_mismatch(self):
        factory = self.private / 'factory'
        (factory / 'runtime').mkdir(parents=True)
        (factory / 'runtime/pins.json').write_text('{}')
        installed = self.private / 'installed'
        installed.mkdir(mode=0o700)
        tool = installed / 'tool'
        tool.write_bytes(b'verified executable')
        tool.chmod(0o755)
        source = {'runtime/pins.json': guard.digest(b'{}')}
        manifest = dict(schema=1, revision='a' * 40, source=source, pins={},
                        files={'tool': dict(sha256=guard.digest(tool.read_bytes()), mode=0o755)},
                        tools={name: dict(path='tool', sha256=guard.digest(tool.read_bytes())) for name in self.tools})
        path = installed / 'manifest.json'
        path.write_text(json.dumps(manifest))
        path.chmod(0o600)
        os.environ['FACTORY_RUNTIME_MANIFEST'] = str(path)
        with patch.object(guard, 'ROOT', factory), patch.object(guard, 'check_source', return_value=('fixture/factory', 'a' * 40, source)):
            self.assertEqual(set(guard.load()), set(self.tools))
            tool.write_bytes(b'changed executable')
            with self.assertRaises(ProviderError):
                guard.load()
            tool.write_bytes(b'verified executable')
            tool.chmod(0o644)
            with self.assertRaises(ProviderError):
                guard.load()
            tool.chmod(0o755)
            extra = installed / 'unexpected.py'
            extra.write_bytes(b'unexpected')
            with self.assertRaises(ProviderError):
                guard.load()
            extra.unlink()
            manifest['source'] = {}
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ProviderError):
                guard.load()

    def test_source_check_requires_exact_clean_committed_origin_and_revision(self):
        factory = self.private / 'source'
        (factory / 'runtime').mkdir(parents=True)
        (factory / 'scripts/lib').mkdir(parents=True)
        (factory / 'runtime/pins.json').write_text('{}')
        (factory / 'scripts/lib/runtime.py').write_text('committed fixture')
        env = guard.base_env(self.private)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(factory), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args], env=env).decode().strip()
        git('init', '--quiet')
        git('remote', 'add', 'origin', 'https://github.com/fixture-owner/factory.git')
        git('add', '.')
        git('commit', '--quiet', '-m', 'fixture')
        os.environ.update(FACTORY_SOURCE_REPOSITORY='fixture-owner/factory', FACTORY_SOURCE_REVISION=git('rev-parse', 'HEAD'))
        with patch.object(guard, 'ROOT', factory):
            self.assertEqual(guard.check_source()[1], os.environ['FACTORY_SOURCE_REVISION'])
            git('remote', 'set-url', 'origin', 'https://github.com/Fixture-Owner/factory')
            self.assertEqual(guard.check_source()[1], os.environ['FACTORY_SOURCE_REVISION'])
            git('remote', 'set-url', 'origin', 'https://credential@github.com/fixture-owner/factory')
            with self.assertRaises(ProviderError):
                guard.check_source()
            git('remote', 'set-url', 'origin', 'https://github.com/fixture-owner/factory.git')
            (factory / 'runtime/pins.json').write_text('{"changed":true}')
            with self.assertRaises(ProviderError):
                guard.check_source()
            (factory / 'runtime/pins.json').write_text('{}')
            os.environ['FACTORY_SOURCE_REVISION'] = 'b' * 40
            with self.assertRaises(ProviderError):
                guard.check_source()

    def test_clean_source_refresh_uses_only_reviewed_fast_forward(self):
        factory = self.private / 'factory-source'
        (factory / '.git').mkdir(parents=True)
        os.environ['FACTORY_SOURCE_REPOSITORY'] = 'fixture-owner/factory'
        responses = [str(factory).encode(), b'main', b'https://github.com/fixture-owner/factory.git', b'',
                     b'core.repositoryformatversion', b'b' * 40, b'', b'', b'', b'', b'a' * 40]
        calls = []
        def fake(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, responses[len(calls)-1], b'')
        with patch.object(startup, 'ROOT', factory), patch.object(startup.subprocess, 'run', side_effect=fake):
            self.assertTrue(startup.refresh())
        self.assertEqual(calls[-2][-4:], ['merge', '--ff-only', '--no-edit', 'a' * 40])
        self.assertFalse(any('reset' in call or 'checkout' in call or 'switch' in call for call in calls))

    def test_refresh_rejects_dirty_branch_or_origin_before_fetch(self):
        factory = self.private / 'factory-source'
        (factory / '.git').mkdir(parents=True)
        os.environ.update(FACTORY_SOURCE_REPOSITORY='fixture-owner/factory')
        for values in ([str(factory).encode(), b'feature', b'https://github.com/fixture-owner/factory.git'],
                       [str(factory).encode(), b'main', b'https://github.com/other/factory.git'],
                       [str(factory).encode(), b'main', b'https://github.com/fixture-owner/factory.git', b' M user-file']):
            calls = []
            def fake(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, values[len(calls) - 1], b'')
            with patch.object(startup, 'ROOT', factory), patch.object(startup.subprocess, 'run', side_effect=fake), self.assertRaises(ProviderError):
                startup.refresh()
            self.assertFalse(any('fetch' in call or 'merge' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
