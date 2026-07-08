---
description: Build a word co-occurrence network from free text (transcripts, notes, survey answers) and lay it out
argument-hint: "[path to a text file, or paste the text]"
allowed-tools: Task, Read
---

# Build a text network

Dispatch the **text-network-builder** agent to turn the text in `$ARGUMENTS` into a
word co-occurrence network in Gephi — recurring concepts as nodes, co-occurrence as
edges, themes as communities.

- If `$ARGUMENTS` is a file path (or several), pass it to the agent; if it is a folder
  or a naturally segmented corpus, tell the agent so it builds from a **list** (one
  transcript turn / note / answer per item) rather than one blob — the co-occurrence
  window should reset per segment.
- If `$ARGUMENTS` is empty, ask the user for the text or a path, then dispatch.

The agent builds, inspects the vocabulary, rebuilds with better stopwords/POS/frequency
settings if the hubs are noise, then colors, sizes, and lays out the graph. It runs in
its own context so the tuning iterations stay out of this conversation. When it returns,
show the export/caption and relay its notes on what the construction choices did (a
co-occurrence edge is proximity in text, not a claim of meaning). Reading the map is a
separate step — offer `/analyze-network` or the network-analyst agent for that.
