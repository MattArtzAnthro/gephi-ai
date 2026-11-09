#!/usr/bin/env bash
# Gephi AI installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/MattArtzAnthro/gephi-ai/main/install.sh | bash
#
# Pass options after `bash -s --`, for example `... | bash -s -- --dry-run`.
#
#   --yes                 accept every default without asking
#   --dry-run             print what would change and change nothing
#   --clients LIST        only these, comma-separated: claude,codex,gemini,desktop
#   --skip-gephi-plugin   leave Gephi Desktop alone; connect the assistants only
#   --version X.Y.Z       install a specific release instead of the latest
#   --allow-unverified    install the Gephi plugin even when no checksum can be
#                         found for it (otherwise the installer refuses)
#   --open-gephi          open Gephi at the end and check that the plugin answers
#   --no-launch           do not reopen Gephi if the installer had to close it
#   --uninstall           remove what this script installs (leaves uv and Gephi)
#
# Safe to re-run: it updates what is out of date and skips what is current.
# Windows: see install.ps1 in the same repository.

set -Eeuo pipefail

REPO="MattArtzAnthro/gephi-ai"
MARKETPLACE="gephi-ai"
PLUGIN="gephi-network-analysis@gephi-ai"
MODULE_BASE="org-gephi-plugins-gephi-ai"
LEGACY_BASE="org-gephi-plugins-gephi-mcp"
DOWNLOAD_PAGE="https://gephi.org/desktop/"

YES=0 DRY=0 UNINSTALL=0 SKIP_NBM=0 NO_LAUNCH=0 OPEN_GEPHI=0 CLIENTS="" WANT_VERSION="" ALLOW_UNVERIFIED=0
CLOSED_GEPHI=0
TMP="" LOG="" UVX="" STEP="starting" NBM_OK=0

# ---------- output ----------

if [ -t 1 ]; then
  B=$'\033[1m' G=$'\033[32m' Y=$'\033[33m' R=$'\033[31m' D=$'\033[2m' N=$'\033[0m'
else
  B="" G="" Y="" R="" D="" N=""
fi
say()  { printf '%s\n' "$*"; }
head_() { STEP="$*"; printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$*" "$N" >&2; exit 1; }
# The summary lives in files because each assistant is set up in a subshell,
# which cannot add to the parent's variables.
done_() { printf '%s\n' "${G}✓${N} $*" >>"$TMP/summary"; }
skip_() { printf '%s\n' "${Y}–${N} $*" >>"$TMP/summary"; }
fail_() { printf '%s\n' "${R}✗${N} $*" >>"$TMP/summary"; }
next_() { printf '%s\n' "$*" >>"$TMP/next"; }

# Prompts read the terminal, not stdin, because under `curl | bash` stdin is
# the script itself. With no terminal, or with --yes, the default stands.
ask() { # ask "Question?" Y|N
  local q=$1 def=$2 hint reply
  [ "$def" = Y ] && hint="[Y/n]" || hint="[y/N]"
  if [ "$YES" = 1 ] || ! { : </dev/tty; } 2>/dev/null; then
    [ "$def" = Y ]; return
  fi
  printf '  %s %s ' "$q" "$hint" >/dev/tty
  read -r reply </dev/tty || reply=""
  case "${reply:-$def}" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

# run CMD... runs a command unless --dry-run. Its output goes to the log, and
# reaches the screen only when the command fails.
run() {
  if [ "$DRY" = 1 ]; then printf '  %swould run: %s%s\n' "$D" "$*" "$N"; return 0; fi
  local out rc=0
  out=$("$@" 2>&1) || rc=$?
  [ -n "$LOG" ] && printf '$ %s\n%s\n' "$*" "$out" >>"$LOG"
  if [ "$rc" != 0 ]; then
    printf '  %s$ %s%s\n' "$D" "$*" "$N"
    printf '%s\n' "$out" | tail -15 | sed 's/^/    /'
  fi
  return "$rc"
}

on_error() {
  # set -E carries this trap into $(...) subshells, where a failure is often
  # expected and handled; only the main shell reports.
  [ "$BASH_SUBSHELL" = 0 ] || return 0
  printf '\n%s✗ Stopped while: %s (line %s).%s\n' "$R" "$STEP" "$1" "$N" >&2
  printf '  Nothing half-done is left behind that a re-run will not fix. Re-run the same command to retry.\n' >&2
  [ -n "$LOG" ] && printf '  Full log: %s\n  Attach it to an issue at https://github.com/%s/issues\n' "$LOG" "$REPO" >&2
}

cleanup() { [ -n "$TMP" ] && rm -rf "$TMP"; return 0; }

# ---------- small utilities ----------

has() { command -v "$1" >/dev/null 2>&1; }

# output_has PATTERN CMD...: true when CMD's output matches PATTERN. Capturing
# first avoids `cmd | grep -q`, which under pipefail can report a match as a
# failure when grep exits before cmd finishes writing.
output_has() {
  local pat=$1 out
  shift
  out=$("$@" 2>&1) || true
  printf '%s\n' "$out" | grep -qE -- "$pat"
}

# ver_ge A B: true when version A >= B. A pre-release suffix ("0.11.3-rc") is
# dropped, so 0.11.3-rc counts as 0.11.3. A version with a part that is not a
# number is not new enough (returns 1).
ver_ge() {
  local IFS=. i a b x y
  x=${1%%[-+]*}; y=${2%%[-+]*}
  read -r -a a <<<"$x"; read -r -a b <<<"$y"
  for i in 0 1 2 3; do
    x=${a[i]:-0}; y=${b[i]:-0}
    case $x in "" | *[!0-9]*) return 1 ;; esac
    case $y in "" | *[!0-9]*) return 1 ;; esac
    [ "$((10#$x))" -gt "$((10#$y))" ] && return 0
    [ "$((10#$x))" -lt "$((10#$y))" ] && return 1
  done
  return 0
}

# claude_has_server NAME: `claude mcp get` exits 0 even when it finds nothing,
# so read what it says.
claude_has_server() {
  local out
  out=$(claude mcp get "$1" 2>&1) || return 1
  case $out in *"No MCP server found"*) return 1 ;; esac
  return 0
}

# https only, including after a redirect.
fetch() { curl -fsSL --proto '=https' --proto-redir '=https' --retry 3 --connect-timeout 15 "$@"; }

sha256() {
  if has shasum; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi
}

