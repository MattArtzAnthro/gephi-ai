# Text Network Analysis

`gephi_text_to_network` turns free text into a word co-occurrence graph and
loads it straight into Gephi: words are lemmatized (reduced to their dictionary
form) and stopwords (common function words such as "the" and "of") are removed,
then an edge connects two words that appear within `window_size` tokens of each
other, weighted by proximity. From that point on, this is just a graph: nothing
about the rest of the workflow (statistics, layout, verification, teachback) is
specific to text. Run `gephi_profile_graph` next, as for any other network.

`gephi_text_to_network` adds to the current workspace unless `clear_existing`
is true. Build in a fresh workspace (`gephi_new_workspace` first), and rebuild
in that workspace with `clear_existing: true`.

## Start here: one long text

A novel, a report, or a long transcript arrives as one file. Prepare it before
building:

1. **Split it into paragraphs and pass them as a list** (`text: ["first
   paragraph", "second paragraph", ...]`). The co-occurrence window then stops
   at each paragraph break (see the next section).
2. **Strip what is not the text**: front matter (title page, contents, licence
   and publisher notes), epigraphs, chapter headings, page numbers, and markers
   such as `[Illustration]` or `[Footnote]`. Each would otherwise enter the
   graph as words.
3. **Build once**, with `min_edge_weight` left at 0 so later steps see every
   tie. Check the `stats` block (below) before anything else.
4. **Read the vocabulary** with `gephi_query_nodes(column="frequency", min=k,
   limit=20)`, raising or lowering `k` until about ten to twenty words match
   (`matches` gives the total). This shows the words the text repeats most
   without exporting anything.
5. **Read the edge weights** with `gephi_column_value_frequencies(column="weight",
   target="edge")`: how many ties are weak and how many strong.
6. **Thin the edges with the backbone** (`gephi_extract_backbone`, below)
   rather than a flat weight cutoff, and sweep its `alpha`. Rebuild only when
   the vocabulary itself needs to change (stopwords, a frequency floor, noun
   filtering).

## Pass a list of documents, not one concatenated string

If the source is naturally many separate units (article titles, survey
responses, transcript turns, the paragraphs of one long text), pass them as a
list, not joined into one string. The co-occurrence window resets at each list
item and never bridges from the end of one document into the start of the
next. A single concatenated string creates an edge between the last word of
one document and the first word of the next at every boundary, and nothing in
the output marks those edges as different from real co-occurrences.
`stats.document_count` reports how many units were passed; a value of 1 on a
corpus that obviously has many units means the boundaries were lost before the
call.

## Naming a community from its top words can mistake shared vocabulary for a shared topic

The obvious way to name a community (a modularity class) is to take its two or
three highest-degree words and join them into a label. This fails in a
specific, recognizable way: a word can have high degree because many
*different* documents about *different* subjects use it as a theoretical frame
or stock phrase, not because the documents share a topic. A theoretical term
used as a lens by articles on unrelated subjects can pull those articles into
one community. The community is real, but a topic-shaped name for it implies a
single subject that does not exist.

Before finalizing a name, read the source documents behind two or three of the
community's top words, not just the single highest one. If they are different
documents about different things, the community is a "shared vocabulary"
cluster, not a "shared topic" cluster, and its name should say so (for example
"Liminality across contexts" rather than a topic label). A rough warning sign
before checking sources: if the top two or three words do not obviously belong
in one sentence together, be suspicious. This is a different failure from the
self-referential hubs and citation artifacts below: those inflate one node with
meaningless frequency, while this one merges separate content under one
misleadingly specific name.

**Pick label candidates by degree and betweenness together.** A cluster's
highest-degree word is what it repeats most; its highest-betweenness word is
what holds it together (what other members route through). These are often
different words. Read both before settling on two or three words to name a
cluster.

## Caption placement: a hub can be buried in its own cluster

`gephi_label_clusters` anchors each caption on a cluster's highest-degree node,
which is usually right. In a dense core where several clusters' hubs converge,
a hub can be surrounded by larger or equal-sized neighbours of the same colour,
and its label then renders underneath them: the label exists (`gephi_get_node`
returns it) but does not show in the export.

A Label Adjust pass does not fix this (it moves labels relative to their own
node, not the crowd around it), and enlarging the buried node only buries
whichever neighbour becomes the smallest. What fixes it: move the caption to another
node in the same cluster at the cluster's visible edge, either with
`gephi_label_clusters(..., prefer="size")` or by moving that one node a few
dozen units out of the crowd with `gephi_set_node_position` (no full re-layout
needed), with a modest size increase if it is still the smallest node nearby.
Check the exported image itself, not only that the label was accepted.

## Check document frequency, not raw frequency, for self-referential hubs

