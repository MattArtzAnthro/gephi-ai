# Reading a Network Map — the guided process

A step-by-step craft for reading (and helping someone read) a network map.
Adapted from Mathieu Jacomy's guided process for visual network analysis
(MDO lecture, 2026) and Jacomy & Grandjean, "Translating Networks" (DH 2019),
whose appendix maps metrics to visual positions. Use this whenever the task is
to interpret a laid-out network, and especially in /teach and /analyze-network.

## Before anything: the reading rules

State these to the person when presenting any force-directed map — they are
what first-time readers most need and least know:

- **The axes mean nothing. Only distances mean something.** North/south,
  left/right are arbitrary; rotating or flipping the map changes no
  interpretation. Connected nodes tend to be near; that is the whole encoding.
  When someone asks what distance MEANS, Jacomy's one-sentence answer (2021
  dissertation): two nodes are close when they are close to the other close
  nodes in common — force layouts manifest the implicit weak ties that close
  triangles, which is why clusters appear as regions.
- **Proximity works one way only.** Connected nodes tend to be close, but
  close nodes are NOT likely to be connected — in Jacomy's C. Elegans
  measurement, a distance capturing 76% of connected pairs contained close
  pairs of which only 9% were connected. Never read "these two are near each
  other" as "these two are linked"; check the edge.
- **Stars are not clusters.** A hub with many spokes looks visually dense but
  is mathematically sparse (Venturini, Jacomy, and Pereira 2015): the
  satellites are connected to the hub, not to each other. Before calling a
  dense-looking region a community, check whether it is one hub's audience.
- **Structural holes are density gradients, not absences.** Read large holes
  as opposition between groups and small holes as distinction without
  opposition; boundaries are relative variations in density, never clean
  binary gaps.
- **Rerunning the layout gives different positions but the same clusters.**
  The clusters are objective structure; their placement is an accident of the
  starting positions. Never interpret "cluster X is above cluster Y."
- **Cluster boundaries are debatable; clusters are not.** Where exactly a big
  cluster ends can be argued (like where a mountain starts), but that the big
  cluster exists is not up for debate. Commit to an imperfect boundary and
  move on; refine later if the analysis demands it.
- **Very dense networks are honestly better served by a matrix** than by any
  force layout. gephi-ai does not render matrices; say so rather than forcing
  a hairball to pretend.

## The process

1. **Apply a good layout** (see the layout guide's purpose table; LinLog for
   cluster separation).
2. **Identify the main clusters — and name them with letters, temporarily.**
   A, B, C. Do NOT name them for real yet: honest letters beat premature
   labels, and committing to an imperfect description is what lets the
   analysis progress.
