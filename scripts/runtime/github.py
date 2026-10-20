#!/usr/bin/env python3
"""Explicit GitHub CLI and normal authenticated Git command paths."""
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from provider import gh_environment
from runtime import ROOT, Operation, Parser, base_env, cli, event, known_credentials, load, read_private, require, run


def selected_env(home, target):
    selected = gh_environment()
    env = base_env(home)
    for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if key in selected:
            env[key] = selected[key]
    if os.environ.get('FACTORY_GITHUB_CREDENTIAL_SOURCE', 'cli') == 'cli':
        for key in ('HOME', 'GH_CONFIG_DIR', 'XDG_CONFIG_HOME'):
            if selected.get(key):
                env[key] = selected[key]
    else:
        env['GH_CONFIG_DIR'] = str(home)
    env.update(GH_HOST='github.com', GH_REPO=target, GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1',
               GH_NO_EXTENSION_UPDATE_NOTIFIER='1', GH_PAGER='cat')
    return env


def identity(tools, env, owner):
    user = json.loads(run([tools['gh'], 'api', '--hostname', 'github.com', 'user'], env, 'GitHub'))
    require(isinstance(user.get('login'), str), 'GitHub principal cannot be verified')
    if user['login'].lower() != owner:
        member = json.loads(run([tools['gh'], 'api', '--hostname', 'github.com', 'user/memberships/orgs/' + owner], env, 'GitHub'))
        require(member.get('state') == 'active' and member.get('organization', {}).get('login', '').lower() == owner,
                'GitHub approved owner membership cannot be verified')
    return user['login'].lower()


def repository(tools, env, target, visibility):
    repo = json.loads(run([tools['gh'], 'api', '--hostname', 'github.com', 'repos/' + target], env, 'GitHub'))
    require(repo.get('full_name', '').lower() == target and repo.get('private') is (visibility == 'private'),
            'GitHub repository identity/visibility mismatch')


def gh_command(command, target, user, visibility):
    require(len(command) >= 2, 'Specify a supported gh api/repo/pr command')
    forbidden = ('--hostname', '--header', '-H', '--verbose', '--include', '-i', '--web', '-w', '--browser', '--editor', '-e',
                 '--repo', '-R', '--recover', '--source', '--push', '--clone', '--fill', '--fill-first', '--fill-verbose', '--template')
    require(not any(arg.split('=')[0] in forbidden or arg.startswith(('-R', '-H')) for arg in command),
            'GitHub target/auth/debug/editor overrides are forbidden')
    payload = None
    if command[0] == 'api':
        endpoint = command[1].lstrip('/')
        require('..' not in endpoint and re.fullmatch(r'[A-Za-z0-9_/?=&.-]+', endpoint), 'Invalid scoped GitHub API endpoint')
        method = 'GET'
        rest = command[2:]
        index = 0
        while index < len(rest):
            flag = rest[index]
            if flag in ('--method', '-X'):
                require(index + 1 < len(rest) and rest[index + 1] in ('GET', 'POST', 'PATCH', 'PUT', 'DELETE'), 'Invalid API method')
                method = rest[index + 1]
                index += 2
            elif flag == '--input':
                require(payload is None and index + 1 < len(rest), 'Use one private API input')
                payload = read_private(rest[index + 1])
                index += 2
            elif flag in ('--paginate', '--slurp'):
                index += 1
            else:
                require(False, 'Use API endpoint, --method, private --input and GET pagination only')
        if payload is not None and method == 'GET':
            require(False, 'Specify the method explicitly for API input')
        require(method == 'GET' or not any(flag in rest for flag in ('--paginate', '--slurp')), 'Mutation pagination is forbidden')
        creation = endpoint == 'user/repos' or endpoint == 'orgs/' + target.split('/')[0] + '/repos'
        if creation:
            body = json.loads(payload or b'{}')
            require(isinstance(body, dict) and method == 'POST' and body.get('name', '').lower() == target.split('/')[1]
                    and body.get('private') is (visibility == 'private'), 'Repository creation payload differs from target/visibility')
            require((endpoint == 'user/repos') == (user == target.split('/')[0]), 'Repository creation owner mismatch')
        else:
            require(endpoint == 'repos/' + target or endpoint.startswith('repos/' + target + '/')
                    or (method == 'GET' and endpoint == 'user'), 'API endpoint differs from the exact repository')
        result = ['api', '--hostname', 'github.com', endpoint, '--method', method]
        if payload is not None:
            result += ['--input', '-']
        result += [flag for flag in ('--paginate', '--slurp') if flag in rest]
        return result, payload, creation
    require(command[0:2] == ['repo', 'create'] or (command[0] == 'pr' and command[1] in
            ('create', 'view', 'list', 'status', 'checks', 'diff', 'edit', 'ready')), 'Use scoped gh api, repo create or ordinary PR commands')
    result = list(command)
    if result[0] == 'pr':
        for index, value in enumerate(result[2:], start=2):
            require(not value.startswith(('https://', 'http://')) or result[index - 1] in ('--body', '-b', '--title', '-t'),
                    'PR target URLs are forbidden; use the exact repository and PR number/branch')
            if value in ('--head', '-H') or value.startswith('--head='):
                head = value.split('=', 1)[1] if '=' in value else result[index + 1] if index + 1 < len(result) else ''
                require(re.fullmatch(r'(?:' + re.escape(target.split('/')[0]) + r':)?[A-Za-z0-9][A-Za-z0-9_./-]*', head)
                        and '..' not in head, 'PR head must be an explicit branch in the approved owner')
        if result[1] == 'create':
            require(any(value == '--head' or value.startswith('--head=') for value in result)
                    and any(value == '--title' or value.startswith('--title=') for value in result)
                    and '--body-file' in result, 'PR creation requires explicit --head, --title and private --body-file')
    if result[:2] == ['repo', 'create']:
        require(len(result) >= 3 and result[2].lower() == target and '--' + visibility in result
                and not (set(result) & ({'--private', '--public', '--internal'} - {'--' + visibility})),
                'Repository creation requires the exact target and visibility')
    for index, value in enumerate(result):
        if value == '--body-file':
            require(index + 1 < len(result), 'PR body file is missing')
            payload = read_private(result[index + 1])
            result[index + 1] = '-'
    return result, payload, result[:2] == ['repo', 'create']


