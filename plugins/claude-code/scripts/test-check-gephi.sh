#!/usr/bin/env bash
# Test for check-gephi.sh: it must BLOCK (exit 2) when the API is unreachable
# and ALLOW (exit 0) when /health returns 200. Run: bash test-check-gephi.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/check-gephi.sh"
fail=0

# Wait until something listens on the port. A fixed pause is too short on a busy machine, and the
# hook then finds nothing there.
listening() {
  local _
  for _ in $(seq 1 150); do
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && return 0
    sleep 0.2
  done
  echo "FAIL nothing listened on port $1 within 30s"; fail=1
}

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
listening 8731
GEPHI_API_URL="http://127.0.0.1:8731" bash "$HOOK" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then echo "ok   up -> exit 0"; else echo "FAIL up: expected 0, got $rc"; fail=1; fi

# 3) Another service holds the port (404 on /health) -> exit 2, and say so: "Gephi is not
#    running" sends the person to restart a Gephi that is running on another port.
other="$(mktemp -d)"
( cd "$other" && exec python3 -m http.server 8732 --bind 127.0.0.1 ) >/dev/null 2>&1 &
srv2=$!
trap 'kill "$srv" "$srv2" 2>/dev/null; rm -rf "$tmp" "$other"' EXIT
listening 8732
msg=$(GEPHI_API_URL="http://127.0.0.1:8732" bash "$HOOK" 2>&1 >/dev/null)
rc=$?
case "$rc:$msg" in
  2:*GEPHI_API_URL*) echo "ok   other service -> exit 2, names GEPHI_API_URL" ;;
  *) echo "FAIL other service: expected exit 2 naming GEPHI_API_URL, got $rc: $msg"; fail=1 ;;
esac

# 4) Something accepts the connection and never answers (a frozen Gephi) -> exit 2 within a few
#    seconds, saying it did not answer: "not running" sends the person to start a running Gephi.
python3 -c '
import socket, time
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 8733)); s.listen(1); c, _ = s.accept(); time.sleep(20)
' >/dev/null 2>&1 &
srv3=$!
trap 'kill "$srv" "$srv2" "$srv3" 2>/dev/null; rm -rf "$tmp" "$other"' EXIT
listening 8733
start=$SECONDS
msg=$(GEPHI_API_URL="http://127.0.0.1:8733" bash "$HOOK" 2>&1 >/dev/null)
rc=$?
took=$((SECONDS - start))
case "$rc:$took:$msg" in
  2:[0-5]:*"did not answer"*) echo "ok   silent listener -> exit 2 in ${took}s, says it did not answer" ;;
  *) echo "FAIL silent listener: expected exit 2 within 5s saying 'did not answer', got $rc after ${took}s: $msg"; fail=1 ;;
esac

[ "$fail" -eq 0 ] && echo "ALL HOOK TESTS PASS" || echo "HOOK TESTS FAILED"
exit "$fail"
