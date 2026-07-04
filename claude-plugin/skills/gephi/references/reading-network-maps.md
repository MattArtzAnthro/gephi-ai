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

Notes that keep the process honest: it is iterative at every level (later
steps revise earlier categories), and whether its outputs are hypotheses or
findings depends on the situation — say which they are.
