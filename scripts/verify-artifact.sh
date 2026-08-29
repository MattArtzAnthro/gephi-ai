#!/bin/bash
# Verify what actually ships, not what is on disk.
#
# The test suite reads the working tree. A release reads the built wheel. Everything that lives in
# the gap between them — packaging rules, excluded files, data files a local run has rewritten —
# is invisible to a green suite and visible only here.
#
# That gap is not hypothetical for this repo: 1.15.0 and 1.16.0 shipped one machine's probe
# verdicts to every user because caveats.json is rewritten by a local probe run and the wheel was
# built afterwards. Every test passed the whole time.
#
# Run before publishing. Exits non-zero and names the problem if the artifact is wrong.

set -euo pipefail
cd "$(dirname "$0")/.."

FAIL=0
say() { printf '  %s\n' "$1"; }
bad() { printf '  FAIL: %s\n' "$1"; FAIL=1; }

echo "Building the distributions..."
rm -rf mcp-server/dist
# Build BOTH. Checking only the wheel is how caveats.local.json reached PyPI in the
# 1.16.1 sdist: the exclude was set on the wheel target alone, the wheel verified clean,
# and the sdist shipped one machine's probe verdicts to every user. A release publishes
# both artifacts, so verification has to read both.
(cd mcp-server && uv build >/dev/null 2>&1)
WHEEL=$(ls mcp-server/dist/*.whl)
SDIST=$(ls mcp-server/dist/*.tar.gz)
say "built $(basename "$WHEEL")"
say "built $(basename "$SDIST")"

python3 - "$SDIST" <<'PYSDIST' || FAIL=1
import sys, tarfile
names = tarfile.open(sys.argv[1]).getnames()
ok = True
if any(n.endswith("caveats.local.json") for n in names):
    print("  FAIL: caveats.local.json is in the sdist — one machine's verdicts would ship to every user")
    ok = False
else:
    print("  no local probe overlay in the sdist")
if not any(n.endswith("caveats.json") and not n.endswith("caveats.local.json") for n in names):
    print("  FAIL: caveats.json is MISSING from the sdist")
    ok = False
else:
    print("  caveats.json is present in the sdist")
sys.exit(0 if ok else 1)
PYSDIST

echo
echo "Inspecting the artifact:"

python3 - "$WHEEL" <<'PY' || FAIL=1
import json, sys, zipfile

wheel = zipfile.ZipFile(sys.argv[1])
names = wheel.namelist()
ok = True

def check(condition, good, bad_msg):
    global ok
    print(f"  {good}" if condition else f"  FAIL: {bad_msg}")
    if not condition:
        ok = False

# The register must ship, or every caveat silently disappears.
register = next((n for n in names if n.endswith("caveats.json")
                 and not n.endswith("caveats.local.json")), None)
check(register is not None, "caveats.json is present", "caveats.json is MISSING from the wheel")

# Probe verdicts describe one install and must never be published as a claim about every install.
check(not any(n.endswith("caveats.local.json") for n in names),
      "no local probe overlay in the wheel",
      "caveats.local.json is in the wheel — one machine's verdicts would ship to every user")

if register:
    data = json.loads(wheel.read(register))
    stamped = [e["id"] for e in data["caveats"]
               if e["verification"].get("checked_on")
               or e["verification"]["status"] in {"reproduced", "not_reproduced"}]
    check(not stamped, "the shipped register carries no verdicts",
          f"the shipped register asserts verdicts for {stamped}")
    check("reproduced on this gephi" not in wheel.read(register).decode().lower(),
          "no caveat claims to have been reproduced on the reader's Gephi",
          "a caveat says 'Reproduced on this Gephi' — false on every machine but the prober's")

sys.exit(0 if ok else 1)
PY

echo
echo "Installing the artifact and exercising it:"
VENV=$(mktemp -d)/venv
python3 -m venv "$VENV" >/dev/null
"$VENV/bin/pip" install -q "$WHEEL" 2>/dev/null

"$VENV/bin/python" - <<'PY' || FAIL=1
import re, sys
from pathlib import Path

import gephi_mcp
import stats_integrity

ok = True

def check(condition, good, bad_msg):
    global ok
    print(f"  {good}" if condition else f"  FAIL: {bad_msg}")
    if not condition:
        ok = False

tools = {t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}
check(bool(tools), f"{len(tools)} tools register from the installed package",
      "no tools registered from the installed package")

entries = stats_integrity.load_register()
check(bool(entries), f"the register loads from the install ({len(entries)} entries)",
      "the register does not load from the installed package")

# A fresh install has run no probes, so it must claim nothing about the user's Gephi.
asserted = [e["id"] for e in entries
            if e["verification"]["status"] in {"reproduced", "not_reproduced"}]
check(not asserted, "a fresh install asserts no verdict about the user's Gephi",
      f"a fresh install already asserts {asserted}")

check(not stats_integrity.local_overlay_path().exists(),
      "a fresh install carries no probe overlay",
      "a fresh install already has a probe overlay")

sys.exit(0 if ok else 1)
PY

echo
echo "Checking the documented tool count against the artifact:"
COUNT=$("$VENV/bin/python" -c "import gephi_mcp; print(len({t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}))")
for f in README.md CLAUDE.md AGENTS.md GEMINI.md mcp-server/README.md plugins/claude-code/skills/gephi/SKILL.md plugins/gephi-network-analysis/skills/gephi/SKILL.md mcpb/manifest.json; do
  if grep -qE "[0-9]+ (tools|Gephi tools|Gephi MCP tools|MCP tools)" "$f" 2>/dev/null; then
    if grep -qE "\b$COUNT (tools|Gephi tools|Gephi MCP tools|MCP tools)" "$f"; then
      say "$f agrees ($COUNT)"
    else
      bad "$f does not say $COUNT tools"
    fi
  fi
done

rm -rf "$(dirname "$VENV")"
echo
if [ "$FAIL" -ne 0 ]; then
  echo "ARTIFACT VERIFICATION FAILED — do not publish."
  rm -f "$(git rev-parse --show-toplevel)/.artifact-verified"
  exit 1
fi

# Stamp the marker the publish gate looks for. Nothing else creates it, so without this the
# gate is a nag that anyone clears by hand, which teaches people to clear it reflexively.
# Written only on success, and removed above on failure, so its presence means something.
touch "$(git rev-parse --show-toplevel)/.artifact-verified"

echo "Artifact verification passed."
