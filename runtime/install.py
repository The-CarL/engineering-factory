#!/usr/bin/env python3
"""Install a versioned Linux prepared-host runtime; never retain credentials."""
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from runtime import ROOT, Parser, base_env, check_source, cli, digest, require


def download(pin, destination):
    with urllib.request.urlopen(pin['url'], timeout=120) as response, destination.open('xb') as output:
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            require(total <= 512 * 1024 * 1024, 'Tool archive exceeds limit')
            output.write(block)
    require(digest(destination.read_bytes()) == pin['sha256'], 'Official tool archive hash mismatch')


def version(command, expected, env):
    result = subprocess.run(command, env=env, capture_output=True, timeout=120)
    require(result.returncode == 0 and re.search(r'(?<![0-9.])' + re.escape(expected) + r'(?![0-9A-Za-z.+-])', result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')),
            'Prepared host/tool version does not match reviewed pins')


def install(destination):
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Runtime requires the reviewed Linux x86_64 prepared host')
    repo, revision, sources = check_source()
    pins = json.loads((ROOT / 'runtime/pins.json').read_text())
    require(destination.is_absolute() and '..' not in destination.parts
            and not any(p.is_symlink() for p in (destination, *destination.parents)), 'Runtime destination must be canonical')
    require(destination.parent.is_dir() and not destination.exists(), 'Use a new versioned runtime directory; never overwrite a retained release')
    if destination.is_relative_to(ROOT):
        require(subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--quiet', '--', str(destination)],
                               capture_output=True, env=base_env('/tmp')).returncode == 0, 'Runtime destination must be ignored')
    with tempfile.TemporaryDirectory(prefix='.factory-install-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        env = base_env(stage)
        host = {name: str(Path(shutil.which(executable) or '').resolve()) for name, executable in
                (('git', 'git'), ('python', 'python3'), ('node', 'node'), ('npm', 'npm'))}
        for name in ('git', 'python', 'node'):
            version([host[name], '--version'], pins['host'][name], env)
        version([host['node'], host['npm'], '--version'], pins['host']['npm'], env)
        gh_archive, aws_archive = stage / 'gh.tar.gz', stage / 'aws.zip'
        download(pins['gh'], gh_archive)
        download(pins['aws'], aws_archive)
        release = stage / 'release'
        release.mkdir(mode=0o700)
        (release / 'bin').mkdir()
        with tarfile.open(gh_archive) as archive:
            member = archive.getmember('gh_' + pins['gh']['version'] + '_linux_amd64/bin/gh')
            require(member.isfile(), 'Unexpected gh archive member')
            (release / 'bin/gh').write_bytes(archive.extractfile(member).read())
            (release / 'bin/gh').chmod(0o755)
        with zipfile.ZipFile(aws_archive) as archive:
            for member in archive.infolist():
                path = Path(member.filename)
                require(not path.is_absolute() and '..' not in path.parts and not (member.external_attr >> 16) & 0o170000 == 0o120000,
                        'Unsafe AWS archive member')
            archive.extractall(stage / 'unpacked')
            for member in archive.infolist():
                path = stage / 'unpacked' / member.filename
                if not member.is_dir() and member.external_attr >> 16 & 0o111:
                    path.chmod(0o755)
        result = subprocess.run(['/bin/sh', str(stage / 'unpacked/aws/install'), '--install-dir', str(release / 'aws'),
                                 '--bin-dir', str(release / 'aws-bin')], env=env, capture_output=True, timeout=120)
        require(result.returncode == 0, 'Verified AWS installer failed; detail withheld')
        # AWS's installer embeds absolute symlink targets. Relocate them to the final immutable release.
        for item in release.rglob('*'):
            if item.is_symlink():
                target = os.readlink(item)
                if target.startswith(str(release)):
                    item.unlink()
                    item.symlink_to(os.path.relpath(target, item.parent))
        (release / 'vercel').mkdir()
        for name in ('package.json', 'package-lock.json'):
            shutil.copyfile(ROOT / 'runtime/vercel' / name, release / 'vercel' / name)
        for name in ('user-npmrc', 'global-npmrc'):
            (stage / name).touch(mode=0o600)
        npm_env = dict(env, npm_config_cache=str(stage / 'npm-cache'), npm_config_userconfig=str(stage / 'user-npmrc'),
                       npm_config_globalconfig=str(stage / 'global-npmrc'), npm_config_registry='https://registry.npmjs.org')
        result = subprocess.run([host['node'], host['npm'], 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--omit=dev'],
                                cwd=release / 'vercel', env=npm_env, capture_output=True, timeout=600)
        require(result.returncode == 0, 'Locked Vercel installation failed; detail withheld')
        paths = dict(host, gh='bin/gh', aws='aws/v2/current/bin/aws', vercel='vercel/node_modules/vercel/dist/index.js')
        version([str(release / paths['gh']), '--version'], pins['gh']['version'], env)
        version([str(release / paths['aws']), '--version'], 'aws-cli/' + pins['aws']['version'], env)
        version([host['node'], str(release / paths['vercel']), '--version'], pins['vercel']['version'], env)
        for name, script, mode in (('factory-aws', 'aws.py', []), ('factory-gh', 'github.py', ['gh']),
                                   ('factory-git', 'github.py', ['git']), ('factory-vercel', 'vercel.py', [])):
            content = '#!' + host['python'] + '\nimport os,sys\nos.execv(' + repr(host['python']) + ', [' + repr(host['python']) + ', ' + repr(str(ROOT / 'scripts/runtime' / script)) + ', *' + repr(mode) + ', *sys.argv[1:]])\n'
            (release / 'bin' / name).write_text(content)
            (release / 'bin' / name).chmod(0o755)
        files = {}
        for item in sorted(release.rglob('*')):
            if item.is_symlink():
                require(item.resolve().is_relative_to(release), 'Installed symlink escapes runtime')
                files[str(item.relative_to(release))] = {'link': os.readlink(item)}
            elif item.is_file():
                files[str(item.relative_to(release))] = {'sha256': digest(item.read_bytes()), 'mode': item.stat().st_mode & 0o777}
        tools = {}
        for name, path in paths.items():
            item = Path(path) if Path(path).is_absolute() else release / path
            tools[name] = {'path': path, 'sha256': digest(item.read_bytes())}
        manifest = dict(schema=1, repository=repo, revision=revision, source=sources, tools=tools, files=files, pins=pins)
        (release / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True) + '\n')
        (release / 'manifest.json').chmod(0o600)
        release.rename(destination)
    print('Runtime installed. Configure its private manifest path and run startup verification before use.')


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    install(parser.parse_args().destination)


if __name__ == '__main__':
    cli(main)
