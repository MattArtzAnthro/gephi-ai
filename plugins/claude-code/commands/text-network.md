---
description: Build a word co-occurrence network from free text (transcripts, notes, survey answers) and lay it out
argument-hint: "[path to a text file, or paste the text]"
allowed-tools: Agent, Task, Skill(gephi-network-analysis:gephi), Read
---

# Build a text network

Turn the text in `$ARGUMENTS` into a word co-occurrence network in Gephi: recurring
concepts as nodes, co-occurrence as edges, themes as communities.

## Rules this command must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Get the text.** If `$ARGUMENTS` is empty, ask the user for the text or a path.
   There is no default text: without one, stop and say what is needed.

3. **Dispatch the text-network-builder agent** with the text or path.
   - If `$ARGUMENTS` is a file path (or several), pass it on; if it is a folder or a
     naturally segmented corpus, tell the agent so it builds from a **list** (one
     transcript turn, note, or answer per item) rather than one blob, because the
     co-occurrence window should reset per segment.
   - The agent reads `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/text-network-analysis.md`,
     builds in a new workspace, inspects the vocabulary, rebuilds with better
     stopword, part-of-speech, or frequency settings if the hubs are noise, checks
     community stability, then colors, sizes, and lays out the graph. It runs in
     its own context so the tuning iterations stay out of this conversation.

4. **Relay the result.** Show the export paths, the caption, and the legend, and
   relay the agent's notes on what the construction choices did (a co-occurrence
   edge is proximity in text, not a claim of meaning) and any "Choices I made".
   Reading the map is a separate step: offer `/analyze-network` or the
   network-analyst agent for that.
