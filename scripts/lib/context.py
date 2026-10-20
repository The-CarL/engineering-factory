"""Strict private Git context records. Storage content is data, never executable input."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import uuid
from urllib.parse import urlsplit

from provider import gh_environment, METADATA
from runtime import ROOT, base_env, digest, known_credentials, load, private_path, read_private, require, run

REPO = r'[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9_.-]{0,99}'
BRANCH = r'[A-Za-z0-9][A-Za-z0-9_./-]{0,199}'
CONFIG = {
    'FACTORY_GITHUB_OWNER': r'[A-Za-z0-9][A-Za-z0-9-]{0,38}',
    'FACTORY_VERCEL_TEAM_ID': r'team_[A-Za-z0-9]+',
    'FACTORY_VERCEL_TEAM_SLUG': r'[A-Za-z0-9][A-Za-z0-9-]{0,99}',
    'VERCEL_PROJECT_ID': r'prj_[A-Za-z0-9]+',
    'FACTORY_AWS_ACCOUNT_ID': r'[0-9]{12}',
    'FACTORY_AWS_ROLE_NAME': r'[A-Za-z0-9+=,.@_-]{1,64}',
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
            and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value['environment'])
            and isinstance(value['resources'], list) and 1 <= len(value['resources']) <= 128, 'Invalid inventory schema/project')
    identities = []
    for item in value['resources']:
        fields = {'provider', 'resource_id', 'resource_type', 'parent_id', 'backend_ref', 'run_id', 'source_commit', 'status', 'ownership'}
        require(isinstance(item, dict) and fields <= set(item) <= fields | {'url'}, 'Invalid inventory resource fields')
        provider, identity = item['provider'], item['resource_id']
        require(provider in ('AWS', 'Vercel', 'GitHub') and isinstance(identity, str) and len(identity) <= 1024, 'Invalid inventory provider/ID')
        pattern = {'AWS': r'(?:arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:[A-Za-z0-9_./:@+=,-]+|[A-Za-z0-9][A-Za-z0-9_.-]{0,255})',
                   'Vercel': r'(?:prj|dpl|team)_[A-Za-z0-9]+', 'GitHub': REPO}[provider]
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
            'source_commit', 'factory_source_commit', 'config', 'artifacts'} and value['schema'] == 1, 'Invalid project context schema')
    project_id(value['project_id'])
    require(re.fullmatch(REPO, value['repository']) and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value['environment'])
            and re.fullmatch(BRANCH, value['branch']) and '..' not in value['branch']
            and (value['source_commit'] is None or re.fullmatch(r'[a-f0-9]{40}', value['source_commit']))
            and re.fullmatch(r'[a-f0-9]{40}', value['factory_source_commit']), 'Invalid project source/environment')
    require(isinstance(value['config'], dict) and set(value['config']) <= set(CONFIG), 'Context cannot supply credentials or executable configuration')
    for key, selected in value['config'].items():
        require(isinstance(selected, str) and re.fullmatch(CONFIG[key], selected), 'Invalid provider target configuration')
    require(value['config'].get('FACTORY_GITHUB_OWNER', '').lower() == value['repository'].split('/')[0], 'Context repository owner mismatch')
    require(isinstance(value['artifacts'], dict) and len(value['artifacts']) <= 256, 'Context artifact count exceeded')
    for name, item in value['artifacts'].items():
        relative(name)
        require(isinstance(item, dict) and set(item) == {'sha256', 'kind'} and item['kind'] in ('journal', 'ownership', 'inventory')
                and re.fullmatch(r'[a-f0-9]{64}', item['sha256']), 'Invalid artifact manifest')
    encoded = json.dumps(value, sort_keys=True).encode()
    require(len(encoded) <= 128 * 1024, 'Project metadata size exceeded')
    clean(encoded)
    return value


def app_identity(tools, app, target):
    require(app.is_absolute() and '..' not in app.parts and not any(p.is_symlink() for p in (app, *app.parents))
            and app != ROOT and not ROOT.is_relative_to(app), 'Invalid independent app path')
    require((app / '.git').is_dir() and not (app / '.git').is_symlink()
            and not (app / '.git/objects/info/alternates').exists(), 'App must be an independent clone')
    def git(*args, optional=False):
        result = subprocess.run([tools['git'], '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                                 '-C', str(app), *args], env=base_env('/tmp'), capture_output=True, timeout=30)
        require(optional or result.returncode == 0, 'Local app identity cannot be verified')
        return result.stdout.decode().strip() if result.returncode == 0 else None
    require(git('rev-parse', '--show-toplevel') == str(app), 'App path differs from Git root')
    allowed = ('https://github.com/' + target, 'https://github.com/' + target + '.git', 'git@github.com:' + target + '.git')
    require(git('remote', 'get-url', '--all', 'origin').lower() in allowed
            and git('remote', 'get-url', '--push', '--all', 'origin').lower() in allowed, 'App origin differs from selected context')
    branch = git('symbolic-ref', '--short', 'HEAD')
    require(re.fullmatch(BRANCH, branch) and '..' not in branch, 'App requires a normal selected branch')
    return branch, git('rev-parse', '--verify', 'HEAD', optional=True)


class Store:
    def __init__(self, tools):
        self.tools = tools
        self.repository = os.environ.get('FACTORY_CONTEXT_REPOSITORY', '').lower()
        require(re.fullmatch(REPO, self.repository) and self.repository.split('/')[0] == os.environ.get('FACTORY_GITHUB_OWNER', '').lower()
                and self.repository != os.environ.get('FACTORY_SOURCE_REPOSITORY', '').lower(), 'Select an independent exact private context repository')
        require(os.environ.get('FACTORY_GITHUB_CREDENTIAL_SOURCE') == 'factory-token', 'Context storage requires explicit factory-token credential selection')
        selected = gh_environment()
        self.directory = Path(os.environ.get('FACTORY_CONTEXT_DIRECTORY', ''))
        require(self.directory.is_absolute() and '..' not in self.directory.parts
                and not any(p.is_symlink() for p in (self.directory, *self.directory.parents)), 'Select a canonical private context directory')
        if not self.directory.exists():
            private_path(self.directory)
            self.directory.mkdir(mode=0o700)
        private_path(self.directory / 'probe')
        self.env = base_env('/tmp')
        self.env.update(GH_TOKEN=selected['GH_TOKEN'], GH_HOST='github.com', GH_PROMPT_DISABLED='1', GH_CONFIG_DIR=str(self.directory))
        self.prefix = [tools['git'], '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'credential.helper=',
                       '-c', 'credential.https://github.com.helper=!' + shlex.quote(tools['gh']) + ' auth git-credential',
                       '-c', 'user.name=Factory context', '-c', 'user.email=factory-context@example.invalid', '-C', str(self.directory)]

    def git(self, *args, optional=False):
        result = subprocess.run([*self.prefix, *args], env=self.env, capture_output=True, timeout=120)
        require(optional or result.returncode == 0, 'Context Git sync failed; preserve local state and reconcile before retrying')
        return result.stdout if result.returncode == 0 else None

    def api(self, target):
        response = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com', 'repos/' + target], self.env, 'GitHub context'))
        require(response.get('full_name', '').lower() == target and isinstance(response.get('private'), bool), 'Context repository target cannot be verified')
        return response

    @contextmanager
    def locked(self):
        lock = self.directory.parent / ('.' + self.directory.name + '.lock')
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            os.close(descriptor)
            yield self
        finally:
            lock.unlink()

    def remote(self, *args):
        info = self.api(self.repository)
        require(info['private'] is True and info.get('archived') is False, 'Context repository must remain private and writable')
        return self.git(*args)

    def sync(self, reconcile=False):
        principal = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com', 'user'], self.env, 'GitHub context'))
        require(isinstance(principal.get('login'), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', principal['login']), 'Context principal cannot be verified')
        owner = self.repository.split('/')[0]
        if principal['login'].lower() != owner:
            member = json.loads(run([self.tools['gh'], 'api', '--hostname', 'github.com',
                'user/memberships/orgs/' + owner], self.env, 'GitHub context'))
            require(member.get('state') == 'active' and member.get('organization', {}).get('login', '').lower() == owner,
                    'Context approved owner membership cannot be verified')
        repository = self.api(self.repository)
        require(repository['private'] is True and repository.get('archived') is False, 'Context repository must remain private and writable')
        self.branch = repository['default_branch']
        require(re.fullmatch(BRANCH, self.branch) and '..' not in self.branch, 'Invalid context branch')
        if not (self.directory / '.git').exists():
            require(not list(self.directory.iterdir()), 'Context directory is not empty; no files changed')
            self.git('init', '--quiet')
            self.git('remote', 'add', 'origin', 'https://github.com/' + self.repository + '.git')
        require((self.directory / '.git').is_dir() and not (self.directory / '.git').is_symlink()
                and not (self.directory / '.git/objects/info/alternates').exists(), 'Context must be an independent Git clone')
        require(self.git('rev-parse', '--show-toplevel').decode().strip() == str(self.directory)
                and self.git('remote', 'get-url', '--all', 'origin').decode().strip() == 'https://github.com/' + self.repository + '.git'
                and self.git('remote', 'get-url', '--push', '--all', 'origin').decode().strip() == 'https://github.com/' + self.repository + '.git', 'Context Git origin differs from approved repository')
        keys = self.git('config', '--local', '--name-only', '--list').decode().lower().splitlines()
        allowed = {'core.repositoryformatversion', 'core.filemode', 'core.bare', 'core.logallrefupdates',
                   'core.ignorecase', 'core.precomposeunicode', 'remote.origin.url', 'remote.origin.fetch'}
        require(set(keys) <= allowed, 'Unexpected context Git configuration')
        require(not self.git('status', '--porcelain', '--untracked-files=all').strip(), 'Context has pending local changes; reconcile without resetting')
        heads = self.remote('ls-remote', '--heads', 'origin', 'refs/heads/' + self.branch)
        if not heads.strip():
            current = self.git('rev-parse', '--verify', 'HEAD', optional=True)
            require(repository.get('size') == 0 and (current is None or reconcile), 'Context branch missing or local publication pending; reconcile')
            if current:
                self.validate_local()
                self.publish_pending()
            return
        self.remote('fetch', '--no-tags', 'origin', 'refs/heads/' + self.branch)
        self.validate_tree('FETCH_HEAD')
        current = self.git('rev-parse', '--verify', 'HEAD', optional=True)
        if current:
            if self.git('merge-base', '--is-ancestor', 'HEAD', 'FETCH_HEAD', optional=True) is None:
                require(reconcile and self.git('merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD', optional=True) is not None,
                        'Context has unpublished/divergent commits; preserve and reconcile without force push')
                self.validate_local()
                self.publish_pending()
            else:
                self.git('merge', '--ff-only', 'FETCH_HEAD')
        else:
            self.git('checkout', '--detach', 'FETCH_HEAD')

    def validate_local(self):
        self.validate_tree('HEAD')
        for path in (self.directory / 'projects').glob('*/project.json'):
            data = record(json.loads(path.read_bytes()))
            require(path.parent.name == data['project_id'], 'Context namespace differs from UUID')
            self.artifacts(data)

    def publish_pending(self):
        head = self.git('rev-parse', 'HEAD').decode().strip()
        self.remote('push', 'origin', 'HEAD:refs/heads/' + self.branch)
        observed = self.remote('ls-remote', '--heads', 'origin', 'refs/heads/' + self.branch).decode().split()
        require(len(observed) == 2 and observed[0] == head, 'Context publication readback differs; preserve and reconcile')

    def validate_tree(self, revision):
        entries = self.git('ls-tree', '-r', '-z', revision).split(b'\0')
        require(len(entries) <= 1025, 'Context tree has too many files')
        total = 0
        for entry in filter(None, entries):
            header, name = entry.decode().split('\t', 1)
            mode, kind, object_id = header.split()
            require(mode == '100644' and kind == 'blob', 'Context symlinks/submodules/executables are forbidden')
            parts = Path(name).parts
            if name != 'README.md':
                require(len(parts) >= 3 and parts[0] == 'projects', 'Unexpected context tree path')
                project_id(parts[1])
                require(parts[2:] == ('project.json',) or len(parts) >= 4 and parts[2] == 'artifacts', 'Unexpected context project path')
                if parts[2] == 'artifacts':
                    relative('/'.join(parts[3:]))
            size = int(self.git('cat-file', '-s', object_id))
            total += size
            require(size <= LIMIT and total <= 16 * LIMIT, 'Context tree byte bounds exceeded')

    def find(self, target):
        require(re.fullmatch(REPO, target) and target != self.repository, 'Select an independent exact app repository')
        matches = []
        for path in sorted((self.directory / 'projects').glob('*/project.json')):
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024, 'Unsafe project context file')
            data = record(json.loads(path.read_bytes()))
            require(path.parent.name == data['project_id'], 'Context namespace differs from UUID')
            if data['repository'] == target:
                matches.append(data)
        require(len(matches) <= 1, 'Duplicate context repositories require reconciliation')
        return matches[0] if matches else None

    def artifacts(self, data):
        result = {}
        base = self.directory / 'projects' / data['project_id'] / 'artifacts'
        total = 0
        for name, item in data['artifacts'].items():
            path = base / relative(name)
            require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe context artifact')
            content = path.read_bytes()
            total += len(content)
            require(total <= LIMIT and digest(content) == item['sha256'], 'Context artifact integrity/size failed')
            parsed = artifact(content, data['project_id'], item['kind'])
            if item['kind'] == 'inventory':
                require(parsed['environment'] == data['environment'], 'Inventory environment differs from selected context')
            result[name] = content
        for name, item in data['artifacts'].items():
            if item['kind'] == 'ownership':
                owner = receipt(result[name], data['project_id'])
                evidence = result.get(owner['creation_record'])
                require(evidence is not None and digest(evidence) == owner['creation_record_sha256'], 'Ownership creation journal missing or changed')
                events = journal(evidence, data['project_id'])
                require(events[-1]['state'] == 'complete' and any(event.get('state') == 'created-resource'
                        and event.get('team') == owner['team_id'] and event.get('project') == owner['project_id']
                        and event.get('name') == owner['project_name'] and event.get('metadata') == owner['metadata'] for event in events),
                        'Ownership receipt lacks completed exact creation evidence')
        return result

    def publish(self):
        self.git('add', '--', 'projects')
        if not self.git('diff', '--cached', '--quiet', optional=True) == b'':
            self.git('commit', '--quiet', '-m', 'chore: checkpoint verified project context')
        # Recheck private visibility immediately before publication. Normal push is the concurrency gate.
        self.validate_local()
        self.remote('push', 'origin', 'HEAD:refs/heads/' + self.branch)


def configured():
    return bool(os.environ.get('FACTORY_CONTEXT_REPOSITORY'))


def values(data, app):
    result = dict(data['config'], FACTORY_PROJECT_ID=data['project_id'], FACTORY_ENVIRONMENT=data['environment'],
                  FACTORY_PROJECT_REPOSITORY=data['repository'], FACTORY_PROJECT_APP=str(app))
    for key, expected in result.items():
        if key == 'FACTORY_AWS_REGION' and os.environ.get(key):
            require(re.fullmatch(CONFIG[key], os.environ[key]), 'Invalid explicit AWS region override')
            result[key] = os.environ[key]
            continue
        require(not os.environ.get(key) or os.environ[key] == expected, 'Selected project/provider context differs; use a clean explicit project selection')
    return result


def checkpoint(target, app=None, additions=(), initialize=False, environment=None, tools=None):
    tools = tools or load()
    store = Store(tools)
    with store.locked():
        store.sync()
        data = store.find(target)
        if data is None:
            require(initialize and app is not None and environment, 'Unknown project; explicit verified initialization required')
            require(store.api(target).get('full_name', '').lower() == target, 'App repository cannot be verified')
            data = dict(schema=1, project_id=project_id(os.environ.get('FACTORY_PROJECT_ID') or str(uuid.uuid4())), repository=target,
                        environment=environment, branch='main', source_commit=None,
                        factory_source_commit=os.environ['FACTORY_SOURCE_REVISION'], config={}, artifacts={})
            require(not (store.directory / 'projects' / data['project_id']).exists(), 'Project UUID already belongs to another context; no namespace reuse')
        contents = store.artifacts(data)
        for key, expected in dict(data['config'], FACTORY_PROJECT_ID=data['project_id'], FACTORY_ENVIRONMENT=data['environment']).items():
            if key == 'FACTORY_AWS_REGION' and os.environ.get(key):
                require(re.fullmatch(CONFIG[key], os.environ[key]), 'Invalid explicit AWS region override')
                continue
            require(not os.environ.get(key) or os.environ[key] == expected, 'Checkpoint selected targets differ from saved project')
        if app is not None:
            data['branch'], data['source_commit'] = app_identity(tools, app, target)
        data['factory_source_commit'] = os.environ['FACTORY_SOURCE_REVISION']
        data['config'].update({key: os.environ[key] for key in CONFIG if os.environ.get(key)
                               and (key != 'FACTORY_AWS_REGION' or key not in data['config'])})
        record(data)
        for source, kind in additions:
            source = Path(source)
            name = str(source.relative_to(Path(os.environ['FACTORY_PRIVATE_ROOT'])))
            relative(name)
            content = read_private(source)
            if kind == 'journal':
                events = journal(content, data['project_id'])
                require(all(not event.get('repository') or event['repository'] == target for event in events), 'Journal repository differs from selected app')
            else:
                parsed = artifact(content, data['project_id'], kind)
                if kind == 'inventory':
                    require(parsed['environment'] == data['environment'], 'Inventory environment differs from selected context')
            if kind == 'ownership':
                owner = receipt(content, data['project_id'])
                require(owner['metadata']['factorySourceRepo'].lower() == target, 'Ownership source differs from selected app')
                evidence = Path(os.environ['FACTORY_PRIVATE_ROOT']) / owner['creation_record']
                raw = read_private(evidence)
                journal(raw, data['project_id'])
                require(digest(raw) == owner['creation_record_sha256'], 'Ownership journal digest mismatch')
                contents[owner['creation_record']] = raw
                data['artifacts'][owner['creation_record']] = dict(kind='journal', sha256=digest(raw))
            contents[name] = content
            data['artifacts'][name] = dict(kind=kind, sha256=digest(content))
        require(sum(map(len, contents.values())) <= LIMIT, 'Context project byte bounds exceeded')
        record(data)
        folder = store.directory / 'projects' / data['project_id']
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name, content in contents.items():
            destination = folder / 'artifacts' / relative(name)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(content)
            destination.chmod(0o644)
        (folder / 'project.json').write_text(json.dumps(data, sort_keys=True) + '\n')
        (folder / 'project.json').chmod(0o644)
        store.artifacts(data)
        store.publish()
        return data


def restore(target, app=None, tools=None):
    tools = tools or load()
    store = Store(tools)
    with store.locked():
        store.sync()
        data = store.find(target)
        require(data is not None, 'Unknown project; no automatic adoption or restore')
        contents = store.artifacts(data)
        store.api(target)  # App visibility is independent from private context confidentiality.
        app = app or ROOT / 'workspaces' / target
        require(app.is_absolute() and '..' not in app.parts and not any(p.is_symlink() for p in (app, *app.parents))
                and app != ROOT and not ROOT.is_relative_to(app), 'Invalid restore app path')
        values(data, app)  # Reject conflicting selected targets before any app/artifact writes.
        existing_app = app.exists()
        if not existing_app:
            app.parent.mkdir(parents=True, exist_ok=True)
            command = [*store.prefix[:-2], 'clone', '--no-tags', *(['--branch', data['branch']] if data['source_commit'] else []), 'https://github.com/' + target + '.git', str(app)]
            run(command, store.env, 'GitHub context clone')
        branch, commit = app_identity(tools, app, target)
        require(commit is not None or data['source_commit'] is None, 'App source is incomplete; preserve and reconcile the interrupted clone')
        if not existing_app:
            require(branch == data['branch'], 'Restored app branch differs from durable context')
        if not existing_app and data['source_commit']:
            result = subprocess.run([tools['git'], '-C', str(app), 'merge-base', '--is-ancestor', data['source_commit'], commit],
                                    env=base_env('/tmp'), capture_output=True, timeout=30)
            require(result.returncode == 0, 'App source is behind or diverges from durable context; preserve and reconcile')
        pending = []
        root = Path(os.environ['FACTORY_PRIVATE_ROOT'])
        for name, content in contents.items():
            destination = root / relative(name)
            require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Restore path contains a symlink')
            if destination.exists():
                require(read_private(destination) == content, 'Existing private artifact differs; no restore overwrites')
            else:
                pending.append((destination, content))
        for destination, content in pending:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            private_path(destination)
            with destination.open('xb') as stream:
                os.chmod(destination, 0o600)
                stream.write(content)
        return values(data, app)


def automatic(record_path, ownership=None):
    if not configured():
        return
    target = os.environ.get('FACTORY_PROJECT_REPOSITORY', '')
    if not target:
        return  # Context-free reads/repository bootstrap have no project namespace to export yet.
    additions = [(record_path, 'journal')]
    if ownership:
        additions.append((ownership, 'ownership'))
    app = Path(os.environ['FACTORY_PROJECT_APP']) if os.environ.get('FACTORY_PROJECT_APP') else None
    try:
        checkpoint(target, app, additions)
    except Exception:
        from provider import ProviderError
        raise ProviderError('Provider result retained; durable context pending. Reconcile storage without replaying the provider operation') from None


def preflight(tools=None):
    if not configured() or not os.environ.get('FACTORY_PROJECT_REPOSITORY'):
        return {}
    target = os.environ['FACTORY_PROJECT_REPOSITORY']
    selected = restore(target, Path(os.environ['FACTORY_PROJECT_APP']) if os.environ.get('FACTORY_PROJECT_APP') else None, tools)
    os.environ.update(selected)
    return selected


def reconcile(tools=None):
    store = Store(tools or load())
    with store.locked():
        store.sync(reconcile=True)
        store.validate_local()
