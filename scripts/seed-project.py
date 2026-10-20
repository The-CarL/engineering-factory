#!/usr/bin/env python3
"""Seed three instruction files in a verified independent clone; local Git reads only."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ("AGENTS.md", "CLAUDE.md", "ENGINEERING.md")


class SeedError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SeedError(message)


def git(path, *args):
    env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    result = subprocess.run(["git", "-C", str(path), *args], env=env, capture_output=True, timeout=30)
    require(result.returncode == 0, "Local Git verification failed")
    return result.stdout


def repository(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value)
            and not value.endswith(".git"), "Specify an exact GitHub OWNER/REPO")
    return value.lower()


def origin_repo(origin):
    patterns = (r"https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?",
                r"git@github\.com:([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
                r"ssh://git@github\.com/([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?")
    for pattern in patterns:
        match = re.fullmatch(pattern, origin)
        if match:
            return repository(match[1])
    raise SeedError("Origin must be an exact credential-free GitHub URL")


def app_path(value):
    require(value.is_absolute() and ".." not in value.parts, "App path must be absolute without path escapes")
    require(not any(part.is_symlink() for part in (value, *value.parents)), "Symlinks in the app path are unsupported; use its canonical path")
    path = value.resolve(strict=True)
    require(path.is_dir() and path != ROOT and not ROOT.is_relative_to(path), "Factory checkout/ancestor cannot be an app target")
    require((path / ".git").is_dir() and not (path / ".git").is_symlink(), "App must be an independent clone, not a linked worktree")
    require(git(path, "rev-parse", "--show-toplevel").decode().strip() == str(path), "App path differs from Git root")
    common = Path(git(path, "rev-parse", "--git-common-dir").decode().strip())
    common = common if common.is_absolute() else path / common
    require(common.resolve() == path / ".git" and not (path / ".git/objects/info/alternates").exists(), "Shared or linked Git metadata is unsupported")
    if path.is_relative_to(ROOT):
        require(path.is_relative_to(ROOT / "workspaces"), "Nested app must be under ignored workspaces")
        require(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--quiet", "--", str(path / ".seed-check")],
                               env={"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
                               capture_output=True, timeout=30).returncode == 0, "App path must be ignored by factory Git")
    return path


def contents(target, origin):
    require(git(ROOT, "rev-parse", "--show-toplevel").decode().strip() == str(ROOT), "Factory source root cannot be verified")
    revision = git(ROOT, "rev-parse", "HEAD").decode().strip()
    require(re.fullmatch(r"[a-f0-9]{40}", revision), "Factory source revision is unavailable")
    factory_repo = origin_repo(git(ROOT, "remote", "get-url", "--all", "origin").decode().strip())
    require(factory_repo != target, "Factory repository cannot be an app target")
    # Verify the version recorded actually contains this helper, its templates and standard.
    names = ["scripts/seed-project.py", "standards/application-design.md", "standards/conversational-delivery.md"] + ["templates/project/" + name + ".tmpl" for name in FILES]
    for name in names:
        require(not (ROOT / name).is_symlink() and git(ROOT, "show", revision + ":" + name) == (ROOT / name).read_bytes(),
                "Commit the reviewed seeding source/templates/standard before use")
    values = {"repository": target, "origin": origin, "revision": revision, "factory_url": "https://github.com/" + factory_repo}
    result = {}
    for name in FILES:
        text = (ROOT / "templates/project" / (name + ".tmpl")).read_text()
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        require(not re.search(r"\{\{[^}]+\}\}", text), "Unresolved instruction template fields")
        result[name] = text.encode()
    return result


def seed(path, expected, confirmation, dry_run=False):
    target = repository(expected)
    require(dry_run or confirmation.lower() == target, "Seeding requires matching --confirm OWNER/REPO")
    path = app_path(path)
    fetch = git(path, "remote", "get-url", "--all", "origin").decode().strip()
    push = git(path, "remote", "get-url", "--push", "--all", "origin").decode().strip()
    require(origin_repo(fetch) == target and origin_repo(push) == target, "App fetch/push origin differs from the expected repository")
    rendered = contents(target, fetch)
    missing = []
    for name, content in rendered.items():
        output = path / name
        require(not output.is_symlink(), "Instruction output is a symlink; no files changed")
        if output.exists():
            require(output.is_file() and output.read_bytes() == content,
                    "Existing instructions differ; integrate deliberately instead of overwriting. No files changed")
        else:
            missing.append((output, content))
    if dry_run:
        print("PLAN ONLY: verified app/source and instruction collisions; no writes or network calls.")
        return
    if not missing:
        print("Instruction seed already matches; no files changed.")
        return
    created = []
    try:
        # Complete every tiny file before exclusive publication. A failed write
        # cannot leave a truncated instruction file in the app root.
        with tempfile.TemporaryDirectory(prefix=".factory-seed-", dir=path) as temporary:
            staged = []
            for output, content in missing:
                stage = Path(temporary) / output.name
                stage.write_bytes(content)
                stage.chmod(0o644)
                staged.append((stage, output, content))
            for stage, output, content in staged:
                os.link(stage, output)  # Atomic and fails if output now exists.
                created.append((output, stage.stat().st_ino, content))
    except OSError:
        # Roll back only our own unchanged complete files, never a user's file.
        for output, inode, content in created:
            if not output.is_symlink() and output.is_file() and output.stat().st_ino == inode and output.read_bytes() == content:
                output.unlink()
        raise SeedError("Instruction write interrupted; existing user files preserved") from None
    print("Instruction seed ready; identical existing files preserved. App implementation/CI/deployment remain app-owned.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        seed(args.app, args.repo, args.confirm, args.dry_run)
    except SeedError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        print("ERROR: Invalid local checkout/source or instruction files; existing user files preserved.", file=sys.stderr)
        sys.exit(1)
