# Layout Algorithm Guide

## Choosing a layout (by purpose)

Lead with what the person wants to see, not with algorithm names. When
explaining a choice, use the plain-language purpose, then name the layout.

Know which interpretation regime the network is in before judging any layout
(Jacomy 2021): SMALL networks (up to a few dozen nodes) are read
diagrammatically — follow the individual paths, so judge layouts by
legibility, minimal edge crossings, even spacing. LARGE networks are read
topologically — nobody follows individual edges; density patterns ARE the
message, so judge layouts by whether clusters, holes, and bridges show.
Applying small-network standards to a big map (or vice versa) is a category
error: a 30-node org chart does not need LinLog, and a 3,000-node map should
not be criticized for crossing edges.

| What the person wants | Use | Notes |
|---|---|---|
| "Show me the groups/communities" | ForceAtlas 2 (linLogMode true, gravity 0) | The default for almost everything; see the reference config below |
| Groups in a TREE-LIKE network (replies, retweets, seeded citations) | Community layout (`gephi_community_layout`) | Force layouts cannot separate star-shaped communities — run modularity first, then this; see the tree-like section below |
| "Who plays similar roles?" (even if not directly connected) | Similarity layout (`gephi_similarity_layout`) | Embedding-based; proximity = similar structural role, NOT connection — always say so when presenting. Compare against FA2; disagreements mark bridge/boundary actors |
| A huge network (50k+ nodes) | OpenOrd first, then a short ForceAtlas 2 pass | OpenOrd is built for scale; FA2 refines the detail |
| A quick, decent picture of a medium network | Yifan Hu | Fast spring layout, less community emphasis than FA2 |
| A small network with classic, even spacing | Fruchterman Reingold | Best under ~1k nodes; the "textbook" look |
| Nodes are overlapping | Noverlap (finishing pass) | Run after the main layout; also FA2's adjustSizes |
| Labels are overlapping before export | Label Adjust (finishing pass) | Run last, after sizing and labels are final |
| The layout is too spread out or too cramped | Contraction / Expansion | One-shot fix; or rerun FA2 with lower/higher scalingRatio |
| Rotate or flip the picture for presentation | Rotate / Mirror | Orientation only, structure unchanged |
| Start over from scratch | Random Layout | Scramble, then run the real layout |

All of the above ship with Gephi. The plugin portal
(gephi.org/desktop/plugins) adds more, and anything installed there is
immediately runnable here by name (gephi_list_layouts shows what is present).
Worth suggesting when the purpose fits:

| Purpose | Portal plugin |
|---|---|
| Points on a real map (lat/long data) | GeoLayout, Map of Countries |
| Arrange nodes in a circle by an attribute or ranking | Circular Layout |
| Two-type (bipartite) data in layers | Multipartite Layout |
| 3D exploration | Force Atlas 3D, Network Splitter 3D |
| Untangle a hairball for triage | Hairball Buster |

If someone asks for an effect no available layout gives, check the portal
before improvising: install in Gephi (Tools > Plugins), restart Gephi, and
the new layout appears in gephi_list_layouts.


Grounded in visual network analysis (VNA) research: Venturini, Jacomy, and Jensen,
"What do we see when we look at networks" (Big Data & Society, 2021) and Jacomy et al.,
"ForceAtlas2, a continuous graph layout algorithm" (PLoS ONE, 2014). The goal of a
layout is to translate topology into visible patterns: clusters appear as denser
gatherings separated by emptier zones, bridges sit between regions, central nodes move
toward middle positions. Judge a layout by whether those patterns are readable, and
expect to reach a good layout by iteration, not by one perfect setting.

## Algorithm Selection Matrix

| Algorithm | Best For | Graph Size | Speed | Quality |
|-----------|----------|------------|-------|---------|
| **ForceAtlas2** | Most networks, community visualization | <50k nodes | Medium | Excellent |
| **Yifan Hu** | Large graphs, fast overview | >10k nodes | Fast | Good |
| **Fruchterman-Reingold** | Small networks, even spacing | <5k nodes | Slow | Good |
| **Circular** | Ring layouts, ordered visualization | Any | Instant | Varies |
| **Random** | Reset positions before re-layout | Any | Instant | N/A |

## ForceAtlas2 (Default Choice)

The go-to algorithm. For revealing community structure, the VNA literature treats
**LinLog mode with gravity 0** as the reference configuration: Noack showed
logarithmic repulsion (LinLog) is the empirical gold standard for rendering
communities as compact, separated visual clusters, and Venturini et al. found FA2
with LinLog and zero gravity made clustering clearly more discernible than both
default FA2 and Fruchterman-Reingold on the same network.

### Gravity: less than you think

