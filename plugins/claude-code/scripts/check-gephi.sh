#!/usr/bin/env bash
# Check if Gephi Desktop is running and the MCP plugin HTTP API is accessible.
# Used as a PreToolUse hook to catch connection issues before graph operations.

BASE_URL="${GEPHI_API_URL:-http://127.0.0.1:8080}"
STATUS=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "${BASE_URL}/health" 2>/dev/null)

if [ "$STATUS" != "200" ]; then
  # Exit code 2 (with the reason on stderr) is what tells Claude Code to BLOCK
  # the tool call. Printing to stdout and exiting 0 would let the call proceed.
  if [ "$STATUS" = "000" ] || [ -z "$STATUS" ]; then
    echo "Gephi Desktop is not running or the MCP plugin is not responding at ${BASE_URL}. Start Gephi with the MCP plugin installed before performing graph operations." >&2
  else
    echo "Something other than the Gephi plugin answered at ${BASE_URL} (HTTP ${STATUS}). If Gephi's API is on another port, set GEPHI_API_URL to it, for example http://127.0.0.1:8081." >&2
  fi
  exit 2
fi

exit 0
