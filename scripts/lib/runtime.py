"""Shared private artifacts, verified runtime and credential-free child defaults."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from provider import ProviderError

ROOT = Path(__file__).resolve().parents[2]
NETWORK = ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy',
           'all_proxy', 'no_proxy', 'NODE_EXTRA_CA_CERTS', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'AWS_CA_BUNDLE')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProviderError('Invalid runtime command arguments; use --help')


def require(condition, message):
    if not condition:
        raise ProviderError(message)


def known_credentials():
    return [os.environ.get(key, '') for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
            'GH_TOKEN', 'GITHUB_TOKEN', 'FACTORY_GITHUB_TOKEN', 'VERCEL_TOKEN')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def base_env(home):
    env = {key: os.environ[key] for key in NETWORK if key in os.environ}
    env.update(PATH='/usr/bin:/bin', HOME=str(home), TMPDIR=str(home), LANG='C.UTF-8',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
    return env


def local_git(*args):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                             '-C', str(ROOT), *args], env=base_env('/tmp'),
                            capture_output=True, timeout=30)
    require(result.returncode == 0, 'Factory Git source verification failed')
    return result.stdout.decode().strip()


def source_files():
    names = local_git('ls-files', '--cached', '--others', '--exclude-standard', '--',
                      'runtime', 'scripts/runtime', 'scripts/lib/runtime.py', 'scripts/lib/provider.py').splitlines()
    return sorted(set(names))


def check_source():
    repo = os.environ.get('FACTORY_SOURCE_REPOSITORY', '')
    revision = os.environ.get('FACTORY_SOURCE_REVISION', '')
    require(re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repo) and re.fullmatch(r'[a-f0-9]{40}', revision),
            'Set exact FACTORY_SOURCE_REPOSITORY and FACTORY_SOURCE_REVISION')
    origin = local_git('remote', 'get-url', '--all', 'origin')
    require(origin.lower() in ('https://github.com/' + repo.lower(), 'https://github.com/' + repo.lower() + '.git',
                               'git@github.com:' + repo.lower() + '.git'),
            'Factory origin differs from approved source')
    require(local_git('rev-parse', '--show-toplevel') == str(ROOT) and local_git('rev-parse', 'HEAD') == revision,
            'Factory source is stale or differs from the approved revision; run reviewed startup refresh')
    require(not local_git('status', '--porcelain', '--untracked-files=all'), 'Factory source is dirty; preserve files and use reviewed committed source')
    files = {}
    for name in source_files():
        path = ROOT / name
        require(path.is_file() and not path.is_symlink(), 'Unsafe runtime source file')
        expected = subprocess.run(['git', '-C', str(ROOT), 'show', revision + ':' + name],
                                  env=base_env('/tmp'), capture_output=True, timeout=30)
        require(expected.returncode == 0 and expected.stdout == path.read_bytes(),
                'Runtime source must match its committed approved revision')
        files[name] = digest(expected.stdout)
    require('runtime/pins.json' in files and 'scripts/lib/runtime.py' in files, 'Runtime source is incomplete')
    return repo, revision, files


def private_path(value, *, existing=False):
    path = Path(value)
    root = Path(os.environ.get('FACTORY_PRIVATE_ROOT', ''))
    require(root.is_absolute() and root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o077 == 0,
            'FACTORY_PRIVATE_ROOT must be an existing private directory (700)')
    require(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
            'Private artifact path must be canonical without symlinks')
    require(path.parent.is_dir() and path.parent.resolve().is_relative_to(root.resolve())
            and path.parent.stat().st_mode & 0o077 == 0, 'Artifact must be inside the private root and a private directory')
    if path.is_relative_to(ROOT):
        require(subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--quiet', '--', str(path)],
                               env=base_env('/tmp'), capture_output=True).returncode == 0,
                'Private artifacts must be ignored by factory Git')
    if existing:
        require(path.is_file() and path.stat().st_mode & 0o077 == 0, 'Private input must be a regular file (600)')
    else:
        require(not path.exists(), 'Artifact already exists; reconcile the prior operation instead of retrying')
    return path


def read_private(value):
    path = private_path(value, existing=True)
    require(path.stat().st_size <= 16 * 1024 * 1024, 'Private input exceeds size limit')
    return path.read_bytes()


def event(path, state, **fields):
    with path.open('a') as stream:
        stream.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(), state=state, **fields), sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class Operation:
    def __init__(self, record, output, provider, request):
        self.record = private_path(record)
        self.output = private_path(output)
        require(self.record != self.output, 'Operation record and output must differ')
        self.record.touch(mode=0o600, exist_ok=False)
        self.output.touch(mode=0o600, exist_ok=False)
        event(self.record, 'intent', provider=provider, source=os.environ.get('FACTORY_SOURCE_REVISION'),
              request_sha256=digest(request))

    def received(self, data, secrets=()):
        require(len(data) <= 16 * 1024 * 1024, 'Response exceeds private output limit')
        require(not any(secret and secret.encode() in data for secret in secrets), 'Credential-like response withheld')
        self.output.write_bytes(data)
        event(self.record, 'response-received', response_sha256=digest(data), size=len(data))

    def finish(self, data, secrets=(), quiet=False):
        self.received(data, secrets)
        event(self.record, 'complete', response_sha256=digest(data), size=len(data))
        if not quiet:
            print('Operation complete; response and evidence retained privately.')

    def failed(self):
        event(self.record, 'failed-or-unknown', detail='Reconcile provider state before another mutation')


def load():
    _, revision, files = check_source()
    path = Path(os.environ.get('FACTORY_RUNTIME_MANIFEST', ''))
    require(path.is_absolute() and path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
            'Set the installed private FACTORY_RUNTIME_MANIFEST')
    manifest = json.loads(path.read_bytes())
    require(manifest.get('schema') == 1 and manifest.get('revision') == revision and manifest.get('source') == files,
            'Installed runtime source is stale or mismatched')
    root = path.parent
    require(root.stat().st_mode & 0o077 == 0, 'Installed runtime directory must be private')
    actual_files = {str(item.relative_to(root)) for item in root.rglob('*') if item.is_file() or item.is_symlink()}
    require(actual_files == set(manifest['files']) | {'manifest.json'}, 'Unexpected or missing retained runtime files')
    require(manifest.get('pins') == json.loads((ROOT / 'runtime/pins.json').read_text()), 'Installed tool pins differ from source')
    for name, entry in manifest['files'].items():
        item = root / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and item.resolve().is_relative_to(root),
                'Unsafe retained runtime path')
        if entry.get('link') is not None:
            require(item.is_symlink() and os.readlink(item) == entry['link'], 'Runtime symlink integrity failed')
        else:
            require(item.is_file() and not item.is_symlink() and digest(item.read_bytes()) == entry['sha256'] and item.stat().st_mode & 0o777 == entry['mode'],
                    'Retained runtime integrity failed')
    tools = {}
    for name, entry in manifest['tools'].items():
        executable = Path(entry['path'])
        executable = executable if executable.is_absolute() else root / executable
        require(executable.is_file() and digest(executable.read_bytes()) == entry['sha256'], 'Runtime executable integrity failed')
        tools[name] = str(executable.resolve())
    require(set(tools) == {'aws', 'gh', 'git', 'python', 'node', 'npm', 'vercel'}, 'Runtime tool manifest is incomplete')
    return tools


def run(command, env, provider, timeout=120, input=None, cwd=None):
    from provider import diagnostic
    try:
        result = subprocess.run(command, env=env, cwd=cwd, input=input, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise ProviderError(provider + '; transport failure; outcome may be unknown') from None
    if result.returncode:
        if provider == 'AWS':
            code = next((code for code in ('AccessDenied', 'ExpiredToken', 'InvalidClientTokenId', 'Throttling',
                                          'ValidationError', 'UnauthorizedOperation') if code.encode() in result.stderr), 'detail withheld')
            raise ProviderError('AWS request failed; ' + code)
        raise ProviderError(diagnostic(provider, stderr=result.stderr))
    return result.stdout


def cli(main):
    try:
        main()
    except ProviderError as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        print('ERROR: Runtime/configuration validation failed; private detail withheld.', file=sys.stderr)
        sys.exit(1)
