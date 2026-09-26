# Statistics Interpretation Guide

## Overview

Gephi statistics compute graph-level and node-level metrics. After running a statistic, results are stored as node and edge attributes that can be used for colouring and sizing. When a statistic has a known defect in Gephi, its reply carries a `caveats` list; read it and pass on what applies.

## Modularity (Community Detection)

### What It Measures
Groups nodes into communities (clusters) using the Louvain method. Nodes in the same community are more densely connected to each other than to the rest of the graph.

### When to Use
- Identify social groups in a social network
- Find topic clusters in citation networks
- Detect organizational structure
- Any exploratory network analysis

### Tool
`gephi_compute_modularity` with `{resolution: float}`
- Resolution 1.0 (default): Standard communities
- Resolution > 1.0 (e.g. 1.5): Fewer, larger communities
- Resolution < 1.0 (e.g. 0.3): More, smaller, tightly-knit communities

**Watch the direction.** Gephi implements the Lambiotte-Delvenne-Barahona
resolution, where *raising* the value merges communities. This is the opposite
of the gamma parameter in much of the modularity literature, where raising the
value splits them. Sanity-check by running two resolutions and comparing the
`modularity_class` count before reporting anything about community granularity.

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `modularity_class` | Integer | Community ID (0, 1, 2, ...) |

### Graph-Level Result
| Result | Description |
|--------|-------------|
| `modularity` | Score from -0.5 to 1.0: how many more edges fall inside the communities than chance would place there, given the same degrees. Not a measure of strength on its own. |

### How to Visualize
`gephi_color_by_partition({column: "modularity_class"})` - Each community gets a distinct color.

### Interpretation
- **The score alone never shows strong communities.** Random graphs with the same degrees score 0.3 to 0.6, and sparse, hub-heavy networks sit at the top of that range. No value is a significance threshold.
- **Check stability before naming communities.** Run `gephi_community_stability`, report `mean_stability` in plain words, and name only the groups in `stable_cores`. When `consensus_warning` appears, the communities are loose: describe the stable cores instead.
- **A very high score** can mean the graph is several disconnected components. Check with `gephi_compute_connected_components`.

## Degree

### What It Measures
The number of connections each node has. In directed graphs, distinguishes between incoming (in-degree) and outgoing (out-degree) connections.

### When to Use
- Identify well-connected nodes (hubs)
- Understand connection distribution
- Basic network characterization
- Always run this as a baseline metric

### Tool
`gephi_compute_degree`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `degree` | Integer | Total connections |
| `indegree` | Integer | Incoming connections (directed) |
| `outdegree` | Integer | Outgoing connections (directed) |

### How to Visualize
- `gephi_size_by_ranking({column: "degree"})` - Hub nodes appear larger (the default range, 10 to 100, gives about one to ten on screen)
- `gephi_color_by_ranking({column: "degree"})` - Gradient from low to high connectivity

### Weighted degree
When ties have weights (messages sent, co-authored papers, words co-occurring),
the count of ties and the total weight of ties can rank nodes differently.
`gephi_run_statistic("Weighted Degree")` writes a "Weighted Degree" column: the
sum of each node's edge weights. Report which of the two a ranking uses.

### Interpretation
- **High degree nodes**: Hubs, influencers, central actors
- **Heavy-tailed distribution** (a few high-degree hubs, many low-degree nodes):
  describe it as hub dominance in *this* network. Do NOT call it "scale-free" or
  fit a "power law": power-law and log-normal fits are nearly
  indistinguishable in practice, and the label smuggles in a universal-law
  claim (Jacomy 2020). Most real networks are not scale-free on a formal test
  (Broido and Clauset 2019).
- **Describe a heavy tail from the profile.** `gephi_profile_graph` gives what
  a plain description needs, under `degree`:
  - `gini`: how unequal the degrees are, from 0 (every node has the same
    number of ties) to 1 (one node has them all);
  - `top_5pct_edge_share`: the share of all ties that touch the best-connected
    5% of nodes;
  - `max` against `median`: how far the largest hub sits above a typical node.

  "The best-connected 5% of nodes touch 60% of the ties, and the largest hub has
  40 times the median degree" is a finding a reader can check. Choose the
  numbers that fit the question; there is no cutoff that makes a tail "heavy."
