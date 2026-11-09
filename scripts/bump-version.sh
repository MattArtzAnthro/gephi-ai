#!/bin/bash
# Bump gephi-ai version strings across all three tracks from one command.
#
# A release touches ~13 version strings in 11 files across 3 independent tracks
# (server / java / plugin). Doing it by hand is how they drift — a lagging
# .mcp.json pin or a stale latest.json is the exact class of bug this prevents.
#
# Usage:
#   scripts/bump-version.sh [--server X] [--java Y] [--plugin Z] [--nbm-file PATH]
# Any track you omit is left unchanged. Reads the current version from each
# track's source of truth, replaces that exact string everywhere it appears, then
# verifies consistency. Does NOT touch CHANGELOG (prose, written by hand) or build
# anything — run tests/build/publish separately (see RELEASING.md).
#
# latest.json also carries nbm_sha256, the SHA-256 of the built .nbm, which the installers
# check the download against. It is written from --nbm-file, or from ./gephi-ai-<java>.nbm
# when that file exists. A java bump drops the old digest, so run the script again with
# --nbm-file once the .nbm is built (RELEASING.md step 3).
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

NEW_SERVER="" NEW_JAVA="" NEW_PLUGIN="" NBM_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --server) NEW_SERVER="$2"; shift 2 ;;
    --java)   NEW_JAVA="$2"; shift 2 ;;
    --plugin) NEW_PLUGIN="$2"; shift 2 ;;
    --nbm-file) NBM_FILE="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Current versions from each track's source of truth.
