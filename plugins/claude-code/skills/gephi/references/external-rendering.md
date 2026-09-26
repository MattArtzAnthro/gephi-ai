# Rendering outside Gephi

Most maps need none of this. `gephi_export_png` fills the background from `background.color`
in the preview settings, `gephi_visual_qa` gives `suggested_export` dimensions that leave out
runaway nodes, and `gephi_label_clusters` captions groups inside Gephi. Use these recipes when
an export has already been made and needs a different background or frame, or when a figure
needs labels or placement Gephi cannot give. They need Python with Pillow, NumPy, and, for
re-rendering, matplotlib. Ask before installing any of them.

Whatever the route, the figure still ships with its caption and legend (see
reading-network-maps.md).

## Colours for a dark surface

Use the dark-surface palette, keyed from the largest group down (hex values of the palette in
SKILL.md):

```python
DARK = ["#3987E5", "#C98500", "#008300", "#D55181", "#9085E9", "#E66767", "#199E70", "#D95926"]
BG = "#1C1C2E"      # dark navy background
OTHER = "#8C8C8C"   # groups past the eighth
```

Past eight groups, colour cannot tell groups apart. Give the rest the neutral colour, label the
groups on the map, and say so in the caption.

## Put an existing white export on a dark background

This recovers each pixel's colour and opacity against white, then lays it over the dark
background.

```python
from PIL import Image
import numpy as np

img = Image.open("export.png").convert("RGB")
arr = np.array(img, dtype=np.float32)
bg = np.array([28, 28, 46], dtype=np.float32)   # BG as RGB

alpha = np.clip(np.max(255.0 - arr, axis=2) / 255.0 * 1.8, 0, 1)
a_safe = np.maximum(alpha, 0.02)[:, :, np.newaxis]
recovered = np.clip((arr - 255.0 * (1 - alpha[:, :, np.newaxis])) / a_safe, 0, 255)
result = np.clip(bg + alpha[:, :, np.newaxis] * (recovered - bg), 0, 255).astype(np.uint8)
Image.fromarray(result).save("export-dark.png")
```

- Export with `edge.opacity` of at least 60. Fainter edges are too close to white for their
  colour to be recovered.
- Use the validated colours, not pastels, which are close to white and turn grey.
- Use it for unlabelled exports only. White label outlines become navy and the labels
  disappear; for a labelled map, stay on white.

## Crop around the centre of the drawing

Crop around the centroid (the average position of everything drawn), not around the
bounding box of every non-white pixel: on a sparse graph a few outlying nodes push that box to
the full canvas.

```python
alpha = np.clip(np.max(255.0 - arr, axis=2) / 255.0 * 1.8, 0, 1)
ys, xs = np.where(alpha > 0.12)
cy, cx = int(ys.mean()), int(xs.mean())
H, W = alpha.shape
half_w, half_h = 900, 700   # widen for a spread-out graph
box = (max(0, cx - half_w), max(0, cy - half_h), min(W, cx + half_w), min(H, cy + half_h))
img.crop(box).resize((3840, 2160), Image.LANCZOS).save("export-zoom.png")
```

On a dark composite, composite first, then crop the result.

## Label groups on an exported image

Gephi has no group labels of its own beyond `gephi_label_clusters`. To overlay one label per
group on a PNG:

1. Read positions and the group column. `gephi_query_nodes` returns each node's `x`, `y`, and
   every column, a page at a time (`limit` and `offset`); for more than a few hundred nodes,
   read `gephi_export_gexf` instead (below).
2. For each group, take the centroid of its members: the mean of their x and the mean of
   their y.
3. Map graph coordinates to pixels with the bounding box of all positions. The y axis is
   inverted:

   ```python
   px = (cx - x_min) / (x_max - x_min) * W
   py = H - (cy - y_min) / (y_max - y_min) * H
   ```

4. Draw each label with Pillow, first in white at 2-pixel offsets to make an outline, then in
   the group's colour.
5. Leave out any group whose centroid falls far outside the drawing. A single-node group can
   sit at an extreme position (x of -233494, for example); check every centroid before
   cropping.
6. Crop to the in-frame centroids plus a margin of about 320 pixels on each side, then resize.

In hub-and-spoke networks, group centroids land inside the central mass and labels collide.
Use radial labels (below).

## Re-render from GEXF

For full control over colour and labels, export the positioned graph with
`gephi_export_gexf` and draw it again in matplotlib. The GEXF carries each node's position,
size, and colour plus every attribute (`modularity_class`, `pageranks`). The node CSV from
`gephi_export_csv` has no positions, so do not use it for this. This route also avoids
compositing, because matplotlib draws the background directly.

