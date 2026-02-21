package org.gephi.plugins.mcp.service;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.awt.Color;
import java.io.File;
import java.io.StringWriter;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.swing.SwingUtilities;
import org.gephi.appearance.api.AppearanceController;
import org.gephi.appearance.api.AppearanceModel;
import org.gephi.appearance.api.Function;
import org.gephi.graph.api.Column;
import org.gephi.graph.api.DirectedGraph;
import org.gephi.graph.api.Edge;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphController;
import org.gephi.graph.api.GraphModel;
import org.gephi.graph.api.Node;
import org.gephi.graph.api.Table;
import org.gephi.io.exporter.api.ExportController;
import org.gephi.io.exporter.spi.CharacterExporter;
import org.gephi.io.exporter.spi.Exporter;
import org.gephi.io.exporter.spi.GraphExporter;
import org.gephi.io.importer.api.Container;
import org.gephi.io.importer.api.ImportController;
import org.gephi.io.processor.spi.Processor;
import org.gephi.layout.spi.Layout;
import org.gephi.layout.spi.LayoutBuilder;
import org.gephi.layout.spi.LayoutProperty;
import org.gephi.preview.api.PreviewController;
import org.gephi.preview.api.PreviewModel;
import org.gephi.preview.api.PreviewProperty;
import org.gephi.preview.types.DependantColor;
import org.gephi.preview.types.DependantOriginalColor;
import org.gephi.preview.types.EdgeColor;
import org.gephi.project.api.ProjectController;
import org.gephi.project.api.Workspace;
import org.gephi.statistics.spi.Statistics;
import org.gephi.statistics.spi.StatisticsBuilder;
import org.openide.util.Lookup;

public class GephiControlService {

    private static final Logger LOGGER = Logger.getLogger(GephiControlService.class.getName());
    private static GephiControlService instance;

    private final AtomicBoolean layoutRunning = new AtomicBoolean(false);
    private volatile String currentLayoutName = null;
    private volatile Future<?> layoutFuture = null;
    private final ExecutorService layoutExecutor = Executors.newSingleThreadExecutor();

    private GephiControlService() {}

    public static synchronized GephiControlService getInstance() {
        if (instance == null) instance = new GephiControlService();
        return instance;
    }

    // ─── Helpers ─────────────────────────────────────────────────────

    private ProjectController getProjectController() {
        return Lookup.getDefault().lookup(ProjectController.class);
    }

    private GraphController getGraphController() {
        return Lookup.getDefault().lookup(GraphController.class);
    }

    @SuppressWarnings("unchecked")
    private <T> T runOnEDT(Callable<T> callable) {
        if (SwingUtilities.isEventDispatchThread()) {
            try { return callable.call(); }
            catch (Exception e) { throw new RuntimeException(e); }
        }
        final Object[] result = new Object[1];
        final Exception[] exception = new Exception[1];
        try {
            SwingUtilities.invokeAndWait(() -> {
                try { result[0] = callable.call(); }
                catch (Exception e) { exception[0] = e; }
            });
        } catch (Exception e) { throw new RuntimeException(e); }
        if (exception[0] != null) throw new RuntimeException(exception[0]);
        return (T) result[0];
    }

    private JsonObject success(String msg) {
        JsonObject r = new JsonObject();
        r.addProperty("success", true);
        r.addProperty("message", msg);
        return r;
    }

    private JsonObject error(String msg) {
        JsonObject r = new JsonObject();
        r.addProperty("success", false);
        r.addProperty("error", msg);
        return r;
    }

    private Workspace currentWorkspace() {
        return getProjectController().getCurrentWorkspace();
    }

    private GraphModel currentGraphModel() {
        Workspace ws = currentWorkspace();
        return ws != null ? getGraphController().getGraphModel(ws) : null;
    }

    /** Find an edge between two nodes, checking all edge types (directed type 1 and undirected type 0). */
    private Edge findEdge(Graph g, Node source, Node target) {
        Edge e = g.getEdge(source, target, 1);  // directed
        if (e == null) e = g.getEdge(source, target, 0);  // undirected
        if (e == null) e = g.getEdge(source, target);  // default
        return e;
    }

    // ─── Project Management ──────────────────────────────────────────

