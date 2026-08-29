# Text Network Analysis

`gephi_text_to_network` turns free text into a word co-occurrence graph and
loads it straight into Gephi: words are lemmatized and stopwords removed,
then an edge connects two words that appear within `window_size` tokens of
each other, weighted by proximity. From that point on, this is just a graph
— nothing about the rest of the workflow (statistics, layout, verification,
teachback) is text-specific. Run `gephi_profile_graph` next, same as any
other network.

## Pass a list of documents, not one concatenated string

If the source is naturally many separate units — article titles, survey
responses, transcript turns — pass them as a list (`text: ["title one",
"title two", ...]`), not joined into one string. The co-occurrence window
resets at each list item and never bridges from the end of one document into
the start of the next. Concatenating first and passing a single string
silently manufactures an edge between the last word of one document and the
first word of the next, for every boundary in the corpus — with a few
hundred documents that is a few hundred fabricated edges, and nothing in the
output flags it as different from a real co-occurrence. `stats.document_count`
reports how many units were actually passed; a value of 1 on a corpus that
obviously has many natural units is the tell that boundaries were lost before
the call.

## Naming a community from its top words can mistake shared vocabulary for a shared topic

The obvious way to name a modularity class is to take its 2-3 highest-degree
words and mash them into a label. This works most of the time and fails in a
specific, recognizable way: a word can have high degree because many
*different* documents about *different* subjects all happen to use it as a
theoretical frame or stock phrase, not because the documents share a topic.
On a corpus of academic titles, a concept like "liminality" showed up as the
theoretical lens in an article about advertising history, a completely
separate one about interdisciplinary collaboration, a third about
organizational innovation, and a fourth about design pedagogy — four
unrelated empirical subjects, bridged into one modularity class because they
all reach for the same abstract term. The resulting class was real (Louvain
found genuine structure), but naming it after that term plus the second-
highest word ("Design, Ethics & Advertising") implied a single coherent
topic that didn't exist — it was actually several small, otherwise-
unconnected articles sharing a recurring keyword.

The check that catches this: before finalizing a name, read the actual
source documents behind at least 2-3 of a class's top words, not just the
single highest one — if they turn out to be different documents about
different things rather than the same document or the same subject repeated,
the class is a "shared vocabulary" cluster, not a "shared topic" cluster, and
should be named to reflect that (e.g. "Liminality Across Contexts" rather
than a topic-shaped label). A rough tell before even checking sources: if a
class's top 2-3 words don't obviously belong in the same sentence together,
be suspicious rather than confident. This is a distinct failure mode from
the self-referential-hub and citation-artifact issues above — those inflate
one node with meaningless frequency; this one merges genuinely separate
content under a single misleadingly specific name.

**Pick label candidates by degree *and* betweenness together, not degree
alone.** A cluster's highest-degree word is what it repeats most; its
highest-betweenness word is what holds it together structurally (what
other members of the cluster actually route through). These are frequently
different words. Reading both before settling on 2-3 words to name a
cluster catches cases a pure frequency read misses — the same discipline
already used for whole-graph betweenness, applied one level down at the
per-cluster naming step.

## Caption placement: a cluster's hub node can be too buried in its own cluster to show a label

`gephi_label_clusters` picks a cluster's highest-degree node as its caption
anchor, which is usually right — but in a dense core where several
clusters' hub nodes converge (the most central, most topically load-bearing
communities sit closest to the graph's center of gravity), that hub node
can be completely surrounded by larger or equal-sized same-color neighbors,
and its label renders invisibly underneath them. This showed up as a label
that was confirmed present via the API (`gephi_get_node` returned the
correct text) but never appeared in the exported image — not a missing-data
problem, a pure geometric occlusion.

