#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/lib/common.sh"
PROVIDERS=(); OFFLINE=false; VERCEL_TRANSPORT=cli
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vercel-transport) [[ $# -ge 2 && ( "$2" == cli || "$2" == api ) ]] || fail 'Vercel transport must be cli or api.'; VERCEL_TRANSPORT="$2"; shift 2 ;;
    --offline) OFFLINE=true; shift ;;
    --provider) [[ $# -ge 2 ]] || fail 'Missing provider.'; case "$2" in github|vercel|aws) PROVIDERS+=("$2");; *) fail 'Provider must be github, vercel, or aws.';; esac; shift 2 ;;
    --help|-h) printf 'Usage: preflight.sh [--offline] [--provider github|vercel|aws ...] [--vercel-transport cli|api]\nDefault: tool inventory only; no network calls.\n'; exit 0 ;;
    *) fail 'Unknown option.' ;;
  esac
done
for tool in git gh python3 node npm aws vercel terraform cdk; do
  if command -v "$tool" >/dev/null 2>&1; then printf 'Tool %-10s available\n' "$tool"; else printf 'Tool %-10s missing (required only by selected workflow)\n' "$tool"; fi
done
printf 'Dry-run support: plan-repo.sh and clone --dry-run = offline plans; git push --dry-run = remote negotiation.\nGitHub repository creation is manual; Vercel deployment has no universal no-write dry-run here.\nAWS dry-run is service/operation specific; IaC plans can read APIs and are not permission proofs.\n'
if "$OFFLINE" || [[ ${#PROVIDERS[@]} -eq 0 ]]; then
  printf 'Tool inventory only. Authentication, approved targets, and write permissions UNVERIFIED.\n'
  exit 0
fi
need python3
for provider in "${PROVIDERS[@]}"; do
  case "$provider" in
    github)
      need gh
      [[ "${FACTORY_GITHUB_OWNER:-}" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$ ]] || fail 'Set a valid FACTORY_GITHUB_OWNER.'
      TARGET="$FACTORY_GITHUB_OWNER/preflight-probe"; OWNER="$FACTORY_GITHUB_OWNER"
      lookup_repo
      printf 'GitHub: identity and approved owner inventory readable. Repository creation is manual. Existing-repository clone/push/PR/CI permissions UNVERIFIED.\n' ;;
    vercel)
      if [[ "$VERCEL_TRANSPORT" == api ]]; then
        python3 "$FACTORY_ROOT/scripts/vercel-preview.py" identity || fail 'Vercel REST identity gate failed.'
        continue
      fi
      need vercel
      [[ "${FACTORY_VERCEL_TEAM_ID:-}" =~ ^team_[A-Za-z0-9]+$ ]] || fail 'Set FACTORY_VERCEL_TEAM_ID for the approved sandbox team.'
      [[ "${FACTORY_VERCEL_TEAM_SLUG:-}" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]*$ ]] || fail 'Set FACTORY_VERCEL_TEAM_SLUG.'
      response="$(VERCEL_TELEMETRY_DISABLED=1 vercel whoami --format json --scope "$FACTORY_VERCEL_TEAM_SLUG" --non-interactive 2>/dev/null)" || fail 'Vercel identity read failed; check CLI support and credentials privately.'
      printf %s "$response" | python3 "$FACTORY_ROOT/scripts/lib/json-check.py" vercel "$FACTORY_VERCEL_TEAM_ID" || fail 'Vercel effective team does not match approved team, or response cannot be verified.'
      printf 'Vercel native CLI: authenticated principal and approved team verified. Linked project/deployment permissions UNVERIFIED.\n' ;;
    aws)
      need aws
      [[ "${FACTORY_AWS_ACCOUNT_ID:-}" =~ ^[0-9]{12}$ ]] || fail 'Set FACTORY_AWS_ACCOUNT_ID.'
      [[ "${FACTORY_AWS_REGION:-}" =~ ^[a-z]{2}(-[a-z]+)+-[0-9]+$ ]] || fail 'Set FACTORY_AWS_REGION.'
      [[ "${FACTORY_AWS_ROLE_NAME:-}" =~ ^[A-Za-z0-9+=,.@_-]+$ ]] || fail 'Set FACTORY_AWS_ROLE_NAME for an approved assumed role.'
      [[ -z "${AWS_REGION:-}" || "$AWS_REGION" == "$FACTORY_AWS_REGION" ]] || fail 'AWS_REGION differs from approved region.'
      [[ -z "${AWS_DEFAULT_REGION:-}" || "$AWS_DEFAULT_REGION" == "$FACTORY_AWS_REGION" ]] || fail 'AWS_DEFAULT_REGION differs from approved region.'
      arn="$(AWS_PAGER='' aws sts get-caller-identity --region "$FACTORY_AWS_REGION" --query Arn --output text --no-cli-pager 2>/dev/null)" || fail 'AWS identity read failed; check session and network privately.'
      [[ "$arn" == "arn:aws:sts::$FACTORY_AWS_ACCOUNT_ID:assumed-role/$FACTORY_AWS_ROLE_NAME/"* ]] || fail 'AWS identity is not the approved account and assumed role.'
      printf 'AWS: approved assumed role/account identity verified; explicit region selected. Service permissions, budget, and policy enforcement UNVERIFIED.\n' ;;
  esac
done
printf 'No provider writes performed. Identity/target checks do not authorize deployment.\n'
