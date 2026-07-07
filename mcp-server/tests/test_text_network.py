"""Tests for text_network.py — pure logic, no Gephi or MCP involved at all."""

import text_network


def test_tokenize_lowercases_and_strips_punctuation():
    tokens = text_network.tokenize("Hello, World! It's a test-case.")
    assert tokens == ["hello", "world", "it's", "a", "test-case"]


def test_stopwords_are_removed():
    graph = text_network.build_cooccurrence_graph("the cat sat on the mat")
    ids = {n["id"] for n in graph["nodes"]}
    assert "the" not in ids
    assert "on" not in ids
    assert "cat" in ids
    assert "mat" in ids
    # "sat" lemmatizes to "sit" when lemmatization is available; accept either
    # so this test doesn't depend on whether NLTK's data is installed.
    assert ("sat" in ids) or ("sit" in ids)


def test_lemmatization_merges_inflected_forms_when_available():
    if not text_network.LEMMATIZATION_AVAILABLE:
        import pytest
        pytest.skip("NLTK wordnet/tagger data not installed in this environment")
    # Regular inflections merge reliably once correctly POS-tagged. Note:
    # POS tagging is statistical, not perfect — an irregular past tense like
    # "ran" can get mistagged as a noun in a short, ambiguous sentence and
    # stay unmerged. That's a real characteristic of the tagger, not this
    # module, so this test sticks to forms that tag reliably rather than
    # asserting perfection on every irregular verb.
    graph = text_network.build_cooccurrence_graph("the dogs are running and jumping")
    ids = {n["id"] for n in graph["nodes"]}
    assert "dog" in ids and "dogs" not in ids
    assert "run" in ids and "running" not in ids
    assert graph["stats"]["lemmatization"] == "active"


