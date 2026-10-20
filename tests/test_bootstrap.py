"""Bootstrap host capability, archive, activation and interrupted-install recovery contracts."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import runtime
from provider import ProviderError


def module(name, source):
    spec = importlib.util.spec_from_file_location(name, ROOT / source)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


install = module('bootstrap_install', 'runtime/install.py')
setup = module('bootstrap_setup', 'runtime/setup.py')


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.release = self.root / 'release'
        self.pins = json.loads((ROOT / 'runtime/pins.json').read_text())
        self.environ = patch.dict(os.environ, dict(FACTORY_PRIVATE_ROOT=str(self.root),
            FACTORY_SOURCE_REPOSITORY='fixture-owner/factory', FACTORY_SOURCE_REVISION='a' * 40,
            FACTORY_RUNTIME_DIRECTORY=str(self.release), PATH='/old/wrapper:/usr/bin:/bin'), clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.tools = {name: str(self.release / name / 'bin' / name) for name in ('aws', 'gh', 'node', 'python', 'git', 'npm', 'vercel')}


    def test_one_command_onboarding_defaults_paths_but_requires_reviewed_source_pin(self):
        for key in ('FACTORY_SOURCE_REPOSITORY', 'FACTORY_SOURCE_REVISION', 'FACTORY_RUNTIME_DIRECTORY'):
            del os.environ[key]
        with patch.object(setup, 'local_git', return_value='https://github.com/fixture-owner/factory.git'), \
             patch.object(setup, 'setup') as bootstrap, patch.object(sys, 'argv', ['setup.py', '--source-revision', 'b' * 40]):
            setup.main()
        self.assertEqual(os.environ['FACTORY_SOURCE_REPOSITORY'], 'fixture-owner/factory')
        self.assertEqual(os.environ['FACTORY_SOURCE_REVISION'], 'b' * 40)
        self.assertEqual(bootstrap.call_args.args, (self.root / 'releases' / ('b' * 40), self.root / 'runtime.env'))
        os.environ.pop('FACTORY_SOURCE_REVISION')
        with patch.object(setup, 'setup') as bootstrap, patch.object(sys, 'argv', ['setup.py']), self.assertRaises(ProviderError):
            setup.main()
        bootstrap.assert_not_called()

    def test_base_accepts_supported_git_python_without_preinstalled_node_or_npm(self):
        versions = [subprocess.CompletedProcess([], 0, b'git version 2.43.0\n', b''),
                    subprocess.CompletedProcess([], 0, b'Python 3.12.3\n', b'')]
        with patch.object(install.shutil, 'which', return_value='/usr/bin/git') as lookup, \
             patch.object(install.subprocess, 'run', side_effect=versions) as process, \
             patch.object(install.platform, 'libc_ver', return_value=('glibc', '2.39')):
            tools, observed = install.host_tools(self.pins, runtime.base_env(self.root))
        self.assertEqual(set(tools), {'git', 'python'})
        self.assertEqual(observed['git'], '2.43.0')
        self.assertEqual(lookup.call_args.args, ('git',))
        self.assertTrue(all('GH_TOKEN' not in call.kwargs['env'] for call in process.call_args_list))

    def test_unsupported_base_stops_before_artifact_download(self):
        old = subprocess.CompletedProcess([], 0, b'git version 2.20.0\n', b'')
        with patch.object(install.subprocess, 'run', return_value=old), \
             patch.object(install.shutil, 'which', return_value='/usr/bin/git'), self.assertRaises(ProviderError):
            install.host_tools(self.pins, runtime.base_env(self.root))

    def archive(self, members):
        archive = self.root / 'node.tar.xz'
        with tarfile.open(archive, 'w:xz') as output:
            for name, content, link in members:
                entry = tarfile.TarInfo(name)
                if link:
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = link
                    output.addfile(entry)
                else:
                    entry.size = len(content)
                    entry.mode = 0o755
                    output.addfile(entry, io.BytesIO(content))
        return archive

    def test_node_archive_extracts_pinned_layout_and_rejects_escape_before_writes(self):
        prefix = 'node-v24.19.0-linux-x64'
        archive = self.archive([(prefix + '/bin/node', b'fixture node', None),
                                (prefix + '/bin/npm', b'', '../lib/node_modules/npm/bin/npm-cli.js'),
                                (prefix + '/lib/node_modules/npm/bin/npm-cli.js', b'fixture npm', None)])
        target = self.root / 'unpacked'
        target.mkdir()
        extracted = install.unpack_node(archive, target, self.pins['node'])
        self.assertEqual((extracted / 'bin/node').read_bytes(), b'fixture node')
        self.assertEqual((extracted / 'bin/npm').resolve(), extracted / 'lib/node_modules/npm/bin/npm-cli.js')
        archive.unlink()
        malicious = self.archive([(prefix + '/bin/node', b'not extracted', None), (prefix + '/escape', b'', '../../../outside')])
        rejected = self.root / 'rejected'
        rejected.mkdir()
        with self.assertRaises(ProviderError):
            install.unpack_node(malicious, rejected, self.pins['node'])
        self.assertEqual(list(rejected.iterdir()), [])

    def test_partial_download_leaves_no_release_and_preserves_prior_release(self):
        old = self.root / 'last-confirmed'
        old.mkdir(mode=0o700)
        (old / 'sentinel').write_text('keep')
        with patch.object(install.platform, 'system', return_value='Linux'), \
             patch.object(install.platform, 'machine', return_value='x86_64'), \
             patch.object(install, 'check_source', return_value=('fixture-owner/factory', 'a' * 40, {})), \
             patch.object(install, 'host_tools', return_value=({'git': '/usr/bin/git', 'python': sys.executable}, {})), \
             patch.object(install, 'download', side_effect=ProviderError('fixture transport failed')):
            for _ in range(2):
                with self.assertRaises(ProviderError):
                    install.install(self.release)
        self.assertFalse(self.release.exists())
        self.assertEqual((old / 'sentinel').read_text(), 'keep')
        self.assertFalse(list(self.root.glob('.factory-install-*')))

    def test_setup_retry_reuses_verified_release_but_never_reinstalls_tampered_one(self):
        output = self.root / 'runtime.env'
        def installed(path):
            path.mkdir(mode=0o700)
            (path / 'manifest.json').write_text('{}')
        with patch.object(setup, 'install', side_effect=installed) as installer, \
             patch.object(setup, 'load', return_value=self.tools), redirect_stdout(io.StringIO()):
            setup.setup(self.release, output)
            setup.setup(self.release, output)
        self.assertEqual(installer.call_count, 1)
        text = output.read_text()
        self.assertIn('FACTORY_GITHUB_CREDENTIAL_SOURCE=factory-token', text)
        self.assertNotIn('/old/wrapper', text)
        self.assertIn(str(self.release / 'aws/bin'), text)
        self.assertIn(str(self.release / 'vercel/node_modules/.bin'), text)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with patch.object(setup, 'load', side_effect=ProviderError('integrity mismatch')), \
             patch.object(setup, 'install') as installer, self.assertRaises(ProviderError):
            setup.setup(self.release, output)
        installer.assert_not_called()
        self.assertEqual(output.read_text(), text)

    def test_setup_manifest_mismatch_and_unrelated_activation_are_preserved(self):
        os.environ['FACTORY_RUNTIME_MANIFEST'] = str(self.root / 'wrong/manifest.json')
        with patch.object(setup, 'install') as installer, self.assertRaises(ProviderError):
            setup.setup(self.release, self.root / 'runtime.env')
        installer.assert_not_called()
        del os.environ['FACTORY_RUNTIME_MANIFEST']
        target = self.root / 'runtime.env'
        target.write_text('preserve user configuration')
        target.chmod(0o600)
        with self.assertRaises(ProviderError):
            runtime.write_environment(target, self.tools)
        self.assertEqual(target.read_text(), 'preserve user configuration')


if __name__ == '__main__':
    unittest.main()
