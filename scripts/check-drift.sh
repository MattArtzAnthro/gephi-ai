#!/bin/bash
# Check gephi-ai's DISTRIBUTION state for drift: uncommitted/unpushed work in the
# dev repo, a PyPI publish gap behind the pinned version (the "dead on install"
# hazard), and stale marketplace clones (host Claude Code, and Cowork's separate
# private plugin store, if present on this machine).
#
# This is the complement to gephi_health_check's own "update" field: that checks
# whether a RUNNING install (server/plugin/Gephi .nbm) is behind latest.json.
# This script checks whether the REPO ITSELF and its distribution channels
# (git remote, PyPI, marketplace clones) are in sync with each other. Report-only
# by default — never commits, pushes, or publishes anything.
#
# Usage:
#   scripts/check-drift.sh              # report only
#   scripts/check-drift.sh --fix-clones # also `git pull` any stale marketplace
#                                        # clones found (host + Cowork) to match
#                                        # origin/main. Never touches git commit/
#                                        # push/publish — those stay manual.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

FIX_CLONES=0
[ "${1:-}" = "--fix-clones" ] && FIX_CLONES=1

ISSUES=0
note() { echo "  - $1"; ISSUES=$((ISSUES + 1)); }
ok()   { echo "  OK  $1"; }

echo "=== gephi-ai drift check ==="
echo ""

# ---- 1. dev repo: uncommitted or unpushed work ----
echo "-- dev repo --"
DIRTY="$(git status --porcelain)"
if [ -n "$DIRTY" ]; then
  note "uncommitted changes present:"
  echo "$DIRTY" | sed 's/^/      /'
else
  ok "working tree clean"
fi

git fetch origin --quiet 2>/dev/null
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then
  note "$AHEAD commit(s) not pushed to origin/main"
elif [ "$AHEAD" = "?" ]; then
  note "could not compare against origin/main (no network / no remote?)"
else
  ok "HEAD matches origin/main (nothing unpushed)"
fi
if [ "$BEHIND" != "0" ] && [ "$BEHIND" != "?" ]; then
  note "local is $BEHIND commit(s) BEHIND origin/main — pull before continuing"
fi
echo ""

# ---- 2. PyPI vs the pinned version (the "dead on install" hazard) ----
echo "-- PyPI publish gap --"
PINNED=$(python3 -c "import json;print(json.load(open('claude-plugin/.mcp.json'))['mcpServers']['gephi-mcp']['args'][1].split('==')[1])" 2>/dev/null)
if [ -z "$PINNED" ]; then
  note "could not read pinned version from claude-plugin/.mcp.json"
else
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://pypi.org/pypi/gephi-mcp/$PINNED/json" 2>/dev/null)
  if [ "$HTTP_CODE" = "200" ]; then
    ok "pinned gephi-mcp==$PINNED is published on PyPI"
  else
    note "DEAD ON INSTALL: .mcp.json pins gephi-mcp==$PINNED but PyPI does not have it yet (HTTP $HTTP_CODE) — publish before anyone reinstalls/updates"
  fi
fi
echo ""

# ---- 3. marketplace clones (host Claude Code, plus Cowork's separate store) ----
echo "-- marketplace clones --"
ORIGIN_HEAD=$(git rev-parse origin/main 2>/dev/null)

check_clone() {  # check_clone <label> <path>
  local label="$1" path="$2"
  [ -d "$path/.git" ] || return 0
  local local_head
  local_head=$(git -C "$path" rev-parse HEAD 2>/dev/null)
  if [ "$local_head" = "$ORIGIN_HEAD" ]; then
    ok "$label clone is current ($local_head)"
  else
    note "$label clone is STALE ($local_head vs origin $ORIGIN_HEAD)"
    if [ "$FIX_CLONES" = "1" ]; then
      echo "      fixing: git pull in $path"
      git -C "$path" pull --quiet 2>&1 | sed 's/^/      /'
    fi
  fi
}

check_clone "host" "$HOME/.claude/plugins/marketplaces/gephi-ai"

LATEST_PLUGIN=$(python3 -c "import json;print(json.load(open('latest.json'))['plugin'])" 2>/dev/null)

while IFS= read -r -d '' cowork_mp; do
  # label with the Cowork session id (two dirs up from marketplaces/gephi-ai:
  # .../<session-uuid>/cowork_plugins/marketplaces/gephi-ai) — avoid xargs here,
  # it re-splits on the space in "Application Support" and mangles the path.
  session_dir=$(dirname "$(dirname "$(dirname "$cowork_mp")")")
  session_id=$(basename "$session_dir")
  check_clone "Cowork ($session_id)" "$cowork_mp"

  # Cowork loads plugins from its OWN cache + installed_plugins.json, separate
  # from the marketplace clone git history — a synced clone does not mean
  # Cowork will actually pick it up. Check that manifest directly too.
  cowork_plugins_dir=$(dirname "$(dirname "$cowork_mp")")
  manifest="$cowork_plugins_dir/installed_plugins.json"
  if [ -f "$manifest" ] && [ -n "$LATEST_PLUGIN" ]; then
    installed=$(python3 -c "
import json
try:
    d = json.load(open('$manifest'))
    print(d['plugins']['gephi-network-analysis@gephi-ai'][0]['version'])
except Exception:
    print('')
" 2>/dev/null)
    if [ -z "$installed" ]; then
      : # plugin not installed in this Cowork session — nothing to check
    elif [ "$installed" = "$LATEST_PLUGIN" ]; then
      ok "Cowork ($session_id) installed_plugins.json is current ($installed)"
    else
      note "Cowork ($session_id) installed_plugins.json is STALE ($installed vs $LATEST_PLUGIN) — cache dir + manifest need updating, not just the clone"
    fi
  fi
done < <(find "$HOME/Library/Application Support/Claude/local-agent-mode-sessions" \
  -maxdepth 6 -type d -iname "gephi-ai" -path "*marketplaces*" -print0 2>/dev/null)
echo ""

echo "=== $ISSUES issue(s) found ==="
[ "$ISSUES" -gt 0 ] && exit 1
exit 0
