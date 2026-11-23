---------------------------- MODULE ReadGate ----------------------------
(* The tool lock and the read gate in mcp-server/gephi_mcp.py (_one_at_a_time, _ReadGate).

   Writers take the tool lock. Holders (gephi_whatif, gephi_compare_workspaces) take the lock,
   close the gate, wait for the reads inside to leave, and only then switch workspaces. Reads
   take no lock and pass the gate while it is open. Any waiting call can be cancelled.

   Drain is the guard that makes a holder wait for the reads already inside. *)
EXTENDS Naturals, FiniteSets

CONSTANTS Readers, Holders, Writers, Drain

VARIABLES pc, lock, open, inside   \* inside: reads counted by the gate

vars == <<pc, lock, open, inside>>
Procs == Readers \cup Holders \cup Writers

Init == pc = [p \in Procs |-> "new"] /\ lock = 0 /\ open = TRUE /\ inside = 0

ReadEnter(p) == /\ p \in Readers /\ pc[p] = "new" /\ open
                /\ pc' = [pc EXCEPT ![p] = "in"] /\ inside' = inside + 1 /\ UNCHANGED <<lock, open>>
\* Leaving and being cancelled both run the same finally block.
ReadLeave(p) == /\ p \in Readers /\ pc[p] = "in"
                /\ pc' = [pc EXCEPT ![p] = "done"] /\ inside' = inside - 1 /\ UNCHANGED <<lock, open>>
Cancel(p) == /\ pc[p] = "new" /\ pc' = [pc EXCEPT ![p] = "done"] /\ UNCHANGED <<lock, open, inside>>

Lock(p) == /\ p \in Holders \cup Writers /\ pc[p] = "new" /\ lock = 0 /\ lock' = p
           /\ pc' = [pc EXCEPT ![p] = IF p \in Holders THEN "closing" ELSE "in"]
           /\ UNCHANGED <<open, inside>>
Close(p) == /\ p \in Holders /\ pc[p] = "closing" /\ open' = FALSE
            /\ pc' = [pc EXCEPT ![p] = "draining"] /\ UNCHANGED <<lock, inside>>
Enter(p) == /\ p \in Holders /\ pc[p] = "draining" /\ (Drain => inside = 0)
            /\ pc' = [pc EXCEPT ![p] = "in"] /\ UNCHANGED <<lock, open, inside>>
\* A holder that finishes, or is cancelled while draining or inside, opens the gate and unlocks.
HolderLeave(p) == /\ p \in Holders /\ pc[p] \in {"draining", "in"} /\ open' = TRUE /\ lock' = 0
                  /\ pc' = [pc EXCEPT ![p] = "done"] /\ UNCHANGED inside
HolderCancelEarly(p) == /\ p \in Holders /\ pc[p] = "closing" /\ lock' = 0
                        /\ pc' = [pc EXCEPT ![p] = "done"] /\ UNCHANGED <<open, inside>>
WriterLeave(p) == /\ p \in Writers /\ pc[p] = "in" /\ lock' = 0
                  /\ pc' = [pc EXCEPT ![p] = "done"] /\ UNCHANGED <<open, inside>>

Next == \E p \in Procs : ReadEnter(p) \/ ReadLeave(p) \/ Cancel(p) \/ Lock(p) \/ Close(p)
                         \/ Enter(p) \/ HolderLeave(p) \/ HolderCancelEarly(p) \/ WriterLeave(p)
Spec == Init /\ [][Next]_vars

In(S) == {p \in S : pc[p] = "in"}
(* No read runs while a holder has switched workspaces. *)
ReadsHeldBack == In(Holders) # {} => In(Readers) = {}
OneAtATime == Cardinality(In(Holders) \cup In(Writers) \cup {p \in Holders : pc[p] \in {"closing", "draining"}}) <= 1
(* The gate is never left shut with no holder to open it, and the count matches the reads inside. *)
GateReopens == ~open => \E p \in Holders : pc[p] \in {"draining", "in"}
LockReleased == lock # 0 => pc[lock] \in {"closing", "draining", "in"}
CountRight == inside = Cardinality(In(Readers))
NeverHeld == In(Holders) = {}   \* probe: a holder does get in
=============================================================================
