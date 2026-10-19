#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT"
LINTER="$ROOT/.cache/tools/shellcheck"
[[ -x "$LINTER" ]] || { printf 'Run scripts/install-check-tools.sh first.\n' >&2; exit 1; }
"$LINTER" --version | grep -q '^version: 0.10.0$' || { printf 'Wrong ShellCheck version.\n' >&2; exit 1; }
while IFS= read -r -d '' path; do
  bash -n "$path"
  "$LINTER" --external-sources --check-sourced --shell=bash "$path"
done < <(find scripts -type f -name '*.sh' -print0)
python3 scripts/check-policy.py
python3 -m unittest discover -s tests -v
./scripts/scan-secrets.sh