A corpus that is *about* one subject often names that subject in most of its
documents: a journal's own name in its article titles, a survey's own topic in
its responses. That word dominates the graph without distinguishing any
structure, because it is common to nearly every document and so to nearly
every cluster.

**Do not rely on a top-frequency list to catch it.** Raw frequency cannot tell
"mentioned constantly in a few documents" (a real topic) from "present in
almost every document" (the corpus's own subject or, in full-text corpora,
generic prose such as "our research shows"). A word present in nearly every
document can still sit outside the top forty by count.

Every node carries a `document_frequency` attribute (how many documents
contain it), and `stats.self_referential_candidates` lists every word whose
share of documents clears `self_referential_threshold` (default 0.5, present in
at least half the corpus), worst first. Check this list before styling by size
or degree, as you check `stats.pos_filter_applied`. Add flagged words to
`extra_stopwords` and rebuild, or set `exclude_self_referential=True` to drop
them automatically.

**On a large full-text corpus, a high `min_word_frequency` alone makes this
worse.** A high count floor without a document-frequency ceiling selects FOR
generic words: a word needs presence across many documents to reach a large
total count, and "present in most documents" is close to the definition of
generic. The communities then form around prose scaffolding rather than
topics. Turn on `exclude_self_referential=True` first, and keep the frequency
floor low, so it only trims the rare long tail.

## The 40 to 50% document-frequency band needs a human read

`self_referential_threshold` draws a hard line, and real corpora do not split
cleanly at it: topical hub words and generic scaffolding words can sit in the
same band just under 0.5. Two responses are both wrong:

- **Lowering the threshold to catch the band.** It drops the generic words but
  also the good hubs at a similar ratio; document share is not what differs
  between them.
- **Hand-picking words to exclude and keeping the list for later corpora.** A
  word that is scaffolding in one corpus can be exactly the topic in another.

Graph measures do not separate the two kinds of word either: post-backbone
degree and edge-weight concentration (whether a word's ties go to a few strong
partners or many weak ones) overlap.

One text signal carries real information: `peak_document_count`, the word's
highest count in any single document. Generic words tend to peak low in every
document, while a topical word usually has at least one document that uses it
heavily. Treat it as one piece of evidence, not a cutoff.

**Concentration can hide inside a word that reads as generic.** A word can be
filler across most documents and still be the actual subject of one. Excluding
it may still be the right overall call, but it discards that sub-topic too, and
only the documents where the word is concentrated reveal this.

The fix is `context_snippets` (default 0, off). Set it to 2 or 3 and every
entry in `stats.self_referential_candidates` gets a `context` list: excerpts of
the surrounding text, taken first from the documents with the *highest* count
of the word. That ordering is what surfaces a concentrated sub-topic. Two or
three sentences settle it: a word whose excerpts all point at one specific
subject is a topic; a word whose excerpts are incidental and unrelated is
filler.

## What a structural gap is, and is not

Two dense clusters joined by few or no edges is the interesting pattern in a
text network: the source may treat two topics as separate registers. It can
also mean nothing: short texts, small vocabularies, and a tight `window_size`
all produce gaps that are sampling artifacts.

Do not report a gap as a finding on sight. Check it like any other claimed
structure: compute modularity (`gephi_compute_modularity`), then run
`gephi_visual_qa` with `partition_column` set to `modularity_class`, the same
within-group share against random baseline test used for any partition. A
"strong" verdict means the gap reflects something in the co-occurrence
structure. A "none" or "weak" verdict means say so plainly rather than narrate
a gap that is not there.

The `stats` block `gephi_text_to_network` returns (`raw_word_count`,
`kept_word_count`, `words_filtered`, `edge_count`) is the first check, before
any statistic: a short text (well under a few hundred kept words) produces a
sparse, low-confidence graph however the gap looks. Say so before reading
structure into it.

## Window size is a real choice

`window_size` sets how many tokens ahead of each word get connected to it:

- **Small (2 to 3)**: only adjacent or near-adjacent words connect. Tight,
  literal co-occurrence, suited to short texts, titles, or the question "what
  gets said right next to what."
- **Larger (4 to 6)**: words across a sentence or two connect. Looser, more
  thematic association, better for longer documents, but it can connect words
  that share a paragraph without being related, which inflates density and
  shrinks gaps.

No value is correct in general. State the window size when reporting a gap or
a cluster, as a layout's settings go in a caption: a different window can make
a gap appear or disappear.

## Betweenness reads as "bridge concepts" here

On a text network, the words with high betweenness (`gephi_compute_betweenness`)
sit between topical clusters: concepts a discourse routes through, rather than
concepts that simply recur (that is degree or frequency). Frequency asks what
is talked about most; betweenness asks what connects what is talked about.
Report both, and do not conflate them.

