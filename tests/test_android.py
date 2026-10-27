"""Android release boundaries: package identity, signing continuity and partial-write recovery."""
import argparse
import base64
from contextlib import redirect_stdout
import importlib.util
import io
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
import android


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


artifact = module('android_artifact', 'android-artifact.py')
release = module('android_release', 'android-release.py')
signer = module('android_signer', 'android-sign.py')


def settings():
    return dict(schema=1, repository='fixture-owner/android-notes', project_id=str(uuid.uuid4()),
                project_name='Android Notes', environment='development', application_id='com.example.notes',
                version_code=2, version_name='0.2.0', minimum_sdk=24, target_sdk=35, compile_sdk=35,
                certificate_sha256='a' * 64, java_version='17.0.12', build_tools_version='35.0.0')


class FakeGitHub:
    def __init__(self, manifest, paths):
        self.manifest, self.paths = manifest, paths
        self.reference = None
        self.release = None
        self.assets = {}
        self.writes = []
        self.fail_upload = False
        self.corrupt_download = False
        self.wrong_visibility = False

    def api(self, endpoint, data=None, missing=False):
        commit = self.manifest['source']['commit']
        if data is not None:
            self.writes.append(('POST', endpoint))
        if endpoint == '':
            return dict(full_name=self.manifest['app']['repository'], private=not self.wrong_visibility)
        if endpoint.startswith('git/commits/'):
            return dict(sha=commit)
        if endpoint.startswith('git/ref/tags/'):
            return self.reference
        if endpoint == 'git/refs':
            self.reference = dict(object=dict(type='commit', sha=data['sha']))
            return self.reference
        if endpoint == 'releases':
            self.release = dict(data, id=42, assets=[])
            return self.release
        if endpoint.startswith('releases/tags/'):
            if self.release is not None:
                self.release['assets'] = [dict(name=name) for name in self.assets]
            return self.release
        raise AssertionError(endpoint)

    def find_release(self, tag):
        if self.release is not None:
            self.release['assets'] = [dict(name=name) for name in self.assets]
        return self.release

    def command(self, *args, **kwargs):
        args = list(map(str, args))
        if args[:2] == ['release', 'upload']:
            if self.fail_upload:
                raise android.AndroidError('Injected uncertain upload')
            path = Path(args[3])
            self.writes.append(('upload', path.name))
            self.assets[path.name] = path.read_bytes()
        elif args[:2] == ['release', 'download']:
            directory = Path(args[args.index('--dir') + 1])
            for name, data in self.assets.items():
                (directory / name).write_bytes(b'wrong' if self.corrupt_download else data)
        elif args[:2] == ['release', 'edit']:
            self.writes.append(('publish',))
            self.release['draft'] = False
        else:
            raise AssertionError(args)
        return b''


class AndroidTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='factory android ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'app'
        self.source.mkdir()
        self.env = dict(PATH=os.environ.get('PATH', os.defpath), GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Carlo Example')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/fixture-owner/android-notes.git')
        (self.source / 'app.txt').write_text('real committed source')
        self.git('add', 'app.txt')
        self.git('commit', '--quiet', '-m', 'initial')
        self.settings = settings()
        self.facts = android.git_facts(self.source, self.settings['repository'], self.env)
        self.tools = {name: Path('/fixture') / name for name in ('apksigner', 'aapt2', 'zipalign')}

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.source), *args], env=self.env,
                              check=True, capture_output=True).stdout.decode().strip()

    def tool_output(self, command, env):
        command = list(map(str, command))
        if command[0].endswith('apksigner'):
            output = 'Signer #1 certificate SHA-256 digest: ' + self.settings['certificate_sha256'] + '\n'
        elif 'badging' in command:
            output = "package: name='com.example.notes' versionCode='2' versionName='0.2.0'\nsdkVersion:'24'\ntargetSdkVersion:'35'\n"
        elif 'xmltree' in command:
            output = 'E: manifest\n  E: application\n'
        else:
            output = ''
        return subprocess.CompletedProcess(command, 0, stdout=output.encode(), stderr=b'')

    def make_bundle(self):
        directory = self.root / 'bundle'
        directory.mkdir()
        (directory / 'app.apk').write_bytes(b'fixture bytes: never a live signed APK')
        manifest = dict(schema=1, platform='android', app=self.settings, source=self.facts,
                        apk=dict(name='app.apk', sha256=android.sha256(directory / 'app.apk'),
                                 size=(directory / 'app.apk').stat().st_size))
        (directory / 'release.json').write_text(json.dumps(manifest))
        (directory / 'SHA256SUMS').write_text(''.join(android.sha256(directory / name) + '  ' + name + '\n'
                                                   for name in ('app.apk', 'release.json')))
        return android.bundle(directory)

    def arguments(self, bundle, number=1):
        return argparse.Namespace(bundle=bundle, repo=self.settings['repository'], visibility='private',
                                  tag='android-v0.2.0', gh=Path('/not-used/gh'),
                                  record=self.root / ('operation-' + str(number) + '.jsonl'), source_commit=self.facts['commit'])

    def test_closed_configuration_and_update_continuity(self):
        android.config(self.settings)
        for change in (dict(version_code=True), dict(minimum_sdk=99), dict(certificate_sha256='unknown'),
                       dict(application_id='../app'), dict(unexpected='field'), dict(java_version='latest')):
            with self.subTest(change=change), self.assertRaises((android.AndroidError, TypeError)):
                android.config(dict(self.settings, **change))
        previous = dict(self.settings, version_code=1)
        android.verify_upgrade(self.settings, previous)
        for change in (dict(version_code=2), dict(application_id='com.example.other'),
                       dict(certificate_sha256='b' * 64), dict(project_id=str(uuid.uuid4())),
                       dict(environment='production')):
            with self.subTest(change=change), self.assertRaises(android.AndroidError):
                android.verify_upgrade(self.settings, dict(previous, **change))

    def test_actual_git_origin_dirty_source_and_author_are_verified(self):
        self.assertEqual(self.facts['commit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.facts['author'], 'Carlo Example')
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/notes.git')
        with self.assertRaises(android.AndroidError):
            android.git_facts(self.source, self.settings['repository'], self.env)
        self.git('remote', 'set-url', 'origin', 'https://github.com/fixture-owner/android-notes.git')
        (self.source / 'app.txt').write_text('keep my edits')
        with self.assertRaises(android.AndroidError):
            android.git_facts(self.source, self.settings['repository'], self.env)
        self.assertEqual((self.source / 'app.txt').read_text(), 'keep my edits')

    def test_android_tools_never_inherit_provider_or_signing_credentials(self):
        with patch.dict(os.environ, GH_TOKEN='fixture-secret', AWS_SECRET_ACCESS_KEY='fixture-secret',
                        ANDROID_KEYSTORE_PASSWORD='fixture-secret', JAVA_TOOL_OPTIONS='-agentlib:untrusted'):
            env = android.environment(self.root, self.root / 'jdk')
        self.assertFalse(any(key in env for key in ('GH_TOKEN', 'AWS_SECRET_ACCESS_KEY',
                                                   'ANDROID_KEYSTORE_PASSWORD', 'JAVA_TOOL_OPTIONS')))

    def test_package_signer_versions_and_flags_are_verified(self):
        with patch.object(android, 'run', side_effect=self.tool_output):
            android.inspect_apk(self.root / 'app.apk', self.settings, self.tools, self.env)
        def explicit_false(command, env):
            result = self.tool_output(command, env)
            if 'xmltree' in command:
                result.stdout += b'    A: android:debuggable(0x0101000f)=(type 0x12)0x0\n'
            return result
        with patch.object(android, 'run', side_effect=explicit_false):
            android.inspect_apk(self.root / 'app.apk', self.settings, self.tools, self.env)
        cases = [('apksigner', 'Signer #1 certificate SHA-256 digest: ' + 'b' * 64 + '\n'),
                 ('apksigner', 'Signer #1 certificate SHA-256 digest: ' + 'a' * 64
                  + '\nSigner #2 certificate SHA-256 digest: ' + 'a' * 64 + '\n'),
                 ('badging', "package: name='com.other.app' versionCode='2' versionName='0.2.0'\n"),
                 ('badging', "package: name='com.example.notes' versionCode='2' versionName='0.2.0' split='config.en'\n"),
                 ('xmltree', 'A: android:debuggable(0x0101000f)=(type 0x12)0xffffffff\n'),
                 ('xmltree', 'A: android:testOnly(0x01010272)=(type 0x12)0xffffffff\n'),
                 ('xmltree', 'A: android:testOnly(0x01010272)=unknown\n')]
        for selector, replacement in cases:
            def output(command, env):
                normal = self.tool_output(command, env)
                if selector in str(command[0]) or selector in command:
                    normal.stdout = (('E: manifest\n  E: application\n' if selector == 'xmltree' else '') + replacement).encode()
                return normal
            with self.subTest(selector=selector), patch.object(android, 'run', side_effect=output), self.assertRaises(android.AndroidError):
                android.inspect_apk(self.root / 'app.apk', self.settings, self.tools, self.env)

    def test_prepare_retains_verified_bytes_without_overwriting_existing_output(self):
        config = self.source / 'config.json'
        config.write_text(json.dumps(self.settings))
        self.git('add', 'config.json')
        self.git('commit', '--quiet', '-m', 'reviewed Android release contract')
        self.facts = android.git_facts(self.source, self.settings['repository'], self.env)
        apk = self.root / 'signed.apk'
        apk.write_bytes(b'fixture')
        args = argparse.Namespace(source=self.source, config=config, apk=apk, sdk_root=self.root,
                                  java_home=self.root, output=self.root / 'prepared', previous_manifest=None)
        with patch.object(artifact, 'toolchain', return_value=(self.tools, {})), \
             patch.object(artifact, 'inspect_apk'), redirect_stdout(io.StringIO()):
            artifact.prepare(args)
        directory, paths, manifest = android.bundle(args.output)
        self.assertEqual(paths['app.apk'].read_bytes(), b'fixture')
        self.assertEqual(manifest['source']['commit'], self.facts['commit'])
        self.assertIn('assertion', manifest['assurance'])
        before = {name: path.read_bytes() for name, path in paths.items()}
        with self.assertRaises(android.AndroidError):
            artifact.prepare(args)
        self.assertEqual(before, {name: path.read_bytes() for name, path in paths.items()})

    def test_modified_bundle_and_extra_files_fail_before_github(self):
        directory, paths, _ = self.make_bundle()
        (directory / 'keystore.jks').write_bytes(b'not a real key')
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory))
        (directory / 'keystore.jks').unlink()
        paths['app.apk'].write_bytes(b'changed after signing')
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory))
        self.assertFalse(self.arguments(directory).record.exists())

    def test_successful_publish_checks_remote_bytes_and_repeated_run_does_not_write(self):
        directory, paths, manifest = self.make_bundle()
        gh = FakeGitHub(manifest, paths)
        with redirect_stdout(io.StringIO()):
            release.publish(self.arguments(directory), gh)
        self.assertFalse(gh.release['draft'])
        self.assertEqual(gh.assets, {name: path.read_bytes() for name, path in paths.items()})
        writes = list(gh.writes)
        with redirect_stdout(io.StringIO()):
            release.publish(self.arguments(directory, 2), gh)
        self.assertEqual(writes, gh.writes)
        events = [json.loads(line)['state'] for line in self.arguments(directory, 2).record.read_text().splitlines()]
        self.assertEqual(events[-1], 'complete')

    def test_partial_draft_is_reconciled_without_recreating_tag_release_or_clobbering(self):
        directory, paths, manifest = self.make_bundle()
        gh = FakeGitHub(manifest, paths)
        gh.fail_upload = True
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory), gh)
        self.assertTrue(gh.release['draft'])
        gh.fail_upload = False
        gh.assets['app.apk'] = paths['app.apk'].read_bytes()
        before = list(gh.writes)
        with redirect_stdout(io.StringIO()):
            release.publish(self.arguments(directory, 2), gh)
        self.assertFalse(gh.release['draft'])
        self.assertEqual(gh.writes[len(before):], [('upload', 'release.json'), ('upload', 'SHA256SUMS'), ('publish',)])

    def test_wrong_target_conflicting_tag_or_release_never_mutates(self):
        for failure in ('visibility', 'tag', 'release'):
            with self.subTest(failure=failure):
                directory, paths, manifest = self.make_bundle()
                gh = FakeGitHub(manifest, paths)
                if failure == 'visibility':
                    gh.wrong_visibility = True
                elif failure == 'tag':
                    gh.reference = dict(object=dict(type='commit', sha='b' * 40))
                else:
                    gh.reference = dict(object=dict(type='commit', sha=manifest['source']['commit']))
                    gh.release = dict(tag_name='android-v0.2.0', body='unrelated release', prerelease=True, id=8, assets=[])
                with self.assertRaises(android.AndroidError):
                    release.publish(self.arguments(directory), gh)
                self.assertEqual(gh.writes, [])
                self.arguments(directory).record.unlink()
                shutil.rmtree(directory)

    def test_corrupt_remote_asset_keeps_release_draft_and_preserves_failure_record(self):
        directory, paths, manifest = self.make_bundle()
        gh = FakeGitHub(manifest, paths)
        gh.corrupt_download = True
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory), gh)
        self.assertTrue(gh.release['draft'])
        self.assertNotIn(('publish',), gh.writes)
        self.assertIn('"failed-or-unknown"', self.arguments(directory).record.read_text())

    def test_existing_corrupt_draft_asset_is_not_replaced(self):
        directory, paths, manifest = self.make_bundle()
        gh = FakeGitHub(manifest, paths)
        gh.corrupt_download = True
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory), gh)
        gh.corrupt_download = False
        gh.assets['app.apk'] = b'corrupted existing upload'
        before = list(gh.writes)
        with self.assertRaises(android.AndroidError):
            release.publish(self.arguments(directory, 2), gh)
        self.assertEqual(gh.writes, before)
        self.assertTrue(gh.release['draft'])

    def test_github_failure_classification_only_accepts_actual_404(self):
        executable = self.root / 'gh'
        executable.write_text('fixture')
        with patch.dict(os.environ, GH_TOKEN='fixture-token'):
            gh = release.GitHub(executable, self.settings['repository'], self.root)
        self.assertNotIn('GITHUB_TOKEN', gh.env)
        for status in (401, 403, 500):
            response = subprocess.CompletedProcess([], 1, b'', ('gh: failure (HTTP ' + str(status) + ')').encode())
            with patch.object(release.subprocess, 'run', return_value=response), self.assertRaises(android.AndroidError):
                gh.api('releases/tags/android-v0.2.0', missing=True)
        response = subprocess.CompletedProcess([], 1, b'', b'gh: Not Found (HTTP 404)')
        with patch.object(release.subprocess, 'run', return_value=response):
            self.assertIsNone(gh.api('releases/tags/android-v0.2.0', missing=True))

    def test_signer_uses_narrow_secret_environment_and_removes_temporary_key(self):
        contract = self.root / 'sign-config.json'
        contract.write_text(json.dumps(self.settings))
        unsigned = self.root / 'unsigned.apk'
        unsigned.write_bytes(b'unsigned fixture')
        args = argparse.Namespace(unsigned=unsigned, config=contract, sdk_root=self.root,
                                  java_home=self.root, output=self.root / 'signed.apk')
        bindings = dict(ANDROID_KEYSTORE_BASE64=base64.b64encode(b'fixture key bytes').decode(),
                        ANDROID_KEYSTORE_PASSWORD='fixture-store-password', ANDROID_KEY_PASSWORD='fixture-key-password',
                        ANDROID_KEY_ALIAS='fixture-alias', AWS_SECRET_ACCESS_KEY='unrelated-provider-secret')
        observed = []
        def command(argv, env):
            argv = list(map(str, argv))
            self.assertNotIn('ANDROID_KEYSTORE_BASE64', env)
            self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
            self.assertNotIn('fixture-store-password', ' '.join(argv))
            if argv[0].endswith('zipalign'):
                Path(argv[-1]).write_bytes(unsigned.read_bytes())
            else:
                key = Path(argv[argv.index('--ks') + 1])
                self.assertEqual(key.read_bytes(), b'fixture key bytes')
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                observed.append(key)
                Path(argv[argv.index('--out') + 1]).write_bytes(b'signed fixture')
            return subprocess.CompletedProcess(argv, 0, b'', b'')
        with patch.dict(os.environ, bindings), patch.object(signer, 'toolchain', return_value=(self.tools, {})), \
             patch.object(signer, 'run', side_effect=command), patch.object(android, 'inspect_apk'), \
             redirect_stdout(io.StringIO()):
            signer.sign(args)
        self.assertEqual(args.output.read_bytes(), b'signed fixture')
        self.assertTrue(observed)
        self.assertFalse(any(path.exists() for path in observed))
        with patch.dict(os.environ, bindings), self.assertRaises(android.AndroidError):
            signer.sign(args)

    def test_signer_failure_removes_key_without_publishing_output(self):
        contract = self.root / 'sign-config.json'
        contract.write_text(json.dumps(self.settings))
        unsigned = self.root / 'unsigned.apk'
        unsigned.write_bytes(b'unsigned fixture')
        args = argparse.Namespace(unsigned=unsigned, config=contract, sdk_root=self.root,
                                  java_home=self.root, output=self.root / 'signed.apk')
        observed = []
        def fail(argv, env):
            observed.append(Path(env['HOME']) / 'release.jks')
            self.assertTrue(observed[-1].is_file())
            raise android.AndroidError('simulated tool failure')
        with patch.dict(os.environ, ANDROID_KEYSTORE_BASE64=base64.b64encode(b'fixture key').decode(),
                        ANDROID_KEYSTORE_PASSWORD='fixture-password', ANDROID_KEY_PASSWORD='fixture-password',
                        ANDROID_KEY_ALIAS='alias'), patch.object(signer, 'toolchain', return_value=(self.tools, {})), \
             patch.object(signer, 'run', side_effect=fail), self.assertRaises(android.AndroidError):
            signer.sign(args)
        self.assertFalse(args.output.exists())
        self.assertTrue(observed)
        self.assertFalse(any(path.exists() for path in observed))

    def test_toolchain_rejects_drift_in_java_build_tools_and_platform(self):
        sdk, java = self.root / 'sdk', self.root / 'jdk'
        build, platform = sdk / 'build-tools/35.0.0', sdk / 'platforms/android-35'
        build.mkdir(parents=True)
        platform.mkdir(parents=True)
        (java / 'bin').mkdir(parents=True)
        (java / 'bin/java').write_text('#!/bin/sh\necho \'openjdk version "17.0.12"\' >&2\n')
        (java / 'bin/java').chmod(0o755)
        for name in ('apksigner', 'aapt2', 'zipalign'):
            (build / name).write_text('#!/bin/sh\nexit 0\n')
            (build / name).chmod(0o755)
        (build / 'source.properties').write_text('Pkg.Revision=35.0.0\n')
        (platform / 'source.properties').write_text('AndroidVersion.ApiLevel=35\n')
        (platform / 'android.jar').write_bytes(b'fixture')
        tools, record = android.toolchain(self.settings, sdk, java, android.environment(self.root, java))
        self.assertEqual(set(tools), {'java', 'apksigner', 'aapt2', 'zipalign'})
        self.assertEqual(record['executable_sha256']['aapt2'], android.sha256(build / 'aapt2'))
        for changes in (dict(java_version='21.0.0'), dict(build_tools_version='34.0.0'), dict(compile_sdk=36)):
            with self.subTest(changes=changes), self.assertRaises(android.AndroidError):
                android.toolchain(dict(self.settings, **changes), sdk, java, android.environment(self.root, java))

    def test_wrong_explicit_source_commit_stops_before_github_or_record(self):
        directory, paths, manifest = self.make_bundle()
        gh = FakeGitHub(manifest, paths)
        args = self.arguments(directory)
        args.source_commit = 'b' * 40
        with self.assertRaises(android.AndroidError):
            release.publish(args, gh)
        self.assertEqual(gh.writes, [])
        self.assertFalse(args.record.exists())

    def test_draft_lookup_uses_pending_tag_graphql_and_reads_exact_release_id(self):
        executable = self.root / 'gh'
        executable.write_text('fixture')
        with patch.dict(os.environ, GH_TOKEN='fixture-token'):
            gh = release.GitHub(executable, self.settings['repository'], self.root)
        payload = dict(data=dict(repository=dict(release=dict(databaseId=42))))
        with patch.object(gh, 'command', return_value=json.dumps(payload).encode()) as call, \
             patch.object(gh, 'api', return_value=dict(id=42, draft=True)) as api:
            self.assertTrue(gh.find_release('android-v0.2.0')['draft'])
        api.assert_called_once_with('releases/42')
        request = json.loads(call.call_args.kwargs['input'])
        self.assertEqual(request['variables'], dict(owner='fixture-owner', name='android-notes', tag='android-v0.2.0'))
        with patch.object(gh, 'command', return_value=b'{"data":{"repository":{"release":null}}}'):
            self.assertIsNone(gh.find_release('android-v0.2.0'))
        for payload in (dict(errors=[dict(message='denied')]), dict(data=dict(repository=None))):
            with patch.object(gh, 'command', return_value=json.dumps(payload).encode()), self.assertRaises(android.AndroidError):
                gh.find_release('android-v0.2.0')


if __name__ == '__main__':
    unittest.main()
