"""Convert free text into a word co-occurrence graph.

Normalizes text, lemmatizes it, removes stopwords, and connects words that
appear near each other within a sliding window, weighted by proximity. The
output is a plain nodes/edges dict shaped for gephi_add_nodes /
gephi_add_edges — nothing here is Gephi-specific, and nothing downstream
(layout, verification, teachback) needs to know the graph came from text
rather than a GEXF file: the same craft applies once it's a graph.

Lemmatization, not stemming, on purpose: the words here become visible node
labels in an actual Gephi graph, and a stemmer's mangled fragments ("argu" for
"argument"/"arguing") would look broken on a canvas in a way they'd never be
noticed as plain features in a typical text-mining pipeline. POS-aware
lemmatization needs NLTK's wordnet corpus and POS tagger, downloaded once via
`python -m nltk.downloader wordnet omw-1.4 averaged_perceptron_tagger_eng`.
If that data isn't present, this module degrades to lowercasing only rather
than failing — LEMMATIZATION_AVAILABLE and the stats dict's "lemmatization"
field disclose which mode actually ran, so a caller (or the assistant) can
say so rather than silently returning a lower-quality graph.
"""

from __future__ import annotations

import math
import re
from collections import Counter

try:
    import nltk
    from nltk.corpus import wordnet as _wordnet

    def _lemmatizer_ready() -> bool:
        try:
            nltk.data.find("corpora/wordnet")
            nltk.data.find("corpora/omw-1.4")
            nltk.data.find("taggers/averaged_perceptron_tagger_eng")
        except LookupError:
            try:
                # older nltk releases shipped the tagger under this name
                nltk.data.find("taggers/averaged_perceptron_tagger")
            except LookupError:
                return False
        return True

    LEMMATIZATION_AVAILABLE = _lemmatizer_ready()
except ImportError:
    LEMMATIZATION_AVAILABLE = False

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]*")

