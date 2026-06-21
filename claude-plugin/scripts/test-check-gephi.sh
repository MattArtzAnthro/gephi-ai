#!/usr/bin/env bash
# Test for check-gephi.sh: it must BLOCK (exit 2) when the API is unreachable
# and ALLOW (exit 0) when /health returns 200. Run: bash test-check-gephi.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/check-gephi.sh"
fail=0

# 1) API down -> exit 2 (nothing listening on this port)
GEPHI_API_URL="http://127.0.0.1:59999" bash "$HOOK" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 2 ]; then echo "ok   down -> exit 2"; else echo "FAIL down: expected 2, got $rc"; fail=1; fi

# 2) API up: serve a /health file that returns 200 -> exit 0
tmp="$(mktemp -d)"
printf '{"success": true}' > "$tmp/health"
( cd "$tmp" && exec python3 -m http.server 8731 --bind 127.0.0.1 ) >/dev/null 2>&1 &
srv=$!
trap 'kill "$srv" 2>/dev/null; rm -rf "$tmp"' EXIT
sleep 1
GEPHI_API_URL="http://127.0.0.1:8731" bash "$HOOK" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then echo "ok   up -> exit 0"; else echo "FAIL up: expected 0, got $rc"; fail=1; fi

[ "$fail" -eq 0 ] && echo "ALL HOOK TESTS PASS" || echo "HOOK TESTS FAILED"
exit "$fail"
