"""Offline rendering/fault checks; these are not AWS authorization simulation."""
import copy
import fnmatch
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('aws_profile', Path(__file__).resolve().parents[1] / 'infra/aws/render.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


class AWSProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(account_id='123456789012', runner_role='runner', bootstrap_user='bootstrap',
            app_boundary_name='EngineeringFactoryAppBoundary', app_policy_name='EngineeringFactoryAppProvisioner',
            protected_resource_arns=['arn:aws:ec2:us-east-2:123456789012:instance/i-0123456789abcdef0'],
            runner_managed_policy_count=0, runner_managed_policy_limit=20)
        self.arn = 'arn:aws:iam::123456789012:role/runner'
        zone = 'arn:aws:route53:::hostedzone/ZEXAMPLE'
        name_key = 'route53:ChangeResourceRecordSetsNormalizedRecordNames'
        self.baseline = profile.document([
            dict(profile.statement('route53:ChangeResourceRecordSets', zone, {
                'ForAllValues:StringLike': {name_key: ['factory-*.example.test']},
                'Null': {name_key: 'false'}}), Sid='CreateNamesInReservedFactoryNamespace'),
            dict(profile.statement('route53:ChangeResourceRecordSets', zone,
                {'ForAnyValue:StringLike': {name_key: ['example.test', 'core.example.test', '*.core.example.test']}},
                effect='Deny'), Sid='DenyCoreNamesAndReservedSubtrees'),
            dict(profile.statement('*', '*', {'DateGreaterThanEquals': {'aws:CurrentTime': '2030-01-01T00:00:00Z'}}, effect='Deny'), Sid='DenyAfterExpiry'),
            dict(profile.statement('*', '*', {'Bool': {'aws:SecureTransport': 'false'}}, effect='Deny'), Sid='DenyInsecureTransport')])
        self.boundary = profile.document([dict(profile.statement(list(profile.ADMIN_ACTIONS), '*', effect='Deny'), Sid='DenyAccountAndIdentityAdministration')])
        conditions = {'StringLike': {'sts:RoleSessionName': 'factory-*'},
            'DateLessThan': {'aws:CurrentTime': '2030-01-01T00:00:00Z'}, 'Bool': {'aws:SecureTransport': 'true'}}
        self.bootstrap = profile.document([
            dict(profile.statement('sts:AssumeRole', self.arn, conditions), Sid='AssumeFactoryRunnerOnly'),
            {'Sid': 'DenyDirectAwsUse', 'Effect': 'Deny', 'NotAction': 'sts:AssumeRole', 'Resource': '*'},
            {'Sid': 'DenyOtherRoles', 'Effect': 'Deny', 'Action': 'sts:AssumeRole', 'NotResource': self.arn}])
        trust_conditions = copy.deepcopy(conditions)
        trust_conditions['ArnEquals'] = {'aws:PrincipalArn': 'arn:aws:iam::123456789012:user/bootstrap'}
        self.trust = profile.document([{'Effect': 'Allow', 'Principal': {'AWS': 'arn:aws:iam::123456789012:root'},
            'Action': 'sts:AssumeRole', 'Condition': trust_conditions}])
        self.args = [self.config, self.baseline, self.boundary, self.bootstrap, self.trust]
        self.result = profile.render(*self.args)

    def test_preserves_rollback_and_input_documents_but_replaces_dns_semantics(self):
        original = copy.deepcopy(self.args)
        self.assertEqual(self.result['runner-dns-baseline.json'], self.baseline)
        self.assertNotEqual(self.result['runner-dns-policy.json'], self.baseline)
        profile.render(*self.args)
        self.assertEqual(self.args, original)
        for name in ('runner-boundary.json', 'app-execution-boundary.json'):
            self.assertTrue(all('Sid' not in s for s in self.result[name]['Statement']))

    def test_dns_own_namespace_children_wildcards_and_mixed_batch_guard(self):
        dns = self.result['runner-dns-policy.json']['Statement']
        grant = next(s for s in dns if s['Effect'] == 'Allow' and s['Action'] == 'route53:ChangeResourceRecordSets')
        key = 'route53:ChangeResourceRecordSetsNormalizedRecordNames'
        patterns = grant['Condition']['ForAllValues:StringLike'][key]
        scope = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee-dev'
        patterns = [p.replace(profile.SCOPE, scope) for p in patterns]
        own = 'factory-' + scope + '-r-api.example.test'
        for name in (own, '_acm.' + own, '\\052.' + own):
            self.assertTrue(any(fnmatch.fnmatchcase(name, p) for p in patterns))
        for name in ('example.test', 'core.example.test', 'factory-other-dev-r-api.example.test', 'factory-' + scope + '-prod-r-api.example.test'):
            self.assertFalse(any(fnmatch.fnmatchcase(name, p) for p in patterns))
        identifier = own.split('.')[0]
        self.assertRegex(identifier, r'^[a-z][a-z0-9-]{0,62}$')
        self.assertNotIn('--', identifier)
        self.assertFalse(identifier.endswith('-'))
        self.assertEqual(grant['Condition']['Null'], {key: 'false'})
        self.assertNotIn('ForAnyValue:StringLike', grant['Condition'])
        # No obsolete CREATE-only/RR-type restriction: Route53 itself validates its enum.
        self.assertNotIn('route53:ChangeResourceRecordSetsActions', json.dumps(grant))
        core = next(s for s in dns if s['Effect'] == 'Deny' and s['Action'] == 'route53:ChangeResourceRecordSets')
        self.assertEqual(core, self.baseline['Statement'][1])

    def test_general_service_grant_has_no_short_service_or_region_allowlist(self):
        for name in ('runner-boundary.json', 'app-execution-boundary.json'):
            broad = next(s for s in self.result[name]['Statement'] if s['Effect'] == 'Allow' and 'NotAction' in s)
            self.assertEqual(broad['NotAction'], ['route53:*', 'route53domains:*'])
            self.assertEqual(broad['Resource'], '*')
            self.assertNotIn('aws:RequestedRegion', json.dumps(self.result[name]))
        self.assertNotIn('HoldUnreviewedDelegatedExecution', json.dumps(self.result))

    def test_self_contained_iam_boundary_blocks_outside_paths_boundary_removal_and_elevation(self):
        for name in ('runner-boundary.json', 'app-execution-boundary.json'):
            statements = self.result[name]['Statement']
            iam = next(s for s in statements if s.get('Action') == 'iam:*')
            self.assertEqual(len(iam['NotResource']), 3)
            for kind, arn in zip(('role', 'instance-profile', 'policy'), iam['NotResource']):
                self.assertIn(':' + kind + '/factory/' + profile.SCOPE + '/*', arn)
                self.assertNotIn(self.arn, arn)
            boundary = next(s for s in statements if s.get('Action') == ['iam:CreateRole', 'iam:PutRolePermissionsBoundary'])
            self.assertEqual(boundary['Effect'], 'Deny')
            self.assertEqual(boundary['Condition']['ArnNotEquals']['iam:PermissionsBoundary'],
                             'arn:aws:iam::123456789012:policy/EngineeringFactoryAppBoundary')
            self.assertIn(profile.statement('iam:DeleteRolePermissionsBoundary', '*', effect='Deny'), statements)
            self.assertIn(profile.statement('sts:*', '*', effect='Deny'), statements)
            self.assertIn('identitystore:*', json.dumps(statements))

    def test_scope_missing_override_and_canonical_mismatch_are_explicit_denials(self):
        for name in ('runner-boundary.json', 'app-execution-boundary.json'):
            statements = self.result[name]['Statement']
            relation = next(s for s in statements if 'aws:PrincipalTag/factory:scope' in s.get('Condition', {}).get('StringNotEquals', {}))
            self.assertEqual(relation['Effect'], 'Deny')
            value = relation['Condition']['StringNotEquals']['aws:PrincipalTag/factory:scope']
            self.assertEqual(value, "${aws:PrincipalTag/factory:project-id, '/'}-${aws:PrincipalTag/factory:environment, '/'}")
        app = self.result['app-execution-boundary.json']['Statement']
        path_guard = next(s for s in app if 'ArnNotLike' in s.get('Condition', {}) and 'aws:PrincipalArn' in s['Condition']['ArnNotLike'])
        self.assertIn('/factory/' + profile.SCOPE + '/*', path_guard['Condition']['ArnNotLike']['aws:PrincipalArn'])
        meta = next(s for s in app if 'aws:PrincipalTag/factory:scope' in s.get('Condition', {}).get('StringLike', {}))
        self.assertIn('*${*}*', meta['Condition']['StringLike']['aws:PrincipalTag/factory:scope'])
        self.assertIn('*${?}*', meta['Condition']['StringLike']['aws:PrincipalTag/factory:scope'])
        self.assertIn('*-r-*', meta['Condition']['StringLike']['aws:PrincipalTag/factory:scope'])
        self.assertNotIn('DateGreaterThanEquals', json.dumps(app))
        self.assertIn('aws:SecureTransport', json.dumps(app))
        self.assertIn('DateGreaterThanEquals', json.dumps(self.result['runner-boundary.json']))

    def test_tag_session_four_keys_relation_and_default_role_provenance(self):
        for policy in (self.result['bootstrap-policy.json'], self.result['runner-trust.json']):
            tags = next(s for s in policy['Statement'] if s.get('Action') == 'sts:TagSession' and s['Effect'] == 'Allow')
            self.assertEqual(tags['Condition']['StringEquals']['aws:RequestTag/factory:scope'],
                             '${aws:RequestTag/factory:project-id}-${aws:RequestTag/factory:environment}')
            self.assertEqual(len(tags['Condition']['ForAllValues:StringEquals']['aws:TagKeys']), 4)
        environment_guard = next(s for s in self.result['bootstrap-policy.json']['Statement']
            if s['Effect'] == 'Deny' and 'aws:RequestTag/factory:environment' in s.get('Condition', {}).get('StringLike', {}))
        forbidden = environment_guard['Condition']['StringLike']['aws:RequestTag/factory:environment']
        for value in ('r', 'r-prod', 'prod-r', 'prod-r-west', 'dev-'):
            self.assertTrue(any(fnmatch.fnmatchcase(value, p) for p in forbidden))
        for value in ('dev', 'dev-prod', 'rds'):
            self.assertFalse(any(fnmatch.fnmatchcase(value, p) for p in forbidden))
        create = self.result['app-execution-policy.json']['Statement'][-1]
        self.assertEqual(create['Condition']['StringEquals']['aws:RequestTag/factory:scope'], profile.SCOPE)
        self.assertEqual(len(create['Condition']['StringLike']) - 1, 13)

    def test_engine_guards_cover_stored_roles_and_cluster_target_not_unsupported_rolearn(self):
        statements = self.result['app-execution-boundary.json']['Statement']
        engines = next(s for s in statements if 'NotResource' in s and s.get('Action') != 'iam:*')
        for action in ('cloudformation:ExecuteChangeSet', 'cloudformation:ExecuteStackRefactor',
                       'lambda:UpdateFunctionCode', 'codebuild:StartBuild', 'ecs:CreateService'):
            self.assertTrue(any(fnmatch.fnmatchcase(action.lower(), p.lower()) for p in engines['Action']))
        self.assertNotIn('cloudformation:RoleArn', json.dumps(statements))
        scope = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee-dev'
        scoped = [p.replace(profile.SCOPE, scope) for p in engines['NotResource']]
        self.assertTrue(any(fnmatch.fnmatchcase('arn:aws:states:us-east-2:123456789012:stateMachine:factory-' + scope + '-r-api:live', p) for p in scoped))
        self.assertFalse(any(fnmatch.fnmatchcase('arn:aws:states:us-east-2:123456789012:stateMachine:core:factory-' + scope + '-r-alias', p) for p in scoped))
        cluster = next(s for s in statements if 'ecs:cluster' in s.get('Condition', {}).get('ArnNotLike', {}))
        for action in ('ecs:CreateService', 'ecs:UpdateTaskSet'):
            self.assertTrue(any(fnmatch.fnmatchcase(action, p) for p in cluster['Action']))
        versions = next(s for s in statements if s.get('Action') == 'autoscaling:*')
        self.assertEqual(versions['Condition'], {'Bool': {'autoscaling:LaunchTemplateVersionSpecified': 'false'}})
        for key in ('ssm:resourceTag/factory:scope', 'aws:ResourceTag/factory:scope'):
            self.assertIn(key, json.dumps(statements))
        global_controls = next(s for s in statements if 'ssm:CreateAssociation*' in s.get('Action', []))
        for action in ('ssm:RegisterTaskWithMaintenanceWindow', 'servicecatalog:UpdateConstraint', 'autoscaling:StartInstanceRefresh'):
            self.assertIn(action, global_controls['Action'])

    def test_protected_exact_inventory_and_child_derivation(self):
        self.config['protected_resource_arns'] += ['arn:aws:s3:::protected-example-bucket',
            'arn:aws:lambda:us-east-2:123456789012:function:protected-function']
        self.config['protected_resource_arns'].append('arn:aws:payments::123456789012:payment-instrument:example')
        protected = profile.protected_resources(self.config)
        self.assertNotIn('arn:aws:payments::123456789012:payment-instrument:example', protected)
        self.assertIn('arn:aws:s3:::protected-example-bucket/*', protected)
        self.assertIn('arn:aws:lambda:us-east-2:123456789012:function:protected-function:*', protected)
        for bad in ('arn:aws:s3:::*', 'arn:aws:iam::123456789012:role/admin',
                    'arn:aws:ec2:us-east-2:999999999999:instance/i-other'):
            self.config['protected_resource_arns'] = [bad]
            with self.assertRaises(ValueError):
                profile.render(*self.args)

    def test_realistic_quota_and_input_faults_fail_closed(self):
        for name, policy in self.result.items():
            self.assertLessEqual(len(profile.compact(policy)), 2048 if name == 'bootstrap-policy.json' else 6144)
        realistic = copy.deepcopy(self.config)
        realistic['protected_resource_arns'] = ['arn:aws:ec2:us-east-2:123456789012:instance/i-' + str(i).zfill(17) for i in range(12)]
        rendered = profile.render(realistic, *self.args[1:])
        self.assertLessEqual(len(profile.compact(rendered['app-execution-boundary.json'])), 6144)
        for count, limit in ((20, 20), (-1, 20), (0, 26), (False, 20)):
            self.config.update(runner_managed_policy_count=count, runner_managed_policy_limit=limit)
            with self.assertRaises(ValueError):
                profile.render(*self.args)
        self.config.update(runner_managed_policy_count=0, runner_managed_policy_limit=20)
        self.config['protected_resource_arns'] = ['arn:aws:ec2:us-east-2:123456789012:instance/i-' + str(i).zfill(17) for i in range(100)]
        with self.assertRaisesRegex(ValueError, 'quota'):
            profile.render(*self.args)

    def test_cli_private_hashes_and_invalid_input_has_no_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = []
            for key, value in zip(('config', 'baseline', 'boundary', 'bootstrap', 'trust'), self.args):
                path = root / (key + '.json')
                path.write_text(json.dumps(value))
                inputs += ['--' + key, str(path)]
            output = root / 'policies'
            command = [sys.executable, str(SPEC.origin), *inputs, '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            manifest = json.loads((output / 'review-manifest.json').read_text())
            self.assertEqual(manifest['planned_new_runner_attachments'], 1)
            for name, record in manifest['policies'].items():
                path = output / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['sha256'])
            self.assertNotIn('123456789012', result.stdout + result.stderr)
            (root / 'config.json').write_text('{}')
            bad = root / 'bad'
            command[-1] = str(bad)
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(bad.exists())

    def test_missing_original_guards_and_changed_bootstrap_identity_are_rejected(self):
        for sid in ('AssumeFactoryRunnerOnly', 'DenyDirectAwsUse', 'DenyOtherRoles'):
            changed = copy.deepcopy(self.bootstrap)
            changed['Statement'] = [s for s in changed['Statement'] if s.get('Sid') != sid]
            with self.assertRaises(ValueError):
                profile.render(self.config, self.baseline, self.boundary, changed, self.trust)
        changed = copy.deepcopy(self.boundary)
        changed['Statement'][0]['Action'].remove('identitystore:*')
        with self.assertRaises(ValueError):
            profile.render(self.config, self.baseline, changed, self.bootstrap, self.trust)
        changed = copy.deepcopy(self.baseline)
        changed['Statement'][0]['Resource'] = '*'
        with self.assertRaises(ValueError):
            profile.render(self.config, changed, self.boundary, self.bootstrap, self.trust)
        self.trust['Statement'][0]['Condition']['ArnEquals']['aws:PrincipalArn'] = 'arn:aws:iam::123456789012:user/other'
        with self.assertRaises(ValueError):
            profile.render(*self.args)


if __name__ == '__main__':
    unittest.main()