# A standard English stopword list, hardcoded rather than pulled from a
# corpus download, so basic tokenization/stopword filtering works with zero
# dependencies even when lemmatization's NLTK data isn't installed.
DEFAULT_STOPWORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can't",
    "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from",
    "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having",
    "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its",
    "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't",
    "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while",
    "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves",
    # Modal verbs and discourse markers: low-content words that keep showing
    # up as top "concepts" if left in (surfaced by testing against real text,
    # where "can" and "rather" outranked actual content words).
    "can", "could", "may", "might", "must", "shall", "will", "rather",
    "quite", "just", "also", "even", "still", "yet", "much", "many",
    "however", "therefore", "thus", "hence", "otherwise", "instead",
})


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation/digits, split into word tokens."""
    return [w.lower() for w in _WORD_RE.findall(text)]


def _wordnet_pos(treebank_tag: str) -> str:
    """Map a Penn Treebank POS tag to the WordNet POS category the
    lemmatizer needs (it defaults to noun otherwise, which mislemmatizes
    verbs, e.g. "running" would stay "running" instead of becoming "run")."""
    if treebank_tag.startswith("J"):
        return _wordnet.ADJ
    if treebank_tag.startswith("V"):
        return _wordnet.VERB
    if treebank_tag.startswith("R"):
        return _wordnet.ADV
    return _wordnet.NOUN


def _coarse_pos(treebank_tag: str) -> str:
    """Collapse a Penn Treebank tag to noun/verb/adj/adv/other, for filtering."""
    if treebank_tag.startswith("NN"):
        return "noun"
    if treebank_tag.startswith("VB"):
        return "verb"
    if treebank_tag.startswith("JJ"):
        return "adj"
    if treebank_tag.startswith("RB"):
        return "adv"
    return "other"


def _tag_and_lemmatize(tokens: list[str]) -> list[tuple[str, str]]:
    """Lemmatize and coarse-POS-tag in one pass, so both lemmatize() and
    POS-filtering in build_cooccurrence_graph share a single tagging pass
    rather than tagging the same sequence twice.

    Returns (lemma, coarse_pos) pairs. If LEMMATIZATION_AVAILABLE is False,
    coarse_pos is always "other" for every token — there's no tagger to ask,
    so pos_filter must not silently keep nothing in that case; callers that
    filter by POS need to check LEMMATIZATION_AVAILABLE themselves and
    disclose when the filter couldn't run, the same pattern already used for
    lemmatization mode.
    """
    if not tokens:
        return []
    if not LEMMATIZATION_AVAILABLE:
        return [(t, "other") for t in tokens]
    lemmatizer = nltk.stem.WordNetLemmatizer()
    tagged = nltk.pos_tag(tokens)
    return [(lemmatizer.lemmatize(word, _wordnet_pos(tag)), _coarse_pos(tag)) for word, tag in tagged]


def lemmatize(tokens: list[str]) -> list[str]:
    """POS-aware lemmatization: "running"/"ran" -> "run", "mice" -> "mouse".

    Tags the full token sequence first (POS tagging is more accurate with
    surrounding function words still present), then lemmatizes each word
    using its tag. Returns tokens unchanged if LEMMATIZATION_AVAILABLE is
    False rather than raising — see the module docstring.
    """
    if not LEMMATIZATION_AVAILABLE or not tokens:
        return tokens
    return [lemma for lemma, _pos in _tag_and_lemmatize(tokens)]


# Content-bearing POS patterns worth considering as one concept rather than
# two co-occurring words: adjective+noun ("artificial intelligence") and
# noun+noun ("machine learning"). Verb-containing and function-word
# patterns are deliberately excluded — they're rarely a single stable concept
# and would multiply candidate pairs without much payoff.
_PHRASE_PATTERNS = {("adj", "noun"), ("noun", "noun")}


def extract_phrases(
    tagged_documents: list[list[tuple[str, str]]],
    min_count: int = 3,
    min_pmi: float = 3.0,
    max_phrases: int = 1000,
) -> dict[tuple[str, str], str]:
    """Find cohesive two-word phrases worth merging into a single graph node.

    tagged_documents: per-document lists of (lemma, coarse_pos) pairs, e.g.
    from calling _tag_and_lemmatize on each document — the same tagging
    build_cooccurrence_graph already does for pos_filter, reused here rather
    than re-tagging.

    A candidate pair must pass two independent tests, not one:
    1. Its POS tags match a content-bearing pattern (_PHRASE_PATTERNS) —
       this alone would still catch grammatically-adjacent-but-unrelated
       pairs ("of the", "is a") if either word were mistagged, and doesn't
       tell you the pair is actually a stable unit rather than two words
       that just happen to sit next to each other sometimes.
    2. Pointwise mutual information (PMI) between the pair exceeds
       `min_pmi`: how much more often the two words appear consecutively
       than their independent frequencies would predict by chance. High
       co-occurrence frequency alone isn't enough either — two very common
       words (e.g. "new" and "work") will co-occur often just because
       they're both everywhere, without being one concept; PMI normalizes
       for that.
    `min_count` guards against PMI being unreliably high for pairs seen only
    once or twice (a single coincidental adjacency can produce a huge PMI
    score with no real support). `max_phrases` caps how many merges get
    applied, keeping the highest-PMI candidates if more qualify — prevents
    runaway vocabulary growth on a large corpus.

    Returns {(word1, word2): "word1_word2"} for qualifying pairs only.
    """
    unigram_freq: Counter[str] = Counter()
    bigram_freq: Counter[tuple[str, str]] = Counter()
    total = 0
    for tagged in tagged_documents:
        for lemma, _pos in tagged:
            unigram_freq[lemma] += 1
            total += 1
        for (w1, p1), (w2, p2) in zip(tagged, tagged[1:]):
            if w1 != w2 and (p1, p2) in _PHRASE_PATTERNS:
                bigram_freq[(w1, w2)] += 1

    if total == 0:
        return {}

    candidates = []
    for (w1, w2), count in bigram_freq.items():
        if count < min_count:
            continue
        pmi = math.log2((count * total) / (unigram_freq[w1] * unigram_freq[w2]))
        if pmi >= min_pmi:
            candidates.append(((w1, w2), pmi))

    candidates.sort(key=lambda item: -item[1])
    return {pair: f"{pair[0]}_{pair[1]}" for pair, _pmi in candidates[:max_phrases]}


def _merge_phrases(
    tagged: list[tuple[str, str]], phrase_map: dict[tuple[str, str], str]
) -> list[tuple[str, str]]:
    """Rewrite a tagged sequence, merging recognized bigrams into one token.

    A merged phrase is tagged "noun" regardless of its parts' original tags
    (an adjective+noun pair like "artificial_intelligence" functions as a
    noun as a whole) so pos_filter="nouns" treats it consistently rather
    than needing its own special case.
    """
    merged = []
    i = 0
    while i < len(tagged):
        if i + 1 < len(tagged):
            pair = (tagged[i][0], tagged[i + 1][0])
            if pair in phrase_map:
                merged.append((phrase_map[pair], "noun"))
                i += 2
                continue
        merged.append(tagged[i])
        i += 1
    return merged


def _context_snippets(
    word: str, documents: list[str], max_snippets: int = 2, radius_chars: int = 60
) -> list[str]:
    """Grab short excerpts of surrounding original text around a word.

    Deliberately re-searches the raw, unlemmatized documents (rather than the
    lemmatized token stream build_cooccurrence_graph already has) so the
    excerpt reads as real prose a human can judge at a glance, not a bag of
    normalized tokens. A literal, case-insensitive whole-word match is an
    approximation — it won't catch every inflected form a lemma collapsed
    (e.g. "dogs" is found, "the dog ran" is found, but an irregular form
    might not match) — good enough for a quick sanity read, not a precise
    concordance.

    Snippets come from the documents where the word occurs *most* often, not
    just the first documents it happens to appear in — a word can be spread
    thin across a corpus as filler while also being the concentrated subject
    of a handful of documents (a real sub-topic hiding inside what looks, by
    document-frequency ratio alone, like pure scaffolding). Tested on a real
    corpus: a manual read of two arbitrary example sentences for one such
    word read as generic filler and missed that the same word was also the
    explicit subject of several documents, one of them using it well over a
    hundred times. Surfacing the highest-count document first would have
    shown that concentration immediately instead of missing it by chance.
    """
    pattern = re.compile(rf"\b{re.escape(word)}\w*\b", re.IGNORECASE)
    counted = sorted(
        ((len(pattern.findall(doc)), doc) for doc in documents),
        key=lambda item: -item[0],
    )
    snippets = []
    for count, doc in counted:
        if count == 0 or len(snippets) >= max_snippets:
            break
        match = pattern.search(doc)
        start = max(0, match.start() - radius_chars)
        end = min(len(doc), match.end() + radius_chars)
        excerpt = doc[start:end].replace("\n", " ").strip()
        prefix = f"[{count}x in this document] " if count > 1 else ""
        snippets.append(f"{prefix}...{excerpt}..." if start > 0 or end < len(doc) else f"{prefix}{excerpt}")
    return snippets


def build_cooccurrence_graph(
    text: str | list[str],
    window_size: int = 4,
    min_edge_weight: float = 0.0,
    extra_stopwords: list[str] | None = None,
    pos_filter: str | None = None,
    min_word_frequency: int = 1,
    merge_phrases: bool = False,
    self_referential_threshold: float = 0.5,
    exclude_self_referential: bool = False,
    context_snippets: int = 0,
) -> dict:
    """Build a word co-occurrence graph from text.

    text: either one string, or a list of strings (documents/statements/
    titles). Pass a list whenever the input is naturally a set of separate
    units rather than one continuous passage — a co-occurrence window must
    never bridge from the end of one document into the start of an unrelated
    one, since that manufactures a relationship the source never expressed.
    A single string is treated as one document, same as before.

    window_size: how many tokens ahead of each word to connect it to. Words
    one apart get the strongest edge (weight = window_size - 1); words at the
    edge of the window get weight 1. The window resets at each document
    boundary rather than running across the concatenation of all documents.

    min_edge_weight: drop edges below this total weight after aggregation
    (weak, likely coincidental co-occurrences).

    extra_stopwords: additional words to filter beyond DEFAULT_STOPWORDS, for
    filler words specific to one corpus (e.g. a recurring interviewer name,
    or terms that name the corpus's own subject and so appear in nearly every
    document — those dominate the graph without discriminating anything).

    pos_filter: None (default) keeps every non-stopword token regardless of
    part of speech. "nouns" restricts the graph to noun tokens only (singular,
    plural, and proper nouns), dropping verbs/adjectives/adverbs/etc. before
    windowing — surviving nouns become adjacent to each other once the
    non-nouns between them are removed, the same "bridge the gap" principle
    dependency-parse text networks use. Nouns are the concept-carrying part of
    speech (Rule, Cointet, and Bearman 2015): a noun-only graph is sparser and
    more topically legible, at the cost of dropping relational/qualitative
    information verbs and adjectives carry. Requires the POS tagger
    (LEMMATIZATION_AVAILABLE); if it isn't installed, the filter is skipped
    entirely rather than silently keeping nothing, and
    stats.pos_filter_applied discloses whether it actually ran.

    min_word_frequency: drop words appearing fewer than this many times in
    the whole corpus before building any edges (standard practice for
    Zipfian text: most unique words occur once or twice and contribute long-
    tail node clutter without carrying repeatable structure). Default 1
    keeps every word, same as before this parameter existed. This is a node-
    level floor, distinct from min_edge_weight (an edge-level floor) — a
    word can pass min_word_frequency yet still lose all its edges to
    min_edge_weight, ending up an isolated node; drop those separately if a
    fully edgeless node list is unwanted.

    merge_phrases: if True, cohesive two-word phrases ("machine learning",
    "artificial intelligence") are detected corpus-wide and merged into a
    single node ("machine_learning") before windowing, rather than left
    as two separately co-occurring unigrams. A pair qualifies only if its
    POS tags match a content pattern (adjective+noun or noun+noun) AND its
    pointwise mutual information clears a threshold (default: seen at least
    3 times, PMI >= 3.0) — POS pattern alone would also catch grammatically-
    adjacent but unrelated words; PMI alone would merge two merely-frequent
    words that aren't really one concept. Capped at the 1000 highest-PMI
    pairs. Requires the POS tagger; silently does nothing (disclosed via
    stats.phrases_detected == 0) if it isn't installed, matching pos_filter's
    fallback behavior. Call `extract_phrases` directly first to inspect
    candidates before turning this on, if precision matters more than
    convenience for a given corpus.

    self_referential_threshold: flags any word appearing in at least this
    fraction of documents (default 0.5, i.e. half) as a candidate self-
    referential or generic-scaffolding hub, via stats.self_referential_
    candidates. Raw frequency alone can't distinguish "mentioned constantly
    within a few documents" (a real topic) from "present in almost every
    document" (the corpus's own subject name, or generic prose scaffolding
    in full-text corpora — "our research shows," "in this study") — a word
    can rank far down a top-N-by-raw-count list and still be the single most
    universal word in the corpus. Every node also carries a
    "document_frequency" attribute for the same check from the Data
    Laboratory directly. Check this list before trusting a graph, the same
    way stats.pos_filter_applied or stats.lemmatization get checked — don't
    rely on having remembered to eyeball a frequency ranking manually.

    exclude_self_referential: if True, every word flagged by
    self_referential_threshold is actually dropped from the graph before
    windowing (gap-closing, same as pos_filter/min_word_frequency), not just
    reported. Consider this seriously on large multi-document corpora: a
    high min_word_frequency floor, on its own, can systematically select FOR
    generic words rather than against them — a word needs sustained
    presence across many documents to rack up a large total count, and
    "spread across most documents" is close to the definition of generic,
    not topical. On a real 255-document corpus, requiring 200+ total
    occurrences left half the surviving vocabulary flagged as appearing in
    most documents; min_word_frequency alone was solving the wrong problem
    at that scale. Default False (report only) because dropping ~half a
    corpus's vocabulary is a real methodological choice to make
    deliberately, not a default to apply silently.

    context_snippets: how many short excerpts of original surrounding text to
    attach to each self_referential_candidate (default 0, off). This exists
    because document-frequency ratio alone can't tell "genuinely generic
    scaffolding word" apart from "genuinely topical hub word that just
    happens to appear in many documents" — on real data (a 255-document text
    corpus), both kinds of words land in the same 40-50% document-frequency band, and
    graph-structural signals (degree, edge-weight concentration after
    backbone extraction) don't reliably separate them either.
    peak_document_count (see below) is a real, if imperfect, signal here —
    scaffolding words rarely repeat more than a dozen or so times even in
    their heaviest document, while a word with a genuine concentrated
    sub-topic (even one hiding inside what looks like generic vocabulary
    overall) spikes far higher in the documents actually about it. But that
    gap won't be equally clean on every corpus, and it still can't be
    trusted blind: excerpts are what confirm it's a real topic rather than,
    say, one document that happens to repeat a word oddly. This surfaces
    excerpts from the documents with the *highest* count of the word first
    (not just the first documents it happens to appear in), specifically so
    a word that reads as filler in one random sentence but is the
    concentrated subject of a handful of documents doesn't get missed — this
    happened on real data: one word read as generic from two arbitrary
    excerpts, but its highest-count document used it well over a hundred
    times and turned out to be a genuine article about that word's own
    subject. A word that's generic scaffolding in one corpus could be
    exactly the topic in another — rather than guessing with a hardcoded
    word list (which would silently overfit to whichever corpus it was
    tuned on), this gives a human — or the assistant — the real evidence
    needed to judge it on any dataset, without hand-grepping the source
    text. Excludes
    nothing by itself; combine with a manually curated extra_stopwords list
    once the gray zone has actually been read.

    Returns {"nodes": [...], "edges": [...], "stats": {...}} — nodes and edges
    are already in the shape gephi_add_nodes / gephi_add_edges expect. stats
    includes "lemmatization": "active" or "unavailable" so the caller can
    disclose which mode actually ran, "document_count" so a caller can tell
    whether boundaries were respected, "phrases_detected" (count of merged
    bigrams actually used, 0 if merge_phrases was off or found none), and
    "self_referential_candidates" (words whose document-frequency ratio
    clears self_referential_threshold, sorted highest-ratio first — each
    entry is {"word", "document_frequency", "document_ratio",
    "peak_document_count"}, plus "context" (a list of excerpt strings) when
    context_snippets > 0).
    """
    if window_size < 2:
        raise ValueError("window_size must be at least 2 (need at least one neighbor to connect)")
    if pos_filter not in (None, "nouns"):
        raise ValueError('pos_filter must be None or "nouns"')

    documents = [text] if isinstance(text, str) else list(text)
    pos_filter_applied = pos_filter is not None and LEMMATIZATION_AVAILABLE

    stop = DEFAULT_STOPWORDS
    if extra_stopwords:
        # Lemmatize user-provided stopwords too, so "replied" matches the
        # lemmatized token "reply" regardless of which surface form the
        # caller happened to type.
        stop = stop | frozenset(lemmatize([w.lower() for w in extra_stopwords]))

    # Pass 1: tag every document. Phrase merging (if requested) needs the
    # tagged sequence, unfiltered, across the whole corpus before anything
    # else happens to it — merging has to see original adjacency, and PMI
    # needs corpus-wide bigram/unigram counts.
    raw_word_count = 0
    tagged_documents: list[list[tuple[str, str]]] = []
    for document in documents:
        raw_tokens = tokenize(document)
        tagged_documents.append(_tag_and_lemmatize(raw_tokens))
        raw_word_count += len(raw_tokens)

    phrases_detected: dict[tuple[str, str], str] = {}
    if merge_phrases and LEMMATIZATION_AVAILABLE:
        phrases_detected = extract_phrases(tagged_documents)
        # A stopword (or an extra_stopword like a corpus's own self-
        # referential subject name) must not survive by hiding inside a
        # merged phrase — phrase detection runs before stopword filtering
        # (it needs the original adjacency), so without this a pair like
        # ("customer", "service") merges into "customer_service" and evades
        # a stopword list that explicitly named both halves.
        phrases_detected = {
            pair: merged for pair, merged in phrases_detected.items()
            if pair[0] not in stop and pair[1] not in stop
        }

    # Pass 2: merge phrases, apply pos_filter, lemmatize/stopword-filter, and
    # count global frequency, before any windowing happens. min_word_frequency
    # needs the corpus-wide count decided up front so a rare word can be
    # dropped from windowing the same way a filtered-out part of speech is:
    # removed before its neighbors are indexed, so survivors close the gap
    # and become adjacent, rather than windowing around a hole.
    per_document_tokens: list[list[str]] = []
    frequency: Counter[str] = Counter()
    document_frequency: Counter[str] = Counter()
    peak_document_count: dict[str, int] = {}
    for tagged in tagged_documents:
        if phrases_detected:
            tagged = _merge_phrases(tagged, phrases_detected)
        if pos_filter_applied:
            tagged = [(w, pos) for w, pos in tagged if pos == "noun"]
        lemmas = [w for w, _pos in tagged]
        tokens = [w for w in lemmas if w not in stop and len(w) > 1]
        per_document_tokens.append(tokens)
        frequency.update(tokens)
        document_frequency.update(set(tokens))
        for word, count in Counter(tokens).items():
            if count > peak_document_count.get(word, 0):
                peak_document_count[word] = count

    if min_word_frequency > 1:
        frequency = Counter({w: c for w, c in frequency.items() if c >= min_word_frequency})

    # A word that shows up in nearly every document is a candidate self-
    # referential/generic hub regardless of its raw count — the count alone
    # can't distinguish "mentioned constantly within a few articles" (a real
    # topic) from "present in almost every article" (the corpus's own
    # subject, or generic scaffolding vocabulary). Document frequency is the
    # metric that catches the second case; raw frequency alone missed
    # exactly this on a real corpus (a word in 254 of 255 documents survived
    # a manual top-40-by-raw-frequency check because plenty of individually
    # rarer, more topical words outranked it in absolute count that one time,
    # even though almost nothing in the corpus is more universal than it).
    self_referential_candidates = []
    if documents:
        for word, count in frequency.items():
            ratio = document_frequency[word] / len(documents)
            if ratio >= self_referential_threshold:
                candidate = {
                    "word": word, "document_frequency": document_frequency[word],
                    "document_ratio": round(ratio, 3),
                    "peak_document_count": peak_document_count.get(word, 0),
                }
                if context_snippets > 0:
                    candidate["context"] = _context_snippets(word, documents, context_snippets)
                self_referential_candidates.append(candidate)
        self_referential_candidates.sort(key=lambda c: -c["document_ratio"])

    if exclude_self_referential and self_referential_candidates:
        excluded = {c["word"] for c in self_referential_candidates}
        frequency = Counter({w: c for w, c in frequency.items() if w not in excluded})

    # Pass 2: window each document using only surviving words.
    edge_weights: Counter[tuple[str, str]] = Counter()
    kept_word_count = 0
    for tokens in per_document_tokens:
        tokens = [w for w in tokens if w in frequency]
        kept_word_count += len(tokens)

        # Windowing happens per-document: this loop never sees tokens from
        # any other document, so distance and adjacency are only ever
        # measured within one unit of text.
        for i, word in enumerate(tokens):
            for distance in range(1, window_size):
                j = i + distance
                if j >= len(tokens):
                    break
                other = tokens[j]
                if other == word:
                    continue
                pair = tuple(sorted((word, other)))
                edge_weights[pair] += (window_size - distance)

    nodes = [
        {
            "id": word,
            "label": word,
            "attributes": {
                "frequency": count,
                "document_frequency": document_frequency[word],
            },
        }
        for word, count in frequency.items()
    ]
    edges = [
        {"source": a, "target": b, "weight": float(weight), "directed": False}
        for (a, b), weight in edge_weights.items()
        if weight >= min_edge_weight
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "raw_word_count": raw_word_count,
            "kept_word_count": kept_word_count,
            "unique_words": len(nodes),
            "words_filtered": raw_word_count - kept_word_count,
            "edge_count": len(edges),
            "document_count": len(documents),
            "lemmatization": "active" if LEMMATIZATION_AVAILABLE else "unavailable",
            "pos_filter_applied": pos_filter_applied,
            "phrases_detected": len(phrases_detected),
            "self_referential_candidates": self_referential_candidates,
        },
    }


def extract_backbone(edges: list[dict], alpha: float = 0.05) -> dict:
    """Prune a weighted graph to its statistically significant backbone.

    Implements the disparity filter (Serrano, Boguna, and Vespignani 2009): a
    principled alternative to dropping edges below a single global weight
    cutoff. A flat threshold (e.g. min_edge_weight) removes an edge for being
    weak in absolute terms, which unfairly prunes a low-degree, specialized
    node's only real connection while leaving an equally-weak edge on a
    high-degree hub untouched just because the hub has other edges to
    compare it to. The disparity filter instead asks, per node: given this
    node's total edge weight split across its `k` neighbors, is this
    particular edge's share more concentrated than chance would produce? A
    node's own edges are compared only to each other, so significance is
    local, not a single global bar every edge must clear.

    For a node i with degree k and strength s (sum of incident weights), an
    edge of weight w gets a p-value under the null hypothesis that weight is
    distributed randomly among i's edges:

        p_ij = w_ij / s_i
        alpha_ij = (1 - p_ij) ** (k_i - 1)

    An edge survives if alpha_ij <= `alpha` from *either* endpoint's
    perspective (it only needs to be significant to one of the two nodes it
    connects). Nodes with degree 1 have no distribution to test against —
    their only edge is always kept, matching the standard convention that
    the filter should not disconnect a node entirely.

    edges: list of {"source", "target", "weight"} dicts (same shape
    build_cooccurrence_graph returns). alpha: significance threshold — lower
    keeps fewer edges (stricter backbone); 0.05 and 0.01 are common choices
    in the literature. Isolated nodes are not created or removed here; this
    only decides which edges survive; drop now-unconnected nodes yourself if
    the caller wants a strictly cleaner node list.

    Returns {"edges": [...] (surviving edges, same shape as input),
    "stats": {"edges_kept", "edges_removed", "alpha"}}.
    """
    strength: dict[str, float] = Counter()
    degree: dict[str, int] = Counter()
    for e in edges:
        w = e["weight"]
        strength[e["source"]] += w
        strength[e["target"]] += w
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    def _alpha(node: str, weight: float) -> float:
        k = degree[node]
        if k <= 1:
            return 0.0  # only edge this node has; always significant
        p = weight / strength[node]
        return (1 - p) ** (k - 1)

    kept = [
        e for e in edges
        if min(_alpha(e["source"], e["weight"]), _alpha(e["target"], e["weight"])) <= alpha
    ]

    return {
        "edges": kept,
        "stats": {
            "edges_kept": len(kept),
            "edges_removed": len(edges) - len(kept),
            "alpha": alpha,
        },
    }
