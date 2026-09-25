#!/bin/bash
# Build the one-click Claude Desktop bundle. The host installs Python and gephi-ai itself
# (MCPB server.type "uv"), so nothing is vendored here.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(python3 -c "import json; print(json.load(open('mcpb/manifest.json'))['version'])")}"
grep -q "\"gephi-ai==${VERSION}\"" mcpb/pyproject.toml || { echo "mcpb/pyproject.toml does not pin gephi-ai==${VERSION}"; exit 1; }
mkdir -p dist
npx -y @anthropic-ai/mcpb pack mcpb "dist/gephi-ai-${VERSION}.mcpb"
echo "Built dist/gephi-ai-${VERSION}.mcpb"
