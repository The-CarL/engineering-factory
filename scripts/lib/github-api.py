#!/usr/bin/env python3
"""Official gh REST transport with conservative failure diagnostics."""
import json
import sys
from provider import ProviderError, gh, gh_clone

try:
    mode, *args = sys.argv[1:]
    if mode == "read":
        sys.stdout.buffer.write(gh(args))
    elif mode == "clone" and len(args) == 2:
        gh_clone(*args)
    elif mode == "create" and len(args) == 3:
        kind, target, visibility = args
        owner, name = target.split("/")
        if kind not in ("User", "Organization") or visibility not in ("private", "public"):
            raise ValueError()
        endpoint = "user/repos" if kind == "User" else "orgs/" + owner + "/repos"
        raw = gh(["--method", "POST", endpoint, "--input", "-"],
                 {"name": name, "private": visibility == "private"}, include=True)
        data = json.loads(raw)
        if (data.get("full_name", "").lower() != target.lower()
                or data.get("private") is not (visibility == "private")):
            raise ProviderError("GitHub; created response target/visibility mismatch; reconcile before retry")
    else:
        raise ValueError()
except (ValueError, TypeError, KeyError):
    print("ERROR: Invalid GitHub request or response; reconcile before retry.", file=sys.stderr)
    sys.exit(1)
except ProviderError as error:
    print("ERROR: " + str(error), file=sys.stderr)
    sys.exit(1)