# CRC-32 of a file, the checksum NetBeans records for installed plugin files.
# gzip stores it little-endian in the 4 bytes before the trailing length.
crc32() {
  local t
  t=$(gzip -c <"$1" | tail -c8 | od -An -tu4)
  # shellcheck disable=SC2086  # split od's two numbers; the first is the CRC
  set -- $t
  printf '%s' "$1"
}

unzip_to() { # unzip_to ARCHIVE DIR
  if has unzip; then unzip -q -o "$1" -d "$2"
  elif has bsdtar; then bsdtar -xf "$1" -C "$2"
  else python3 -m zipfile -e "$1" "$2"; fi
}

# ---------- release metadata ----------

SERVER_VER="" NBM_VER="" NEEDS_GEPHI="" NBM_URL="" NBM_SHA=""

read_release() {
  head_ "Looking up the ${WANT_VERSION:-latest} release"
  local api json
  if [ -n "$WANT_VERSION" ]; then
    api="https://api.github.com/repos/$REPO/releases/tags/v${WANT_VERSION#v}"
  else
    api="https://api.github.com/repos/$REPO/releases/latest"
  fi
  local auth=()
  [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
  json=$(fetch -H "Accept: application/vnd.github+json" ${auth[@]+"${auth[@]}"} "$api" 2>/dev/null) || json=""
  SERVER_VER=$(printf '%s\n' "$json" | sed -n 's/^  "tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -1) || true

  # GitHub allows 60 API calls an hour per network address, which a classroom
  # on one network can use up. The release's latest.json is served from
  # elsewhere and carries the same versions and, in newer releases, the plugin's checksum.
  if [ -z "$SERVER_VER" ]; then
    local ref=main marker
    [ -n "$WANT_VERSION" ] && ref="v${WANT_VERSION#v}"
    if ! marker=$(fetch "https://raw.githubusercontent.com/$REPO/$ref/latest.json" 2>/dev/null); then
      [ -n "$WANT_VERSION" ] && die "There is no Gephi AI release $WANT_VERSION. Releases: https://github.com/$REPO/releases"
      die "Could not reach GitHub. Check your internet connection and try again."
    fi
    SERVER_VER=$(printf '%s\n' "$marker" | sed -n 's/.*"server": *"\([^"]*\)".*/\1/p' | head -1)
    NBM_VER=$(printf '%s\n' "$marker" | sed -n 's/.*"nbm": *"\([^"]*\)".*/\1/p' | head -1)
    NEEDS_GEPHI=$(printf '%s\n' "$marker" | sed -n 's/.*"nbm_needs_gephi": *"\([^"]*\)".*/\1/p' | head -1)
    NBM_SHA=$(printf '%s\n' "$marker" | sed -n 's/.*"nbm_sha256": *"\([0-9A-Fa-f]\{64\}\)".*/\1/p' | head -1)
    if [ -z "$SERVER_VER" ] || [ -z "$NBM_VER" ]; then
      die "Could not read the release from GitHub. Try again in a few minutes."
    fi
    NBM_URL="https://github.com/$REPO/releases/download/v$SERVER_VER/gephi-ai-$NBM_VER.nbm"
    NEEDS_GEPHI=${NEEDS_GEPHI:-0.11.4}
    warn "GitHub's API was unavailable (often its hourly limit on a shared network); using the release's version file"
    [ -n "$NBM_SHA" ] || warn "That file lists no checksum for the Gephi plugin"
    ok "Gephi AI $SERVER_VER (Gephi plugin $NBM_VER, needs Gephi $NEEDS_GEPHI or newer)"
    return 0
  fi

  # Each asset lists its digest before its download URL, so remember the last
  # digest seen and pair it with the next URL.
  local pairs
  pairs=$(printf '%s\n' "$json" | awk -F'"' '
    /"digest":/ { d = $4 }
    /"browser_download_url":/ { print $4 " " d; d = "" }')
  NBM_URL=$(printf '%s\n' "$pairs" | awk '$1 ~ /\.nbm$/ {print $1; exit}')
  NBM_SHA=$(printf '%s\n' "$pairs" | awk '$1 ~ /\.nbm$/ {sub(/^sha256:/, "", $2); print $2; exit}')
  NBM_VER=$(printf '%s\n' "$NBM_URL" | sed -n 's/.*gephi-ai-\([0-9.]*\)\.nbm$/\1/p')

  # The release's latest.json is the second source for the checksum, used when
  # the API listed no digest for the asset.
  local marker
  marker=$(fetch "https://raw.githubusercontent.com/$REPO/v$SERVER_VER/latest.json" 2>/dev/null) || marker=""
  NEEDS_GEPHI=$(printf '%s\n' "$marker" | sed -n 's/.*"nbm_needs_gephi": *"\([^"]*\)".*/\1/p' | head -1) || true
  NEEDS_GEPHI=${NEEDS_GEPHI:-0.11.4}
  if [ -z "$NBM_SHA" ]; then
    NBM_SHA=$(printf '%s\n' "$marker" | sed -n 's/.*"nbm_sha256": *"\([0-9A-Fa-f]\{64\}\)".*/\1/p' | head -1) || true
  fi

  ok "Gephi AI $SERVER_VER (Gephi plugin $NBM_VER, needs Gephi $NEEDS_GEPHI or newer)"
}

# download URL SHA256 DEST: fetch a release asset and refuse it if the checksum
# does not match. With no checksum, it refuses unless --allow-unverified was given.
download() {
  local url=$1 want=$2 dest=$3 got
  if [ -z "$want" ] && [ "$ALLOW_UNVERIFIED" != 1 ]; then
    die "No checksum is available for $(basename "$url"), so it was not downloaded. Run this again later, or pass --allow-unverified to install it without a check."
  fi
  fetch -o "$dest" "$url" || die "Download failed: $url"
  if [ -n "$want" ]; then
    got=$(sha256 "$dest")
    [ "$got" = "$(printf '%s' "$want" | tr 'A-F' 'a-f')" ] || die "Checksum mismatch for $(basename "$url"). Expected $want, got $got. Nothing was installed from it."
    ok "Downloaded $(basename "$url") (checksum verified)"
  else
    warn "Downloaded $(basename "$url") WITHOUT a checksum, as --allow-unverified asked"
  fi
}

# ---------- Gephi Desktop ----------

OS=$(uname -s)
GEPHI_APP="" GEPHI_BIN="" GEPHI_HOME="" GEPHI_VER="" USERDIR=""

find_gephi() {
  GEPHI_APP="" GEPHI_BIN="" GEPHI_HOME="" GEPHI_VER=""
  local c
  if [ "$OS" = Darwin ]; then
    for c in "/Applications/Gephi.app" "$HOME/Applications/Gephi.app"; do
      [ -d "$c" ] && { GEPHI_APP=$c; break; }
    done
    if [ -z "$GEPHI_APP" ] && has mdfind; then
      GEPHI_APP=$(mdfind "kMDItemCFBundleIdentifier == 'org.gephi'" 2>/dev/null | head -1)
    fi
    [ -n "$GEPHI_APP" ] || return 1
    GEPHI_BIN="$GEPHI_APP/Contents/MacOS/gephi"
    GEPHI_HOME="$GEPHI_APP/Contents/Resources/gephi"
    GEPHI_VER=$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$GEPHI_APP/Contents/Info.plist" 2>/dev/null || true)
  else
    if has gephi; then
      c=$(command -v gephi)
      c=$(readlink -f "$c" 2>/dev/null || printf '%s' "$c")
      GEPHI_BIN=$c
      GEPHI_HOME=$(cd "$(dirname "$c")/.." && pwd)
    else
      # Several installs: take the newest version, not the last path matched.
      c=$(for d in "$HOME"/gephi-0.* "$HOME"/Applications/gephi-0.* /opt/gephi* /usr/local/gephi-0.*; do
            [ -x "$d/bin/gephi" ] && printf '%s\t%s\n' "$(basename "$d")" "$d"
          done | sort -V -k1,1 | tail -1 | cut -f2) || true
      [ -n "$c" ] && { GEPHI_HOME=$c; GEPHI_BIN="$c/bin/gephi"; }
    fi
    [ -n "$GEPHI_BIN" ] || return 1
    # gephi-0.11.4, or gephi-0.11.4-rc1 (a pre-release, which the version check reads as 0.11.4).
    GEPHI_VER=$(basename "$GEPHI_HOME" | sed -n 's/^gephi-\([0-9][0-9.]*\(-[A-Za-z0-9.]\{1,\}\)\{0,1\}\)$/\1/p')
  fi
  return 0
}

# Gephi keeps per-user plugins in its user directory, named in gephi.conf.
find_userdir() {
  local root conf line
  if [ "$OS" = Darwin ]; then root="$HOME/Library/Application Support/gephi"; else root="$HOME/.gephi"; fi
  conf="$GEPHI_HOME/etc/gephi.conf"
  line=$(sed -n 's/^default_userdir="\(.*\)"/\1/p' "$conf" 2>/dev/null | head -1) || true
  # gephi.conf holds literal ${...} placeholders, so these quotes are deliberate.
  # shellcheck disable=SC2016
  [ -n "$line" ] || line='${DEFAULT_USERDIR_ROOT}/0.11'
  # shellcheck disable=SC2016
  line=${line//'${DEFAULT_USERDIR_ROOT}'/$root}
  # shellcheck disable=SC2016
  line=${line//'${HOME}'/$HOME}
  USERDIR=$line
}

gephi_pattern() {
  # The launcher passes --branding gephi on every platform. On macOS, match only
  # a java process (Gephi's own Java or one gephi.conf points to), so an editor or a
  # shell with a path in Gephi.app on its command line is not mistaken for Gephi. The
  # bracket keeps the pattern from matching a command line that contains the pattern,
  # such as this installer run with bash -c.
  if [ "$OS" = Darwin ]; then printf '%s' '^/.*/bin/jav[a] .*--branding gephi'
  else printf '%s' "branding gephi"; fi
}
gephi_running() { pgrep -f "$(gephi_pattern)" >/dev/null 2>&1; }

start_gephi() {
  if [ -n "$GEPHI_APP" ]; then open -a "$GEPHI_APP" --env "HOME=$HOME"
  else nohup "$GEPHI_BIN" >/dev/null 2>&1 & fi
}

# macOS asks once before it opens an app downloaded from the internet, and
# Gephi waits at that prompt until someone clicks Open. The quarantine flags
# gain the 0x40 bit once the person has approved the app.
gephi_awaits_first_open() {
  [ -n "$GEPHI_APP" ] || return 1
  local q
  q=$(xattr -p com.apple.quarantine "$GEPHI_APP" 2>/dev/null) || return 1
  q=${q%%;*}
  case "$q" in "" | *[!0-9a-fA-F]*) return 1 ;; esac
  [ "$(( 0x$q & 0x40 ))" -eq 0 ]
}

# Newer Gephi releases ship the plugin themselves. The bundled module's file
# names are not settled yet, so look for either name the plugin has had.
# Prints the module's config file inside the Gephi installation, if any.
gephi_bundled_module() {
  [ -n "$GEPHI_HOME" ] || return 1
  find "$GEPHI_HOME" -path '*/config/Modules/*.xml' \( -name '*gephi-ai*' -o -name '*gephi-mcp*' \) 2>/dev/null |
    head -1 | grep . || return 1
}

# The version Gephi recorded for a bundled module, read from its cluster's
# update_tracking folder (config/Modules/x.xml -> update_tracking/x.xml).
bundled_version() {
  local cluster
  cluster=$(dirname "$(dirname "$(dirname "$1")")")
  sed -n 's/.*specification_version="\([^"]*\)".*/\1/p' \
    "$cluster/update_tracking/$(basename "$1")" 2>/dev/null | head -1 || true
}

# The 5-second wait leaves a stalled Gephi, whose full health check samples the renderer and
# probes the graph lock, time to answer. A plugin that knows ?quick skips both; the plugins
# released so far ignore the parameter and give the full answer.
health() { curl -s -m 5 "http://127.0.0.1:8080/health?quick=true" 2>/dev/null || true; }

ensure_gephi() {
  head_ "Gephi Desktop"
  if find_gephi; then
    if [ -n "$GEPHI_VER" ] && ! ver_ge "$GEPHI_VER" "$NEEDS_GEPHI"; then
      warn "Gephi $GEPHI_VER is installed; the plugin needs $NEEDS_GEPHI or newer"
      if [ "$OS" = Darwin ] && has brew && brew list --cask gephi >/dev/null 2>&1 &&
         ask "Upgrade Gephi with Homebrew now?" Y; then
        run brew upgrade --cask gephi
        [ "$DRY" = 1 ] || find_gephi
      else
        say "  Download Gephi $NEEDS_GEPHI or newer from $DOWNLOAD_PAGE, install it, and run this again."
        fail_ "Gephi $GEPHI_VER is too old for the plugin (needs $NEEDS_GEPHI)"
        next_ "Update Gephi from $DOWNLOAD_PAGE, then re-run this installer."
        return 1
      fi
    fi
    ok "Found Gephi ${GEPHI_VER:-(version unknown)} at ${GEPHI_APP:-$GEPHI_HOME}"
    return 0
  fi

  warn "Gephi Desktop is not installed"
  if [ "$OS" = Darwin ] && has brew && ask "Install Gephi with Homebrew (brew install --cask gephi)?" Y; then
    run brew install --cask gephi
    [ "$DRY" = 1 ] && { GEPHI_APP=/Applications/Gephi.app; GEPHI_HOME="$GEPHI_APP/Contents/Resources/gephi"; return 0; }
    find_gephi && { ok "Installed Gephi $GEPHI_VER"; return 0; }
  fi
  say "  Download Gephi from $DOWNLOAD_PAGE, install it, open it once, then run this again."
  say "  The assistant setup below still goes ahead, so the re-run will only add the Gephi plugin."
  if [ "$OS" = Darwin ]; then [ "$DRY" = 1 ] || open "$DOWNLOAD_PAGE" 2>/dev/null || true
  elif has xdg-open; then [ "$DRY" = 1 ] || xdg-open "$DOWNLOAD_PAGE" >/dev/null 2>&1 || true; fi
  skip_ "Gephi plugin not installed: Gephi Desktop is missing"
  next_ "Install Gephi from $DOWNLOAD_PAGE, then re-run this installer to add the plugin."
  return 1
}

quit_gephi() {
  gephi_running || return 0
  warn "Gephi is open. It has to be closed while the plugin is installed."
  CLOSED_GEPHI=1
  if ask "Close Gephi now? (it will ask to save anything unsaved)" Y; then
    # osascript reports "User canceled" when Gephi quits mid-reply; that is success.
    if [ "$OS" = Darwin ]; then run osascript -e 'quit app "Gephi"' >/dev/null 2>&1 || true
    else say "  Please close Gephi yourself."; fi
  fi
  [ "$DRY" = 1 ] && return 0
  local i
  for i in $(seq 1 60); do
    gephi_running || { ok "Gephi is closed"; return 0; }
    [ "$i" = 1 ] && say "  Waiting for Gephi to close..."
    [ "$i" = 30 ] && say "  Still open. If Gephi is asking whether to save, answer it there."
    sleep 1
  done
  if ask "Gephi has not closed. Force it to quit? Anything unsaved in Gephi will be lost." N; then
    run pkill -f "$(gephi_pattern)" || true
    sleep 3
    gephi_running || { ok "Gephi is closed"; return 0; }
  fi
  die "Gephi is still open. Close it and run this again."
}

installed_module_version() {
  sed -n 's/.*specification_version="\([^"]*\)".*/\1/p' \
    "$USERDIR/update_tracking/$MODULE_BASE.xml" 2>/dev/null | head -1 || true
}

# remove_tracked BASE: delete the files a plugin install recorded, then the record.
remove_tracked() {
  local base=$1 track="$USERDIR/update_tracking/$1.xml" f
  if [ -f "$track" ]; then
    sed -n 's/.*<file [^>]*name="\([^"]*\)".*/\1/p' "$track" | while IFS= read -r f; do
      [ -n "$f" ] && rm -f "$USERDIR/$f"
    done
  fi
  rm -f "$USERDIR/modules/$base.jar" "$USERDIR/config/Modules/$base.xml" "$track"
  rm -rf "$USERDIR/modules/ext/org.gephi.plugins.${base#org-gephi-plugins-}"
}

install_nbm() {
  head_ "Gephi AI plugin for Gephi"
  find_userdir
  ok "Gephi user folder: $USERDIR"

  # Refuse before closing Gephi or removing anything when the plugin has to be downloaded and
  # there is nothing to check it against.
  if [ -z "$NBM_SHA" ] && [ "$ALLOW_UNVERIFIED" != 1 ] && ! gephi_bundled_module >/dev/null &&
     ! { [ "$(installed_module_version)" = "$NBM_VER" ] && [ -f "$USERDIR/modules/$MODULE_BASE.jar" ]; }; then
    warn "No checksum for the Gephi plugin could be found, so it will not be installed"
    say "  GitHub's release data and the release's version file both lacked one. Run this again in a few minutes,"
    say "  or pass --allow-unverified to install the plugin without checking it."
    fail_ "Gephi plugin not installed: no checksum to verify it against"
    next_ "Re-run this installer later, or add --allow-unverified to install the plugin without a checksum."
    return 1
  fi

  # Plugin 1.2.x and older was named "Gephi AI (MCP)". Left in place it grabs
  # port 8080 first and the assistant talks to the old version.
  if [ -f "$USERDIR/modules/$LEGACY_BASE.jar" ] || [ -f "$USERDIR/update_tracking/$LEGACY_BASE.xml" ]; then
    warn "An old version of the plugin (Gephi AI (MCP)) is installed and would block the new one on port 8080"
    if ask "Remove the old plugin? (a backup is kept)" Y; then
      quit_gephi
      local bak
      bak="$HOME/.gephi-ai-installer/backup-$(date +%Y%m%d-%H%M%S)"
      if [ "$DRY" = 0 ]; then
        mkdir -p "$bak"
        if ! (cd "$USERDIR" && find . -path "*gephi-mcp*" -type f | tar -cf - -T -) | (cd "$bak" && tar -xf -); then
          die "Could not back up the old plugin to $bak, so it was left in place. Remove \"Gephi AI (MCP)\" in Gephi under Tools > Plugins > Installed, then run this again."
        fi
        remove_tracked "$LEGACY_BASE"
      fi
      if [ "$DRY" = 1 ]; then
        say "  ${D}would move the old plugin's files to $bak${N}"
        done_ "Old Gephi AI (MCP) plugin: would be removed (dry run)"
      else
        ok "Removed the old plugin (backup in $bak)"
        done_ "Removed the old Gephi AI (MCP) plugin"
      fi
    else
      warn "Keeping it. Uninstall Gephi AI (MCP) in Tools > Plugins > Installed before using the new plugin."
      next_ "In Gephi, Tools > Plugins > Installed: uninstall 'Gephi AI (MCP)', then restart Gephi."
    fi
  fi

  local have bundled
  have=$(installed_module_version)
  if bundled=$(gephi_bundled_module); then
    local bver
    bver=$(bundled_version "$bundled")
    ok "Gephi ${GEPHI_VER:-} already includes the Gephi AI plugin${bver:+ ($bver)}"
    # A copy this installer added for an older Gephi would load instead of the
    # bundled one, or fight it for port 8080. Keep it only if it is newer.
    if [ -n "$have" ] && { [ -z "$bver" ] || [ "$have" = "$bver" ] || ! ver_ge "$have" "$bver"; }; then
      say "  Removing the separate copy ($have) added for an older Gephi, so Gephi uses its own"
      quit_gephi
      [ "$DRY" = 1 ] || { remove_tracked "$MODULE_BASE"; touch "$USERDIR/.lastModified"; }
    fi
    NBM_OK=1
    done_ "Gephi plugin: built into Gephi${bver:+ ($bver)}"
    return 0
  fi
  if [ -n "$have" ] && [ "$have" = "$NBM_VER" ] && [ -f "$USERDIR/modules/$MODULE_BASE.jar" ]; then
    ok "Plugin $NBM_VER is already installed"
    NBM_OK=1
    done_ "Gephi plugin $NBM_VER (already current)"
    return 0
  fi
  [ -n "$have" ] && say "  Updating the plugin from $have to $NBM_VER"

  quit_gephi
  local nbm="$TMP/gephi-ai.nbm" x="$TMP/nbm"
  if [ "$DRY" = 1 ]; then
    say "  ${D}would download $NBM_URL and unpack it into $USERDIR${N}"
    done_ "Gephi plugin $NBM_VER (dry run)"
    return 0
  fi
  download "$NBM_URL" "$NBM_SHA" "$nbm"
  mkdir -p "$x"
  unzip_to "$nbm" "$x"
  [ -f "$x/netbeans/modules/$MODULE_BASE.jar" ] || die "The downloaded plugin file is not laid out as expected."

  remove_tracked "$MODULE_BASE"
  mkdir -p "$USERDIR/update_tracking"
  cp -R "$x/netbeans/." "$USERDIR/"

  # Tells Gephi its module list changed, so it rebuilds its cache at next start.
  touch "$USERDIR/.lastModified"

  # Record the install the way Gephi's own installer does, so Tools > Plugins
  # lists it and can uninstall or update it later. Written last: a re-run takes
  # this record to mean the install finished.
  local codename track="$USERDIR/update_tracking/$MODULE_BASE.xml" f
  codename=$(sed -n 's/.*codenamebase="\([^"]*\)".*/\1/p' "$x/Info/info.xml" | head -1)
  {
    printf '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    printf '<module codename="%s">\n' "${codename:-org.gephi.plugins.gephi.ai}"
    printf '    <module_version install_time="%s000" last="true" origin="gephi-ai-%s.nbm" specification_version="%s">\n' \
      "$(date +%s)" "$NBM_VER" "$NBM_VER"
    (cd "$x/netbeans" && find . -type f | sed 's|^\./||' | sort) | while IFS= read -r f; do
      printf '        <file crc="%s" name="%s"/>\n' "$(crc32 "$x/netbeans/$f")" "$f"
    done
    printf '    </module_version>\n</module>\n'
  } >"$track.tmp"
  mv "$track.tmp" "$track"

  ok "Installed the Gephi plugin $NBM_VER"
  NBM_OK=1
  done_ "Gephi plugin $NBM_VER"
}

check_gephi_connection() {
  [ "$NBM_OK" = 1 ] || return 0
  local h opened=0
  h=$(health)
  # Gephi opens only when asked to, or when the installer closed it. Opening it
  # unasked would put macOS's first-open prompt in front of a new user.
  if [ -z "$h" ] && { [ "$OPEN_GEPHI" = 1 ] || { [ "$CLOSED_GEPHI" = 1 ] && [ "$NO_LAUNCH" = 0 ]; }; }; then
    head_ "Checking that Gephi answers"
    [ "$DRY" = 1 ] && { say "  ${D}would open Gephi and wait for the plugin on 127.0.0.1:8080${N}"; return 0; }
    if has lsof && lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1 && ! gephi_running; then
      warn "Another program is already using port 8080, so the plugin cannot start there."
      say "  In Gephi, Tools > Gephi AI Server lets you pick another port; set GEPHI_API_URL to match."
    fi
    if ! gephi_running; then
      if [ "$CLOSED_GEPHI" = 1 ]; then say "  Reopening Gephi..."; else say "  Opening Gephi (the first start can take a minute)..."; fi
      start_gephi
    fi
    opened=1
    local i tries=90
    if gephi_awaits_first_open; then
      warn "This is Gephi's first start on this Mac, so macOS asks whether to open it."
      say "  Click Open in the window that says Gephi was downloaded from the internet."
      tries=150
    fi
    for i in $(seq 1 "$tries"); do
      h=$(health); [ -n "$h" ] && break
      sleep 2
    done
  fi
  if [ -z "$h" ]; then
    if [ "$opened" = 0 ]; then
      next_ "Open Gephi. The plugin starts with it."
      return 0
    fi
    if gephi_awaits_first_open; then
      warn "Gephi is still waiting for you to click Open in the macOS prompt."
      fail_ "Gephi has not been opened yet; click Open in the macOS prompt"
      return 0
    fi
    warn "Gephi did not answer on port 8080 within 3 minutes."
    say "  Open Gephi and check Tools > Gephi AI Server. Its log is in $USERDIR/var/log/messages.log"
    fail_ "Gephi plugin did not answer; see Tools > Gephi AI Server"
    return 0
  fi
  [ "$opened" = 1 ] || head_ "Checking that Gephi answers"
  local v
  v=$(printf '%s' "$h" | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' | head -1)
  if [ -n "$NBM_VER" ] && [ "$v" != "$NBM_VER" ] && [ "$SKIP_NBM" = 0 ] && ! gephi_bundled_module >/dev/null; then
    warn "Gephi answered with plugin $v, not $NBM_VER. Restart Gephi; if it persists, check Tools > Plugins > Installed for a second copy."
    fail_ "Gephi answered with plugin $v instead of $NBM_VER"
  else
    ok "Gephi is running with the plugin ($v)"
    done_ "Gephi answers on 127.0.0.1:8080 (plugin $v)"
  fi
}

# ---------- uv ----------

ensure_uv() {
  head_ "uv (runs the Gephi AI server)"
  local c
  for c in "$(command -v uvx 2>/dev/null || true)" "$HOME/.local/bin/uvx" "$HOME/.cargo/bin/uvx" /opt/homebrew/bin/uvx /usr/local/bin/uvx; do
    [ -n "$c" ] && [ -x "$c" ] && { UVX=$c; break; }
  done
  if [ -n "$UVX" ]; then ok "Found uvx at $UVX"; return 0; fi

  warn "uv is not installed. The assistants use it to run the Gephi AI server."
  ask "Install uv now (from astral.sh, the official installer)?" Y ||
    die "uv is required. Install it from https://docs.astral.sh/uv/ and run this again."
  if [ "$DRY" = 1 ]; then
    run sh -c "curl -LsSf --proto '=https' --proto-redir '=https' https://astral.sh/uv/install.sh | sh"
    UVX="$HOME/.local/bin/uvx"; return 0
  fi
  fetch https://astral.sh/uv/install.sh | sh
  UVX="$HOME/.local/bin/uvx"
  [ -x "$UVX" ] || die "uv installed, but uvx was not found at $UVX."
  ok "Installed uv"
  done_ "Installed uv"
  next_ "Open a new terminal window so 'uvx' is on your PATH before starting your assistant."
}

# Start the server once and send it the MCP handshake. This proves it runs, and
# downloads it and its Python now; otherwise the first launch does that inside
# the assistant and can run past the assistant's startup timeout.
check_server() { # check_server SPEC
  [ "$DRY" = 1 ] && { say "  ${D}would start $1 once and check that it answers${N}"; return 0; }
  local req out err="$TMP/server.err" t=()
  req='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"installer","version":"1.0"}}}'
  has perl && t=(perl -e 'alarm shift; exec @ARGV' 300)
  out=$(printf '%s\n' "$req" | ${t[@]+"${t[@]}"} "$UVX" --quiet --from "$1" gephi-ai 2>"$err") || true
  if printf '%s' "$out" | grep -q '"serverInfo"'; then
    ok "The Gephi AI server ($1) starts and answers"
  else
    warn "The Gephi AI server ($1) did not answer. Its last messages:"
    tail -5 "$err" | sed 's/^/      /'
    fail_ "Gephi AI server did not start; see the log"
  fi
}

# ---------- assistants ----------

detect_clients() {
  local found=""
  has claude && found="$found,claude"
  has codex && found="$found,codex"
  has gemini && found="$found,gemini"
  [ "$OS" = Darwin ] && { [ -d "/Applications/Claude.app" ] || [ -d "$HOME/Applications/Claude.app" ]; } && found="$found,desktop"
  printf '%s' "${found#,}"
}

want() { case ",$CLIENTS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

setup_claude_code() {
  head_ "Claude Code"
  if output_has "(^|[[:space:]])$MARKETPLACE\$" claude plugin marketplace list; then
    run claude plugin marketplace update "$MARKETPLACE"
  else
    run claude plugin marketplace add "$REPO"
  fi
  if output_has "$PLUGIN" claude plugin list; then
    run claude plugin update "$PLUGIN"
  else
    run claude plugin install "$PLUGIN"
  fi
  # The plugin brings its own server. A hand-registered one beside it means
  # two servers and every tool listed twice.
  local n
  for n in gephi-ai gephi-mcp; do
    if claude_has_server "$n"; then
      warn "A separately registered '$n' server would duplicate the plugin's tools"
      if ask "Remove the separate '$n' registration?" Y; then
        run claude mcp remove -s user "$n" || true
      fi
    fi
  done
  ok "Claude Code has the Gephi AI plugin"
  done_ "Claude Code: plugin $PLUGIN"
  next_ "Claude Code: start a new session to load the plugin."
}

setup_codex() {
  head_ "OpenAI Codex"
  if output_has "^${MARKETPLACE}[[:space:]]" codex plugin marketplace list; then
    run codex plugin marketplace upgrade "$MARKETPLACE"
  else
    run codex plugin marketplace add "$REPO" --ref main
  fi
  run codex plugin add "$PLUGIN"
  local n
  for n in gephi-ai gephi-mcp; do
    if grep -q "^\[mcp_servers\.$n\]" "${CODEX_HOME:-$HOME/.codex}/config.toml" 2>/dev/null; then
      warn "A separately registered '$n' server would duplicate the plugin's tools"
      ask "Remove the separate '$n' registration?" Y && run codex mcp remove "$n"
    fi
  done
  ok "Codex has the Gephi AI plugin"
  done_ "Codex: plugin $PLUGIN"
  next_ "Codex: start a new task to load the plugin."
}

setup_gemini() {
  head_ "Gemini CLI"
  local list
  list=$(gemini mcp list 2>/dev/null || true)
  if printf '%s' "$list" | grep -q "gephi-mcp"; then
    warn "Found the old 'gephi-mcp' registration; replacing it with 'gephi-ai'"
    run gemini mcp remove -s user gephi-mcp || true
  fi
  if printf '%s' "$list" | grep -q "gephi-ai"; then
    ok "Gemini CLI already has gephi-ai"
  else
    run gemini mcp add -s user gephi-ai "$UVX" "gephi-ai@$SERVER_VER"
    ok "Registered gephi-ai with Gemini CLI"
  fi
  check_server "gephi-ai==$SERVER_VER"
  done_ "Gemini CLI: gephi-ai server"
}

DESKTOP_CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
DESKTOP_EXT="$HOME/Library/Application Support/Claude/Claude Extensions/local.mcpb.matt-artz.gephi-ai"

# Claude Desktop reads its servers from a JSON file, which needs no click to
# change (installing an extension does). Desktop apps do not see the
# terminal's PATH, so the entry names uvx by its full path.
# desktop_edit add|replace|remove: prints current, added, updated, removed,
# absent, custom:<command>, legacy, or invalid:<why>.
desktop_edit() {
  mkdir -p "$(dirname "$DESKTOP_CFG")"
  "$(dirname "$UVX")/uv" run --no-project --quiet python - "$1" "$DESKTOP_CFG" "$UVX" "gephi-ai==$SERVER_VER" <<'PY'
import json, os, shutil, stat, sys, time
action, path, uvx, spec = sys.argv[1:5]
# Write through a symlinked settings file, not over the link.
path = os.path.realpath(path)
try:
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    cfg = json.loads(text) if text.strip() else {}
except FileNotFoundError:
    cfg = {}
except json.JSONDecodeError as e:
    print(f"invalid:{e}")
    sys.exit(0)
servers = cfg.setdefault("mcpServers", {})
old = servers.get("gephi-ai")
if action == "remove":
    if old is None:
        print("absent")
        sys.exit(0)
    # Remove only the entry this installer writes (one that runs uvx).
    cmd = os.path.basename(str(old.get("command", ""))).lower()
    if cmd not in ("uvx", "uvx.exe"):
        print("custom:" + str(old.get("command", "")))
        sys.exit(0)
    del servers["gephi-ai"]
    result = "removed"
else:
    # The server's old name runs the same tools; adding gephi-ai beside it
    # would list every tool twice.
    if "gephi-mcp" in servers and action != "replace":
        print("legacy")
        sys.exit(0)
    # An entry that does not run uvx is someone's own setup (a development
    # checkout, a custom launcher). Replace it only when asked to.
    cmd = os.path.basename(str((old or {}).get("command", ""))).lower()
    if old and cmd not in ("uvx", "uvx.exe") and action != "replace":
        print("custom:" + str(old.get("command", "")))
        sys.exit(0)
    servers.pop("gephi-mcp", None)
    # Keep anything else the user put in the entry, such as an env block.
    entry = {**(old or {}), "command": uvx, "args": ["--from", spec, "gephi-ai"]}
    if entry == old:
        print("current")
        sys.exit(0)
    servers["gephi-ai"] = entry
    result = "updated" if old else "added"
if os.path.exists(path):
    shutil.copy2(path, path + time.strftime(".bak-%Y%m%d-%H%M%S"))
tmp = path + ".tmp"
if os.path.lexists(tmp):
    os.remove(tmp)
# Created owner-only, so the settings are never readable by others while being written; then
# given the original file's permissions, which os.replace would otherwise not keep.
with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
if os.path.exists(path):
    os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode))
os.replace(tmp, path)
print(result)
PY
}

setup_desktop() {
  head_ "Claude Desktop"
  # Someone who installed the Gephi AI extension keeps it; a config entry
  # beside it would list every tool twice.
  if [ -f "$DESKTOP_EXT/manifest.json" ]; then
    local have
    have=$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$DESKTOP_EXT/manifest.json" | head -1)
    if [ "$have" = "$SERVER_VER" ]; then
      ok "The Gephi AI extension $have is already installed"
      done_ "Claude Desktop: extension $have (already current)"
    else
      ok "Claude Desktop has the Gephi AI extension ${have:-}"
      done_ "Claude Desktop: extension ${have:-} (update it in Settings > Extensions)"
      next_ "Claude Desktop: Settings > Extensions > Gephi AI > Update, to move to $SERVER_VER."
    fi
    return 0
  fi
  if [ "$DRY" = 1 ]; then
    say "  ${D}would add or update \"gephi-ai\" in $DESKTOP_CFG (backup kept)${N}"
    done_ "Claude Desktop: gephi-ai $SERVER_VER (dry run)"
    return 0
  fi
  local result
  result=$(desktop_edit add)
  case $result in
    custom:*|legacy)
      if [ "$result" = legacy ]; then warn "Claude Desktop runs Gephi AI under its old name, gephi-mcp"
      else warn "Claude Desktop already runs Gephi AI through your own command: ${result#custom:}"; fi
      if ask "Replace it with the standard setup? (a backup is kept)" N; then
        result=$(desktop_edit replace)
      else
        ok "Kept your own Claude Desktop setup"
        skip_ "Claude Desktop: kept your own setup"
        return 0
      fi ;;
  esac
  case $result in
    current) ok "Claude Desktop already has gephi-ai $SERVER_VER"; done_ "Claude Desktop: gephi-ai $SERVER_VER (already current)" ;;
    added|updated)
      ok "Added gephi-ai $SERVER_VER to Claude Desktop's settings (backup kept beside them)"
      done_ "Claude Desktop: gephi-ai $SERVER_VER"
      next_ "Claude Desktop: quit it fully (Cmd+Q) and reopen it to load Gephi AI." ;;
    invalid:*)
      warn "Claude Desktop's config file is not valid JSON, so it was left alone: ${result#invalid:}"
      fail_ "Claude Desktop: config file is not valid JSON; fix $DESKTOP_CFG and re-run" ;;
    *) fail_ "Claude Desktop: could not update $DESKTOP_CFG" ;;
  esac
}

