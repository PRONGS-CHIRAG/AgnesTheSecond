#!/usr/bin/env bash
# CI guard: fail when any chirag source file imports the taim project.
#
# The taim reference code must remain a standalone comparison artefact. All
# ported logic lives under chirag/src/agnes/... and must not pull symbols from
# the taim package at runtime.
#
# Exit codes:
#   0 — no taim imports detected
#   1 — found one or more forbidden imports (printed to stderr)
#
# Usage:
#   bash scripts/check_no_taim_imports.sh
#
# Run from anywhere. Searches chirag/src and chirag/scripts.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
CHIRAG_ROOT="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"

SEARCH_PATHS=(
  "$CHIRAG_ROOT/src"
  "$CHIRAG_ROOT/scripts"
  "$CHIRAG_ROOT/tests"
)

# Only match at line start (with optional indent) to avoid prose hits in
# docstrings / comments. Requires ``import taim``, ``import taim.foo`` or
# ``from taim[.foo] import ...``.
PATTERN='^[[:space:]]*(from[[:space:]]+taim(\.[a-zA-Z0-9_]+)*[[:space:]]+import|import[[:space:]]+taim(\.[a-zA-Z0-9_]+)?([[:space:]]+as[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*)?[[:space:]]*$)'

hits=""
for path in "${SEARCH_PATHS[@]}"; do
  if [[ -d "$path" ]]; then
    # grep returns 1 when no matches — swallow that, keep going.
    found=$(grep -RInE "$PATTERN" "$path" --include='*.py' --include='*.sh' || true)
    if [[ -n "$found" ]]; then
      hits+="$found"$'\n'
    fi
  fi
done

if [[ -n "${hits// }" ]]; then
  echo "error: forbidden 'taim' import detected in chirag source tree:" >&2
  echo "$hits" >&2
  echo "" >&2
  echo "The taim reference project must remain isolated — port the logic into" >&2
  echo "chirag/src/agnes/... instead of importing it." >&2
  exit 1
fi

echo "OK: no taim imports found in $(IFS=', '; echo "${SEARCH_PATHS[*]}")"