    public JsonObject createProject(String name) {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            pc.newProject();
            Workspace ws = pc.getCurrentWorkspace();
            JsonObject r = success("Project created");
            r.addProperty("workspace_id", ws != null ? ws.getId() : -1);
            return r;
        });
    }

    public JsonObject openProject(String filePath) {
        return runOnEDT(() -> {
            File file = new File(filePath);
            if (!file.exists()) return error("File not found: " + filePath);
            try {
                getProjectController().openProject(file);
                return success("Project opened");
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject saveProject(String filePath) {
        return runOnEDT(() -> {
            try {
                ProjectController pc = getProjectController();
                pc.saveProject(pc.getCurrentProject(), new File(filePath));
                return success("Project saved");
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject getProjectInfo() {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            if (ws != null) {
                GraphModel gm = getGraphController().getGraphModel(ws);
                Graph g = gm.getGraph();
                r.addProperty("has_project", true);
                r.addProperty("workspace_id", ws.getId());
                r.addProperty("node_count", g.getNodeCount());
                r.addProperty("edge_count", g.getEdgeCount());
                r.addProperty("is_directed", gm.isDirected());
                r.addProperty("is_mixed", gm.isMixed());
            } else {
                r.addProperty("has_project", false);
            }
            return r;
        });
    }

    // ─── Workspace Management ────────────────────────────────────────

    public JsonObject newWorkspace() {
        return runOnEDT(() -> {
            try {
                ProjectController pc = getProjectController();
                if (pc.getCurrentProject() == null) return error("No project open");
                Workspace ws = pc.newWorkspace(pc.getCurrentProject());
                pc.openWorkspace(ws);
                JsonObject r = success("Workspace created");
                r.addProperty("workspace_id", ws.getId());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject listWorkspaces() {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            if (pc.getCurrentProject() == null) return error("No project open");
            JsonArray arr = new JsonArray();
            Workspace current = pc.getCurrentWorkspace();
            for (Workspace ws : pc.getCurrentProject().getLookup().lookupAll(Workspace.class)) {
                JsonObject o = new JsonObject();
                o.addProperty("id", ws.getId());
                o.addProperty("current", ws.equals(current));
                arr.add(o);
            }
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.add("workspaces", arr);
            return r;
        });
    }

    public JsonObject switchWorkspace(int index) {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            if (pc.getCurrentProject() == null) return error("No project open");
            int i = 0;
            for (Workspace ws : pc.getCurrentProject().getLookup().lookupAll(Workspace.class)) {
                if (i == index) {
                    pc.openWorkspace(ws);
                    return success("Switched to workspace " + ws.getId());
                }
                i++;
            }
            return error("Workspace index out of range: " + index);
        });
    }

    public JsonObject deleteWorkspace(int index) {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            if (pc.getCurrentProject() == null) return error("No project open");
            int i = 0;
            for (Workspace ws : pc.getCurrentProject().getLookup().lookupAll(Workspace.class)) {
                if (i == index) {
                    pc.deleteWorkspace(ws);
                    return success("Workspace deleted");
                }
                i++;
            }
            return error("Workspace index out of range: " + index);
        });
    }

    // ─── Node Operations ─────────────────────────────────────────────

    public JsonObject addNode(String id, String label, Map<String, Object> attrs) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                if (g.getNode(id) != null) return error("Node exists: " + id);
                Node n = gm.factory().newNode(id);
                n.setLabel(label != null ? label : id);
                n.setX((float)(Math.random() * 1000 - 500));
                n.setY((float)(Math.random() * 1000 - 500));
                n.setSize(10f);
                if (attrs != null) {
                    for (Map.Entry<String, Object> e : attrs.entrySet()) {
                        ensureColumnAndSet(gm.getNodeTable(), n, e.getKey(), e.getValue());
                    }
                }
                g.addNode(n);
                JsonObject r = success("Node added");
                r.addProperty("node_id", id);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject addNodes(List<Map<String, Object>> nodes) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            int added = 0, skipped = 0;
            g.writeLock();
            try {
                for (Map<String, Object> nd : nodes) {
                    String id = (String) nd.get("id");
                    if (id == null || g.getNode(id) != null) { skipped++; continue; }
                    String label = (String) nd.getOrDefault("label", id);
                    Node n = gm.factory().newNode(id);
                    n.setLabel(label);
                    n.setX((float)(Math.random() * 1000 - 500));
                    n.setY((float)(Math.random() * 1000 - 500));
                    n.setSize(10f);
                    g.addNode(n);
                    added++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("added", added);
                r.addProperty("skipped", skipped);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject removeNode(String id) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = getGraphController().getGraphModel(ws).getGraph();
            g.writeLock();
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                int edgesRemoved = g.getDegree(n);
                g.removeNode(n);
                JsonObject r = success("Node removed");
                r.addProperty("edges_removed", edgesRemoved);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject bulkRemoveNodes(List<String> ids) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = getGraphController().getGraphModel(ws).getGraph();
            g.writeLock();
            try {
                int removed = 0, notFound = 0;
                for (String id : ids) {
                    Node n = g.getNode(id);
                    if (n == null) { notFound++; continue; }
                    g.removeNode(n);
                    removed++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("removed", removed);
                r.addProperty("not_found", notFound);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject queryNodes(String attr, String val, int limit, int offset) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            g.readLock();
            try {
                JsonArray arr = new JsonArray();
                int count = 0, skip = 0;
                for (Node n : g.getNodes()) {
                    if (skip++ < offset) continue;
                    if (count >= limit) break;
                    JsonObject o = new JsonObject();
                    o.addProperty("id", n.getId().toString());
                    o.addProperty("label", n.getLabel());
                    o.addProperty("x", n.x());
                    o.addProperty("y", n.y());
                    o.addProperty("size", n.size());
                    o.addProperty("degree", g.getDegree(n));
                    Color c = n.getColor();
                    if (c != null) {
                        o.addProperty("r", c.getRed());
                        o.addProperty("g", c.getGreen());
                        o.addProperty("b", c.getBlue());
                        o.addProperty("a", c.getAlpha());
                    }
                    // Include all custom attributes
                    JsonObject attrs = new JsonObject();
                    for (Column col : gm.getNodeTable()) {
                        if (col.isProperty()) continue; // skip built-in
                        Object v = n.getAttribute(col);
                        if (v != null) {
                            if (v instanceof Number) attrs.addProperty(col.getTitle(), (Number) v);
                            else if (v instanceof Boolean) attrs.addProperty(col.getTitle(), (Boolean) v);
                            else attrs.addProperty(col.getTitle(), v.toString());
                        }
                    }
                    if (attrs.size() > 0) o.add("attributes", attrs);
                    arr.add(o);
                    count++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("total", g.getNodeCount());
                r.addProperty("count", count);
                r.add("nodes", arr);
                return r;
            } finally { g.readUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeLabel(String id, String label) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setLabel(label);
                return success("Label set");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodePosition(String id, float x, float y) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setX(x);
                n.setY(y);
                return success("Position set");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject batchSetPositions(List<Map<String, Object>> positions) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                int set = 0, notFound = 0;
                for (Map<String, Object> pos : positions) {
                    String id = (String) pos.get("id");
                    Node n = g.getNode(id);
                    if (n == null) { notFound++; continue; }
                    n.setX(((Number) pos.get("x")).floatValue());
                    n.setY(((Number) pos.get("y")).floatValue());
                    set++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("set", set);
                r.addProperty("not_found", notFound);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Edge Operations ─────────────────────────────────────────────

    public JsonObject addEdge(String src, String tgt, Double weight, boolean directed) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                Node s = g.getNode(src), t = g.getNode(tgt);
                if (s == null) return error("Source not found: " + src);
                if (t == null) return error("Target not found: " + tgt);
                if (findEdge(g, s, t) != null) return error("Edge exists");
                Edge e = gm.factory().newEdge(s, t, directed ? 1 : 0, weight != null ? weight : 1.0, true);
                g.addEdge(e);
                return success("Edge added");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject addEdges(List<Map<String, Object>> edges) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            int added = 0, skipped = 0;
            g.writeLock();
            try {
                for (Map<String, Object> ed : edges) {
                    String src = (String) ed.get("source");
                    String tgt = (String) ed.get("target");
                    if (src == null || tgt == null) { skipped++; continue; }
                    Node s = g.getNode(src), t = g.getNode(tgt);
                    if (s == null || t == null || findEdge(g, s, t) != null) { skipped++; continue; }
                    Double w = ed.containsKey("weight") ? ((Number) ed.get("weight")).doubleValue() : 1.0;
                    Edge e = gm.factory().newEdge(s, t, 1, w, true);
                    g.addEdge(e);
                    added++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("added", added);
                r.addProperty("skipped", skipped);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject removeEdge(String source, String target) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                g.removeEdge(e);
                return success("Edge removed");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeWeight(String source, String target, double weight) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                e.setWeight(weight);
                return success("Weight set to " + weight);
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeLabel(String source, String target, String label) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                e.setLabel(label);
                return success("Edge label set");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject queryEdges(int limit, int offset) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            g.readLock();
            try {
                JsonArray arr = new JsonArray();
                int count = 0, skip = 0;
                for (Edge e : g.getEdges()) {
                    if (skip++ < offset) continue;
                    if (count >= limit) break;
                    JsonObject o = new JsonObject();
                    o.addProperty("source", e.getSource().getId().toString());
                    o.addProperty("target", e.getTarget().getId().toString());
                    o.addProperty("weight", e.getWeight());
                    o.addProperty("directed", e.isDirected());
                    if (e.getLabel() != null) o.addProperty("label", e.getLabel());
                    Color c = e.getColor();
                    if (c != null) {
                        o.addProperty("r", c.getRed());
                        o.addProperty("g", c.getGreen());
                        o.addProperty("b", c.getBlue());
                    }
                    // Include custom attributes
                    JsonObject attrs = new JsonObject();
                    for (Column col : gm.getEdgeTable()) {
                        if (col.isProperty()) continue;
                        Object v = e.getAttribute(col);
                        if (v != null) {
                            if (v instanceof Number) attrs.addProperty(col.getTitle(), (Number) v);
                            else if (v instanceof Boolean) attrs.addProperty(col.getTitle(), (Boolean) v);
                            else attrs.addProperty(col.getTitle(), v.toString());
                        }
                    }
                    if (attrs.size() > 0) o.add("attributes", attrs);
                    arr.add(o);
                    count++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("total", g.getEdgeCount());
                r.addProperty("count", count);
                r.add("edges", arr);
                return r;
            } finally { g.readUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Graph Stats ─────────────────────────────────────────────────

    public JsonObject getGraphStats() {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            g.readLock();
            try {
                int nc = g.getNodeCount(), ec = g.getEdgeCount();
                double density = nc > 1 ? (2.0 * ec) / (nc * (nc - 1)) : 0;
                double avgDeg = nc > 0 ? (2.0 * ec) / nc : 0;
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("node_count", nc);
                r.addProperty("edge_count", ec);
                r.addProperty("density", density);
                r.addProperty("average_degree", avgDeg);
                r.addProperty("is_directed", gm.isDirected());
                return r;
            } finally { g.readUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Graph Type ──────────────────────────────────────────────────

    public JsonObject getGraphType() {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("directed", gm.isDirected());
            r.addProperty("undirected", gm.isUndirected());
            r.addProperty("mixed", gm.isMixed());
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Attribute / Column Management ───────────────────────────────

    public JsonObject getColumns(String target) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Table table = "edge".equalsIgnoreCase(target) ? gm.getEdgeTable() : gm.getNodeTable();
            JsonArray arr = new JsonArray();
            for (Column col : table) {
                JsonObject o = new JsonObject();
                o.addProperty("id", col.getId());
                o.addProperty("title", col.getTitle());
                o.addProperty("type", col.getTypeClass().getSimpleName());
                o.addProperty("property", col.isProperty());
                arr.add(o);
            }
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("target", target);
            r.add("columns", arr);
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject addColumn(String name, String type, String target) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Table table = "edge".equalsIgnoreCase(target) ? gm.getEdgeTable() : gm.getNodeTable();
            if (table.getColumn(name) != null) return error("Column already exists: " + name);
            Class<?> cls = typeStringToClass(type);
            if (cls == null) return error("Unknown type: " + type + ". Use: string, integer, double, float, boolean, long");
            table.addColumn(name, cls);
            return success("Column '" + name + "' added");
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeAttributes(String id, Map<String, Object> attrs) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                for (Map.Entry<String, Object> e : attrs.entrySet()) {
                    ensureColumnAndSet(gm.getNodeTable(), n, e.getKey(), e.getValue());
                }
                return success("Attributes set on node " + id);
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject batchSetNodeAttributes(List<Map<String, Object>> updates) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                int set = 0, notFound = 0;
                for (Map<String, Object> update : updates) {
                    String id = (String) update.get("id");
                    Node n = g.getNode(id);
                    if (n == null) { notFound++; continue; }
                    @SuppressWarnings("unchecked")
                    Map<String, Object> attrs = (Map<String, Object>) update.get("attributes");
                    if (attrs != null) {
                        for (Map.Entry<String, Object> e : attrs.entrySet()) {
                            ensureColumnAndSet(gm.getNodeTable(), n, e.getKey(), e.getValue());
                        }
                    }
                    set++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("set", set);
                r.addProperty("not_found", notFound);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeAttributes(String source, String target, Map<String, Object> attrs) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                for (Map.Entry<String, Object> entry : attrs.entrySet()) {
                    ensureColumnAndSet(gm.getEdgeTable(), e, entry.getKey(), entry.getValue());
                }
                return success("Attributes set on edge");
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    private void ensureColumnAndSet(Table table, Object element, String key, Object value) {
        Column col = table.getColumn(key);
        if (col == null) {
            Class<?> cls = String.class;
            if (value instanceof Number) {
                if (value instanceof Integer) cls = Integer.class;
                else if (value instanceof Long) cls = Long.class;
                else if (value instanceof Float) cls = Float.class;
                else cls = Double.class;
            } else if (value instanceof Boolean) {
                cls = Boolean.class;
            }
            col = table.addColumn(key, cls);
        }
        // Convert value to column type
        Object converted = convertToColumnType(value, col.getTypeClass());
        if (element instanceof Node) ((Node) element).setAttribute(col, converted);
        else if (element instanceof Edge) ((Edge) element).setAttribute(col, converted);
    }

    private Object convertToColumnType(Object value, Class<?> targetType) {
        if (value == null) return null;
        if (targetType.isInstance(value)) return value;
        String s = value.toString();
        try {
            if (targetType == Integer.class) return (int) Double.parseDouble(s);
            if (targetType == Long.class) return (long) Double.parseDouble(s);
            if (targetType == Float.class) return (float) Double.parseDouble(s);
            if (targetType == Double.class) return Double.parseDouble(s);
            if (targetType == Boolean.class) return Boolean.parseBoolean(s);
        } catch (Exception e) { /* fall through */ }
        return s;
    }

    private Class<?> typeStringToClass(String type) {
        if (type == null) return null;
        switch (type.toLowerCase()) {
            case "string": return String.class;
            case "integer": case "int": return Integer.class;
            case "double": return Double.class;
            case "float": return Float.class;
            case "boolean": case "bool": return Boolean.class;
            case "long": return Long.class;
            default: return null;
        }
    }

    // ─── Appearance: Individual Node/Edge Styling ────────────────────

    public JsonObject setNodeColor(String id, int r, int g, int b, int a) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            graph.writeLock();
            try {
                Node n = graph.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setColor(new Color(r, g, b, a));
                return success("Node color set");
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeSize(String id, float size) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            graph.writeLock();
            try {
                Node n = graph.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setSize(size);
                return success("Node size set to " + size);
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeColor(String source, String target, int r, int g, int b, int a) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            graph.writeLock();
            try {
                Node s = graph.getNode(source), t = graph.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(graph, s, t);
                if (e == null) return error("Edge not found");
                e.setColor(new Color(r, g, b, a));
                return success("Edge color set");
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject batchSetNodeColors(List<Map<String, Object>> nodeColors) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            graph.writeLock();
            try {
                int set = 0, notFound = 0;
                for (Map<String, Object> nc : nodeColors) {
                    String id = (String) nc.get("id");
                    Node n = graph.getNode(id);
                    if (n == null) { notFound++; continue; }
                    int r = ((Number) nc.get("r")).intValue();
                    int g = ((Number) nc.get("g")).intValue();
                    int b = ((Number) nc.get("b")).intValue();
                    int a = nc.containsKey("a") ? ((Number) nc.get("a")).intValue() : 255;
                    n.setColor(new Color(r, g, b, a));
                    set++;
                }
                JsonObject res = new JsonObject();
                res.addProperty("success", true);
                res.addProperty("set", set);
                res.addProperty("not_found", notFound);
                return res;
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject resetAppearance(int r, int g, int b, float size) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            Color defaultColor = new Color(r, g, b);
            graph.writeLock();
            try {
                for (Node n : graph.getNodes()) {
                    n.setColor(defaultColor);
                    n.setSize(size);
                }
                return success("Appearance reset for all nodes");
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Appearance: Color/Size by Attribute ─────────────────────────

    public JsonObject colorByPartition(String columnName, Map<String, int[]> colorMap) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph graph = gm.getGraph();
            Column col = gm.getNodeTable().getColumn(columnName);
            if (col == null) return error("Column not found: " + columnName);

            // Collect distinct values
            java.util.Map<String, Color> palette = new java.util.LinkedHashMap<>();
            if (colorMap != null && !colorMap.isEmpty()) {
                for (Map.Entry<String, int[]> e : colorMap.entrySet()) {
                    int[] c = e.getValue();
                    palette.put(e.getKey(), new Color(c[0], c[1], c[2]));
                }
            } else {
                // Auto-generate palette
                java.util.Set<String> values = new java.util.LinkedHashSet<>();
                graph.readLock();
                try {
                    for (Node n : graph.getNodes()) {
                        Object v = n.getAttribute(col);
                        if (v != null) values.add(v.toString());
                    }
                } finally { graph.readUnlock(); }

                Color[] defaultPalette = {
                    new Color(31, 119, 180), new Color(255, 127, 14), new Color(44, 160, 44),
                    new Color(214, 39, 40), new Color(148, 103, 189), new Color(140, 86, 75),
                    new Color(227, 119, 194), new Color(127, 127, 127), new Color(188, 189, 34),
                    new Color(23, 190, 207), new Color(174, 199, 232), new Color(255, 187, 120)
                };
                int idx = 0;
                for (String v : values) {
                    palette.put(v, defaultPalette[idx % defaultPalette.length]);
                    idx++;
                }
            }

            graph.writeLock();
            try {
                int colored = 0;
                for (Node n : graph.getNodes()) {
                    Object v = n.getAttribute(col);
                    if (v != null) {
                        Color c = palette.get(v.toString());
                        if (c != null) {
                            n.setColor(c);
                            colored++;
                        }
                    }
                }
                JsonObject r = success("Colored " + colored + " nodes by " + columnName);
                r.addProperty("partitions", palette.size());
                return r;
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject colorByRanking(String columnName, int rMin, int gMin, int bMin, int rMax, int gMax, int bMax) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph graph = gm.getGraph();
            Column col = gm.getNodeTable().getColumn(columnName);
            if (col == null) return error("Column not found: " + columnName);

            // Find min/max values
            double min = Double.MAX_VALUE, max = Double.MIN_VALUE;
            graph.readLock();
            try {
                for (Node n : graph.getNodes()) {
                    Object v = n.getAttribute(col);
                    if (v instanceof Number) {
                        double d = ((Number) v).doubleValue();
                        if (d < min) min = d;
                        if (d > max) max = d;
                    }
                }
            } finally { graph.readUnlock(); }

            if (min == Double.MAX_VALUE) return error("No numeric values in column " + columnName);
            double range = max - min;
            if (range == 0) range = 1;

            graph.writeLock();
            try {
                int colored = 0;
                for (Node n : graph.getNodes()) {
                    Object v = n.getAttribute(col);
                    if (v instanceof Number) {
                        double t = (((Number) v).doubleValue() - min) / range;
                        int r = (int)(rMin + t * (rMax - rMin));
                        int g = (int)(gMin + t * (gMax - gMin));
                        int b = (int)(bMin + t * (bMax - bMin));
                        n.setColor(new Color(
                            Math.max(0, Math.min(255, r)),
                            Math.max(0, Math.min(255, g)),
                            Math.max(0, Math.min(255, b))
                        ));
                        colored++;
                    }
                }
                JsonObject res = success("Colored " + colored + " nodes by ranking on " + columnName);
                res.addProperty("min_value", min);
                res.addProperty("max_value", max);
                return res;
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject sizeByRanking(String columnName, float minSize, float maxSize) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph graph = gm.getGraph();
            Column col = gm.getNodeTable().getColumn(columnName);
            if (col == null) return error("Column not found: " + columnName);

            double min = Double.MAX_VALUE, max = Double.MIN_VALUE;
            graph.readLock();
            try {
                for (Node n : graph.getNodes()) {
                    Object v = n.getAttribute(col);
                    if (v instanceof Number) {
                        double d = ((Number) v).doubleValue();
                        if (d < min) min = d;
                        if (d > max) max = d;
                    }
                }
            } finally { graph.readUnlock(); }

            if (min == Double.MAX_VALUE) return error("No numeric values in column " + columnName);
            double range = max - min;
            if (range == 0) range = 1;

            graph.writeLock();
            try {
                int sized = 0;
                for (Node n : graph.getNodes()) {
                    Object v = n.getAttribute(col);
                    if (v instanceof Number) {
                        double t = (((Number) v).doubleValue() - min) / range;
                        n.setSize((float)(minSize + t * (maxSize - minSize)));
                        sized++;
                    }
                }
                JsonObject res = success("Sized " + sized + " nodes by " + columnName);
                res.addProperty("min_value", min);
                res.addProperty("max_value", max);
                return res;
            } finally { graph.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Layout ──────────────────────────────────────────────────────

    public JsonObject runLayout(String algo, int iterations) {
        if (layoutRunning.get()) return error("Layout already running");
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Layout layout = null;
            for (LayoutBuilder b : Lookup.getDefault().lookupAll(LayoutBuilder.class)) {
                if (b.getName().toLowerCase().contains(algo.toLowerCase())) {
                    layout = b.buildLayout();
                    break;
                }
            }
            if (layout == null) return error("Layout not found: " + algo);
            layout.setGraphModel(gm);
            final Layout fl = layout;
            final int iters = iterations > 0 ? iterations : 1000;
            layoutRunning.set(true);
            currentLayoutName = algo;
            layoutFuture = layoutExecutor.submit(() -> {
                try {
                    fl.initAlgo();
                    for (int i = 0; i < iters && layoutRunning.get() && fl.canAlgo(); i++) fl.goAlgo();
                    fl.endAlgo();
                } catch (Exception e) { LOGGER.log(Level.WARNING, "Layout error", e); }
                finally { layoutRunning.set(false); currentLayoutName = null; }
            });
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("layout", algo);
            r.addProperty("status", "running");
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject stopLayout() {
        if (!layoutRunning.get()) return success("No layout running");
        layoutRunning.set(false);
        if (layoutFuture != null) layoutFuture.cancel(true);
        return success("Layout stopped");
    }

    public JsonObject getLayoutStatus() {
        JsonObject r = new JsonObject();
        r.addProperty("success", true);
        r.addProperty("running", layoutRunning.get());
        if (currentLayoutName != null) r.addProperty("layout", currentLayoutName);
        return r;
    }

    public JsonObject getAvailableLayouts() {
        JsonArray arr = new JsonArray();
        for (LayoutBuilder b : Lookup.getDefault().lookupAll(LayoutBuilder.class)) {
            JsonObject o = new JsonObject();
            o.addProperty("name", b.getName());
            arr.add(o);
        }
        JsonObject r = new JsonObject();
        r.addProperty("success", true);
        r.add("layouts", arr);
        return r;
    }

    public JsonObject getLayoutProperties(String algo) {
        try {
            Layout layout = null;
            for (LayoutBuilder b : Lookup.getDefault().lookupAll(LayoutBuilder.class)) {
                if (b.getName().toLowerCase().contains(algo.toLowerCase())) {
                    layout = b.buildLayout();
                    break;
                }
            }
            if (layout == null) return error("Layout not found: " + algo);
            // Need a graph model for the layout to report properties
            Workspace ws = currentWorkspace();
            if (ws != null) layout.setGraphModel(currentGraphModel());

            JsonArray arr = new JsonArray();
            LayoutProperty[] props = layout.getProperties();
            if (props != null) {
                for (LayoutProperty prop : props) {
                    JsonObject o = new JsonObject();
                    o.addProperty("name", prop.getCanonicalName() != null ? prop.getCanonicalName() : prop.getProperty().getDisplayName());
                    o.addProperty("display_name", prop.getProperty().getDisplayName());
                    o.addProperty("type", prop.getProperty().getValueType().getSimpleName());
                    Object val = prop.getProperty().getValue();
                    if (val != null) o.addProperty("value", val.toString());
                    String desc = prop.getProperty().getShortDescription();
                    if (desc != null) o.addProperty("description", desc);
                    arr.add(o);
                }
            }
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("algorithm", algo);
            r.add("properties", arr);
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setLayoutProperties(String algo, Map<String, Object> properties, int iterations) {
        if (layoutRunning.get()) return error("Layout already running");
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Layout layout = null;
            for (LayoutBuilder b : Lookup.getDefault().lookupAll(LayoutBuilder.class)) {
                if (b.getName().toLowerCase().contains(algo.toLowerCase())) {
                    layout = b.buildLayout();
                    break;
                }
            }
            if (layout == null) return error("Layout not found: " + algo);
            layout.setGraphModel(gm);

            // Set properties
            if (properties != null) {
                LayoutProperty[] props = layout.getProperties();
                if (props != null) {
                    for (LayoutProperty prop : props) {
                        String name = prop.getCanonicalName() != null ? prop.getCanonicalName() : prop.getProperty().getDisplayName();
                        String displayName = prop.getProperty().getDisplayName();
                        // Match by canonical name or display name
                        Object val = properties.get(name);
                        if (val == null) val = properties.get(displayName);
                        if (val == null) {
                            // Try case-insensitive match
                            for (Map.Entry<String, Object> e : properties.entrySet()) {
                                if (e.getKey().equalsIgnoreCase(name) || e.getKey().equalsIgnoreCase(displayName)) {
                                    val = e.getValue();
                                    break;
                                }
                            }
                        }
                        if (val != null) {
                            Class<?> type = prop.getProperty().getValueType();
                            Object converted = convertLayoutProperty(val, type);
                            if (converted != null) prop.getProperty().setValue(converted);
                        }
                    }
                }
            }

            // Run layout with configured properties
            final Layout fl = layout;
            final int iters = iterations > 0 ? iterations : 1000;
            layoutRunning.set(true);
            currentLayoutName = algo;
            layoutFuture = layoutExecutor.submit(() -> {
                try {
                    fl.initAlgo();
                    for (int i = 0; i < iters && layoutRunning.get() && fl.canAlgo(); i++) fl.goAlgo();
                    fl.endAlgo();
                } catch (Exception e) { LOGGER.log(Level.WARNING, "Layout error", e); }
                finally { layoutRunning.set(false); currentLayoutName = null; }
            });
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("layout", algo);
            r.addProperty("status", "running");
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    private Object convertLayoutProperty(Object val, Class<?> type) {
        if (val == null) return null;
        String s = val.toString();
        try {
            if (type == Boolean.class || type == boolean.class) return Boolean.parseBoolean(s);
            if (type == Integer.class || type == int.class) return (int) Double.parseDouble(s);
            if (type == Double.class || type == double.class) return Double.parseDouble(s);
            if (type == Float.class || type == float.class) return (float) Double.parseDouble(s);
            if (type == Long.class || type == long.class) return (long) Double.parseDouble(s);
            if (type == String.class) return s;
        } catch (Exception e) { /* fall through */ }
        return null;
    }

    // ─── Statistics ──────────────────────────────────────────────────

    private JsonObject runStatistic(String builderName, Map<String, Object> params) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();

            // Find statistics builder by name
            StatisticsBuilder matchedBuilder = null;
            for (StatisticsBuilder sb : Lookup.getDefault().lookupAll(StatisticsBuilder.class)) {
                String name = sb.getName();
                LOGGER.info("MCP: Found StatisticsBuilder: " + name + " (" + sb.getClass().getName() + ")");
                if (name.equalsIgnoreCase(builderName) || sb.getClass().getSimpleName().toLowerCase().contains(builderName.toLowerCase())) {
                    matchedBuilder = sb;
                    break;
                }
            }
            if (matchedBuilder == null) {
                // Also try matching by statistics class name
                for (StatisticsBuilder sb : Lookup.getDefault().lookupAll(StatisticsBuilder.class)) {
                    try {
                        Statistics stat = sb.getStatistics();
                        if (stat.getClass().getSimpleName().equalsIgnoreCase(builderName)) {
                            matchedBuilder = sb;
                            break;
                        }
                    } catch (Exception e) { /* skip */ }
                }
            }
            if (matchedBuilder == null) return error("Statistics not found: " + builderName);

            Statistics stat = matchedBuilder.getStatistics();

            // Set parameters via reflection
            if (params != null) {
                for (Map.Entry<String, Object> e : params.entrySet()) {
                    setViaReflection(stat, e.getKey(), e.getValue());
                }
            }

            // Execute
            stat.execute(gm);

            // Build result
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.addProperty("statistic", matchedBuilder.getName());

            // Try to get common result values via reflection
            tryAddResult(r, stat, "getModularity", "modularity");
            tryAddResult(r, stat, "getAverageDegree", "average_degree");
            tryAddResult(r, stat, "getPathLength", "average_path_length");
            tryAddResult(r, stat, "getDiameter", "diameter");
            tryAddResult(r, stat, "getRadius", "radius");
            tryAddResult(r, stat, "getAverageClusteringCoefficient", "average_clustering_coefficient");
            tryAddResult(r, stat, "getConnectedComponentsCount", "connected_components");

            // Get the report
            try {
                String report = stat.getReport();
                if (report != null) {
                    r.addProperty("report_available", true);
                    r.addProperty("report_html", report);
                }
            } catch (Exception e) { /* no report */ }

            return r;
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Statistic execution failed", e);
            return error("Failed: " + e.getMessage());
        }
    }

    private void setViaReflection(Object obj, String setter, Object value) {
        String methodName = "set" + setter.substring(0, 1).toUpperCase() + setter.substring(1);
        try {
            for (java.lang.reflect.Method m : obj.getClass().getMethods()) {
                if (m.getName().equals(methodName) && m.getParameterCount() == 1) {
                    Class<?> paramType = m.getParameterTypes()[0];
                    Object converted = convertLayoutProperty(value, paramType);
                    if (converted != null) m.invoke(obj, converted);
                    return;
                }
            }
        } catch (Exception e) {
            LOGGER.fine("Could not set " + methodName + ": " + e.getMessage());
        }
    }

    private void tryAddResult(JsonObject r, Object obj, String getter, String jsonKey) {
        try {
            java.lang.reflect.Method m = obj.getClass().getMethod(getter);
            Object val = m.invoke(obj);
            if (val instanceof Number) r.addProperty(jsonKey, (Number) val);
            else if (val instanceof Boolean) r.addProperty(jsonKey, (Boolean) val);
            else if (val != null) r.addProperty(jsonKey, val.toString());
        } catch (NoSuchMethodException e) { /* method not available for this statistic */ }
        catch (Exception e) { LOGGER.fine("Could not get " + getter + ": " + e.getMessage()); }
    }

    public JsonObject computeModularity(double resolution) {
        java.util.Map<String, Object> params = new java.util.HashMap<>();
        params.put("resolution", resolution);
        params.put("useWeight", false);
        return runStatistic("Modularity", params);
    }

    public JsonObject computeDegree() {
        return runStatistic("Degree", null);
    }

    public JsonObject computeBetweenness() {
        return runStatistic("GraphDistance", null);
    }

    public JsonObject computePageRank() {
        return runStatistic("PageRank", null);
    }

    public JsonObject computeConnectedComponents() {
        return runStatistic("ConnectedComponents", null);
    }

    public JsonObject computeClusteringCoefficient() {
        return runStatistic("ClusteringCoefficient", null);
    }

    public JsonObject computeAvgPathLength() {
        java.util.Map<String, Object> params = new java.util.HashMap<>();
        params.put("directed", false);
        return runStatistic("GraphDistance", params);
    }

    public JsonObject computeHITS() {
        return runStatistic("HITS", null);
    }

    public JsonObject computeEigenvectorCentrality() {
        return runStatistic("EigenvectorCentrality", null);
    }

    // ─── Filters ─────────────────────────────────────────────────────

    public JsonObject filterByDegreeRange(int minDegree, int maxDegree) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();

            // Manual filtering: remove nodes outside degree range
            g.writeLock();
            try {
                java.util.List<Node> toRemove = new java.util.ArrayList<>();
                for (Node n : g.getNodes()) {
                    int deg = g.getDegree(n);
                    if (deg < minDegree || (maxDegree > 0 && deg > maxDegree)) {
                        toRemove.add(n);
                    }
                }
                for (Node n : toRemove) g.removeNode(n);
                JsonObject r = success("Filtered by degree [" + minDegree + ", " + maxDegree + "]");
                r.addProperty("removed", toRemove.size());
                r.addProperty("remaining_nodes", g.getNodeCount());
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject filterByEdgeWeight(double minWeight, double maxWeight) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();

            g.writeLock();
            try {
                java.util.List<Edge> toRemove = new java.util.ArrayList<>();
                for (Edge e : g.getEdges()) {
                    double w = e.getWeight();
                    if (w < minWeight || (maxWeight > 0 && w > maxWeight)) {
                        toRemove.add(e);
                    }
                }
                for (Edge e : toRemove) g.removeEdge(e);
                JsonObject r = success("Filtered edges by weight [" + minWeight + ", " + maxWeight + "]");
                r.addProperty("removed", toRemove.size());
                r.addProperty("remaining_edges", g.getEdgeCount());
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Preview Settings ────────────────────────────────────────────

    public JsonObject getPreviewSettings() {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                PreviewModel pm = pc.getModel(ws);
                if (pm == null) return error("Preview model not available");

                JsonObject settings = new JsonObject();
                // Get commonly used properties
                for (PreviewProperty prop : pm.getProperties().getProperties()) {
                    String name = prop.getName();
                    Object val = prop.getValue();
                    if (val != null) {
                        if (val instanceof Color) {
                            Color c = (Color) val;
                            settings.addProperty(name, String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()));
                        } else if (val instanceof Number) {
                            settings.addProperty(name, (Number) val);
                        } else if (val instanceof Boolean) {
                            settings.addProperty(name, (Boolean) val);
                        } else {
                            settings.addProperty(name, val.toString());
                        }
                    }
                }

                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.add("settings", settings);
                return r;
            } catch (Exception e) {
                return error("Failed: " + e.getMessage());
            }
        });
    }

    public JsonObject setPreviewSettings(Map<String, Object> settings) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                PreviewModel pm = pc.getModel(ws);
                if (pm == null) return error("Preview model not available");

                int set = 0;
                for (Map.Entry<String, Object> e : settings.entrySet()) {
                    String key = e.getKey();
                    Object val = e.getValue();
                    if (val == null) continue;  // Skip null values to avoid corrupting preview model
                    PreviewProperty prop = pm.getProperties().getProperty(key);
                    if (prop != null) {
                        // Convert value based on property type
                        Class<?> type = prop.getType();
                        if (type == Color.class && val instanceof String) {
                            String hex = (String) val;
                            if (hex.startsWith("#")) hex = hex.substring(1);
                            prop.setValue(new Color(Integer.parseInt(hex, 16)));
                        } else if (type == Boolean.class || type == boolean.class) {
                            prop.setValue(Boolean.parseBoolean(val.toString()));
                        } else if (type == Float.class || type == float.class) {
                            prop.setValue(Float.parseFloat(val.toString()));
                        } else if (type == Integer.class || type == int.class) {
                            prop.setValue(Integer.parseInt(val.toString()));
                        } else if (type == java.awt.Font.class && val instanceof String) {
                            // Parse font string like "Arial 12 Bold" -> Font object
                            String fontStr = val.toString().trim();
                            String[] parts = fontStr.split("\\s+");
                            String name = parts.length > 0 ? parts[0] : "Arial";
                            int size = 12;
                            int style = java.awt.Font.PLAIN;
                            for (int i = 1; i < parts.length; i++) {
                                try { size = Integer.parseInt(parts[i]); }
                                catch (NumberFormatException nfe) {
                                    if ("Bold".equalsIgnoreCase(parts[i])) style = java.awt.Font.BOLD;
                                    else if ("Italic".equalsIgnoreCase(parts[i])) style = java.awt.Font.ITALIC;
                                }
                            }
                            prop.setValue(new java.awt.Font(name, style, size));
                        } else if (type == java.awt.Font.class) {
                            // Non-string font value, skip to avoid corruption
                            continue;
                        } else if (type == DependantColor.class && val instanceof String) {
                            // DependantColor supports: "parent", "darker", or "#RRGGBB" hex for custom
                            String s = val.toString().trim().toLowerCase();
                            if ("parent".equals(s)) {
                                prop.setValue(new DependantColor(DependantColor.Mode.PARENT));
                            } else if ("darker".equals(s)) {
                                prop.setValue(new DependantColor(DependantColor.Mode.DARKER));
                            } else if (s.startsWith("#")) {
                                Color c = new Color(Integer.parseInt(s.substring(1), 16));
                                prop.setValue(new DependantColor(c));
                            } else {
                                continue; // Skip unknown value to avoid corruption
                            }
                        } else if (type == DependantOriginalColor.class && val instanceof String) {
                            // DependantOriginalColor supports: "parent", "original", or "#RRGGBB" hex
                            String s = val.toString().trim().toLowerCase();
                            if ("parent".equals(s)) {
                                prop.setValue(new DependantOriginalColor(DependantOriginalColor.Mode.PARENT));
                            } else if ("original".equals(s)) {
                                prop.setValue(new DependantOriginalColor(DependantOriginalColor.Mode.ORIGINAL));
                            } else if (s.startsWith("#")) {
                                Color c = new Color(Integer.parseInt(s.substring(1), 16));
                                prop.setValue(new DependantOriginalColor(c));
                            } else {
                                continue; // Skip unknown value to avoid corruption
                            }
                        } else if (type == EdgeColor.class && val instanceof String) {
                            // EdgeColor supports: "source", "target", "mixed", "original", or "#RRGGBB" hex
                            String s = val.toString().trim().toLowerCase();
                            if ("source".equals(s)) {
                                prop.setValue(new EdgeColor(EdgeColor.Mode.SOURCE));
                            } else if ("target".equals(s)) {
                                prop.setValue(new EdgeColor(EdgeColor.Mode.TARGET));
                            } else if ("mixed".equals(s)) {
                                prop.setValue(new EdgeColor(EdgeColor.Mode.MIXED));
                            } else if ("original".equals(s)) {
                                prop.setValue(new EdgeColor(EdgeColor.Mode.ORIGINAL));
                            } else if (s.startsWith("#")) {
                                Color c = new Color(Integer.parseInt(s.substring(1), 16));
                                prop.setValue(new EdgeColor(c));
                            } else {
                                continue; // Skip unknown value to avoid corruption
                            }
                        } else {
                            // Skip unknown types to avoid corrupting the preview model
                            continue;
                        }
                        set++;
                    }
                }
                JsonObject r = success("Set " + set + " preview properties");
                r.addProperty("properties_set", set);
                return r;
            } catch (Exception e) {
                return error("Failed: " + e.getMessage());
            }
        });
    }

    // ─── Export ───────────────────────────────────────────────────────

    public JsonObject exportGexf(String filePath) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("gexf");
                if (exporter == null) return error("GEXF exporter not available");
                if (exporter instanceof GraphExporter) {
                    ((GraphExporter) exporter).setExportVisible(true);
                    ((GraphExporter) exporter).setWorkspace(ws);
                }
                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportPng(String filePath, int w, int h) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                // Refresh preview first
                PreviewController previewController = Lookup.getDefault().lookup(PreviewController.class);
                if (previewController != null) {
                    previewController.refreshPreview(ws);
                }

                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("png");
                if (exporter == null) return error("PNG exporter not available");

                // Set dimensions via reflection (PNGExporter is in plugin, not API)
                setViaReflection(exporter, "width", w);
                setViaReflection(exporter, "height", h);

                if (exporter instanceof GraphExporter) {
                    ((GraphExporter) exporter).setWorkspace(ws);
                }

                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportPdf(String filePath, int w, int h) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                PreviewController previewController = Lookup.getDefault().lookup(PreviewController.class);
                if (previewController != null) previewController.refreshPreview(ws);

                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("pdf");
                if (exporter == null) return error("PDF exporter not available");
                if (w > 0) setViaReflection(exporter, "width", w);
                if (h > 0) setViaReflection(exporter, "height", h);
                if (exporter instanceof GraphExporter) ((GraphExporter) exporter).setWorkspace(ws);
                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportSvg(String filePath) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                PreviewController previewController = Lookup.getDefault().lookup(PreviewController.class);
                if (previewController != null) previewController.refreshPreview(ws);

                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("svg");
                if (exporter == null) return error("SVG exporter not available");
                if (exporter instanceof GraphExporter) ((GraphExporter) exporter).setWorkspace(ws);
                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportGraphml(String filePath) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("graphml");
                if (exporter == null) return error("GraphML exporter not available");
                if (exporter instanceof GraphExporter) {
                    ((GraphExporter) exporter).setExportVisible(true);
                    ((GraphExporter) exporter).setWorkspace(ws);
                }
                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportCsv(String filePath, String separator, String target) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                ExportController ec = Lookup.getDefault().lookup(ExportController.class);
                Exporter exporter = ec.getExporter("csv");
                if (exporter == null) {
                    // Manual CSV export fallback
                    return exportCsvManual(filePath, separator, target);
                }
                if (exporter instanceof GraphExporter) {
                    ((GraphExporter) exporter).setWorkspace(ws);
                }
                ec.exportFile(new File(filePath), exporter);
                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    private JsonObject exportCsvManual(String filePath, String separator, String target) {
        try {
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            String sep = separator != null ? separator : ",";
            StringBuilder sb = new StringBuilder();

            if (!"edges".equalsIgnoreCase(target)) {
                // Export nodes
                sb.append("Id").append(sep).append("Label");
                for (Column col : gm.getNodeTable()) {
                    if (!col.isProperty()) sb.append(sep).append(col.getTitle());
                }
                sb.append("\n");
                g.readLock();
                try {
                    for (Node n : g.getNodes()) {
                        sb.append(n.getId()).append(sep).append(n.getLabel() != null ? n.getLabel() : "");
                        for (Column col : gm.getNodeTable()) {
                            if (!col.isProperty()) {
                                Object v = n.getAttribute(col);
                                sb.append(sep).append(v != null ? v.toString() : "");
                            }
                        }
                        sb.append("\n");
                    }
                } finally { g.readUnlock(); }
            }

            if ("edges".equalsIgnoreCase(target) || "both".equalsIgnoreCase(target)) {
                if (sb.length() > 0) sb.append("\n");
                sb.append("Source").append(sep).append("Target").append(sep).append("Weight");
                for (Column col : gm.getEdgeTable()) {
                    if (!col.isProperty()) sb.append(sep).append(col.getTitle());
                }
                sb.append("\n");
                g.readLock();
                try {
                    for (Edge e : g.getEdges()) {
                        sb.append(e.getSource().getId()).append(sep).append(e.getTarget().getId()).append(sep).append(e.getWeight());
                        for (Column col : gm.getEdgeTable()) {
                            if (!col.isProperty()) {
                                Object v = e.getAttribute(col);
                                sb.append(sep).append(v != null ? v.toString() : "");
                            }
                        }
                        sb.append("\n");
                    }
                } finally { g.readUnlock(); }
            }

            java.io.FileWriter fw = new java.io.FileWriter(filePath);
            fw.write(sb.toString());
            fw.close();
            return success("Exported to " + filePath);
        } catch (Exception e) {
            return error("CSV export failed: " + e.getMessage());
        }
    }

    // ─── Import ──────────────────────────────────────────────────────

    public JsonObject importFile(String filePath) {
        return runOnEDT(() -> {
            File file = new File(filePath);
            if (!file.exists()) return error("File not found: " + filePath);
            try {
                ImportController ic = Lookup.getDefault().lookup(ImportController.class);
                Container c = ic.importFile(file);
                if (c == null) return error("Import failed - unsupported format or empty file");

                Workspace ws = currentWorkspace();
                if (ws == null) {
                    getProjectController().newProject();
                    ws = currentWorkspace();
                }

                Processor processor = null;
                for (Processor p : Lookup.getDefault().lookupAll(Processor.class)) {
                    if (p.getClass().getSimpleName().equals("DefaultProcessor")) {
                        processor = p;
                        break;
                    }
                }
                if (processor == null) processor = Lookup.getDefault().lookup(Processor.class);
                if (processor == null) return error("No processor found");

                ic.process(c, processor, ws);
                Graph g = getGraphController().getGraphModel(ws).getGraph();
                JsonObject r = success("Imported from " + file.getName());
                r.addProperty("node_count", g.getNodeCount());
                r.addProperty("edge_count", g.getEdgeCount());
                return r;
            } catch (Exception e) { return error("Import failed: " + e.getMessage()); }
        });
    }

    // ─── Graph Operations ────────────────────────────────────────────

    public JsonObject clearGraph() {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            g.writeLock();
            try {
                int nodeCount = g.getNodeCount();
                int edgeCount = g.getEdgeCount();
                g.clear();
                JsonObject r = success("Graph cleared");
                r.addProperty("nodes_removed", nodeCount);
                r.addProperty("edges_removed", edgeCount);
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

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

    public JsonObject extractEgoNetwork(String nodeId, int depth) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            g.writeLock();
            try {
                Node center = g.getNode(nodeId);
                if (center == null) return error("Node not found: " + nodeId);

                // BFS to find nodes within depth
                java.util.Set<Node> keep = new java.util.LinkedHashSet<>();
                java.util.Queue<Node> queue = new java.util.LinkedList<>();
                java.util.Map<Node, Integer> distances = new java.util.HashMap<>();
                keep.add(center);
                queue.add(center);
                distances.put(center, 0);

                while (!queue.isEmpty()) {
                    Node current = queue.poll();
                    int dist = distances.get(current);
                    if (dist >= depth) continue;
                    for (Node neighbor : g.getNeighbors(current)) {
                        if (!keep.contains(neighbor)) {
                            keep.add(neighbor);
                            queue.add(neighbor);
                            distances.put(neighbor, dist + 1);
                        }
                    }
                }

                // Remove nodes not in keep set
                java.util.List<Node> toRemove = new java.util.ArrayList<>();
                for (Node n : g.getNodes()) {
                    if (!keep.contains(n)) toRemove.add(n);
                }
                for (Node n : toRemove) g.removeNode(n);

                JsonObject r = success("Ego network extracted for " + nodeId);
                r.addProperty("kept_nodes", keep.size());
                r.addProperty("removed_nodes", toRemove.size());
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject extractGiantComponent() {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();

            // First, run connected components
            StatisticsBuilder ccBuilder = null;
            for (StatisticsBuilder sb : Lookup.getDefault().lookupAll(StatisticsBuilder.class)) {
                if (sb.getName().equalsIgnoreCase("ConnectedComponents") ||
                    sb.getClass().getSimpleName().toLowerCase().contains("connectedcomponents")) {
                    ccBuilder = sb;
                    break;
                }
            }
            if (ccBuilder == null) return error("ConnectedComponents statistic not found");

            Statistics stat = ccBuilder.getStatistics();
            stat.execute(gm);

            // Find the column
            Column ccCol = gm.getNodeTable().getColumn("componentnumber");
            if (ccCol == null) {
                // Try alternate column names
                for (Column col : gm.getNodeTable()) {
                    if (col.getTitle().toLowerCase().contains("component")) {
                        ccCol = col;
                        break;
                    }
                }
            }
            if (ccCol == null) return error("Component column not found after running statistics");

            // Count nodes per component
            g.readLock();
            java.util.Map<Integer, Integer> componentSizes = new java.util.HashMap<>();
            try {
                for (Node n : g.getNodes()) {
                    Object v = n.getAttribute(ccCol);
                    int comp = v instanceof Number ? ((Number) v).intValue() : 0;
                    componentSizes.put(comp, componentSizes.getOrDefault(comp, 0) + 1);
                }
            } finally { g.readUnlock(); }

            // Find largest component
            int giantComp = 0;
            int giantSize = 0;
            for (java.util.Map.Entry<Integer, Integer> e : componentSizes.entrySet()) {
                if (e.getValue() > giantSize) {
                    giantSize = e.getValue();
                    giantComp = e.getKey();
                }
            }

            // Remove nodes not in giant component
            final int gc = giantComp;
            final Column fccCol = ccCol;
            g.writeLock();
            try {
                java.util.List<Node> toRemove = new java.util.ArrayList<>();
                for (Node n : g.getNodes()) {
                    Object v = n.getAttribute(fccCol);
                    int comp = v instanceof Number ? ((Number) v).intValue() : -1;
                    if (comp != gc) toRemove.add(n);
                }
                for (Node n : toRemove) g.removeNode(n);

                JsonObject r = success("Giant component extracted");
                r.addProperty("kept_nodes", giantSize);
                r.addProperty("removed_nodes", toRemove.size());
                r.addProperty("component_count", componentSizes.size());
                return r;
            } finally { g.writeUnlock(); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeThicknessByWeight(float minThickness, float maxThickness) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                PreviewModel pm = pc.getModel(ws);
                if (pm == null) return error("Preview model not available");

                // Set edge thickness to be rescaled based on weight
                // Use the preview property for edge thickness
                PreviewProperty edgeThicknessProp = pm.getProperties().getProperty("edge.thickness");
                if (edgeThicknessProp != null) {
                    edgeThicknessProp.setValue(minThickness);
                }

                // Set rescale weight property if available
                PreviewProperty rescaleProp = pm.getProperties().getProperty("edge.rescale-weight");
                if (rescaleProp != null) {
                    rescaleProp.setValue(true);
                }

                PreviewProperty rescaleMinProp = pm.getProperties().getProperty("edge.rescale-weight.min");
                if (rescaleMinProp != null) {
                    rescaleMinProp.setValue(minThickness);
                }

                PreviewProperty rescaleMaxProp = pm.getProperties().getProperty("edge.rescale-weight.max");
                if (rescaleMaxProp != null) {
                    rescaleMaxProp.setValue(maxThickness);
                }

                JsonObject r = success("Edge thickness configured by weight");
                r.addProperty("min_thickness", minThickness);
                r.addProperty("max_thickness", maxThickness);
                return r;
            } catch (Exception e) {
                return error("Failed: " + e.getMessage());
            }
        });
    }

    public JsonObject resetFilters() {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            // Reset visible view to the main view (show all nodes/edges)
            gm.setVisibleView(null);
            return success("Filters reset - full graph view restored");
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Shutdown ────────────────────────────────────────────────────

    public void shutdown() {
        layoutRunning.set(false);
        layoutExecutor.shutdownNow();
    }
}
