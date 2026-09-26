# Layout Algorithm Guide

## Choosing a layout (by purpose)

Lead with what the person wants to see, not with algorithm names. When
explaining a choice, use the plain-language purpose, then name the layout.

Know which interpretation regime the network is in before judging any layout
(Jacomy 2021): SMALL networks (up to a few dozen nodes) are read
diagrammatically: readers follow the individual paths, so judge layouts by
legibility, minimal edge crossings, and even spacing. LARGE networks are read
topologically: nobody follows individual edges, and density patterns ARE the
message, so judge layouts by whether clusters, holes, and bridges show.
Applying small-network standards to a big map (or vice versa) is a category
error: a 30-node org chart does not need LinLog, and a 3,000-node map should
not be criticized for crossing edges.

| What the person wants | Use | Notes |
|---|---|---|
| "Show me the groups/communities" | ForceAtlas 2 in two passes (LinLog off, then on) | The default for almost everything; see the two passes below |
| Groups in a TREE-LIKE network (replies, retweets, seeded citations) | Community layout (`gephi_community_layout`) | Force layouts cannot separate star-shaped communities: run modularity first, then this; see the tree-like section below |
| "Who plays similar roles?" (even if not directly connected) | Similarity layout (`gephi_similarity_layout`) | Embedding-based; proximity = similar structural role, NOT connection; always say so when presenting. Compare against FA2; disagreements mark bridge/boundary actors |
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
immediately runnable here by name (gephi_get_available_layouts shows what is present).
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
the new layout appears in gephi_get_available_layouts.


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
| **OpenOrd** | Massive graphs, hard cluster separation | >50k nodes | Fast | Good (clustered) |
| **Fruchterman-Reingold** | Small networks, even spacing | <5k nodes | Slow | Good |
| **Circular** | Ring layouts, ordered visualization | Any | Instant | Varies |
| **Random** | Reset positions before re-layout | Any | Instant | N/A |

## ForceAtlas2 (Default Choice)

The go-to algorithm. LinLog mode (logarithmic attraction) is the gold standard for
rendering communities as compact, separated clusters: Noack showed it empirically,
and Venturini et al. found FA2 with LinLog made clustering clearly more discernible
than default FA2 and Fruchterman-Reingold on the same network. LinLog also converges
slowly, so it is the second pass, not the first.

### Two passes

This procedure, and the advice below on gravity, Dissuade Hubs, Prevent Overlap and edge
weights, follows Mathieu Jacomy's ForceAtlas 2 tutorials (YouTube, 2025).

1. **Tune with LinLog off.** `{"linLogMode": false, "scalingRatio": 10,
   "strongGravityMode": true, "gravity": 0.01}`, about 1500 iterations. Adjust
   scalingRatio here. For a quick look, stop after this pass.
2. **Final map: LinLog on.** Stop the layout, switch `linLogMode` on, divide
   scalingRatio by about 20, lower gravity (0.001 or below), and run 3000
   iterations or more. Large networks keep improving for a long time (10,000+
   nodes: let it run). The clusters become denser, with more space between them.

Change settings only while the layout is stopped.

### Gravity: small, and usually strong mode

Gravity only keeps islands and filaments in frame. Plain gravity barely does that,
and raising it packs the graph into a ball. Use `strongGravityMode` with a small
value (0.01, going to 0.001 or far below with LinLog). It holds the network in an
emergent circle with islands on its edge. Too much crushes filaments and makes the
network look denser than it is: lower it until the containing circle is no longer
visible. There is no correct value; it depends on size and density. Never raise
gravity to tighten a layout: lower `scalingRatio` instead.

### Key Parameters
| Parameter | Recommended start | Effect |
|-----------|-------------------|--------|
| `linLogMode` | false in pass 1, true in pass 2 | Clearest cluster separation, slow to converge |
| `scalingRatio` | 10 in pass 1; that value ÷ 20 in pass 2 | Ratio of repulsion to attraction: the overall spread. More room allows more contrast between small and big nodes |
| `strongGravityMode` + `gravity` | true + 0.01 (lower in pass 2) | Keeps islands and filaments in frame; excess makes the network look denser |
| `distributedAttraction` | **false** | Dissuade Hubs: acts only on directed networks, pushes nodes that send many links but receive few to the edge, and costs cluster separation. Use only as a deliberate exploration view, say so in the caption, and offer the map without it |
| `barnesHutOptimization` | true above ~1k nodes | Faster; adds a little noise |
| `edgeWeightInfluence` | 1.0 (set 0 to test whether weights matter) | An exponent on the weight. With weights between 0 and 1, raising it weakens ties. Normalize very large ranges and never use negative weights |
| `jitterTolerance` | 1.0 | Lower it (e.g. 0.25) when nodes keep vibrating |
| `adjustSizes` | true only for the final polishing pass | Prevent Overlap: slows the layout on purpose and treats nodes as slightly bigger; check it did not blur the clusters. If it jams, shrink the nodes |

