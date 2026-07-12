#!/usr/bin/env sh
set -eu
if command -v witness >/dev/null 2>&1; then
  exec witness "$@"
fi
if [ -x "$HOME/.local/bin/witness" ]; then
  exec "$HOME/.local/bin/witness" "$@"
fi
echo "Witness is not installed. Run the repository's scripts/install-codex.sh first." >&2
exit 2
