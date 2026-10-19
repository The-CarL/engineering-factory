#!/usr/bin/env python3
"""Render a reusable project-scoped AWS application profile. Never applies policies."""
import argparse
import copy
import json
from pathlib import Path
import re

TAG_KEYS = (
    'project-id', 'environment', 'owner', 'managed-by', 'source-repo', 'source-commit',
    'created-by', 'created-at', 'creation-run-id', 'last-run-id', 'last-source-commit',
    'provenance-version', 'expires-at',
)
ORIGINAL_TAGS = ['factory:' + k for k in TAG_KEYS if k not in ('last-run-id', 'last-source-commit', 'expires-at')]
PROJECT = '${aws:PrincipalTag/factory:project-id}'
ENVIRONMENT = '${aws:PrincipalTag/factory:environment}'


def document(statements):
    return {'Version': '2012-10-17', 'Statement': statements}


def statement(actions, resources, condition=None, effect='Allow', **extra):
    result = {'Effect': effect, 'Action': actions, 'Resource': resources}
    if condition:
        result['Condition'] = condition
    return dict(result, **extra)


def context():
    return {'StringEquals': {'aws:PrincipalTag/factory:managed-by': 'engineering-factory'},
            'Null': {'aws:PrincipalTag/factory:project-id': 'false', 'aws:PrincipalTag/factory:environment': 'false'},
            'StringLike': {'aws:PrincipalTag/factory:project-id': '????????-????-????-????-????????????'}}


def creation():
    result = context()
    result['StringEquals'].update({
        'aws:RequestTag/factory:managed-by': 'engineering-factory',
        'aws:RequestTag/factory:project-id': PROJECT,
        'aws:RequestTag/factory:environment': ENVIRONMENT,
        'aws:RequestTag/factory:provenance-version': '1',
    })
    result['StringLike'].update({'aws:RequestTag/factory:' + k: '?*' for k in TAG_KEYS})
    return result


def owned():
    result = context()
    result['StringEquals'].update({
        'aws:ResourceTag/factory:managed-by': 'engineering-factory',
        'aws:ResourceTag/factory:project-id': PROJECT,
        'aws:ResourceTag/factory:environment': ENVIRONMENT,
    })
    return result


def read_json(path):
    return json.loads(Path(path).read_text())


