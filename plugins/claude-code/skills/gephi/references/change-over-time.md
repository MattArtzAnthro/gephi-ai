# Change over time

Someone asks how a network changed: "did the field fragment after 2010?",
"who joined the core in the second year?", "is the team more connected than it
was?". Answer it by comparing the network in two or more periods, each measured
the same way.

## 1. Does the network have time data?

`gephi_get_timeline` says whether it does (`graph_is_dynamic`) and over what range.

If it does not, but a column holds when each node or edge appeared (a founding
year, a first-contact date, a posting date), give it time data with
`gephi_set_time_from_columns`:

- `start` names the column saying when something appears; `end`, if there is
  one, when it stops. Without an end, a node counts as present from its start
  onwards. Without a start, from the beginning.
- Columns holding numbers (years) are used as they are. Dates held as text need
  `date_format`, a Java date pattern such as `"yyyy-MM-dd"` or `"dd/MM/yyyy"`.
  Read a few values with `gephi_column_value_frequencies` first and match the
  pattern to them.
- Run it for edges too (`target="edge"`) when ties have their own dates;
  otherwise an edge is present whenever both of its nodes are.

### Separate node and edge files, one edge row per pair per period

A common shape: a node file, and an edge file with one row for each pair in
each period (the same two people appear once for 2020, again for 2021). Do not
import that edge file as a CSV. Gephi merges repeated source-target rows on
import: their weights are summed and only one row's other values survive, so
the years are lost and the network can no longer be sliced by period. Load it
this way instead:

1. `gephi_import_file` on the node file. It opens in its own workspace.
2. `gephi_add_edges` with the edge rows, in batches of a few hundred. Give each
   row `edge_type` set to its period (for example `"2021"`) and
   `attributes: {"year": 2021}`. A pair can hold one edge of each type, so the
   rows for different periods stay separate edges.
3. `gephi_set_time_from_columns(start="year", end="year", target="edge")`, so
   each edge is present in its own year only.
4. Lay out once, on the whole network (section 3).
5. `gephi_time_slice(start, end)` for each period.

To add node attributes from a second file afterwards, import it with
`gephi_import_file(..., mode="append")`: rows whose ids match existing nodes
attach their values to those nodes.

Say what the time means before going further: "a node is present from the
year it joined, and never leaves" is an assumption the reader should see.

## 2. Choose the periods with the person

Periods should answer their question: terms, funding cycles, before and after
an event. Equal lengths make periods comparable; a longer window accumulates
more ties, so a later period drawn twice as wide looks denser for that reason
alone. How the time windows are drawn shapes what a temporal network appears to
show (Holme and Saramäki 2012), so name the windows in the result.

## 3. Lay out once, then slice

Run the layout on the whole network before slicing. Each slice keeps the
network's positions, so every period is drawn on the same map and a node
stays in the same place across periods. Laying out each slice separately
moves everything, and the maps can no longer be compared by eye.

Then `gephi_time_slice(start, end)` for each period. Each opens in its own
workspace, named after the source and the period; the network and Gephi's
timeline stay as they were. A slice holds the nodes present at any moment in
the window, and the edges present then between them. Nodes and edges with no
time data count as always present, so they appear in every slice.

## 4. Measure every period the same way

In each slice run the same statistics with the same settings, then line the
periods up with `gephi_compare_workspaces`. Report what changed as numbers:
nodes, edges, density, components, modularity, and the nodes whose rank moved.

- **Communities.** Community numbers are arbitrary in each run, so community 3
  in one period is not community 3 in the next. Compare communities by their
  members. To follow the same groups through time, run modularity on the whole
  network before slicing: the slices keep its `modularity_class`, so each
  period shows how the overall communities were present then. Say which of the
  two you did.
- **Centrality.** A node's degree in a period counts the ties present in that
  window. Rising degree across equal windows is growth; across widening windows
  it may only be accumulation.
- **Small periods.** A slice with few nodes gives unstable statistics. Say so
  rather than reading a trend into noise.

## Mixing between groups, period by period

"Did the two departments work together more after the merger?" is a question
about mixing: how many ties stay inside a group and how many cross between
groups. In each period's workspace, run `gephi_visual_qa` with
`partition_column` set to the grouping column. Its `partition` block gives:

- `within_fraction`: the share of ties that stay inside a group;
- `random_baseline`: the share that would stay inside by chance, given the
  group sizes;
- `ratio_vs_random`: the first divided by the second.

A within-group share well above the baseline means the groups keep to
themselves; near the baseline, ties ignore the groups. Compare the ratio across
periods rather than the raw share, because the baseline moves when group sizes
change.

For ties between two named groups when there are more, first narrow the view to
those two groups with `gephi_apply_filters`, one filter per group and
`combine="any"`, then run `gephi_visual_qa` on what is shown. Reset the filter
(`gephi_reset_filters`) before the next period. The count is by tie, not by
weight: ten weak ties and ten strong ones count the same. Say so when weights
matter to the question.

## 5. Dynamic statistics, for a series instead of snapshots

Gephi's dynamic statistics (Dynamic Degree, Dynamic # Nodes, # Edges,
Clustering Coefficient) step a window through the timeline and store a value
for each step, which suits "how did X change year by year" better than a few
slices. Run them with `gephi_run_statistic`, passing `params={"window": 1,
"tick": 1}` in the network's time units (here, one year); without them, or
without time data, the run is refused with the network's time range.

## Reporting

State the periods, how time was assigned, whether communities were found on the
whole network or per period, and the numbers for each period. A change between
two slices is a description of these data under these windows; it does not by
itself explain why the network changed.

Holme, Petter, and Jari Saramäki. 2012. "Temporal Networks." *Physics Reports*
519 (3): 97–125.
