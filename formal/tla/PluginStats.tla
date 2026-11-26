---------------------------- MODULE PluginStats ----------------------------
(* The Gephi plugin's record of running statistics.

   A request claims a statistic by name, runs it, and releases the claim when it stops waiting.
   A second request for a statistic that is claimed is refused. POST /statistics/stop copies
   the claims, then marks each one as stopped by request and cancels it. A request can stop
   waiting while its statistic is still running in Gephi: at the wait cap, or when a statistic
   does not end within the grace period after its deadline cancelled it.

   SyncStop and HoldClaim are guards. TRUE is the rule the plugin follows, FALSE the rule it
   followed before. *)
EXTENDS Naturals, FiniteSets

CONSTANTS Stats,       \* runs of one statistic, each its own instance
          SyncStop,    \* stop marks a run only while it is still claimed; release is one step
          HoldClaim,   \* a claim lasts until the statistic has ended in Gephi
          MaxStops

VARIABLES st,        \* per run: "new", "running", "ended"
          waiting,   \* per run: its request is still waiting for it
          claimed,   \* the runs recorded as running
          stopReq,   \* the runs marked as stopped by request
          rel,       \* per run: 0 not released, 1 claim removed, 2 mark removed as well
          snap,      \* the stop request's copy of the claims still to mark
          stopPc, stops, everStopped

vars == <<st, waiting, claimed, stopReq, rel, snap, stopPc, stops, everStopped>>

Init == /\ st = [s \in Stats |-> "new"] /\ waiting = [s \in Stats |-> FALSE]
        /\ claimed = {} /\ stopReq = {} /\ rel = [s \in Stats |-> 0]
        /\ snap = {} /\ stopPc = "idle" /\ stops = 0 /\ everStopped = FALSE

Start(s) == /\ st[s] = "new" /\ claimed = {}
            /\ st' = [st EXCEPT ![s] = "running"] /\ waiting' = [waiting EXCEPT ![s] = TRUE]
            /\ claimed' = {s}
            /\ UNCHANGED <<stopReq, rel, snap, stopPc, stops, everStopped>>

Ends(s) == /\ st[s] = "running" /\ st' = [st EXCEPT ![s] = "ended"]
           /\ UNCHANGED <<waiting, claimed, stopReq, rel, snap, stopPc, stops, everStopped>>

(* The request stops waiting while the statistic runs on. *)
GivesUp(s) == /\ st[s] = "running" /\ waiting[s] /\ waiting' = [waiting EXCEPT ![s] = FALSE]
              /\ UNCHANGED <<st, claimed, stopReq, rel, snap, stopPc, stops, everStopped>>

MayRelease(s) == /\ (rel[s] = 0 /\ s \in claimed) \/ rel[s] = 1
                 /\ IF HoldClaim THEN st[s] = "ended"
                                 ELSE st[s] = "ended" \/ (st[s] = "running" /\ ~waiting[s])

Release(s) ==
  /\ MayRelease(s)
  /\ IF SyncStop
       THEN claimed' = claimed \ {s} /\ stopReq' = stopReq \ {s} /\ rel' = [rel EXCEPT ![s] = 2]
       ELSE IF rel[s] = 0
              THEN claimed' = claimed \ {s} /\ stopReq' = stopReq /\ rel' = [rel EXCEPT ![s] = 1]
              ELSE claimed' = claimed /\ stopReq' = stopReq \ {s} /\ rel' = [rel EXCEPT ![s] = 2]
  /\ waiting' = [waiting EXCEPT ![s] = FALSE]
  /\ UNCHANGED <<st, snap, stopPc, stops, everStopped>>

StopCopies == /\ stopPc = "idle" /\ stops < MaxStops /\ stops' = stops + 1
              /\ snap' = claimed /\ stopPc' = "marking"
              /\ UNCHANGED <<st, waiting, claimed, stopReq, rel, everStopped>>

StopMarks == /\ stopPc = "marking"
             /\ IF snap = {}
                  THEN stopPc' = "idle" /\ UNCHANGED <<snap, stopReq, everStopped>>
                  ELSE \E s \in snap :
                         /\ snap' = snap \ {s} /\ stopPc' = stopPc
                         /\ IF SyncStop /\ s \notin claimed
                              THEN UNCHANGED <<stopReq, everStopped>>
                              ELSE stopReq' = stopReq \cup {s} /\ everStopped' = TRUE
             /\ UNCHANGED <<st, waiting, claimed, rel, stops>>

Next == \/ \E s \in Stats : Start(s) \/ Ends(s) \/ GivesUp(s) \/ Release(s)
        \/ StopCopies \/ StopMarks

Spec == Init /\ [][Next]_vars

NoStaleStop == \A s \in Stats : rel[s] = 2 => s \notin stopReq   \* no mark outlives its run
StopReaches == \A s \in Stats : st[s] = "running" => s \in claimed  \* a stop can reach every run
OneAtATime == Cardinality({s \in Stats : st[s] = "running"}) <= 1
NeverStopped == ~everStopped                                     \* probe
=============================================================================
