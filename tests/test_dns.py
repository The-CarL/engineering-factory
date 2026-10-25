"""Offline DNS readback/CREATE-first controls. No provider authentication or writes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import dns_records
from provider import ProviderError
spec = importlib.util.spec_from_file_location('runtime_dns', ROOT / 'scripts/runtime/dns.py')
dns = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dns)


class DNSTests(unittest.TestCase):
    def setUp(self):
        self.config = dns_records.target('ZEXAMPLE', 'example.test')
        self.zone = {'HostedZone': {'Id': '/hostedzone/ZEXAMPLE', 'Name': 'example.test.', 'Config': {'PrivateZone': False}}}
        self.records = {'ResourceRecordSets': [{'Name': r'\052.elsewhere.example.test.', 'Type': 'A',
                                             'TTL': 300, 'ResourceRecords': [{'Value': '192.0.2.1'}]}]}
        self.desired = dict(Name='hello.core.example.test', Type='CNAME', TTL=300,
                            ResourceRecords=[{'Value': 'edge.example.net.'}])
        self.project, self.environment = '12345678-1234-1234-1234-123456789abc', 'validation'

    def plan(self, records=None):
        return dns.plan(self.zone, self.records if records is None else records, self.desired, self.config,
                        self.project, self.environment, 'a' * 40, 'dns-run')

    def test_plan_absent_record_is_one_create_and_preserves_other_records(self):
        before = copy.deepcopy(self.records)
        batch, receipt = self.plan()
        self.assertEqual(batch, {'Changes': [{'Action': 'CREATE', 'ResourceRecordSet': dict(self.desired, Name=self.desired['Name'] + '.')} ]})
        self.assertEqual(receipt['before'], 'absent')
        self.assertFalse(receipt['created_by_this_operation'])
        self.assertEqual(self.records, before)
        self.assertEqual(receipt['project_id'], self.project)
        self.assertEqual(receipt['zone'], self.config)

    def test_matching_existing_record_never_claims_creation_or_cleanup_ownership(self):
        existing = dict(self.desired, Name=self.desired['Name'] + '.')
        records = {'ResourceRecordSets': [existing]}
        batch, receipt = self.plan(records)
        self.assertEqual(batch, {'Changes': []})
        self.assertEqual(receipt['state'], 'reconciled-existing')
        result = dns.verify(receipt, self.zone, records)
        self.assertEqual(result['state'], 'verified-existing')
        self.assertFalse(result['created_by_this_operation'])
        with self.assertRaises(ProviderError):
            dns.verify(receipt, self.zone, records, {}, {})

    def test_conflict_routing_alias_and_incomplete_readbacks_fail_before_plan(self):
        conflict = dict(self.desired, TTL=600)
        for records in ({'ResourceRecordSets': [conflict]},
                        {'ResourceRecordSets': [dict(self.desired, Type='A')]},
                        {'ResourceRecordSets': [dict(self.desired, SetIdentifier='other')]},
                        {'ResourceRecordSets': [dict(self.desired, AliasTarget={})]},
                        {'ResourceRecordSets': [], 'IsTruncated': True},
                        {'ResourceRecordSets': [], 'NextToken': 'more'}, {'ResourceRecordSets': [{}]}):
            with self.subTest(records=records), self.assertRaises((ValueError, ProviderError)):
                self.plan(records)

    def test_zone_pair_public_zone_and_exact_targets_are_required(self):
        for config in ({'FACTORY_AWS_DNS_ZONE_ID': 'ZEXAMPLE'}, {'FACTORY_AWS_DNS_ZONE_NAME': 'example.test'},
                       dict(self.config, FACTORY_AWS_DNS_ZONE_ID='/hostedzone/ZEXAMPLE'),
                       dict(self.config, FACTORY_AWS_DNS_ZONE_NAME='*.example.test'),
                       dict(self.config, FACTORY_AWS_DNS_ZONE_NAME='EXAMPLE.test'),
                       dict(self.config, FACTORY_AWS_DNS_ZONE_NAME='example.test.')):
            with self.assertRaises(ValueError):
                dns_records.configured(config)
        self.assertEqual(dns_records.configured({}), {})
        for field, value in (('Id', '/hostedzone/ZOTHER'), ('Name', 'other.test.'), ('Config', {'PrivateZone': True})):
            zone = copy.deepcopy(self.zone)
            zone['HostedZone'][field] = value
            with self.assertRaises(ValueError):
                dns_records.verify_zone(zone, self.config)

    def test_unsafe_record_shapes_names_types_and_ttls_rejected(self):
        for changes in (dict(Name='*.example.test'), dict(Name=r'\052.example.test'), dict(Name='example.test'),
                        dict(Name='other.test'), dict(Type='NS'), dict(Type='SOA'), dict(Type='DS'),
                        dict(TTL=0), dict(TTL=True), dict(AliasTarget={}),
                        dict(ResourceRecords=[{'Value': 'value\nnext'}])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                dns_records.record(dict(self.desired, **changes), 'example.test')
        validation = dict(self.desired, Name='_hash.hello.core.example.test')
        self.assertEqual(dns_records.record(validation, 'example.test')['Name'], validation['Name'] + '.')

    def test_completion_requires_matching_record_and_same_insync_change(self):
        batch, receipt = self.plan()
        records = {'ResourceRecordSets': [batch['Changes'][0]['ResourceRecordSet']]}
        submitted = {'ChangeInfo': {'Id': '/change/CEXAMPLE', 'Status': 'PENDING'}}
        completed = {'ChangeInfo': {'Id': '/change/CEXAMPLE', 'Status': 'INSYNC'}}
        result = dns.verify(receipt, self.zone, records, submitted, completed)
        self.assertTrue(result['created_by_this_operation'])
        self.assertEqual(result['change_id'], '/change/CEXAMPLE')
        for after, response, change in ((self.records, submitted, completed), (records, None, None),
                                       (records, submitted, submitted),
                                       (records, submitted, {'ChangeInfo': {'Id': '/change/COTHER', 'Status': 'INSYNC'}})):
            with self.assertRaises((ValueError, ProviderError)):
                dns.verify(receipt, self.zone, after, response, change)
        modified = dict(receipt, batch_sha256='b' * 64)
        with self.assertRaises(ProviderError):
            dns.verify(modified, self.zone, records, submitted, completed)

    def test_private_cli_artifacts_reconcile_without_network_and_refuse_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            inputs = {'zone': self.zone, 'records': self.records, 'desired': self.desired}
            for key, value in inputs.items():
                path = root / (key + '.json')
                path.write_text(json.dumps(value)); path.chmod(0o600)
            args = ['factory-dns', 'plan', '--zone', str(root / 'zone.json'), '--records', str(root / 'records.json'),
                    '--desired', str(root / 'desired.json'), '--source-commit', 'a' * 40, '--run-id', 'dns-run',
                    '--batch', str(root / 'batch.json'), '--receipt', str(root / 'plan.json')]
            env = dict(self.config, FACTORY_PRIVATE_ROOT=str(root), FACTORY_PROJECT_ID=self.project, FACTORY_ENVIRONMENT=self.environment)
            with patch.dict(os.environ, env, clear=True), patch.object(dns, 'load'), patch.object(sys, 'argv', args), patch('builtins.print'):
                dns.main()
                self.assertEqual((root / 'batch.json').stat().st_mode & 0o777, 0o600)
                self.assertEqual((root / 'plan.json').stat().st_mode & 0o777, 0o600)
                before = (root / 'plan.json').read_bytes()
                with self.assertRaises(ProviderError):
                    dns.main()
                self.assertEqual((root / 'plan.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