def render(config, baseline, boundary, bootstrap, trust):
    account = config['account_id']
    role, user = config['runner_role'], config['bootstrap_user']
    if not re.fullmatch(r'[0-9]{12}', account) or account == '000000000000':
        raise ValueError('A real private commercial account ID is required')
    if not all(re.fullmatch(r'[A-Za-z0-9+=,.@_-]{1,64}', value) for value in (role, user)):
        raise ValueError('Invalid role or user name')
    names = [config[key] for key in ('app_boundary_name', 'app_policy_name')]
    if not all(re.fullmatch(r'EngineeringFactory[A-Za-z0-9-]+', name) for name in names) or names[0] == names[1]:
        raise ValueError('Distinct dedicated managed policy names are required')
    arn = 'arn:aws:'
    role_arn = f'{arn}iam::{account}:role/{role}'
    app_role = f'{arn}iam::{account}:role/factory/{PROJECT}/{ENVIRONMENT}/*'
    app_boundary, app_policy = [f'{arn}iam::{account}:policy/{name}' for name in names]
    prefix = 'factory-' + PROJECT + '-' + ENVIRONMENT + '-*'
    resources = {
        'lambda': [f'{arn}lambda:*:{account}:function:{prefix}'],
        'dynamodb': [f'{arn}dynamodb:*:{account}:table/{prefix}'],
        'sqs': [f'{arn}sqs:*:{account}:{prefix}'],
        'sns': [f'{arn}sns:*:{account}:{prefix}'],
        'secretsmanager': [f'{arn}secretsmanager:*:{account}:secret:{prefix}'],
        'logs': [f'{arn}logs:*:{account}:log-group:{prefix}', f'{arn}logs:*:{account}:log-group:/aws/lambda/{prefix}'],
    }
    buckets = [f'{arn}s3:::factory-{PROJECT}-{ENVIRONMENT}-*']
    objects = [buckets[0] + '/*']
    creates = {
        'lambda': ['CreateFunction', 'TagResource'],
        'dynamodb': ['CreateTable', 'TagResource'],
        'sqs': ['CreateQueue', 'TagQueue'],
        'sns': ['CreateTopic', 'TagResource'],
        'secretsmanager': ['CreateSecret', 'TagResource'],
        'logs': ['CreateLogGroup', 'TagResource', 'TagLogGroup'],
    }
    actions = {
        'lambda': ['GetFunction', 'GetFunctionConfiguration', 'GetFunctionCodeSigningConfig', 'GetFunctionConcurrency',
                   'GetFunctionUrlConfig', 'GetPolicy', 'ListTags', 'ListVersionsByFunction', 'ListAliases',
                   'UpdateFunctionCode', 'UpdateFunctionConfiguration', 'DeleteFunction', 'InvokeFunction',
                   'PublishVersion', 'CreateAlias', 'UpdateAlias', 'DeleteAlias', 'GetAlias',
                   'PutFunctionConcurrency', 'DeleteFunctionConcurrency', 'CreateFunctionUrlConfig',
                   'UpdateFunctionUrlConfig', 'DeleteFunctionUrlConfig', 'AddPermission', 'RemovePermission'],
        'dynamodb': ['DescribeTable', 'DescribeTimeToLive', 'DescribeContinuousBackups', 'ListTagsOfResource',
                     'UpdateTable', 'DeleteTable', 'UpdateTimeToLive', 'UpdateContinuousBackups',
                     'GetItem', 'PutItem', 'UpdateItem', 'DeleteItem', 'Query', 'Scan', 'BatchGetItem', 'BatchWriteItem',
                     'ConditionCheckItem', 'DescribeStream', 'GetRecords', 'GetShardIterator'],
        'sqs': ['GetQueueUrl', 'GetQueueAttributes', 'ListQueueTags', 'SetQueueAttributes', 'DeleteQueue', 'PurgeQueue',
                'SendMessage', 'ReceiveMessage', 'DeleteMessage', 'ChangeMessageVisibility'],
        'sns': ['GetTopicAttributes', 'ListTagsForResource', 'SetTopicAttributes', 'DeleteTopic', 'Publish',
                'Subscribe', 'ListSubscriptionsByTopic'],
        'secretsmanager': ['DescribeSecret', 'GetSecretValue', 'ListSecretVersionIds', 'PutSecretValue',
                           'UpdateSecret', 'UpdateSecretVersionStage', 'DeleteSecret', 'RestoreSecret'],
        'logs': ['DescribeLogStreams', 'FilterLogEvents', 'ListTagsForResource',
                 'ListTagsLogGroup', 'PutRetentionPolicy', 'DeleteRetentionPolicy', 'DeleteLogGroup'],
    }
    grants = []
    for service, create_actions in creates.items():
        grants.append(statement([service + ':' + a for a in create_actions], resources[service], creation()))
        target = resources[service]
        grants.append(statement([service + ':' + a for a in actions[service]], target, owned()))
    # S3 bucket tags require ABAC enablement before ResourceTag works.
    # A UUID/environment namespace and fixed resource account enforce bootstrap isolation.
    s3_context = context()
    s3_context['StringEquals']['s3:ResourceAccount'] = account
    grants += [statement(['s3:CreateBucket', 's3:TagResource'], buckets, creation()),
               statement(['s3:GetBucketLocation', 's3:ListBucket', 's3:GetBucketTagging', 's3:ListTagsForResource',
                          's3:GetBucketAbac', 's3:PutBucketAbac', 's3:GetBucketVersioning', 's3:PutBucketVersioning',
                          's3:GetEncryptionConfiguration', 's3:PutEncryptionConfiguration',
                          's3:GetBucketPublicAccessBlock', 's3:PutBucketPublicAccessBlock',
                          's3:GetLifecycleConfiguration', 's3:PutLifecycleConfiguration',
                          's3:ListBucketMultipartUploads', 's3:DeleteBucket'], buckets, s3_context),
               statement(['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:GetObjectVersion', 's3:DeleteObjectVersion',
                          's3:AbortMultipartUpload', 's3:ListMultipartUploadParts'], objects, s3_context)]
    # Child streams have no independent provenance tags; their parent namespace is mandatory.
    streams = [r + ':log-stream:*' for r in resources['logs']]
    grants.append(statement(['logs:CreateLogStream', 'logs:PutLogEvents', 'logs:DeleteLogStream',
                             'logs:GetLogEvents'], streams, context()))
    tag_actions = ['lambda:TagResource', 'dynamodb:TagResource', 'sqs:TagQueue', 'sns:TagResource',
                   'secretsmanager:TagResource', 'logs:TagResource', 'logs:TagLogGroup', 'iam:TagRole', 's3:TagResource']
    tag_resources = sum(resources.values(), []) + buckets + [app_role]
    latest = owned()
    latest['ForAllValues:StringEquals'] = {'aws:TagKeys': ['factory:last-run-id', 'factory:last-source-commit', 'factory:expires-at']}
    latest['Null']['aws:TagKeys'] = 'false'
    grants.append(statement(tag_actions, tag_resources, latest))
    # Original provenance may be restated unchanged, never silently rewritten or removed.
    for key in ORIGINAL_TAGS:
        grants.append(statement(tag_actions, '*', {
            'Null': {'aws:ResourceTag/' + key: 'false', 'aws:RequestTag/' + key: 'false'},
            'StringNotEquals': {'aws:RequestTag/' + key: '${aws:ResourceTag/' + key + '}'},
        }, effect='Deny'))
    grants.append(statement(['lambda:UntagResource', 'dynamodb:UntagResource', 'sqs:UntagQueue', 'sns:UntagResource',
                             'secretsmanager:UntagResource', 'logs:UntagResource', 'logs:UntagLogGroup',
                             'iam:UntagRole', 's3:UntagResource', 's3:PutBucketTagging'], '*', effect='Deny'))
    create_role = creation()
    create_role['StringEquals']['iam:PermissionsBoundary'] = app_boundary
    grants.append(statement('iam:CreateRole', [app_role], create_role))
    grants.append(statement('iam:TagRole', [app_role], creation()))
    grants.append(statement(['iam:GetRole', 'iam:ListRolePolicies', 'iam:ListAttachedRolePolicies', 'iam:ListRoleTags',
                             'iam:DeleteRole'], [app_role], owned()))
    grants.append(statement(['iam:AttachRolePolicy', 'iam:DetachRolePolicy'], [app_role], {
        **owned(), 'ArnEquals': {'iam:PolicyARN': app_policy}}))
    grants.append(statement('iam:PassRole', [app_role], {
        **context(), 'StringEquals': {'aws:PrincipalTag/factory:managed-by': 'engineering-factory',
                                     'iam:PassedToService': 'lambda.amazonaws.com'}}))
    # No unrestricted service discovery reads. Exact names/ARNs are kept in private inventory.
    grants.append(statement(['sts:GetCallerIdentity'], '*'))
    # Split identity policies so no managed document exceeds AWS's 6144-character quota.
    chunks, current = [], []
    for item in grants:
        if len(json.dumps(document(current + [item]), separators=(',', ':'))) > 6000 and current:
            chunks.append(document(current)); current = []
        current.append(item)
    chunks.append(document(current))
    new_boundary = copy.deepcopy(boundary)
    admin = [s for s in new_boundary['Statement'] if s.get('Sid') == 'DenyAccountAndIdentityAdministration']
    if len(admin) != 1 or 'iam:*' not in admin[0]['Action']:
        raise ValueError('Expected existing explicit account/IAM boundary guard')
    admin[0]['Action'].remove('iam:*')
    approved_iam = ['iam:CreateRole', 'iam:TagRole', 'iam:GetRole', 'iam:ListRolePolicies', 'iam:ListAttachedRolePolicies',
                    'iam:ListRoleTags', 'iam:DeleteRole', 'iam:AttachRolePolicy', 'iam:DetachRolePolicy', 'iam:PassRole']
    broad = next(s for s in new_boundary['Statement'] if s.get('Effect') == 'Allow' and 'NotAction' in s)
    broad['NotAction'].append('iam:*')
    new_boundary['Statement'] += [
        statement([a for a in approved_iam if a != 'iam:PassRole'], [app_role], context()),
        statement('iam:PassRole', [app_role], {'StringEquals': {'iam:PassedToService': 'lambda.amazonaws.com',
                                                             'aws:PrincipalTag/factory:managed-by': 'engineering-factory'}}),
        {'Effect': 'Deny', 'Action': 'iam:*', 'NotResource': app_role},
        {'Effect': 'Deny', 'NotAction': approved_iam, 'Resource': app_role},
    ]
    # SIDs are diagnostic labels, not semantics. Remove to stay below the boundary quota.
    for item in new_boundary['Statement']:
        item.pop('Sid', None)
    if len(json.dumps(new_boundary, separators=(',', ':'))) > 6144:
        raise ValueError('Boundary exceeds AWS managed policy quota')
    required_bootstrap = ('AssumeFactoryRunnerOnly', 'DenyDirectAwsUse', 'DenyOtherRoles')
    for sid in required_bootstrap:
        if sum(s.get('Sid') == sid for s in bootstrap.get('Statement', [])) != 1:
            raise ValueError('Expected exactly one bootstrap protection: ' + sid)
    original_assume = next(s for s in bootstrap['Statement'] if s.get('Sid') == 'AssumeFactoryRunnerOnly')
    if original_assume.get('Action') != 'sts:AssumeRole' or original_assume.get('Effect') != 'Allow':
        raise ValueError('Unexpected bootstrap assumption grant')
    if any(s.get('Effect') == 'Allow' and s.get('Sid') != 'AssumeFactoryRunnerOnly' for s in bootstrap['Statement']):
        raise ValueError('Unexpected additional bootstrap grant')
    new_bootstrap = copy.deepcopy(bootstrap)
    for item in new_bootstrap['Statement']:
        if item.get('Sid') == 'DenyDirectAwsUse':
            if item['NotAction'] != 'sts:AssumeRole':
                raise ValueError('Unexpected bootstrap direct-use protection')
            item['NotAction'] = ['sts:AssumeRole', 'sts:TagSession']
        if item.get('Sid') == 'DenyOtherRoles':
            if item['NotResource'] != role_arn:
                raise ValueError('Unexpected bootstrap target')
            item['Action'] = ['sts:AssumeRole', 'sts:TagSession']
    tag_condition = creation_session_condition()
    assume = next(s for s in new_bootstrap['Statement'] if s.get('Sid') == 'AssumeFactoryRunnerOnly')
    if assume['Resource'] != role_arn:
        raise ValueError('Unexpected bootstrap runner target')
    merge_conditions(tag_condition, assume['Condition'])
    new_bootstrap['Statement'].append(statement('sts:TagSession', role_arn, tag_condition))
    # Prevent wildcard/path substitution into project-namespaced Resource ARNs.
    for key in ('project-id', 'environment'):
        new_bootstrap['Statement'].append(statement('sts:TagSession', role_arn, {
            'StringLike': {'aws:RequestTag/factory:' + key: ['*${*}*', '*${?}*', '*/*', '*:*', '*${$}*', '*\\*']}
        }, effect='Deny'))
    for item in new_bootstrap['Statement']:
        item.pop('Sid', None)
    if len(json.dumps(new_bootstrap, separators=(',', ':'))) > 2048:
        raise ValueError('Bootstrap exceeds IAM user inline-policy quota')
    new_trust = copy.deepcopy(trust)
    if len(new_trust['Statement']) != 1:
        raise ValueError('Unexpected runner trust statement count')
    base = new_trust['Statement'][0]
    if (base.get('Effect') != 'Allow' or base.get('Action') != 'sts:AssumeRole'
            or base.get('Principal') != {'AWS': f'{arn}iam::{account}:root'}):
        raise ValueError('Unexpected runner trust grant')
    if base['Condition']['ArnEquals']['aws:PrincipalArn'] != f'{arn}iam::{account}:user/{user}':
        raise ValueError('Unexpected runner trust source')
    tagged_trust = copy.deepcopy(base)
    tagged_trust['Sid'] = 'TrustBootstrapProjectTags'
    tagged_trust['Action'] = 'sts:TagSession'
    session_condition = creation_session_condition()
    # Exact bootstrap identity enforces the UUID-shaped value and excludes ARN metacharacters.
    # Trust policies reject wildcard-only project values in an Allow, so retain required keys here.
    session_condition.pop('StringLike')
    merge_conditions(tagged_trust['Condition'], session_condition)
    new_trust['Statement'].append(tagged_trust)
    data_actions = {
        'dynamodb': ['GetItem', 'PutItem', 'UpdateItem', 'DeleteItem', 'Query', 'Scan', 'BatchGetItem', 'BatchWriteItem', 'ConditionCheckItem', 'DescribeTable'],
        'sqs': ['GetQueueUrl', 'GetQueueAttributes', 'SendMessage', 'ReceiveMessage', 'DeleteMessage', 'ChangeMessageVisibility'],
        'sns': ['Publish'], 'secretsmanager': ['GetSecretValue', 'DescribeSecret'],
        'lambda': ['InvokeFunction'],
    }
    execution = [statement(['sts:GetCallerIdentity'], '*')]
    execution.append(statement([service + ':' + action for service, permitted in data_actions.items() for action in permitted],
                               [resource for service in data_actions for resource in resources[service]], owned()))
    execution += [statement(['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket'], objects + buckets, s3_context),
                  statement(['logs:CreateLogStream', 'logs:PutLogEvents'], streams, context())]
    # Role-session tags cannot silently redirect execution to a different project or environment.
    # PrincipalArn is the immutable IAM role ARN for assumed-role sessions, not a caller-supplied tag.
    for item in execution:
        if item['Resource'] != '*':
            item['Condition']['ArnLike'] = {'aws:PrincipalArn': app_role}
    execution_guards = [statement('*', '*', {
        'StringLike': {'aws:PrincipalTag/factory:' + key: ['*${*}*', '*${?}*', '*/*', '*:*', '*${$}*', '*\\*']}
    }, effect='Deny') for key in ('project-id', 'environment')]
    execution_boundary = document(copy.deepcopy(execution) + execution_guards)
    result = {'runner-boundary.json': new_boundary, 'runner-dns-baseline.json': copy.deepcopy(baseline),
              'bootstrap-policy.json': new_bootstrap, 'runner-trust.json': new_trust,
              'app-execution-boundary.json': execution_boundary, 'app-execution-policy.json': document(execution)}
    result.update({f'runner-app-{i + 1}.json': policy for i, policy in enumerate(chunks)})
    return result