Gravity is NOT a quality knob. Its only job is to keep disconnected components from
drifting off-screen. Excessive gravity packs all nodes toward the center and
destroys the attraction-repulsion balance that makes structure visible — the single
most common cause of unreadable, over-compacted layouts.

- Connected graph: **gravity 0** (or 0.5 if the frame drifts).
- Disconnected components: the smallest gravity that keeps them in frame
  (start at 0.5; go to 1.0 only if pieces still escape).
- Never raise gravity to "tighten" a layout — lower `scalingRatio` instead.
- `strongGravityMode` is almost never right for analysis layouts.

### Key Parameters
| Parameter | Recommended start | Effect |
|-----------|-------------------|--------|
| `linLogMode` | **true** for community readability | Logarithmic repulsion; clusters become compact and separated |
| `gravity` | **0** (0.5–1.0 only for disconnected graphs) | Pulls everything centerward; excess packs the graph into a blob |
| `scalingRatio` | by node count: <1k start 1-2; 1k-10k start 2-4; >10k start 4-8 (raise to spread, lower to tighten) | Overall expansion; the correct knob for micro/macro balance. Start low and expand only if cramped — starting high over-spreads into specks |
| `barnesHutOptimization` | true above ~5k nodes | Faster with slight approximation |
| `edgeWeightInfluence` | 1.0 (0 to ignore weights) | How strongly weights pull |
| `jitterTolerance` | 1.0 | Higher = faster, less precise |
| `preventOverlap` | true only for the final polishing pass | Readability; distorts distances slightly |

### Micro/macro balance

LinLog emphasizes macrostructure (separation between clusters) at some cost to
microstructure (readable detail inside each cluster). Balance them deliberately:

- Cluster blobs too tight to read internally → raise `scalingRatio`, or run a short
  finishing pass with `linLogMode: false` to relax local spacing.
- Clusters readable but global shape mushy → LinLog on, check gravity is 0.
- Judge at two zoom levels: does the overview show distinct regions, and does a
  zoomed region show distinguishable nodes? A layout that only works at one zoom
  level is half-finished.

### The inspect-and-adjust loop (do this, always)

Never trust settings blind; look at the result and iterate. After each layout run:

1. Export a modest PNG (e.g. 1200px) and actually look at it.
2. Diagnose with this table:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Dense ball in the center, empty margins | Gravity too strong | Set gravity to 0, rerun |
| Tight little clusters lost in vast whitespace | scalingRatio too high for the graph size (LinLog amplifies this) | Lower scalingRatio (halve it), rerun; `gephi_visual_qa` flags this as "over-spread" |
| Uniform circle/disc, no lumps or hollows | Structure not yet expressed | LinLog on, more iterations; if it persists, the graph may genuinely lack clustering |
| "Hairball" tangle | Settings, not necessarily the data | LinLog on, gravity 0, raise scalingRatio; consider filtering weak edges first |
| Clusters overlap and smear together | Repulsion too weak | Raise scalingRatio; check LinLog is on |
| Distinct clusters but unreadable inside | Macro over micro | Raise scalingRatio or short non-LinLog finishing pass |
| Components flying off-frame | No gravity on a disconnected graph | Small gravity (0.5) |
| Nodes on top of each other in final render | Overlap not resolved | Final short pass with preventOverlap: true |

3. Change ONE parameter, rerun (a few hundred iterations suffice for adjustment), and
   look again. Two or three loops usually converge. Report what you saw and changed.

Composition tip: once structure is right, a short final pass (200-300 iterations) with
slightly higher gravity (1-2) rounds a straggly composition into the frame without
destroying cluster separation — apply gently and re-inspect.

Shape-reading notes: a non-circular overall silhouette usually indicates polarization
(a meaningful axis); density differences indicate clustering; do not over-read exact
distances between individual node pairs — force layouts convey topology as regions and
gradients, not calibrated distances.

### Iteration Guidelines
- Small graph (<500 nodes): 200-500 iterations
- Medium graph (500-5k): 500-1000 iterations
- Large graph (5k-50k): 1000-3000 iterations (barnesHutOptimization: true)
- Check layout status and stop early if converged

### Recommended Settings by Graph Type
**Community-focused (the usual case):**
```json
{"linLogMode": true, "gravity": 0, "scalingRatio": 2.0}
```

**Large graph (>5k nodes):**
```json
{"linLogMode": true, "gravity": 0, "scalingRatio": 10.0, "barnesHutOptimization": true}
```

**Disconnected graph:**
```json
{"linLogMode": true, "gravity": 0.5, "scalingRatio": 2.0}
```

