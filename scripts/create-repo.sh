#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/lib/common.sh"
usage() { printf 'Usage: create-repo.sh OWNER/REPO [--visibility private|public] [--dry-run | --confirm OWNER/REPO]\n'; }
TARGET=''; VISIBILITY=private; DRY_RUN=false; CONFIRM=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --visibility|--confirm) [[ $# -ge 2 ]] || fail "Missing value for $1"; if [[ "$1" == --visibility ]]; then VISIBILITY="$2"; else CONFIRM="$2"; fi; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage; exit 0 ;;
    -*) fail 'Unknown option.' ;;
    *) [[ -z "$TARGET" ]] || fail 'Specify one OWNER/REPO.'; TARGET="$1"; shift ;;
  esac
done
[[ "$VISIBILITY" == private || "$VISIBILITY" == public ]] || fail 'Visibility must be private or public.'
validate_target; check_paths
if [[ -e "$CHECKOUT" ]]; then need python3; verify_checkout "$CHECKOUT"; fi
if "$DRY_RUN"; then
  printf 'PLAN ONLY: inspect GitHub identity and visible inventory; create %s (%s) if not visible; verify visibility; clone to %s\nNo network calls or writes. Authorization and availability unverified.\n' "$TARGET" "$VISIBILITY" "$CHECKOUT"
  exit 0
fi
[[ "$CONFIRM" == "$TARGET" ]] || fail 'Creation requires --confirm OWNER/REPO matching the requested target.'
lookup_repo
if [[ "$REPO_STATE" == not-visible ]]; then
  # Missing from a successful visible inventory is not proof of global availability.
  # An inaccessible private repository or concurrent create safely fails at GitHub.
  if ! python3 "$FACTORY_ROOT/scripts/lib/github-api.py" create "$OWNER_KIND" "$TARGET" "$VISIBILITY"; then
    # Do not retry POST, even if the response was lost. A subsequent invocation
    # starts with inventory reconciliation and can reuse a visible exact match.
    lookup_repo
    if [[ "$REPO_STATE" == not-visible ]]; then
      fail 'Create failed or outcome unknown; target remains not visible. No clone or mutation retry attempted.'
    fi
    fail 'Create outcome reconciled to a visible repository. No clone attempted; inspect visibility and retry safely.'
  fi
  lookup_repo
fi
verify_visibility
clone_verified
