#!/usr/bin/env bash
# Check if Gephi Desktop is running and the MCP plugin HTTP API is accessible.
# Used as a PreToolUse hook to catch connection issues before graph operations.

STATUS=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 http://127.0.0.1:8080/health 2>/dev/null)

if [ "$STATUS" != "200" ]; then
  echo "BLOCK: Gephi Desktop is not running or the MCP plugin is not responding. Please start Gephi with the MCP plugin installed before performing graph operations."
fi
