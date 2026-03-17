# Gephi MCP Plugin Bug Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all bugs in GephiControlService.java that cause edge rendering failures, preview corruption, and lock conflicts — making the plugin reliable for end users.

**Architecture:** All fixes are in a single file (`GephiControlService.java`). The bugs are: (1) EdgeColor preview property corrupts SVG edge rendering, (2) font string parsing fails on multi-word names, (3) hex color parsing has no error handling, (4) filter operations don't refresh preview and use wrong threading, (5) GEXF import doesn't cap viz:size. Each fix is independent.

**Tech Stack:** Java 11, Gephi 0.10.1 APIs, Swing EDT threading

---

## Chunk 1: Preview Settings Fixes

### Task 1: Add try-catch around ALL hex color parsing

**Files:**
- Modify: `gephi-mcp-plugin/src/main/java/org/gephi/plugins/mcp/service/GephiControlService.java:1492-1562`

The `setPreviewSettings` method parses hex color strings like `"#FF0000"` in four places (Color, DependantColor, DependantOriginalColor, EdgeColor) using `Integer.parseInt(hex, 16)` with no error handling. Malformed hex crashes the entire method.

- [ ] **Step 1: Wrap Color hex parsing (line 1495)**

Replace:
```java
prop.setValue(new Color(Integer.parseInt(hex, 16)));
```
With:
```java
try {
    prop.setValue(new Color(Integer.parseInt(hex, 16)));
} catch (NumberFormatException nfe) {
    LOGGER.warning("Invalid hex color: #" + hex);
    continue;
}
```

- [ ] **Step 2: Wrap DependantColor hex parsing (line 1528)**

Replace:
```java
Color c = new Color(Integer.parseInt(s.substring(1), 16));
prop.setValue(new DependantColor(c));
```
With:
```java
try {
    Color c = new Color(Integer.parseInt(s.substring(1), 16));
    prop.setValue(new DependantColor(c));
} catch (NumberFormatException nfe) {
    LOGGER.warning("Invalid hex color: " + s);
    continue;
}
```

- [ ] **Step 3: Wrap DependantOriginalColor hex parsing (line 1541)**

Same pattern — wrap the `Integer.parseInt` + `new Color` + `prop.setValue` in try-catch.

- [ ] **Step 4: Wrap EdgeColor hex parsing (line 1558)**

Same pattern.

---

### Task 2: Fix font string parsing for multi-word font names

**Files:**
- Modify: `GephiControlService.java:1502-1516`

Current parser splits on whitespace, so "Arial 12 Bold" works but "Courier New 12 Bold" breaks (name becomes "Courier", "New" is ignored). Fix: treat everything before the first number as the font name.

- [ ] **Step 1: Replace font parsing block**

Replace lines 1502-1516 with:
```java
} else if (type == java.awt.Font.class && val instanceof String) {
    try {
        String fontStr = val.toString().trim();
        // Parse: everything before first digit is name, first number is size, rest is style
        String name = "Arial";
        int size = 12;
        int style = java.awt.Font.PLAIN;

        // Find where the numeric part starts
        int numStart = -1;
        for (int ci = 0; ci < fontStr.length(); ci++) {
            if (Character.isDigit(fontStr.charAt(ci))) {
                numStart = ci;
                break;
            }
        }

        if (numStart > 0) {
            name = fontStr.substring(0, numStart).trim();
            String rest = fontStr.substring(numStart).trim();
            String[] parts = rest.split("\\s+");
            if (parts.length > 0) {
                try { size = Integer.parseInt(parts[0]); } catch (NumberFormatException ignored) {}
            }
            for (int pi = 1; pi < parts.length; pi++) {
                if ("Bold".equalsIgnoreCase(parts[pi])) style |= java.awt.Font.BOLD;
                else if ("Italic".equalsIgnoreCase(parts[pi])) style |= java.awt.Font.ITALIC;
            }
        } else if (numStart == 0) {
            // Starts with number — just size, use default name
            String[] parts = fontStr.split("\\s+");
            try { size = Integer.parseInt(parts[0]); } catch (NumberFormatException ignored) {}
        } else {
            // No numbers — just a font name
            name = fontStr;
        }

        prop.setValue(new java.awt.Font(name, style, size));
    } catch (Exception e) {
        LOGGER.warning("Failed to parse font: " + val + " - " + e.getMessage());
        continue; // Skip to avoid corruption
    }
```

---

### Task 3: Fix EdgeColor "source"/"target" modes — implement per-edge coloring workaround

**Files:**
- Modify: `GephiControlService.java:1546-1562`
- Add new method: `colorEdgesBySource()` / `colorEdgesByTarget()`

Setting `EdgeColor.Mode.SOURCE` via preview properties corrupts Gephi's SVG edge renderer, causing ALL edges to vanish from exports. The fix: when user requests "source" or "target" edge coloring, don't set the preview property. Instead, iterate all edges and set each edge's color to match its source/target node's color. This produces the same visual result without corrupting the preview.

- [ ] **Step 1: Add helper method `colorEdgesByNodeColor`**

