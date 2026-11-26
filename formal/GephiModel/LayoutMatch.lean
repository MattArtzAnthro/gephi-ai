/-
  gephi-ai-plugin GephiControlService.java: bestLayoutMatch.

  A layout is found by name: the first name that equals the query wins, wherever it stands in the
  list; with no equal name, the first name that contains the query. `exact` and `sub` stand for
  those two tests on one name. The theorems hold for any tests where an equal name also contains
  the query, which is true of string equality and containment.
-/
namespace GephiModel

def firstIdx {α : Type} (p : α → Bool) : List α → Nat → Option Nat
  | [], _ => none
  | a :: as, i => if p a then some i else firstIdx p as (i + 1)

def bestMatch {α : Type} (exact sub : α → Bool) (names : List α) : Option Nat :=
  match firstIdx exact names 0 with
  | some i => some i
  | none => firstIdx sub names 0

theorem firstIdx_none {α : Type} (p : α → Bool) (l : List α) (k : Nat) :
    firstIdx p l k = none ↔ ∀ a ∈ l, p a = false := by
  induction l generalizing k with
  | nil => simp [firstIdx]
  | cons a as ih =>
    unfold firstIdx
    cases h : p a with
    | true => simp [h]
    | false => simp [h, ih]

theorem firstIdx_range {α : Type} (p : α → Bool) (l : List α) (k i : Nat)
    (h : firstIdx p l k = some i) : k ≤ i ∧ i < k + l.length := by
  induction l generalizing k with
  | nil => simp [firstIdx] at h
  | cons a as ih =>
    unfold firstIdx at h
    cases hp : p a with
    | true =>
      simp [hp] at h
      subst h
      simp
    | false =>
      simp [hp] at h
      have := ih (k + 1) h
      simp only [List.length_cons]
      omega

/-- The index found names a layout in the list. -/
theorem match_in_range {α : Type} (exact sub : α → Bool) (names : List α) (i : Nat)
    (h : bestMatch exact sub names = some i) : i < names.length := by
  unfold bestMatch at h
  cases he : firstIdx exact names 0 with
  | some j =>
    simp [he] at h
    subst h
    have := firstIdx_range exact names 0 j he
    omega
  | none =>
    simp [he] at h
    have := firstIdx_range sub names 0 i h
    omega

/-- An equal name wins over any name that only contains the query, even one listed earlier. -/
theorem exact_wins {α : Type} (exact sub : α → Bool) (names : List α)
    (h : ∃ a ∈ names, exact a = true) :
    bestMatch exact sub names = firstIdx exact names 0 := by
  unfold bestMatch
  cases he : firstIdx exact names 0 with
  | some j => rfl
  | none =>
    have hn := (firstIdx_none exact names 0).mp he
    obtain ⟨a, ha, hx⟩ := h
    have := hn a ha
    simp [hx] at this

/-- No layout is found exactly when no name contains the query. -/
theorem no_match_iff {α : Type} (exact sub : α → Bool) (names : List α)
    (hsub : ∀ a, exact a = true → sub a = true) :
    bestMatch exact sub names = none ↔ ∀ a ∈ names, sub a = false := by
  unfold bestMatch
  cases he : firstIdx exact names 0 with
  | some j =>
    simp only [reduceCtorEq, false_iff]
    intro hall
    have hr := firstIdx_range exact names 0 j he
    have hne : ¬ (∀ a ∈ names, exact a = false) := by
      intro hn
      have := (firstIdx_none exact names 0).mpr hn
      simp [he] at this
    apply hne
    intro a ha
    cases hx : exact a with
    | false => rfl
    | true =>
      have := hsub a hx
      simp [hall a ha] at this
  | none => exact firstIdx_none sub names 0

end GephiModel
