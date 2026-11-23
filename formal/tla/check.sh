#!/usr/bin/env bash
# TLC over the TLA+ models in this folder: every property in every configuration, against the
# expected result. An expected FAIL is a rule the server no longer follows (the row turns that
# guard off, to show the guard is needed), a probe, or a residual; if it starts passing, the
# model has lost the behaviour, and this check fails. "current" rows are the server as it ships.
#
# Needs Java 11 or later and tla2tools.jar (TLA_JAR; default ~/.local/share/tla/tla2tools.jar,
# from https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar).
# TRACES=1 prints the counterexample for each FAIL.
set -euo pipefail
cd "$(dirname "$0")"
JAR=${TLA_JAR:-$HOME/.local/share/tla/tla2tools.jar}
[[ -f "$JAR" ]] || { echo "tla: no tla2tools.jar at $JAR" >&2; exit 1; }
command -v java >/dev/null || { echo "tla: no java on PATH" >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/tla-XXXXXX")
trap 'rm -rf "$work"' EXIT
cp ./*.tla "$work/"
bad=0

# run MODULE NAME "CONSTANTS ..." PROPERTY EXPECT
run() {
  local module=$1 name=$2 consts=$3 prop=$4 expect=$5 out got
  printf 'CONSTANTS %s\nSPECIFICATION Spec\nINVARIANT %s\n' "$consts" "$prop" > "$work/m.cfg"
  out=$(cd "$work" && java -XX:+UseParallelGC -Djava.io.tmpdir="$work" -cp "$JAR" tlc2.TLC -config m.cfg \
        -workers auto -deadlock -cleanup -metadir "$work/states" "$module.tla" 2>&1 || true)
  if grep -q "No error has been found" <<< "$out"; then got=PASS
  elif grep -q "is violated" <<< "$out"; then got=FAIL
  else echo "$out" >&2; echo "tla: TLC did not finish: $module $name $prop" >&2; exit 1; fi
  local states mark
  states=$(grep -oE "[0-9,]+ distinct states found" <<< "$out" | tail -1 || true)
  if [[ "$got" == "$expect" ]]; then mark=ok; else mark=UNEXPECTED; bad=1; fi
  printf '%-9s %-14s %-16s %-4s (expected %-4s) %-10s %s\n' "$module" "$name" "$prop" "$got" "$expect" "$mark" "$states"
  if [[ "${TRACES:-}" == 1 && "$got" == FAIL ]]; then
    sed -n '/is violated/,/states generated/p' <<< "$out" | grep -E '^State [0-9]+|^/\\ ' | sed 's/^/      /'
  fi
}

# ---- Workspace: the undo snapshot, gephi_undo, what-if, compare, and the methods record
wk() { run Workspace "$1" "UndoBySource = $2 CompareResets = $3 RefuseOffOriginal = $4 MaxFaults = $5 MaxWs = 5 MaxEdits = 3" "$6" "$7"; }
#  name          source compare refuse faults property         expect
wk current       TRUE   TRUE    TRUE   2      TypeOK           PASS
wk current       TRUE   TRUE    TRUE   2      OneSnapshot      PASS
wk current       TRUE   TRUE    TRUE   2      UndoKeepsOthers  PASS
wk current       TRUE   TRUE    TRUE   2      RecordOnScreen   PASS
wk current       TRUE   TRUE    TRUE   2      ChangeOnTarget   PASS
wk current       TRUE   TRUE    TRUE   0      NeverUndone      FAIL  # probe: an undo does happen
wk current       TRUE   TRUE    TRUE   0      UndoRestores     FAIL  # residual: a change made on the "[undo]" workspace itself
wk undo-current  FALSE  TRUE    TRUE   0      UndoKeepsOthers  FAIL  # undo after a switch removed the workspace on screen
wk compare-keeps TRUE   FALSE   TRUE   1      RecordOnScreen   FAIL  # a compare that cannot switch back kept the record
wk compare-keeps TRUE   FALSE   TRUE   0      RecordOnScreen   PASS  # without a failed switch the record is right
wk no-refuse     TRUE   TRUE    FALSE  2      ChangeOnTarget   FAIL  # a failed snapshot left another workspace; the change ran on it
wk no-refuse     TRUE   TRUE    FALSE  1      ChangeOnTarget   PASS  # one failed switch is recovered

# ---- Layout: run, stop, and what the record says of each run
ly() { run Layout "$1" "MarkOnStop = $2 WaitForStop = $3 MaxRuns = $4 MaxStops = 2" "$5" "$6"; }
#  name          mark   wait   runs property       expect
ly current       TRUE   TRUE   1    RecordHonest   PASS
ly current       TRUE   TRUE   1    SaidRight      PASS
ly current       TRUE   TRUE   1    NeverStopped   FAIL  # probe: a stop does happen
ly current       TRUE   TRUE   2    RecordHonest   FAIL  # residual: a stop answered after the next layout began marks that one
ly current       TRUE   TRUE   2    SaidRight      FAIL  # residual: the same stop is counted against the next sync run
ly no-mark       FALSE  TRUE   1    RecordHonest   FAIL  # a stopped background layout was recorded as run in full
ly no-wait       TRUE   FALSE  1    SaidRight      FAIL  # a sync run decided before the stop was answered
ly no-wait       FALSE  FALSE  1    RecordHonest   FAIL  # the server before both guards

# ---- ReadGate: the tool lock and the read gate
rg() { run ReadGate "$1" "Drain = $2 Readers = {1, 2} Holders = {3, 4} Writers = {5}" "$3" "$4"; }
#  name          drain property       expect
rg current       TRUE  ReadsHeldBack  PASS
rg current       TRUE  OneAtATime     PASS
rg current       TRUE  GateReopens    PASS
rg current       TRUE  LockReleased   PASS
rg current       TRUE  CountRight     PASS
rg current       TRUE  NeverHeld      FAIL  # probe: a holder does get in
rg no-drain      FALSE ReadsHeldBack  FAIL  # a holder that does not wait for the reads inside

[[ $bad == 0 ]] && echo "tla: all as expected" || { echo "tla: FAILED: unexpected results" >&2; exit 1; }
