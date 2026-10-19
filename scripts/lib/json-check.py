#!/usr/bin/env python3
"""Validate provider data without printing raw responses or credentials."""
import json
import re
import sys

mode, target = sys.argv[1:3]
try:
    raw = sys.stdin.read()
    if mode == "origin":
        patterns = (r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?",
                    r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?",
                    r"ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?")
        matches = [re.fullmatch(pattern, raw) for pattern in patterns]
        if not any(match and match[1].lower() == target.lower() for match in matches):
            raise ValueError("origin")
    elif mode == "repository":
        pages = json.loads(raw)
        if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
            raise ValueError("pages")
        repos = [repo for page in pages for repo in page]
        if any(not isinstance(repo, dict)
               or not isinstance(repo.get("full_name"), str)
               or not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", repo["full_name"])
               or repo.get("visibility") not in ("private", "public", "internal")
               for repo in repos):
            raise ValueError("repository entry")
        found = [repo for repo in repos if repo["full_name"].lower() == target.lower()]
        if len(found) > 1:
            raise ValueError("duplicate")
        if not found:
            print("not-visible")
        else:
            visibility = found[0].get("visibility")
            if visibility not in ("private", "public", "internal"):
                raise ValueError("visibility")
            print(visibility)
    elif mode == "vercel":
        data = json.loads(raw)
        team = data.get("team")
        if not isinstance(team, dict) or team.get("id") != target:
            raise ValueError("team")
        if not data.get("username") and not data.get("app"):
            raise ValueError("principal")
    else:
        raise ValueError("mode")
except (ValueError, TypeError, AttributeError, KeyError):
    sys.exit(1)
