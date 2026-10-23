#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/lib/common.sh"
usage() { printf 'Usage: plan-repo.sh OWNER/REPO [--visibility private|public] [--description TEXT]\nPrints a manual creation brief for Carlo. No network calls or writes.\n'; }
TARGET=''; VISIBILITY=private; DESCRIPTION='Independent application built with the engineering factory.'; CONFIRM=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --visibility|--description|--confirm)
      [[ $# -ge 2 ]] || fail "Missing value for $1"
      case "$1" in
        --visibility) VISIBILITY="$2" ;;
        --description) DESCRIPTION="$2" ;;
        --confirm) CONFIRM="$2" ;; # Legacy create-repo.sh callers; never authorizes a write.
      esac
      shift 2 ;;
    --dry-run) shift ;; # Every invocation is offline.
    --help|-h) usage; exit 0 ;;
    -*) fail 'Unknown option.' ;;
    *) [[ -z "$TARGET" ]] || fail 'Specify one OWNER/REPO.'; TARGET="$1"; shift ;;
  esac
done
[[ "$VISIBILITY" == private || "$VISIBILITY" == public ]] || fail 'Visibility must be private or public.'
validate_target
[[ -z "$CONFIRM" || "$CONFIRM" == "$TARGET" ]] || fail 'Legacy confirmation differs from requested target.'
printf '%s\n' \
  'MANUAL ACTION: Carlo creates the repository at https://github.com/new' \
  "Owner: $OWNER" "Repository name: $REPO" "Visibility: $VISIBILITY" \
  "Description: $DESCRIPTION" \
  'For a new app, leave README, .gitignore and license initialization unchecked.' \
  "Expected URL (unverified): https://github.com/$TARGET" \
  'Return the repository URL when ready. The factory will verify access, owner and visibility before cloning.' \
  'No GitHub requests or filesystem writes performed. Repository existence and access are unverified.'
