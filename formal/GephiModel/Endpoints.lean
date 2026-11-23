/-
  mcp-server/stats_integrity.py: mutates_graph and replaces_graph.

  GephiClient.request retires the cached graph facts before any call for which mutates_graph
  holds, and starts a new methods record only inside that branch, when replaces_graph holds too.
  So a call that replaces the graph must also count as mutating it, or the record would go on
  describing a graph that is no longer on screen. `replaces_implies_mutates` proves it for every
  path. tests/test_formal_conformance.py holds the Python tuples to the three lists below.
-/
namespace GephiModel

def nonStructural : List String := [
  "/statistics/", "/export/", "/appearance/", "/layout/", "/preview/",
  "/datalab/frequencies", "/datalab/duplicates",
  "/graph/nodes/attributes", "/graph/node/attributes", "/graph/columns/add",
  "/graph/nodes/positions", "/graph/node/position",
  "/view/focus", "/graph/shortest-path", "/selection", "/health"]

def replacesPrefixes : List String := [
  "/graph/clear", "/graph/generate", "/workspace/", "/project/", "/import/", "/time/slice"]

def keepsGraph : List String := ["/workspace/rename", "/project/save"]

def chars (l : List String) : List (List Char) := l.map String.toList

/-- Python's `any(path.startswith(prefix) for prefix in prefixes)`. -/
def startsWithAny (path : List Char) (prefixes : List (List Char)) : Bool :=
  prefixes.any (fun p => p.isPrefixOf path)

def mutatesGraph (isGet : Bool) (path : List Char) : Bool :=
  !isGet && !startsWithAny path (chars nonStructural)

def replacesGraph (isGet : Bool) (path : List Char) : Bool :=
  !isGet && !startsWithAny path (chars keepsGraph) && startsWithAny path (chars replacesPrefixes)

/-- Two prefixes of one path: one of them is a prefix of the other. -/
theorem prefixes_comparable {a b p : List Char}
    (ha : a.isPrefixOf p = true) (hb : b.isPrefixOf p = true) :
    a.isPrefixOf b = true ∨ b.isPrefixOf a = true := by
  induction p generalizing a b with
  | nil =>
    cases a with
    | nil => left; cases b <;> rfl
    | cons _ _ => simp [List.isPrefixOf] at ha
  | cons x xs ih =>
    cases a with
    | nil => left; cases b <;> rfl
    | cons y ys =>
      cases b with
      | nil => right; rfl
      | cons z zs =>
        simp only [List.isPrefixOf, Bool.and_eq_true, beq_iff_eq] at ha hb ⊢
        obtain ⟨h1, h2⟩ := ha
        obtain ⟨h3, h4⟩ := hb
        subst h1; subst h3
        rcases ih h2 h4 with h | h
        · left; exact ⟨rfl, h⟩
        · right; exact ⟨rfl, h⟩

/-- No graph-replacing prefix and no non-structural prefix is a prefix of the other. -/
theorem lists_disjoint :
    (chars replacesPrefixes).all (fun r => (chars nonStructural).all (fun n =>
      !r.isPrefixOf n && !n.isPrefixOf r)) = true := by decide

theorem replaces_implies_mutates (isGet : Bool) (path : List Char)
    (h : replacesGraph isGet path = true) : mutatesGraph isGet path = true := by
  simp only [replacesGraph, mutatesGraph, Bool.and_eq_true, Bool.not_eq_true',
    startsWithAny, List.any_eq_true] at h ⊢
  obtain ⟨⟨hget, _⟩, r, hr, hrp⟩ := h
  refine ⟨hget, ?_⟩
  cases hn : (chars nonStructural).any (fun p => p.isPrefixOf path) with
  | false => rfl
  | true =>
    obtain ⟨n, hnm, hnp⟩ := List.any_eq_true.mp hn
    have hd := lists_disjoint
    rw [List.all_eq_true] at hd
    have hd2 := hd r hr
    rw [List.all_eq_true] at hd2
    have hd3 := hd2 n hnm
    simp only [Bool.and_eq_true, Bool.not_eq_true'] at hd3
    rcases prefixes_comparable hrp hnp with c | c
    · rw [hd3.1] at c; exact absurd c (by decide)
    · rw [hd3.2] at c; exact absurd c (by decide)

theorem get_never_mutates (path : List Char) : mutatesGraph true path = false := rfl
theorem get_never_replaces (path : List Char) : replacesGraph true path = false := rfl

/-- A path no list has seen is assumed to change the graph. -/
theorem unknown_path_mutates (path : List Char)
    (h : startsWithAny path (chars nonStructural) = false) : mutatesGraph false path = true := by
  simp [mutatesGraph, h]

/-- A rename or a save never ends the record, whatever else the path matches. -/
theorem keeps_wins (isGet : Bool) (path : List Char)
    (h : startsWithAny path (chars keepsGraph) = true) : replacesGraph isGet path = false := by
  simp [replacesGraph, h]

end GephiModel