Add after `setEdgeThicknessByWeight()` (around line 2000):
```java
public JsonObject colorEdgesByNodeColor(boolean useSource) {
    return runOnEDT(() -> {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        try {
            Graph graph = currentGraphModel().getGraph();
            Node[] nodes = graph.getNodes().toArray();
            Edge[] edges = graph.getEdges().toArray();

            // Build node color lookup
            java.util.Map<Node, Color> nodeColors = new java.util.HashMap<>();
            for (Node n : nodes) {
                nodeColors.put(n, n.getColor());
            }

            // Set each edge's color from its source or target node
            int colored = 0;
            for (Edge e : edges) {
                Node ref = useSource ? e.getSource() : e.getTarget();
                Color c = nodeColors.get(ref);
                if (c != null) {
                    e.setColor(c);
                    colored++;
                }
            }

            JsonObject r = success("Colored " + colored + " edges by " + (useSource ? "source" : "target") + " node");
            r.addProperty("colored", colored);
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    });
}
```

- [ ] **Step 2: Modify EdgeColor handling in setPreviewSettings**

Replace lines 1546-1562 with:
```java
} else if (type == EdgeColor.class && val instanceof String) {
    String s = val.toString().trim().toLowerCase();
    if ("source".equals(s) || "target".equals(s)) {
        // Don't set EdgeColor preview property — it corrupts SVG edge rendering.
        // Instead, color each edge individually to match its source/target node.
        boolean useSource = "source".equals(s);
        Graph graph = currentGraphModel().getGraph();
        Node[] nodes = graph.getNodes().toArray();
        Edge[] edges = graph.getEdges().toArray();
        java.util.Map<Node, Color> nodeColors = new java.util.HashMap<>();
        for (Node n : nodes) nodeColors.put(n, n.getColor());
        for (Edge edge : edges) {
            Node ref = useSource ? edge.getSource() : edge.getTarget();
            Color c = nodeColors.get(ref);
            if (c != null) edge.setColor(c);
        }
        // Set to ORIGINAL mode so export uses the per-edge colors we just set
        prop.setValue(new EdgeColor(EdgeColor.Mode.ORIGINAL));
    } else if ("mixed".equals(s)) {
        prop.setValue(new EdgeColor(EdgeColor.Mode.MIXED));
    } else if ("original".equals(s)) {
        prop.setValue(new EdgeColor(EdgeColor.Mode.ORIGINAL));
    } else if (s.startsWith("#")) {
        try {
            Color c = new Color(Integer.parseInt(s.substring(1), 16));
            prop.setValue(new EdgeColor(c));
        } catch (NumberFormatException nfe) {
            LOGGER.warning("Invalid edge color hex: " + s);
            continue;
        }
    } else {
        continue;
    }
}
```

- [ ] **Step 3: Add API endpoint for `colorEdgesByNodeColor`**

In `GephiAPIServer.java`, add route:
```java
case "/appearance/edges/color-by-source":
    return jsonResponse(service.colorEdgesByNodeColor(true));
case "/appearance/edges/color-by-target":
    return jsonResponse(service.colorEdgesByNodeColor(false));
```

---

## Chunk 2: Filter & Threading Fixes

### Task 4: Wrap filter operations in runOnEDT and add preview refresh

**Files:**
- Modify: `GephiControlService.java` — `removeIsolates()`, `filterByDegreeRange()`, `extractGiantComponent()`, `extractEgoNetwork()`

All filter operations currently run on the HTTP server thread with direct graph locks. This causes `IllegalMonitorStateException` when subsequent EDT operations try to access the graph. Fix: wrap in `runOnEDT()` and add preview refresh after graph modification.

- [ ] **Step 1: Fix `removeIsolates()` (lines 1822-1840)**

Replace:
```java
public JsonObject removeIsolates() {
    try {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        Graph g = currentGraphModel().getGraph();
        g.writeLock();
        try {
            java.util.List<Node> isolates = new java.util.ArrayList<>();
            for (Node n : g.getNodes()) {
                if (g.getDegree(n) == 0) isolates.add(n);
            }
            for (Node n : isolates) g.removeNode(n);
            JsonObject r = success("Removed " + isolates.size() + " isolated nodes");
            r.addProperty("removed", isolates.size());
            r.addProperty("remaining_nodes", g.getNodeCount());
            return r;
        } finally { g.writeUnlock(); }
    } catch (Exception e) { return error("Failed: " + e.getMessage()); }
}
```

With:
```java
public JsonObject removeIsolates() {
    return runOnEDT(() -> {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        try {
            Graph g = currentGraphModel().getGraph();
            // Collect isolates using toArray() to avoid holding read lock
            Node[] allNodes = g.getNodes().toArray();
            java.util.List<Node> isolates = new java.util.ArrayList<>();
            for (Node n : allNodes) {
                if (g.getDegree(n) == 0) isolates.add(n);
            }
            for (Node n : isolates) g.removeNode(n);

            // Refresh preview so exports reflect the change
            PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
            if (pc != null) pc.refreshPreview(ws);

            JsonObject r = success("Removed " + isolates.size() + " isolated nodes");
            r.addProperty("removed", isolates.size());
            r.addProperty("remaining_nodes", g.getNodeCount());
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    });
}
```

