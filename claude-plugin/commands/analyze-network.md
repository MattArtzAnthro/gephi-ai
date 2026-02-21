---
description: Run comprehensive structural analysis and report network properties
allowed-tools: mcp__gephi-mcp__*
---

# Comprehensive Network Analysis

Run a full structural analysis of the current graph and present a detailed report of its properties.

## Steps

1. **Health check**: Call `gephi_health_check` to confirm Gephi is running.

2. **Basic stats**: Call `gephi_get_graph_stats` and `gephi_get_graph_type` to get node count, edge count, density, average degree, and directionality.

3. **Connectivity**: Call `gephi_compute_connected_components` to identify how many connected components exist. If more than one, note the fragmentation.

4. **Degree distribution**: Call `gephi_compute_degree`. Query nodes to understand the degree distribution — report min, max, average, and whether it follows a power-law (scale-free) or normal distribution.

5. **Community structure**: Call `gephi_compute_modularity` with resolution 1.0. Report the modularity score and number of communities.

6. **Path analysis**: Call `gephi_compute_avg_path_length` to get average path length, diameter, and radius.

7. **Clustering**: Call `gephi_compute_clustering_coefficient` to measure local cohesion.

8. **Centrality**: Call `gephi_compute_betweenness` and `gephi_compute_pagerank`.

9. **Report**: Present a structured summary:

   ### Network Overview
   - Nodes, edges, density, average degree, graph type

   ### Connectivity
   - Number of components, size of giant component

   ### Community Structure
   - Modularity score, number of communities, interpretation

   ### Small-World Properties
   - Average path length, clustering coefficient, comparison with random network expectations

   ### Key Nodes
   - Top 5 by degree, betweenness, and PageRank

   ### Network Classification
   - Classify the network type (scale-free, small-world, random, regular) based on the metrics
