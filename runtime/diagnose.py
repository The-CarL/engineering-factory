#!/usr/bin/env python3
"""Credential-free bounded diagnosis; offline unless --network is explicitly selected."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from provider import NoRedirect, ProviderError, transport_reason
from runtime import Parser, base_env

CHILD_MARKER = 'factory-diagnose child-started'
SELECTORS = ('FACTORY_SOURCE_REPOSITORY', 'FACTORY_SOURCE_REVISION', 'FACTORY_RUNTIME_MANIFEST', 'FACTORY_PRIVATE_ROOT')
OUTCOMES = {'os_permission_denied', 'timeout', 'dns_failure', 'tls_failure', 'proxy_tunnel_failure',
            'connection_failure', 'transport_or_response_failure', 'http_response', 'child_failed', 'invalid_child_result'}


def configuration():
    result = {key: 'set' if os.environ.get(key) else 'missing' for key in SELECTORS}
    selected = os.environ.get('FACTORY_GITHUB_CREDENTIAL_SOURCE', 'cli')
    result['github_credential_source'] = selected if selected in ('cli', 'factory-token') else 'invalid'
    result['github_source_explicit'] = 'FACTORY_GITHUB_CREDENTIAL_SOURCE' in os.environ
    result['github_factory_binding'] = 'present' if os.environ.get('FACTORY_GITHUB_TOKEN', '').strip() else 'missing'
    return result


def offline_probe():
    from runtime import check_source, load
    result = {'source': 'blocked', 'runtime': 'blocked'}
    if all(os.environ.get(key) for key in SELECTORS[:2]):
        try:
            check_source()
            result['source'] = 'verified'
        except (ProviderError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
            result['source'] = 'failed'
    if result['source'] == 'verified' and os.environ.get('FACTORY_RUNTIME_MANIFEST'):
        try:
            load()
            result['runtime'] = 'verified'
        except (ProviderError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
            result['runtime'] = 'failed'
    return result


def network_probe():
    # Fixed unauthenticated recipient; no redirects, body, cookies or provider token.
    request = urllib.request.Request('https://api.github.com', headers={'User-Agent': 'engineering-factory-diagnose'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=4) as response:
            return {'outcome': 'http_response', 'http_status': response.status}
    except urllib.error.HTTPError as error:
        return {'outcome': 'http_response', 'http_status': error.code}
    except (OSError, ValueError, urllib.error.URLError) as error:
        return {'outcome': transport_reason(error)}


def valid_result(probe, result):
    if not isinstance(result, dict):
        return False
    if probe == 'offline':
        return set(result) == {'source', 'runtime'} and all(value in ('blocked', 'verified', 'failed') for value in result.values())
    return (set(result) == {'outcome'} and result['outcome'] in OUTCOMES - {'http_response'}
            or set(result) == {'outcome', 'http_status'} and result['outcome'] == 'http_response'
            and type(result['http_status']) is int and 100 <= result['http_status'] <= 599)


def bounded_probe(probe, seconds):
    env = base_env('/tmp')
    if probe == 'offline':
        env.update({key: os.environ[key] for key in SELECTORS if key in os.environ})
    command = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', probe]
    try:
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        return {'outcome': transport_reason(error), 'child_started': False}
    try:
        output, _ = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        return {'outcome': 'timeout', 'child_started': CHILD_MARKER.encode() in (error.output or b'')}
    lines = output.splitlines()
    started = bool(lines and lines[0] == CHILD_MARKER.encode())
    if process.returncode or not started:
        return {'outcome': 'child_failed', 'child_started': started}
    try:
        result = json.loads(lines[1]) if len(lines) == 2 else None
        if valid_result(probe, result):
            return dict(result, child_started=True)
    except (ValueError, TypeError):
        pass
    return {'outcome': 'invalid_child_result', 'child_started': started}


def main():
    print('factory-diagnose execution-start', flush=True)
    parser = Parser(description=__doc__)
    parser.add_argument('--network', action='store_true', help='Probe only unauthenticated GitHub API HTTPS; no auth/write test')
    args = parser.parse_args()
    print(json.dumps({'configuration': configuration()}, sort_keys=True), flush=True)
    print('factory-diagnose offline-probe-start', flush=True)
    print(json.dumps({'offline': bounded_probe('offline', 10)}, sort_keys=True), flush=True)
    if args.network:
        print('factory-diagnose network-probe-start', flush=True)
        print(json.dumps({'network': bounded_probe('network', 6)}, sort_keys=True), flush=True)
    print('Diagnosis only: provider authentication, write grants and deployment readiness are unverified.', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] in (['--worker', 'offline'], ['--worker', 'network']):
        print(CHILD_MARKER, flush=True)
        print(json.dumps(offline_probe() if sys.argv[-1] == 'offline' else network_probe(), sort_keys=True), flush=True)
    else:
        try:
            main()
        except (ProviderError, OSError, ValueError, TypeError):
            print('Diagnosis command failed; private details withheld.', flush=True)
            sys.exit(1)