**Final polish (after structure is right):**
```json
{"preventOverlap": true, "scalingRatio": 2.0}
```
(short pass, ~100-200 iterations)

## Yifan Hu

Fast multilevel force-directed algorithm. Good for initial positioning of large
graphs, often followed by ForceAtlas2 refinement.

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

Classic force-directed algorithm with even node spacing. Note: on clustered
networks it shows community structure noticeably worse than ForceAtlas2 — prefer
FA2 unless you specifically want uniform spacing on a small graph.

### When to Use
- Small graphs (<1000 nodes)
- When you want even spacing over cluster separation

### Key Parameters
| Parameter | Default | Effect |
|-----------|---------|--------|
| `area` | 10000 | Layout area size |
| `gravity` | 10.0 | Attraction to center |
| `speed` | 1.0 | Convergence speed |

### Recommended Iterations
- 500-1000 iterations

## Circular

Arranges nodes in a circle. Useful for ordered/sequential data, attribute
comparisons, or as a starting arrangement before a force-directed pass.

## Random

Assigns random positions. Use as a reset when a layout gets stuck in a bad
configuration.

## Common Workflow Patterns

### Standard exploration (community structure)
```
gephi_run_layout({algorithm: "forceatlas2", iterations: 800, properties: {linLogMode: true, gravity: 0, scalingRatio: 2.0}})
# Export a small PNG, inspect, diagnose with the table above, adjust ONE parameter, rerun ~300 iterations
```

### Publication quality
```
gephi_run_layout({algorithm: "forceatlas2", iterations: 1000, properties: {linLogMode: true, gravity: 0, scalingRatio: 2.0}})
# Inspect and adjust until macro and micro both read well, then:
gephi_run_layout({algorithm: "forceatlas2", iterations: 150, properties: {preventOverlap: true}})
```

### Large graph
```
gephi_run_layout({algorithm: "yifanhu", iterations: 300})
gephi_run_layout({algorithm: "forceatlas2", iterations: 1500, properties: {linLogMode: true, gravity: 0, scalingRatio: 10.0, barnesHutOptimization: true}})
```

## Real-world harvest networks (single-window mention/interaction data)

Networks harvested from a short collection window (a day of tweets, one export
of interactions) have a characteristic shape the demo networks never show:

- **Expect heavy fragmentation** (hundreds of tiny components) and a
  leaf-majority degree distribution (most nodes have exactly one tie). The
  profile flags both. Neither is a data error — they describe the harvest.
- **Map the skeleton, keep the whole.** For a readable map, filter to
  degree >= 2 (then giant component); keep the full graph for statistics and
  say what was set aside — the excluded share is itself a finding.
- **Fit the extent mechanically when over-spread persists:** run Contraction
  (~20% shrink per pass) repeatedly until gephi_visual_qa stops warning, then
  Noverlap. Raising node sizes also closes the ratio from the other side.
- **Directed hub maps: kill the arrowheads before export** (preview setting
  `arrow.size` 0) — at hub scale they render as giant wedges that bury the map.
- **Captions vs legend:** in-place captions (and centroid captions) assume
  communities occupy separate regions. When communities interpenetrate — one
  dense core, colors mixed through it — use a legend instead; colliding
  captions are the map telling you the groups share space.
- **External matplotlib re-render note:** GEXF colors parse as strings like
  `rgb(27,175,122)` — handle that format, not only hex.

## Tree-like networks: when force layouts cannot separate communities

Reply, retweet, mention, and seeded-citation networks are tree-like (barely
more ties than nodes — the profile flags it). Their communities are stars
fanning out from hub accounts, and interleaved star-arms have no ties pulling
them together, so **ForceAtlas 2 leaves real communities fully mixed no matter
how many iterations you run**. This is structural, not a tuning problem;
measured on a real reply network, 4,000 LinLog iterations moved the
separation score only from 0.88 to 0.84.

The fix is `gephi_community_layout`: detect communities first (modularity),
then draw each as its own radial disc — hub at center, members ringed by
reply-distance, discs packed side by side. Same network: separation 0.10.

- **Judge separation by number, not by eye.** The tool reports
  separation_before/after (mean intra-community pair distance over mean random
  pair distance; 1.0 = fully mixed). Quote it when explaining the layout
  switch. Below ~0.5 captions work; above it, use a legend.
- **The reading rules change and you must say so.** Grouping and within-disc
  distances come from the data; disc placement relative to other discs is
  arranged for legibility and means nothing. Put that in the caption.
- **Labels are a budget.** Thousands of labels is zero labels. Label only the
  hubs (gephi_label_clusters, or per-community top accounts plus the global
  top), and for exports thin further with collision-avoidance. Community
  names go on as the top typographic layer once they are earned.
