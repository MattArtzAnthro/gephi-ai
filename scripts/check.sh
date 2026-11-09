#!/usr/bin/env bash
# The repo quality gate: offline tests, the coverage floor, and lint. The global
# pre-commit hook runs this before every commit, so keep it offline and quick.
# Live tests stay opt-in and never run here. Bypass one commit with --no-verify.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
cd "$(git rev-parse --show-toplevel)"
COV_DIR="${TMPDIR:-/tmp}/check-$(basename "$PWD")"
mkdir -p "$COV_DIR"
export COVERAGE_FILE="$COV_DIR/.coverage"

RUFF=ruff
[ -x mcp-server/.venv/bin/ruff ] && RUFF="$PWD/mcp-server/.venv/bin/ruff"
(cd mcp-server && "$RUFF" check . ../plugins/gephi-network-analysis/tests)
# Incremental, so a second run takes well under a second. The viewer is named for the reason
# given in ci.yml.
(cd mcp-server && .venv/bin/mypy ./*.py gephi_mcp_viewer)
(cd mcp-server && .venv/bin/bandit -q -c pyproject.toml -r .)
(cd mcp-server && PYTHONPATH=. .venv/bin/python -m pytest -q -p no:cacheprovider --cov)
bash plugins/claude-code/scripts/test-check-gephi.sh >/dev/null
# The same script and workflow lint CI runs, so a push does not go red on a lint
# that never ran here. Skipped with a warning on a Mac without the tool.
if command -v shellcheck >/dev/null; then
  shellcheck install.sh scripts/*.sh plugins/claude-code/scripts/*.sh
else
  echo "check.sh: shellcheck not installed; CI will run it" >&2
fi
if command -v actionlint >/dev/null; then actionlint; else echo "check.sh: actionlint not installed; CI will run it" >&2; fi
mcp-server/.venv/bin/python -m unittest discover -s plugins/gephi-network-analysis/tests >/dev/null 2>&1 \
  || mcp-server/.venv/bin/python -m unittest discover -s plugins/gephi-network-analysis/tests
# The Java build takes a minute, so it runs only when plugin sources are staged
# (CI runs it on every push regardless).
if git diff --cached --name-only | grep -q '^gephi-ai-plugin/'; then
  (cd gephi-ai-plugin && JAVA_HOME=$(/usr/libexec/java_home -v 21) \
     mvn -B -q -o -Dmaven.antrun.skip=true test)
fi
