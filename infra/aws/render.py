#!/usr/bin/env python3
"""Prepare general application permissions with immutable AWS control-plane guards."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/lib"))
from dns_records import name as dns_name, target as dns_target

TAG_KEYS = ('project-id', 'environment', 'owner', 'managed-by', 'source-repo', 'source-commit',
            'created-by', 'created-at', 'creation-run-id', 'last-run-id', 'last-source-commit',
            'provenance-version', 'expires-at')
PROJECT = '${aws:PrincipalTag/factory:project-id}'
ENVIRONMENT = '${aws:PrincipalTag/factory:environment}'
SCOPE = '${aws:PrincipalTag/factory:s}'
ADMIN_ACTIONS = ('iam:*', 'organizations:*', 'account:*', 'account-access:*', 'sso:*', 'sso-directory:*',
                 'identitystore:*', 'rolesanywhere:*', 'aws-portal:*', 'billing:*', 'budgets:*', 'payments:*', 'tax:*')


def document(statements):
    return {'Version': '2012-10-17', 'Statement': copy.deepcopy(statements)}


def statement(actions, resources, condition=None, effect='Allow', **extra):
    result = {'Effect': effect, 'Action': copy.deepcopy(actions), 'Resource': copy.deepcopy(resources)}
    if condition:
        result['Condition'] = copy.deepcopy(condition)
    return dict(result, **extra)


def context():
    return {'StringEquals': {'aws:PrincipalTag/factory:managed-by': 'engineering-factory'},
            'Null': {'aws:PrincipalTag/factory:project-id': 'false', 'aws:PrincipalTag/factory:environment': 'false'},
            'StringLike': {'aws:PrincipalTag/factory:project-id': '????????-????-????-????-????????????'}}


def creation():
    result = context()
    result['StringEquals'].update({'aws:RequestTag/factory:managed-by': 'engineering-factory',
        'aws:RequestTag/factory:project-id': PROJECT, 'aws:RequestTag/factory:environment': ENVIRONMENT,
        'aws:RequestTag/factory:provenance-version': '1', 'aws:RequestTag/factory:s': SCOPE})
    result['StringLike'].update({'aws:RequestTag/factory:' + key: '?*' for key in TAG_KEYS})
    return result


def read_json(path):
    return json.loads(Path(path).read_text())


def compact(policy):
    return json.dumps(policy, separators=(',', ':'), sort_keys=True).encode()


def protected_resources(config):
    resources = config['protected_resource_arns']
    if not isinstance(resources, list) or any(not isinstance(value, str) or not re.fullmatch(r'arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:[A-Za-z0-9_./:+=,@-]+', value)
            or value.split(':')[2] in ('iam', 'route53', 'route53domains')
            or value.split(':')[4] not in ('', config['account_id']) for value in resources):
        raise ValueError('Protected resources must be exact commercial-account resource ARNs; DNS/IAM use their own envelopes')
    # A global service deny already protects these exact ARNs; avoid duplicating them in a size-limited boundary.
    denied_services = {action.split(':')[0] for action in ADMIN_ACTIONS if action != 'iam:*'}
    result = {value for value in resources if value.split(':')[2] not in denied_services}
    for value in resources:
        if value.startswith('arn:aws:s3:::') and '/' not in value.split(':::', 1)[1]:
            result.add(value + '/*')
        if value.startswith('arn:aws:lambda:') and ':function:' in value and len(value.split(':')) == 7:
            result.add(value + ':*')
    return sorted(result)


def iam_envelope(app_role, app_boundary):
    paths = [app_role.replace(':role/', ':' + kind + '/') for kind in ('role', 'instance-profile', 'policy')]
    return [
        {'Effect': 'Deny', 'Action': 'iam:*', 'NotResource': paths},
        statement(['iam:CreateRole', 'iam:PutRolePermissionsBoundary'], '*',
                  {'ArnNotEquals': {'iam:PermissionsBoundary': app_boundary}}, effect='Deny'),
        statement('iam:DeleteRolePermissionsBoundary', '*', effect='Deny'),
    ]


def dns_permissions(baseline, config=None):
    original = next(s for s in baseline['Statement'] if s.get('Sid') == 'CreateNamesInReservedFactoryNamespace')
    if (original.get('Effect') != 'Allow' or original.get('Action') != 'route53:ChangeResourceRecordSets'
            or not isinstance(original.get('Resource'), str)
            or not re.fullmatch(r'arn:aws:route53:::hostedzone/[A-Z0-9]+', original['Resource'])):
        raise ValueError('Expected one exact approved hosted zone')
    condition = original['Condition']
    old = condition['ForAllValues:StringLike']['route53:ChangeResourceRecordSetsNormalizedRecordNames']
    if not isinstance(old, list):
        old = [old]
    if len(old) != 1 or not old[0].startswith('factory-*.') or '*' in old[0][len('factory-*.'):]:
        raise ValueError('Expected one original reserved DNS domain')
    suffix = old[0][len('factory-*'):]
    name = 'factory-' + SCOPE + '-r-*' + suffix
    names = 'route53:ChangeResourceRecordSetsNormalizedRecordNames'
    core = next(s for s in baseline['Statement'] if s.get('Sid') == 'DenyCoreNamesAndReservedSubtrees')
    if (core.get('Effect') != 'Deny' or core.get('Action') != 'route53:ChangeResourceRecordSets'
            or core.get('Resource') != original['Resource'] or not core.get('Condition', {}).get('ForAnyValue:StringLike')):
        raise ValueError('Expected original explicit core-record denial')
    change = statement('route53:ChangeResourceRecordSets', original['Resource'], {
        'ForAllValues:StringLike': {names: [name, '*.' + name]},
        'Null': {names: 'false'}})
    reads = statement(['route53:GetHostedZone', 'route53:ListResourceRecordSets', 'route53:GetChange'],
                      [original['Resource'], 'arn:aws:route53:::change/*'])
    if config is not None:
        required = {'mode', 'zone_id', 'zone_name', 'protected_record_names', 'release_protected_subtrees'}
        if not isinstance(config, dict) or set(config) != required or config['mode'] != 'application-records-v1':
            raise ValueError('Explicit application-records-v1 DNS configuration is required')
        dns_target(config['zone_id'], config['zone_name'])
        if (config['zone_name'] != suffix[1:] or original['Resource'] != 'arn:aws:route53:::hostedzone/' + config['zone_id']):
            raise ValueError('DNS target must match the retained baseline zone and domain')
        protected = config['protected_record_names']
        released = config['release_protected_subtrees']
        if (not isinstance(protected, list) or not protected or len(set(protected)) != len(protected)
                or not isinstance(released, list) or len(set(released)) != len(released)):
            raise ValueError('Provide explicit exact protected inventory and released baseline subtrees')
        for value in protected:
            if dns_name(value, record=True) != value or not (value == config['zone_name'] or value.endswith(suffix)):
                raise ValueError('Protected DNS inventory must contain normalized exact in-zone names')
        original_names = core['Condition']['ForAnyValue:StringLike'].get(names)
        if (set(core['Condition']) != {'ForAnyValue:StringLike'}
                or set(core['Condition']['ForAnyValue:StringLike']) != {names}
                or not isinstance(original_names, list) or not original_names):
            raise ValueError('Expected explicit original protected DNS names')
        for value in original_names:
            dns_name(value[2:] if value.startswith('*.') else value, record=True)
            if '*' in value.removeprefix('*.') or '?' in value or not (value == config['zone_name'] or value.endswith(suffix)):
                raise ValueError('Unrecognized retained DNS protection')
        if (config['zone_name'] not in protected or any(value not in protected for value in original_names if not value.startswith('*.'))
                or any(not isinstance(value, str) or not value.startswith('*.') or value not in original_names
                       or value[2:] not in protected for value in released)):
            raise ValueError('Retain all exact core names and explicitly acknowledge each released subtree with its protected parent')
        # Deny literal wildcard records: Route53 normalizes '*' to the literal octal escape \052.
        deny_names = sorted(set(protected + [value for value in original_names if value not in released] + [r'*\052*']))
        core = statement('route53:ChangeResourceRecordSets', original['Resource'],
                         {'ForAnyValue:StringLike': {names: deny_names}}, effect='Deny')
        types = 'route53:ChangeResourceRecordSetsRecordTypes'
        change = statement('route53:ChangeResourceRecordSets', original['Resource'], {
            'ForAllValues:StringLike': {names: '*' + suffix},
            'ForAllValues:StringNotEquals': {types: ['NS', 'SOA', 'DS']},
            'Null': {names: 'false', types: 'false'}})
    return [reads, change, copy.deepcopy(core)]


def boundary_dns(dns, config):
    if config is None:
        return copy.deepcopy(dns)
    reads, change, core = copy.deepcopy(dns)
    key = 'route53:ChangeResourceRecordSetsNormalizedRecordNames'
    patterns = core['Condition']['ForAnyValue:StringLike'][key]
    # The positive child-zone condition already excludes apex. Retained '*.' subtrees
    # subsume exact children; preserve full private inventory and the explicit inline Deny.
    exclusions = [value for value in patterns if value != config['zone_name'] and not any(
        other.startswith('*.') and value != other and value.endswith(other[1:]) for other in patterns)]
    change['Condition']['ForAllValues:StringNotLike'] = {key: exclusions}
    # This is the only DNS Allow in each boundary; broad NotAction excludes all DNS.
    # Excluding protected names here therefore has the same boundary ceiling as Deny.
    return [reads, change]


def delegation_guards(account, protected):
    prefix = 'factory-' + SCOPE + '-r-*'
    scoped = [f'arn:aws:{service}:*:{account}:*/{prefix}' for service in ('cloudformation', 'ecs', 'codebuild', 'ssm')] + [
              f'arn:aws:lambda:*:{account}:function:{prefix}',
              f'arn:aws:states:*:{account}:stateMachine:{prefix}',
              f'arn:aws:states:*:{account}:execution:{prefix}:*']
    operations = ['cloudformation:*teStack*', 'cloudformation:*ChangeSet', 'cloudformation:*Rollback*', 'cloudformation:Cancel*', 'cloudformation:Set*', 'cloudformation:Signal*',
        'ecs:Create*', 'ecs:Update*', 'ecs:Delete*', 'ecs:Register*', 'ecs:Deregister*',
        'ecs:Put*', 'ecs:RunTask', 'ecs:StartTask', 'ecs:Stop*', 'ecs:ExecuteCommand',
        'lambda:*Function', 'lambda:UpdateFunction*', 'lambda:InvokeFunction*',
        'lambda:*Permission', 'lambda:PublishVersion', 'lambda:*Alias', 'lambda:PutFunction*',
        'codebuild:Create*', 'codebuild:Update*', 'codebuild:Start*', 'codebuild:Retry*', 'codebuild:Delete*',
        'states:*teStateMachine*', 'states:*Execution',
        'ssm:*teDocument*', 'ssm:ModifyDocumentPermission', 'ssm:StartAutomationExecution']
    def deny(actions, condition=None, resources='*', **extra):
        item = statement(actions, resources, condition, effect='Deny', **extra)
        if 'NotResource' in item:
            item.pop('Resource')
        return item
    result = [deny(operations, NotResource=scoped),
        deny('autoscaling:*', {'Bool': {'autoscaling:LaunchTemplateVersionSpecified': 'false'}}),
        deny('lambda:*ateEventSourceMapping',
             {'ArnNotLike': {'lambda:FunctionArn': f'arn:aws:lambda:*:{account}:function:{prefix}'}}),
        deny(['ecs:RunTask', 'ecs:StartTask', 'ecs:*Service', 'ecs:*TaskSet'], {'ArnNotLike': {'ecs:cluster': f'arn:aws:ecs:*:{account}:cluster/{prefix}'}}),
        deny(['ssm:SendCommand', 'ssm:StartSession'], {'StringNotEquals': {'ssm:resourceTag/factory:s': SCOPE}},
             [f'arn:aws:ec2:*:{account}:instance/*', f'arn:aws:ssm:*:{account}:managed-instance/*']),
        deny(['servicecatalog:ProvisionProduct', 'servicecatalog:CreateConstraint'],
             {'StringNotEquals': {'aws:ResourceTag/factory:s': SCOPE}}, f'arn:aws:catalog:*:{account}:product/*'),
        deny('sts:*'),
        deny(['autoscaling:StartInstanceRefresh', 'cloudformation:*OrganizationsAccess', 'servicecatalog:*OrganizationsAccess',
              'servicecatalog:UpdateConstraint', 'servicecatalog:UpdateProvisionedProduct',
              'servicecatalog:ExecuteProvisionedProduct*',
              'ssm:CreateAssociation*', 'ssm:UpdateAssociation', 'ssm:StartAssociationsOnce',
              'ssm:RegisterTaskWithMaintenanceWindow', 'ssm:UpdateMaintenanceWindowTask'])]
    if protected:
        result.append(deny('*', resources=protected))
    return result


def strip_sids(policy):
    """Coalesce only identical envelopes: their Action alternatives are an exact union."""
    result = copy.deepcopy(policy)
    grouped = {}
    statements = []
    for item in result['Statement']:
        item.pop('Sid', None)
        for key in ('Action', 'NotAction', 'Resource', 'NotResource'):
            if isinstance(item.get(key), list) and len(item[key]) == 1:
                item[key] = item[key][0]
        if 'Action' not in item:
            statements.append(item)
            continue
        signature = json.dumps({k: v for k, v in item.items() if k != 'Action'}, sort_keys=True)
        if signature not in grouped:
            grouped[signature] = item
            statements.append(item)
            continue
        previous = grouped[signature]
        actions = previous['Action'] if isinstance(previous['Action'], list) else [previous['Action']]
        extra = item['Action'] if isinstance(item['Action'], list) else [item['Action']]
        previous['Action'] = list(dict.fromkeys(actions + extra))
    result['Statement'] = statements
    return result


def render(config, baseline, boundary, bootstrap, trust):
    account = config['account_id']
    role, user = config['runner_role'], config['bootstrap_user']
    if not re.fullmatch(r'[0-9]{12}', account) or account == '000000000000':
        raise ValueError('A real private commercial account ID is required')
    if not all(re.fullmatch(r'[A-Za-z0-9+=,.@_-]{1,64}', value) for value in (role, user)):
        raise ValueError('Invalid role or user name')
    names = [config[key] for key in ('app_boundary_name', 'app_policy_name')]
    if not all(re.fullmatch(r'EngineeringFactory[A-Za-z0-9-]+', name) for name in names) or names[0] == names[1]:
        raise ValueError('Distinct fixed managed policy names are required')
    count, limit = config['runner_managed_policy_count'], config['runner_managed_policy_limit']
    if type(count) is not int or type(limit) is not int or not 0 <= count < limit <= 25:
        raise ValueError('Provide observed runner attachment count and quota with capacity for one policy')
    protected = protected_resources(config)
    arn = 'arn:aws:'
    role_arn = f'{arn}iam::{account}:role/{role}'
    app_role = f'{arn}iam::{account}:role/factory/{SCOPE}/*'
    app_boundary, app_policy = [f'{arn}iam::{account}:policy/{name}' for name in names]
    admin = [s for s in boundary['Statement'] if s.get('Sid') == 'DenyAccountAndIdentityAdministration']
    if len(admin) != 1 or admin[0].get('Effect') != 'Deny' or not set(ADMIN_ACTIONS).issubset(admin[0].get('Action', [])):
        raise ValueError('Expected explicit account/IAM boundary guard')
    admin = copy.deepcopy(admin[0])
    admin['Action'].remove('iam:*')
    dns = dns_permissions(baseline, config.get('dns'))
    guards = delegation_guards(account, protected)
    broad = {'Effect': 'Allow', 'NotAction': ['route53:*', 'route53domains:*'], 'Resource': '*', 'Condition': context()}
    allows = [broad, *boundary_dns(dns, config.get('dns'))]
    iam_guards = iam_envelope(app_role, app_boundary)
    # Resource vendors are literal and disjoint: the union cannot make an IAM ARN
    # exempt an engine action, or make an engine ARN exempt an IAM action.
    namespace = {'Effect': 'Deny', 'Action': ['iam:*'] + guards[0]['Action'],
                 'NotResource': iam_guards[0]['NotResource'] + guards[0]['NotResource']}
    iam_guards = iam_guards[1:]
    guards = [namespace] + guards[1:]
    # Default values keep the negative comparison valid even when canonical tags are absent.
    # Missing scope also makes StringNotEquals true, so this is an explicit fail-closed deny.
    relation = statement('*', '*', {'StringNotEquals': {'aws:PrincipalTag/factory:s':
        "${aws:PrincipalTag/factory:project-id, '/'}-${aws:PrincipalTag/factory:environment, '/'}"}}, effect='Deny')
    allows[0]['Condition'] = {'StringLike': {'aws:PrincipalTag/factory:project-id': '????????-????-????-????-????????????'}}
    transport = [s for s in baseline['Statement'] if s.get('Sid') == 'DenyInsecureTransport']
    expiry = [s for s in baseline['Statement'] if s.get('Sid') == 'DenyAfterExpiry']
    if len(transport) != 1 or len(expiry) != 1:
        raise ValueError('Expected original TLS and provisioning expiry protections')
    new_boundary = document([*allows, relation, admin, *iam_guards, *guards, *transport, *expiry])
    # A named-role existence lookup can be evaluated before a stored path exists.
    # Only the runner gets this root-name exception; its paired identity Deny
    # below closes every operation except these two reads on that same ARN.
    # Install that Deny before expanding the boundary; reverse this order on rollback.
    role_lookup = f'{arn}iam::{account}:role/factory-{SCOPE}-r-*'
    next(s for s in new_boundary['Statement'] if 'NotResource' in s)['NotResource'].append(role_lookup)
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
    merge_conditions(tag_condition, tag_session_conditions(assume['Condition']))
    new_bootstrap['Statement'].append(statement('sts:TagSession', role_arn, tag_condition))
    # Prevent wildcard/path substitution into project-namespaced Resource ARNs.
    for key in ('project-id', 'environment'):
        new_bootstrap['Statement'].append(statement('sts:TagSession', role_arn, {
            'StringLike': {'aws:RequestTag/factory:' + key: ['*${*}*', '*${?}*', '*/*', '*:*', '*${$}*', '*\\*', '*--*', '*-', 'r', 'r-*', '*-r', '*-r-*']}
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
    tagged_trust['Condition'] = tag_session_conditions(tagged_trust['Condition'])
    session_condition = creation_session_condition()
    # Exact bootstrap identity enforces the UUID-shaped value and excludes ARN metacharacters.
    # Trust policies reject wildcard-only project values in an Allow, so retain required keys here.
    session_condition.pop('StringLike')
    merge_conditions(tagged_trust['Condition'], session_condition)
    new_trust['Statement'].append(tagged_trust)
    app_guard = statement('*', '*', {'ArnNotLike': {'aws:PrincipalArn': app_role}}, effect='Deny')
    metachar = [statement('*', '*', {'StringLike': {'aws:PrincipalTag/factory:' + key:
        ['*${*}*', '*${?}*', '*--*', '*-r', '*-r-*']}}, effect='Deny') for key in ('s',)]
    deployed_allows = copy.deepcopy(allows)
    deployed_allows[0].pop('Condition')
    deployed = document([*deployed_allows, relation, admin, *iam_guards, *guards, *transport, app_guard, *metachar])
    identity_broad = copy.deepcopy(broad)
    identity_broad['Condition'] = context()
    identity_broad['NotAction'] += ['iam:CreateRole', 'iam:CreateInstanceProfile', 'iam:CreatePolicy']
    create_paths = [app_role.replace(':role/', ':' + kind + '/') for kind in ('role', 'instance-profile', 'policy')]
    identity = document([identity_broad, *[s for s in dns if s['Effect'] == 'Allow'],
        statement(['iam:CreateRole', 'iam:CreateInstanceProfile', 'iam:CreatePolicy'], create_paths, creation())])
    runner_identity = copy.deepcopy(identity)
    runner_identity['Statement'].append({'Effect': 'Deny', 'NotAction': ['iam:GetRole', 'iam:GetRolePolicy'],
                                         'Resource': role_lookup})
    result = {'runner-boundary.json': strip_sids(new_boundary), 'runner-dns-baseline.json': copy.deepcopy(baseline),
        'runner-dns-policy.json': document([*dns, *transport, *expiry]),
        'bootstrap-policy.json': new_bootstrap, 'runner-trust.json': new_trust,
        'app-execution-boundary.json': strip_sids(deployed), 'app-execution-policy.json': strip_sids(identity),
        'runner-app-1.json': strip_sids(runner_identity)}
    for name, policy in result.items():
        for item in policy['Statement']:
            for field in ('Resource', 'NotResource'):
                values = item.get(field, [])
                for value in values if isinstance(values, list) else [values]:
                    if value != '*' and (not value.startswith('arn:aws:') or not re.fullmatch(r'[a-z0-9-]+', value.split(':')[2])):
                        raise ValueError('Resource ARN vendors must be literal, not wildcard expressions')
        maximum = 2048 if name == 'bootstrap-policy.json' else 6144
        if len(compact(policy)) > maximum:
            raise ValueError('Rendered policy exceeds its quota; never drop protections to fit: ' + name)
    return result

def tag_session_conditions(conditions):
    """RoleSessionName applies to AssumeRole, not its separate TagSession authorization."""
    result = copy.deepcopy(conditions)
    for operator in list(result):
        result[operator].pop('sts:RoleSessionName', None)
        if not result[operator]:
            del result[operator]
    return result


def merge_conditions(target, source):
    for operator, values in source.items():
        target.setdefault(operator, {}).update(copy.deepcopy(values))


def creation_session_condition():
    return {'StringEquals': {'aws:RequestTag/factory:managed-by': 'engineering-factory',
                'aws:RequestTag/factory:s': '${aws:RequestTag/factory:project-id}-${aws:RequestTag/factory:environment}'},
            'StringLike': {'aws:RequestTag/factory:project-id': '????????-????-????-????-????????????',
                           'aws:RequestTag/factory:environment': '?*'},
            'ForAllValues:StringEquals': {'aws:TagKeys': ['factory:managed-by', 'factory:project-id', 'factory:environment', 'factory:s']},
            'Null': {'aws:TagKeys': 'false'}}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'baseline', 'boundary', 'bootstrap', 'trust', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    inputs = {key: getattr(args, key) for key in ('config', 'baseline', 'boundary', 'bootstrap', 'trust')}
    data = {key: read_json(value) for key, value in inputs.items()}
    result = render(*(data[key] for key in inputs))
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, policy in result.items():
        with os.fdopen(os.open(args.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(compact(policy) + b'\n')
    review = dict(schema=3, dns_contract=data['config'].get('dns', {'mode': 'retained-factory-namespace'}), renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256={key: hashlib.sha256(value.read_bytes()).hexdigest() for key, value in inputs.items()},
        policies={name: dict(chars=len(compact(policy)), sha256=hashlib.sha256(compact(policy)+b'\n').hexdigest()) for name, policy in result.items()},
        runner_managed_policy_count=data['config']['runner_managed_policy_count'],
        runner_managed_policy_limit=data['config']['runner_managed_policy_limit'], planned_new_runner_attachments=1,
        runner_role_lookup_guard='Install runner-app-1 explicit root-role mutation Deny before runner boundary update; rollback boundary first',
        activation_gates=['live policy/trust comparison', 'complete proposed policy-set validation/simulation',
            'protected and delegated-resource inventory coverage review', 'actual STS/service-context checks',
            'default policy versions, attachments and boundary readback'],
        scope='General cross-service application access; no universal new-resources-only or all-service ABAC guarantee')
    with os.fdopen(os.open(args.output / 'review-manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(review, stream, sort_keys=True)
        stream.write('\n')
    print('Rendered private general application policies. No AWS changes made; administrator activation gates remain.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit('Policy preparation failed; inspect private inputs/quotas without exposing their values.') from None
