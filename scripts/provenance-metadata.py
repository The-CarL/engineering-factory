#!/usr/bin/env python3
"""Prepare readable provenance and AWS tag payloads locally; never call a provider."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from context import metadata
from provider import preserve_creation_metadata, validate_metadata_shape
from runtime import Parser, cli, known_credentials, private_path, project_scope, read_private, require

AWS_METADATA = {
    'factoryProjectId': 'project-id', 'factoryEnvironment': 'environment', 'factoryOwner': 'owner',
    'factoryManagedBy': 'managed-by', 'factorySourceRepo': 'source-repo',
    'factorySourceCommit': 'source-commit', 'factoryCreatedBy': 'created-by',
    'factoryCreatedAt': 'created-at', 'factoryCreationRunId': 'creation-run-id',
    'factoryLastRunId': 'last-run-id', 'factoryLastSourceCommit': 'last-source-commit',
    'factoryProvenanceVersion': 'provenance-version', 'factoryExpiresAt': 'expires-at',
    'factoryProjectName': 'project-name', 'factoryRepoName': 'repo-name',
    'factorySourceBranch': 'source-branch', 'factorySourceAuthor': 'source-author',
    'factoryLastSourceBranch': 'last-source-branch', 'factoryLastSourceAuthor': 'last-source-author',
}


def git(source, *args):
    env = dict(PATH=os.environ.get('PATH', os.defpath), GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
               GIT_NO_REPLACE_OBJECTS='1')
    result = subprocess.run(['git', '--no-pager', '-c', 'core.hooksPath=/dev/null',
        '-c', 'core.fsmonitor=false', '-C', str(source), *args],
        env=env, capture_output=True, timeout=30)
    require(result.returncode == 0, 'Local source metadata cannot be verified')
    return result.stdout.decode('utf-8').rstrip('\n')


def source_facts(source, repo):
    require(source.is_absolute() and '..' not in source.parts
            and not any(p.is_symlink() for p in (source, *source.parents)),
            'Use a canonical absolute app source path without symlinks')
    require(git(source, 'rev-parse', '--show-toplevel') == str(source),
            'Source path must be the exact app Git root')
    origin = git(source, 'remote', 'get-url', '--all', 'origin')
    patterns = (r'https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?',
                r'git@github\.com:([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?',
                r'ssh://git@github\.com/([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?')
    matches = [re.fullmatch(pattern, origin) for pattern in patterns]
    require(any(match and match[1].lower() == repo.lower() for match in matches),
            'Source origin differs from the provenance repository')
    require(not git(source, 'status', '--porcelain=v1', '--untracked-files=normal'),
            'Use clean committed app source for provenance')
    return (git(source, 'rev-parse', 'HEAD'), git(source, 'branch', '--show-current') or 'detached',
            git(source, 'show', '--no-patch', '--format=%an', 'HEAD'))


def prepare(meta, source, project_name, mode, branch_label=None, author_label=None):
    metadata(meta)
    commit, branch, author = source_facts(source, meta['factorySourceRepo'])
    require(commit == meta['factoryLastSourceCommit'], 'Source HEAD differs from latest provenance commit')
    require(mode in ('create', 'update'), 'Select create or update metadata preparation')
    current = dict(factoryProjectName=project_name,
                   factoryRepoName=meta['factorySourceRepo'].rsplit('/', 1)[-1],
                   factoryLastSourceBranch=branch_label if branch_label is not None else branch,
                   factoryLastSourceAuthor=author_label if author_label is not None else author)
    result = dict(meta, **current)
    if mode == 'create':
        require(meta['factorySourceCommit'] == commit
                and meta['factoryCreationRunId'] == meta['factoryLastRunId'],
                'New creation metadata must initialize original/latest source and run together')
        result.update(factorySourceBranch=current['factoryLastSourceBranch'],
                      factorySourceAuthor=current['factoryLastSourceAuthor'])
    else:
        # A commit does not establish the historical creation branch or human actor.
        result.update(factorySourceBranch=meta.get('factorySourceBranch', 'unknown'),
                      factorySourceAuthor=meta.get('factorySourceAuthor', 'unknown'))
    preserve_creation_metadata(result, meta)
    validate_metadata_shape(result)
    metadata(result)
    encoded = json.dumps(result)
    require(not any(secret and secret in encoded for secret in known_credentials()),
            'Credential-like provenance rejected')
    tags = {'factory:' + AWS_METADATA[key]: value for key, value in result.items()}
    tags['factory:s'] = project_scope(meta['factoryProjectId'], meta['factoryEnvironment'])
    return result, tags


def execute(args):
    meta = json.loads(read_private(args.input))
    result, tags = prepare(meta, args.source, args.project_name, args.mode,
                           args.branch_label, args.author_label)
    output = private_path(args.output)
    contents = {
        'provenance.json': result,
        'aws-tag-map.json': tags,
        'aws-tags.json': [{'Key': key, 'Value': value} for key, value in sorted(tags.items())],
    }
    # Validate everything before the exclusive local output directory is created.
    output.mkdir(mode=0o700)
    for name, value in contents.items():
        with os.fdopen(os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    print('Prepared readable provenance and AWS tag payloads privately. No provider calls or resource changes.')


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--input', required=True, help='Private canonical provenance JSON')
    parser.add_argument('--source', required=True, type=Path, help='Exact clean app Git root')
    parser.add_argument('--project-name', required=True, help='Approved nonsecret project display name')
    parser.add_argument('--mode', required=True, choices=('create', 'update'),
                        help='Prepare a new resource record or preserve existing creation history')
    parser.add_argument('--branch-label', help='Explicit safe display alias when the Git ref cannot be tagged')
    parser.add_argument('--author-label', help='Explicit safe display alias when the Git author cannot be tagged')
    parser.add_argument('--output', required=True, help='New directory under FACTORY_PRIVATE_ROOT')
    execute(parser.parse_args())


if __name__ == '__main__':
    cli(main)
