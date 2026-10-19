#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/lib/common.sh"
usage() { printf 'Usage: clone-repo.sh OWNER/REPO [--visibility private|public|internal] [--dry-run]\n'; }
TARGET=''; VISIBILITY=private; DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --visibility) [[ $# -ge 2 ]] || fail 'Missing visibility.'; VISIBILITY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage; exit 0 ;;
    -*) fail 'Unknown option.' ;;
    *) [[ -z "$TARGET" ]] || fail 'Specify one OWNER/REPO.'; TARGET="$1"; shift ;;
  esac
done
[[ "$VISIBILITY" == private || "$VISIBILITY" == public || "$VISIBILITY" == internal ]] || fail 'Unsupported visibility.'
validate_target; check_paths
if [[ -e "$CHECKOUT" ]]; then need python3; verify_checkout "$CHECKOUT"; fi
if "$DRY_RUN"; then
  printf 'PLAN ONLY: inspect visible GitHub repository %s (%s); clone to %s or verify existing origin.\nNo network calls or writes. Authorization and availability unverified.\n' "$TARGET" "$VISIBILITY" "$CHECKOUT"
  exit 0
fi
lookup_repo
[[ "$REPO_STATE" != not-visible ]] || fail 'Repository not visible in successful inventory; check target and access. Nothing cloned.'
verify_visibility
clone_verified
