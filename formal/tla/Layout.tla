----------------------------- MODULE Layout -----------------------------
(* gephi_run_layout, gephi_stop_layout and what the methods record says of each run.

   A layout runs in Gephi after its request is answered. gephi_stop_layout takes no lock, so
   its request and its answer are two steps that anything can fall between. A run with
   sync=true keeps the tool lock and polls until Gephi says no layout is running.

   MarkOnStop and WaitForStop are guards: TRUE is the rule the server follows, FALSE the rule
   it followed before. *)
EXTENDS Naturals

CONSTANTS MaxRuns, MaxStops,
          MarkOnStop,   \* gephi_stop_layout marks the run it stopped in the record
          WaitForStop   \* a sync run does not decide while a stop request is unanswered

VARIABLES layout,   \* the run in progress in Gephi; 0 when none
          truth,    \* per run: "none", "running", "finished", "stopped"
          record,   \* per run, what the methods record says: "none", "full", "stopped"
          runs, stops, sent,
          stopPc,   \* "idle", or "sent" while a stop request is unanswered
          stopHit,  \* the run that request stopped; 0 when no layout was running
          waiter,   \* the sync run being waited for; 0 when none
          before,   \* the stop count that sync run saw when it began to wait
          said      \* per run, what a sync call reported: "-", "completed", "stopped"

vars == <<layout, truth, record, runs, stops, sent, stopPc, stopHit, waiter, before, said>>
Runs == 1..MaxRuns

Init == /\ layout = 0 /\ truth = [r \in Runs |-> "none"] /\ record = [r \in Runs |-> "none"]
        /\ runs = 0 /\ stops = 0 /\ sent = 0 /\ stopPc = "idle" /\ stopHit = 0
        /\ waiter = 0 /\ before = 0 /\ said = [r \in Runs |-> "-"]

Run(sync) == /\ waiter = 0 /\ layout = 0 /\ runs < MaxRuns
             /\ runs' = runs + 1 /\ layout' = runs + 1
             /\ truth' = [truth EXCEPT ![runs + 1] = "running"]
             /\ record' = [record EXCEPT ![runs + 1] = "full"]
             /\ waiter' = IF sync THEN runs + 1 ELSE 0
             /\ before' = stops
             /\ UNCHANGED <<stops, sent, stopPc, stopHit, said>>

Finish == /\ layout # 0 /\ truth' = [truth EXCEPT ![layout] = "finished"] /\ layout' = 0
          /\ UNCHANGED <<record, runs, stops, sent, stopPc, stopHit, waiter, before, said>>

StopSend == /\ stopPc = "idle" /\ sent < MaxStops /\ sent' = sent + 1 /\ stopPc' = "sent"
            /\ stopHit' = layout /\ layout' = 0
            /\ truth' = IF layout # 0 THEN [truth EXCEPT ![layout] = "stopped"] ELSE truth
            /\ UNCHANGED <<record, runs, stops, waiter, before, said>>

StopAnswered == /\ stopPc = "sent" /\ stopPc' = "idle"
                /\ stops' = IF stopHit # 0 THEN stops + 1 ELSE stops
                \* The record's last run is marked: the record does not know which run Gephi stopped.
                /\ record' = IF MarkOnStop /\ stopHit # 0 /\ runs > 0
                               THEN [record EXCEPT ![runs] = "stopped"] ELSE record
                /\ UNCHANGED <<layout, truth, runs, sent, stopHit, waiter, before, said>>

Poll == /\ waiter # 0 /\ layout = 0
        /\ WaitForStop => stopPc = "idle"
        /\ IF stops # before
             THEN /\ said' = [said EXCEPT ![waiter] = "stopped"]
                  /\ record' = [record EXCEPT ![waiter] = "stopped"]
             ELSE /\ said' = [said EXCEPT ![waiter] = "completed"] /\ UNCHANGED record
        /\ waiter' = 0
        /\ UNCHANGED <<layout, truth, runs, stops, sent, stopPc, stopHit, before>>

Next == Run(TRUE) \/ Run(FALSE) \/ Finish \/ StopSend \/ StopAnswered \/ Poll
Spec == Init /\ [][Next]_vars

Settled == stopPc = "idle" /\ waiter = 0
(* Once nothing is in flight, the record says of every run what happened to it. *)
RecordHonest == Settled => \A r \in Runs :
                  /\ truth[r] = "stopped" => record[r] = "stopped"
                  /\ truth[r] = "finished" => record[r] = "full"
(* A sync call says "stopped" exactly when its layout was stopped. *)
SaidRight == \A r \in Runs : /\ said[r] = "stopped" => truth[r] = "stopped"
                             /\ said[r] = "completed" => truth[r] = "finished"
NeverStopped == \A r \in Runs : truth[r] # "stopped"   \* probe: a stop does happen
=============================================================================
