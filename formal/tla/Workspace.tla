---------------------------- MODULE Workspace ----------------------------
(* The undo snapshot, gephi_undo, gephi_whatif, gephi_compare_workspaces and the methods
   record (the ledger), as mcp-server/gephi_mcp.py drives Gephi's workspaces.

   Tools that change the graph run one at a time (the tool lock, see ReadGate.tla), so each
   tool is one step here. A workspace switch can fail (Gephi's interface thread is busy);
   MaxFaults bounds how many do.

   The three constants named Undo..., Compare... and Refuse... are guards. TRUE is the rule the
   server follows; FALSE is the rule it followed before, kept so the check shows each guard is
   needed. *)
EXTENDS Naturals, FiniteSets

CONSTANTS MaxWs,             \* workspaces ever made
          MaxEdits,          \* graph-changing calls
          MaxFaults,         \* workspace switches that fail
          UndoBySource,      \* gephi_undo removes the workspace the snapshot was copied from
          CompareResets,     \* a compare that cannot switch back ends the methods record
          RefuseOffOriginal  \* no change is made when a failed snapshot left another workspace on screen

VARIABLES ws,          \* workspaces that exist
          kind,        \* "work", or "snap" for the one named "[undo] ..."
          src,         \* for a snapshot: the workspace it was copied from
          dirty,       \* a snapshot edited since it was taken
          cur,         \* the workspace on screen
          made, edits, faults,
          ledger,      \* the workspace the methods record describes; 0 when the record is empty
          wrongDelete, \* gephi_undo removed a workspace that was not the snapshot's source
          badRestore,  \* gephi_undo reported a restore from a snapshot edited since it was taken
          wrongTarget  \* a change landed on a workspace other than the one on screen at the call

vars == <<ws, kind, src, dirty, cur, made, edits, faults, ledger, wrongDelete, badRestore, wrongTarget>>
Ids == 1..MaxWs
Snaps == {w \in ws : kind[w] = "snap"}

Init == /\ ws = {1} /\ kind = [i \in Ids |-> "work"] /\ src = [i \in Ids |-> 0]
        /\ dirty = [i \in Ids |-> FALSE] /\ cur = 1 /\ made = 1 /\ edits = 0 /\ faults = 0
        /\ ledger = 0 /\ wrongDelete = FALSE /\ badRestore = FALSE /\ wrongTarget = FALSE

(* A tool that takes the undo snapshot and then changes the graph. *)
Change ==
  /\ edits < MaxEdits /\ edits' = edits + 1
  /\ \/ \* On the snapshot itself: the snapshot is refused and the change goes ahead on it.
        /\ kind[cur] = "snap"
        /\ dirty' = [dirty EXCEPT ![cur] = TRUE]
        /\ UNCHANGED <<ws, kind, src, cur, made, faults, ledger, wrongDelete, badRestore, wrongTarget>>
     \/ \* The snapshot is taken: the old one goes, the copy is named, the original is on screen.
        /\ kind[cur] = "work" /\ made < MaxWs
        /\ LET n == made + 1 IN
             /\ ws' = (ws \ Snaps) \cup {n}
             /\ kind' = [kind EXCEPT ![n] = "snap"]
             /\ src' = [src EXCEPT ![n] = cur]
             /\ dirty' = [dirty EXCEPT ![n] = FALSE]
             /\ made' = n
        /\ UNCHANGED <<cur, faults, ledger, wrongDelete, badRestore, wrongTarget>>
     \/ \* The switch back fails once; the cleanup's switch works and the copy is removed.
        /\ kind[cur] = "work" /\ made < MaxWs /\ faults < MaxFaults
        /\ ws' = ws \ Snaps /\ made' = made + 1 /\ faults' = faults + 1
        /\ UNCHANGED <<kind, src, dirty, cur, ledger, wrongDelete, badRestore, wrongTarget>>
     \/ \* Both switches fail; the copy is removed while on screen and Gephi shows another.
        /\ kind[cur] = "work" /\ made < MaxWs /\ faults + 2 <= MaxFaults
        /\ ws' = ws \ Snaps /\ made' = made + 1 /\ faults' = faults + 2
        /\ ledger' = 0
        /\ \E c \in ws \ Snaps :
             /\ cur' = c
             /\ wrongTarget' = (wrongTarget \/ (c # cur /\ ~RefuseOffOriginal))
        /\ UNCHANGED <<kind, src, dirty, wrongDelete, badRestore>>

Undo ==
  \E s \in Snaps :
    /\ badRestore' = (badRestore \/ dirty[s])
    /\ kind' = [kind EXCEPT ![s] = "work"]
    /\ IF cur = s
         THEN UNCHANGED <<ws, cur, ledger, wrongDelete>>
         ELSE LET victim == IF UndoBySource THEN src[s] ELSE cur IN
                /\ ws' = ws \ {victim}
                /\ wrongDelete' = (wrongDelete \/ (victim \in ws /\ victim # src[s]))
                /\ cur' = s /\ ledger' = 0
    /\ UNCHANGED <<src, dirty, made, edits, faults, wrongTarget>>

Switch == \E w \in ws \ {cur} :
            /\ cur' = w /\ ledger' = 0
            /\ UNCHANGED <<ws, kind, src, dirty, made, edits, faults, wrongDelete, badRestore, wrongTarget>>

NewWorkspace == /\ made < MaxWs /\ made' = made + 1 /\ ws' = ws \cup {made + 1}
                /\ cur' = made + 1 /\ ledger' = 0
                /\ UNCHANGED <<kind, src, dirty, edits, faults, wrongDelete, badRestore, wrongTarget>>

Style == /\ ledger' = cur
         /\ UNCHANGED <<ws, kind, src, dirty, cur, made, edits, faults, wrongDelete, badRestore, wrongTarget>>

(* gephi_compare_workspaces reads another workspace by switching to it and back. *)
Compare == \E w \in ws \ {cur} :
             \/ UNCHANGED vars
             \/ /\ faults < MaxFaults /\ faults' = faults + 1 /\ cur' = w
                /\ ledger' = IF CompareResets THEN 0 ELSE ledger
                /\ UNCHANGED <<ws, kind, src, dirty, made, edits, wrongDelete, badRestore, wrongTarget>>

(* gephi_whatif works on a scratch copy and removes it. If the switch back fails, the copy is
   removed while on screen, Gephi shows some workspace, and the record ends. *)
WhatIf == \/ UNCHANGED vars
          \/ /\ faults < MaxFaults /\ faults' = faults + 1 /\ ledger' = 0
             /\ \E c \in ws : cur' = c
             /\ UNCHANGED <<ws, kind, src, dirty, made, edits, wrongDelete, badRestore, wrongTarget>>

Next == Change \/ Undo \/ Switch \/ NewWorkspace \/ Style \/ Compare \/ WhatIf
Spec == Init /\ [][Next]_vars

TypeOK == cur \in ws /\ ws \subseteq Ids /\ ledger \in ws \cup {0}
OneSnapshot == Cardinality(Snaps) <= 1
UndoKeepsOthers == ~wrongDelete
UndoRestores == ~badRestore
ChangeOnTarget == ~wrongTarget
RecordOnScreen == ledger # 0 => ledger = cur
NeverUndone == \A w \in ws : kind[w] = "work" => src[w] = 0   \* probe: an undo does happen
=============================================================================
