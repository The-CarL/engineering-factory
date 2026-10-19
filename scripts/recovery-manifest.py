#!/usr/bin/env python3
"""Hash explicitly selected private recovery files without copying or printing them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


def entry(root, name):
    path = Path(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError()
    source = root / path
    if any((root / Path(*path.parts[:index])).is_symlink() for index in range(1, len(path.parts) + 1)):
        raise ValueError()
    info = source.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError()
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": path.as_posix(), "sha256": digest.hexdigest(), "size": info.st_size,
            "mode": stat.S_IMODE(info.st_mode)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--commit")
    parser.add_argument("files", nargs="*")
    args = parser.parse_intermixed_args()
    root = args.root.resolve(strict=True)
    if not root.is_dir() or root.stat().st_mode & 0o077 or args.manifest.is_symlink():
        raise ValueError()
    if args.command == "create":
        if not re.fullmatch(r"[a-f0-9]{40}", args.commit or "") or not args.files or len(set(args.files)) != len(args.files):
            raise ValueError()
        data = {"version": 1, "source_commit": args.commit,
                "files": [entry(root, name) for name in sorted(args.files)]}
        # Exclusive creation preserves the original snapshot instead of re-blessing tampering.
        descriptor = os.open(args.manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    else:
        if args.manifest.stat().st_mode & 0o077:
            raise ValueError()
        data = json.loads(args.manifest.read_text())
        if data.get("version") != 1 or not re.fullmatch(r"[a-f0-9]{40}", data.get("source_commit", "")) or not data.get("files"):
            raise ValueError()
        expected = data["files"]
        if len({item["path"] for item in expected}) != len(expected) or any(entry(root, item["path"]) != item for item in expected):
            raise ValueError()
    print("Recovery integrity verified for explicitly selected files. Durable storage/restore acceptance remains separate.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError):
        print("ERROR: Recovery manifest/file integrity or private permissions failed. Original artifacts preserved.", file=sys.stderr)
        sys.exit(1)
