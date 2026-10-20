#!/usr/bin/env python3
"""One explicit Vercel REST operation with private inputs/results; no automatic retry."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from provider import METADATA, Vercel
from runtime import Operation, Parser, cli, digest, event, known_credentials, load, private_path, read_private, require, valid_environment


def provenance(path):
    require(path, 'Mutations require a private canonical provenance record')
    meta = json.loads(read_private(path))
    require(isinstance(meta, dict) and set(meta) == set(METADATA)
            and all(isinstance(value, str) and 0 < len(value) <= 256 for value in meta.values()), 'Provide exactly the 13 canonical provenance fields')
    project = os.environ.get('FACTORY_PROJECT_ID', '')
    require(str(uuid.UUID(project)) == project and uuid.UUID(project).int != 0 and meta['factoryProjectId'] == project,
            'Factory project UUID differs from private context')
    require(meta['factoryManagedBy'] == 'engineering-factory' and meta['factoryProvenanceVersion'] == '1'
            and meta['factoryEnvironment'] == os.environ.get('FACTORY_ENVIRONMENT')
            and valid_environment(meta['factoryEnvironment']), 'Invalid project/environment provenance')
    for key in ('factorySourceCommit', 'factoryLastSourceCommit'):
        require(re.fullmatch(r'[a-f0-9]{40}', meta[key]), 'Exact source commits are required')
    for key in ('factoryOwner', 'factoryCreatedBy', 'factoryCreationRunId', 'factoryLastRunId'):
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', meta[key]) and not re.fullmatch(r'[0-9]{12}', meta[key]), 'Use nonsecret owner/actor/run aliases')
    require(re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', meta['factorySourceRepo']), 'Use a nonsecret owner/repository source alias')
    created = datetime.fromisoformat(meta['factoryCreatedAt'].replace('Z', '+00:00'))
    require(created.tzinfo is not None and created.utcoffset().total_seconds() == 0
            and created <= datetime.now(timezone.utc), 'Creation timestamp must be UTC and not in the future')
    if meta['factoryExpiresAt'] != 'none':
        expiry = datetime.fromisoformat(meta['factoryExpiresAt'].replace('Z', '+00:00'))
        require(expiry.tzinfo is not None and expiry > created, 'Expiry must be later than creation, or none for approved nonexpiring retention')
    require(not any(value and value in json.dumps(meta) for value in known_credentials()), 'Credential-like provenance rejected')
    return meta


def owned(path, team, project, meta):
    require(path, 'Existing project mutations require a journaled factory ownership receipt; no automatic adoption')
    record = json.loads(read_private(path))
    require(record.get('schema') == 1 and record.get('factory_project_id') == meta['factoryProjectId']
            and record.get('team_id') == team and record.get('project_id') == project['id']
            and record.get('project_name') == project['name'], 'Private project ownership differs from target/context')
    relative = Path(record.get('creation_record', ''))
    require(not relative.is_absolute() and '..' not in relative.parts, 'Invalid ownership creation record reference')
    evidence = read_private(Path(os.environ['FACTORY_PRIVATE_ROOT']) / relative)
    require(digest(evidence) == record.get('creation_record_sha256'), 'Ownership creation evidence integrity failed')
    events = [json.loads(line) for line in evidence.splitlines()]
    require(events and events[-1].get('state') == 'complete' and any(item.get('state') == 'created-resource'
            and item.get('team') == team and item.get('project') == project['id'] and item.get('name') == project['name']
            and item.get('metadata') == record.get('metadata') for item in events), 'Ownership needs successful exact project creation/readback evidence')
    require(record.get('metadata', {}).get('factoryProjectId') == meta['factoryProjectId'], 'Ownership UUID mismatch')
    return record


def execute(args):
    tools = load()
    from context import preflight
    preflight(tools)
    team = os.environ.get('FACTORY_VERCEL_TEAM_ID', '')
    slug = os.environ.get('FACTORY_VERCEL_TEAM_SLUG', '')
    require(re.fullmatch(r'team_[A-Za-z0-9]+', team) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', slug), 'Set exact approved Vercel team ID/slug')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', args.project), 'Specify an exact project name or ID')
    require(re.fullmatch(r'/v\d+/(?:projects|deployments)(?:/[A-Za-z0-9_.-]+)*', args.path)
            and '..' not in args.path, 'Use a project/deployment API path without query, redirect or endpoint override')
    payload = json.loads(read_private(args.request)) if args.request else None
    require(payload is None or isinstance(payload, (dict, list)), 'API request must be a reviewed JSON object or array')
    require(args.method == 'GET' or payload is not None or args.method == 'DELETE', 'Mutations require a reviewed private JSON request')
    require(not any(value and value in json.dumps(payload) for value in known_credentials()), 'Factory credential in API payload rejected')
    mutation = args.method != 'GET'
    meta = provenance(getattr(args, 'provenance', None)) if mutation else None
    client = Vercel()
    scope = '?teamId=' + team
    principal = client.request('GET', '/v2/user').get('user')
    require(isinstance(principal, dict) and isinstance(principal.get('id'), str) and principal['id'], 'Vercel principal cannot be verified')
    actual_team = client.request('GET', '/v2/teams/' + team)
    require(actual_team.get('id') == team and actual_team.get('slug') == slug, 'Vercel team identity mismatch')
    creation = args.method == 'POST' and args.path == '/v11/projects'
    if creation:
        require(getattr(args, 'owner_record', None), 'New project creation requires a new private ownership receipt path')
        ownership_path = private_path(args.owner_record)
        require(meta['factoryCreationRunId'] == meta['factoryLastRunId'] and meta['factorySourceCommit'] == meta['factoryLastSourceCommit'], 'Creation provenance must initialize original/latest fields together')
        require(isinstance(payload, dict), 'Project creation requires a JSON object')
        require(payload.get('name') == args.project and payload.get('publicSource') is False,
                'Project creation target/source visibility mismatch')
        require(payload.get('ssoProtection') == {'deploymentType': 'all'} and not payload.get('gitRepository'),
                'New project requires all-deployment protection and no automatic source-linked build')
        inventory = client.request('GET', '/v9/projects' + scope + '&search=' + args.project)
        pagination = inventory.get('pagination') or {}
        require(isinstance(inventory.get('projects'), list) and isinstance(pagination, dict) and not pagination.get('next')
                and not any(project.get('name') == args.project for project in inventory['projects']),
                'Existing project name requires reconciliation, not creation')
    else:
        project = client.request('GET', '/v9/projects/' + args.project + scope)
        require(args.project in (project.get('id'), project.get('name')) and project.get('accountId') == team,
                'Vercel project identity mismatch')
        ownership = owned(getattr(args, 'owner_record', None), team, project, meta) if mutation else None
        parts = args.path.split('/')
        if parts[2] == 'projects':
            require(len(parts) >= 4 and parts[3] == project['id'], 'Project API path must use the exact verified ID')
            if mutation:
                for key in ('factorySourceRepo', 'factorySourceCommit', 'factoryCreatedBy', 'factoryCreatedAt', 'factoryCreationRunId'):
                    require(meta[key] == ownership['metadata'][key], 'Project updates must preserve original creation attribution')
        elif args.method == 'POST' and args.path == '/v13/deployments':
            require(isinstance(payload, dict), 'Deployment creation requires a JSON object')
            require(payload.get('project') == project['id'] and payload.get('name') == project['name'], 'Deployment payload target mismatch')
            require(payload.get('meta') == meta, 'Deployment request must include the exact canonical provenance metadata')
        else:
            require(len(parts) >= 4, 'Use an exact known deployment ID')
            deployment = client.request('GET', '/v13/deployments/' + parts[3] + scope)
            require(deployment.get('projectId') == project['id'], 'Deployment belongs to another project')
            if mutation:
                previous = deployment.get('meta', {})
                require(isinstance(previous, dict) and previous.get('factoryProjectId') == meta['factoryProjectId'], 'Deployment provenance is missing or belongs to another factory project')
                for key in ('factorySourceRepo', 'factorySourceCommit', 'factoryCreatedBy', 'factoryCreatedAt', 'factoryCreationRunId'):
                    require(meta[key] == previous.get(key), 'Deployment updates must preserve original creation attribution')
    operation = Operation(args.record, args.output, 'Vercel', json.dumps([args.method, args.path, payload], sort_keys=True).encode())
    try:
        event(operation.record, 'identity-verified', principal=principal['id'], team=team, project=args.project, metadata=meta)
        result = client.request(args.method, args.path + scope, payload)
        operation.received(json.dumps(result, sort_keys=True).encode() + b'\n', known_credentials())
        if creation:
            require(isinstance(result.get('id'), str) and result.get('name') == args.project and result.get('accountId') == team,
                    'Project creation response mismatch; reconcile without retry')
            saved = client.request('GET', '/v9/projects/' + result['id'] + scope)
            require(saved.get('id') == result['id'] and saved.get('name') == args.project and saved.get('accountId') == team
                    and saved.get('publicSource') is False and isinstance(saved.get('ssoProtection'), dict)
                    and saved['ssoProtection'].get('deploymentType') == 'all',
                    'Created project configuration readback mismatch; reconcile without retry')
            event(operation.record, 'created-resource', team=team, project=result['id'], name=args.project, metadata=meta)
        operation.finish(json.dumps(result, sort_keys=True).encode() + b'\n', known_credentials(), quiet=creation, persist=not creation)
        if creation:
            receipt = dict(schema=1, factory_project_id=meta['factoryProjectId'], team_id=team, project_id=result['id'],
                           project_name=args.project, metadata=meta,
                           creation_record=str(operation.record.relative_to(Path(os.environ['FACTORY_PRIVATE_ROOT']))),
                           creation_record_sha256=digest(operation.record.read_bytes()))
            with os.fdopen(os.open(ownership_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
                stream.write(json.dumps(receipt, sort_keys=True) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            from context import automatic
            automatic(operation.record, ownership_path)
            print('Project created/read back; private ownership and provenance retained.')
    except Exception:
        operation.failed()
        raise


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--method', choices=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], default='GET')
    parser.add_argument('--project', required=True)
    parser.add_argument('--path', required=True)
    parser.add_argument('--request')
    parser.add_argument('--provenance', help='Private canonical 13-field metadata JSON for mutations')
    parser.add_argument('--owner-record', help='Private project ownership receipt (new for creation, required for mutations)')
    parser.add_argument('--record', required=True)
    parser.add_argument('--output', required=True)
    execute(parser.parse_args())


if __name__ == '__main__':
    cli(main)
