"""Bounded execution/network faults and secret-safe configuration diagnosis."""
from contextlib import redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import urllib.error
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import provider
import runtime

spec = importlib.util.spec_from_file_location('runtime_diagnose', ROOT / 'runtime/diagnose.py')
diagnose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnose)


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.secret = uuid.uuid4().hex
        self.environ = patch.dict(os.environ, dict(GH_TOKEN=self.secret, FACTORY_GITHUB_TOKEN=self.secret,
                                  VERCEL_TOKEN=self.secret, AWS_ACCESS_KEY_ID=self.secret,
                                  AWS_SECRET_ACCESS_KEY=self.secret, AWS_SESSION_TOKEN=self.secret), clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def test_missing_setup_runs_offline_without_network_and_never_claims_permissions(self):
        with patch.object(diagnose, 'network_probe') as network, patch.object(diagnose, 'offline_probe', wraps=diagnose.offline_probe):
            result = diagnose.offline_probe()
        network.assert_not_called()
        self.assertEqual(result, dict(source='blocked', runtime='blocked'))
        settings = diagnose.configuration()
        self.assertEqual(settings['FACTORY_RUNTIME_MANIFEST'], 'missing')
        self.assertEqual(settings['FACTORY_SOURCE_REVISION'], 'missing')
        self.assertEqual(settings['github_credential_source'], 'cli')
        self.assertFalse(settings['github_source_explicit'])
        self.assertNotIn(self.secret, json.dumps(settings))
        process = subprocess.run([sys.executable, str(ROOT / 'runtime/diagnose.py')], env=runtime.base_env('/tmp'),
                                 capture_output=True, timeout=12)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout.splitlines()[0], b'factory-diagnose execution-start')
        self.assertIn(b'"runtime": "blocked"', process.stdout)
        self.assertNotIn(b'network-probe-start', process.stdout)

    def test_selector_is_only_declared_config_and_invalid_values_are_withheld(self):
        os.environ.update(FACTORY_GITHUB_CREDENTIAL_SOURCE='factory-token')
        self.assertEqual(diagnose.configuration()['github_factory_binding'], 'present')
        del os.environ['FACTORY_GITHUB_TOKEN']
        self.assertEqual(diagnose.configuration()['github_factory_binding'], 'missing')
        os.environ['FACTORY_GITHUB_CREDENTIAL_SOURCE'] = self.secret
        result = diagnose.configuration()
        self.assertEqual(result['github_credential_source'], 'invalid')
        self.assertNotIn(self.secret, json.dumps(result))

    def test_missing_stale_and_invalid_runtime_are_distinct_from_verified_source(self):
        os.environ.update(FACTORY_SOURCE_REPOSITORY='fixture/factory', FACTORY_SOURCE_REVISION='a'*40)
        with patch.object(runtime, 'check_source', return_value=None), patch.object(runtime, 'load') as load:
            self.assertEqual(diagnose.offline_probe(), dict(source='verified', runtime='blocked'))
            load.assert_not_called()
            os.environ['FACTORY_RUNTIME_MANIFEST'] = '/missing/private/manifest.json'
            load.side_effect = FileNotFoundError(self.secret)
            self.assertEqual(diagnose.offline_probe(), dict(source='verified', runtime='failed'))
        with patch.object(runtime, 'check_source', side_effect=provider.ProviderError(self.secret)):
            self.assertEqual(diagnose.offline_probe(), dict(source='failed', runtime='blocked'))

    def test_network_fixed_recipient_no_auth_redirect_body_or_retry(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.status = 200
        opener = unittest.mock.Mock()
        opener.open.return_value = response
        with patch.object(diagnose.urllib.request, 'build_opener', return_value=opener) as build:
            result = diagnose.network_probe()
        self.assertEqual(result, dict(outcome='http_response', http_status=200))
        self.assertIsInstance(build.call_args.args[0], provider.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.github.com')
        self.assertNotIn('Authorization', request.headers)
        self.assertIsNone(request.data)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 4)
        self.assertEqual(opener.open.call_count, 1)
        response.read.assert_not_called()

    def test_network_denial_dns_tls_proxy_and_timeout_never_echo_secret_errors(self):
        cases = [(PermissionError(errno.EPERM, self.secret), 'os_permission_denied'),
                 (PermissionError(errno.EACCES, self.secret), 'os_permission_denied'),
                 (socket.gaierror(socket.EAI_NONAME, self.secret), 'dns_failure'),
                 (ssl.SSLCertVerificationError(self.secret), 'tls_failure'),
                 (TimeoutError(self.secret), 'timeout'),
                 (OSError('Tunnel connection failed: 403 ' + self.secret), 'proxy_tunnel_failure'),
                 (ConnectionRefusedError(errno.ECONNREFUSED, self.secret), 'connection_failure')]
        for error, expected in cases:
            with self.subTest(expected=expected), patch.object(diagnose.urllib.request.OpenerDirector, 'open',
                    side_effect=urllib.error.URLError(error)) as request:
                result = diagnose.network_probe()
            self.assertEqual(result, dict(outcome=expected))
            self.assertNotIn(self.secret, json.dumps(result))
            self.assertEqual(request.call_count, 1)
        error = urllib.error.HTTPError('https://api.github.com', 403, 'permission denied '+self.secret, {}, io.BytesIO(self.secret.encode()))
        with patch.object(diagnose.urllib.request.OpenerDirector, 'open', side_effect=error):
            self.assertEqual(diagnose.network_probe(), dict(outcome='http_response', http_status=403))

    def test_probe_child_keeps_approved_proxy_ca_but_excludes_provider_and_debug_sources(self):
        os.environ.update(HTTPS_PROXY='http://approved-proxy.invalid', SSL_CERT_FILE='/approved/ca.pem',
                          GH_DEBUG=self.secret, GIT_TRACE=self.secret, AWS_PROFILE=self.secret,
                          FACTORY_GITHUB_CREDENTIAL_SOURCE='factory-token', FACTORY_SOURCE_REVISION='a'*40)
        child = unittest.mock.Mock(returncode=0)
        child.communicate.return_value = ((diagnose.CHILD_MARKER+'\n'+json.dumps(dict(outcome='http_response', http_status=200))+'\n').encode(), None)
        with patch.object(diagnose.subprocess, 'Popen', return_value=child) as spawn:
            result = diagnose.bounded_probe('network', 6)
        env = spawn.call_args.kwargs['env']
        self.assertEqual(env['HTTPS_PROXY'], 'http://approved-proxy.invalid')
        self.assertEqual(env['SSL_CERT_FILE'], '/approved/ca.pem')
        self.assertNotIn(self.secret, env.values())
        self.assertNotIn('FACTORY_SOURCE_REVISION', env)
        self.assertEqual(result['http_status'], 200)
        with patch.object(diagnose.subprocess, 'Popen', side_effect=PermissionError(errno.EPERM, self.secret)):
            self.assertEqual(diagnose.bounded_probe('network', 6), dict(outcome='os_permission_denied', child_started=False))

    def test_real_stalled_child_is_killed_with_bounded_execution_and_start_evidence(self):
        original = subprocess.Popen
        children = []
        def stalled(command, **kwargs):
            child = original([sys.executable, '-c', 'import time; print('+repr(diagnose.CHILD_MARKER)+', flush=True); time.sleep(30)'], **kwargs)
            children.append(child)
            return child
        started = time.monotonic()
        with patch.object(diagnose.subprocess, 'Popen', side_effect=stalled):
            result = diagnose.bounded_probe('network', .5)
        self.assertLess(time.monotonic()-started, 3)
        self.assertEqual(result, dict(outcome='timeout', child_started=True))
        self.assertIsNotNone(children[0].poll())

    def test_execution_marker_is_flushed_before_probe_dispatch_and_child_garbage_is_withheld(self):
        class Stream(io.StringIO):
            flushes = 0
            def flush(self):
                self.flushes += 1
        stream = Stream()
        def probe(*args):
            self.assertTrue(stream.getvalue().startswith('factory-diagnose execution-start\n'))
            self.assertGreater(stream.flushes, 0)
            return dict(source='blocked', runtime='blocked')
        with patch.object(sys, 'argv', ['diagnose.py']), patch.object(diagnose, 'bounded_probe', side_effect=probe), redirect_stdout(stream):
            diagnose.main()
        child = unittest.mock.Mock(returncode=0)
        child.communicate.return_value = ((diagnose.CHILD_MARKER+'\n'+self.secret+'\n').encode(), None)
        with patch.object(diagnose.subprocess, 'Popen', return_value=child):
            result = diagnose.bounded_probe('network', 6)
        self.assertEqual(result['outcome'], 'invalid_child_result')
        self.assertNotIn(self.secret, json.dumps(result))

    def test_provider_os_denial_is_not_inferred_from_http_forbidden_body(self):
        denied = provider.diagnostic('GitHub', stderr=('dial tcp: operation not permitted '+self.secret).encode())
        self.assertIn('status unknown', denied)
        self.assertIn('OS denied', denied)
        forbidden = provider.diagnostic('GitHub', status=403, body=json.dumps(dict(message='operation not permitted '+self.secret)).encode())
        self.assertIn('HTTP 403', forbidden)
        self.assertNotIn('OS denied', forbidden)
        self.assertNotIn(self.secret, denied+forbidden)
        with patch.object(provider.subprocess, 'run', side_effect=PermissionError(errno.EPERM, self.secret)):
            with self.assertRaises(provider.ProviderError) as error:
                provider.gh(['user'])
        self.assertIn('os_permission_denied', str(error.exception))
        self.assertIn('outcome may be unknown', str(error.exception))
        self.assertNotIn(self.secret, str(error.exception))


if __name__ == '__main__':
    unittest.main()
