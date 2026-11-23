/-
  mcp-server/session_ledger.py: the methods record.

  An entry is modelled by what the summary reads from it: its kind and, for a visual mapping,
  its channel. `legend_one_per_channel` proves a legend never describes one channel twice;
  `new_graph_is_empty` and `earlier_bounded` prove a change of graph starts an empty record and
  keeps at most twenty earlier ones; `forget_removes` proves a reset channel leaves the legend.
-/
namespace GephiModel

inductive Channel | nodeColour | nodeSize | edgeColour | edgeWidth
  deriving DecidableEq, Repr

inductive Entry
  | mapping (ch : Channel) (tag : Nat)   -- tag stands for the column and palette
  | layout (tag : Nat) (stopped : Bool)
  | statistic (tag : Nat)
  | analysis (tag : Nat)
  deriving DecidableEq, Repr

def Entry.channel? : Entry → Option Channel
  | .mapping ch _ => some ch
  | _ => none

/-- Python's dict keyed by channel: a later mapping replaces the value and keeps the place. -/
def put (items : List (Channel × Nat)) (ch : Channel) (tag : Nat) : List (Channel × Nat) :=
  match items with
  | [] => [(ch, tag)]
  | (c, t) :: rest => if c = ch then (c, tag) :: rest else (c, t) :: put rest ch tag

def legendFrom (acc : List (Channel × Nat)) : List Entry → List (Channel × Nat)
  | [] => acc
  | .mapping ch tag :: rest => legendFrom (put acc ch tag) rest
  | _ :: rest => legendFrom acc rest

def legendItems (entries : List Entry) : List (Channel × Nat) := legendFrom [] entries

def earlierKept : Nat := 20

structure Ledger where
  entries : List Entry
  earlier : List (List Entry)

def Ledger.startNewGraph (l : Ledger) : Ledger :=
  if l.entries.isEmpty then { l with entries := [] }
  else
    let e := l.earlier ++ [l.entries]
    { entries := [], earlier := e.drop (e.length - earlierKept) }

def Ledger.forgetChannel (l : Ledger) (ch : Channel) : Ledger :=
  { l with entries := l.entries.filter (fun e => e.channel? != some ch) }

theorem put_keys (items : List (Channel × Nat)) (ch : Channel) (tag : Nat) :
    (put items ch tag).map Prod.fst =
      if ch ∈ items.map Prod.fst then items.map Prod.fst else items.map Prod.fst ++ [ch] := by
  induction items with
  | nil => simp [put]
  | cons hd tl ih =>
    obtain ⟨c, t⟩ := hd
    by_cases hc : c = ch
    · simp [put, hc]
    · have hne : ¬ ch = c := fun h => hc h.symm
      simp only [put, hc, ite_false, List.map_cons, ih, List.mem_cons, hne, false_or]
      split <;> simp

theorem put_nodup (items : List (Channel × Nat)) (ch : Channel) (tag : Nat)
    (h : (items.map Prod.fst).Nodup) : ((put items ch tag).map Prod.fst).Nodup := by
  rw [put_keys]
  split
  · exact h
  · rename_i hn
    rw [List.nodup_append]
    refine ⟨h, by simp, ?_⟩
    intro a ha b hb
    simp only [List.mem_singleton] at hb
    subst hb
    intro hab
    subst hab
    exact hn ha

theorem legendFrom_nodup (acc : List (Channel × Nat)) (entries : List Entry)
    (h : (acc.map Prod.fst).Nodup) : ((legendFrom acc entries).map Prod.fst).Nodup := by
  induction entries generalizing acc with
  | nil => exact h
  | cons e rest ih =>
    cases e with
    | mapping ch tag => exact ih _ (put_nodup acc ch tag h)
    | layout _ _ => exact ih _ h
    | statistic _ => exact ih _ h
    | analysis _ => exact ih _ h

/-- A legend holds at most one item per visual channel. -/
theorem legend_one_per_channel (entries : List Entry) :
    ((legendItems entries).map Prod.fst).Nodup :=
  legendFrom_nodup [] entries (by simp)

theorem new_graph_is_empty (l : Ledger) : l.startNewGraph.entries = [] := by
  unfold Ledger.startNewGraph
  split <;> rfl

theorem earlier_bounded (l : Ledger) (h : l.earlier.length ≤ earlierKept) :
    l.startNewGraph.earlier.length ≤ earlierKept := by
  unfold Ledger.startNewGraph
  split
  · exact h
  · simp only [List.length_drop, List.length_append, List.length_singleton, earlierKept] at *
    omega

/-- A record that was not empty is kept as the newest earlier section. -/
theorem new_graph_keeps_record (l : Ledger) (h : l.entries.isEmpty = false) :
    l.startNewGraph.earlier.getLast? = some l.entries := by
  unfold Ledger.startNewGraph
  simp only [h, Bool.false_eq_true, ite_false]
  rw [List.getLast?_drop]
  simp [earlierKept]
  omega

theorem put_mem_key (items : List (Channel × Nat)) (ch : Channel) (tag : Nat) (c : Channel)
    (h : c ∈ (put items ch tag).map Prod.fst) : c = ch ∨ c ∈ items.map Prod.fst := by
  rw [put_keys] at h
  split at h
  · exact Or.inr h
  · simp only [List.mem_append, List.mem_singleton] at h
    exact h.symm

theorem legendFrom_keys (acc : List (Channel × Nat)) (entries : List Entry) (c : Channel)
    (h : c ∈ (legendFrom acc entries).map Prod.fst) :
    c ∈ acc.map Prod.fst ∨ ∃ e ∈ entries, e.channel? = some c := by
  induction entries generalizing acc with
  | nil => exact Or.inl h
  | cons e rest ih =>
    cases e with
    | mapping ch tag =>
      rcases ih _ h with h1 | ⟨e, he, hc⟩
      · rcases put_mem_key acc ch tag c h1 with h2 | h2
        · subst h2; exact Or.inr ⟨_, List.mem_cons_self, rfl⟩
        · exact Or.inl h2
      · exact Or.inr ⟨e, List.mem_cons_of_mem _ he, hc⟩
    | layout a b =>
      rcases ih _ h with h1 | ⟨e, he, hc⟩
      · exact Or.inl h1
      · exact Or.inr ⟨e, List.mem_cons_of_mem _ he, hc⟩
    | statistic a =>
      rcases ih _ h with h1 | ⟨e, he, hc⟩
      · exact Or.inl h1
      · exact Or.inr ⟨e, List.mem_cons_of_mem _ he, hc⟩
    | analysis a =>
      rcases ih _ h with h1 | ⟨e, he, hc⟩
      · exact Or.inl h1
      · exact Or.inr ⟨e, List.mem_cons_of_mem _ he, hc⟩

/-- After a channel is reset, the legend no longer describes it. -/
theorem forget_removes (l : Ledger) (ch : Channel) :
    ch ∉ (legendItems (l.forgetChannel ch).entries).map Prod.fst := by
  intro h
  rcases legendFrom_keys [] _ ch h with h1 | ⟨e, he, hc⟩
  · simp at h1
  · simp only [Ledger.forgetChannel, List.mem_filter] at he
    simp [hc] at he

end GephiModel