- **A formal test needs a separate package.** Fitting and comparing
  distributions properly needs a statistics package this plugin does not
  bundle. Ask before installing one. Even then, never report a fitted exponent
  as a finding: the fit says which curve is least bad for these data, not that
  the network follows a law (Broido and Clauset 2019).
- **Even distribution**: connections spread across nodes, no dominant hubs

### Directed communication data: compare in and out
In email, messaging, or reply networks, read `indegree` (ties received) next to
`outdegree` (ties sent) for the top nodes. A node that sends widely and hears
back rarely is often a mailing list, an announcement account, or a system
sender, not a person at the centre of the conversation. Report such nodes
separately, and test what they do to the picture with `gephi_whatif` removing
them. Judge each case by what the node is; there is no fixed in-to-out ratio
that marks one.

## Betweenness Centrality

### What It Measures
How often a node lies on the shortest path between other pairs of nodes. High betweenness = the node is a bridge or broker.

### When to Use
- Find bridge nodes connecting communities
- Identify information bottlenecks
- Detect gatekeepers in social networks
- Vulnerability analysis (removing bridges fragments the network)

### Tool
`gephi_compute_betweenness`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `betweenesscentrality` | Double | Betweenness score (0 to 1, normalized) |
| `closnesscentrality` | Double | Closeness centrality |
| `harmonicclosnesscentrality` | Double | Harmonic closeness centrality |
| `eccentricity` | Double | Maximum shortest path to any other node |

Gephi's closeness carries a known caveat (the reply's `caveats` list says
which). For "central to the whole network," PageRank is the safer read.

### Graph-Level Results
| Result | Description |
|--------|-------------|
| `average_path_length` | Average shortest path between all pairs |
| `diameter` | Longest shortest path in the graph |
| `radius` | Shortest eccentricity |

### How to Visualize
- `gephi_color_by_ranking({column: "betweenesscentrality"})` - Bridges appear as hot spots
- `gephi_size_by_ranking({column: "betweenesscentrality"})` - Bridge nodes appear larger

### Interpretation
- **High betweenness, low degree**: Bridge node connecting different clusters
- **High betweenness, high degree**: Central hub and bridge
- **Low betweenness, high degree**: Local hub within a cluster

## PageRank

### What It Measures
Node importance based on the quality and quantity of incoming links. A node is important if other important nodes link to it (recursive definition).

### When to Use
- Web page ranking
- Citation influence
- Social media influence
- Any directed network importance ranking

### Tool
`gephi_compute_pagerank`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `pageranks` | Double | PageRank score (sum across all nodes = 1.0) |

### How to Visualize
- `gephi_size_by_ranking({column: "pageranks"})` - Important nodes appear larger
- `gephi_color_by_ranking({column: "pageranks"})` - Gradient from low to high importance

### Interpretation
- Higher PageRank = more important in the network's link structure
- Differs from degree: a node with few but high-quality incoming links can outrank a node with many low-quality links

## Eigenvector Centrality

### What It Measures
Similar to PageRank but for undirected networks. Measures influence: a node is important if its neighbors are also important.

### When to Use
- Undirected social networks
- Collaboration networks
- When PageRank is not appropriate (undirected graph)

### Tool
`gephi_compute_eigenvector`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `eigencentrality` | Double | Eigenvector centrality (0 to 1) |

### Caveat
Gephi's eigenvector centrality stops iterating before its values settle on some
networks, which can put the wrong node first. `gephi_compute_eigenvector` runs
1,000 iterations, which recovers the order on known cases, but values can still
differ from an exact calculation by up to about a tenth. Do not rank on small
differences: compute PageRank as well, compare the two top lists, and say so when
they disagree.

### How to Visualize
- `gephi_size_by_ranking({column: "eigencentrality"})` - Influential nodes appear larger
- `gephi_color_by_ranking({column: "eigencentrality"})` - Gradient of influence

## Connected Components

### What It Measures
Identifies groups of nodes that are reachable from each other. Each group is a connected component.

