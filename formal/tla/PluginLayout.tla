--------------------------- MODULE PluginLayout ---------------------------
(* The Gephi plugin's staged layout settings: POST /layout/properties stores settings for a
   layout, and the next POST /layout/run of that layout with no settings of its own uses them.

   A layout has more than one accepted spelling ("forceatlas2", "ForceAtlas 2"). A run is
   refused while another layout is running. The plugin answers requests on several threads, so
   a stage and a run can interleave.

   The three constants are guards. TRUE is the rule the plugin follows, FALSE the rule it
   followed before. *)
EXTENDS Naturals

CONSTANTS MatchByLayout,   \* staged settings belong to the layout, whatever spelling named it
          KeepOnRefusal,   \* a refused run leaves staged settings in place
          OneHolder,       \* the settings and their layout are stored and taken as one value
          MaxSteps

Layouts == {"A", "B"}
Spellings == {1, 2}

VARIABLES props,    \* the layout the stored settings were made for; "none" when none
          name,     \* <<layout, spelling>> stored beside them; "none" when none
          owed,     \* the layout whose staged settings the next run that starts must use
          busy,     \* a layout is running
          stager,   \* "idle", or <<layout, spelling>> between a stage's two writes
          steps,
          lost,     \* a run started without the settings staged for it
          mixed,    \* a run started with settings made for another layout
          applied   \* some run used staged settings

vars == <<props, name, owed, busy, stager, steps, lost, mixed, applied>>

Init == /\ props = "none" /\ name = "none" /\ owed = "none" /\ busy = FALSE
        /\ stager = "idle" /\ steps = 0 /\ lost = FALSE /\ mixed = FALSE /\ applied = FALSE

Tick == steps < MaxSteps /\ steps' = steps + 1

Stage(l, sp) ==
  /\ Tick /\ stager = "idle"
  /\ props' = l
  /\ IF OneHolder THEN name' = <<l, sp>> /\ owed' = l /\ stager' = stager
                  ELSE name' = name /\ owed' = owed /\ stager' = <<l, sp>>
  /\ UNCHANGED <<busy, lost, mixed, applied>>

StageEnds ==
  /\ stager # "idle" /\ name' = stager /\ owed' = stager[1] /\ stager' = "idle"
  /\ UNCHANGED <<props, busy, steps, lost, mixed, applied>>

Match(l, sp) == /\ props # "none" /\ name # "none"
                /\ IF MatchByLayout THEN name[1] = l ELSE name = <<l, sp>>

Run(l, sp) ==
  /\ Tick
  /\ IF busy
       THEN \* refused: "Layout already running"
            /\ IF KeepOnRefusal THEN UNCHANGED <<props, name>>
                                ELSE props' = "none" /\ name' = "none"
            /\ UNCHANGED <<owed, busy, lost, mixed, applied>>
       ELSE /\ mixed' = (mixed \/ (Match(l, sp) /\ props # l))
            /\ lost' = (lost \/ (owed = l /\ ~(Match(l, sp) /\ props = l)))
            /\ applied' = (applied \/ Match(l, sp))
            /\ props' = "none" /\ name' = "none" /\ owed' = "none" /\ busy' = TRUE
  /\ UNCHANGED stager

Finish == busy /\ busy' = FALSE
          /\ UNCHANGED <<props, name, owed, stager, steps, lost, mixed, applied>>

Next == \/ \E l \in Layouts, sp \in Spellings : Stage(l, sp) \/ Run(l, sp)
        \/ StageEnds \/ Finish

Spec == Init /\ [][Next]_vars

SettingsReachRun == ~lost       \* staged settings are used by the next run of their layout
SettingsOwnLayout == ~mixed     \* a run never uses settings made for another layout
NeverApplied == ~applied        \* probe
=============================================================================