def merge_conditions(target, source):
    for operator, values in source.items():
        target.setdefault(operator, {}).update(copy.deepcopy(values))


def creation_session_condition():
    return {'StringEquals': {'aws:RequestTag/factory:managed-by': 'engineering-factory'},
            'StringLike': {'aws:RequestTag/factory:project-id': '????????-????-????-????-????????????',
                           'aws:RequestTag/factory:environment': '?*'},
            'ForAllValues:StringEquals': {'aws:TagKeys': ['factory:managed-by', 'factory:project-id', 'factory:environment']},
            'Null': {key: 'false' for key in ('aws:RequestTag/factory:managed-by', 'aws:RequestTag/factory:project-id',
                                             'aws:RequestTag/factory:environment', 'aws:TagKeys')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'baseline', 'boundary', 'bootstrap', 'trust', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    if args.output.stat().st_mode & 0o077:
        raise ValueError('Output must be private')
    result = render(*(read_json(getattr(args, key)) for key in ('config', 'baseline', 'boundary', 'bootstrap', 'trust')))
    for name, policy in result.items():
        target = args.output / name
        with target.open('x') as stream:
            target.chmod(0o600)
            stream.write(json.dumps(policy, indent=2) + '\n')
    print('Rendered private policies. No AWS changes made. Validate and simulate before administrator apply.')


if __name__ == '__main__':
    main()