What does *not* reliably fix it: running `"Label Adjust"` as a layout pass
(it adjusts label positions relative to their own node, not the underlying
node crowding) and enlarging the buried node's own size (this just buries
whichever neighbor is now smaller — a whack-a-mole problem in a packed
core, since something is always going to be the new smallest circle in
that spot). What does fix it: move the caption to a different node in the
same cluster that sits at the cluster's visual edge rather than its packed
interior (`gephi_set_node_position` on that one node, a few dozen units
away from the crowd, is enough — this doesn't need a full re-layout), and
if needed follow with a modest size bump so it isn't the smallest node in
its new neighborhood either. Verify by reading the actual exported pixels,
not just confirming the API accepted the label — the two can disagree.

## Check document frequency, not raw frequency, for self-referential hubs

A corpus that is *about* one subject often names that subject in most of its
documents — a journal's own name in its article titles, a survey's own topic
in its own responses. That word will dominate the graph without
discriminating any structure at all — it is common to nearly every
document, so it is common to nearly every cluster.

**Do not rely on a manual top-frequency-ranking eyeball check — it misses
real cases.** Raw frequency rank can't distinguish "mentioned constantly
within a few documents" (a real topic) from "present in almost every
document" (the corpus's own subject, or in full-text corpora, generic prose
scaffolding — "our research shows," "in this study we examine"). On a real
255-article full-text corpus, a word present in 254 of 255 documents
survived a manual check of the top 40 words by raw count, because plenty of
individually rarer, more topical words outranked it in absolute frequency
that one time — a word can be simultaneously "not in the top 40 by count"
and "the single most universal word in the entire corpus."

`build_cooccurrence_graph`/`gephi_text_to_network` compute this
automatically now: every node carries a `document_frequency` attribute
(how many distinct documents contain it), and `stats.self_referential_
candidates` lists every word whose document-frequency *ratio* clears
`self_referential_threshold` (default 0.5 — present in at least half the
corpus), sorted worst-first. Check this list before styling by size or
degree, the same way `stats.pos_filter_applied` gets checked. Add flagged
words to `extra_stopwords` and rebuild, or set `exclude_self_referential=
True` to drop them automatically.

**On a large multi-document full-text corpus, `min_word_frequency` alone can
make this worse, not better.** A high absolute-count floor, applied without
a document-frequency ceiling, systematically selects FOR generic words: a
word needs sustained presence across *many* documents to rack up a large
total count, and "present in most documents" is close to the definition of
generic. On the same real corpus, requiring 200+ total occurrences (to
control a ~1M-word vocabulary down to a legible node count) left literally
half the surviving vocabulary flagged as present in most documents —
modularity on that graph was 0.47, dominated by scaffolding-vocabulary
communities ("Time & Temporal Narrative," "Everyday Speech & Quotation").
Turning on `exclude_self_referential=True` and lowering the frequency floor
back down (no longer needing to do double duty as a generic-word filter)
raised modularity to 0.60 on the identical corpus and produced sharply
specific, topical communities instead ("Chinese Family Firms & Capitalism,"
"Ethics, Codes & Professional Networks" — the latter's hub words included
"aaa," the American Anthropological Association, found via its ethics code
being discussed repeatedly in a concentrated subset of articles, exactly
the kind of signal a document-frequency ceiling protects and a pure
frequency floor drowns out).

## The 40-50% document-frequency gray zone needs a human read, not a bigger threshold or a word list

`self_referential_threshold` (default 0.5) draws a hard line, but real corpora
don't split cleanly at it. Tested on a real 255-document corpus: several
genuinely topical hub words and one genuinely generic scaffolding word all sat
in the same 40-50% band, just under the default threshold. Two temptations
here are both wrong:

- **Lowering the threshold to catch the gray zone.** It would drop the
  generic words but also destroy the good hubs sitting at a similar ratio —
  the threshold can't distinguish them because document-frequency ratio isn't
  what actually differs between them.
- **Hand-picking words to exclude by reading one dataset and hardcoding a
  list.** Solves that one corpus and overfits every other one. A word
  that's generic scaffolding on one corpus can be exactly the topic on
  another — a word list tuned on one dataset is a liability on the next.

Graph-structural signals don't cleanly separate the two kinds of words either
— post-backbone degree and edge-weight concentration (a Herfindahl-style
measure of whether a word's connections concentrate on a few strong partners
or spread thin across many) put a genuinely generic word and a genuine topic
hub in overlapping ranges.

One text-level signal did turn out to carry real information:
`peak_document_count` (the word's single highest per-document occurrence
count). On the same corpus, truly generic words peaked at 12-16 occurrences
in their heaviest document, while every genuinely topical word tested peaked
at 30-175 — roughly a 2x floor-to-ceiling gap, consistent across every word
tried. It's a real, useful piece of evidence, but not a clean classifier on
its own — treat it as one input to weigh, not a cutoff to apply blindly, and
always confirm with the actual excerpt before excluding anything.

