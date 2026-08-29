#!/bin/bash
# Bump gephi-ai version strings across all three tracks from one command.
#
# A release touches ~13 version strings in 11 files across 3 independent tracks
# (server / java / plugin). Doing it by hand is how they drift — a lagging
# .mcp.json pin or a stale latest.json is the exact class of bug this prevents.
#
# Usage:
#   scripts/bump-version.sh [--server X] [--java Y] [--plugin Z]
# Any track you omit is left unchanged. Reads the current version from each
# track's source of truth, replaces that exact string everywhere it appears, then
# verifies consistency. Does NOT touch CHANGELOG (prose, written by hand) or build
# anything — run tests/build/publish separately (see RELEASING.md).
#
# Examples:
#   scripts/bump-version.sh --server 1.9.22            # server-only release
#   scripts/bump-version.sh --server 1.9.22 --java 1.2.16 --plugin 1.9.26
set -euo pipefail
cd "$(dirname "$0")/.."

# Portable in-place sed (BSD/macOS needs an empty -i arg; GNU/Linux does not).
sedi() {
  if sed --version >/dev/null 2>&1; then sed -i "$@"; else sed -i '' "$@"; fi
}

NEW_SERVER="" NEW_JAVA="" NEW_PLUGIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --server) NEW_SERVER="$2"; shift 2 ;;
    --java)   NEW_JAVA="$2"; shift 2 ;;
    --plugin) NEW_PLUGIN="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Current versions from each track's source of truth.
OLD_SERVER=$(grep -m1 '^version = ' mcp-server/pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
OLD_JAVA=$(grep -m1 '<version>' gephi-ai-plugin/pom.xml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
OLD_PLUGIN=$(python3 -c "import json;print(json.load(open('claude-plugin/.claude-plugin/plugin.json'))['version'])")

jset() { # jset <file> <key> <value>  (safe JSON field write)
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
f, k, v = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(f)); d[k] = v
json.dump(d, open(f, "w"), indent=2); open(f, "a").write("\n")
PY
}

if [ -n "$NEW_SERVER" ] && [ "$NEW_SERVER" != "$OLD_SERVER" ]; then
  echo "server  $OLD_SERVER -> $NEW_SERVER"
  sedi "s/^version = \"$OLD_SERVER\"/version = \"$NEW_SERVER\"/" mcp-server/pyproject.toml
  sedi "s/gephi-mcp==$OLD_SERVER/gephi-mcp==$NEW_SERVER/" claude-plugin/.mcp.json
  jset mcpb/manifest.json version "$NEW_SERVER"
  jset latest.json server "$NEW_SERVER"
fi

if [ -n "$NEW_JAVA" ] && [ "$NEW_JAVA" != "$OLD_JAVA" ]; then
  echo "java    $OLD_JAVA -> $NEW_JAVA"
  sedi "s|<version>$OLD_JAVA</version>|<version>$NEW_JAVA</version>|" gephi-ai-plugin/pom.xml
  sedi "s/gephi-ai-$OLD_JAVA\.nbm/gephi-ai-$NEW_JAVA.nbm/g" README.md
  sedi "s/Gephi AI Plugin ($OLD_JAVA+)/Gephi AI Plugin ($NEW_JAVA+)/" claude-plugin/skills/gephi/SKILL.md
  jset latest.json nbm "$NEW_JAVA"
fi

if [ -n "$NEW_PLUGIN" ] && [ "$NEW_PLUGIN" != "$OLD_PLUGIN" ]; then
  echo "plugin  $OLD_PLUGIN -> $NEW_PLUGIN"
  jset claude-plugin/.claude-plugin/plugin.json version "$NEW_PLUGIN"
  sedi "s/version: \"$OLD_PLUGIN\"/version: \"$NEW_PLUGIN\"/" claude-plugin/skills/gephi/SKILL.md
  sedi "s/Skill version $OLD_PLUGIN/Skill version $NEW_PLUGIN/" claude-plugin/skills/gephi/SKILL.md
  jset latest.json plugin "$NEW_PLUGIN"
  # marketplace.json carries the plugin version in TWO fields
  python3 - "$NEW_PLUGIN" <<'PY'
import json, sys
p = ".claude-plugin/marketplace.json"
d = json.load(open(p))
d["version"] = sys.argv[1]
d["plugins"][0]["version"] = sys.argv[1]
json.dump(d, open(p, "w"), indent=2); open(p, "a").write("\n")
PY
fi

# ---- verify every surface agrees ----
S=$(grep -m1 '^version = ' mcp-server/pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
J=$(grep -m1 '<version>' gephi-ai-plugin/pom.xml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
P=$(python3 -c "import json;print(json.load(open('claude-plugin/.claude-plugin/plugin.json'))['version'])")
fail=0
check() { [ "$2" = "$3" ] || { echo "  MISMATCH $1: '$2' != '$3'"; fail=1; }; }
echo "--- verify ---"
check ".mcp.json pin"      "$(python3 -c "import json;print(json.load(open('claude-plugin/.mcp.json'))['mcpServers']['gephi-mcp']['args'][1].split('==')[1])")" "$S"
check "mcpb manifest"      "$(python3 -c "import json;print(json.load(open('mcpb/manifest.json'))['version'])")" "$S"
check "latest.json server" "$(python3 -c "import json;print(json.load(open('latest.json'))['server'])")" "$S"
# /health reads its version from the module manifest, which nbm-maven-plugin generates from
# the POM, so there is nothing to sweep here. What must stay true is that nobody reintroduces
# a literal — that is the drift this check used to chase.
if grep -qE '"version", "[0-9]+\.[0-9]+\.[0-9]+"' gephi-ai-plugin/src/main/java/org/gephi/plugins/mcp/api/GephiAPIServer.java; then
  echo "  HARDCODED version in GephiAPIServer.java; /health should call moduleVersion()"
  fail=1
else
  echo "  OK  health version is read from the module manifest, not hardcoded"
fi
check "README nbm"         "$(grep -oE 'gephi-ai-[0-9.]+\.nbm' README.md | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$J"
check "latest.json nbm"    "$(python3 -c "import json;print(json.load(open('latest.json'))['nbm'])")" "$J"
check "SKILL version"      "$(grep -m1 'version:' claude-plugin/skills/gephi/SKILL.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$P"
check "latest.json plugin" "$(python3 -c "import json;print(json.load(open('latest.json'))['plugin'])")" "$P"
check "marketplace.json"   "$(python3 -c "import json;print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])")" "$P"
[ "$fail" = 0 ] && echo "  OK  server=$S java=$J plugin=$P — all surfaces consistent" || { echo "  FAILED"; exit 1; }
echo "Next: update CHANGELOG, run tests, build + publish (see RELEASING.md)."