### Micro/macro balance

LinLog emphasizes macrostructure (separation between clusters) at some cost to
microstructure (readable detail inside each cluster). Balance them deliberately:

- Cluster blobs too tight to read internally → raise `scalingRatio`, or finish with a
  short pass with `linLogMode: false`.
- Clusters readable but global shape mushy → run the LinLog pass longer.
- Judge at two zoom levels: does the overview show distinct regions, and does a
  zoomed region show distinguishable nodes? A layout that only works at one zoom
  level is half-finished.

### The inspect-and-adjust loop (do this, always)

Never trust settings blind; look at the result and iterate. After each layout run:

1. Run `gephi_visual_qa` with `partition_column`, export a modest PNG (e.g. 1200px) and
   actually look at it.
2. Diagnose with this table:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Dense ball in the center, empty margins | Gravity too strong | Lower gravity (strong mode, smaller value), rerun |
| A visible round containing circle | Strong gravity too high | Lower gravity until the circle disappears |
| Tight little clusters lost in vast whitespace | scalingRatio too high for the graph size (LinLog amplifies this) | Lower scalingRatio (halve it), rerun; `gephi_visual_qa` flags this as "over-spread" |
| Uniform circle/disc, no lumps or hollows | Not yet separated, or groups too mixed to show | Run the LinLog pass longer. A round blob does not prove there are no groups: the eye only sees groups separated by a gap, and large groups fill it. Check with modularity and `gephi_community_stability` |
| "Hairball" tangle | Settings, not necessarily the data | Run the LinLog pass; consider filtering weak edges first |
| Clusters overlap and smear together | Repulsion too weak, or Dissuade Hubs on | Raise scalingRatio; turn Dissuade Hubs off |
| Distinct clusters but unreadable inside | Macro over micro | Raise scalingRatio or a short non-LinLog finishing pass |
| Components flying off-frame | No gravity on a disconnected graph | `strongGravityMode` with a small gravity |
| Nodes on top of each other in final render | Overlap not resolved | Final short pass with `adjustSizes: true` |

3. Change ONE parameter, rerun (a few hundred iterations suffice for adjustment), and
   look again. Two or three loops usually converge. Report what you saw and changed.

Once the person has started reading the map, stop rerunning it: a rerun keeps the
clusters but moves and rotates them, and they lose what they learned. Decide the
orientation for the output (horizontal or vertical; a diagonal spread never fits)
before that point.