# ---------- uninstall ----------

uninstall() {
  head_ "Removing Gephi AI"
  if has claude; then
    if output_has "$PLUGIN" claude plugin list; then
      run claude plugin uninstall "$PLUGIN" || warn "Claude Code did not remove the plugin; run: claude plugin uninstall $PLUGIN"
    fi
    if output_has "(^|[[:space:]])$MARKETPLACE\$" claude plugin marketplace list; then
      run claude plugin marketplace remove "$MARKETPLACE" || warn "Claude Code did not remove the marketplace; run: claude plugin marketplace remove $MARKETPLACE"
    fi
  fi
  if has codex && output_has "^${MARKETPLACE}[[:space:]]" codex plugin marketplace list; then
    run codex plugin remove "$PLUGIN" || true
    run codex plugin marketplace remove "$MARKETPLACE" || true
  fi
  if has gemini && output_has "gephi-ai" gemini mcp list; then
    run gemini mcp remove -s user gephi-ai || true
  fi
  if find_gephi; then
    find_userdir
    if [ -f "$USERDIR/modules/$MODULE_BASE.jar" ]; then
      quit_gephi
      [ "$DRY" = 1 ] || remove_tracked "$MODULE_BASE"
      ok "Removed the Gephi plugin from $USERDIR"
    fi
  fi
  if [ "$OS" = Darwin ] && [ -f "$DESKTOP_CFG" ] && grep -q '"gephi-ai"' "$DESKTOP_CFG"; then
    if [ "$DRY" = 1 ]; then say "  ${D}would remove \"gephi-ai\" from $DESKTOP_CFG${N}"
    else
      UVX=$(command -v uvx || true)
      if [ -z "$UVX" ]; then
        warn "uv is not installed, so \"gephi-ai\" was left in $DESKTOP_CFG; remove it by hand"
      else
        result=$(desktop_edit remove)
        case "$result" in
          removed) ok "Removed gephi-ai from Claude Desktop's settings (backup kept)" ;;
          custom:*) warn "Left Claude Desktop's \"gephi-ai\" entry alone: it runs your own command (${result#custom:})" ;;
        esac
      fi
    fi
  fi
  if [ -d "$DESKTOP_EXT" ]; then
    say "  Claude Desktop: remove the extension in Settings > Extensions."
  fi
  ok "Done. uv and Gephi Desktop were left installed."
}