Key changes: `runOnEDT()` wrapper, `toArray()` instead of iterator (avoids holding read lock), removed explicit write lock (Gephi's `removeNode` handles its own locking internally when called from EDT), added preview refresh.

- [ ] **Step 2: Fix `filterByDegreeRange()` — same pattern**

Wrap in `runOnEDT()`, use `toArray()`, add preview refresh.

- [ ] **Step 3: Fix `extractGiantComponent()` — same pattern**

Wrap in `runOnEDT()`, use `toArray()` for node iteration, add preview refresh.

- [ ] **Step 4: Fix `extractEgoNetwork()` — same pattern**

Wrap in `runOnEDT()`, use `toArray()`, add preview refresh.

- [ ] **Step 5: Fix `colorByPartition()` — wrap in runOnEDT**

Currently uses direct `graph.writeLock()`. Wrap in `runOnEDT()` and use `toArray()`.

- [ ] **Step 6: Fix `colorByRanking()` — same pattern**

- [ ] **Step 7: Fix `sizeByRanking()` — same pattern**

- [ ] **Step 8: Fix `setEdgeColor()` — wrap in runOnEDT**

- [ ] **Step 9: Fix `resetAppearance()` — wrap in runOnEDT**

---

### Task 5: Cap imported viz:size after GEXF import

**Files:**
- Modify: `GephiControlService.java:1766-1799` (`importFile()`)

GEXF files with `viz:size` values of 60-100 create enormous nodes that cover all edges. After import, cap node sizes to a reasonable maximum.

- [ ] **Step 1: Add size capping after import**

After `ic.process(c, processor, ws);` (line 1791), add:
```java
// Cap imported node sizes to prevent viz:size from GEXF making nodes enormous
Graph g = getGraphController().getGraphModel(ws).getGraph();
Node[] importedNodes = g.getNodes().toArray();
float maxAllowedSize = 30.0f;
for (Node n : importedNodes) {
    if (n.size() > maxAllowedSize) {
        n.setSize(maxAllowedSize);
    }
}
```

---

## Chunk 3: Build, Deploy, Test

### Task 6: Build and deploy the fixed plugin

- [ ] **Step 1: Build the plugin**

```bash
cd /Users/mattartz/Documents/GitHub/gephi-ai/gephi-mcp-plugin
mvn clean package -DskipTests
```

- [ ] **Step 2: Install the updated NBM in Gephi**

```bash
# Find the built NBM
ls target/*.nbm

# Install: Open Gephi → Tools → Plugins → Downloaded → Add Plugins → select NBM
# Or copy directly:
cp target/gephi-mcp-plugin-*.nbm ~/Library/Application\ Support/gephi/0.10/update/download/

# Clear Gephi cache
rm -f ~/Library/Caches/gephi/0.10/*.dat

# Restart Gephi
```

- [ ] **Step 3: Test each fix**

Test 1 — Edge coloring doesn't corrupt:
```bash
# Set edge.color to "source" and verify edges still render
curl -X POST http://127.0.0.1:8080/preview/settings -d '{"edge.color":"source"}'
curl -X POST http://127.0.0.1:8080/export/svg -d '{"file":"/tmp/test.svg"}'
grep -c '<path' /tmp/test.svg  # Should be > 0
```

Test 2 — Font setting doesn't corrupt:
```bash
curl -X POST http://127.0.0.1:8080/preview/settings -d '{"node.label.font":"Courier New 10 Bold"}'
curl -X POST http://127.0.0.1:8080/export/png -d '{"file":"/tmp/test.png","width":800,"height":600}'
# Should succeed without "Font cast" error
```

Test 3 — Filters don't break edges:
```bash
curl -X POST http://127.0.0.1:8080/filter/remove-isolates
curl -X POST http://127.0.0.1:8080/export/svg -d '{"file":"/tmp/test.svg"}'
grep -c '<path' /tmp/test.svg  # Should be > 0
```

Test 4 — Import caps viz:size:
```bash
curl -X POST http://127.0.0.1:8080/import/file -d '{"file":"test.gexf"}'
curl 'http://127.0.0.1:8080/graph/nodes?limit=5' | grep '"size"'
# All sizes should be <= 30
```

- [ ] **Step 4: Commit**

```bash
git add gephi-mcp-plugin/src/
git commit -m "fix: resolve edge rendering corruption, font parsing, filter threading, and viz:size bugs"
```

---

### Task 7: Update skill documentation to remove workarounds

After the Java fixes are deployed, the skill no longer needs the workaround warnings.

- [ ] **Step 1: Update SKILL.md "Critical Things To Know"**

Remove:
- "NEVER set edge.color" warning → replace with "edge.color 'source' and 'target' now work correctly"
- "Filters break edge rendering" → replace with "Filters now properly refresh the preview"
- "GEXF viz:size" → replace with "Imported node sizes are automatically capped at 30"
- "Never restyle after layout" → remove if lock fixes resolve this

- [ ] **Step 2: Update visualize command**

Re-add `"edge.color": "source"` to the preview settings (it's now safe).

- [ ] **Step 3: Sync to cache and GitHub**
