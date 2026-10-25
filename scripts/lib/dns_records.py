"""Exact DNS targets and CREATE-first reconciliation; no provider calls or ownership claims."""
import re

DNS_TYPES = ('A', 'AAAA', 'CNAME', 'TXT', 'MX', 'CAA', 'SRV')
ZONE_KEYS = ('FACTORY_AWS_DNS_ZONE_ID', 'FACTORY_AWS_DNS_ZONE_NAME')


def name(value, record=False):
    if not isinstance(value, str):
        raise ValueError('DNS name must be text')
    value = value.removesuffix('.')
    label = r'[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?' if record else r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if len(value) > 253 or len(value.split('.')) < 2 or not all(re.fullmatch(label, part) for part in value.split('.')):
        raise ValueError('Use an exact lowercase DNS name without wildcards or escapes')
    return value


def target(zone_id, zone_name):
    if not isinstance(zone_id, str) or not re.fullmatch(r'Z[A-Z0-9]{1,63}', zone_id):
        raise ValueError('Set an exact Route53 hosted-zone ID without an ARN or path')
    normalized = name(zone_name)
    if normalized != zone_name:
        raise ValueError('Configure a normalized zone name without a trailing dot')
    return {ZONE_KEYS[0]: zone_id, ZONE_KEYS[1]: normalized}


def configured(environment):
    values = [environment.get(key, '') for key in ZONE_KEYS]
    if not any(values):
        return {}
    if not all(values):
        raise ValueError('Configure DNS zone ID and name together')
    return target(*values)


def verify_zone(response, config):
    zone = response['HostedZone']
    if (zone['Id'] != '/hostedzone/' + config[ZONE_KEYS[0]]
            or name(zone['Name']) != config[ZONE_KEYS[1]] or zone['Config']['PrivateZone'] is not False):
        raise ValueError('Readback must match the exact approved public hosted zone ID and name')


def record(value, zone_name):
    if (not isinstance(value, dict) or set(value) != {'Name', 'Type', 'TTL', 'ResourceRecords'}
            or value['Type'] not in DNS_TYPES or type(value['TTL']) is not int or not 60 <= value['TTL'] <= 86400):
        raise ValueError('Use a reviewed simple record with an allowed type and TTL 60..86400; aliases/routing need native CLI review')
    normalized = name(value['Name'], record=True)
    if not normalized.endswith('.' + zone_name):
        raise ValueError('Application DNS must be a child of the approved zone')
    records = value['ResourceRecords']
    if (not isinstance(records, list) or not 1 <= len(records) <= 100 or any(not isinstance(item, dict)
            or set(item) != {'Value'} or not isinstance(item['Value'], str) or not item['Value']
            or len(item['Value']) > 4096 or '\n' in item['Value'] or '\r' in item['Value'] for item in records)):
        raise ValueError('Invalid resource-record values')
    values = sorted(item['Value'] for item in records)
    if len(set(values)) != len(values) or (value['Type'] == 'CNAME' and len(values) != 1):
        raise ValueError('Duplicate values or invalid CNAME cardinality')
    return dict(Name=normalized + '.', Type=value['Type'], TTL=value['TTL'], ResourceRecords=[{'Value': item} for item in values])


def inspect(response, requested, zone_name):
    # A complete AWS CLI auto-paginated response is required, including other types at this name.
    if not isinstance(response, dict) or not isinstance(response.get('ResourceRecordSets'), list) or any(
            response.get(key) for key in ('IsTruncated', 'NextToken', 'NextRecordName', 'NextRecordType', 'NextRecordIdentifier')) or any(
                not isinstance(item, dict) or not isinstance(item.get('Name'), str) or not isinstance(item.get('Type'), str)
                for item in response['ResourceRecordSets']):
        raise ValueError('Use complete, unfiltered AWS CLI record-set readback with no remaining page')
    same = [item for item in response['ResourceRecordSets'] if isinstance(item, dict)
            and isinstance(item.get('Name'), str) and item['Name'].lower().removesuffix('.') == requested['Name'][:-1]]
    matching = [item for item in same if item['Type'] == requested['Type']]
    if len(matching) > 1 or any('SetIdentifier' in item or 'AliasTarget' in item for item in same):
        raise ValueError('Routing or alias records at this name require explicit native CLI review')
    if (requested['Type'] == 'CNAME' and any(item['Type'] != 'CNAME' for item in same)
            or requested['Type'] != 'CNAME' and any(item['Type'] == 'CNAME' for item in same)):
        raise ValueError('Existing CNAME/other-type conflict; preserve it')
    if matching:
        if record(matching[0], zone_name) != requested:
            raise ValueError('Existing record differs; preserve it and review ownership and an explicit before/after update')
        return 'matching-existing'
    return 'absent'