def git_command(tools, env, args, target):
    app = Path(args.app or '')
    require(app.is_absolute() and '..' not in app.parts and not any(p.is_symlink() for p in (app, *app.parents)), 'App path must be canonical')
    require(app != ROOT and not ROOT.is_relative_to(app), 'Factory source cannot be an app')
    if app.is_relative_to(ROOT):
        require(app == ROOT / 'workspaces' / target, 'Nested app must use its exact independent workspace')
    require(args.branch is None or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*', args.branch) and '..' not in args.branch,
            'Specify a normal branch without force/deletion syntax')
    helper = '!' + shlex.quote(tools['gh']) + ' auth git-credential'
    common = [tools['git'], '-c', 'credential.helper=', '-c', 'credential.https://github.com.helper=',
              '-c', 'credential.https://github.com.helper=' + helper, '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false']
    if args.action == 'clone':
        require(not app.exists() and app.parent.is_dir(), 'Clone destination must be absent; inspect existing work separately')
        return [*common, 'clone', 'https://github.com/' + target + '.git', str(app)], None
    require(app.is_dir() and (app / '.git').is_dir() and not (app / '.git').is_symlink(), 'App must be an independent clone')
    origin = run([*common, '-C', str(app), 'remote', 'get-url', '--all', 'origin'], env, 'GitHub').decode().strip()
    push = run([*common, '-C', str(app), 'remote', 'get-url', '--push', '--all', 'origin'], env, 'GitHub').decode().strip()
    require(origin in ('https://github.com/' + target, 'https://github.com/' + target + '.git') and push == origin,
            'App HTTPS fetch/push origin mismatch')
    require(run([*common, '-C', str(app), 'rev-parse', '--show-toplevel'], env, 'GitHub').decode().strip() == str(app), 'App Git root mismatch')
    config = run([*common, '-C', str(app), 'config', '--local', '--name-only', '--list'], env, 'GitHub').decode().lower()
    require(not any('extraheader' in key or key.startswith('url.') for key in config.splitlines()), 'Review local Git URL/auth header overrides privately')
    require(args.branch, 'Push/fetch requires an exact branch')
    run([*common, 'check-ref-format', '--branch', args.branch], env, 'GitHub')
    if args.action == 'push':
        head = run([*common, '-C', str(app), 'symbolic-ref', '--short', 'HEAD'], env, 'GitHub').decode().strip()
        require(head == args.branch, 'Push branch differs from the checked-out branch')
        return [*common, '-C', str(app), 'push', 'origin', 'HEAD:refs/heads/' + args.branch], None
    return [*common, '-C', str(app), 'fetch', 'origin', args.branch], None


def execute(args):
    tools = load()
    target = args.repo.lower()
    contextual = os.environ.get('FACTORY_PROJECT_REPOSITORY', '') == target
    if contextual:
        from context import preflight
        preflight(tools)
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9_.-]{0,99}', target)
            and target.split('/')[0] == os.environ.get('FACTORY_GITHUB_OWNER', '').lower(), 'GitHub target differs from approved owner/repository')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    tokens = known_credentials()
    require(not any(token and token in value for token in tokens for value in command), 'Credential argument rejected')
    # Validate explicit source before any subprocess, including identity calls.
    gh_environment()
    with tempfile.TemporaryDirectory(prefix='factory-github-') as temporary:
        env = selected_env(temporary, target)
        user = identity(tools, env, target.split('/')[0])
        if args.mode == 'gh':
            command, payload, creation = gh_command(command, target, user, args.visibility)
            if not creation:
                repository(tools, env, target, args.visibility)
            executable = [tools['gh'], *command]
        else:
            repository(tools, env, target, args.visibility)
            executable, payload = git_command(tools, env, args, target)
        require(not any(token and token.encode() in (payload or b'') for token in tokens), 'Factory credential in request body rejected')
        operation = Operation(args.record, args.output, 'GitHub', json.dumps(executable).encode() + (payload or b''), contextual=contextual)
        try:
            event(operation.record, 'identity-verified', principal=user, repository=target, visibility=args.visibility)
            response = run(executable, env, 'GitHub', input=payload, timeout=900)
            operation.received(response, tokens)
            if args.mode == 'gh' and creation:
                repository(tools, env, target, args.visibility)
            operation.finish(response, tokens)
        except Exception:
            operation.failed()
            raise


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('mode', choices=['gh', 'git'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--visibility', choices=['private', 'public'], default='private')
    parser.add_argument('--app')
    parser.add_argument('--action', choices=['clone', 'fetch', 'push'], default='clone')
    parser.add_argument('--branch')
    parser.add_argument('--record', required=True)
    parser.add_argument('--output', required=True)
    values = sys.argv[1:]
    divider = values.index('--') if '--' in values else len(values)
    args = parser.parse_args(values[:divider])
    args.command = values[divider + 1:] if divider < len(values) else []
    require(args.mode != 'gh' or divider < len(values), 'Separate gh command arguments with --')
    execute(args)


if __name__ == '__main__':
    cli(main)
