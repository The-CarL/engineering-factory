#!/usr/bin/env python3
"""Run a normal AWS service command using only a verified assumed-role session."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from dns_records import configured as dns_configured
from runtime import Operation, Parser, base_env, cli, digest, event, known_credentials, load, project_scope, require, run


def execute(args):
    tools = load()
    from context import preflight
    preflight(tools)
    account, role, region = (os.environ.get('FACTORY_AWS_' + key, '') for key in ('ACCOUNT_ID', 'ROLE_NAME', 'REGION'))
    require(re.fullmatch(r'[0-9]{12}', account) and account != '000000000000'
            and re.fullmatch(r'[A-Za-z0-9+=,.@_-]{1,64}', role)
            and re.fullmatch(r'(?:us|eu|ap|sa|ca|me|af|il|mx)-(?:[a-z]+-)+[0-9]+', region) and not region.startswith(('us-gov-', 'us-iso')),
            'Set exact approved commercial AWS account, role name and region')
    dns = dns_configured(os.environ)
    duration = int(os.environ.get('FACTORY_AWS_SESSION_SECONDS', '900'))
    require(900 <= duration <= 3600, 'Requested AWS session must be 900..3600 seconds')
    command = list(args.command)
    if command[:1] == ['--']:
        command = command[1:]
    require(command, 'Specify an AWS service command or trusted --exec command')
    if args.exec:
        executable = Path(os.environ.get('FACTORY_AWS_EXECUTABLE', ''))
        expected_hash = os.environ.get('FACTORY_AWS_EXECUTABLE_SHA256', '')
        require(executable.is_absolute() and executable.is_file() and not executable.is_symlink()
                and re.fullmatch(r'[a-f0-9]{64}', expected_hash) and digest(executable.read_bytes()) == expected_hash
                and command[0] == str(executable), 'Trusted exec requires the exact privately reviewed executable and hash')
    else:
        require(len(command) >= 2 and re.fullmatch(r'[a-z][a-z0-9-]*', command[0]), 'Specify an AWS service and command')
    forbidden = ('--profile', '--endpoint-url', '--no-verify-ssl', '--debug', '--no-sign-request', '--ca-bundle',
                 '--region', '--cli-auto-prompt', '--cli-connect-timeout', '--cli-read-timeout')
    require(args.exec or not any(any(option.startswith(arg.split('=')[0]) for option in forbidden) for arg in command), 'AWS credential/endpoint/region/debug overrides are forbidden')
    require(args.exec or (command[0] not in ('configure', 'sso', 'sso-oidc', 'login', 'signin')
            and (command[0] != 'sts' or command[1] == 'get-caller-identity')), 'Alternate AWS credential/session flows are forbidden')
    bootstrap = {key: os.environ.get(key, '') for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN')}
    require(bootstrap['AWS_ACCESS_KEY_ID'] and bootstrap['AWS_SECRET_ACCESS_KEY'], 'Direct AWS bootstrap signing bindings are required')
    require(not any(value and value in arg for value in known_credentials() for arg in command), 'Credential argument rejected')
    tags = []
    scope = ''
    project, environment = os.environ.get('FACTORY_PROJECT_ID', ''), os.environ.get('FACTORY_ENVIRONMENT', '')
    if project or environment:
        scope = project_scope(project, environment)
        tags = ['--tags', 'Key=factory:managed-by,Value=engineering-factory',
                'Key=factory:project-id,Value=' + project, 'Key=factory:environment,Value=' + environment,
                'Key=factory:s,Value=' + scope]
    operation = Operation(args.record, args.output, 'AWS', json.dumps(command).encode())
    try:
        with tempfile.TemporaryDirectory(prefix='factory-aws-') as temporary:
            env = base_env(temporary)
            env.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull, BOTO_CONFIG=os.devnull,
                       AWS_EC2_METADATA_DISABLED='true', AWS_CLI_AUTO_PROMPT='off', AWS_PAGER='', AWS_MAX_ATTEMPTS='1',
                       AWS_RETRY_MODE='standard', AWS_REGION=region, AWS_DEFAULT_REGION=region)
            env.update({key: value for key, value in bootstrap.items() if value})
            session = 'factory-' + uuid.uuid4().hex[:24]
            expected = 'arn:aws:sts::' + account + ':assumed-role/' + role + '/' + session
            common = ['--region', region, '--no-cli-pager', '--output', 'json']
            response = json.loads(run([tools['aws'], 'sts', 'assume-role', '--role-arn',
                'arn:aws:iam::' + account + ':role/' + role, '--role-session-name', session,
                '--duration-seconds', str(duration), *tags, *common], env, 'AWS'))
            require(response['AssumedRoleUser']['Arn'] == expected, 'AssumeRole returned an unexpected identity')
            creds = response['Credentials']
            expiry = datetime.fromisoformat(creds['Expiration'].replace('Z', '+00:00'))
            remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
            require(30 < remaining <= duration + 120 and all(isinstance(creds.get(key), str) and creds[key]
                    and '\n' not in creds[key] for key in ('AccessKeyId', 'SecretAccessKey', 'SessionToken')),
                    'AssumeRole returned invalid/expired credentials')
            env.update(dns)
            env.update(AWS_ACCESS_KEY_ID=creds['AccessKeyId'], AWS_SECRET_ACCESS_KEY=creds['SecretAccessKey'], AWS_SESSION_TOKEN=creds['SessionToken'])
            identity = json.loads(run([tools['aws'], 'sts', 'get-caller-identity', *common], env, 'AWS'))
            require(identity.get('Account') == account and identity.get('Arn') == expected, 'Assumed AWS account/role verification failed')
            event(operation.record, 'identity-verified', account=account, arn=expected, region=region,
                  expiry=creds['Expiration'], project=project or None, environment=environment or None)
            if args.exec:
                env['PATH'] = os.pathsep.join(dict.fromkeys([str(Path(tools[name]).parent) for name in ('node', 'python', 'git', 'aws')] + ['/usr/bin', '/bin']))
                env.update(FACTORY_PROJECT_ID=project, FACTORY_ENVIRONMENT=environment, FACTORY_AWS_SCOPE=scope,
                           FACTORY_AWS_ACCOUNT_ID=account, FACTORY_AWS_REGION=region, FACTORY_AWS_ROLE_NAME=role)
                for key in ('FACTORY_AWS_APP_BOUNDARY_ARN', 'FACTORY_AWS_APP_POLICY_ARN'):
                    value = os.environ.get(key, '')
                    if value:
                        require(re.fullmatch(r'arn:aws:iam::' + account + r':policy/[A-Za-z0-9_+=,.@/-]+', value), 'App policy/boundary ARN must be exact and in the approved account')
                        env[key] = value
            child = command if args.exec else [tools['aws'], *command, '--region', region, '--no-cli-pager']
            result = run(child, env, 'AWS', timeout=900)
            operation.finish(result, [*known_credentials(), creds['AccessKeyId'], creds['SecretAccessKey'], creds['SessionToken']])
    except Exception:
        operation.failed()
        raise


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--exec', action='store_true', help='Run a privately reviewed exact executable under the same assumed session')
    parser.add_argument('--record', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    execute(parser.parse_args())


if __name__ == '__main__':
    cli(main)
