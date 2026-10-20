#!/usr/bin/env python3
"""Initialize/checkpoint or restore one explicitly selected independent project."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from context import checkpoint, reconcile, restore, values
from runtime import ROOT, Parser, cli, load, require, write_environment


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('command', choices=('init', 'open', 'checkpoint', 'reconcile', 'inventory'))
    parser.add_argument('--repo', default=os.environ.get('FACTORY_PROJECT_REPOSITORY'))
    parser.add_argument('--app', type=Path)
    parser.add_argument('--branch', help='Explicit branch for a fresh clone; existing branches are preserved')
    parser.add_argument('--environment', default=os.environ.get('FACTORY_ENVIRONMENT', 'development'))
    parser.add_argument('--environment-file', type=Path)
    parser.add_argument('--inventory', type=Path, help='Explicit reviewed strict-schema nonsecret resource inventory')
    parser.add_argument('--journal', type=Path, action='append', default=[], help='Reviewed safe journal, including initial repository bootstrap evidence')
    parser.add_argument('--ownership', type=Path, action='append', default=[], help='Reviewed creation receipt with its original private journal')
    args = parser.parse_args()
    require(args.repo, 'Select the exact known app repository')
    target = args.repo.lower()
    tools = load()
    app = args.app or (Path(os.environ['FACTORY_PROJECT_APP']) if os.environ.get('FACTORY_PROJECT_APP') else ROOT / 'workspaces' / target)
    if args.command == 'reconcile':
        reconcile(tools, target, app)
        print('Selected app commit reconciled with its remote branch; no reset or provider replay.')
        return
    if args.command == 'open':
        selected = restore(target, app, tools, args.branch)
    else:
        require(args.command != 'inventory' or args.inventory is not None, 'Inventory command requires a reviewed private input')
        additions = [(path, 'journal') for path in args.journal] + [(path, 'ownership') for path in args.ownership]
        if args.inventory:
            additions.append((args.inventory, 'inventory'))
        data = checkpoint(target, app, additions, initialize=args.command == 'init', environment=args.environment, tools=tools)
        selected = values(data, app)
    output = args.environment_file or Path(os.environ['FACTORY_PRIVATE_ROOT']) / 'project.env'
    write_environment(output, tools, selected)
    print('App registry verified; activation selects its identity. Checkpoint files remain uncommitted until the app delivery commit/push.')


if __name__ == '__main__':
    cli(main)