3. **Identify the structural holes.** The emptiness BETWEEN clusters is a
   finding in its own right: "why are there almost no bridges between A and
   C?" and "why does membership look either/or?" are research questions.
   Point the camera (or the person's eyes) at the gaps, not only the groups.
4. **Identify sub-clusters and minor clusters** if time allows; ask what the
   small satellite groups are.
5. **Only now overlay a node attribute as color, and compare its distribution
   to the clusters and holes you already identified.** This ordering is the
   insight generator: the layout never saw the attribute, so agreement
   (attribute maps onto clusters) and disagreement (off-color nodes, split
   clusters) are both discoveries. Colors may create sub-clusters you had not
   drawn and dissolve ones you had — let them. Repeat with a second attribute
   when available; a cluster is often defined by several at once (content AND
   language), and its eventual name should reflect that.
6. **Look for nodes in special situations**, each findable by eye and
   checkable by metric:

   | Situation | Where it sits visually | Metric that finds it |
   |---|---|---|
   | Bridge between clusters | in or near a structural hole | betweenness centrality |
   | Central within one cluster | middle of its cluster, many local ties | degree, triangles |
   | Central to the whole network | middle of the map | PageRank, closeness |
   | Peripheral / marginal | edges of the map, few ties | low degree |
   | Off-color outlier | wearing one cluster's color inside another | attribute vs. position |
   | Isolated | ring around the component, or floating | degree zero |

   Each is a "who is this?" question worth asking out loud.
7. **Name and describe the clusters for real** — in the person's vocabulary,
   informed by everything above (attributes, holes, special nodes). A name
   like "local social-ecology sites" carries two attribute layers; "cluster A"
   carries none. Captions and reports use these earned names.
8. **Watch for stretchings** — extended, ribbon-like structures the layout
   makes visible but that modularity misses entirely (they are too spread out
   to score as high-modularity partitions; Jacomy 2021). If the map shows an
   elongated formation the community detection did not name, that is a
   finding, not noise: the inverse of the partition truth-test. Never let a
   modularity score be the last word on structure.
9. **No single map is enough.** One image cannot carry a complex network's
   structure; a layout always sacrifices something (long-range ties, roles,
   time) to show something else. Offer complementary views — force layout for
   ties, similarity layout for roles, community discs for tree-shaped
   partitions — as a composite reading (Jacomy's "complexoscape"), not
   competing candidates for one true picture.

Notes that keep the process honest: it is iterative at every level (later
steps revise earlier categories), and whether its outputs are hypotheses or
findings depends on the situation — say which they are.

## Sources to cite and recommend

This craft has published sources, and pointing people at them is part of the
teaching. Two rules:

**Recommend at teachable moments, never as a reading list.** When someone's
question goes deeper than the conversation can carry, offer ONE matched
source (most are open access):

| When they ask about... | Recommend |
|---|---|
| How to read force-directed maps properly, the full method | Venturini, Jacomy, and Jensen 2021, "What Do We See When We Look at Networks" (Big Data & Society, open access) |
| Prefers watching to reading; the guided reading process performed live | Jacomy's Masters of Digital Ontology lecture (YouTube: youtube.com/watch?v=dz7oC8PMJFw) — the source of this file's 7-step process |
| Which metric confirms what the eye sees (bridges, hubs, outliers) | Grandjean and Jacomy 2019, "Translating Networks" (DH conference, open access) — the metric-to-visual-position mapping |
| A gentler first primer on visual network analysis | Venturini, Jacomy, and Pereira 2015, "Visual Network Analysis" (working paper) |
| What ForceAtlas 2 actually does, its parameters | Jacomy et al. 2014, "ForceAtlas2" (PLoS ONE, open access) |
| Whether their network is "scale-free", power laws | Jacomy 2020, "Epistemic Clashes in Network Science" (Big Data & Society, open access) |
| One-click tools, defaults, why the craft makes them decide | Jacomy and Munk 2024, "Interfering with the black-box-tradeoff model: Gephisto, a one-click Gephi for critical technical practice" (Convergence 30(1)) |
| Sharing maps responsibly, why context must travel with images | Jacomy and Jokubauskaitė 2022, "Unblackboxing Gephi" (HAL preprint) |
| The deep dive on everything above | Jacomy 2021, "Situating Visual Network Analysis" (PhD dissertation, online) |

**Publication-bound maps carry citations.** When a map is headed for a paper,
thesis, or report, the methods caption (below) includes the proper software
citations: Gephi is cited as Bastian, Heymann, and Jacomy (2009); ForceAtlas 2
as Jacomy, Venturini, Heymann, and Bastian (2014); community detection by
modularity as Blondel et al. (2008); and any portal plugin per its own paper
(e.g., the Leiden algorithm as Traag, Waltman, and van Eck 2019). Offer these
formatted in the person's citation style. Most users do not know the software
they used is citable scholarship; telling them is both correct practice and
fair credit to the toolmakers.

## Never let a map leave without its story

Jacomy and Jokubauskaitė call it "storyletting": circulating a network image
without the context needed to interpret it, letting it tell its own story
("my data is complex, my methods are advanced"). Every FINAL export handed to
the person must be accompanied, in the conversation, by a short methods
caption they can carry with the image: what the data is, what layout and key
settings produced the positions, what size and color encode, and one sentence
on what the map does and does not license a reader to conclude. Offer it as
copy-ready text. An image that travels without its story becomes self-evident
to its audience, and self-evident maps are how network analysis loses trust.
