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
    parser.add_argument('--environment', default=os.environ.get('FACTORY_ENVIRONMENT', 'development'))
    parser.add_argument('--environment-file', type=Path)
    parser.add_argument('--inventory', type=Path, help='Explicit reviewed strict-schema nonsecret resource inventory')
    args = parser.parse_args()
    if args.command == 'reconcile':
        reconcile()
        print('Context remote and local committed data reconciled without resetting or replaying provider work.')
        return
    require(args.repo, 'Select the exact known app repository')
    target = args.repo.lower()
    tools = load()
    app = args.app or (Path(os.environ['FACTORY_PROJECT_APP']) if os.environ.get('FACTORY_PROJECT_APP') else ROOT / 'workspaces' / target)
    if args.command == 'open':
        selected = restore(target, app, tools)
    else:
        require(args.command != 'inventory' or args.inventory is not None, 'Inventory command requires a reviewed private input')
        additions = [(args.inventory, 'inventory')] if args.command == 'inventory' else []
        data = checkpoint(target, app, additions, initialize=args.command == 'init', environment=args.environment, tools=tools)
        selected = values(data, app)
    output = args.environment_file or Path(os.environ['FACTORY_PRIVATE_ROOT']) / 'project.env'
    write_environment(output, tools, selected)
    print('Verified project context synchronized; generated activation selects its identity and targets. No app source or arbitrary documents exported.')


if __name__ == '__main__':
    cli(main)