**Concentration can hide inside a word that also reads as generic.** On that
same corpus, reading two arbitrary example sentences for one word turned up
nothing but incidental, unrelated mentions — suggesting it was safe to treat
as scaffolding. But that word's single highest-count document used it well
over 150 times and turned out to be a genuine document specifically about
that word's own subject, not noise. A blanket exclusion of that word (which
was still the right overall call — it was dominating the corpus's document
count almost entirely through generic use elsewhere) discards that real
sub-topic along with the actual noise, and there was no way to know that
without checking where the word was concentrated, not just where it was
scattered.

The actual fix: `context_snippets` on `build_cooccurrence_graph`/
`gephi_text_to_network` (default 0, off). Set it to 2-3 and every entry in
`stats.self_referential_candidates` gets a `context` list — real excerpts of
surrounding original text, pulled from the documents with the *highest* count
of the word first, not just the first documents it happens to appear in.
That ordering matters: it's precisely what surfaces a concentrated sub-topic
that a random-order excerpt would miss. Reading two or three sentences
settles it without grepping the source text by hand: a word whose excerpts
all point at the same specific subject is a topic; a word whose excerpts are
incidental and unrelated to each other is filler. This generalizes to any
corpus because it's asking a human (or the assistant) to read real evidence,
not asking a formula to guess.

## What a structural gap actually is, and isn't

Two dense clusters connected by few or no edges is the interesting pattern
in a text network — it can mean the source genuinely treats two topics as
separate, unconnected registers. It can also mean nothing: short texts,
small vocabularies, and a `window_size` set too tight will all produce
gaps that are sampling artifacts, not findings.

Do not report a gap as insight on sight. Treat it exactly like any other
claimed structure: check it. Compute modularity (`gephi_compute_modularity`),
then run `gephi_visual_qa` with `partition_column` set to the resulting
`modularity_class` — the same within-group-edge-share-vs-baseline test used
for any other partition. A "strong" verdict means the gap reflects something
in the co-occurrence structure, not an artifact of a small or skewed sample.
A "none" or "weak" verdict means say so plainly rather than narrating a gap
that isn't statistically there.

The stats block `gephi_text_to_network` returns
(`raw_word_count`, `kept_word_count`, `words_filtered`, `edge_count`) is the
first sanity check, before running any statistic at all: a short text (well
under a few hundred kept words) will produce a sparse, low-confidence graph
no matter how the gap looks visually. Say so before reading structure into
it.

## Window size is a real choice, not a default to ignore

`window_size` sets how many tokens ahead of each word get connected to it.
This is a tradeoff, not a technical detail:

- **Small (2-3)**: only directly adjacent or near-adjacent words connect.
  Tight, literal co-occurrence — good for short texts, titles, or when the
  question is "what gets said right next to what."
- **Larger (4-6)**: words across a whole sentence or two connect. Looser,
  more thematic association — better for longer documents, but risks
  connecting words that share a paragraph without actually being related,
  inflating apparent density and shrinking apparent gaps.

There's no universally correct value. State the window size used when
reporting a gap or a cluster, the same way a layout's parameters get stated
in an export caption — a different window size can make a gap appear or
disappear.

## If layout parameters never seem to change anything, check the request key before anything else

When driving the Gephi HTTP API directly (not through the `gephi_run_layout`
MCP tool), `/layout/run` expects tuning values under the JSON key
`"properties"`. A request built with `"params"` instead is not an error —
it returns `success: true` and runs the layout — but every custom value in
it is silently discarded and the algorithm runs on its defaults. This is
much worse than a normal typo because there is no failure signal: the
layout genuinely runs, genuinely repositions nodes, and produces a plausible-
looking (if unexplained) result each time, so nothing points at the request
shape as the cause.

The concrete symptom that should raise suspicion: changing `scalingRatio`
or `gravity` across a wide range (e.g. 20 to 100, or 0 to 4) and getting
back nearly the same layout extent every time, no matter which direction
the parameter moved. A layout that is genuinely insensitive to a parameter
across that wide a range is itself the anomaly — check the request body
against the tool's actual implementation (or just use `gephi_run_layout`,
which builds the request correctly) before concluding the parameter doesn't
matter for this graph. In one real session this false floor was mistaken
for "this crowded core resists every layout parameter" and chased through
five parameter combinations plus a Noverlap pass, all running on defaults
the whole time; fixing the request key and re-running the exact first
`scalingRatio`/`gravity` values that had appeared to do nothing produced an
immediately, obviously better-separated layout.

