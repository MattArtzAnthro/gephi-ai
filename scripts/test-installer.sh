#!/usr/bin/env bash
# Unit tests for install.sh: ver_ge, download's checksum rules, and the Claude Desktop config
# rewrite. install.sh is sourced with GEPHI_AI_INSTALLER_TEST=1, which skips its final main call.
# Offline: fetch is stubbed, and HOME is a temp folder, so no real config is read or written.
# Run: bash scripts/test-installer.sh   (INSTALL_SH=path tests another copy)
# Variables set and functions defined here are used by the sourced installer, and expect()
# runs functions handed to it by name; the linter sees neither.
# shellcheck disable=SC2034,SC2329
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL_SH="${INSTALL_SH:-$HERE/../install.sh}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export HOME="$WORK/home"
mkdir -p "$HOME"
fail=0
pass() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
# expect NAME CMD...: pass when the command succeeds.
expect() { local n=$1; shift; if "$@"; then pass "$n"; else bad "$n"; fi; }

# Each check runs in a subshell with the installer sourced, because die() exits.
load() {
  export GEPHI_AI_INSTALLER_TEST=1
  # shellcheck disable=SC1090
  source "$INSTALL_SH"
  set +eEu +o pipefail
  trap - ERR
}

# --- ver_ge ---
ver_case() { # ver_case A B expected(0|1)
  ( load; ver_ge "$1" "$2"; echo $? ) | tail -1
}
for row in "0.11.4|0.11.4|0" "0.11.5|0.11.4|0" "0.11.3|0.11.4|1" "0.11.10|0.11.4|0" \
           "0.11.3-rc|0.11.4|1" "0.11.4-rc|0.11.4|0" "1|0.11.4|0" "abc|0.11.4|1" "|0.11.4|1" \
           "0.11.4|abc|1"; do
  IFS='|' read -r a b want <<<"$row"
  got=$(ver_case "$a" "$b")
  if [ "$got" = "$want" ]; then pass "ver_ge '$a' '$b' -> $want"; else bad "ver_ge '$a' '$b': wanted $want, got $got"; fi
done

# --- download: stub fetch, never the network ---
SRC="$WORK/asset.bin"; printf 'payload' >"$SRC"
GOOD=$(shasum -a 256 "$SRC" 2>/dev/null | cut -d' ' -f1 || true)
[ -n "$GOOD" ] || GOOD=$(sha256sum "$SRC" | cut -d' ' -f1)
run_download() { # run_download SHA ALLOW -> prints exit code; fetched file lands in $WORK/out
  rm -f "$WORK/out"
  (
    load
    ALLOW_UNVERIFIED=$2
    fetch() { local dest=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && dest=$2; shift; done; cp "$SRC" "$dest"; }
    download "https://example.invalid/asset.bin" "$1" "$WORK/out" >/dev/null 2>&1
  )
  echo $?
}
ZERO=0000000000000000000000000000000000000000000000000000000000000000
refused() { [ "$(run_download "$1" "$2")" != 0 ]; }
refused_without_file() { [ "$(run_download "$1" "$2")" != 0 ] && [ ! -e "$WORK/out" ]; }
accepted_with_file() { [ "$(run_download "$1" "$2")" = 0 ] && cmp -s "$SRC" "$WORK/out"; }
expect "download refuses with no checksum" refused_without_file "" 0
expect "download allows no checksum under ALLOW_UNVERIFIED=1" accepted_with_file "" 1
expect "download refuses a checksum mismatch" refused "$ZERO" 0
expect "ALLOW_UNVERIFIED does not excuse a mismatch" refused "$ZERO" 1
expect "download accepts the right checksum" accepted_with_file "$GOOD" 0

# --- Claude Desktop config rewrite ---
# desktop_edit runs its Python through `<dir of UVX>/uv run --no-project --quiet python -`; the
# stub uv runs the system python3 instead, so the test needs no uv and no network.
BIN="$WORK/bin"; mkdir -p "$BIN"
cat >"$BIN/uv" <<'STUB'
#!/bin/sh
while [ "$1" != python ]; do shift; done; shift
exec python3 "$@"
STUB
chmod +x "$BIN/uv"
CFG="$WORK/cfg/claude_desktop_config.json"
mkdir -p "$(dirname "$CFG")"
edit() { ( load; UVX="$BIN/uvx"; SERVER_VER=9.9.9; DESKTOP_CFG="$CFG"; desktop_edit "$1" ); }
mode_of() { python3 -c 'import os,stat,sys;print(oct(stat.S_IMODE(os.stat(sys.argv[1]).st_mode)))' "$1"; }

printf '{"theme": "dark", "mcpServers": {"other": {"command": "node", "args": ["x.js"]}}}' >"$CFG"
chmod 600 "$CFG"
out=$(edit add)
expect "desktop_edit adds the entry" test "$out" = added
expect "a 0600 config stays 0600" test "$(mode_of "$CFG")" = 0o600
keeps_unrelated_keys() {
  python3 - "$CFG" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
assert c["theme"] == "dark" and c["mcpServers"]["other"] == {"command": "node", "args": ["x.js"]}
assert c["mcpServers"]["gephi-ai"]["args"] == ["--from", "gephi-ai==9.9.9", "gephi-ai"]
PY
}
expect "unrelated keys survive" keeps_unrelated_keys
expect "a second add changes nothing" test "$(edit add)" = current
expect "remove answers removed" test "$(edit remove)" = removed
expect "remove keeps the mode too" test "$(mode_of "$CFG")" = 0o600

# --- health: asks the quick /health and waits long enough for a busy Gephi; curl is stubbed ---
health_args() { # prints the arguments health() hands to curl
  (
    load
    curl() { printf '%s\n' "$*" >"$WORK/curl-args"; return 0; }
    health >/dev/null
    cat "$WORK/curl-args"
  )
}
HEALTH_ARGS=$(health_args)
health_asks_quick() { case "$HEALTH_ARGS" in *"/health?quick=true"*) true ;; *) false ;; esac; }
health_waits_five() { case " $HEALTH_ARGS " in *" -m 5 "*) true ;; *) false ;; esac; }
expect "health asks for /health?quick=true" health_asks_quick
expect "health waits 5 seconds" health_waits_five

[ "$fail" -eq 0 ] && echo "ALL INSTALLER TESTS PASS" || echo "INSTALLER TESTS FAILED"
exit "$fail"
