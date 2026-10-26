"""Project-owned bounded registry. Data never authorizes resource adoption or executes code."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit

from provider import gh_environment, METADATA
from runtime import ROOT, base_env, digest, known_credentials, load, private_path, read_private, require, run, valid_environment

REPO = r'[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9_.-]{0,99}'
BRANCH = r'[A-Za-z0-9][A-Za-z0-9_./-]{0,199}'
CONFIG = {
    'FACTORY_GITHUB_OWNER': r'[A-Za-z0-9][A-Za-z0-9-]{0,38}',
    'FACTORY_VERCEL_TEAM_ID': r'team_[A-Za-z0-9]+',
    'FACTORY_VERCEL_TEAM_SLUG': r'[A-Za-z0-9][A-Za-z0-9-]{0,99}',
    'VERCEL_PROJECT_ID': r'prj_[A-Za-z0-9]+',
    'VERCEL_ORG_ID': r'team_[A-Za-z0-9]+',
    'FACTORY_AWS_ACCOUNT_ID': r'[0-9]{12}',
    'FACTORY_AWS_ROLE_NAME': r'[A-Za-z0-9+=,.@_-]{1,64}',
    'FACTORY_AWS_DNS_ZONE_ID': r'Z[A-Z0-9]{1,63}',
    'FACTORY_AWS_DNS_ZONE_NAME': r'[a-z0-9.-]{3,253}',
    'FACTORY_AWS_REGION': r'[a-z]{2}(?:-[a-z]+)+-[0-9]+',
}
LIMIT = 4 * 1024 * 1024


def project_id(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0, 'Invalid project UUID')
    return value


def relative(value):
    path = Path(value)
    require(isinstance(value, str) and len(value) <= 240 and not path.is_absolute() and 1 <= len(path.parts) <= 6
            and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', part) and part not in ('.', '..') for part in path.parts),
            'Invalid context artifact path')
    return path


def clean(data):
    require(len(data) <= LIMIT and not any(secret and secret.encode() in data for secret in known_credentials()),
            'Credential-like or oversized context content rejected')


def metadata(data):
    require(isinstance(data, dict) and set(data) == set(METADATA), 'Invalid ownership metadata schema')
    for key, value in data.items():
        require(isinstance(value, str) and 0 < len(value) <= 256 and '\n' not in value, 'Invalid ownership metadata value')
        if key in ('factoryProjectId',):
            project_id(value)
        elif key == 'factoryEnvironment':
            require(valid_environment(value), 'Invalid ownership environment namespace')
        elif key in ('factorySourceCommit', 'factoryLastSourceCommit'):
            require(re.fullmatch(r'[a-f0-9]{40}', value), 'Invalid metadata commit')
        elif key in ('factoryCreatedAt', 'factoryExpiresAt'):
            if not (key == 'factoryExpiresAt' and value == 'none'):
                require(datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None, 'Invalid metadata timestamp')
        elif key == 'factorySourceRepo':
            require(re.fullmatch(REPO, value.lower()), 'Invalid metadata repository')
        else:
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value), 'Invalid metadata alias')
    require(data['factoryManagedBy'] == 'engineering-factory' and data['factoryProvenanceVersion'] == '1', 'Invalid ownership manager/schema')


def journal(data, expected):
    clean(data)
    require(len(data) <= 256 * 1024 and data.endswith(b'\n'), 'Invalid journal size/termination')
    entries = [json.loads(line) for line in data.splitlines()]
    require(1 <= len(entries) <= 512, 'Invalid journal event count')
    shared = {'time', 'state'}
    for entry in entries:
        require(isinstance(entry, dict) and shared <= set(entry), 'Invalid journal event')
        require(datetime.fromisoformat(entry['time']).tzinfo is not None, 'Invalid journal timestamp')
        state = entry['state']
        require(isinstance(state, str), 'Invalid journal state')
        keys = {
            'intent': {'provider', 'source', 'request_sha256'},
            'response-received': {'response_sha256', 'size'}, 'complete': {'response_sha256', 'size'},
            'failed-or-unknown': {'detail'}, 'continuity-pending': {'detail'},
            'created-resource': {'team', 'project', 'name', 'metadata'},
            'identity-verified': None,
        }
        require(state in keys, 'Unknown context journal state')
        if state == 'identity-verified':
            allowed = ({'principal', 'repository', 'visibility'}, {'principal', 'team', 'project', 'metadata'},
                       {'account', 'arn', 'region', 'expiry', 'project', 'environment'})
            require(set(entry) - shared in allowed, 'Invalid identity journal fields')
        else:
            require(set(entry) == shared | keys[state], 'Unexpected journal fields; raw request/output export forbidden')
        for key, value in entry.items():
            if key in ('time', 'state'):
                continue
            if key == 'provider':
                require(value in ('AWS', 'GitHub', 'Vercel'), 'Unknown journal provider')
            elif key == 'metadata':
                if value is not None:
                    metadata(value)
                    require(value['factoryProjectId'] == expected, 'Journal belongs to another project')
            elif key in ('request_sha256', 'response_sha256', 'source'):
                require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{40}' if key == 'source' else r'[a-f0-9]{64}', value), 'Invalid journal hash')
            elif key == 'environment' and value is not None:
                require(valid_environment(value), 'Invalid journal environment namespace')
            elif key == 'size':
                require(type(value) is int and 0 <= value <= 16 * 1024 * 1024, 'Invalid response byte count')
            elif key == 'detail':
                require(value in ('Reconcile provider state before another mutation', 'Provider result retained; durable context pending reconciliation'), 'Arbitrary journal detail forbidden')
            elif value is not None:
                require(isinstance(value, str) and len(value) <= 256 and re.fullmatch(r'[A-Za-z0-9_+.,:/=@-]+', value), 'Invalid journal scalar')
                if key == 'project' and 'arn' in entry:
                    require(value == expected, 'AWS journal belongs to another project')
    require(entries[0]['state'] == 'intent', 'Journal must begin with intent')
    return entries


def receipt(data, expected):
    clean(data)
    value = json.loads(data)
    require(isinstance(value, dict) and set(value) == {'schema', 'factory_project_id', 'team_id', 'project_id',
            'project_name', 'metadata', 'creation_record', 'creation_record_sha256'} and value['schema'] == 1
            and value['factory_project_id'] == expected, 'Invalid ownership receipt schema/project')
    metadata(value['metadata'])
    require(value['metadata']['factoryProjectId'] == expected and re.fullmatch(r'team_[A-Za-z0-9]+', value['team_id'])
            and re.fullmatch(r'prj_[A-Za-z0-9]+', value['project_id'])
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', value['project_name'])
            and re.fullmatch(r'[a-f0-9]{64}', value['creation_record_sha256']), 'Invalid ownership receipt target/hash')
    relative(value['creation_record'])
    return value


def inventory(data, expected):
    clean(data)
    require(len(data) <= 256 * 1024, 'Inventory byte limit exceeded')
    value = json.loads(data)
    require(isinstance(value, dict) and set(value) == {'schema', 'project_id', 'environment', 'resources'}
            and value['schema'] == 1 and value['project_id'] == expected
            and valid_environment(value['environment'])
            and isinstance(value['resources'], list) and 1 <= len(value['resources']) <= 128, 'Invalid inventory schema/project')
    identities = []
    for item in value['resources']:
        fields = {'provider', 'resource_id', 'resource_type', 'parent_id', 'backend_ref', 'run_id', 'source_commit', 'status', 'ownership'}
        require(isinstance(item, dict) and fields <= set(item) <= fields | {'url'}, 'Invalid inventory resource fields')
        provider, identity = item['provider'], item['resource_id']
        require(provider in ('AWS', 'Vercel', 'GitHub') and isinstance(identity, str) and len(identity) <= 1024, 'Invalid inventory provider/ID')
        pattern = {'AWS': r'(?:arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:[A-Za-z0-9_.$!/:@+=,-]+|[A-Za-z0-9$][A-Za-z0-9_.$!/:@+=,-]{0,511})',
                   'Vercel': r'(?:prj|dpl|team)_[A-Za-z0-9]+', 'GitHub': REPO}[provider]
        if provider == 'Vercel' and isinstance(item['resource_type'], str):
            kind = item['resource_type'].lower().split(':')[-1]
            if kind == 'domain':
                pattern = r'(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
            elif kind == 'certificate':
                pattern = r'[A-Za-z0-9][A-Za-z0-9_-]{0,255}'
        require(re.fullmatch(pattern, identity) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}', item['resource_type'])
                and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', item['run_id'])
                and re.fullmatch(r'[a-f0-9]{40}', item['source_commit'])
                and item['status'] in ('planned', 'created', 'updated', 'ready', 'failed', 'unknown', 'deleted', 'external')
                and item['ownership'] in ('managed', 'external'), 'Invalid inventory resource metadata')
        if 'url' in item:
            url = urlsplit(item['url'])
            require(len(item['url']) <= 1024 and url.scheme == 'https' and url.hostname and url.port in (None, 443)
                    and not url.username and not url.password and not url.query and not url.fragment
                    and re.fullmatch(r'[A-Za-z0-9.-]+', url.hostname) and re.fullmatch(r'/[A-Za-z0-9._~/-]*|', url.path),
                    'Inventory URL must be a nonsecret HTTPS endpoint without credentials/query/fragment')
        identities.append(identity)
    require(len(set(identities)) == len(identities), 'Duplicate inventory resource IDs')
    for item in value['resources']:
        require(all(item[key] is None or item[key] in identities for key in ('parent_id', 'backend_ref')),
                'Inventory parent/backend reference requires a typed resource entry')
    return value


def artifact(data, expected, kind):
    require(kind in ('journal', 'ownership', 'inventory'), 'Invalid context artifact kind')
    return {'journal': journal, 'ownership': receipt, 'inventory': inventory}[kind](data, expected)


def record(value):
    require(isinstance(value, dict) and set(value) == {'schema', 'project_id', 'repository', 'environment', 'branch',
            'source_commit', 'factory_source_commit', 'factory_source_repository', 'publication', 'config', 'artifacts'} and value['schema'] == 2, 'Invalid project context schema')
    project_id(value['project_id'])
    require(re.fullmatch(REPO, value['factory_source_repository']) and value['publication'] in ('private', 'public-minimal'), 'Invalid registry standard reference/publication policy')
    require(re.fullmatch(REPO, value['repository']) and valid_environment(value['environment'])
            and re.fullmatch(BRANCH, value['branch']) and '..' not in value['branch']
            and (value['source_commit'] is None or re.fullmatch(r'[a-f0-9]{40}', value['source_commit']))
            and re.fullmatch(r'[a-f0-9]{40}', value['factory_source_commit']), 'Invalid project source/environment')
    require(isinstance(value['config'], dict) and set(value['config']) <= set(CONFIG), 'Context cannot supply credentials or executable configuration')
    for key, selected in value['config'].items():
        require(isinstance(selected, str) and re.fullmatch(CONFIG[key], selected), 'Invalid provider target configuration')
    require(not (value['config'].get('VERCEL_ORG_ID') and value['config'].get('FACTORY_VERCEL_TEAM_ID'))
            or value['config']['VERCEL_ORG_ID'] == value['config']['FACTORY_VERCEL_TEAM_ID'],
            'Vercel CLI organization differs from selected team')
    from dns_records import configured as dns_configured
    dns_configured(value['config'])
    require(value['config'].get('FACTORY_GITHUB_OWNER', '').lower() == value['repository'].split('/')[0], 'Context repository owner mismatch')
    require(isinstance(value['artifacts'], dict) and len(value['artifacts']) <= 256, 'Context artifact count exceeded')
    for name, item in value['artifacts'].items():
        relative(name)
        require(isinstance(item, dict) and set(item) == {'sha256', 'kind'} and item['kind'] in ('journal', 'ownership', 'inventory')
                and re.fullmatch(r'[a-f0-9]{64}', item['sha256']), 'Invalid artifact manifest')
    if value['publication'] == 'public-minimal':
        require(set(value['config']) <= {'FACTORY_GITHUB_OWNER'} and not value['artifacts'], 'Confidential registry data cannot be published to a public app')
    encoded = json.dumps(value, sort_keys=True).encode()
    require(len(encoded) <= 128 * 1024, 'Project metadata size exceeded')
    clean(encoded)
    return value


def app_identity(tools, app, target):
    require(app.is_absolute() and '..' not in app.parts and not any(p.is_symlink() for p in (app, *app.parents))
            and app != ROOT and not ROOT.is_relative_to(app), 'Invalid independent app path')
    marker = app / '.git'
    require((marker.is_dir() or marker.is_file()) and not marker.is_symlink(),
            'App must be a Git checkout with regular metadata')
    def git(*args, optional=False):
        result = subprocess.run([tools['git'], '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                                 '-C', str(app), *args], env=base_env('/tmp'), capture_output=True, timeout=30)
        require(optional or result.returncode == 0, 'Local app identity cannot be verified')
        return result.stdout.decode().strip() if result.returncode == 0 else None
    require(git('rev-parse', '--show-toplevel') == str(app), 'App path differs from Git root')
    common = Path(git('rev-parse', '--path-format=absolute', '--git-common-dir'))
    require(common.is_absolute() and common.is_dir() and common == common.resolve()
            and not any(p.is_symlink() for p in (common, *common.parents))
            and not (common / 'objects/info/alternates').exists(), 'App Git storage must be canonical and self-contained')
    require(not git('rev-parse', '--show-superproject-working-tree'), 'App cannot be a submodule')
    allowed = ('https://github.com/' + target, 'https://github.com/' + target + '.git', 'git@github.com:' + target + '.git')
    require(git('remote', 'get-url', '--all', 'origin').lower() in allowed
            and git('remote', 'get-url', '--push', '--all', 'origin').lower() in allowed, 'App origin differs from selected context')
    keys = git('config', '--name-only', '--list').lower().splitlines()
    require(not any('extraheader' in key or key.startswith('url.') for key in keys), 'Review app Git URL/auth overrides privately')
    branch = git('symbolic-ref', '--short', 'HEAD')
    require(re.fullmatch(BRANCH, branch) and '..' not in branch, 'App requires a normal selected branch')
    return branch, git('rev-parse', '--verify', 'HEAD', optional=True)


def reject_legacy():
    require(not any(os.environ.get(key) for key in ('FACTORY_CONTEXT_REPOSITORY', 'FACTORY_CONTEXT_DIRECTORY')),
            'Central context storage is no longer supported; remove stale FACTORY_CONTEXT_REPOSITORY/DIRECTORY and select the app repository')


def configured():
    reject_legacy()
    return bool(os.environ.get('FACTORY_PROJECT_REPOSITORY'))


def values(data, app):
    result = dict(data['config'], FACTORY_PROJECT_ID=data['project_id'], FACTORY_ENVIRONMENT=data['environment'],
                  FACTORY_PROJECT_REPOSITORY=data['repository'], FACTORY_PROJECT_APP=str(app))
    if result.get('VERCEL_PROJECT_ID') and result.get('FACTORY_VERCEL_TEAM_ID'):
        require(result.get('VERCEL_ORG_ID', result['FACTORY_VERCEL_TEAM_ID']) == result['FACTORY_VERCEL_TEAM_ID'],
                'Vercel CLI organization differs from selected team')
        result['VERCEL_ORG_ID'] = result['FACTORY_VERCEL_TEAM_ID']
    for key, expected in result.items():
        if key == 'FACTORY_AWS_REGION' and os.environ.get(key):
            require(re.fullmatch(CONFIG[key], os.environ[key]), 'Invalid explicit AWS region override')
            result[key] = os.environ[key]
            continue
        require(not os.environ.get(key) or os.environ[key] == expected, 'Selected project/provider registry differs; use an explicit clean project selection')
    return result


def atomic(path, content, mode):
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Registry path contains a symlink')
    require(not path.exists() or path.is_file(), 'Registry target must be a regular file')
    descriptor, temporary = tempfile.mkstemp(prefix='.factory-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(app, tools):
    result = subprocess.run([tools['git'], '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
        '-C', str(app), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
        env=base_env('/tmp'), capture_output=True, timeout=30)
    require(result.returncode == 0, 'Registry lock Git storage cannot be verified')
    common = Path(result.stdout.decode().strip())
    require(common.is_absolute() and common.is_dir() and common == common.resolve()
            and not any(p.is_symlink() for p in (common, *common.parents)), 'Unsafe registry lock path')
    path = common / 'factory-registry.lock'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink()


class Project:
    def __init__(self, tools, target, app):
        reject_legacy()
        require(re.fullmatch(REPO, target) and target != os.environ.get('FACTORY_SOURCE_REPOSITORY', '').lower()
                and target.split('/')[0] == os.environ.get('FACTORY_GITHUB_OWNER', '').lower(), 'Select an independent app under the approved owner')
        require(os.environ.get('FACTORY_GITHUB_CREDENTIAL_SOURCE') in ('factory-token', 'cli'), 'Select the explicit GitHub credential source')
        self.tools, self.target, self.app = tools, target, app

    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='factory-registry-')
        self.env = base_env(self.temporary.name)
        selected = gh_environment()
        for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
            if selected.get(key):
                self.env[key] = selected[key]
        if os.environ['FACTORY_GITHUB_CREDENTIAL_SOURCE'] == 'cli':
            for key in ('HOME', 'GH_CONFIG_DIR', 'XDG_CONFIG_HOME'):
                if selected.get(key):
                    self.env[key] = selected[key]
        else:
            self.env['GH_CONFIG_DIR'] = self.temporary.name
        self.env.update(GH_HOST='github.com', GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1')
        self.prefix = [self.tools['git'], '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                       '-c', 'credential.helper=', '-c', 'credential.https://github.com.helper=',
                       '-c', 'credential.https://github.com.helper=!' + shlex.quote(self.tools['gh']) + ' auth git-credential']
        return self

    def __exit__(self, *args):
        self.temporary.cleanup()

    def git(self, *args, optional=False):
        result = subprocess.run([*self.prefix, '-C', str(self.app), *args], env=self.env, capture_output=True, timeout=120)
        require(optional or result.returncode == 0, 'App registry Git operation failed; preserve state and reconcile without replay')
        return result.stdout if result.returncode == 0 else None

    def verify(self):
        principal = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com', 'user'], self.env, 'GitHub registry'))
        require(isinstance(principal.get('login'), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', principal['login']), 'GitHub principal cannot be verified')
        owner = self.target.split('/')[0]
        if principal['login'].lower() != owner:
            member = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com', 'user/memberships/orgs/' + owner], self.env, 'GitHub registry'))
            require(member.get('state') == 'active' and member.get('organization', {}).get('login', '').lower() == owner,
                    'GitHub approved owner membership cannot be verified')
        info = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com', 'repos/' + self.target], self.env, 'GitHub registry'))
        require(info.get('full_name', '').lower() == self.target and type(info.get('private')) is bool
                and not info.get('archived', False), 'App repository identity/visibility cannot be verified')
        self.private = info['private']
        return info

    def read(self, revision=None):
        contents = {}
        if revision:
            entries = self.git('ls-tree', '-r', '-z', revision, '--', '.factory').split(b'\0')
            require(len(entries) <= 258, 'Registry file count exceeded')
            for entry in filter(None, entries):
                header, name = entry.decode().split('\t', 1)
                mode, kind, object_id = header.split()
                require(mode == '100644' and kind == 'blob', 'Registry symlinks/submodules/executables are forbidden')
                require(int(self.git('cat-file', '-s', object_id)) <= LIMIT, 'Registry file size exceeded')
                contents[name] = self.git('cat-file', 'blob', object_id)
        else:
            folder = self.app / '.factory'
            require(not folder.is_symlink(), 'Registry directory cannot be a symlink')
            if folder.exists():
                require(folder.is_dir(), 'Registry must be a directory')
                for count, path in enumerate(folder.rglob('*')):
                    require(count < 1024, 'Registry directory count exceeded')
                    require(not path.is_symlink(), 'Registry symlinks are forbidden')
                    if path.is_file():
                        require(len(contents) < 257 and path.stat().st_size <= LIMIT and not path.stat().st_mode & 0o111, 'Registry bounds/modes exceeded')
                        contents[str(path.relative_to(self.app))] = path.read_bytes()
                    else:
                        relative(str(path.relative_to(folder)))
        require(sum(map(len, contents.values())) <= LIMIT + 128 * 1024, 'Registry byte limit exceeded')
        if not contents:
            return None, {}
        require('.factory/project.json' in contents and len(contents['.factory/project.json']) <= 128 * 1024, 'Missing/bounded app registry required')
        data = record(json.loads(contents.pop('.factory/project.json')))
        require(data['repository'] == self.target, 'Registry belongs to another app; no adoption')
        require(data['publication'] == ('private' if self.private else 'public-minimal'), 'Registry visibility changed; confidential publication blocked')
        require(set(contents) == {'.factory/artifacts/' + name for name in data['artifacts']}, 'Unknown or missing registry files')
        artifacts = {name: contents['.factory/artifacts/' + name] for name in data['artifacts']}
        validate_artifacts(data, artifacts)
        return data, artifacts


def validate_artifacts(data, contents):
    require(sum(map(len, contents.values())) <= LIMIT, 'Project artifact byte limit exceeded')
    for name, item in data['artifacts'].items():
        content = contents[name]
        require(digest(content) == item['sha256'], 'Registry artifact digest mismatch')
        parsed = artifact(content, data['project_id'], item['kind'])
        if item['kind'] == 'inventory':
            require(parsed['environment'] == data['environment'], 'Inventory environment differs from app')
        if item['kind'] == 'journal':
            require(all((not event.get('repository') or event['repository'] == data['repository']) and (not event.get('metadata') or event['metadata']['factorySourceRepo'].lower() == data['repository']) for event in parsed), 'Journal belongs to another app')
        if item['kind'] == 'ownership':
            require(parsed['metadata']['factorySourceRepo'].lower() == data['repository'], 'Receipt belongs to another app')
            evidence = contents.get(parsed['creation_record'])
            require(evidence is not None and digest(evidence) == parsed['creation_record_sha256'], 'Ownership creation journal missing or changed')
            events = journal(evidence, data['project_id'])
            require(events[-1]['state'] == 'complete' and any(event.get('state') == 'created-resource'
                    and event.get('team') == parsed['team_id'] and event.get('project') == parsed['project_id']
                    and event.get('name') == parsed['project_name'] and event.get('metadata') == parsed['metadata'] for event in events),
                    'Ownership receipt lacks completed exact creation evidence')


def pending_file(data):
    root = Path(os.environ['FACTORY_PRIVATE_ROOT'])
    folder = root / 'project-continuity' / data['project_id']
    require(not any(p.is_symlink() for p in (folder, *folder.parents)), 'Pending registry path contains a symlink')
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    # mkdir(parents=True) may use default intermediate permissions.
    (root / 'project-continuity').chmod(0o700)
    path = folder / 'pending.json'
    private_path(path, existing=path.exists())
    return path


def pending(data):
    path = pending_file(data)
    if not path.exists():
        return {}
    require(path.stat().st_size <= 128 * 1024, 'Pending manifest byte limit exceeded')
    value = json.loads(read_private(path))
    require(isinstance(value, dict) and set(value) == {'schema', 'repository', 'project_id', 'artifacts'} and value['schema'] == 1
            and value['repository'] == data['repository'] and value['project_id'] == data['project_id'], 'Pending registry belongs to another app')
    record(dict(data, artifacts=value['artifacts'], publication='private'))
    return value['artifacts']


def collect(data, additions, contents):
    root = Path(os.environ['FACTORY_PRIVATE_ROOT'])
    for source, kind in additions:
        source = Path(source)
        name = str(source.relative_to(root))
        relative(name)
        content = read_private(source)
        parsed = artifact(content, data['project_id'], kind)
        if kind == 'ownership':
            evidence = root / parsed['creation_record']
            raw = read_private(evidence)
            journal(raw, data['project_id'])
            require(digest(raw) == parsed['creation_record_sha256'], 'Ownership journal digest mismatch')
            contents[parsed['creation_record']] = raw
            data['artifacts'][parsed['creation_record']] = dict(kind='journal', sha256=digest(raw))
        contents[name] = content
        data['artifacts'][name] = dict(kind=kind, sha256=digest(content))
    record(dict(data, publication='private'))
    validate_artifacts(data, contents)


def checkpoint(target, app=None, additions=(), initialize=False, environment=None, tools=None):
    tools = tools or load()
    app = app or Path(os.environ.get('FACTORY_PROJECT_APP', ''))
    with Project(tools, target, app) as project:
        project.verify()
        branch, commit = app_identity(tools, app, target)
        with locked(app, tools):
            data, contents = project.read()
            if data is None:
                require(initialize and environment, 'App registry missing; initialize this verified app explicitly')
                data = dict(schema=2, project_id=project_id(os.environ.get('FACTORY_PROJECT_ID') or str(uuid.uuid4())), repository=target,
                            environment=environment, branch=branch, source_commit=commit, factory_source_commit=os.environ['FACTORY_SOURCE_REVISION'],
                            factory_source_repository=os.environ['FACTORY_SOURCE_REPOSITORY'].lower(), publication='private' if project.private else 'public-minimal',
                            config={'FACTORY_GITHUB_OWNER': target.split('/')[0]}, artifacts={})
            values(data, app)
            saved_pending = pending(data)
            queued = []
            for name, item in saved_pending.items():
                source = Path(os.environ['FACTORY_PRIVATE_ROOT']) / relative(name)
                require(digest(read_private(source)) == item['sha256'], 'Pending evidence changed; reconcile original operation without replay')
                queued.append((source, item['kind']))
            require(project.private or not additions and not queued,
                    'Public app confidential export blocked; local evidence retained. Use project-owned protected/encrypted storage, no central fallback')
            data.update(branch=branch, source_commit=commit, factory_source_commit=os.environ['FACTORY_SOURCE_REVISION'])
            if project.private:
                data['config'].update({key: os.environ[key] for key in CONFIG if os.environ.get(key)
                                       and (key != 'FACTORY_AWS_REGION' or key not in data['config'])})
            collect(data, [*queued, *additions], contents)
            record(data)
            folder = app / '.factory'
            folder.mkdir(exist_ok=True)
            # Write validated artifact bytes first and publish the manifest last. No Git index changes.
            for name, content in contents.items():
                path = folder / 'artifacts' / relative(name)
                require(not any(p.is_symlink() for p in (path, *path.parents)), 'Registry artifact path contains symlink')
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic(path, content, 0o644)
            atomic(folder / 'project.json', json.dumps(data, sort_keys=True).encode() + b'\n', 0o644)
            if saved_pending:
                pending_file(data).unlink()
            return data


def restore(target, app=None, tools=None, branch=None):
    tools = tools or load()
    app = app or (Path(os.environ['FACTORY_PROJECT_APP']) if os.environ.get('FACTORY_PROJECT_APP') else ROOT / 'workspaces' / target)
    require(app.is_absolute() and '..' not in app.parts and not any(p.is_symlink() for p in (app, *app.parents))
            and app != ROOT and not ROOT.is_relative_to(app), 'Invalid restore app path')
    require(branch is None or re.fullmatch(BRANCH, branch) and '..' not in branch, 'Invalid explicit restore branch')
    with Project(tools, target, app) as project:
        project.verify()
        fresh = not app.exists()
        if fresh:
            app.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run([*project.prefix, 'clone', '--no-checkout', '--no-tags', '--single-branch',
                *(['--branch', branch] if branch else []), 'https://github.com/' + target + '.git', str(app)],
                env=project.env, capture_output=True, timeout=120)
            require(result.returncode == 0, 'App clone incomplete; preserve and reconcile the selected app')
        current, _ = app_identity(tools, app, target)
        require(not branch or fresh or branch == current, 'Existing app branch differs; preserve it and select explicitly')
        data, contents = project.read('HEAD' if fresh else None)
        require(data is not None, 'App has no registered project; explicit initialization required, no implicit adoption')
        selected = values(data, app)
        staged = []
        for name, content in contents.items():
            destination = Path(os.environ['FACTORY_PRIVATE_ROOT']) / relative(name)
            require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Restore path contains symlink')
            if destination.exists():
                require(read_private(destination) == content, 'Existing private artifact differs; no overwrites')
            else:
                staged.append((destination, content))
        if fresh:
            project.git('checkout', '--quiet')
        for destination, content in staged:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            private_path(destination)
            atomic(destination, content, 0o600)
        if any(item['kind'] == 'journal' and journal(contents[name], data['project_id'])[-1]['state'] != 'complete'
               for name, item in data['artifacts'].items()):
            print('Registry contains unfinished/unknown provider operations; reconcile their outcomes before related writes.', file=sys.stderr)
        return selected


def automatic(record_path, ownership=None):
    if not configured():
        return
    target, app = os.environ['FACTORY_PROJECT_REPOSITORY'], Path(os.environ.get('FACTORY_PROJECT_APP', ''))
    tools = load()
    app_identity(tools, app, target)
    # Read only this app's local registry; remote checks occur in action preflight/checkpoint/publication.
    folder = app / '.factory/project.json'
    require(folder.is_file() and not any(p.is_symlink() for p in (folder, *folder.parents)) and folder.stat().st_size <= 128 * 1024, 'Selected app registry missing')
    data = record(json.loads(folder.read_bytes()))
    require(data['repository'] == target, 'Selected registry belongs to another app')
    values(data, app)
    with locked(app, tools):
        queued = pending(data)
        temporary = dict(data, artifacts=dict(queued), publication='private')
        contents = {name: read_private(Path(os.environ['FACTORY_PRIVATE_ROOT']) / relative(name)) for name in queued}
        collect(temporary, [(record_path, 'journal')] + ([(ownership, 'ownership')] if ownership else []), contents)
        value = dict(schema=1, repository=target, project_id=data['project_id'], artifacts=temporary['artifacts'])
        atomic(pending_file(data), json.dumps(value, sort_keys=True).encode() + b'\n', 0o600)


def preflight(tools=None):
    if not configured():
        return {}
    selected = restore(os.environ['FACTORY_PROJECT_REPOSITORY'], tools=tools)
    os.environ.update(selected)
    return selected


def publication(tools, target, app, revision='HEAD'):
    """Validate the committed registry before a normal app push; never stage or commit."""
    with Project(tools, target, app) as project:
        project.verify()
        app_identity(tools, app, target)
        data, _ = project.read(revision)
        # No registry is required for initial repository/source bootstrap.
        if not project.private:
            commits = project.git('rev-list', '--max-count=129', revision, '--', '.factory').decode().splitlines()
            require(len(commits) <= 128, 'Public registry history requires explicit bounded confidentiality review')
            for commit in commits:
                project.read(commit)
        return data


def reconcile(tools=None, target=None, app=None):
    """Read remote branch state; normal push only if the remote is an ancestor of local."""
    tools = tools or load()
    target = target or os.environ.get('FACTORY_PROJECT_REPOSITORY', '')
    app = app or Path(os.environ.get('FACTORY_PROJECT_APP', ''))
    publication(tools, target, app)
    with Project(tools, target, app) as project:
        branch, head = app_identity(tools, app, target)
        require(head is not None, 'Commit app source and registry before publication')
        # Dirty source/index is preserved and never staged; only the explicit existing commit can be pushed.
        project.verify()
        remote = project.git('ls-remote', '--heads', 'origin', 'refs/heads/' + branch).decode().split()
        require(not remote or len(remote) == 2 and re.fullmatch(r'[a-f0-9]{40}', remote[0]), 'Invalid remote branch readback')
        if remote and remote[0] == head:
            return
        if remote:
            project.git('fetch', '--no-tags', 'origin', 'refs/heads/' + branch)
            require(project.git('merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD', optional=True) is not None,
                    'App branch diverged; reconcile deliberately without reset/force/replaying provider work')
        project.verify()
        project.git('push', 'origin', 'HEAD:refs/heads/' + branch)
        observed = project.git('ls-remote', '--heads', 'origin', 'refs/heads/' + branch).decode().split()
        require(len(observed) == 2 and observed[0] == head, 'App publication outcome unknown; retain commit and reconcile before retry')
