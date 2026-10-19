"""Checks for the one-time profile renderer's isolation and unchanged baseline guards."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('aws_profile', Path(__file__).resolve().parents[1] / 'infra/aws/render.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


class AWSProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(account_id='123456789012', runner_role='runner', bootstrap_user='bootstrap',
                           app_boundary_name='EngineeringFactoryAppBoundary', app_policy_name='EngineeringFactoryAppData')
        self.arn = 'arn:aws:iam::123456789012:role/runner'
        self.baseline = profile.document([profile.statement('route53:ChangeResourceRecordSets', '*', effect='Deny'),
                                          profile.statement('*', '*', {'DateGreaterThanEquals': {'aws:CurrentTime': '2030-01-01T00:00:00Z'}}, effect='Deny')])
        self.boundary = profile.document([
            {'Effect': 'Allow', 'NotAction': ['route53:*', 'route53domains:*'], 'Resource': '*'},
            dict(profile.statement(['iam:*', 'account:*', 'organizations:*'], '*', effect='Deny'), Sid='DenyAccountAndIdentityAdministration'),
            profile.statement(['sts:AssumeRole', 'sts:TagSession'], '*', effect='Deny'), *self.baseline['Statement']])
        conditions = {'StringLike': {'sts:RoleSessionName': 'factory-*'},
                      'DateLessThan': {'aws:CurrentTime': '2030-01-01T00:00:00Z'}, 'Bool': {'aws:SecureTransport': 'true'}}
        self.bootstrap = profile.document([
            dict(profile.statement('sts:AssumeRole', self.arn, conditions), Sid='AssumeFactoryRunnerOnly'),
            {'Sid': 'DenyDirectAwsUse', 'Effect': 'Deny', 'NotAction': 'sts:AssumeRole', 'Resource': '*'},
            {'Sid': 'DenyOtherRoles', 'Effect': 'Deny', 'Action': 'sts:AssumeRole', 'NotResource': self.arn}])
        trust_conditions = copy.deepcopy(conditions)
        trust_conditions['ArnEquals'] = {'aws:PrincipalArn': 'arn:aws:iam::123456789012:user/bootstrap'}
        self.trust = profile.document([{'Sid': 'TrustBootstrapUserOnly', 'Effect': 'Allow', 'Principal': {'AWS': 'arn:aws:iam::123456789012:root'},
                                       'Action': 'sts:AssumeRole', 'Condition': trust_conditions}])
        self.args = [self.config, self.baseline, self.boundary, self.bootstrap, self.trust]
        self.result = profile.render(*self.args)

    def test_preserves_dns_expiry_and_input_documents(self):
        original = copy.deepcopy(self.args)
        self.assertEqual(self.result['runner-dns-baseline.json'], self.baseline)
        for guard in self.baseline['Statement']:
            self.assertIn(guard, self.result['runner-boundary.json']['Statement'])
        profile.render(*self.args)
        self.assertEqual(self.args, original)
        for statement in self.result['runner-boundary.json']['Statement']:
            self.assertNotIn('Sid', statement)

    def test_iam_exception_only_project_roles_and_lambda(self):
        boundary = self.result['runner-boundary.json']['Statement']
        broad = next(s for s in boundary if 'NotAction' in s and s['Effect'] == 'Allow')
        self.assertIn('iam:*', broad['NotAction'])
        denied_elsewhere = next(s for s in boundary if s.get('Action') == 'iam:*' and 'NotResource' in s)
        self.assertEqual(denied_elsewhere['NotResource'], 'arn:aws:iam::123456789012:role/factory/' + profile.PROJECT + '/' + profile.ENVIRONMENT + '/*')
        role_policies = [s for k,p in self.result.items() if k.startswith('runner-app-') for s in p['Statement']]
        create = next(s for s in role_policies if s['Action'] == 'iam:CreateRole')
        self.assertEqual(create['Condition']['StringEquals']['iam:PermissionsBoundary'], 'arn:aws:iam::123456789012:policy/EngineeringFactoryAppBoundary')
        passed = next(s for s in role_policies if s['Action'] == 'iam:PassRole')
        self.assertEqual(passed['Condition']['StringEquals']['iam:PassedToService'], 'lambda.amazonaws.com')
        self.assertNotIn('iam:UpdateAssumeRolePolicy', json.dumps(role_policies))
        self.assertNotIn('iam:PutRolePolicy', json.dumps(role_policies))

    def test_tag_sessions_require_exact_source_tags_and_reject_arn_metacharacters(self):
        statement = self.result['runner-trust.json']['Statement'][1]
        self.assertEqual(statement['Condition']['ArnEquals'], self.trust['Statement'][0]['Condition']['ArnEquals'])
        self.assertEqual(statement['Condition']['StringLike']['sts:RoleSessionName'], 'factory-*')
        tags = next(s for s in self.result['bootstrap-policy.json']['Statement'] if s.get('Action') == 'sts:TagSession' and s['Effect'] == 'Allow')
        self.assertIn('aws:RequestTag/factory:project-id', tags['Condition']['StringLike'])
        self.assertIn('sts:RoleSessionName', tags['Condition']['StringLike'])
        deny = self.result['bootstrap-policy.json']['Statement'][-2]
        self.assertEqual(deny['Effect'], 'Deny')
        self.assertIn('*${*}*', deny['Condition']['StringLike']['aws:RequestTag/factory:project-id'])

    def test_no_unbounded_management_and_managed_policy_quotas(self):
        self.assertLessEqual(len(json.dumps(self.result['bootstrap-policy.json'], separators=(',', ':'))), 2048)
        for name, policy in self.result.items():
            if name not in ('runner-trust.json', 'bootstrap-policy.json', 'runner-dns-baseline.json'):
                self.assertLessEqual(len(json.dumps(policy, separators=(',', ':'))), 6144)
            if name.startswith('runner-app-'):
                for s in policy['Statement']:
                    if s['Effect'] != 'Allow' or s['Action'] == ['sts:GetCallerIdentity']:
                        continue
                    self.assertNotEqual(s['Resource'], '*')
                    self.assertIn(profile.PROJECT, json.dumps(s['Resource']))
        guard = self.result['app-execution-boundary.json']['Statement'][-2]
        self.assertEqual(guard['Effect'], 'Deny')
        self.assertIn('*${*}*', guard['Condition']['StringLike']['aws:PrincipalTag/factory:project-id'])
        for item in self.result['app-execution-policy.json']['Statement']:
            if item['Resource'] != '*':
                self.assertIn('aws:PrincipalArn', item['Condition']['ArnLike'])
                self.assertIn(profile.ENVIRONMENT, item['Condition']['ArnLike']['aws:PrincipalArn'])
        app = json.dumps([s.get('Action') for s in self.result['app-execution-boundary.json']['Statement']])
        for forbidden in ('iam:', 'route53:', 'CreateFunction', 'DeleteTable', 'PutBucketPolicy', 'AssumeRole'):
            self.assertNotIn(forbidden, app)

    def test_execution_conditions_cannot_mutate_runner_grants(self):
        statements = [s for name, policy in self.result.items() if name.startswith('runner-app-') for s in policy['Statement']]
        object_grant = next(s for s in statements if s['Effect'] == 'Allow' and isinstance(s['Action'], list) and 's3:PutObject' in s['Action'])
        self.assertNotIn('ArnLike', object_grant['Condition'])
        self.assertEqual(object_grant['Condition']['StringEquals']['s3:ResourceAccount'], self.config['account_id'])

    def test_missing_bootstrap_guards_are_rejected(self):
        for sid in ('AssumeFactoryRunnerOnly', 'DenyDirectAwsUse', 'DenyOtherRoles'):
            changed = copy.deepcopy(self.bootstrap)
            changed['Statement'] = [s for s in changed['Statement'] if s.get('Sid') != sid]
            with self.assertRaises(ValueError):
                profile.render(self.config, self.baseline, self.boundary, changed, self.trust)

    def test_rejects_unexpected_existing_boundary_and_trust(self):
        self.boundary['Statement'][1]['Action'].remove('iam:*')
        with self.assertRaises(ValueError):
            profile.render(*self.args)
        self.setUp()
        self.trust['Statement'][0]['Condition']['ArnEquals']['aws:PrincipalArn'] = 'arn:aws:iam::123456789012:user/other'
        with self.assertRaises(ValueError):
            profile.render(*self.args)


if __name__ == '__main__':
    unittest.main()
