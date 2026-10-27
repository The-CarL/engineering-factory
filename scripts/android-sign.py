#!/usr/bin/env python3
"""Sign one aligned APK using app-owned keystore environment bindings; never generate or rotate keys."""
import argparse
import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from android import AndroidError, canonical, config, environment, read_json, require, run, toolchain


def sign(args):
    unsigned = canonical(args.unsigned)
    settings = config(read_json(canonical(args.config)))
    java = canonical(args.java_home, directory=True)
    output = Path(args.output)
    canonical(output.parent, directory=True)
    require(output.is_absolute() and '..' not in output.parts and not output.exists() and not output.is_symlink(),
            'Use a new signed APK path; preserve prior outputs')
    with tempfile.TemporaryDirectory(prefix='factory-android-sign-') as home:
        home = Path(home).resolve()
        env = environment(home, java)
        tools, _ = toolchain(settings, args.sdk_root, java, env)
        # Resolve sensitive bindings after checking inputs and toolchain.
        encoded = os.environ.get('ANDROID_KEYSTORE_BASE64', '')
        require(encoded and len(encoded) <= 48 * 1024, 'Provide a bounded app-owned keystore binding')
        keystore = base64.b64decode(encoded, validate=True)
        require(keystore, 'Keystore binding is empty')
        key = home / 'release.jks'
        key.write_bytes(keystore)
        key.chmod(0o600)
        for name in ('ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_PASSWORD', 'ANDROID_KEY_ALIAS'):
            require(os.environ.get(name), 'Required app signing binding is missing')
        env['ANDROID_KEYSTORE_PASSWORD'] = os.environ['ANDROID_KEYSTORE_PASSWORD']
        env['ANDROID_KEY_PASSWORD'] = os.environ['ANDROID_KEY_PASSWORD']
        aligned, signed = home / 'aligned.apk', home / 'signed.apk'
        run([tools['zipalign'], '-P', '16', '-f', '4', unsigned, aligned], env)
        run([tools['apksigner'], 'sign', '--ks', key, '--ks-key-alias', os.environ['ANDROID_KEY_ALIAS'],
             '--ks-pass', 'env:ANDROID_KEYSTORE_PASSWORD', '--key-pass', 'env:ANDROID_KEY_PASSWORD',
             '--out', signed, aligned], env)
        from android import inspect_apk
        inspect_apk(signed, settings, tools, environment(home, java))
        with output.open('xb') as stream:
            os.chmod(output, 0o600)
            with signed.open('rb') as source:
                import shutil
                shutil.copyfileobj(source, stream)
    print('APK signed and verified; temporary keystore removed. Retain the enrolled key in approved durable storage.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('unsigned', 'config', 'sdk-root', 'java-home', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    sign(parser.parse_args())


if __name__ == '__main__':
    try:
        main()
    except (AndroidError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        print('ERROR: APK signing failed; details withheld. Preserve the existing signing identity.', file=sys.stderr)
        sys.exit(1)