### When to Use
- Check if the graph is connected or fragmented
- Identify isolated subgroups
- Pre-processing: extract the giant component for analysis

### Tool
`gephi_compute_connected_components`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `componentnumber` | Integer | Component ID (0, 1, 2, ...) |

### Graph-Level Results
| Result | Description |
|--------|-------------|
| `connected_components` | Number of distinct components |

### How to Visualize
`gephi_color_by_partition({column: "componentnumber"})` - Each component gets a distinct color.

### Follow-Up
`gephi_extract_giant_component` to keep only the largest component for further analysis.

## Clustering Coefficient

### What It Measures
How connected a node's neighbors are to each other. High clustering = the node's neighbors also know each other (clique-like).

### When to Use
- Measure local cohesion
- Detect tightly-knit groups
- Compare with random network expectations
- Small-world network analysis

### Tool
`gephi_compute_clustering_coefficient`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `clustering` | Double | Local clustering coefficient (0 to 1) |

### Graph-Level Results
| Result | Description |
|--------|-------------|
| `average_clustering_coefficient` | Average across all nodes |

### Interpretation
- **~0**: Neighbors not connected (tree-like, star-like)
- **~0.5**: Moderate clustering
- **~1.0**: All neighbors connected to each other (clique)
- **High avg clustering + short path length**: Small-world network

## HITS (Hub and Authority)

### What It Measures
Two related scores:
- **Authority**: Node receives links from many good hubs
- **Hub**: Node links to many good authorities

### When to Use
- Web analysis
- Information flow networks
- Directed networks where you want to distinguish senders from receivers

### Tool
`gephi_compute_hits`

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `Authority` | Double | Authority score |
| `Hub` | Double | Hub score |

### How to Visualize
- `gephi_size_by_ranking({column: "Authority"})` - Show authoritative nodes
- `gephi_color_by_ranking({column: "Hub"})` - Show hub nodes

## Average Path Length

### What It Measures
The average shortest path between all pairs of nodes. Also computes diameter (longest shortest path).

### When to Use
- Understand how quickly information spreads
- Small-world analysis
- Network efficiency measurement

### Tool
`gephi_compute_avg_path_length`

### Graph-Level Results
| Result | Description |
|--------|-------------|
| `average_path_length` | Average shortest path |
| `diameter` | Longest shortest path |
| `radius` | Shortest eccentricity |

### Interpretation
- **Small avg path length relative to nodes**: "Small world" property
- **Six degrees of separation**: avg path ~6 is common in social networks
- **Large diameter**: Some nodes are very far apart

## Recommended Analysis Order

For comprehensive analysis, run statistics in this order:

1. `gephi_compute_degree` - Always first (fast, creates baseline)
2. `gephi_compute_connected_components` - Check connectivity
3. `gephi_compute_modularity` - Community structure
4. `gephi_compute_betweenness` - Bridge nodes (can be slow)
5. `gephi_compute_pagerank` - Node importance
6. `gephi_compute_clustering_coefficient` - Local cohesion
7. `gephi_compute_eigenvector` - Influence (optional; compare with PageRank)
8. `gephi_compute_hits` - Hub/authority (optional, directed graphs)

## Statistics Over Time

On a network with time data, run the same statistics in each period and compare
them (see references/change-over-time.md), or use Gephi's dynamic statistics for a
year-by-year series. A dynamic statistic needs `params={"window": ..., "tick": ...}`
in the network's time units; without them, or without time data, it is refused
with the network's time range.

## Paths Between Two Nodes

Average path length and diameter describe the whole network. For two named nodes,
`gephi_find_shortest_path` gives the path itself. Count steps (`weighting="none"`)
unless the weights mean something: "distance" when a weight is a length or a cost,
"strength" when a heavier tie means a closer one. `equally_short_paths` above 1
means the path shown is one of several, so no single middle node is the only link.

## References

Broido, Anna D., and Aaron Clauset. 2019. "Scale-Free Networks Are Rare."
*Nature Communications* 10: 1017.

Jacomy, Mathieu. 2020. "Epistemic Clashes in Network Science: Mapping the Tensions between Idiographic and Nomothetic Subcultures." *Big Data & Society* 7 (2).
