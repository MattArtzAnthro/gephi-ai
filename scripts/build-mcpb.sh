#!/bin/bash
# Build the one-click Claude Desktop bundle (gephi-ai.mcpb).
# Usage: scripts/build-mcpb.sh [version]   (default: version from mcpb/manifest.json)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(python3 -c "import json; print(json.load(open('mcpb/manifest.json'))['version'])")}"
echo "Bundling gephi-mcp==${VERSION} from PyPI"
rm -rf mcpb/server/lib
python3 -m pip install --quiet --target mcpb/server/lib "gephi-mcp==${VERSION}"
npx -y @anthropic-ai/mcpb pack mcpb "gephi-ai-${VERSION}.mcpb"
echo "Built gephi-ai-${VERSION}.mcpb"
