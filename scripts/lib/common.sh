#!/usr/bin/env bash
# Shared by entry points; never load shell code from local .env files.
set -euo pipefail
FACTORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Required tool missing: $1"; }
validate_target() {
  [[ "$TARGET" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}$ ]] || fail 'Use an explicit GitHub OWNER/REPO.'
  OWNER="${TARGET%%/*}"; REPO="${TARGET#*/}"
  [[ "$REPO" != '.' && "$REPO" != '..' && "$REPO" != *.git ]] || fail 'Repository name cannot be ., .., or end in .git.'
  [[ -n "${FACTORY_GITHUB_OWNER:-}" ]] || fail 'Set FACTORY_GITHUB_OWNER to the approved owner.'
  [[ "$(printf %s "$OWNER" | tr '[:upper:]' '[:lower:]')" == "$(printf %s "$FACTORY_GITHUB_OWNER" | tr '[:upper:]' '[:lower:]')" ]] || fail 'Requested owner differs from FACTORY_GITHUB_OWNER.'
  WORKSPACE_OWNER="$(printf %s "$OWNER" | tr '[:upper:]' '[:lower:]')"
  WORKSPACE_REPO="$(printf %s "$REPO" | tr '[:upper:]' '[:lower:]')"
  CHECKOUT="$FACTORY_ROOT/workspaces/$WORKSPACE_OWNER/$WORKSPACE_REPO"
}
check_paths() {
  local path
  need git
  git -C "$FACTORY_ROOT" check-ignore --quiet -- "$CHECKOUT/.factory-ignore-probe" || fail 'Factory workspace path must be ignored by Git before any operation.'
  for path in "$FACTORY_ROOT/workspaces" "$FACTORY_ROOT/workspaces/$WORKSPACE_OWNER" "$CHECKOUT"; do
    [[ ! -L "$path" ]] || fail 'Refusing symlink in checkout path.'
    [[ ! -e "$path" || -d "$path" ]] || fail 'Checkout path component is not a directory.'
  done
}
# Capture only intended data. Provider stderr may contain private context.
gh_read() { GH_HOST=github.com gh api --hostname github.com "$@" 2>/dev/null || fail 'GitHub read failed; check authentication, scope, connectivity, and target privately.'; }
check_identity() {
  need gh; need git; need python3
  IDENTITY="$(gh_read user --jq .login)"
  [[ "$IDENTITY" =~ ^[A-Za-z0-9-]+$ ]] || fail 'Unexpected GitHub identity response.'
}
# A successful complete visible inventory is required. A failed lookup never means absent.
lookup_repo() {
  local kind membership inventory
  check_identity
  kind="$(gh_read "users/$OWNER" --jq .type)"
  case "$kind" in
    User)
      [[ "$(printf %s "$IDENTITY" | tr '[:upper:]' '[:lower:]')" == "$(printf %s "$OWNER" | tr '[:upper:]' '[:lower:]')" ]] || fail 'Personal owner must match authenticated GitHub user.'
      inventory="$(gh_read --paginate --slurp 'user/repos?affiliation=owner&per_page=10')" ;;
    Organization)
      membership="$(gh_read "user/memberships/orgs/$OWNER" --jq .state)"
      [[ "$membership" == active ]] || fail 'Active organization membership was not verified.'
      inventory="$(gh_read --paginate --slurp "orgs/$OWNER/repos?type=all&per_page=10")" ;;
    *) fail 'Unsupported GitHub owner type.' ;;
  esac
  REPO_STATE="$(printf %s "$inventory" | python3 "$FACTORY_ROOT/scripts/lib/json-check.py" repository "$TARGET")" || fail 'Malformed repository inventory or mismatched repository response.'
}
verify_visibility() {
  [[ "$REPO_STATE" == "$VISIBILITY" ]] || fail 'Existing repository visibility differs from requested visibility; no change made.'
}
verify_checkout() {
  local path="$1" top origin push_origin
  [[ -d "$path/.git" && ! -L "$path/.git" ]] || fail 'Existing path is not an independent Git clone.'
  top="$(git -C "$path" rev-parse --show-toplevel 2>/dev/null)" || fail 'Cannot verify checkout root.'
  [[ "$top" == "$(cd -- "$path" && pwd -P)" ]] || fail 'Checkout root does not match expected path.'
  origin="$(git -C "$path" remote get-url --all origin 2>/dev/null)" || fail 'Cannot verify origin.'
  printf %s "$origin" | python3 "$FACTORY_ROOT/scripts/lib/json-check.py" origin "$TARGET" || fail 'Origin differs from requested GitHub repository.'
  push_origin="$(git -C "$path" remote get-url --push --all origin 2>/dev/null)" || fail 'Cannot verify push origin.'
  printf %s "$push_origin" | python3 "$FACTORY_ROOT/scripts/lib/json-check.py" origin "$TARGET" || fail 'Push origin differs from requested GitHub repository.'
}
clone_verified() {
  check_paths
  mkdir -p -- "$FACTORY_ROOT/workspaces/$WORKSPACE_OWNER"
  LOCK="$FACTORY_ROOT/workspaces/$WORKSPACE_OWNER/.$WORKSPACE_REPO.lock"
  mkdir -- "$LOCK" 2>/dev/null || fail 'Checkout is locked; inspect another run before removing a stale lock.'
  CLONE_TEMP=''
  trap '[[ -z "$CLONE_TEMP" ]] || rm -rf -- "$CLONE_TEMP"; rmdir -- "$LOCK"' EXIT
  if [[ -e "$CHECKOUT" ]]; then
    verify_checkout "$CHECKOUT"
    printf 'Verified existing checkout: %s\nNo pull, reset, or file changes performed.\n' "$CHECKOUT"
    return
  fi
  CLONE_TEMP="$(mktemp -d "$FACTORY_ROOT/workspaces/$WORKSPACE_OWNER/.clone.XXXXXX")"
  GH_HOST=github.com gh repo clone "$TARGET" "$CLONE_TEMP/repo" >/dev/null 2>&1 || fail 'Clone failed; repository may exist remotely. Retry safely after fixing authentication or connectivity.'
  verify_checkout "$CLONE_TEMP/repo"
  [[ ! -e "$CHECKOUT" && ! -L "$CHECKOUT" ]] || fail 'Checkout appeared during clone; inspect before retrying.'
  mv -- "$CLONE_TEMP/repo" "$CHECKOUT"
  printf 'Checkout ready: %s\n' "$CHECKOUT"
}