def test_extra_stopwords_match_regardless_of_inflected_form_typed():
    if not text_network.LEMMATIZATION_AVAILABLE:
        import pytest
        pytest.skip("NLTK wordnet/tagger data not installed in this environment")
    # User types "replied" (past tense); the text contains "reply" (base
    # form) via a different sentence — both should be filtered since they
    # share a lemma.
    graph = text_network.build_cooccurrence_graph(
        "the participant replied quickly then chose to reply again",
        extra_stopwords=["replied"],
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "reply" not in ids
    assert "replied" not in ids


def test_frequency_attribute_counts_occurrences():
    graph = text_network.build_cooccurrence_graph("dog cat dog bird dog cat")
    freq = {n["id"]: n["attributes"]["frequency"] for n in graph["nodes"]}
    assert freq["dog"] == 3
    assert freq["cat"] == 2
    assert freq["bird"] == 1


def test_adjacent_words_get_stronger_edge_than_distant_ones():
    # window_size=3: "dog cat bird" -> dog-cat distance 1 (weight 2),
    # dog-bird distance 2 (weight 1), cat-bird distance 1 (weight 2)
    graph = text_network.build_cooccurrence_graph("dog cat bird", window_size=3)
    weights = {tuple(sorted((e["source"], e["target"]))): e["weight"] for e in graph["edges"]}
    assert weights[("cat", "dog")] == 2.0
    assert weights[("bird", "dog")] == 1.0
    assert weights[("bird", "cat")] == 2.0


def test_repeated_cooccurrence_aggregates_into_one_edge():
    # "dog cat" appears twice adjacently; the edge weight should sum, and
    # there should be exactly one edge between them, not two.
    graph = text_network.build_cooccurrence_graph("dog cat dog cat", window_size=2)
    dog_cat_edges = [e for e in graph["edges"]
                     if {e["source"], e["target"]} == {"dog", "cat"}]
    assert len(dog_cat_edges) == 1
    # 3 adjacent (dog,cat) pairs in "dog cat dog cat" at window_size=2 (weight 1 each) = 3.0
    assert dog_cat_edges[0]["weight"] == 3.0


def test_edges_are_undirected():
    graph = text_network.build_cooccurrence_graph("dog cat")
    assert all(e["directed"] is False for e in graph["edges"])


def test_min_edge_weight_prunes_weak_edges():
    graph = text_network.build_cooccurrence_graph(
        "dog cat bird fish tree", window_size=5, min_edge_weight=3.0
    )
    assert all(e["weight"] >= 3.0 for e in graph["edges"])


def test_extra_stopwords_are_respected():
    graph = text_network.build_cooccurrence_graph(
        "interviewer said the participant replied", extra_stopwords=["interviewer", "replied"]
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "interviewer" not in ids
    assert "replied" not in ids
    assert "participant" in ids


def test_empty_text_produces_empty_graph():
    graph = text_network.build_cooccurrence_graph("the a an")
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["stats"]["unique_words"] == 0


def test_stats_report_filtering_counts():
    graph = text_network.build_cooccurrence_graph("the dog and the cat")
    assert graph["stats"]["raw_word_count"] == 5
    assert graph["stats"]["kept_word_count"] == 2
    assert graph["stats"]["words_filtered"] == 3


def test_window_size_must_be_at_least_two():
    import pytest
    with pytest.raises(ValueError):
        text_network.build_cooccurrence_graph("dog cat", window_size=1)


def test_document_list_does_not_bridge_window_across_boundary():
    # "dog cat" / "bird fish": as one concatenated string at window_size=3,
    # "cat" and "bird" would land one token apart and get an edge. Passed as
    # two separate documents, that edge must never form.
    graph = text_network.build_cooccurrence_graph(["dog cat", "bird fish"], window_size=3)
    pairs = {tuple(sorted((e["source"], e["target"]))) for e in graph["edges"]}
    assert ("bird", "cat") not in pairs
    assert ("cat", "fish") not in pairs
    assert ("dog", "bird") not in pairs
    assert ("dog", "fish") not in pairs
    assert ("cat", "dog") in pairs
    assert ("bird", "fish") in pairs


def test_document_list_matches_single_document_semantics():
    # A one-item list must behave identically to passing that string directly.
    as_list = text_network.build_cooccurrence_graph(["dog cat bird"], window_size=3)
    as_str = text_network.build_cooccurrence_graph("dog cat bird", window_size=3)
    weights_list = {tuple(sorted((e["source"], e["target"]))): e["weight"] for e in as_list["edges"]}
    weights_str = {tuple(sorted((e["source"], e["target"]))): e["weight"] for e in as_str["edges"]}
    assert weights_list == weights_str


def test_document_count_reported_in_stats():
    graph = text_network.build_cooccurrence_graph(["dog cat", "bird fish", "tree leaf"])
    assert graph["stats"]["document_count"] == 3
    single = text_network.build_cooccurrence_graph("dog cat")
    assert single["stats"]["document_count"] == 1


def test_frequency_aggregates_across_documents():
    graph = text_network.build_cooccurrence_graph(["dog cat", "dog bird"])
    freq = {n["id"]: n["attributes"]["frequency"] for n in graph["nodes"]}
    assert freq["dog"] == 2


def test_pos_filter_invalid_value_raises():
    import pytest
    with pytest.raises(ValueError):
        text_network.build_cooccurrence_graph("dog cat", pos_filter="verbs")


def test_pos_filter_nouns_drops_verbs_and_adjectives():
    if not text_network.LEMMATIZATION_AVAILABLE:
        import pytest
        pytest.skip("NLTK wordnet/tagger data not installed in this environment")
    graph = text_network.build_cooccurrence_graph(
        "the busy manager reviewed quarterly reports quickly", pos_filter="nouns"
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "manager" in ids and "report" in ids
    assert "review" not in ids and "reviewed" not in ids  # verb, dropped
    assert "busy" not in ids and "quarterly" not in ids  # adjectives, dropped
    assert "quickly" not in ids  # adverb, dropped
    assert graph["stats"]["pos_filter_applied"] is True


def test_pos_filter_none_keeps_all_parts_of_speech():
    graph = text_network.build_cooccurrence_graph("the busy manager reviewed quarterly reports quickly")
    assert graph["stats"]["pos_filter_applied"] is False


def test_pos_filter_falls_back_without_tagger(monkeypatch):
    monkeypatch.setattr(text_network, "LEMMATIZATION_AVAILABLE", False)
    graph = text_network.build_cooccurrence_graph("busy manager reviewed reports", pos_filter="nouns")
    ids = {n["id"] for n in graph["nodes"]}
    # filter skipped entirely rather than silently keeping nothing
    assert "reviewed" in ids
    assert graph["stats"]["pos_filter_applied"] is False


def test_min_word_frequency_drops_rare_words():
    # "dog" appears 3 times, "cat" once, "bird" once.
    graph = text_network.build_cooccurrence_graph(
        "dog cat dog bird dog", window_size=2, min_word_frequency=2
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "dog" in ids
    assert "cat" not in ids
    assert "bird" not in ids


def test_min_word_frequency_default_keeps_everything():
    graph = text_network.build_cooccurrence_graph("dog cat bird", window_size=2)
    ids = {n["id"] for n in graph["nodes"]}
    assert ids == {"dog", "cat", "bird"}


def test_min_word_frequency_closes_gap_for_windowing():
    # With "cat" dropped (frequency 1, floor 2), "dog" and "bird" — both
    # frequency 2 — must become adjacent across the gap "cat" leaves, the
    # same gap-closing behavior pos_filter relies on.
    graph = text_network.build_cooccurrence_graph(
        "dog cat bird dog bird", window_size=2, min_word_frequency=2
    )
    pairs = {tuple(sorted((e["source"], e["target"]))) for e in graph["edges"]}
    assert ("bird", "dog") in pairs
    assert not any("cat" in pair for pair in pairs)


def test_extract_backbone_keeps_only_edge_of_low_degree_node():
    # A is a hub; D has degree 1 (only connects to A) so its one edge must
    # survive regardless of weight. E has the same weight as D but also
    # connects elsewhere, giving it degree 2 — its edge to A is
    # proportionally insignificant from both sides and should be pruned.
    edges = [
        {"source": "A", "target": "B", "weight": 10.0},
        {"source": "A", "target": "C", "weight": 10.0},
        {"source": "A", "target": "D", "weight": 1.0},
        {"source": "A", "target": "E", "weight": 1.0},
        {"source": "E", "target": "F", "weight": 1.0},
    ]
    backbone = text_network.extract_backbone(edges, alpha=0.05)
    pairs = {(e["source"], e["target"]) for e in backbone["edges"]}
    assert ("A", "D") in pairs  # degree-1 node: always kept
    assert ("A", "E") not in pairs  # same weight, but insignificant from both sides


def test_extract_backbone_stats_report_kept_and_removed():
    edges = [
        {"source": "A", "target": "B", "weight": 10.0},
        {"source": "A", "target": "E", "weight": 1.0},
        {"source": "E", "target": "F", "weight": 1.0},
        {"source": "A", "target": "C", "weight": 10.0},
    ]
    backbone = text_network.extract_backbone(edges, alpha=0.05)
    assert backbone["stats"]["edges_kept"] + backbone["stats"]["edges_removed"] == len(edges)
    assert backbone["stats"]["edges_kept"] == len(backbone["edges"])
    assert backbone["stats"]["alpha"] == 0.05


def _needs_tagger():
    if not text_network.LEMMATIZATION_AVAILABLE:
        import pytest
        pytest.skip("NLTK wordnet/tagger data not installed in this environment")


def test_extract_phrases_finds_repeated_noun_noun_pair():
    _needs_tagger()
    docs = [
        "Climate change as a statistical process",
        "Data science and climate change are related fields",
        "Climate change matters a lot for climate change students",
    ]
    tagged_docs = [text_network._tag_and_lemmatize(text_network.tokenize(d)) for d in docs]
    phrases = text_network.extract_phrases(tagged_docs, min_count=2, min_pmi=1.0)
    assert ("climate", "change") in phrases
    assert phrases[("climate", "change")] == "climate_change"


def test_extract_phrases_respects_min_count():
    _needs_tagger()
    docs = ["Climate change is one thing"]
    tagged_docs = [text_network._tag_and_lemmatize(text_network.tokenize(d)) for d in docs]
    # seen once: min_count=2 must reject it regardless of PMI
    phrases = text_network.extract_phrases(tagged_docs, min_count=2, min_pmi=0.0)
    assert ("climate", "change") not in phrases


def test_extract_phrases_rejects_two_merely_frequent_unrelated_words():
    _needs_tagger()
    # "new" and "work" both appear often but never as a stable pair alongside
    # plenty of other neighbors - low PMI should keep them unmerged even
    # though their raw co-occurrence count is non-trivial.
    docs = [
        "New research on work practices",
        "New study of professional work culture",
        "New findings about remote work arrangements",
        "New approaches to work life balance",
    ]
    tagged_docs = [text_network._tag_and_lemmatize(text_network.tokenize(d)) for d in docs]
    phrases = text_network.extract_phrases(tagged_docs, min_count=2, min_pmi=3.0)
    assert ("new", "work") not in phrases


def test_merge_phrases_rewrites_consecutive_pair_and_tags_it_noun():
    tagged = [("climate", "noun"), ("change", "noun"), ("study", "noun")]
    phrase_map = {("climate", "change"): "climate_change"}
    merged = text_network._merge_phrases(tagged, phrase_map)
    assert merged == [("climate_change", "noun"), ("study", "noun")]


def test_merge_phrases_leaves_unmatched_tokens_alone():
    tagged = [("dog", "noun"), ("run", "verb"), ("fast", "adj")]
    merged = text_network._merge_phrases(tagged, {("cat", "toy"): "cat_toy"})
    assert merged == tagged


def test_build_cooccurrence_graph_merges_phrases_when_enabled():
    _needs_tagger()
    # "climate" and "change" appear only as this pair, never alone -
    # maximizes PMI for the given corpus size so the default threshold is
    # comfortably cleared (unlike a mix of paired and standalone mentions).
    docs = [
        "Climate change matters greatly",
        "Climate change shapes practice",
        "Climate change guides students",
        "Fieldwork methods in ethnographic research",
        "Consumer culture and market studies",
        "Organizational reform in global firms",
    ]
    graph = text_network.build_cooccurrence_graph(docs, merge_phrases=True, window_size=3)
    ids = {n["id"] for n in graph["nodes"]}
    assert "climate_change" in ids
    assert "climate" not in ids  # fully absorbed into the merged phrase
    assert graph["stats"]["phrases_detected"] >= 1


def test_merge_phrases_does_not_let_a_stopword_hide_inside_a_phrase():
    _needs_tagger()
    # "customer" and "service" are both stopworded (e.g. the corpus's
    # own self-referential subject name) - the pair must not survive merged
    # into "customer_service", which would evade the stopword list.
    docs = [
        "Customer service matters greatly",
        "Customer service shapes practice",
        "Customer service guides students",
        "Fieldwork methods in ethnographic research",
        "Consumer culture and market studies",
        "Organizational change in global firms",
    ]
    graph = text_network.build_cooccurrence_graph(
        docs, merge_phrases=True, window_size=3,
        extra_stopwords=["customer", "service"],
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "customer_service" not in ids
    assert "customer" not in ids
    assert "service" not in ids


def test_build_cooccurrence_graph_merge_phrases_off_by_default():
    docs = ["Climate change as a statistical process"]
    graph = text_network.build_cooccurrence_graph(docs)
    assert graph["stats"]["phrases_detected"] == 0
    ids = {n["id"] for n in graph["nodes"]}
    assert "climate_change" not in ids


def test_document_frequency_tracked_per_node():
    # "dog" appears in all 3 documents; "cat" only in 1.
    docs = ["dog runs fast", "dog and dog again", "cat and dog play"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2)
    doc_freq = {n["id"]: n["attributes"]["document_frequency"] for n in graph["nodes"]}
    assert doc_freq["dog"] == 3
    assert doc_freq["cat"] == 1


def test_self_referential_candidates_flags_word_in_most_documents():
    # "dog" appears in every document (high document frequency, a candidate
    # self-referential/generic word); "cat" appears in only one, even though
    # both words might have similar total raw counts elsewhere in a bigger
    # corpus - document spread, not raw count, is what should trigger this.
    docs = ["dog walks", "dog runs", "dog jumps", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.5)
    flagged = {c["word"] for c in graph["stats"]["self_referential_candidates"]}
    assert "dog" in flagged
    assert "cat" not in flagged


def test_self_referential_candidates_report_ratio_and_count():
    docs = ["dog walks", "dog runs", "dog jumps", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.5)
    dog_entry = next(c for c in graph["stats"]["self_referential_candidates"] if c["word"] == "dog")
    assert dog_entry["document_frequency"] == 3
    assert dog_entry["document_ratio"] == 0.75


def test_self_referential_candidates_report_peak_document_count():
    # "dog" appears once each in three documents (diffuse); "cat" appears
    # five times concentrated in a single document (a real sub-topic) even
    # though it clears the same document-frequency threshold via one other
    # scattered mention - peak_document_count is what would distinguish them.
    docs = ["dog walks", "dog runs", "dog jumps", "cat cat cat cat cat", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.4)
    by_word = {c["word"]: c for c in graph["stats"]["self_referential_candidates"]}
    assert by_word["dog"]["peak_document_count"] == 1
    assert by_word["cat"]["peak_document_count"] == 5


def test_self_referential_candidates_empty_when_nothing_clears_threshold():
    docs = ["dog walks", "cat sleeps", "bird flies", "fish swims"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.9)
    assert graph["stats"]["self_referential_candidates"] == []


def test_self_referential_threshold_is_configurable():
    docs = ["dog walks", "dog runs", "cat sleeps", "cat plays"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.4)
    flagged = {c["word"] for c in graph["stats"]["self_referential_candidates"]}
    # both dog and cat sit at exactly 0.5 document ratio - a lower threshold
    # (0.4) should catch both rather than needing a majority.
    assert "dog" in flagged
    assert "cat" in flagged


def test_exclude_self_referential_off_by_default():
    docs = ["dog walks", "dog runs", "dog jumps", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.5)
    ids = {n["id"] for n in graph["nodes"]}
    assert "dog" in ids  # flagged but not dropped, since exclude defaults False


def test_exclude_self_referential_drops_flagged_words():
    docs = ["dog walks", "dog runs", "dog jumps", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(
        docs, window_size=2, self_referential_threshold=0.5, exclude_self_referential=True,
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "dog" not in ids
    assert "cat" in ids  # below the threshold, survives


def test_exclude_self_referential_closes_gap_for_windowing():
    # "dog" appears in every document and gets excluded; "walk" and "run"
    # (each in one document, never together) must not become neighbors just
    # because "dog" no longer separates them across documents - windowing
    # still respects per-document boundaries even after exclusion.
    docs = ["dog walk", "dog run"]
    graph = text_network.build_cooccurrence_graph(
        docs, window_size=2, self_referential_threshold=0.5, exclude_self_referential=True,
    )
    pairs = {tuple(sorted((e["source"], e["target"]))) for e in graph["edges"]}
    assert ("run", "walk") not in pairs


def test_context_snippets_off_by_default():
    docs = ["dog walks fast", "dog runs far", "dog jumps high", "cat sleeps"]
    graph = text_network.build_cooccurrence_graph(docs, window_size=2, self_referential_threshold=0.5)
    dog_entry = next(c for c in graph["stats"]["self_referential_candidates"] if c["word"] == "dog")
    assert "context" not in dog_entry


def test_context_snippets_attaches_excerpts_from_original_text():
    docs = ["the dog walks fast", "the dog runs far", "the dog jumps high", "the cat sleeps"]
    graph = text_network.build_cooccurrence_graph(
        docs, window_size=2, self_referential_threshold=0.5, context_snippets=2,
    )
    dog_entry = next(c for c in graph["stats"]["self_referential_candidates"] if c["word"] == "dog")
    assert len(dog_entry["context"]) == 2
    assert any("walks" in s or "runs" in s for s in dog_entry["context"])


def test_context_snippets_respects_max_count():
    docs = ["dog one", "dog two", "dog three", "dog four", "cat five"]
    graph = text_network.build_cooccurrence_graph(
        docs, window_size=2, self_referential_threshold=0.5, context_snippets=1,
    )
    dog_entry = next(c for c in graph["stats"]["self_referential_candidates"] if c["word"] == "dog")
    assert len(dog_entry["context"]) == 1


def test_context_snippets_prioritize_document_with_highest_count():
    # "dog" appears once in most documents (scattered, filler-like) but is
    # the concentrated subject of one document (mentioned 5 times) - the
    # single most informative excerpt is from that concentrated document,
    # not whichever document happens to come first in the list.
    docs = [
        "a dog barked once",
        "dog dog dog dog dog is the sole topic of this document about dogs",
        "another dog appeared briefly",
        "cat sleeps",
    ]
    graph = text_network.build_cooccurrence_graph(
        docs, window_size=2, self_referential_threshold=0.5, context_snippets=1,
    )
    dog_entry = next(c for c in graph["stats"]["self_referential_candidates"] if c["word"] == "dog")
    assert "sole topic" in dog_entry["context"][0]
    assert "6x in this document" in dog_entry["context"][0]  # 5 "dog" + 1 "dogs" (word-prefix match)