Shape-reading notes: a non-circular overall silhouette usually indicates polarization
(a meaningful axis); density differences indicate clustering; do not over-read exact
distances between individual node pairs: force layouts convey topology as regions and
gradients, not calibrated distances. The empty space around a hub is produced by the
layout (repulsion grows with a node's number of links), not a finding. Where a
disconnected island sits means nothing; it can be moved by hand.

### Iteration Guidelines
- Pass 1: about 1500 iterations at any size (barnesHutOptimization above ~1k nodes)
- Pass 2: 3000+ iterations; for 10k+ nodes, much longer
- Check layout status and stop early if converged

### Recommended Settings

**Pass 1 (tuning, or a quick map):**
```json
{"linLogMode": false, "scalingRatio": 10, "strongGravityMode": true, "gravity": 0.01}
```

**Pass 2 (final map):**
```json
{"linLogMode": true, "scalingRatio": 0.5, "strongGravityMode": true, "gravity": 0.001}
```

**Final polish (after structure is right):**
```json
{"linLogMode": true, "scalingRatio": 0.5, "strongGravityMode": true, "gravity": 0.001, "adjustSizes": true}
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
| `stepRatio` | 0.95 | Cooling rate. Higher cools slower: cleaner final layout, longer runtime |
| `optimalDistance` | 100 | Target distance between nodes. Raise to separate clusters in dense graphs |
| `theta` | 1.2 | Barnes-Hut approximation (higher = faster, less precise) |
| `relativeStrength` | 0.2 | Repulsion/attraction balance. Guards against clusters collapsing or over-expanding |
| `initialStepSize` | 20 | Max displacement per iteration. ~10% of `optimalDistance` is the rule of thumb; high values untangle dense graphs fast |
| `convergenceThreshold` | 1.0E-4 | Energy floor at which the layout stops. Smaller = more accurate |
| `adaptiveCooling` | false | Helps escape local energy minima on stubborn graphs |

Pass these keys in camelCase: the plugin matches them against the middle
segment of Gephi's property names (`optimalDistance` for
`YifanHu.optimalDistance.name`). A bare call runs on the defaults above; pass
only what you want to change.

### Recommended Iterations
- 100-500 iterations (converges fast)

## OpenOrd

Built for very large graphs (up to ~1M nodes). Unlike the force layouts, it runs
a fixed simulated-annealing schedule and terminates on its own. Use it as the
first pass on a huge graph, then refine with a short ForceAtlas 2 run.

### Property names are the trap here

OpenOrd exposes **no dotted canonical names**, so the display name is the only
key that resolves, spaces, capitals, and `(%)` included. Unlike Yifan Hu
(where `optimalDistance` matches `YifanHu.optimalDistance.name`) and
ForceAtlas 2 (camelCase), a camelCased `edgeCut` here matches nothing and is
not applied: the reply lists it under `unapplied_params` with a warning, and
the layout runs on its defaults. Use exactly these strings, or call
`gephi_get_layout_properties("OpenOrd")` first.

| Property (exact key) | Default | Effect |
|---|---|---|
| `"Edge Cut"` | 0.8 | 0 = no cutting; 1 = maximum. Higher = more clustered, more separated result. The main knob |
| `"Num Iterations"` | 750 | Raise only for very large graphs. More iterations = less dense result |
| `"Num Threads"` | cores − 1 | |
| `"Layout Size"` | 20000 | Total coordinate span; furthest node lands at ± half this |
| `"Random seed"` | 0 | Output depends on seed, iterations, AND thread count. Not reproducible run to run even with a fixed seed, so do not promise reproducibility |

### Defaults

A bare call runs on the same defaults the Gephi window applies, so pass only
what you want to change. `gephi_get_layout_properties` reports each property's
default in `value`, and its `description` states it in prose.

### The five-stage schedule

Time is split across five annealing stages, tunable as percentages
(`"Liquid (%)"` 25, `"Expansion (%)"` 25, `"Cooldown (%)"` 25,
`"Crunch (%)"` 10, `"Simmer (%)"` 15; they should sum to 100):

1. **Liquid**: high-temperature global structure
2. **Expansion**: push outward, maximize cluster separation
3. **Cooldown**: settle into semi-stable regions
4. **Crunch**: compress around cluster centers, sharpen boundaries
5. **Simmer**: local stabilization, resolve overlaps

Leave the split alone unless you have a specific reason; `Edge Cut` is the knob
that actually changes the picture.

### Recommended starting point

```json
{"Edge Cut": 0.8, "Num Iterations": 750}
```
Then a short ForceAtlas 2 pass (pass 2 settings: LinLog on, small scalingRatio, small strong gravity) for detail.
Lower `Edge Cut` toward 0 if the result fragments more than the data warrants.

## Fruchterman-Reingold

Classic force-directed algorithm with even node spacing. Note: on clustered
networks it shows community structure noticeably worse than ForceAtlas2; prefer
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
gephi_run_layout({algorithm: "ForceAtlas 2", iterations: 1500, sync: true, properties: {linLogMode: false, scalingRatio: 10, strongGravityMode: true, gravity: 0.01}})
# Inspect with gephi_visual_qa and a small PNG, adjust ONE parameter, rerun ~300 iterations
```

### Publication quality
Follow the five-pass recipe below.

### Large graph
```
gephi_run_layout({algorithm: "yifanhu", iterations: 300, sync: true, properties: {optimalDistance: 100, initialStepSize: 20, stepRatio: 0.95, relativeStrength: 0.2}})
gephi_run_layout({algorithm: "ForceAtlas 2", iterations: 1500, sync: true, properties: {linLogMode: false, scalingRatio: 10, strongGravityMode: true, gravity: 0.01, barnesHutOptimization: true}})
gephi_run_layout({algorithm: "ForceAtlas 2", iterations: 5000, sync: true, properties: {linLogMode: true, scalingRatio: 0.5, strongGravityMode: true, gravity: 0.001, barnesHutOptimization: true}})
```
`sync: true` on every pass makes each one wait for the last to finish, so no
pass starts on a graph that is still moving.

## Five-pass recipe for a finished map

A map that looks bad almost always has one of three causes: layout settings
left at their defaults (the most common), overlapping nodes, or edge and label
settings that bury the groups. These five passes address all three. Run every
pass with `sync: true`, and check with `gephi_visual_qa` (with
`partition_column`) between passes.

1. **Tune with LinLog off**, about 1500 iterations: the pass 1 settings above,
   with `distributedAttraction: false` and `barnesHutOptimization` true only
   above about 1,000 nodes. For a quick look, stop here.
2. **Separate the clusters with LinLog on**, 3000 iterations or more: the pass
   2 settings above. Switch LinLog on only after pass 1 has stopped. If nodes
   keep jittering, lower `jitterTolerance`.
3. **Prevent overlap**: rerun pass 2's settings with `"adjustSizes": true` for
   about 200 iterations. Check that `partition.separation` in
   `gephi_visual_qa` did not get worse; if the layout jams, shrink the nodes or
   skip this pass.
4. **Fine separation with Noverlap**:
   ```
   gephi_run_layout({algorithm: "Noverlap", iterations: 300, sync: true, properties: {margin: 3.0}})
   ```
5. **Label positions, only when labels show**:
   ```
   gephi_run_layout({algorithm: "Label Adjust", iterations: 300, sync: true})
   ```
   Run it last, after sizes and labels are final.

Then set the preview for a light background. The edge default keeps edges in a
light neutral close to the background, so the groups stay primary:

```
gephi_set_preview_settings(settings={"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false,
    "node.opacity": 100, "node.border.width": 0.5, "node.label.show": false, "node.label.avoidOverlap": true, "arrow.size": 0})
```

- Set contrast with the edge tone first and lower opacity only a little: low
  opacity piles up into uneven texture where edges bundle.
- Label settings change labels only; they never reset edge values.
- `"edge.color": "source"` (edges tinted by their source community) suits a map
  where it matters where ties come from; say so in the caption.
- `node.label.avoidOverlap` keeps labels from colliding without a Label Adjust
  pass.

## Real-world harvest networks (single-window mention/interaction data)

Networks harvested from a short collection window (a day of tweets, one export
of interactions) have a characteristic shape the demo networks never show:

- **Expect heavy fragmentation** (hundreds of tiny components) and a
  leaf-majority degree distribution (most nodes have exactly one tie). The
  profile flags both. Neither is a data error: they describe the harvest.
- **Map the skeleton, keep the whole.** For a readable map, filter to
  degree >= 2 (then giant component) with `gephi_apply_filter`, which hides
  rather than deletes; keep the full graph for statistics and
  say what was set aside, because the excluded share is itself a finding.
- **Fit the extent mechanically when over-spread persists:** run Contraction
  (~20% shrink per pass) repeatedly until gephi_visual_qa stops warning, then
  Noverlap. Raising node sizes also closes the ratio from the other side.
- **Directed hub maps: kill the arrowheads before export** (preview setting
  `arrow.size` 0): at hub scale they render as giant wedges that bury the map.
- **Captions vs legend:** in-place captions (and centroid captions) assume
  communities occupy separate regions. When communities interpenetrate (one
  dense core, colors mixed through it), use a legend instead; colliding
  captions are the map telling you the groups share space.
- **External matplotlib re-render note:** GEXF colors parse as strings like
  `rgb(27,175,122)`; handle that format, not only hex.

## Tree-like networks: when force layouts cannot separate communities

Reply, retweet, mention, and seeded-citation networks are tree-like (barely
more ties than nodes; the profile flags it). Their communities are stars
fanning out from hub accounts, and interleaved star-arms have no ties pulling
them together, so **ForceAtlas 2 leaves real communities mixed no matter how
many iterations run**. This is structural, not a tuning problem: when thousands
of LinLog iterations barely move `partition.separation` in `gephi_visual_qa`,
more iterations will not help.

The fix is `gephi_community_layout`: detect communities first (modularity),
then draw each as its own radial disc (hub at center, members ringed by
reply distance, discs packed side by side).

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