The same silent-defaults trap applies to `"Noverlap"`: its `speed`, `ratio`,
and `margin` properties default to `0.0`, which is a full no-op (nodes
literally do not move), not a gentle setting — passing real values (e.g.
`speed: 3, ratio: 1.5, margin: 3`) is required for it to do anything at all.

## Betweenness centrality reads as "bridge concepts" here

`gephi_compute_betweenness` already exists for any graph; on a text network,
its high-scoring nodes are the words that sit between topical clusters —
concepts a discourse routes through rather than concepts that just recur
often (that's `degree`/frequency instead). The two measures answer different
questions: frequency asks what's talked about most; betweenness asks what
connects what's talked about. Report both, don't conflate them.

Not every high-betweenness/low-degree word is a genuine bridge concept —
check what it actually is before reporting it as one. On a corpus of academic
article titles, book-review titles that embed full citations ("By John B.
Thompson, Cambridge: Polity Press, 2010") put author names, cities, and
publishers into the token stream as if they were content words. Because a
citation string barely overlaps in vocabulary with anything else in the
corpus except through one or two generic words, those proper nouns can score
very high on betweenness while carrying zero conceptual meaning — they are
bibliographic metadata, not a bridge between ideas. Read the source text
behind a surprising high-betweenness/low-degree word before naming it a
finding; if it's a proper noun, it's very likely this artifact, not a bridge
concept, and the community it sits in is worth checking for a shared
non-content cause (a masthead section, an appendix, a citation list) rather
than treated as a substantive weakly-connected topic.

## Directed or undirected

`gephi_text_to_network` builds an undirected graph: two words co-occurring
is symmetric, "A appears near B" is the same fact as "B appears near A."
This is a deliberate choice, not an oversight — treat it as a design
decision worth stating if asked, not something to silently reconsider
mid-analysis.

## Fixing an actual hairball: prune the data, don't just restyle it

A dense co-occurrence graph rendered with per-node edge colors and uniform
thickness reads as an indistinguishable dark tangle no matter how the layout
is tuned — that's a data-density problem, and only a data-density fix
resolves it. In order of how much they actually help:

1. **`min_word_frequency` when building** — drop the long tail of words that
   occur once or twice before any edge is ever drawn. On a 255-document
   corpus this alone cut node count by more than half.
2. **`gephi_extract_backbone`** on the result — see below. This is the fix
   that actually removed the hairball in practice, not the rescale trick.
3. **`edge.color` as a flat neutral hex** (e.g. `#999999`), not `"original"`
   (per-source-node coloring). Per-node edge coloring adds a second visual
   dimension nobody asked for and makes the tangle read as busier than it
   is; flat gray keeps focus on the node colors, which already carry
   community identity.
4. **`edge.rescale-weight`** (thin weak edges, bold strong ones) is a real
   improvement over uniform thickness, but it is a display-only patch on
   top of however many edges are still actually in the graph — it cannot
   fix a graph that's dense for a real, underlying reason (too many nodes,
   too many weak-but-present edges). Use it as a fast first look before
   deciding whether backbone extraction and a frequency floor are needed,
   not as the fix itself. Both are reversible (nothing is deleted from the
   analytical graph if applied to a copy) and modularity/betweenness
   computed before either remain valid only if computed on the same edge
   set that's actually being rendered — recompute after pruning if the
   two need to match.

## Backbone extraction: `gephi_extract_backbone` removes edges for real, `edge.rescale-weight` only hides them

The rescale trick above changes what gets *drawn*, not what the graph *is* —
useful for a fast first look, but modularity/betweenness are still computed
on every weak edge. `gephi_extract_backbone` (the disparity filter, Serrano,
Boguna, and Vespignani 2009) actually removes edges, and does it in a way a
single `min_edge_weight` cutoff can't replicate: significance is judged per
node, relative to how that node's own weight is split across its neighbors,
not against one global number every edge must clear. A specialized, low-
degree node's one real connection survives even at low absolute weight; a
high-degree hub's proportionally-thin edges get pruned even if their
absolute weight would pass a flat threshold. Run it after building with
`min_edge_weight=0` (so the filter sees the true weight distribution, not
one already thinned by a flat cutoff), and recompute modularity/betweenness
afterward if the analysis depends on them reflecting the pruned graph —
values computed before pruning describe the denser, pre-backbone graph.

**Do not trust alpha=0.05 by default — sweep it.** The disparity-filter
literature's common alpha values (0.05-0.1) were calibrated on networks with
highly skewed per-node weight distributions (airport traffic, citations),
where one or two edges dominate a node's total strength and the rest are
negligible by comparison. Word co-occurrence weights are much more uniform —
most of a node's edges sit within a narrow range of each other — so at
alpha=0.05 almost nothing looks "significant enough" and the filter can
destroy the graph (observed: 1292 edges collapsed to 8, most nodes losing
every connection). Sweep alpha (0.05, 0.1, 0.2, 0.3, 0.4...) and check how
many nodes stay connected at each value; for co-occurrence graphs, something
in the 0.2-0.4 range that keeps the large majority of nodes connected while
still cutting a real share of edges is a more realistic starting point than
the literature's default.

## Restricting to nouns with `pos_filter="nouns"`

Nouns carry most of a discourse's topical structure; verbs, adjectives, and
adverbs add qualitative/relational texture but also noise when the goal is
mapping *what a text is about* (Rule, Cointet, and Bearman 2015). Passing
`pos_filter="nouns"` drops every non-noun token before windowing — surviving
nouns become each other's neighbors once the words between them are gone,
same gap-closing principle a dependency-parse network uses when it strips
out everything but subjects and objects. This produces a sparser, more
legible graph at the real cost of losing relational information ("ethical
concerns *about* AI" and "AI concerns *causing* ethical debate" both reduce
to the same two noun neighbors). Requires the POS tagger; check
`stats.pos_filter_applied` rather than assuming it ran — see the
lemmatization-limitation note below for why the tagger can be unavailable or
occasionally wrong.

## Dropping rare words with `min_word_frequency`

Natural text is Zipfian: most unique words occur once or twice, contributing
long-tail nodes that clutter a layout without carrying repeatable structure.
`min_word_frequency` (default 1, keeps everything) drops words below a
corpus-wide count threshold *before* windowing, the same gap-closing
treatment as `pos_filter`. This is a node-level floor, distinct from
`min_edge_weight` (an edge-level floor) and from `gephi_extract_backbone` (a
per-node statistical test) — the three compose: frequency floor first
reduces the node list, then windowing runs on what's left, then
min_edge_weight or the backbone filter thins the resulting edges.

## Unigrams, bigrams, or a hybrid — and merging phrases with `merge_phrases`

Pure unigrams (the default) keep the graph simple but split cohesive
concepts across two nodes that only ever mean something together —
"design" and "anthropology" co-occurring is not the same claim as "design
anthropology" being one field. Pure n-grams (every consecutive pair as its
own node) go too far the other way: most bigrams are grammatically
adjacent without being one concept ("of the", "is a"), and they multiply
the vocabulary size for little payoff. The standard practice, and what
`merge_phrases=True` implements, is the hybrid in between: unigrams stay
the default node type, and only word pairs that pass two independent tests
get merged into a single node ("machine_learning"):

