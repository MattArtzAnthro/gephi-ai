#!/bin/bash
# Build the one-click Claude Desktop bundle. The host installs Python and gephi-ai itself
# (MCPB server.type "uv"), so nothing is vendored here. The build locks the bundle's
# dependencies into mcpb/uv.lock, which ships in the bundle, so every install gets the same
# versions of gephi-ai's dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(python3 -c "import json; print(json.load(open('mcpb/manifest.json'))['version'])")}"
grep -q "\"gephi-ai==${VERSION}\"" mcpb/pyproject.toml || { echo "mcpb/pyproject.toml does not pin gephi-ai==${VERSION}"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "uv is not on PATH; the build needs it to lock the bundle's dependencies (https://docs.astral.sh/uv/)"; exit 1; }
uv lock --directory mcpb || { echo "uv could not lock the bundle's dependencies. If gephi-ai==${VERSION} was just published, PyPI cannot resolve it yet: wait until pip can install it, then build again."; exit 1; }
mkdir -p dist
npx -y @anthropic-ai/mcpb pack mcpb "dist/gephi-ai-${VERSION}.mcpb"
echo "Built dist/gephi-ai-${VERSION}.mcpb"
