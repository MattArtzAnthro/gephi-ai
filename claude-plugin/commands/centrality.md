---
description: Run centrality analysis and identify the most important nodes
allowed-tools: mcp__gephi-mcp__*
---

# Centrality Analysis Workflow

Run comprehensive centrality analysis to identify the most important and influential nodes in the graph.

## Steps

1. **Health check**: Call `gephi_health_check` to confirm Gephi is running.

2. **Graph info**: Call `gephi_get_project_info` to get node/edge counts and graph type.

3. **Compute all centrality metrics**:
   - Call `gephi_compute_degree` for degree distribution
   - Call `gephi_compute_betweenness` for betweenness centrality, closeness, and eccentricity
   - Call `gephi_compute_pagerank` for PageRank importance
   - Call `gephi_compute_eigenvector` for eigenvector centrality

4. **Query top nodes**: Call `gephi_query_nodes` with limit 100 to retrieve node data. Sort and identify:
   - Top 10 by degree (hubs)
   - Top 10 by betweenness centrality (bridges)
   - Top 10 by PageRank (importance)
   - Nodes that appear in multiple top-10 lists (key actors)

5. **Visualize by betweenness**: Call `gephi_color_by_ranking` with:
   - column: `"betweenesscentrality"`
   - Light blue to dark red gradient: `r_min: 200, g_min: 220, b_min: 255, r_max: 180, g_max: 0, b_max: 0`

6. **Size by PageRank**: Call `gephi_size_by_ranking` with column `"pageranks"`, `min_size: 3`, `max_size: 30`.

7. **Layout**: Call `gephi_run_layout` with algorithm `"forceatlas2"`, 1000 iterations.

8. **Report**: Present a ranked table of key nodes with their centrality scores. Highlight:
   - **Hubs**: High degree nodes
   - **Bridges**: High betweenness, low degree (connecting different communities)
   - **Authorities**: High PageRank / eigenvector centrality
   - **Vulnerabilities**: Nodes whose removal would fragment the network
