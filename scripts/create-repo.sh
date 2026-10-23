#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'Automatic repository creation is retired. Printing the manual creation brief for Carlo.' >&2
exec /bin/bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/plan-repo.sh" "$@"