OLD_SERVER=$(grep -m1 '^version = ' mcp-server/pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
OLD_JAVA=$(grep -m1 '<version>' gephi-ai-plugin/pom.xml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
OLD_PLUGIN=$(python3 -c "import json;print(json.load(open('plugins/claude-code/.claude-plugin/plugin.json'))['version'])")

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
  sedi "s/gephi-ai==$OLD_SERVER/gephi-ai==$NEW_SERVER/" plugins/claude-code/.mcp.json
  sedi "s/gephi-ai==$OLD_SERVER/gephi-ai==$NEW_SERVER/" plugins/gephi-network-analysis/.mcp.json
  jset mcpb/manifest.json version "$NEW_SERVER"
  sedi "s/gephi-ai==$OLD_SERVER/gephi-ai==$NEW_SERVER/" mcpb/pyproject.toml
  sedi "s/^version = \"$OLD_SERVER\"/version = \"$NEW_SERVER\"/" mcpb/pyproject.toml
  jset latest.json server "$NEW_SERVER"
fi

if [ -n "$NEW_JAVA" ] && [ "$NEW_JAVA" != "$OLD_JAVA" ]; then
  echo "java    $OLD_JAVA -> $NEW_JAVA"
  sedi "s|<version>$OLD_JAVA</version>|<version>$NEW_JAVA</version>|" gephi-ai-plugin/pom.xml
  sedi "s/gephi-ai-$OLD_JAVA\.nbm/gephi-ai-$NEW_JAVA.nbm/g" README.md
  # Any version, not just OLD_JAVA: matching only the current one let this line fall behind once
  # and then never match again.
  sedi -E "s/Gephi AI Plugin \([0-9]+\.[0-9]+\.[0-9]+\+\)/Gephi AI Plugin ($NEW_JAVA+)/" plugins/claude-code/skills/gephi/SKILL.md
  jset latest.json nbm "$NEW_JAVA"
  # The old digest belongs to the old .nbm; never leave it beside the new version.
  python3 - <<'PY'
import json
d = json.load(open("latest.json")); d.pop("nbm_sha256", None)
json.dump(d, open("latest.json", "w"), indent=2); open("latest.json", "a").write("\n")
PY
fi
sha256_of() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }
CUR_JAVA=$(grep -m1 '<version>' gephi-ai-plugin/pom.xml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
[ -z "$NBM_FILE" ] && [ -f "gephi-ai-$CUR_JAVA.nbm" ] && NBM_FILE="gephi-ai-$CUR_JAVA.nbm"
if [ -n "$NBM_FILE" ]; then
  [ -f "$NBM_FILE" ] || { echo "no such file: $NBM_FILE" >&2; exit 2; }
  jset latest.json nbm_sha256 "$(sha256_of "$NBM_FILE")"
  echo "nbm_sha256 from $NBM_FILE"
fi
# The Gephi the plugin is built against is the oldest Gephi that will install it; the health
# check reads it before advising a plugin update.
GEPHI_MIN=$(grep -m1 -oE '<gephi.version>[^<]+' gephi-ai-plugin/pom.xml | sed 's/<gephi.version>//')
[ -n "$NEW_JAVA" ] && jset latest.json nbm_needs_gephi "$GEPHI_MIN"

if [ -n "$NEW_PLUGIN" ] && [ "$NEW_PLUGIN" != "$OLD_PLUGIN" ]; then
  echo "plugin  $OLD_PLUGIN -> $NEW_PLUGIN"
  jset plugins/claude-code/.claude-plugin/plugin.json version "$NEW_PLUGIN"
  jset plugins/gephi-network-analysis/.codex-plugin/plugin.json version "$NEW_PLUGIN"
  sedi "s/version: \"$OLD_PLUGIN\"/version: \"$NEW_PLUGIN\"/" plugins/claude-code/skills/gephi/SKILL.md
  sedi "s/Skill version $OLD_PLUGIN/Skill version $NEW_PLUGIN/" plugins/claude-code/skills/gephi/SKILL.md
  sedi "s/version: \"$OLD_PLUGIN\"/version: \"$NEW_PLUGIN\"/" plugins/gephi-network-analysis/skills/gephi/SKILL.md
  sedi "s/Skill version $OLD_PLUGIN/Skill version $NEW_PLUGIN/" plugins/gephi-network-analysis/skills/gephi/SKILL.md
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
P=$(python3 -c "import json;print(json.load(open('plugins/claude-code/.claude-plugin/plugin.json'))['version'])")
fail=0
check() { [ "$2" = "$3" ] || { echo "  MISMATCH $1: '$2' != '$3'"; fail=1; }; }
echo "--- verify ---"
check ".mcp.json pin"      "$(python3 -c "import json;print(json.load(open('plugins/claude-code/.mcp.json'))['mcpServers']['gephi-ai']['args'][1].split('==')[1])")" "$S"
check "Codex .mcp.json pin" "$(python3 -c "import json;print(json.load(open('plugins/gephi-network-analysis/.mcp.json'))['mcpServers']['gephi-ai']['args'][1].split('==')[1])")" "$S"
check "mcpb manifest"      "$(python3 -c "import json;print(json.load(open('mcpb/manifest.json'))['version'])")" "$S"
check "mcpb pyproject pin" "$(grep -oE 'gephi-ai==[0-9.]+' mcpb/pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$S"
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
# The installers refuse to install the plugin without a checksum, so a release needs one.
LJ_SHA=$(python3 -c "import json;print(json.load(open('latest.json')).get('nbm_sha256', ''))")
if [ -n "$NBM_FILE" ]; then
  check "latest.json nbm_sha256" "$LJ_SHA" "$(sha256_of "$NBM_FILE")"
elif [ -z "$LJ_SHA" ]; then
  echo "  WARNING latest.json has no nbm_sha256: build the .nbm, then run  scripts/bump-version.sh --nbm-file gephi-ai-$J.nbm"
elif ! printf '%s' "$LJ_SHA" | grep -qE '^[0-9a-f]{64}$'; then
  echo "  MISMATCH latest.json nbm_sha256 is not a 64-digit hex digest"; fail=1
fi
check "SKILL plugin minimum" "$(grep -oE 'Gephi AI Plugin \([0-9.]+\+\)' plugins/claude-code/skills/gephi/SKILL.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$J"
check "latest.json nbm_needs_gephi" "$(python3 -c "import json;print(json.load(open('latest.json')).get('nbm_needs_gephi', ''))")" "$GEPHI_MIN"
check "SKILL version"      "$(grep -m1 'version:' plugins/claude-code/skills/gephi/SKILL.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$P"
check "Codex manifest"     "$(python3 -c "import json;print(json.load(open('plugins/gephi-network-analysis/.codex-plugin/plugin.json'))['version'])")" "$P"
check "Codex SKILL"        "$(grep -m1 'version:' plugins/gephi-network-analysis/skills/gephi/SKILL.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "$P"
check "latest.json plugin" "$(python3 -c "import json;print(json.load(open('latest.json'))['plugin'])")" "$P"
check "marketplace.json"   "$(python3 -c "import json;print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])")" "$P"
if [ "$fail" = 0 ]; then
  echo "  OK  server=$S java=$J plugin=$P — all surfaces consistent"
else
  echo "  FAILED"
  exit 1
fi
echo "Next: update CHANGELOG, run tests, build + publish (see RELEASING.md)."
