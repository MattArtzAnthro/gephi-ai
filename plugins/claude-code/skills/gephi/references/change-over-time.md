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
