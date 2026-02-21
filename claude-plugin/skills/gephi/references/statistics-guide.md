# Statistics Interpretation Guide

## Overview

Gephi statistics compute graph-level and node-level metrics. After running a statistic, results are stored as node/edge attributes that can be used for coloring and sizing.

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
- Resolution < 1.0: Fewer, larger communities
- Resolution > 1.0: More, smaller communities

### Node Attributes Created
| Attribute | Type | Description |
|-----------|------|-------------|
| `modularity_class` | Integer | Community ID (0, 1, 2, ...) |

### Graph-Level Result
| Result | Description |
|--------|-------------|
| `modularity` | Score from -0.5 to 1.0. Higher = clearer community structure. >0.3 is significant. |

### How to Visualize
`gephi_color_by_partition({column: "modularity_class"})` - Each community gets a distinct color.

### Interpretation
- **0.0-0.3**: Weak community structure
- **0.3-0.5**: Moderate community structure
- **0.5-0.7**: Strong community structure
- **>0.7**: Very strong community structure (may indicate disconnected components)

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
- `gephi_size_by_ranking({column: "degree", min_size: 5, max_size: 40})` - Hub nodes appear larger
- `gephi_color_by_ranking({column: "degree"})` - Gradient from low to high connectivity

### Interpretation
- **High degree nodes**: Hubs, influencers, central actors
- **Power-law distribution**: Scale-free network (few hubs, many low-degree nodes)
- **Normal distribution**: Random-like network

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
Node importance based on the quality and quantity of incoming links. A node is important if it's linked to by other important nodes (recursive definition).

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
7. `gephi_compute_eigenvector` - Influence (optional)
8. `gephi_compute_hits` - Hub/authority (optional, directed graphs)
