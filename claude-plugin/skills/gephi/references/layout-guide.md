# Layout Algorithm Guide

## Algorithm Selection Matrix

| Algorithm | Best For | Graph Size | Speed | Quality |
|-----------|----------|------------|-------|---------|
| **ForceAtlas2** | Most networks, community visualization | <50k nodes | Medium | Excellent |
| **Yifan Hu** | Large graphs, fast overview | >10k nodes | Fast | Good |
| **Fruchterman-Reingold** | Small networks, even spacing | <5k nodes | Slow | Good |
| **Circular** | Ring layouts, ordered visualization | Any | Instant | Varies |
| **Random** | Reset positions before re-layout | Any | Instant | N/A |

## ForceAtlas2 (Default Choice)

The go-to algorithm for most network analysis. Produces layouts that reveal community structure naturally.

### When to Use
- Social networks
- Citation networks
- Any graph where you want to see clusters
- Graphs with 100-50,000 nodes

### Key Parameters
| Parameter | Default | Effect |
|-----------|---------|--------|
| `scalingRatio` | 2.0 | Higher = more spread out |
| `gravity` | 1.0 | Higher = more compact, prevents drift |
| `linLogMode` | false | True emphasizes community separation |
| `barnesHutOptimize` | false | True for faster computation on large graphs |
| `strongGravityMode` | false | True = stronger pull to center |
| `edgeWeightInfluence` | 1.0 | 0 = ignore weights, 1 = full influence |
| `jitterTolerance` | 1.0 | Higher = faster but less precise |

### Recommended Settings by Graph Type
**Community-focused** (find clusters):
```json
{"scalingRatio": 2.0, "gravity": 1.0, "linLogMode": true}
```

**Large graph** (>10k nodes):
```json
{"scalingRatio": 10.0, "gravity": 1.0, "barnesHutOptimize": true}
```

**Dense graph** (many edges):
```json
{"scalingRatio": 5.0, "gravity": 2.0, "jitterTolerance": 0.5}
```

**Sparse graph** (few edges):
```json
{"scalingRatio": 1.0, "gravity": 0.5}
```

### Iteration Guidelines
- Small graph (<500 nodes): 200-500 iterations
- Medium graph (500-5k): 500-1000 iterations
- Large graph (5k-50k): 1000-3000 iterations
- Check layout status and stop early if converged

## Yifan Hu

Fast multilevel force-directed algorithm. Good for initial positioning of large graphs, often followed by ForceAtlas2 refinement.

### When to Use
- Graphs with >10k nodes
- Quick overview before detailed analysis
- When ForceAtlas2 is too slow

### Key Parameters
| Parameter | Default | Effect |
|-----------|---------|--------|
| `stepRatio` | 0.95 | Convergence speed (lower = faster) |
| `optimalDistance` | 100 | Target distance between nodes |
| `theta` | 1.2 | Barnes-Hut approximation (higher = faster, less precise) |

### Recommended Iterations
- 100-500 iterations (converges fast)

## Fruchterman-Reingold

Classic force-directed algorithm. Produces aesthetically pleasing layouts for small graphs with even node spacing.

### When to Use
- Small graphs (<1000 nodes)
- When you want even spacing
- Academic/publication graphics
- Simple, balanced layouts

### Key Parameters
| Parameter | Default | Effect |
|-----------|---------|--------|
| `area` | 10000 | Layout area size |
| `gravity` | 10.0 | Attraction to center |
| `speed` | 1.0 | Convergence speed |

### Recommended Iterations
- 500-1000 iterations

## Circular

Arranges nodes in a circle. Useful for specific visualization needs.

### When to Use
- Ordered/sequential data
- Comparing node positions by attribute
- Ring/cycle visualization
- Combined with other algorithms (circular first, then force-directed)

## Random

Assigns random positions. Use as a reset before applying another algorithm.

### When to Use
- Reset positions when a layout gets stuck
- Starting fresh before a new layout algorithm
- Testing

## Layout Workflow Tips

1. **Start with Random** if the previous layout is distorted
2. **Run ForceAtlas2** with default settings first
3. **Check status** with `gephi_get_layout_status`
4. **Stop early** with `gephi_stop_layout` if the layout looks good
5. **Tune parameters** with `gephi_set_layout_properties` for refinement
6. **Run a second pass** with different parameters if needed

## Common Workflow Patterns

### Quick Exploration
```
gephi_run_layout({algorithm: "yifanhu", iterations: 200})
# Check result
gephi_run_layout({algorithm: "forceatlas2", iterations: 500})
```

### Publication Quality
```
gephi_run_layout({algorithm: "forceatlas2", iterations: 1000, properties: {linLogMode: true, scalingRatio: 2.0}})
# Wait for completion
gephi_run_layout({algorithm: "forceatlas2", iterations: 200, properties: {scalingRatio: 1.0, gravity: 2.0}})
```

### Large Graph
```
gephi_run_layout({algorithm: "yifanhu", iterations: 300})
# Quick positioning
gephi_run_layout({algorithm: "forceatlas2", iterations: 500, properties: {barnesHutOptimize: true, scalingRatio: 10.0}})
```