1. **POS pattern** — adjective+noun or noun+noun. This alone still passes
   through grammatically-adjacent-but-unrelated pairs if a word gets
   mistagged, so it's necessary but not sufficient.
2. **Pointwise mutual information (PMI)** above a threshold — how much more
   often the pair appears consecutively than the two words' independent
   frequencies would predict by chance. This is what actually distinguishes
   a stable concept from two merely-frequent words that happen to sit next
   to each other sometimes ("new" and "work" will co-occur often in a
   corpus about work, without being one concept).

Run on a real 255-title corpus, this correctly identified a range of
genuine compound concepts — proper nouns, technical terms, and named
fields spanning two words — while correctly leaving merely-adjacent,
unrelated word pairs unmerged. `extract_phrases` is exposed separately
from the merge step so candidates can be inspected before turning
`merge_phrases` on, if precision matters more than convenience for a given
corpus.

**A stopword can hide inside a merged phrase — check for it.** Phrase
detection has to run on the original token adjacency, which is before
stopword filtering happens. Without an explicit check, a pair like
`("customer", "service")` — both individually stopworded as a corpus's
self-referential subject name — would merge into `"customer_service"` and
evade the very stopword list built to exclude it. `build_cooccurrence_graph`
drops any candidate phrase where
either half is a stopword before merging, but this is worth knowing if
ever reimplementing phrase merging elsewhere: filtering the *unigrams*
doesn't automatically filter the *phrases built from them*.

## Stripping "not"/"no"/"never" trades sentiment for topical cleanliness

