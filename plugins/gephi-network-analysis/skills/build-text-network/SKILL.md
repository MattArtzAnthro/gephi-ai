---
name: build-text-network
description: Turn transcripts, field notes, survey answers, documents, or social posts into a tuned word co-occurrence network in Gephi. Use for build a text network, concept map this corpus, visualize themes in text, or inspect discourse as a graph.
---

# Build a Text Network

Build and tune a word co-occurrence graph whose vocabulary reflects the corpus
rather than stopwords or collection artifacts. A co-occurrence edge represents
proximity in text, not semantic truth.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break. Read `../gephi/references/text-network-analysis.md`
before choosing construction parameters and `../gephi/references/layout-guide.md`
before laying out the result.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step, remove or overwrite nothing, and list each choice under "Choices I made". If there is no input to work on, stop and say what is needed.
- **Work in a new workspace.** Call `gephi_new_workspace` before the first build, so the person's open work stays as it was, and rebuild there with `clear_existing: true`. Never create, open, or save a project over their work.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).

## Construction Choices

Use `gephi_text_to_network`. Record the final values and why they were chosen:

- `text`: prefer a list when the corpus has natural segments; the window resets
  per item and avoids cross-document edges;
- `window_size`: smaller captures tighter pairings, larger captures looser themes;
- `extra_stopwords`: remove corpus-specific filler, names, and boilerplate;
- `pos_filter`: use nouns or proper nouns for a concept-focused map when suitable;
- `min_word_frequency` and `min_edge_weight`: raise these to remove rare noise;
- `merge_phrases`: combine useful repeated two-word phrases;
- `exclude_self_referential` and `self_referential_threshold`: remove words that
  occur in nearly every document;
- `context_snippets`: preserve examples needed for later interpretation;
- `clear_existing`: `false` (the default) adds to the current workspace; pass
  `true` on every rebuild.

## Build-and-Tune Loop

1. Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.
   If the request contains no text or readable path, ask for one. There is no
   default text: without one, stop and say what is needed.
2. Call `gephi_new_workspace`. If it reports that no project is open, ask the
   person to open a project in Gephi (File > New Project) and stop until they have.
3. Build once with sensible parameters for this corpus. Run
   `gephi_get_graph_stats`, `gephi_profile_graph`, and `gephi_visual_qa`.
4. Inspect the top words with `gephi_query_nodes` (`column: "frequency"`, a `min`
   cutoff, `limit` 20 or less, raising or lowering the cutoff until about ten
   words match), and the edge-weight distribution with
   `gephi_column_value_frequencies` (`target: "edge"`). If hubs are interviewer
   names, filler, boilerplate, or other artifacts, rebuild with
   `clear_existing: true` and improved stopwords, part-of-speech filtering, or
   frequency floors.
5. Repeat the vocabulary check until substantive terms dominate. Rebuild from
   parameters; do not hand-delete noisy nodes.
6. Compute modularity, then `gephi_community_stability`, and call no word cluster
   a theme until it passes. Color by community with `colors` unset (the plugin's
   validated palette, largest group first), size by degree with the default
   sizes, and apply neutral edge styling appropriate for a dense co-occurrence
   graph.
7. Run ForceAtlas 2 and Noverlap according to the layout guide. Perform the full
   `gephi_visual_qa` and one-variable-at-a-time adjustment loop.
8. Export a PNG where requested (default: the Desktop), the legend with
   `gephi_export_legend`, and offer `gephi_view_graph` when MCP Apps are
   supported.

## Boundaries

- Communities are word clusters for interpretation, not validated topics.
- Never infer meaning from an edge without returning to source context.
- Never claim scale-free or power-law structure.
- Keep the full rebuild history so the construction is reproducible.

## Deliverable

Return final construction parameters with reasons, node, edge, and community
counts with their stability, the export and legend paths, a copy-ready caption,
the tuning history, notes on removed stopwords, filters, merged phrases, and
whether the remaining hubs are substantive, and any "Choices I made". Offer
`analyze-network` as a separate interpretation step.