Not every high-betweenness, low-degree word is a bridge concept. Titles or
passages that embed full citations ("By John B. Thompson, Cambridge: Polity
Press, 2010") put author names, cities, and publishers into the token stream.
Because a citation barely overlaps with the rest of the vocabulary, those
proper nouns can score high on betweenness while carrying no conceptual
meaning. Read the source text behind a surprising high-betweenness,
low-degree word before naming it a finding. If it is a proper noun, it is
likely this artifact, and its community is worth checking for a shared
non-content cause (a masthead, an appendix, a citation list).

## Directed or undirected

`gephi_text_to_network` builds an undirected graph: "A appears near B" is the
same fact as "B appears near A." This is a design decision; state it if asked,
and do not reconsider it mid-analysis.

## Fixing a hairball: prune the data, not only the style

A dense co-occurrence graph with per-node edge colours and uniform thickness
reads as a dark tangle however the layout is tuned. That is a data-density
problem, and only a data-density fix resolves it. In order of how much they
help:

1. **`min_word_frequency` when building** drops the long tail of words that
   occur once or twice before any edge is drawn. On a large corpus this alone
   can remove more than half the nodes.
2. **`gephi_extract_backbone`** on the result (below). This is the fix that
   removes the tangle; the rescale in item 4 only hides it.
3. **A flat neutral edge colour** (the light edge default, `#D0D0D0`), not
   per-node colouring. Per-node edge colour adds a second visual dimension
   nobody asked for and makes the tangle look busier; a neutral tone keeps the
   focus on the node colours, which already carry the communities.
4. **`edge.rescale-weight`** (thin weak edges, bold strong ones) improves on
   uniform thickness, but it changes only the drawing: every weak edge is still
   in the graph. Use it for a fast first look before deciding whether the
   backbone and a frequency floor are needed. Statistics computed before
   pruning describe the unpruned graph; recompute after pruning when the map
   and the numbers need to match.

## Backbone extraction: `gephi_extract_backbone` removes edges, `edge.rescale-weight` only hides them

`gephi_extract_backbone` (the disparity filter, Serrano, Boguna, and Vespignani
2009) removes edges, in a way a single `min_edge_weight` cutoff cannot: each
edge is judged per node, against how that node's own weight is split across
its neighbours, not against one global number. A specialized, low-degree
node's one real connection survives even at low weight; a hub's
proportionally thin edges are pruned even when their weight would pass a flat
cutoff. Build with `min_edge_weight=0` so the filter sees the true weight
distribution, and recompute modularity and betweenness afterwards if the
analysis depends on them. The backbone deletes edges with an undo snapshot;
`gephi_undo` restores them (one level).

**Sweep alpha; do not trust 0.05 by default.** The common values in the
disparity-filter literature (0.05 to 0.1) suit networks where one or two edges
dominate each node's total weight (airport traffic, citations). Word
co-occurrence weights are much more even, so at 0.05 almost nothing looks
significant and the filter can strip nearly every edge, leaving most nodes
unconnected. Sweep alpha (0.05, 0.1, 0.2, 0.3, 0.4) and check how many nodes
stay connected at each value. For co-occurrence graphs, a value in the 0.2 to
0.4 range that keeps most nodes connected while still cutting a real share of
edges is a more realistic start.

## Restricting to nouns with `pos_filter="nouns"`

Nouns carry most of a discourse's topical structure; verbs, adjectives, and
adverbs add relational texture but also noise when the goal is mapping *what a
text is about* (Rule, Cointet, and Bearman 2015). `pos_filter="nouns"` drops
every non-noun before windowing, so the surviving nouns become each other's
neighbours once the words between them are gone. The graph is sparser and more
legible, at the cost of relational information ("ethical concerns *about* AI"
and "AI concerns *causing* ethical debate" reduce to the same two nouns). It
needs the part-of-speech tagger; check `stats.pos_filter_applied` rather than
assuming it ran (see the lemmatization note below).

## Dropping rare words with `min_word_frequency`

Natural text follows Zipf's law: most unique words occur once or twice, adding
long-tail nodes that clutter a layout without carrying repeatable structure.
`min_word_frequency` (default 1, keeps everything) drops words below a
corpus-wide count *before* windowing. It is a node-level floor, distinct from
`min_edge_weight` (an edge-level floor) and from `gephi_extract_backbone` (a
per-node statistical test). The three compose: the frequency floor reduces the
word list, windowing runs on what is left, then `min_edge_weight` or the
backbone thins the edges.

## Unigrams, bigrams, or a hybrid: merging phrases with `merge_phrases`

Single words (the default) keep the graph simple but split concepts that only
mean something together: "design" and "anthropology" co-occurring is not the
same claim as "design anthropology" being one field. Treating every
consecutive pair as its own node goes too far the other way: most adjacent
pairs are not one concept ("of the", "is a"), and they multiply the vocabulary
for little gain. `merge_phrases=True` implements the standard hybrid: single
words stay the default, and only pairs that pass two independent tests merge
into one node ("machine_learning"):

1. **Part-of-speech pattern**: adjective and noun, or noun and noun. Necessary
   but not sufficient, since a mistagged word lets unrelated pairs through.
2. **Pointwise mutual information (PMI) above a threshold**: how much more
   often the pair appears side by side than the two words' separate
   frequencies predict. This distinguishes a stable concept from two frequent
   words that sometimes sit together ("new" and "work" in a corpus about work).

Check the candidates before relying on them: phrase detection finds proper
nouns, technical terms, and named fields well, but it is a statistical test.

**A stopword can hide inside a merged phrase.** Phrase detection runs on the
original word order, before stopwords are removed. The tool drops any
candidate phrase in which either word is a stopword, so a corpus's own subject
name, added to `extra_stopwords`, cannot come back as part of a phrase. Any
other phrase-merging step needs the same check: filtering single words does
not filter the phrases built from them.

## Removing "not", "no", and "never" trades polarity for topical cleanliness

The built-in stopword list removes negation words with the other function
words. For mapping *what a text is about*, this is fine. It becomes a real
problem when the material's meaning depends on polarity (reviews, opinion
text, satisfaction surveys): removing "not" from "not good" leaves "good" with
the opposite of its sense, and nothing in the graph flags the reversal. For
such material, restore the negation words before building, or do not use word
co-occurrence at all: a co-occurrence graph cannot represent polarity either
way.

