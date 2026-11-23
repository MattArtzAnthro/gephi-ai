/-
  mcp-server/gephi_mcp.py: _new_copy_id and _new_ids.

  After a workspace duplicate, the snapshot and the what-if must find the copy before they rename,
  edit or delete anything. `copy_is_new` proves the workspace they pick is never the original,
  never one that existed before the duplicate, and is in the list just read.
-/
namespace GephiModel

def newIds (before after : List Nat) : List Nat :=
  after.filter (fun i => !before.contains i)

def newCopyId (before after : List Nat) (orig : Nat) (reported : Option Nat) : Option Nat :=
  match reported with
  | some r => if r != orig && !before.contains r && after.contains r then some r else none
  | none =>
    match newIds before after with
    | [x] => if x != orig then some x else none
    | _ => none

theorem copy_is_new {before after : List Nat} {orig : Nat} {reported : Option Nat} {c : Nat}
    (h : newCopyId before after orig reported = some c) :
    c ≠ orig ∧ c ∉ before ∧ c ∈ after := by
  unfold newCopyId at h
  cases reported with
  | some r =>
    simp only at h
    split at h
    · rename_i hc
      simp only [Bool.and_eq_true, bne_iff_ne, Bool.not_eq_true', List.contains_eq_mem,
        decide_eq_false_iff_not, decide_eq_true_eq, Option.some.injEq] at hc h
      subst h
      exact ⟨hc.1.1, hc.1.2, hc.2⟩
    · cases h
  | none =>
    simp only at h
    split at h
    · rename_i x hx
      split at h
      · rename_i hne
        simp only [Option.some.injEq] at h
        subst h
        have hm : x ∈ newIds before after := by rw [hx]; simp
        simp only [newIds, List.mem_filter, Bool.not_eq_true', List.contains_eq_mem,
          decide_eq_false_iff_not] at hm
        exact ⟨by simpa using hne, hm.2, hm.1⟩
      · cases h
    · cases h

/-- When Gephi reports the copy's id, no other workspace is ever taken in its place. -/
theorem reported_or_nothing {before after : List Nat} {orig r c : Nat}
    (h : newCopyId before after orig (some r) = some c) : c = r := by
  unfold newCopyId at h
  simp only at h
  split at h
  · simpa using h.symm
  · cases h

/-- With no id reported, two new workspaces are never guessed between. -/
theorem two_new_is_nothing {before after : List Nat} {orig a b : Nat} {rest : List Nat}
    (h : newIds before after = a :: b :: rest) : newCopyId before after orig none = none := by
  simp [newCopyId, h]

end GephiModel
