#!/usr/bin/env python3
"""Publish a verified APK bundle to one existing GitHub repository; intended for trusted app CI."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from android import AndroidError, bundle, canonical, environment, require, sha256, timestamp


class GitHub:
    def __init__(self, executable, repository, home):
        self.executable = canonical(executable)
        self.repository = repository
        self.env = environment(home)
        # One explicit job credential. Never fall back to personal CLI caches.
        token = os.environ.get('GH_TOKEN', '')
        require(token.strip(), 'Set GH_TOKEN to the approved app/job credential')
        self.env.update(GH_TOKEN=token, GH_HOST='github.com', GH_CONFIG_DIR=str(home),
                        GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1', GH_PAGER='cat')

    def command(self, *arguments, input=None, missing=False, timeout=120):
        try:
            result = subprocess.run([str(self.executable), *map(str, arguments)], env=self.env,
                                    input=input, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise AndroidError('GitHub outcome may be unknown; reconcile the exact tag/release before retrying') from None
        if missing and result.returncode and re.search(rb'\(HTTP 404\)', result.stderr):
            return None
        require(result.returncode == 0, 'GitHub request failed; stop and reconcile; provider detail withheld')
        return result.stdout

    def api(self, endpoint, data=None, missing=False):
        command = ['api', '--hostname', 'github.com', 'repos/' + self.repository + ('/' + endpoint if endpoint else '')]
        if data is not None:
            command += ['--method', 'POST', '--input', '-']
        raw = self.command(*command, input=json.dumps(data).encode() if data is not None else None, missing=missing)
        return json.loads(raw) if raw is not None else None


    def find_release(self, tag):
        # REST by-tag lookup omits drafts. Resolve the exact pending/published tag
        # through GraphQL, then read the complete release by its numeric ID.
        owner, name = self.repository.split('/')
        query = 'query($owner:String!,$name:String!,$tag:String!){repository(owner:$owner,name:$name){release(tagName:$tag){databaseId}}}'
        request = dict(query=query, variables=dict(owner=owner, name=name, tag=tag))
        response = json.loads(self.command('api', '--hostname', 'github.com', 'graphql', '--input', '-',
                                          input=json.dumps(request).encode()))
        require(not response.get('errors') and isinstance(response.get('data', {}).get('repository'), dict),
                'GitHub release lookup failed; absence is not established')
        found = response['data']['repository'].get('release')
        if found is None:
            return None
        require(type(found.get('databaseId')) is int and found['databaseId'] > 0, 'Invalid release lookup ID')
        return self.api('releases/' + str(found['databaseId']))


def release_identity(release, tag, marker):
    require(release.get('tag_name') == tag and release.get('body') == marker
            and release.get('prerelease') is True, 'Existing release differs; do not adopt or overwrite it')
    require(type(release.get('id')) is int and isinstance(release.get('assets'), list), 'Invalid GitHub release response')


def publish(args, github=None):
    directory, paths, manifest = bundle(args.bundle)
    repo = manifest['app']['repository'].lower()
    require(args.repo.lower() == repo and re.fullmatch(r'android-[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', args.tag),
            'Use the bundle repository and an explicit android-* release tag')
    require(args.visibility in ('private', 'public'), 'Choose expected repository visibility')
    record = Path(args.record)
    canonical(record.parent, directory=True)
    require(record.is_absolute() and not record.exists() and not record.is_symlink() and '..' not in record.parts,
            'Use a new operation record; preserve previous evidence')
    require(not record.is_relative_to(directory), 'Keep operation evidence outside the downloadable bundle')
    commit = manifest['source']['commit']
    require(re.fullmatch(r'[a-f0-9]{40}', args.source_commit) and commit == args.source_commit,
            'Bundle source differs from the explicitly selected release commit')
    marker = 'Engineering Factory Android preview\n\nSource: ' + commit + '\nManifest SHA-256: ' + sha256(paths['release.json'])
    with record.open('x') as stream:
        os.chmod(record, 0o600)
        def event(state, **details):
            stream.write(json.dumps(dict(time=timestamp(), state=state, repository=repo,
                                         tag=args.tag, commit=commit, **details), sort_keys=True) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        with tempfile.TemporaryDirectory(prefix='factory-android-release-') as home:
            home = str(Path(home).resolve())
            gh = github or GitHub(args.gh, repo, home)
            event('intent', manifest_sha256=sha256(paths['release.json']))
            try:
                target = gh.api('')
                require(target.get('full_name', '').lower() == repo
                        and target.get('private') is (args.visibility == 'private'),
                        'GitHub repository identity/visibility mismatch')
                remote_commit = gh.api('git/commits/' + commit)
                require(remote_commit.get('sha') == commit, 'Release source is not present in the target repository')
                reference = gh.api('git/ref/tags/' + args.tag, missing=True)
                if reference is not None:
                    require(reference.get('object', {}).get('type') == 'commit'
                            and reference['object'].get('sha') == commit,
                            'Existing tag differs or is annotated; preserve it and choose/review another tag')
                release = gh.find_release(args.tag)
                if release is not None:
                    release_identity(release, args.tag, marker)
                    require(reference is not None, 'Existing release has no matching source tag')
                if reference is None:
                    gh.api('git/refs', dict(ref='refs/tags/' + args.tag, sha=commit))
                    reference = gh.api('git/ref/tags/' + args.tag)
                    require(reference.get('object') == dict(type='commit', sha=commit)
                            or (reference.get('object', {}).get('type') == 'commit'
                                and reference['object'].get('sha') == commit), 'Created tag readback differs')
                    event('tag-confirmed')
                if release is None:
                    # Draft first. A failed/unknown upload must not expose a partial release.
                    release = gh.api('releases', dict(tag_name=args.tag, target_commitish=commit,
                                     name='Android ' + manifest['app']['version_name'], body=marker,
                                     draft=True, prerelease=True, make_latest='false'))
                    release_identity(release, args.tag, marker)
                    event('draft-confirmed', release_id=release['id'])
                asset_names = [asset.get('name') for asset in release['assets']]
                require(len(asset_names) == len(set(asset_names)) and set(asset_names) <= set(paths),
                        'Existing release has unexpected or duplicate assets')
                if not release.get('draft'):
                    require(set(asset_names) == set(paths), 'Published release is incomplete; do not modify it')
                for name, path in paths.items():
                    if name not in asset_names:
                        gh.command('release', 'upload', args.tag, path, '--repo', repo, timeout=600)
                        event('asset-upload-returned', asset=name)
                # Read every remote asset's bytes, including retained assets after a partial draft.
                downloaded = Path(home) / 'readback'
                downloaded.mkdir()
                gh.command('release', 'download', args.tag, '--repo', repo, '--dir', downloaded, timeout=600)
                require({item.name for item in downloaded.iterdir()} == set(paths), 'Release readback asset set differs')
                for name, path in paths.items():
                    canonical(downloaded / name)
                    require(sha256(downloaded / name) == sha256(path), 'Downloaded release asset differs; preserve evidence')
                event('asset-readback-confirmed')
                # Revalidate local inputs immediately before making the release visible.
                _, _, current = bundle(directory)
                require(current == manifest and sha256(paths['release.json']) in marker, 'Local bundle changed during publication')
                final_ref = gh.api('git/ref/tags/' + args.tag)
                require(final_ref.get('object', {}).get('type') == 'commit'
                        and final_ref['object'].get('sha') == commit, 'Release tag changed during publication')
                if release.get('draft'):
                    gh.command('release', 'edit', args.tag, '--repo', repo, '--draft=false', '--latest=false')
                result = gh.api('releases/tags/' + args.tag)
                release_identity(result, args.tag, marker)
                require(result.get('draft') is False and {asset['name'] for asset in result['assets']} == set(paths),
                        'Final release readback differs')
                url = 'https://github.com/' + repo + '/releases/tag/' + args.tag
                event('complete', url=url)
            except (AndroidError, OSError, ValueError, KeyError, TypeError):
                event('failed-or-unknown')
                raise
    print('Android preview release verified: ' + url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--visibility', required=True, choices=('private', 'public'))
    parser.add_argument('--tag', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--gh', required=True, type=Path)
    parser.add_argument('--record', required=True, type=Path)
    publish(parser.parse_args())


if __name__ == '__main__':
    try:
        main()
    except (AndroidError, OSError, ValueError, KeyError, TypeError):
        print('ERROR: Android release not confirmed; preserve its operation record and reconcile before retrying.', file=sys.stderr)
        sys.exit(1)
