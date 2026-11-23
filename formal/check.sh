#!/usr/bin/env bash
# Builds the Lean model and checks every theorem rests only on Lean's three standard axioms.
# Exit 1 on any failure. The TLA+ models have their own runner: tla/check.sh.
# Needs Lean 4.36.0 (LEAN_LAKE, or a release unpacked into ~/.local/lean). .lake/ is deleted on exit.
set -euo pipefail
cd "$(dirname "$0")"
trap 'rm -rf .lake' EXIT

lake_bin=${LEAN_LAKE:-}
if [[ -z "$lake_bin" ]]; then
  for d in "$HOME"/.local/lean/*/bin; do [[ -x "$d/lake" ]] && lake_bin="$d/lake"; done
fi
if [[ -z "$lake_bin" || ! -x "$lake_bin" ]]; then
  echo "formal: FAILED: no Lean toolchain (set LEAN_LAKE, or unpack a release into ~/.local/lean)" >&2
  exit 1
fi
PATH="$(dirname "$lake_bin"):$PATH"
export PATH
echo "== lean: $(lean --version)"

if grep -rnE '\bsorry\b|native_decide|^\s*axiom\b' GephiModel GephiModel.lean; then
  echo "formal: FAILED: sorry, native_decide or a new axiom in the sources" >&2
  exit 1
fi
if ! build=$("$lake_bin" build 2>&1); then
  echo "$build" | grep -E 'error' | head -20 >&2
  echo "formal: FAILED: lake build" >&2
  exit 1
fi
echo "$build" | tail -1

theorems=$(grep -h '^theorem' GephiModel/*.lean | awk '{print $2}' | sort)
listed=$(grep -oE '#print axioms GephiModel\.[A-Za-z0-9_]+' axioms.lean | sed 's/.*\.//' | sort)
if [[ "$theorems" != "$listed" ]]; then
  echo "formal: FAILED: axioms.lean does not list exactly the theorems in GephiModel/" >&2
  exit 1
fi
axioms=$("$lake_bin" env lean axioms.lean 2>&1)
bad=$(echo "$axioms" | grep -oE "depends on axioms: \[[^]]*\]" | sed 's/.*\[//; s/\]//' | tr ',' '\n' \
  | sed 's/ //g' | grep -vE '^(propext|Classical.choice|Quot.sound)$' || true)
if [[ -n "$bad" ]] || [[ $(echo "$axioms" | grep -c "axioms\|does not depend") -ne $(echo "$theorems" | wc -l) ]]; then
  echo "$axioms" >&2
  echo "formal: FAILED: unexpected axioms or an unchecked theorem: ${bad:-}" >&2
  exit 1
fi
echo "   $(echo "$theorems" | wc -l | tr -d ' ') theorems, standard axioms only"
echo "formal: ok"
