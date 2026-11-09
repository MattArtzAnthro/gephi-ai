#!/usr/bin/env bash
# Unit tests for install.sh: ver_ge, download's checksum rules, the Claude Desktop config
# rewrite, the health request, which processes count as Gephi on macOS, and the refusal to
# change anything when no checksum is available. install.sh is sourced with GEPHI_AI_INSTALLER_TEST=1, which skips its final main call.
# Offline: fetch is stubbed, and HOME is a temp folder, so no real config is read or written.
# Run: bash scripts/test-installer.sh   (INSTALL_SH=path tests another copy)
# Variables set and functions defined here are used by the sourced installer, and expect()
# runs functions handed to it by name; the linter sees neither. Older shellcheck (0.9, on CI's
# Ubuntu image) reports such functions as SC2317, newer ones as SC2329.
# shellcheck disable=SC2034,SC2317,SC2329
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

# --- a new Claude Desktop config is written owner-only ---
rm -f "$CFG"
edit add >/dev/null
expect "a new config is created 0600" test "$(mode_of "$CFG")" = 0o600

# --- macOS: which processes count as a running Gephi ---
matches_gephi() { # matches_gephi "COMMAND LINE" -> true when the macOS pattern matches it
  ( load; OS=Darwin; printf '%s\n' "$1" | grep -qE "$(gephi_pattern)" )
}
not_gephi() { ! matches_gephi "$1"; }
expect "Gephi on its bundled Java counts" matches_gephi \
  "/Applications/Gephi.app/Contents/PlugIns/jdk-17.0.21+9-jre/Contents/Home/bin/java -Djdk.home=/Applications/Gephi.app/Contents/PlugIns/jdk-17.0.21+9-jre/Contents/Home -classpath x org.netbeans.Main --branding gephi"
expect "Gephi on a Java set in gephi.conf counts" matches_gephi \
  "/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java -Djdk.home=/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home -classpath x org.netbeans.Main --branding gephi"
expect "an editor with a file in Gephi.app does not" not_gephi \
  "/Applications/Visual Studio Code.app/Contents/MacOS/Electron /Applications/Gephi.app/Contents/Resources/gephi/etc/gephi.conf"
expect "a shell searching for the branding flag does not" not_gephi "grep -r --branding gephi /Applications/Gephi.app"
# The installer itself, run as /bin/bash -c "...", has the pattern on its own command line.
own_line_is_not_gephi() { ( load; not_gephi "/bin/bash -c pgrep -f '$(OS=Darwin gephi_pattern)'" ); }
expect "the pattern does not match a command line that contains it" own_line_is_not_gephi

# --- Linux: the Gephi version comes from the folder name ---
folder_version() { # folder_version NAME -> the version find_gephi reads from a folder so named
  local fh="$WORK/folders/$1"
  rm -rf "$WORK/folders"; mkdir -p "$fh/bin"; printf '#!/bin/sh\n' >"$fh/bin/gephi"; chmod +x "$fh/bin/gephi"
  ( load; OS=Linux; HOME="$WORK/folders"; has() { [ "$1" != gephi ] && command -v "$1" >/dev/null; }
    find_gephi >/dev/null 2>&1; printf '%s' "$GEPHI_VER" )
}
expect "gephi-0.11.4 reads as 0.11.4" test "$(folder_version gephi-0.11.4)" = 0.11.4
# Read as unknown, a pre-release folder would skip the version check altogether.
expect "gephi-0.11.3-rc1 reads as 0.11.3-rc1, so the version check sees it" \
  test "$(folder_version gephi-0.11.3-rc1)" = 0.11.3-rc1
expect "a folder with no version reads as unknown" test "$(folder_version gephi)" = ""

# --- no checksum: refuse before closing Gephi or removing the old plugin ---
refusal_leaves_legacy() {
  local ud="$WORK/userdir"
  rm -rf "$ud" "$WORK/quit"; mkdir -p "$ud/modules"
  (
    load
    touch "$ud/modules/$LEGACY_BASE.jar"
    find_userdir() { USERDIR="$ud"; }
    gephi_bundled_module() { return 1; }
    ask() { return 0; }
    quit_gephi() { echo quit >>"$WORK/quit"; }
    NBM_SHA="" ALLOW_UNVERIFIED=0 DRY=0 NBM_VER=9.9.9
    install_nbm >/dev/null 2>&1
    rc=$?
    [ "$rc" != 0 ] && [ -f "$ud/modules/$LEGACY_BASE.jar" ] && [ ! -e "$WORK/quit" ]
  )
}
expect "no checksum: the old plugin stays and Gephi is not closed" refusal_leaves_legacy

# --- no checksum is needed when nothing has to be downloaded ---
no_checksum_needed() { # no_checksum_needed bundled|current -> install_nbm succeeds without one
  local ud="$WORK/userdir"
  rm -rf "$ud" "$WORK/quit"; mkdir -p "$ud/modules" "$ud/update_tracking"
  (
    load
    find_userdir() { USERDIR="$ud"; }
    quit_gephi() { echo quit >>"$WORK/quit"; }
    NBM_SHA="" ALLOW_UNVERIFIED=0 DRY=0 NBM_VER=9.9.9
    if [ "$1" = bundled ]; then
      gephi_bundled_module() { echo "$WORK/gephi/gephi/modules/$MODULE_BASE.jar"; }
      bundled_version() { echo 9.9.9; }
    else
      gephi_bundled_module() { return 1; }
      touch "$ud/modules/$MODULE_BASE.jar"
      echo '<module specification_version="9.9.9"/>' >"$ud/update_tracking/$MODULE_BASE.xml"
    fi
    install_nbm >/dev/null 2>&1 && [ "$NBM_OK" = 1 ] && [ ! -e "$WORK/quit" ]
  )
}
expect "no checksum: a Gephi that bundles the plugin is still fine" no_checksum_needed bundled
expect "no checksum: an already current plugin is still fine" no_checksum_needed current

# --- a leftover dangling .tmp link does not stop the Claude Desktop step ---
rm -f "$CFG"; ln -sf "$WORK/nowhere" "$CFG.tmp"
expect "a dangling .tmp link is replaced" test "$(edit add)" = added

[ "$fail" -eq 0 ] && echo "ALL INSTALLER TESTS PASS" || echo "INSTALLER TESTS FAILED"
exit "$fail"