# ---------- main ----------

usage() {
  say "Usage: install.sh [--yes] [--dry-run] [--clients claude,codex,gemini,desktop]"
  say "                  [--skip-gephi-plugin] [--version X.Y.Z] [--allow-unverified] [--open-gephi] [--no-launch] [--uninstall]"
  say "Details: https://github.com/$REPO#install"
}

main() {
  while [ $# -gt 0 ]; do
    case $1 in
      -y|--yes) YES=1 ;;
      -n|--dry-run) DRY=1 ;;
      --clients) CLIENTS=${2:-}; shift ;;
      --clients=*) CLIENTS=${1#*=} ;;
      --skip-gephi-plugin) SKIP_NBM=1 ;;
      --version) WANT_VERSION=${2:-}; shift ;;
      --version=*) WANT_VERSION=${1#*=} ;;
      --allow-unverified) ALLOW_UNVERIFIED=1 ;;
      --no-launch) NO_LAUNCH=1 ;;
      --open-gephi) OPEN_GEPHI=1 ;;
      --uninstall) UNINSTALL=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1 (try --help)" ;;
    esac
    shift
  done

  # Assistants read project settings from the current folder; work from home
  # so a folder the user happens to be in cannot change what is detected.
  cd "$HOME"

  case $OS in Darwin|Linux) ;; *) die "This script is for macOS and Linux. On Windows, use install.ps1." ;; esac
  [ "$(id -u)" = 0 ] && die "Run this as yourself, not with sudo. It installs into your home folder."
  has curl || die "curl is required."

  TMP=$(mktemp -d "${TMPDIR:-/tmp}/gephi-ai-install.XXXXXX")
  LOG=$(mktemp "${TMPDIR:-/tmp}/gephi-ai-install-$(date +%Y%m%d-%H%M%S)-XXXXXX")
  trap 'on_error $LINENO' ERR
  trap cleanup EXIT
  exec > >(tee -a "$LOG") 2>&1

  printf '%sGephi AI installer%s%s\n' "$B" "$N" "$([ "$DRY" = 1 ] && printf ' (dry run: nothing will change)')"

  if [ "$UNINSTALL" = 1 ]; then uninstall; exit 0; fi

  local detected
  detected=$(detect_clients)
  [ -n "$CLIENTS" ] || CLIENTS=$detected
  # Accept "Claude, Codex" as well as "claude,codex", and stop on a typo rather
  # than quietly setting up nothing.
  CLIENTS=$(printf '%s' "$CLIENTS" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
  local c
  for c in ${CLIENTS//,/ }; do
    case "$c" in claude|codex|gemini|desktop) ;; *) die "Unknown assistant '$c'. Choose from: claude, codex, gemini, desktop" ;; esac
  done

  read_release

  head_ "Plan"
  if [ "$SKIP_NBM" = 1 ]; then say "  • Gephi Desktop: leave alone"
  elif find_gephi && gephi_bundled_module >/dev/null; then say "  • Gephi Desktop: already includes the Gephi AI plugin"
  else say "  • Gephi Desktop: install or update the Gephi AI plugin $NBM_VER"; fi
  want claude  && say "  • Claude Code: install or update the gephi-network-analysis plugin"
  want codex   && say "  • OpenAI Codex: install or update the gephi-network-analysis plugin"
  want gemini  && say "  • Gemini CLI: register the gephi-ai server"
  want desktop && say "  • Claude Desktop: add Gephi AI $SERVER_VER to its settings"
  if [ -z "$CLIENTS" ]; then
    warn "No AI assistant found (looked for Claude Code, Codex, Gemini CLI, Claude Desktop)."
    say "    Install one, then re-run. Any other MCP client can run 'uvx gephi-ai' over stdio."
  fi
  ask "Go ahead?" Y || { say "Nothing changed."; exit 0; }

  if [ "$SKIP_NBM" = 0 ] && ensure_gephi; then install_nbm || true; fi

  if want claude || want codex || want gemini || want desktop; then ensure_uv; fi
  if want claude || want codex || want desktop; then
    head_ "Checking the Gephi AI server"
    check_server "gephi-ai==$SERVER_VER"
  fi

  # One assistant failing should not stop the others.
  local c fn rc
  for c in claude codex gemini desktop; do
    want "$c" || continue
    case $c in
      claude) has claude || { skip_ "Claude Code: not installed"; continue; }; fn=setup_claude_code ;;
      codex) has codex || { skip_ "Codex: not installed"; continue; }; fn=setup_codex ;;
      gemini) has gemini || { skip_ "Gemini CLI: not installed"; continue; }; fn=setup_gemini ;;
      desktop) [ "$OS" = Darwin ] || { skip_ "Claude Desktop: macOS only here"; continue; }; fn=setup_desktop ;;
    esac
    trap - ERR; set +e
    ( set -e; $fn )
    rc=$?
    set -e; trap 'on_error $LINENO' ERR
    [ "$rc" = 0 ] || fail_ "$c: setup failed (details above)"
  done

  [ "$SKIP_NBM" = 0 ] && check_gephi_connection

  head_ "Summary"
  sed 's/^/  /' "$TMP/summary" 2>/dev/null || true
  if [ -s "$TMP/next" ]; then
    printf '\n%sNext steps%s\n' "$B" "$N"
    sed 's/^/  • /' "$TMP/next"
  fi
  printf '\nThen, with Gephi open, ask your assistant: %s"Check if Gephi is running."%s\n' "$B" "$N"
  printf '%sLog: %s%s\n' "$D" "$LOG" "$N"
  # A non-zero exit lets scripts and CI notice a step that failed.
  if grep -q "✗" "$TMP/summary" 2>/dev/null; then exit 1; fi
}

# Tests source this file with GEPHI_AI_INSTALLER_TEST=1 to reach the functions without installing.
[ "${GEPHI_AI_INSTALLER_TEST:-}" = 1 ] || main "$@"
