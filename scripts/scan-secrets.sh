#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT"
SCANNER="$ROOT/.cache/tools/gitleaks"
[[ -x "$SCANNER" ]] || { printf 'Run scripts/install-check-tools.sh first.\n' >&2; exit 1; }
[[ "$("$SCANNER" version)" == 8.24.3 ]] || { printf 'Wrong Gitleaks version.\n' >&2; exit 1; }
TEMP="$(mktemp -d)"
trap 'rm -rf -- "$TEMP"' EXIT
# Scan non-ignored source, including pending untracked additions; never crawl app workspaces.
python3 - "$ROOT" "$TEMP/source" <<'EXPORT'
from pathlib import Path
import shutil
import subprocess
import sys
root, dest = map(Path, sys.argv[1:])
dest.mkdir()
names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
for name in set(filter(None, names)):
    source = root / name
    if source.is_symlink():
        sys.exit("Refusing symlink in public source scan.")
    if source.is_file():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
EXPORT
# Force reviewed config and ignore location. No inline allow-comments or custom ignore files.
"$SCANNER" dir "$TEMP/source" --config "$ROOT/.gitleaks.toml" --gitleaks-ignore-path "$TEMP" --ignore-gitleaks-allow --redact=100 --no-banner
"$SCANNER" git "$ROOT" --log-opts=--all --config "$ROOT/.gitleaks.toml" --gitleaks-ignore-path "$TEMP" --ignore-gitleaks-allow --redact=100 --no-banner
