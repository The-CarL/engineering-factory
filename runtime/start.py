#!/usr/bin/env python3
"""Verify runtime/source integrity; use diagnose.py first when setup is missing or blocked."""
import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from runtime import ROOT, Parser, base_env, cli, load, require, write_environment


def refresh():
    revision = os.environ.get('FACTORY_SOURCE_REVISION', '')
    repo = os.environ.get('FACTORY_SOURCE_REPOSITORY', '')
    require(re.fullmatch(r'[a-f0-9]{40}', revision) and re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repo), 'Set exact approved source repository/revision')
    env = base_env('/tmp')
    prefix = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'credential.helper=', '-C', str(ROOT)]
    def git(*args):
        result = subprocess.run(prefix + list(args), env=env, capture_output=True, timeout=120)
        require(result.returncode == 0, 'Safe source refresh failed; preserve checkout and inspect privately')
        return result.stdout.decode().strip()
    require((ROOT / '.git').is_dir() and not (ROOT / '.git').is_symlink(), 'Refresh requires an independent factory checkout')
    require(git('rev-parse', '--show-toplevel') == str(ROOT) and git('branch', '--show-current') == 'main'
            and git('remote', 'get-url', '--all', 'origin').lower() in
            ('https://github.com/' + repo.lower(), 'https://github.com/' + repo.lower() + '.git'),
            'Refresh requires the exact approved HTTPS factory main checkout')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Source is dirty; refresh preserves all files and stops')
    keys = git('config', '--local', '--name-only', '--list').lower().splitlines()
    require(not any('extraheader' in key or key.startswith('url.') for key in keys), 'Review factory Git URL/auth header overrides privately')
    if git('rev-parse', 'HEAD') == revision:
        return False
    git('fetch', '--no-tags', 'https://github.com/' + repo + '.git', 'main')
    git('merge-base', '--is-ancestor', 'HEAD', revision)
    git('merge-base', '--is-ancestor', revision, 'FETCH_HEAD')
    git('merge', '--ff-only', '--no-edit', revision)
    require(git('rev-parse', 'HEAD') == revision, 'Source revision verification failed after refresh')
    return True


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--environment-file', type=Path, help='Write credential-free activation for this exact installed release')
    parser.add_argument('--source-only', action='store_true', help='Verify/refresh source before installing the matching runtime')
    args = parser.parse_args()
    changed = args.refresh and refresh()
    if args.source_only:
        from runtime import check_source
        check_source()
        print('Approved committed runtime source verified; install/verify its matching tool release next.')
        return
    if changed:
        # Execute the approved new source, not this old imported module.
        os.execv(sys.executable, [sys.executable, str(ROOT / 'runtime/start.py'), *(['--environment-file', str(args.environment_file)] if args.environment_file else [])])
    tools = load()
    project = None
    if os.environ.get('FACTORY_PROJECT_REPOSITORY'):
        from context import restore
        project = restore(os.environ['FACTORY_PROJECT_REPOSITORY'], tools=tools)
    if args.environment_file:
        write_environment(args.environment_file, tools, project)
    print('Factory source and retained tool integrity verified. Read the current AGENTS.md before work.')
    print('Provider credential transports, IAM grants and workload acceptance require their separate actual checks.')
    require(all(Path(path).is_file() for path in tools.values()), 'Runtime tools unavailable')


if __name__ == '__main__':
    cli(main)
