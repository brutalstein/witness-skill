#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." 2>/dev/null && pwd || true)
if [ -n "$ROOT" ] && [ -f "$ROOT/pyproject.toml" ] && [ -x "$ROOT/scripts/install-codex.sh" ]; then
  exec "$ROOT/scripts/install-codex.sh" "$@"
fi
echo "This installed skill does not contain the full Witness package." >&2
echo "Clone the Witness GitHub repository and run scripts/install-codex.sh." >&2
exit 2
