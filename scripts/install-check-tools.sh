#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
# Hashes reviewed from official release archives; update version + hashes together.
# Gitleaks: https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3
# ShellCheck: https://github.com/koalaman/shellcheck/releases/tag/v0.10.0
case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)
    GITLEAKS_ASSET=gitleaks_8.24.3_linux_x64.tar.gz
    GITLEAKS_SHA=9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c
    SHELLCHECK_ASSET=shellcheck-v0.10.0.linux.x86_64.tar.xz
    SHELLCHECK_SHA=6c881ab0698e4e6ea235245f22832860544f17ba386442fe7e9d629f8cbedf87 ;;
  Darwin/arm64)
    GITLEAKS_ASSET=gitleaks_8.24.3_darwin_arm64.tar.gz
    GITLEAKS_SHA=b90f13bb8c90ab72083d9b0c842e39dafb82c0e5c3f872f407366b7a58909013
    SHELLCHECK_ASSET=shellcheck-v0.10.0.darwin.aarch64.tar.xz
    SHELLCHECK_SHA=bbd2f14826328eee7679da7221f2bc3afb011f6a928b848c80c321f6046ddf81 ;;
  *) printf 'Unsupported platform: add reviewed official artifact hashes first.\n' >&2; exit 1 ;;
esac
for tool in curl python3 tar; do command -v "$tool" >/dev/null || { printf 'Required: %s\n' "$tool" >&2; exit 1; }; done
for path in "$ROOT/.cache" "$ROOT/.cache/tools"; do
  [[ ! -L "$path" && ( ! -e "$path" || -d "$path" ) ]] || { printf 'Unsafe tools directory.\n' >&2; exit 1; }
done
TEMP="$(mktemp -d)"
trap 'rm -rf -- "$TEMP"' EXIT
verify() {
  python3 - "$1" "$2" <<'VERIFY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    sys.exit("Tool archive checksum mismatch; refusing extraction.")
VERIFY
}
curl --fail --silent --show-error --location --retry 2 --proto '=https' --proto-redir '=https' "https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/$GITLEAKS_ASSET" -o "$TEMP/gitleaks.tar.gz"
verify "$TEMP/gitleaks.tar.gz" "$GITLEAKS_SHA"
curl --fail --silent --show-error --location --retry 2 --proto '=https' --proto-redir '=https' "https://github.com/koalaman/shellcheck/releases/download/v0.10.0/$SHELLCHECK_ASSET" -o "$TEMP/shellcheck.tar.xz"
verify "$TEMP/shellcheck.tar.xz" "$SHELLCHECK_SHA"
tar -xzf "$TEMP/gitleaks.tar.gz" -C "$TEMP" gitleaks
tar -xJf "$TEMP/shellcheck.tar.xz" -C "$TEMP" shellcheck-v0.10.0/shellcheck
mkdir -p -- "$ROOT/.cache/tools"
# Reject existing symlinks before replacing executable files.
for tool in gitleaks shellcheck; do
  [[ ! -L "$ROOT/.cache/tools/$tool" ]] || { printf 'Unsafe tool destination.\n' >&2; exit 1; }
done
cp -- "$TEMP/gitleaks" "$ROOT/.cache/tools/gitleaks"
cp -- "$TEMP/shellcheck-v0.10.0/shellcheck" "$ROOT/.cache/tools/shellcheck"
chmod 755 "$ROOT/.cache/tools/gitleaks" "$ROOT/.cache/tools/shellcheck"
printf 'Installed verified Gitleaks 8.24.3 and ShellCheck 0.10.0 into .cache/tools.\n'
