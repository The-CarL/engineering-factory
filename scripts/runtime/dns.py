#!/usr/bin/env python3
"""Plan/reconcile simple DNS records from native AWS readbacks; performs no provider calls."""
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from dns_records import configured, inspect, record, verify_zone
from runtime import Parser, cli, digest, known_credentials, load, private_path, project_scope, read_private, require


def plan(zone, records, desired, config, project, environment, source, run_id):
    project_scope(project, environment)
    require(re.fullmatch(r'[a-f0-9]{40}', source) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', run_id),
            'Set the exact app source commit and operation ID')
    require(config, 'Configure the approved DNS zone ID and name')
    verify_zone(zone, config)
    desired = record(desired, config['FACTORY_AWS_DNS_ZONE_NAME'])
    state = inspect(records, desired, config['FACTORY_AWS_DNS_ZONE_NAME'])
    batch = {'Changes': [{'Action': 'CREATE', 'ResourceRecordSet': desired}] if state == 'absent' else []}
    receipt = dict(schema=1, project_id=project, environment=environment, source_commit=source, run_id=run_id,
                   zone=config, record=desired, before=state, state='planned' if state == 'absent' else 'reconciled-existing',
                   batch_sha256=digest(json.dumps(batch, sort_keys=True).encode()), created_by_this_operation=False)
    return batch, receipt


def verify(receipt, zone, records, response=None, change=None):
    require(receipt.get('schema') == 1 and receipt.get('state') in ('planned', 'reconciled-existing')
            and receipt.get('created_by_this_operation') is False, 'Use an unmodified original plan receipt')
    config = configured(receipt['zone'])
    _, expected = plan(zone, {'ResourceRecordSets': []} if receipt['before'] == 'absent' else records,
                       receipt['record'], config, receipt['project_id'], receipt['environment'], receipt['source_commit'], receipt['run_id'])
    require(receipt == expected, 'Original plan receipt integrity failed')
    require(inspect(records, receipt['record'], config['FACTORY_AWS_DNS_ZONE_NAME']) == 'matching-existing',
            'Desired DNS record is not present in exact provider readback')
    result = dict(receipt)
    if receipt['before'] == 'absent':
        require(isinstance(response, dict) and isinstance(change, dict), 'Creation response and completed get-change readback are required')
        submitted, completed = response['ChangeInfo'], change['ChangeInfo']
        require(isinstance(submitted.get('Id'), str) and re.fullmatch(r'/change/[A-Z0-9]+', submitted['Id'])
                and submitted.get('Status') in ('PENDING', 'INSYNC') and completed.get('Id') == submitted['Id']
                and completed.get('Status') == 'INSYNC', 'The same submitted DNS change must be INSYNC')
        result.update(state='verified-created', created_by_this_operation=True, change_id=submitted['Id'])
    else:
        require(response is None and change is None, 'An existing matching record was not created by this plan')
        result['state'] = 'verified-existing'
    return result


def read(path):
    return json.loads(read_private(path))


def write(path, value):
    data = json.dumps(value, sort_keys=True, indent=2).encode() + b'\n'
    require(not any(secret and secret.encode() in data for secret in known_credentials()), 'Credential-like DNS artifact rejected')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        output.write(data)


def main():
    parser = Parser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    planning = sub.add_parser('plan')
    planning.add_argument('--desired', required=True)
    planning.add_argument('--source-commit', required=True)
    planning.add_argument('--run-id', required=True)
    planning.add_argument('--batch', required=True)
    checking = sub.add_parser('verify')
    checking.add_argument('--plan', required=True)
    checking.add_argument('--response')
    checking.add_argument('--change')
    for selected in (planning, checking):
        selected.add_argument('--zone', required=True)
        selected.add_argument('--records', required=True)
        selected.add_argument('--receipt', required=True)
    args = parser.parse_args()
    load()
    output = private_path(args.receipt)
    if args.command == 'plan':
        batch_path = private_path(args.batch)
        require(batch_path != output, 'Batch and receipt files must differ')
        batch, receipt = plan(read(args.zone), read(args.records), read(args.desired), configured(os.environ),
                              os.environ.get('FACTORY_PROJECT_ID', ''), os.environ.get('FACTORY_ENVIRONMENT', ''),
                              args.source_commit, args.run_id)
        write(batch_path, batch)
    else:
        receipt = verify(read(args.plan), read(args.zone), read(args.records),
                         read(args.response) if args.response else None, read(args.change) if args.change else None)
    write(output, receipt)
    print('DNS artifact retained privately; no provider request was made. State: ' + receipt['state'])


if __name__ == '__main__':
    cli(main)
