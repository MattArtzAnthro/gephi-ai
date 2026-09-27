#!/bin/bash
# Warn about fix commits that change no test.
#
#   scripts/check-fix-tests.sh <base> [<head>]
#
# Every commit in base..head whose subject starts with "fix" (fix: or fix(scope):)
# should add or change a test that fails without the fix. For each one that touches
# no test file, this prints a warning; in GitHub Actions it is an annotation on the
# pull request. It warns and does not fail: some fixes (a typo in a message, a
# packaging change) have nothing a test can pin down, and the warning is a prompt to
# say so in review.
set -euo pipefail

base="${1:?usage: check-fix-tests.sh <base> [<head>]}"
head="${2:-HEAD}"
tests='^(gephi-ai-plugin/src/test/|mcp-server/tests/|plugins/[^/]+/tests/)'

warned=0
while read -r sha subject; do
  [ -n "$sha" ] || continue
  if ! git diff-tree --no-commit-id --name-only -r "$sha" | grep -Eq "$tests"; then
    msg="fix commit ${sha:0:7} changes no test: $subject"
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
      echo "::warning title=Fix without a test::$msg"
    else
      echo "WARNING: $msg"
    fi
    warned=$((warned + 1))
  fi
done < <(git log --no-merges --format='%H %s' "$base..$head" | grep -E '^[0-9a-f]+ fix(\(|:)' || true)

echo "$warned fix commit(s) without a test change."