Match tags by their local name: `position`, `size`, and `color` sit in the viz namespace,
not the default one.

```python
import xml.etree.ElementTree as ET
from collections import Counter
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe

local = lambda t: t.split("}")[-1]
root = ET.parse("graph-positions.gexf").getroot()
pos, comm, pr = {}, {}, {}
for n in root.iter():
    if local(n.tag) != "node":
        continue
    nid = n.get("id")
    for c in n:
        if local(c.tag) == "position":
            pos[nid] = (float(c.get("x")), float(c.get("y")))
        elif local(c.tag) == "attvalues":
            for av in c:
                if av.get("for") == "modularity_class":
                    comm[nid] = int(float(av.get("value")))
                elif av.get("for") == "pageranks":
                    pr[nid] = float(av.get("value"))
edges = [(e.get("source"), e.get("target")) for e in root.iter()
         if local(e.tag) == "edge" and e.get("source") in pos and e.get("target") in pos]

# Largest group gets the first colour.
by_size = [k for k, _ in Counter(comm.values()).most_common()]
PAL = {k: (DARK[i] if i < len(DARK) else OTHER) for i, k in enumerate(by_size)}
colour = lambda nid: PAL.get(comm.get(nid), OTHER)

nodes = list(pos)
fig, ax = plt.subplots(figsize=(17, 17), dpi=240)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.add_collection(LineCollection([[pos[s], pos[t]] for s, t in edges],
                  colors=[colour(s) for s, _ in edges], linewidths=0.35, alpha=0.10))
pv = np.array([pr.get(n, 0) for n in nodes])
ax.scatter([pos[n][0] for n in nodes], [pos[n][1] for n in nodes],
           s=18 + (pv / pv.max()) * 2600, c=[colour(n) for n in nodes],
           edgecolors="none", alpha=0.95, zorder=3)
```

This colours each edge by its source node's group and sizes nodes by PageRank; say both in the
caption. matplotlib draws several thousand edges without trouble.

## Radial labels with leader lines

Instead of placing labels at the centroids, place them on a ring around the graph, evenly
spaced in the order of each centroid's angle, with a leader line back to a marker at the true
centroid. Labels cannot overlap, and each location stays exact.

```python
xs = np.array([pos[n][0] for n in nodes]); ys = np.array([pos[n][1] for n in nodes])
cx, cy = np.median(xs), np.median(ys)
R = np.percentile(np.hypot(xs - cx, ys - cy), 98)    # cloud radius, ignoring outliers
groups = [k for k in by_size if k in NAMES]
anchor = {k: (np.median([pos[n][0] for n in nodes if comm.get(n) == k]),
              np.median([pos[n][1] for n in nodes if comm.get(n) == k])) for k in groups}
order = sorted(groups, key=lambda k: np.arctan2(anchor[k][1] - cy, anchor[k][0] - cx))
base = np.arctan2(anchor[order[0]][1] - cy, anchor[order[0]][0] - cx)
for i, k in enumerate(order):
    ang = base + 2 * np.pi * i / len(order)             # even spacing: no overlaps
    lx, ly = cx + R * 1.32 * np.cos(ang), cy + R * 1.32 * np.sin(ang)
    ax.plot([anchor[k][0], lx], [anchor[k][1], ly], color=PAL[k], lw=1.2, alpha=0.55, zorder=4)
    ax.scatter([anchor[k][0]], [anchor[k][1]], s=140, facecolor=PAL[k],
               edgecolor="white", lw=1.5, zorder=6)
    t = ax.text(lx, ly, NAMES[k], color="white", ha="left" if lx >= cx else "right",
                va="center", fontsize=16, fontweight="bold", zorder=7)
    t.set_path_effects([pe.withStroke(linewidth=4.5, foreground=PAL[k]),
                        pe.withStroke(linewidth=9, foreground=BG)])
ax.set_aspect("equal"); ax.axis("off")
plt.savefig("graph-labeled.png", facecolor=BG, bbox_inches="tight", pad_inches=0.25)
```

`NAMES` maps each group value to its earned name, for example `{3: "Local food networks"}`.
Name a group only after the reading process in reading-network-maps.md has earned the name
and `gephi_community_stability` has shown the group holds. To see who is in it, read its
members with `gephi_query_nodes` (`column` set to the group column, `value` set to the group)
and look at the ones with the highest PageRank.