## Techniques this tool does not provide

Some techniques from the text-network literature are outside this tool. When a
request needs one, say so and name the alternative:

- **Virtual edges from word embeddings** (connecting words with similar
  meanings that never co-occur, with GloVe, Word2Vec, or FastText), the usual
  remedy for short, sparse texts such as tweets. Not available here.
- **Syntactic dependency networks** (edges from grammatical parses, for
  example with spaCy, instead of proximity windows). A different pipeline, not
  a setting of this tool.
- **Discourse-state classification** (labelling a text as concentrated,
  diversified, or fragmented). The literature gives no numeric thresholds for
  these categories; describe the modularity, community sizes, and degree
  spread instead of assigning a label.
- **Distinctiveness centrality** (a TF-IDF-like score over graph neighbours).
  Not a Gephi statistic.
- **Similarity-mapping layouts (VOS, MDS)**, where 2D distance reflects
  similarity directly. Gephi's layouts are force-directed; VOSviewer offers
  these.
- **Automated cluster labelling by a language model.** The naming practice
  above (reading source documents behind top words, checking degree and
  betweenness together) does this work by hand.

## Known limitation: lemmatization is probabilistic

Words are lemmatized (tagged by part of speech, then reduced to a dictionary
root: "dogs" and "running" become "dog" and "run") rather than only
lowercased, so inflected forms land on one node. This needs NLTK's wordnet
corpus and tagger installed locally (`python -m nltk.downloader wordnet
omw-1.4 averaged_perceptron_tagger_eng`). Without them the tool falls back to
lowercasing only, and `stats.lemmatization` says which mode ran. Check it and
disclose it if asked; never assume lemmatization happened.

Even when it runs, tagging is a statistical model, especially on short or
informal text. An irregular verb can be mistagged (read as a noun) and fail to
merge with its other forms, leaving two nodes for what a person would read as
one word. When that happens, merge them with `gephi_merge_nodes` (their edges
move to the surviving node), naming the form to keep with `into`.

## Filtering out corpus-specific noise

`extra_stopwords` removes words beyond the built-in English stopword list: use
it for names, filler words, or terms specific to one corpus (an interviewer's
name in transcripts, a template phrase repeated in every scraped document).
Each entry is lemmatized the same way the source text is, so "replied" as a
stopword also catches "reply" in the text and the reverse; there is no need to
list every inflected form.

## References

Rule, Alix, Jean-Philippe Cointet, and Peter S. Bearman. 2015. "Lexical Shifts,
Substantive Changes, and Continuity in State of the Union Discourse,
1790–2014." *Proceedings of the National Academy of Sciences* 112 (35):
10837–10844.

Serrano, M. Ángeles, Marián Boguñá, and Alessandro Vespignani. 2009.
"Extracting the Multiscale Backbone of Complex Weighted Networks." *Proceedings
of the National Academy of Sciences* 106 (16): 6483–6488.
