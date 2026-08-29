---
name: build-text-network
description: Turn transcripts, field notes, survey answers, documents, or social posts into a tuned word co-occurrence network in Gephi. Use for build a text network, concept map this corpus, visualize themes in text, or inspect discourse as a graph.
---

# Build a Text Network

Build and tune a word co-occurrence graph whose vocabulary reflects the corpus
rather than stopwords or collection artifacts. A co-occurrence edge represents
proximity in text, not semantic truth.

Read `../gephi/references/text-network-analysis.md` before choosing construction
parameters and `../gephi/references/layout-guide.md` before laying out the result.
If the request does not contain text or a readable path, ask for one.

## Construction Choices

Use `gephi_text_to_network`. Record the final values and why they were chosen:

- `text`: prefer a list when the corpus has natural segments; the window resets
  per item and avoids cross-document edges;
- `window_size`: smaller captures tighter pairings, larger captures looser themes;
- `extra_stopwords`: remove corpus-specific filler, names, and boilerplate;
- `pos_filter`: use nouns or proper nouns for a concept-focused map when suitable;
- `min_word_frequency` and `min_edge_weight`: raise these to remove rare noise;
- `merge_phrases`: combine useful repeated bigrams;
- `exclude_self_referential` and `self_referential_threshold`: remove words that
  occur in nearly every document;
- `context_snippets`: preserve examples needed for later interpretation.

## Build-and-Tune Loop

1. Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.
2. Build once with sensible parameters for this corpus. Run
   `gephi_get_graph_stats`, `gephi_profile_graph`, and `gephi_visual_qa`.
3. Inspect top-degree words with `gephi_query_nodes`. If hubs are interviewer
   names, filler, boilerplate, or other artifacts, rebuild with
   `clear_existing: true` and improved stopwords, part-of-speech filtering, or
   frequency floors.
4. Repeat the vocabulary check until substantive terms dominate. Rebuild from
   parameters; do not hand-delete noisy nodes.
5. Compute modularity, color by community, size by degree, and apply neutral edge
   styling appropriate for a dense co-occurrence graph.
6. Run ForceAtlas 2 and Noverlap according to the layout guide. Perform the full
   `gephi_visual_qa` and one-variable-at-a-time adjustment loop.
7. Export a PNG where requested and offer `gephi_view_graph` when MCP Apps are
   supported.

## Boundaries

- Communities are word clusters for interpretation, not validated topics.
- Never infer meaning from an edge without returning to source context.
- Never claim scale-free or power-law structure.
- Keep the full rebuild history so the construction is reproducible.

## Deliverable

Return final construction parameters with reasons, node/edge/community counts,
the export path, a copy-ready caption, the tuning history, and notes on removed
stopwords, filters, merged phrases, and whether the remaining hubs are substantive.
Offer `analyze-network` as a separate interpretation step.
