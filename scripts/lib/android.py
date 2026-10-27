"""Portable Android artifact contracts; no model client or factory credentials required."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

NETWORK = ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY', 'https_proxy',
           'http_proxy', 'all_proxy', 'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
           'REQUESTS_CA_BUNDLE')
CONFIG_KEYS = {'schema', 'repository', 'project_id', 'project_name', 'environment',
               'application_id', 'version_code', 'version_name', 'minimum_sdk',
               'target_sdk', 'compile_sdk', 'certificate_sha256', 'java_version',
               'build_tools_version'}


class AndroidError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AndroidError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical(value, *, directory=False):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), 'Use canonical absolute paths without symlinks')
    require(path.is_dir() if directory else path.is_file(), 'Required Android input is missing')
    return path


def environment(home, java_home=None):
    env = {key: os.environ[key] for key in NETWORK if key in os.environ}
    env.update(PATH='/usr/bin:/bin', HOME=str(home), TMPDIR=str(home), LANG='C.UTF-8',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    if java_home:
        env['JAVA_HOME'] = str(java_home)
        env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env['PATH']
    return env


def run(command, env, *, timeout=120, input=None):
    try:
        result = subprocess.run([str(x) for x in command], env=env, input=input,
                                capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise AndroidError('Android command did not complete; inspect local tooling before retrying') from None
    require(result.returncode == 0, 'Android command failed; raw output withheld')
    require(len(result.stdout) + len(result.stderr) <= 2 * 1024 * 1024, 'Unexpectedly large tool response')
    return result


def read_json(path):
    require(Path(path).stat().st_size <= 1024 * 1024, 'Android JSON input is too large')
    return json.loads(Path(path).read_text())


def config(value):
    require(isinstance(value, dict) and set(value) == CONFIG_KEYS and value['schema'] == 1,
            'Use the complete Android configuration schema 1')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', value['repository'])
            and not value['repository'].endswith('.git'), 'Use exact GitHub OWNER/REPO')
    require(re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', value['application_id']),
            'Use an Android application ID')
    require(re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value['project_id'])
            and uuid.UUID(value['project_id']).int != 0, 'Use the existing nonzero project UUID')
    for key in ('project_name', 'version_name'):
        require(isinstance(value[key], str) and 0 < len(value[key]) <= 128
                and value[key] == value[key].strip() and not re.search(r'[\x00-\x1f\x7f@]|https?://', value[key]),
                'Use bounded readable Android labels without emails, URLs or controls')
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value['environment']), 'Use an environment label')
    require(type(value['version_code']) is int and 0 < value['version_code'] <= 2100000000,
            'Use a positive Android version code')
    require(all(type(value[key]) is int for key in ('minimum_sdk', 'target_sdk', 'compile_sdk'))
            and 1 <= value['minimum_sdk'] <= value['target_sdk'] <= value['compile_sdk'] <= 999,
            'Use coherent numeric Android SDK versions')
    require(re.fullmatch(r'[a-f0-9]{64}', value['certificate_sha256']),
            'Enroll an exact lowercase SHA-256 signing certificate fingerprint')
    require(re.fullmatch(r'[0-9][0-9.+_-]{1,63}', value['java_version'])
            and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value['build_tools_version']),
            'Pin the actual Java version and stable Android Build Tools version')
    return value


def git_facts(source, expected_repository, env):
    source = canonical(source, directory=True)
    def git(*args):
        return run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                    '-C', source, *args], env, timeout=30).stdout.decode().rstrip('\n')
    require(git('rev-parse', '--show-toplevel') == str(source), 'Source must be the exact app Git root')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Commit or preserve app changes before packaging')
    for option in ((), ('--push',)):
        origin = git('remote', 'get-url', *option, '--all', 'origin').lower()
        repo = expected_repository.lower()
        require(origin in ('https://github.com/' + repo, 'https://github.com/' + repo + '.git',
                           'git@github.com:' + repo + '.git'), 'App origin differs from the Android repository')
    commit = git('rev-parse', 'HEAD')
    require(re.fullmatch(r'[a-f0-9]{40}', commit), 'Use a full committed source SHA')
    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    branch = 'detached' if branch == 'HEAD' else branch
    author = git('show', '-s', '--format=%an', 'HEAD')
    require(all(0 < len(label) <= 256 and not re.search(r'[\x00-\x1f\x7f@]|https?://', label)
                for label in (branch, author)), 'Review source branch/author labels before release')
    return dict(repository=expected_repository.lower(), commit=commit, branch=branch, author=author)


def toolchain(settings, sdk, java_home, env):
    sdk, java_home = canonical(sdk, directory=True), canonical(java_home, directory=True)
    version = run([java_home / 'bin/java', '-version'], env).stderr.decode()
    require(re.search(r'version "' + re.escape(settings['java_version']) + r'"', version),
            'Installed Java differs from the app pin')
    build = canonical(sdk / 'build-tools' / settings['build_tools_version'], directory=True)
    require(re.search(r'^Pkg.Revision\s*=\s*' + re.escape(settings['build_tools_version']) + r'\s*$',
                      (build / 'source.properties').read_text(), re.MULTILINE), 'Build Tools differ from the app pin')
    platform = canonical(sdk / 'platforms' / ('android-' + str(settings['compile_sdk'])), directory=True)
    require(re.search(r'^AndroidVersion.ApiLevel\s*=\s*' + str(settings['compile_sdk']) + r'\s*$',
                      (platform / 'source.properties').read_text(), re.MULTILINE), 'Compile SDK differs from the app pin')
    require((platform / 'android.jar').is_file(), 'Compile SDK is incomplete')
    paths = {name: canonical(build / name) for name in ('apksigner', 'aapt2', 'zipalign')}
    paths['java'] = canonical(java_home / 'bin/java')
    require(all(os.access(path, os.X_OK) for path in paths.values()), 'Android tools must be executable')
    return paths, dict(java_version=settings['java_version'], compile_sdk=settings['compile_sdk'],
                       build_tools_version=settings['build_tools_version'],
                       executable_sha256={key: sha256(path) for key, path in paths.items()})


def inspect_apk(apk, settings, tools, env):
    run([tools['zipalign'], '-c', '-P', '16', '4', apk], env)
    result = run([tools['apksigner'], 'verify', '--verbose', '--print-certs', apk], env)
    signers = re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([a-fA-F0-9]{64})\s*$',
                         result.stdout.decode(), re.MULTILINE)
    require([signer.lower() for signer in signers] == [settings['certificate_sha256']],
            'APK signer differs from the enrolled certificate, or multiple signers are present')
    badging = run([tools['aapt2'], 'dump', 'badging', apk], env).stdout.decode()
    package = re.search(r'^package: (.+)$', badging, re.MULTILINE)
    require(package is not None, 'APK package identity is unavailable')
    attrs = dict(re.findall(r"([A-Za-z0-9_]+)='([^']*)'", package[1]))
    require(attrs.get('name') == settings['application_id']
            and attrs.get('versionCode') == str(settings['version_code'])
            and attrs.get('versionName') == settings['version_name'], 'APK identity or version differs from the app contract')
    require(not attrs.get('split') and attrs.get('versionCodeMajor', '0') == '0',
            'Publish a standalone APK with a supported version code')
    for label, key in (('sdkVersion', 'minimum_sdk'), ('targetSdkVersion', 'target_sdk')):
        require(re.search(r"^" + label + r":'" + str(settings[key]) + r"'\s*$", badging, re.MULTILINE),
                'APK SDK requirements differ from the app contract')
    tree = run([tools['aapt2'], 'dump', 'xmltree', apk, '--file', 'AndroidManifest.xml'], env).stdout.decode()
    require(re.search(r'^\s*E: manifest(?:\s|$)', tree, re.MULTILINE)
            and re.search(r'^\s*E: application(?:\s|$)', tree, re.MULTILINE), 'APK manifest tree cannot be verified')
    for flag in ('debuggable', 'testOnly'):
        lines = [line for line in tree.splitlines() if re.search(r'android:' + flag + r'\(', line)]
        require(all(re.search(r'=\(type 0x12\)0x0\s*$', line.strip()) for line in lines),
                'Release APK is debuggable/test-only, or its flag cannot be verified')


def verify_upgrade(current, previous):
    for key in ('project_id', 'environment', 'application_id', 'certificate_sha256'):
        require(current[key] == previous[key], 'Update changes the app/environment/signing identity')
    require(current['version_code'] > previous['version_code'], 'Updates must increase Android version_code')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def bundle(value):
    directory = canonical(value, directory=True)
    require({p.name for p in directory.iterdir()} == {'app.apk', 'release.json', 'SHA256SUMS'},
            'Android bundle must contain only the APK, release manifest and checksums')
    paths = {name: canonical(directory / name) for name in ('app.apk', 'release.json', 'SHA256SUMS')}
    require(0 < paths['app.apk'].stat().st_size < 2 * 1024 ** 3 and paths['SHA256SUMS'].stat().st_size < 4096,
            'Android bundle exceeds supported size')
    manifest = read_json(paths['release.json'])
    require(manifest.get('schema') == 1 and manifest.get('platform') == 'android'
            and isinstance(manifest.get('source'), dict), 'Invalid Android release manifest')
    config(manifest['app'])
    require(manifest['source']['repository'] == manifest['app']['repository'].lower()
            and re.fullmatch(r'[a-f0-9]{40}', manifest['source']['commit']), 'Manifest source differs from its app')
    require(manifest['apk'] == dict(name='app.apk', sha256=sha256(paths['app.apk']),
                                    size=paths['app.apk'].stat().st_size), 'APK bytes differ from the verified manifest')
    expected = ''.join(sha256(paths[name]) + '  ' + name + '\n' for name in ('app.apk', 'release.json'))
    require(paths['SHA256SUMS'].read_text() == expected, 'Android bundle checksums differ')
    return directory, paths, manifest
