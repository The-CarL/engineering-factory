#!/usr/bin/env python3
"""Verify a signed standalone APK and prepare a GitHub-downloadable bundle; no network writes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from android import AndroidError, canonical, config, environment, git_facts, inspect_apk, read_json, require, sha256, timestamp, toolchain, verify_upgrade


def prepare(args):
    source = canonical(args.source, directory=True)
    contract = canonical(args.config)
    require(contract.is_relative_to(source), 'Android release configuration must belong to the source checkout')
    settings = config(read_json(contract))
    apk = canonical(args.apk)
    output = Path(args.output)
    require(output.is_absolute() and '..' not in output.parts and not output.exists()
            and not output.is_symlink(), 'Use a new absolute bundle directory; preserve previous outputs')
    canonical(output.parent, directory=True)
    require(apk.suffix == '.apk' and 0 < apk.stat().st_size < 2 * 1024 ** 3, 'Use one nonempty APK below 2 GiB')
    java_home = canonical(args.java_home, directory=True)
    with tempfile.TemporaryDirectory(prefix='factory-android-') as home:
        env = environment(home, java_home)
        facts = git_facts(source, settings['repository'], env)
        from android import run
        committed = run(['git', '-c', 'core.hooksPath=/dev/null', '-C', source, 'show',
                         facts['commit'] + ':' + str(contract.relative_to(source))], env, timeout=30).stdout
        require(committed == contract.read_bytes(), 'Commit the reviewed Android release contract before packaging')
        tools, versions = toolchain(settings, args.sdk_root, java_home, env)
        if args.previous_manifest:
            previous = read_json(canonical(args.previous_manifest))
            verify_upgrade(settings, previous['app'])
        # Validate the exact retained copy, not a mutable input checked before copying.
        with tempfile.TemporaryDirectory(prefix='.android-bundle-', dir=output.parent) as stage:
            stage = Path(stage)
            retained = stage / 'app.apk'
            shutil.copyfile(apk, retained)
            inspect_apk(retained, settings, tools, env)
            require(git_facts(source, settings['repository'], env) == facts, 'App source changed during APK verification')
            manifest = dict(schema=1, platform='android', app=settings, source=facts,
                            verified_at=timestamp(), toolchain=versions,
                            apk=dict(name='app.apk', sha256=sha256(retained), size=retained.stat().st_size),
                            assurance='Verified package/signature; source-to-binary mapping is a build-workflow assertion')
            (stage / 'release.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
            (stage / 'SHA256SUMS').write_text(''.join(sha256(stage / name) + '  ' + name + '\n'
                                                   for name in ('app.apk', 'release.json')))
            require(not output.exists(), 'Bundle output appeared during verification; preserve it')
            # Refuse existing destinations, including an empty directory.
            output.mkdir(mode=0o700)
            for item in stage.iterdir():
                shutil.copyfile(item, output / item.name)
                (output / item.name).chmod(0o600)
    print('Android bundle verified. Device behavior, backend integration and updates require their own acceptance.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'config', 'apk', 'sdk-root', 'java-home', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--previous-manifest', type=Path)
    prepare(parser.parse_args())


if __name__ == '__main__':
    try:
        main()
    except (AndroidError, OSError, ValueError, KeyError, TypeError) as error:
        print('ERROR: ' + (str(error) if isinstance(error, AndroidError) else 'Android input validation failed; detail withheld'),
              file=sys.stderr)
        sys.exit(1)
