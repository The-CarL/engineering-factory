"""Real-shell credential selection; optional native gh contract stays entirely offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import runtime

GH = shutil.which('gh')
PROBE = '''import json, os
for key, expected in json.loads(os.environ['EXPECTED_ENV']).items():
    assert os.environ.get(key) == expected, key
'''
TOKEN_PROBE = '''import os, sys
assert sys.stdin.read().rstrip('\\n') == os.environ['EXPECTED_GH_TOKEN']
'''


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='factory activation ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.activation = self.root / 'runtime.env'
        self.tokens = [uuid.uuid4().hex for _ in range(5)]
        self.cached = self.root / 'gh-config'
        self.cached.mkdir(mode=0o700)
        self.hosts = self.cached / 'hosts.yml'
        self.cache_text = ('github.com:\n    user: fixture-user\n    oauth_token: ' + self.tokens[4] + '\n'
                           '    users:\n        fixture-user:\n            oauth_token: ' + self.tokens[4] + '\n')
        self.hosts.write_text(self.cache_text)
        (self.cached / 'config.yml').write_text('version: \"1\"\n')
        self.hosts.chmod(0o600)
        self.env = dict(HOME=str(self.root), PATH='/usr/bin:/bin', GH_CONFIG_DIR=str(self.cached),
                        FACTORY_PRIVATE_ROOT=str(self.root), FACTORY_SOURCE_REPOSITORY='fixture-owner/factory',
                        FACTORY_SOURCE_REVISION='a' * 40, FACTORY_RUNTIME_DIRECTORY=str(self.root / 'release'),
                        GH_TOKEN=self.tokens[1], GITHUB_TOKEN=self.tokens[2], GH_ENTERPRISE_TOKEN=self.tokens[3],
                        GITHUB_ENTERPRISE_TOKEN=self.tokens[3], GH_HOST='other.invalid')
        tools = {name: str(self.root / name / 'bin' / name) for name in ('aws', 'node', 'python', 'git')}
        with patch.dict(os.environ, dict(self.env, FACTORY_GITHUB_TOKEN=self.tokens[0]), clear=True):
            runtime.write_environment(self.activation, tools)
        self.tools = tools

    def source(self, script, expected, env=None):
        child = dict(self.env if env is None else env, EXPECTED_ENV=json.dumps(expected))
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-uc', script,
                                 'activation-test', str(self.activation), sys.executable, PROBE, GH or '', TOKEN_PROBE],
                                env=child, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        for token in self.tokens:
            self.assertNotIn(token, self.activation.read_text())
            self.assertNotIn(token, result.stderr)
        self.assertEqual(self.activation.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.hosts.read_text(), self.cache_text)
        return result

    def test_factory_binding_is_resolved_at_source_time_and_exported_to_children_without_trace(self):
        # The token present during generation differs from the later task binding.
        env = dict(self.env, FACTORY_GITHUB_TOKEN=self.tokens[3])
        result = self.source('set -x\n. "$1" && "$2" -c "$3"',
                             dict(GH_TOKEN=self.tokens[3], GITHUB_TOKEN=self.tokens[3], GH_HOST='github.com',
                                  GH_PROMPT_DISABLED='1', GH_ENTERPRISE_TOKEN=None, GITHUB_ENTERPRISE_TOKEN=None), env)
        self.assertNotIn('ERROR:', result.stderr)

    def test_missing_or_blank_binding_blocks_ambient_auth_even_when_source_failure_is_ignored(self):
        for binding in (None, '', ' \t\n'):
            with self.subTest(binding=binding):
                env = dict(self.env)
                if binding is not None:
                    env['FACTORY_GITHUB_TOKEN'] = binding
                result = self.source('if . "$1"; then exit 9; fi\n"$2" -c "$3"',
                                     dict(GH_TOKEN='factory-token-binding-missing', GITHUB_TOKEN='factory-token-binding-missing'), env)
                self.assertEqual(result.stderr, 'ERROR: FACTORY_GITHUB_TOKEN binding is required for factory-token mode.\n')

    def test_dns_zone_config_is_validated_and_retained_in_activation(self):
        zone = dict(FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE', FACTORY_AWS_DNS_ZONE_NAME='example.test')
        with patch.dict(os.environ, dict(self.env, **zone, FACTORY_GITHUB_TOKEN=self.tokens[0]), clear=True):
            runtime.write_environment(self.activation, self.tools)
        env = dict(self.env, FACTORY_GITHUB_TOKEN=self.tokens[0])
        self.source('. "$1" && "$2" -c "$3"', zone, env)
        with patch.dict(os.environ, dict(self.env, FACTORY_AWS_DNS_ZONE_ID='ZEXAMPLE'), clear=True), self.assertRaises(ValueError):
            runtime.write_environment(self.activation, self.tools)

    def test_explicit_cli_activation_preserves_ambient_sources_and_config(self):
        env = dict(self.env, FACTORY_GITHUB_CREDENTIAL_SOURCE='cli', FACTORY_GITHUB_TOKEN=self.tokens[0])
        with patch.dict(os.environ, env, clear=True):
            runtime.write_environment(self.activation, self.tools)
        result = self.source('. "$1" && "$2" -c "$3"',
                             {key: env[key] for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN',
                                                       'GITHUB_ENTERPRISE_TOKEN', 'GH_HOST', 'GH_CONFIG_DIR')}, env)
        self.assertEqual(result.stderr, '')

    @unittest.skipUnless(GH, 'Native gh unavailable; real-shell environment contracts still run')
    def test_native_gh_token_precedence_and_cached_fallback_without_network_or_token_output(self):
        for mode, binding, ambient, expected in (('factory-token', self.tokens[3], True, self.tokens[3]),
                                               ('factory-token', None, True, 'factory-token-binding-missing'),
                                               ('factory-token', None, False, 'factory-token-binding-missing'),
                                               ('cli', None, True, self.tokens[1]),
                                               ('cli', None, False, self.tokens[4])):
            with self.subTest(mode=mode, binding=bool(binding), ambient=ambient):
                env = dict(self.env, FACTORY_GITHUB_CREDENTIAL_SOURCE=mode, EXPECTED_GH_TOKEN=expected)
                if binding:
                    env['FACTORY_GITHUB_TOKEN'] = binding
                if not ambient:
                    del env['GH_TOKEN'], env['GITHUB_TOKEN']
                with patch.dict(os.environ, env, clear=True):
                    runtime.write_environment(self.activation, self.tools)
                script = 'set -o pipefail\n. "$1" || :\n"$4" auth token --hostname github.com | "$2" -c "$5"'
                self.source(script, {}, env)


if __name__ == '__main__':
    unittest.main()
