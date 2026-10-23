#!/usr/bin/env python3
"""Official gh REST transport with conservative failure diagnostics."""
import sys
from provider import ProviderError, gh, gh_clone

try:
    mode, *args = sys.argv[1:]
    if mode == "read":
        sys.stdout.buffer.write(gh(args))
    elif mode == "clone" and len(args) == 2:
        gh_clone(*args)
    elif mode == "create" and len(args) == 3:
        raise ProviderError("Repository creation is manual. Ask Carlo to create the repository and return its URL; use scripts/plan-repo.sh for details.")
    else:
        raise ValueError()
except (ValueError, TypeError, KeyError):
    print("ERROR: Invalid GitHub request or response; reconcile before retry.", file=sys.stderr)
    sys.exit(1)
except ProviderError as error:
    print("ERROR: " + str(error), file=sys.stderr)
    sys.exit(1)