The built-in stopword list removes negation words along with other function
words. For mapping *what a text is about*, this is fine — "not," "no," and
"never" don't name concepts. It becomes a real problem the moment the
material's meaning depends on polarity (product reviews, opinion/sentiment
text, survey responses about satisfaction): stripping "not" from "not good"
leaves "good" free-floating with the opposite of its actual sense, and nothing
in the graph or its statistics flags that the reversal happened. If the
source is sentiment-bearing, pass negation words back in via a stopword
override before building, or don't use word co-occurrence for that
material at all — a co-occurrence graph has no mechanism for representing
polarity regardless of whether negation words survive filtering.

## Considered and deliberately not built

A few techniques from the text-network-analysis literature are documented
here rather than implemented, because they're a genuinely bigger lift than
the "surgical" scope of this tool, not because they lack merit:

- **Virtual edges via word embeddings** (connecting words that are
  semantically similar but never physically co-occur, using GloVe/Word2Vec/
  FastText) — the fix the literature proposes for short, sparse texts
  (tweets, single survey responses) that produce thin, chain-like graphs.
  Would need a new embedding-model dependency heavier than NLTK's tagger.
- **Syntactic dependency networks** — an entirely different edge-
  construction paradigm (edges from grammatical dependency parses via
  spaCy, not proximity windows) rather than an option on this tool; sparser
  and more precise, but a genuinely different pipeline, not a parameter.
- **Discourse-state classification** (e.g. labeling a text's overall
  structure as concentrated/diversified/fragmented from modularity +
  community-size concentration + degree-distribution entropy) — computable
  from stats this tool already produces, but the literature doesn't specify
  numeric thresholds for the qualitative categories, so building it now
  would mean inventing cutoffs and presenting them with more confidence
  than they've earned.
- **Distinctiveness centrality** (a TF-IDF-like score over graph neighbors,
  highlighting words connected to peripheral/specific areas) — not a
  Gephi-native statistic; computable via the Data Laboratory API on nodes/
  edges already fetched, but not worth a dedicated tool until a real
  analysis needs it.
- **Similarity-mapping layouts (VOS/MDS)** as an alternative to force-
  directed layout — positions nodes so 2D distance reflects normalized
  similarity directly, rather than emerging from a physics simulation.
  Gephi's own layout algorithms are all force-directed; an MDS layout would
  be a different tool (VOSviewer) or a custom implementation, not a
  parameter here.
- **Automated LLM-based cluster labeling** (prompt an LLM on each cluster's
  representative words/documents, consolidate candidate labels, then
  classify) — the actual naming work in this doc (reading source documents
  behind top words, checking degree+betweenness together) already does the
  substance of this by hand each time; automating it as a batch pipeline
  is reasonable for many-cluster graphs but hasn't been needed at the scale
  this tool has been used at so far.
- **WebGL/Level-of-Detail rendering** for large interactive graphs — applies
  to a custom web viewer, not to Gephi's own PNG/SVG export or the
  `gephi_view_graph` MCP App, which already has its own zoom/interaction
  model.

## Known limitation: lemmatization is probabilistic, not perfect

Words are lemmatized (POS-tagged, then reduced to a dictionary root: "dogs"
and "running" become "dog" and "run") rather than merely lowercased, so
inflected forms of the same word land on one node instead of splitting
across several. This needs NLTK's wordnet corpus and POS tagger installed
locally (`python -m nltk.downloader wordnet omw-1.4
averaged_perceptron_tagger_eng`); if that data isn't present, the tool falls
back to lowercasing only, and the returned `stats.lemmatization` field says
which mode actually ran — check it and disclose it if asked, don't assume
lemmatization happened.

Even when active, POS tagging is a statistical model, not ground truth,
especially on short or informal text. An irregular verb can get mistagged
(e.g. read as a noun) and fail to merge with its other inflected forms. This
shows up as two separate nodes for what a person would recognize as one
word. It's a real characteristic of the tagger, not a sign something is
broken — if two forms of the same word both appear as separate nodes, merge
them by hand (`gephi_add_edges` won't help; removing and re-adding under
one id will) rather than assuming the tool guarantees perfect merging.

## Filtering out corpus-specific noise

`extra_stopwords` removes words beyond the built-in English stopword list —
use it for names, filler words, or terms specific to one corpus (a
recurring interviewer's name in transcript data, a template phrase repeated
in every document of a scraped corpus). Whatever form is typed gets
lemmatized the same way the source text does, so "replied" as a stopword
also catches "reply" in the text and vice versa — no need to list every
inflected form separately.
