#!/usr/bin/env python3
"""Credential-free, retry-safe bootstrap and activation for the supported Cloud base."""
import os
from pathlib import Path
import sys
import re
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from runtime import ROOT, Parser, cli, load, local_git, require, write_environment
sys.path.insert(0, str(Path(__file__).resolve().parent))
from install import install


def setup(destination, environment_file):
    print('factory-setup execution-start', flush=True)
    require(destination.is_absolute() and '..' not in destination.parts
            and not any(path.is_symlink() for path in (destination, *destination.parents)), 'Select a canonical versioned runtime directory')
    private = Path(os.environ.get('FACTORY_PRIVATE_ROOT', ''))
    require(private.is_absolute() and private != Path('/') and '..' not in private.parts
            and not any(path.is_symlink() for path in (private, *private.parents)), 'Select a canonical private root')
    if not private.exists():
        private.mkdir(parents=True, mode=0o700)
    require(private.is_dir() and private.stat().st_mode & 0o077 == 0, 'Private root must have mode 700')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ['FACTORY_RUNTIME_DIRECTORY'] = str(destination)
    expected = str(destination / 'manifest.json')
    require(os.environ.get('FACTORY_RUNTIME_MANIFEST', expected) == expected, 'Runtime manifest differs from selected release')
    os.environ['FACTORY_RUNTIME_MANIFEST'] = expected
    if not destination.exists():
        install(destination)
    tools = load()  # An existing release must pass; never overwrite or re-bless it.
    write_environment(environment_file, tools)
    print('Selected source/runtime verified; activation file generated without credentials. Publication and fresh-task acceptance remain separate.')


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--source-revision', help='Exact reviewed full source commit; never inferred/trusted from HEAD')
    parser.add_argument('--source-repository', help='Approved OWNER/REPO; otherwise verify current credential-free GitHub origin')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--environment-file', type=Path)
    args = parser.parse_args()
    revision = args.source_revision or os.environ.get('FACTORY_SOURCE_REVISION', '')
    require(re.fullmatch(r'[a-f0-9]{40}', revision), 'Select a reviewed full --source-revision; current HEAD is not automatically trusted')
    repository = args.source_repository or os.environ.get('FACTORY_SOURCE_REPOSITORY', '')
    if not repository:
        origin = local_git('remote', 'get-url', '--all', 'origin')
        match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?', origin)
        require(match is not None, 'Factory origin must be a single credential-free GitHub repository')
        repository = match[1]
    private = args.private_root or Path(os.environ.get('FACTORY_PRIVATE_ROOT') or ROOT / 'workspaces/.factory-private/runtime-private')
    destination = args.destination or (Path(os.environ['FACTORY_RUNTIME_DIRECTORY']) if os.environ.get('FACTORY_RUNTIME_DIRECTORY')
                    and not args.source_revision else private / 'releases' / revision)
    os.environ.update(FACTORY_SOURCE_REPOSITORY=repository, FACTORY_SOURCE_REVISION=revision, FACTORY_PRIVATE_ROOT=str(private))
    if args.source_revision or args.destination:
        os.environ['FACTORY_RUNTIME_MANIFEST'] = str(destination / 'manifest.json')
    setup(destination, args.environment_file or private / 'runtime.env')


if __name__ == '__main__':
    cli(main)
