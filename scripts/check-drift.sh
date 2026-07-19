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

# ---- 3. GitHub Releases vs latest.json (the "told to update, nothing to download" gap) ----
#
# latest.json is what gephi_health_check reads to tell a running install it is
# behind. If it advertises a version with no matching GitHub Release, users get
# told to update and land on a Releases page that does not have the file. Both
# v1.11.0 and Java 1.2.16 shipped to main without a release before this check
# existed, so the advertised nbm sat two versions ahead of the newest release.
echo "-- GitHub Releases --"
LATEST_SERVER=$(python3 -c "import json;print(json.load(open('latest.json'))['server'])" 2>/dev/null)
LATEST_NBM=$(python3 -c "import json;print(json.load(open('latest.json'))['nbm'])" 2>/dev/null)
if [ -z "$LATEST_SERVER" ] || [ -z "$LATEST_NBM" ]; then
  note "could not read server/nbm versions from latest.json"
elif ! command -v gh >/dev/null 2>&1; then
  note "gh not installed — cannot verify releases (skipping)"
else
  # Release tags follow the server version: v<server>.
  if gh release view "v$LATEST_SERVER" >/dev/null 2>&1; then
    ok "latest.json server $LATEST_SERVER has release v$LATEST_SERVER"
    # The .nbm is the primary download path in README; a release without it
    # attached sends people to the repo-root fallback instead.
    if gh api "repos/{owner}/{repo}/releases/tags/v$LATEST_SERVER" \
         --jq '.assets[].name' 2>/dev/null | grep -q "gephi-mcp-$LATEST_NBM.nbm"; then
      ok "release v$LATEST_SERVER has gephi-mcp-$LATEST_NBM.nbm attached"
    else
      note "release v$LATEST_SERVER is missing asset gephi-mcp-$LATEST_NBM.nbm — README points users at the Releases page for it"
    fi
  else
    note "latest.json advertises server $LATEST_SERVER but there is no release v$LATEST_SERVER — health_check will tell users to update toward a download that does not exist (fix: gh release create v$LATEST_SERVER gephi-ai-$LATEST_SERVER.mcpb gephi-mcp-$LATEST_NBM.nbm ...)"
  fi
fi
echo ""

# ---- 4. repo-root .nbm vs the built plugin version ----
#
# README offers the repo root as a download fallback ("also available at the root
# of this repository"). It went two releases stale (1.2.15 while README said
# 1.2.17) because nothing checked it.
echo "-- repo-root .nbm --"
POM_VERSION=$(grep -m1 '<version>' gephi-mcp-plugin/pom.xml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
ROOT_NBM_COUNT=$(ls -1 gephi-mcp-*.nbm 2>/dev/null | wc -l | tr -d ' ')
if [ -z "$POM_VERSION" ]; then
  note "could not read version from gephi-mcp-plugin/pom.xml"
elif [ "$ROOT_NBM_COUNT" = "0" ]; then
  note "no gephi-mcp-*.nbm at repo root, but README offers it as a download fallback"
elif [ "$ROOT_NBM_COUNT" != "1" ]; then
  note "$ROOT_NBM_COUNT .nbm files at repo root — there should be exactly one (the current build):"
  ls -1 gephi-mcp-*.nbm | sed 's/^/      /'
elif [ -f "gephi-mcp-$POM_VERSION.nbm" ]; then
  ok "repo-root gephi-mcp-$POM_VERSION.nbm matches pom.xml"
else
  note "repo-root $(ls -1 gephi-mcp-*.nbm) is stale — pom.xml is at $POM_VERSION (fix: mvn -f gephi-mcp-plugin/pom.xml clean package && cp gephi-mcp-plugin/target/gephi-mcp-$POM_VERSION.nbm . && git rm <old>)"
fi
echo ""

# ---- 5. marketplace clones (host Claude Code, plus Cowork's separate store) ----
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

LATEST_PLUGIN=$(python3 -c "import json;print(json.load(open('latest.json'))['plugin'])" 2>/dev/null)

# A synced marketplace clone does NOT mean the plugin actually loaded is current:
# Claude installs from the clone into a versioned cache and pins the version in
# installed_plugins.json, and loads from THAT. Applies to the host exactly as it
# does to Cowork — on 2026-07-19 the host clone was current while the host
# manifest still sat at 1.9.29 against a released 1.9.31, and this script
# reported clean because it only looked at the clone.
check_manifest() {  # check_manifest <label> <installed_plugins.json path>
  local label="$1" manifest="$2"
  [ -f "$manifest" ] || return 0
  [ -n "$LATEST_PLUGIN" ] || return 0
  local installed
  installed=$(python3 -c "
import json
try:
    d = json.load(open('$manifest'))
    print(d['plugins']['gephi-network-analysis@gephi-ai'][0]['version'])
except Exception:
    print('')
" 2>/dev/null)
  if [ -z "$installed" ]; then
    : # plugin not installed here — nothing to check
  elif [ "$installed" = "$LATEST_PLUGIN" ]; then
    ok "$label installed_plugins.json is current ($installed)"
  else
    note "$label installed_plugins.json is STALE ($installed vs $LATEST_PLUGIN) — run: claude plugin marketplace update gephi-ai && claude plugin update gephi-network-analysis@gephi-ai"
  fi
}

check_clone    "host" "$HOME/.claude/plugins/marketplaces/gephi-ai"
check_manifest "host" "$HOME/.claude/plugins/installed_plugins.json"

while IFS= read -r -d '' cowork_mp; do
  # label with the Cowork session id (two dirs up from marketplaces/gephi-ai:
  # .../<session-uuid>/cowork_plugins/marketplaces/gephi-ai) — avoid xargs here,
  # it re-splits on the space in "Application Support" and mangles the path.
  session_dir=$(dirname "$(dirname "$(dirname "$cowork_mp")")")
  session_id=$(basename "$session_dir")
  check_clone "Cowork ($session_id)" "$cowork_mp"

  # Cowork loads from its OWN cache + installed_plugins.json, separate from the
  # marketplace clone's git history — check that manifest directly too.
  cowork_plugins_dir=$(dirname "$(dirname "$cowork_mp")")
  check_manifest "Cowork ($session_id)" "$cowork_plugins_dir/installed_plugins.json"
done < <(find "$HOME/Library/Application Support/Claude/local-agent-mode-sessions" \
  -maxdepth 6 -type d -iname "gephi-ai" -path "*marketplaces*" -print0 2>/dev/null)
echo ""

echo "=== $ISSUES issue(s) found ==="
[ "$ISSUES" -gt 0 ] && exit 1
exit 0
