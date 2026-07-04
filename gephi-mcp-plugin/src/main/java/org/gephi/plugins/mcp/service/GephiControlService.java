package org.gephi.plugins.mcp.service;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.StringWriter;
import javax.imageio.ImageIO;
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
    // Stored when setPreviewSettings receives background.color — used by exportPng to composite background
    private volatile Color exportBackgroundColor = null;

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
        // Bounded wait: invokeAndWait parks forever when the EDT is wedged (the
        // "health answers but nothing else does" symptom). Fail fast with guidance
        // instead of hanging until the client's timeout.
        final Object[] result = new Object[1];
        final Exception[] exception = new Exception[1];
        final java.util.concurrent.CountDownLatch done = new java.util.concurrent.CountDownLatch(1);
        SwingUtilities.invokeLater(() -> {
            try { result[0] = callable.call(); }
            catch (Exception e) { exception[0] = e; }
            finally { done.countDown(); }
        });
        try {
            if (!done.await(15, java.util.concurrent.TimeUnit.SECONDS)) {
                throw new RuntimeException(
                    "Gephi's UI thread is unresponsive — the app is likely wedged; fully quit and reopen Gephi");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted while waiting for Gephi's UI thread");
        }
        if (exception[0] != null) throw new RuntimeException(exception[0]);
        return (T) result[0];
    }

    static JsonObject success(String msg) {
        JsonObject r = new JsonObject();
        r.addProperty("success", true);
        r.addProperty("message", msg);
        return r;
    }

    static JsonObject error(String msg) {
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

    // ─── Write-lock acquisition (VizEngine-deadlock-safe) ────────────────

    private static volatile java.lang.reflect.Field WRITE_LOCK_FIELD;

    /**
     * Acquire the graph write lock by polling a non-queuing tryLock() instead of the
     * blocking writeLock(). Gephi's OpenGL VizEngine runs a concurrent "world updater"
     * that holds read locks while join()-ing on sub-tasks that also need read locks; a
     * writer parked indefinitely in the lock's wait queue blocks those sub-readers (writer
     * preference) and deadlocks the renderer permanently (the chronic macOS hang).
     *
     * We instead use a SHORT timed tryLock: it queues only briefly, so it still gets
     * writer-preference and acquires even while the renderer reads near-continuously
     * (e.g. right after a layout) — but if it lands in the nested-read window it times out,
     * dequeues, lets the renderer drain, and retries. So it can never wedge. Once we hold
     * the lock, any Gephi-internal writeLock() on this same thread (setVisibleView, etc.)
     * re-enters for free, which is why callers wrap those calls too. Falls back to the plain
     * blocking lock only if the underlying lock can't be reflected. Throws after ~15s, which
     * callers turn into a "graph busy" error instead of hanging forever.
     */
    static void lockWrite(Graph g) {
        RenderPause.pause();   // free the renderer's read-lock pressure for this section
        boolean acquired = false;
        try {
            java.util.concurrent.locks.ReentrantReadWriteLock.WriteLock wl = writeLockHandle(g);
            if (wl == null) { g.writeLock(); acquired = true; return; }
            long deadline = System.nanoTime() + 15_000_000_000L;
            while (!wl.tryLock(120, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                if (System.nanoTime() > deadline)
                    throw new RuntimeException("Graph is busy (renderer holds the lock); please retry");
                Thread.sleep(5);
            }
            acquired = true;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted while acquiring the write lock");
        } finally {
            if (!acquired) RenderPause.resume();
        }
    }

    /** Release the write lock and resume the renderer paused by lockWrite. */
    static void unlockWrite(Graph g) {
        try {
            g.writeUnlock();
        } finally {
            RenderPause.resume();
        }
    }

    private static volatile java.lang.reflect.Field READ_LOCK_FIELD;

    /*
     * ITERATION RULE (wedge prevention): never iterate a live NodeIterable /
     * EdgeIterable directly — always iterate .toArray(). A live iterator
     * auto-acquires the graph read lock in its constructor and releases it only
     * on exhaustion or doBreak(); an early break, return, or exception leaks the
     * hold, and because NanoHTTPD threads die after their request, the leak is
     * permanent and wedges every future write (found the hard way; see
     * GraphOpsTest#earlyBreakOverToArraySnapshotLeavesNoReadHold).
     */

    /**
     * Timed read-lock acquisition. Plain readLock() parks unboundedly in the lock's
     * wait queue; when a writer is already parked (Gephi's own blocking writeLock())
     * every new reader queues behind it and the request hangs until the client's
     * timeout — the chronic "health answers but nothing else does" symptom. A timed
     * tryLock turns that into an immediate, actionable error instead.
     */
    static void lockRead(Graph g) {
        java.util.concurrent.locks.ReentrantReadWriteLock.ReadLock rl = readLockHandle(g);
        if (rl == null) { g.readLock(); return; }
        long deadline = System.nanoTime() + 10_000_000_000L;
        try {
            while (!rl.tryLock(120, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                if (System.nanoTime() > deadline)
                    throw new RuntimeException(
                        "Graph is busy (lock unavailable) — if this persists, Gephi is wedged; fully quit and reopen it");
                Thread.sleep(5);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted while acquiring the read lock");
        }
    }

    /** The underlying ReentrantReadWriteLock.ReadLock behind Graph.getLock(), or null if unreachable. */
    static java.util.concurrent.locks.ReentrantReadWriteLock.ReadLock readLockHandle(Graph g) {
        try {
            org.gephi.graph.api.GraphLock lock = g.getLock();
            if (lock == null) return null;
            java.lang.reflect.Field f = READ_LOCK_FIELD;
            if (f == null || !f.getDeclaringClass().isInstance(lock)) {
                f = lock.getClass().getDeclaredField("readLock");
                f.setAccessible(true);
                READ_LOCK_FIELD = f;
            }
            Object v = f.get(lock);
            return (v instanceof java.util.concurrent.locks.ReentrantReadWriteLock.ReadLock)
                ? (java.util.concurrent.locks.ReentrantReadWriteLock.ReadLock) v : null;
        } catch (Throwable t) {
            return null;
        }
    }

    /** The underlying ReentrantReadWriteLock.WriteLock behind Graph.getLock(), or null if unreachable. */
    static java.util.concurrent.locks.ReentrantReadWriteLock.WriteLock writeLockHandle(Graph g) {
        try {
            org.gephi.graph.api.GraphLock lock = g.getLock();
            if (lock == null) return null;
            java.lang.reflect.Field f = WRITE_LOCK_FIELD;
            if (f == null || !f.getDeclaringClass().isInstance(lock)) {
                f = lock.getClass().getDeclaredField("writeLock");
                f.setAccessible(true);
                WRITE_LOCK_FIELD = f;
            }
            Object v = f.get(lock);
            return (v instanceof java.util.concurrent.locks.ReentrantReadWriteLock.WriteLock)
                ? (java.util.concurrent.locks.ReentrantReadWriteLock.WriteLock) v : null;
        } catch (Throwable t) {
            return null;
        }
    }

    /** Find an edge between two nodes, checking all edge types (directed type 1 and undirected type 0). */
    static Edge findEdge(Graph g, Node source, Node target) {
        Edge e = g.getEdge(source, target, 1);  // directed
        if (e == null) e = g.getEdge(source, target, 0);  // undirected
        if (e == null) e = g.getEdge(source, target);  // default
        return e;
    }

    /** Locate a layout builder by name (see bestLayoutMatch for the matching rules). */
    private Layout findLayout(String algo) {
        java.util.List<LayoutBuilder> builders = new java.util.ArrayList<>();
        java.util.List<String> names = new java.util.ArrayList<>();
        for (LayoutBuilder b : Lookup.getDefault().lookupAll(LayoutBuilder.class)) {
            builders.add(b);
            names.add(b.getName());
        }
        int idx = bestLayoutMatch(names, algo);
        return idx >= 0 ? builders.get(idx).buildLayout() : null;
    }

    /**
     * Index of the best layout-name match for {@code query}, or -1. An exact match wins
     * (case- and space-insensitive, so the documented "forceatlas2" matches "ForceAtlas 2"
     * and "yifanhu" matches "Yifan Hu"); otherwise the first substring match. Space-folding
     * is what makes the short names in the docs/skill actually resolve. Package-private +
     * static for unit testing without the layout registry.
     */
    static int bestLayoutMatch(java.util.List<String> names, String query) {
        if (query == null) return -1;
        String q = query.toLowerCase().trim();
        String qns = q.replace(" ", "");
        if (qns.isEmpty()) return -1;
        int substr = -1;
        for (int i = 0; i < names.size(); i++) {
            String name = names.get(i);
            if (name == null) continue;
            String n = name.toLowerCase();
            String nns = n.replace(" ", "");
            if (n.equals(q) || nns.equals(qns)) return i;
            if (substr == -1 && (n.contains(q) || nns.contains(qns))) substr = i;
        }
        return substr;
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
            for (Workspace ws : pc.getCurrentProject().getWorkspaces()) {
                JsonObject o = new JsonObject();
                o.addProperty("id", ws.getId());
                o.addProperty("name", ws.getName() != null ? ws.getName() : "Workspace " + ws.getId());
                o.addProperty("current", ws.equals(current));
                GraphModel gm = getGraphController().getGraphModel(ws);
                if (gm != null) {
                    Graph g = gm.getGraph();
                    o.addProperty("node_count", g.getNodeCount());
                    o.addProperty("edge_count", g.getEdgeCount());
                } else {
                    o.addProperty("node_count", 0);
                    o.addProperty("edge_count", 0);
                }
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
            for (Workspace ws : pc.getCurrentProject().getWorkspaces()) {
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
            for (Workspace ws : pc.getCurrentProject().getWorkspaces()) {
                if (i == index) {
                    pc.deleteWorkspace(ws);
                    return success("Workspace deleted");
                }
                i++;
            }
            return error("Workspace index out of range: " + index);
        });
    }

    public JsonObject duplicateWorkspace(int index) {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            if (pc.getCurrentProject() == null) return error("No project open");
            int i = 0;
            for (Workspace ws : pc.getCurrentProject().getWorkspaces()) {
                if (i == index) {
                    try {
                        Workspace copy = pc.duplicateWorkspace(ws);
                        pc.openWorkspace(copy);
                        JsonObject r = success("Workspace duplicated");
                        r.addProperty("workspace_id", copy.getId());
                        return r;
                    } catch (Exception e) { return error("Failed: " + e.getMessage()); }
                }
                i++;
            }
            return error("Workspace index out of range: " + index);
        });
    }

    public JsonObject renameWorkspace(int index, String name) {
        return runOnEDT(() -> {
            ProjectController pc = getProjectController();
            if (pc.getCurrentProject() == null) return error("No project open");
            int i = 0;
            for (Workspace ws : pc.getCurrentProject().getWorkspaces()) {
                if (i == index) {
                    try {
                        pc.renameWorkspace(ws, name);
                        return success("Workspace renamed to: " + name);
                    } catch (Exception e) { return error("Failed: " + e.getMessage()); }
                }
                i++;
            }
            return error("Workspace index out of range: " + index);
        });
    }

    // ─── Node Operations ─────────────────────────────────────────────

    public JsonObject addNode(String id, String label, Map<String, Object> attrs) {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        return addNodeToModel(getGraphController().getGraphModel(ws), id, label, attrs);
    }

    /** Core node-add against an explicit model. Package-private + static so it is testable with a standalone GraphModel. */
    static JsonObject addNodeToModel(GraphModel gm, String id, String label, Map<String, Object> attrs) {
        try {
            Graph g = gm.getGraph();
            lockWrite(g);
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
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject addNodes(List<Map<String, Object>> nodes) {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        return addNodesToModel(getGraphController().getGraphModel(ws), nodes);
    }

    /** Core batch node-add against an explicit model (applies per-node attributes). */
    static JsonObject addNodesToModel(GraphModel gm, List<Map<String, Object>> nodes) {
        try {
            Graph g = gm.getGraph();
            int added = 0, skipped = 0;
            lockWrite(g);
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
                    Object attrsObj = nd.get("attributes");
                    if (attrsObj instanceof Map) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> attrs = (Map<String, Object>) attrsObj;
                        for (Map.Entry<String, Object> e : attrs.entrySet()) {
                            ensureColumnAndSet(gm.getNodeTable(), n, e.getKey(), e.getValue());
                        }
                    }
                    added++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("added", added);
                r.addProperty("skipped", skipped);
                return r;
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject removeNode(String id) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = getGraphController().getGraphModel(ws).getGraph();
            lockWrite(g);
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                int edgesRemoved = g.getDegree(n);
                g.removeNode(n);
                JsonObject r = success("Node removed");
                r.addProperty("edges_removed", edgesRemoved);
                return r;
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject bulkRemoveNodes(List<String> ids) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = getGraphController().getGraphModel(ws).getGraph();
            lockWrite(g);
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
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject queryNodes(String attr, String val, int limit, int offset) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            lockRead(g);
            try {
                JsonArray arr = new JsonArray();
                int count = 0, skip = 0;
                // toArray, not the live iterable: breaking out of an auto-locked
                // iterator before exhaustion leaks its read hold permanently.
                for (Node n : g.getNodes().toArray()) {
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

    public JsonObject getNode(String id) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            Node n = g.getNode(id);
            if (n == null) return error("Node not found: " + id);
            JsonObject o = new JsonObject();
            o.addProperty("id", n.getId().toString());
            o.addProperty("label", n.getLabel());
            o.addProperty("x", n.x());
            o.addProperty("y", n.y());
            o.addProperty("size", n.size());
            o.addProperty("r", (int)(n.r() * 255));
            o.addProperty("g", (int)(n.g() * 255));
            o.addProperty("b", (int)(n.b() * 255));
            JsonObject attrs = new JsonObject();
            for (Column col : gm.getNodeTable()) {
                if (col.isProperty()) continue;
                Object v = n.getAttribute(col);
                if (v == null) continue;
                if (v instanceof Number) attrs.addProperty(col.getTitle(), (Number) v);
                else if (v instanceof Boolean) attrs.addProperty(col.getTitle(), (Boolean) v);
                else attrs.addProperty(col.getTitle(), v.toString());
            }
            o.add("attributes", attrs);
            JsonObject r = new JsonObject();
            r.addProperty("success", true);
            r.add("node", o);
            return r;
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeLabel(String id, String label) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setLabel(label);
                return success("Label set");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodePosition(String id, float x, float y) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setX(x);
                n.setY(y);
                return success("Position set");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject batchSetPositions(List<Map<String, Object>> positions) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
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
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Edge Operations ─────────────────────────────────────────────

    public JsonObject addEdge(String src, String tgt, Double weight, boolean directed) {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        return addEdgeToModel(getGraphController().getGraphModel(ws), src, tgt, weight, directed);
    }

    /** Core edge-add against an explicit model. Type and directedness are kept consistent. */
    static JsonObject addEdgeToModel(GraphModel gm, String src, String tgt, Double weight, boolean directed) {
        try {
            Graph g = gm.getGraph();
            lockWrite(g);
            try {
                Node s = g.getNode(src), t = g.getNode(tgt);
                if (s == null) return error("Source not found: " + src);
                if (t == null) return error("Target not found: " + tgt);
                if (findEdge(g, s, t) != null) return error("Edge exists");
                Edge e = gm.factory().newEdge(s, t, directed ? 1 : 0, weight != null ? weight : 1.0, directed);
                g.addEdge(e);
                return success("Edge added");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject addEdges(List<Map<String, Object>> edges) {
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        return addEdgesToModel(getGraphController().getGraphModel(ws), edges);
    }

    /** Core batch edge-add against an explicit model (honors per-edge directed/label/attributes). */
    static JsonObject addEdgesToModel(GraphModel gm, List<Map<String, Object>> edges) {
        try {
            Graph g = gm.getGraph();
            int added = 0, skipped = 0;
            lockWrite(g);
            try {
                for (Map<String, Object> ed : edges) {
                    String src = (String) ed.get("source");
                    String tgt = (String) ed.get("target");
                    if (src == null || tgt == null) { skipped++; continue; }
                    Node s = g.getNode(src), t = g.getNode(tgt);
                    if (s == null || t == null || findEdge(g, s, t) != null) { skipped++; continue; }
                    Double w = ed.containsKey("weight") ? ((Number) ed.get("weight")).doubleValue() : 1.0;
                    boolean directed = !ed.containsKey("directed") || Boolean.TRUE.equals(ed.get("directed"));
                    Edge e = gm.factory().newEdge(s, t, directed ? 1 : 0, w, directed);
                    Object label = ed.get("label");
                    if (label != null) e.setLabel(label.toString());
                    g.addEdge(e);
                    Object attrsObj = ed.get("attributes");
                    if (attrsObj instanceof Map) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> attrs = (Map<String, Object>) attrsObj;
                        for (Map.Entry<String, Object> en : attrs.entrySet()) {
                            ensureColumnAndSet(gm.getEdgeTable(), e, en.getKey(), en.getValue());
                        }
                    }
                    added++;
                }
                JsonObject r = new JsonObject();
                r.addProperty("success", true);
                r.addProperty("added", added);
                r.addProperty("skipped", skipped);
                return r;
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject removeEdge(String source, String target) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                g.removeEdge(e);
                return success("Edge removed");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeWeight(String source, String target, double weight) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                e.setWeight(weight);
                return success("Weight set to " + weight);
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeLabel(String source, String target, String label) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph g = currentGraphModel().getGraph();
            lockWrite(g);
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                e.setLabel(label);
                return success("Edge label set");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject queryEdges(int limit, int offset) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Graph g = gm.getGraph();
            lockRead(g);
            try {
                JsonArray arr = new JsonArray();
                int count = 0, skip = 0;
                // toArray, not the live iterable: breaking out of an auto-locked
                // iterator before exhaustion leaks its read hold permanently.
                for (Edge e : g.getEdges().toArray()) {
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
            lockRead(g);
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
        Workspace ws = currentWorkspace();
        if (ws == null) return error("No project open");
        return addColumnToModel(currentGraphModel(), name, type, target);
    }

    /**
     * Add a column under the graph write lock. Taking the lock matters for ordering:
     * ensureColumnAndSet() also adds columns while holding the write lock, so doing it
     * lock-free here created an A-holds-graph/wants-column vs B-holds-column/wants-graph
     * deadlock under concurrent requests. Package-private + static for unit testing.
     */
    static JsonObject addColumnToModel(GraphModel gm, String name, String type, String target) {
        try {
            Table table = "edge".equalsIgnoreCase(target) ? gm.getEdgeTable() : gm.getNodeTable();
            Class<?> cls = typeStringToClass(type);
            if (cls == null) return error("Unknown type: " + type + ". Use: string, integer, double, float, boolean, long");
            Graph g = gm.getGraph();
            lockWrite(g);
            try {
                if (table.getColumn(name) != null) return error("Column already exists: " + name);
                table.addColumn(name, cls);
            } finally { unlockWrite(g); }
            return success("Column '" + name + "' added");
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeAttributes(String id, Map<String, Object> attrs) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            lockWrite(g);
            try {
                Node n = g.getNode(id);
                if (n == null) return error("Node not found: " + id);
                for (Map.Entry<String, Object> e : attrs.entrySet()) {
                    ensureColumnAndSet(gm.getNodeTable(), n, e.getKey(), e.getValue());
                }
                return success("Attributes set on node " + id);
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject batchSetNodeAttributes(List<Map<String, Object>> updates) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            lockWrite(g);
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
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeAttributes(String source, String target, Map<String, Object> attrs) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();
            lockWrite(g);
            try {
                Node s = g.getNode(source), t = g.getNode(target);
                if (s == null || t == null) return error("Node not found");
                Edge e = findEdge(g, s, t);
                if (e == null) return error("Edge not found");
                for (Map.Entry<String, Object> entry : attrs.entrySet()) {
                    ensureColumnAndSet(gm.getEdgeTable(), e, entry.getKey(), entry.getValue());
                }
                return success("Attributes set on edge");
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    static void ensureColumnAndSet(Table table, Object element, String key, Object value) {
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

    static Object convertToColumnType(Object value, Class<?> targetType) {
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

    static Class<?> typeStringToClass(String type) {
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
            lockWrite(graph);
            try {
                Node n = graph.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setColor(new Color(r, g, b, a));
                return success("Node color set");
            } finally { unlockWrite(graph); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setNodeSize(String id, float size) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            lockWrite(graph);
            try {
                Node n = graph.getNode(id);
                if (n == null) return error("Node not found: " + id);
                n.setSize(size);
                return success("Node size set to " + size);
            } finally { unlockWrite(graph); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject setEdgeColor(String source, String target, int r, int g, int b, int a) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph graph = currentGraphModel().getGraph();
                lockWrite(graph);
                try {
                    Node s = graph.getNode(source), t = graph.getNode(target);
                    if (s == null || t == null) return error("Node not found");
                    Edge e = findEdge(graph, s, t);
                    if (e == null) return error("Edge not found");
                    e.setColor(new Color(r, g, b, a));
                    return success("Edge color set");
                } finally { unlockWrite(graph); }
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject batchSetNodeColors(List<Map<String, Object>> nodeColors) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            Graph graph = currentGraphModel().getGraph();
            lockWrite(graph);
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
            } finally { unlockWrite(graph); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject resetAppearance(int r, int g, int b, float size) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph graph = currentGraphModel().getGraph();
                Color defaultColor = new Color(r, g, b);
                lockWrite(graph);
                try {
                    for (Node n : graph.getNodes().toArray()) {
                        n.setColor(defaultColor);
                        n.setSize(size);
                    }
                } finally { unlockWrite(graph); }
                return success("Appearance reset for all nodes");
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    // ─── Appearance: Color/Size by Attribute ─────────────────────────

    public JsonObject colorByPartition(String columnName, Map<String, int[]> colorMap) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
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
                    Node[] allNodes = graph.getNodes().toArray();
                    for (Node n : allNodes) {
                        Object v = n.getAttribute(col);
                        if (v != null) values.add(v.toString());
                    }

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

                int colored = 0;
                lockWrite(graph);
                try {
                    for (Node n : graph.getNodes().toArray()) {
                        Object v = n.getAttribute(col);
                        if (v != null) {
                            Color c = palette.get(v.toString());
                            if (c != null) {
                                n.setColor(c);
                                colored++;
                            }
                        }
                    }
                } finally { unlockWrite(graph); }
                JsonObject r = success("Colored " + colored + " nodes by " + columnName);
                r.addProperty("partitions", palette.size());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    /**
     * Min and max over the numeric values of {@code col}, as {@code [min, max]}, or null when
     * the column holds no numeric values. Seeded with infinities so a column whose values are
     * entirely negative ranks correctly — the old {@code Double.MIN_VALUE} seed (smallest
     * positive double) silently broke that case. Package-private + static for unit testing.
     */
    static double[] numericRange(Graph g, Column col) {
        double min = Double.POSITIVE_INFINITY, max = Double.NEGATIVE_INFINITY;
        lockRead(g);
        try {
            for (Node n : g.getNodes().toArray()) {
                Object v = n.getAttribute(col);
                if (v instanceof Number) {
                    double d = ((Number) v).doubleValue();
                    if (d < min) min = d;
                    if (d > max) max = d;
                }
            }
        } finally { g.readUnlock(); }
        return min == Double.POSITIVE_INFINITY ? null : new double[]{min, max};
    }

    /**
     * Column lookup for ranking operations. When a degree column is requested
     * before the degree statistic has run (the #1 cold-start stumble), computes
     * it on the spot instead of failing.
     */
    private Column resolveRankingColumn(GraphModel gm, String columnName) {
        Column col = gm.getNodeTable().getColumn(columnName);
        if (col == null && columnName != null) {
            String lc = columnName.toLowerCase();
            if (lc.equals("degree") || lc.equals("indegree") || lc.equals("outdegree")) {
                runStatistic("Degree", null);
                col = gm.getNodeTable().getColumn(columnName);
            }
        }
        return col;
    }

    private static JsonObject columnNotFound(String columnName) {
        return error("Column not found: " + columnName
            + " — compute the metric first (degree, pagerank, betweenness, modularity"
            + " via the statistics tools) or check the columns list");
    }

    public JsonObject colorByRanking(String columnName, int rMin, int gMin, int bMin, int rMax, int gMax, int bMax) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                GraphModel gm = currentGraphModel();
                Graph graph = gm.getGraph();
                Column col = resolveRankingColumn(gm, columnName);
                if (col == null) return columnNotFound(columnName);

                double[] mm = numericRange(graph, col);
                if (mm == null) return error("No numeric values in column " + columnName);
                double min = mm[0], max = mm[1];
                double range = max - min;
                if (range == 0) range = 1;

                int colored = 0;
                lockWrite(graph);
                try {
                    for (Node n : graph.getNodes().toArray()) {
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
                } finally { unlockWrite(graph); }
                JsonObject res = success("Colored " + colored + " nodes by ranking on " + columnName);
                res.addProperty("min_value", min);
                res.addProperty("max_value", max);
                return res;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject sizeByRanking(String columnName, float minSize, float maxSize) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                GraphModel gm = currentGraphModel();
                Graph graph = gm.getGraph();
                Column col = resolveRankingColumn(gm, columnName);
                if (col == null) return columnNotFound(columnName);

                double[] mm = numericRange(graph, col);
                if (mm == null) return error("No numeric values in column " + columnName);
                double min = mm[0], max = mm[1];
                double range = max - min;
                if (range == 0) range = 1;

                int sized = 0;
                lockWrite(graph);
                try {
                    for (Node n : graph.getNodes().toArray()) {
                        Object v = n.getAttribute(col);
                        if (v instanceof Number) {
                            double t = (((Number) v).doubleValue() - min) / range;
                            n.setSize((float)(minSize + t * (maxSize - minSize)));
                            sized++;
                        }
                    }
                } finally { unlockWrite(graph); }
                JsonObject res = success("Sized " + sized + " nodes by " + columnName);
                res.addProperty("min_value", min);
                res.addProperty("max_value", max);
                return res;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    // ─── Layout ──────────────────────────────────────────────────────

    public JsonObject runLayout(String algo, int iterations) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = getGraphController().getGraphModel(ws);
            Layout layout = findLayout(algo);
            if (layout == null) return error("Layout not found: " + algo);
            layout.setGraphModel(gm);
            final Layout fl = layout;
            final int iters = iterations > 0 ? iterations : 1000;
            if (!layoutRunning.compareAndSet(false, true)) return error("Layout already running");
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
            Layout layout = findLayout(algo);
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
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Layout layout = findLayout(algo);
            if (layout == null) return error("Layout not found: " + algo);
            layout.setGraphModel(gm);

            // Set properties
            if (properties != null) {
                LayoutProperty[] props = layout.getProperties();
                if (props != null) {
                    for (LayoutProperty prop : props) {
                        String canonicalName = prop.getCanonicalName() != null ? prop.getCanonicalName() : "";
                        String displayName = prop.getProperty().getDisplayName();
                        // Extract middle key from "AlgoName.propertyKey.name" pattern
                        String canonicalKey = "";
                        if (!canonicalName.isEmpty()) {
                            String[] parts = canonicalName.split("\\.");
                            if (parts.length >= 3) canonicalKey = parts[parts.length - 2];
                        }
                        Object val = properties.get(canonicalKey);
                        if (val == null && !canonicalName.isEmpty()) val = properties.get(canonicalName);
                        if (val == null) val = properties.get(displayName);
                        if (val == null) {
                            for (Map.Entry<String, Object> e : properties.entrySet()) {
                                String k = e.getKey();
                                if ((!canonicalKey.isEmpty() && k.equalsIgnoreCase(canonicalKey))
                                        || k.equalsIgnoreCase(displayName)
                                        || (!canonicalName.isEmpty() && k.equalsIgnoreCase(canonicalName))) {
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
            if (!layoutRunning.compareAndSet(false, true)) return error("Layout already running");
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

    static Object convertLayoutProperty(Object val, Class<?> type) {
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

    /**
     * Every statistic available in this Gephi instance — built-ins plus any
     * installed plugin that registers a StatisticsBuilder (verified with the
     * CWTS Leiden plugin). Names here are what /statistics/run accepts.
     */
    public JsonObject listStatistics() {
        JsonArray arr = new JsonArray();
        for (StatisticsBuilder sb : Lookup.getDefault().lookupAll(StatisticsBuilder.class)) {
            JsonObject o = new JsonObject();
            o.addProperty("name", sb.getName());
            try {
                o.addProperty("id", sb.getStatistics().getClass().getSimpleName());
            } catch (Throwable t) { /* name alone is enough */ }
            arr.add(o);
        }
        JsonObject r = new JsonObject();
        r.addProperty("success", true);
        r.add("statistics", arr);
        return r;
    }

    /** Run any available statistic by name — the plugin-ecosystem passthrough. */
    public JsonObject runStatisticByName(String name, Map<String, Object> params) {
        return runStatistic(name, params);
    }

    private static final org.gephi.utils.progress.ProgressTicket NOOP_TICKET =
        new org.gephi.utils.progress.ProgressTicket() {
            public void finish() {}
            public void finish(String s) {}
            public void progress() {}
            public void progress(int i) {}
            public void progress(String s) {}
            public void progress(String s, int i) {}
            public String getDisplayName() { return "MCP statistic"; }
            public void setDisplayName(String s) {}
            public void start() {}
            public void start(int i) {}
            public void switchToDeterminate(int i) {}
            public void switchToIndeterminate() {}
        };

    private JsonObject runStatistic(String builderName, Map<String, Object> params) {
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();

            // Find statistics builder by name
            StatisticsBuilder matchedBuilder = null;
            for (StatisticsBuilder sb : Lookup.getDefault().lookupAll(StatisticsBuilder.class)) {
                String name = sb.getName();
                LOGGER.fine("MCP: Found StatisticsBuilder: " + name + " (" + sb.getClass().getName() + ")");
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

            // Plugin statistics are often LongTasks that assume the UI gave them a
            // progress ticket and call it without null checks (e.g. CWTS Leiden).
            // Provide a no-op ticket so they run outside the statistics dialog.
            if (stat instanceof org.gephi.utils.longtask.spi.LongTask) {
                ((org.gephi.utils.longtask.spi.LongTask) stat).setProgressTicket(NOOP_TICKET);
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
                    Object converted = convertStatValue(value, paramType);
                    if (converted != null) m.invoke(obj, converted);
                    return;
                }
            }
            // No setter: plugin statistics (e.g. the CWTS Leiden plugin) often use
            // bare fields configured by their UI panel — set the field directly.
            for (Class<?> c = obj.getClass(); c != null && c != Object.class; c = c.getSuperclass()) {
                for (java.lang.reflect.Field f : c.getDeclaredFields()) {
                    if (f.getName().equalsIgnoreCase(setter)) {
                        Object converted = convertStatValue(value, f.getType());
                        if (converted != null) {
                            f.setAccessible(true);
                            f.set(obj, converted);
                        }
                        return;
                    }
                }
            }
        } catch (Exception e) {
            LOGGER.fine("Could not set " + methodName + ": " + e.getMessage());
        }
    }

    /** Value conversion for statistic parameters: layout-style primitives plus enums by name. */
    static Object convertStatValue(Object val, Class<?> type) {
        if (val != null && type.isEnum()) {
            String want = val.toString();
            for (Object ec : type.getEnumConstants()) {
                if (ec.toString().equalsIgnoreCase(want)) return ec;
            }
            return null;
        }
        return convertLayoutProperty(val, type);
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

    public JsonObject filterByDegreeRange(int minDegree, int maxDegree, boolean dryRun) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph g = currentGraphModel().getGraph();
                Node[] allNodes = g.getNodes().toArray();
                java.util.List<Node> toRemove = new java.util.ArrayList<>();
                for (Node n : allNodes) {
                    int deg = g.getDegree(n);
                    if (deg < minDegree || (maxDegree > 0 && deg > maxDegree)) {
                        toRemove.add(n);
                    }
                }
                if (dryRun) {
                    JsonObject r = success("Dry run: " + toRemove.size() + " nodes would be removed");
                    r.addProperty("would_remove", toRemove.size());
                    r.addProperty("would_remain", g.getNodeCount() - toRemove.size());
                    r.addProperty("dry_run", true);
                    return r;
                }
                lockWrite(g);
                try { for (Node n : toRemove) g.removeNode(n); }
                finally { unlockWrite(g); }
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                if (pc != null) pc.refreshPreview(ws);
                JsonObject r = success("Filtered by degree [" + minDegree + ", " + maxDegree + "]");
                r.addProperty("removed", toRemove.size());
                r.addProperty("remaining_nodes", g.getNodeCount());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject filterByEdgeWeight(double minWeight, double maxWeight, boolean dryRun) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph g = currentGraphModel().getGraph();
                Edge[] allEdges = g.getEdges().toArray();
                java.util.List<Edge> toRemove = new java.util.ArrayList<>();
                for (Edge e : allEdges) {
                    double w = e.getWeight();
                    if (w < minWeight || (maxWeight > 0 && w > maxWeight)) {
                        toRemove.add(e);
                    }
                }
                if (dryRun) {
                    JsonObject r = success("Dry run: " + toRemove.size() + " edges would be removed");
                    r.addProperty("would_remove", toRemove.size());
                    r.addProperty("would_remain", g.getEdgeCount() - toRemove.size());
                    r.addProperty("dry_run", true);
                    return r;
                }
                lockWrite(g);
                try { for (Edge e : toRemove) g.removeEdge(e); }
                finally { unlockWrite(g); }
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                if (pc != null) pc.refreshPreview(ws);
                JsonObject r = success("Filtered edges by weight [" + minWeight + ", " + maxWeight + "]");
                r.addProperty("removed", toRemove.size());
                r.addProperty("remaining_edges", g.getEdgeCount());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
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
                        } else if (val instanceof java.awt.Font) {
                            java.awt.Font f = (java.awt.Font) val;
                            String style = f.isBold() && f.isItalic() ? "BoldItalic" : f.isBold() ? "Bold" : f.isItalic() ? "Italic" : "Plain";
                            settings.addProperty(name, f.getFamily() + " " + f.getSize() + " " + style);
                        } else if (val instanceof EdgeColor) {
                            EdgeColor ec = (EdgeColor) val;
                            if (ec.getMode() == EdgeColor.Mode.ORIGINAL) settings.addProperty(name, "original");
                            else if (ec.getMode() == EdgeColor.Mode.MIXED) settings.addProperty(name, "mixed");
                            else if (ec.getCustomColor() != null) {
                                Color c = ec.getCustomColor();
                                settings.addProperty(name, String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()));
                            } else settings.addProperty(name, ec.getMode().toString().toLowerCase());
                        } else if (val instanceof DependantColor) {
                            DependantColor dc = (DependantColor) val;
                            if (dc.getMode() == DependantColor.Mode.PARENT) settings.addProperty(name, "parent");
                            else if (dc.getMode() == DependantColor.Mode.DARKER) settings.addProperty(name, "darker");
                            else if (dc.getCustomColor() != null) {
                                Color c = dc.getCustomColor();
                                settings.addProperty(name, String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()));
                            } else settings.addProperty(name, "parent");
                        } else if (val instanceof DependantOriginalColor) {
                            DependantOriginalColor doc = (DependantOriginalColor) val;
                            if (doc.getMode() == DependantOriginalColor.Mode.ORIGINAL) settings.addProperty(name, "original");
                            else if (doc.getMode() == DependantOriginalColor.Mode.PARENT) settings.addProperty(name, "parent");
                            else if (doc.getCustomColor() != null) {
                                Color c = doc.getCustomColor();
                                settings.addProperty(name, String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()));
                            } else settings.addProperty(name, "original");
                        } else {
                            settings.addProperty(name, val.toString());
                        }
                    }
                }

                // Include background color if not already captured by the main loop
                try {
                    Object bgVal = pm.getProperties().getValue("background.color");
                    if (bgVal instanceof Color) {
                        Color c = (Color) bgVal;
                        settings.addProperty("background.color", String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()));
                    }
                } catch (Exception ignored) {}

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

                    // Background color: store for PNG compositing and try to set on preview model
                    if ("background.color".equalsIgnoreCase(key) || "backgroundColor".equalsIgnoreCase(key)) {
                        try {
                            String hex = val.toString().trim();
                            if (hex.startsWith("#")) hex = hex.substring(1);
                            Color bgColor = new Color(Integer.parseInt(hex, 16));
                            exportBackgroundColor = bgColor;  // always store for exportPng compositing
                            PreviewProperty bgProp = pm.getProperties().getProperty("background.color");
                            if (bgProp != null) {
                                bgProp.setValue(bgColor);
                            } else {
                                pm.getProperties().putValue("background.color", bgColor);
                            }
                            set++;
                        } catch (NumberFormatException nfe) {
                            LOGGER.warning("MCP: Invalid background color: " + val);
                        }
                        continue;
                    }

                    PreviewProperty prop = pm.getProperties().getProperty(key);
                    if (prop != null) {
                        // Convert value based on property type
                        Class<?> type = prop.getType();
                        try {
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
                                // Parse font string like "Courier New 12 Bold" -> Font object
                                // Everything before first digit = name, first number = size, rest = style
                                String fontStr = val.toString().trim();
                                String name = "Arial";
                                int fontSize = 12;
                                int fontStyle = java.awt.Font.PLAIN;
                                int numStart = -1;
                                for (int ci = 0; ci < fontStr.length(); ci++) {
                                    if (Character.isDigit(fontStr.charAt(ci))) { numStart = ci; break; }
                                }
                                if (numStart > 0) {
                                    name = fontStr.substring(0, numStart).trim();
                                    String[] rest = fontStr.substring(numStart).trim().split("\\s+");
                                    try { fontSize = Integer.parseInt(rest[0]); } catch (NumberFormatException ignored) {}
                                    for (int pi = 1; pi < rest.length; pi++) {
                                        if ("Bold".equalsIgnoreCase(rest[pi])) fontStyle |= java.awt.Font.BOLD;
                                        else if ("Italic".equalsIgnoreCase(rest[pi])) fontStyle |= java.awt.Font.ITALIC;
                                    }
                                } else if (numStart < 0) {
                                    name = fontStr;
                                }
                                prop.setValue(new java.awt.Font(name, fontStyle, fontSize));
                            } else if (type == java.awt.Font.class) {
                                continue; // Non-string font value, skip
                            } else if (type == DependantColor.class && val instanceof String) {
                                String s = val.toString().trim().toLowerCase();
                                if ("parent".equals(s)) {
                                    prop.setValue(new DependantColor(DependantColor.Mode.PARENT));
                                } else if ("darker".equals(s)) {
                                    prop.setValue(new DependantColor(DependantColor.Mode.DARKER));
                                } else if (s.startsWith("#")) {
                                    prop.setValue(new DependantColor(new Color(Integer.parseInt(s.substring(1), 16))));
                                } else { continue; }
                            } else if (type == DependantOriginalColor.class && val instanceof String) {
                                String s = val.toString().trim().toLowerCase();
                                if ("parent".equals(s)) {
                                    prop.setValue(new DependantOriginalColor(DependantOriginalColor.Mode.PARENT));
                                } else if ("original".equals(s)) {
                                    prop.setValue(new DependantOriginalColor(DependantOriginalColor.Mode.ORIGINAL));
                                } else if (s.startsWith("#")) {
                                    prop.setValue(new DependantOriginalColor(new Color(Integer.parseInt(s.substring(1), 16))));
                                } else { continue; }
                            } else if (type == EdgeColor.class && val instanceof String) {
                                // For "source"/"target": color edges individually instead of using
                                // EdgeColor mode (which corrupts SVG rendering in Gephi 0.10)
                                String s = val.toString().trim().toLowerCase();
                                if ("source".equals(s) || "target".equals(s)) {
                                    boolean useSource = "source".equals(s);
                                    Graph graph = currentGraphModel().getGraph();
                                    Node[] graphNodes = graph.getNodes().toArray();
                                    Edge[] graphEdges = graph.getEdges().toArray();
                                    java.util.Map<Node, Color> nodeColors = new java.util.HashMap<>();
                                    for (Node n : graphNodes) nodeColors.put(n, n.getColor());
                                    for (Edge edge : graphEdges) {
                                        Node ref = useSource ? edge.getSource() : edge.getTarget();
                                        Color c = nodeColors.get(ref);
                                        if (c != null) edge.setColor(c);
                                    }
                                    prop.setValue(new EdgeColor(EdgeColor.Mode.ORIGINAL));
                                } else if ("mixed".equals(s)) {
                                    prop.setValue(new EdgeColor(EdgeColor.Mode.MIXED));
                                } else if ("original".equals(s)) {
                                    prop.setValue(new EdgeColor(EdgeColor.Mode.ORIGINAL));
                                } else if (s.startsWith("#")) {
                                    prop.setValue(new EdgeColor(new Color(Integer.parseInt(s.substring(1), 16))));
                                } else { continue; }
                            } else {
                                continue; // Skip unknown types
                            }
                            set++;
                        } catch (NumberFormatException nfe) {
                            LOGGER.warning("MCP: Invalid number/color value for " + key + ": " + val);
                            continue;
                        } catch (Exception ex) {
                            LOGGER.warning("MCP: Failed to set preview property " + key + ": " + ex.getMessage());
                            continue;
                        }
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

    /** GEXF export returned inline as a string — no file round-trip. */
    public JsonObject exportGexfContent() {
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
                java.io.StringWriter sw = new java.io.StringWriter();
                ec.exportWriter(sw, (org.gephi.io.exporter.spi.CharacterExporter) exporter);
                JsonObject r = success("GEXF exported inline");
                r.addProperty("content", sw.toString());
                return r;
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

                // Post-process: composite onto background color if one was set via setPreviewSettings.
                // Gephi's PNG exporter renders a transparent background; this fills it.
                Color bgColor = exportBackgroundColor;
                if (bgColor != null && !bgColor.equals(Color.WHITE)) {
                    BufferedImage exported = ImageIO.read(new File(filePath));
                    if (exported != null) {
                        BufferedImage result = new BufferedImage(exported.getWidth(), exported.getHeight(), BufferedImage.TYPE_INT_RGB);
                        Graphics2D g2d = result.createGraphics();
                        g2d.setColor(bgColor);
                        g2d.fillRect(0, 0, result.getWidth(), result.getHeight());
                        g2d.drawImage(exported, 0, 0, null);
                        g2d.dispose();
                        ImageIO.write(result, "PNG", new File(filePath));
                    }
                }

                return success("Exported to " + filePath);
            } catch (Exception e) { return error("Export failed: " + e.getMessage()); }
        });
    }

    public JsonObject exportPdf(String filePath, int w, int h) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph g = currentGraphModel().getGraph();
                if (g.getNodeCount() == 0) return error("Cannot export PDF: graph has no nodes");
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
            } catch (IllegalArgumentException e) {
                return error("Export failed: graph nodes may not be positioned — run a layout first");
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
            // Always use manual export — Gephi's built-in CSV exporter produces an adjacency matrix
            return exportCsvManual(filePath, separator, target);
        });
    }

    private JsonObject exportCsvManual(String filePath, String separator, String target) {
        try {
            String csvText = buildCsv(currentGraphModel(), separator, target);
            try (java.io.Writer fw = new java.io.OutputStreamWriter(
                    new java.io.FileOutputStream(filePath), java.nio.charset.StandardCharsets.UTF_8)) {
                fw.write(csvText);
            }
            return success("Exported to " + filePath);
        } catch (Exception e) {
            return error("CSV export failed: " + e.getMessage());
        }
    }

    /** Build node/edge CSV text from a model (RFC 4180 quoted). Package-private + static for unit testing. */
    static String buildCsv(GraphModel gm, String separator, String target) {
        Graph g = gm.getGraph();
        String sep = separator != null ? separator : ",";
        StringBuilder sb = new StringBuilder();
        {
            if (!"edges".equalsIgnoreCase(target)) {
                // Export nodes
                sb.append(csv("Id", sep)).append(sep).append(csv("Label", sep));
                for (Column col : gm.getNodeTable()) {
                    if (!col.isProperty()) sb.append(sep).append(csv(col.getTitle(), sep));
                }
                sb.append("\n");
                lockRead(g);
                try {
                    for (Node n : g.getNodes().toArray()) {
                        sb.append(csv(String.valueOf(n.getId()), sep)).append(sep)
                          .append(csv(n.getLabel() != null ? n.getLabel() : "", sep));
                        for (Column col : gm.getNodeTable()) {
                            if (!col.isProperty()) {
                                Object v = n.getAttribute(col);
                                sb.append(sep).append(csv(v != null ? v.toString() : "", sep));
                            }
                        }
                        sb.append("\n");
                    }
                } finally { g.readUnlock(); }
            }

            if ("edges".equalsIgnoreCase(target) || "both".equalsIgnoreCase(target)) {
                if (sb.length() > 0) sb.append("\n");
                sb.append(csv("Source", sep)).append(sep).append(csv("Target", sep)).append(sep).append(csv("Weight", sep));
                for (Column col : gm.getEdgeTable()) {
                    if (!col.isProperty()) sb.append(sep).append(csv(col.getTitle(), sep));
                }
                sb.append("\n");
                lockRead(g);
                try {
                    for (Edge e : g.getEdges().toArray()) {
                        sb.append(csv(String.valueOf(e.getSource().getId()), sep)).append(sep)
                          .append(csv(String.valueOf(e.getTarget().getId()), sep)).append(sep)
                          .append(csv(String.valueOf(e.getWeight()), sep));
                        for (Column col : gm.getEdgeTable()) {
                            if (!col.isProperty()) {
                                Object v = e.getAttribute(col);
                                sb.append(sep).append(csv(v != null ? v.toString() : "", sep));
                            }
                        }
                        sb.append("\n");
                    }
                } finally { g.readUnlock(); }
            }
        }
        return sb.toString();
    }

    /**
     * RFC 4180 field quoting: wrap the value in double quotes (doubling any internal
     * quote) when it contains the separator, a quote, or a line break. Without this,
     * a label or attribute containing the separator silently corrupts the columns.
     */
    static String csv(String value, String sep) {
        if (value == null) value = "";
        boolean needsQuote = value.contains(sep) || value.contains("\"")
                || value.contains("\n") || value.contains("\r");
        return needsQuote ? "\"" + value.replace("\"", "\"\"") + "\"" : value;
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

                Workspace importedWs = ic.process(c, processor, ws);

                // Cap imported node sizes to prevent viz:size from GEXF making nodes enormous
                Graph importedGraph = getGraphController().getGraphModel(ws).getGraph();
                Node[] importedNodes = importedGraph.getNodes().toArray();
                for (Node n : importedNodes) {
                    if (n.size() > 30.0f) n.setSize(30.0f);
                }

                Workspace effectiveWs = importedWs != null ? importedWs : ws;
                Graph g = getGraphController().getGraphModel(effectiveWs).getGraph();
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
            lockWrite(g);
            try {
                int nodeCount = g.getNodeCount();
                int edgeCount = g.getEdgeCount();
                g.clear();
                JsonObject r = success("Graph cleared");
                r.addProperty("nodes_removed", nodeCount);
                r.addProperty("edges_removed", edgeCount);
                return r;
            } finally { unlockWrite(g); }
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    public JsonObject removeIsolates() {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph g = currentGraphModel().getGraph();
                java.util.List<Node> isolates = new java.util.ArrayList<>();
                lockWrite(g);
                try {
                    for (Node n : g.getNodes().toArray()) {
                        if (g.getDegree(n) == 0) isolates.add(n);
                    }
                    for (Node n : isolates) g.removeNode(n);
                } finally { unlockWrite(g); }
                // Refresh preview so exports reflect the filtered graph (outside the lock)
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                if (pc != null) pc.refreshPreview(ws);
                JsonObject r = success("Removed " + isolates.size() + " isolated nodes");
                r.addProperty("removed", isolates.size());
                r.addProperty("remaining_nodes", g.getNodeCount());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject extractEgoNetwork(String nodeId, int depth) {
        return runOnEDT(() -> {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            try {
                Graph g = currentGraphModel().getGraph();
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
                    for (Node neighbor : g.getNeighbors(current).toArray()) {
                        if (!keep.contains(neighbor)) {
                            keep.add(neighbor);
                            queue.add(neighbor);
                            distances.put(neighbor, dist + 1);
                        }
                    }
                }

                // Remove nodes not in keep set
                java.util.List<Node> toRemove = new java.util.ArrayList<>();
                lockWrite(g);
                try {
                    for (Node n : g.getNodes().toArray()) {
                        if (!keep.contains(n)) toRemove.add(n);
                    }
                    for (Node n : toRemove) g.removeNode(n);
                } finally { unlockWrite(g); }

                // Refresh preview so exports reflect the filtered graph (outside the lock)
                PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                if (pc != null) pc.refreshPreview(ws);

                JsonObject r = success("Ego network extracted for " + nodeId);
                r.addProperty("kept_nodes", keep.size());
                r.addProperty("removed_nodes", toRemove.size());
                return r;
            } catch (Exception e) { return error("Failed: " + e.getMessage()); }
        });
    }

    public JsonObject extractGiantComponent() {
        // Statistics must run OFF the EDT (they dispatch UI work to EDT internally).
        // Only node removal and preview refresh need the EDT.
        try {
            Workspace ws = currentWorkspace();
            if (ws == null) return error("No project open");
            GraphModel gm = currentGraphModel();
            Graph g = gm.getGraph();

            // Run connected components (on HTTP thread, not EDT)
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
                for (Column col : gm.getNodeTable()) {
                    if (col.getTitle().toLowerCase().contains("component")) {
                        ccCol = col;
                        break;
                    }
                }
            }
            if (ccCol == null) return error("Component column not found after running statistics");

            // Count nodes per component
            java.util.Map<Integer, Integer> componentSizes = new java.util.HashMap<>();
            Node[] allNodes = g.getNodes().toArray();
            final Column fccCol = ccCol;
            for (Node n : allNodes) {
                Object v = n.getAttribute(fccCol);
                int comp = v instanceof Number ? ((Number) v).intValue() : 0;
                componentSizes.put(comp, componentSizes.getOrDefault(comp, 0) + 1);
            }

            int giantComp = 0;
            int giantSize = 0;
            for (java.util.Map.Entry<Integer, Integer> e : componentSizes.entrySet()) {
                if (e.getValue() > giantSize) {
                    giantSize = e.getValue();
                    giantComp = e.getKey();
                }
            }

            // Remove nodes on EDT (graph modification + preview refresh)
            final int gc = giantComp;
            final int gs = giantSize;
            final int compCount = componentSizes.size();
            return runOnEDT(() -> {
                try {
                    java.util.List<Node> toRemove = new java.util.ArrayList<>();
                    for (Node n : allNodes) {
                        Object v = n.getAttribute(fccCol);
                        int comp = v instanceof Number ? ((Number) v).intValue() : -1;
                        if (comp != gc) toRemove.add(n);
                    }
                    lockWrite(g);
                    try { for (Node n : toRemove) g.removeNode(n); }
                    finally { unlockWrite(g); }
                    PreviewController pc = Lookup.getDefault().lookup(PreviewController.class);
                    if (pc != null) pc.refreshPreview(ws);
                    JsonObject r = success("Giant component extracted");
                    r.addProperty("kept_nodes", gs);
                    r.addProperty("removed_nodes", toRemove.size());
                    r.addProperty("component_count", compCount);
                    return r;
                } catch (Exception e) { return error("Failed: " + e.getMessage()); }
            });
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
            Graph g = gm.getGraph();
            // setVisibleView() takes Gephi's own blocking write lock; hold our deadlock-safe
            // lock first so that call re-enters instead of queuing behind the renderer.
            lockWrite(g);
            try {
                gm.setVisibleView(null);
            } finally { unlockWrite(g); }
            return success("Filters reset - full graph view restored");
        } catch (Exception e) { return error("Failed: " + e.getMessage()); }
    }

    // ─── Shutdown ────────────────────────────────────────────────────

    public void shutdown() {
        layoutRunning.set(false);
        layoutExecutor.shutdownNow();
    }

    /**
     * Cheap wedge detector for /health: try the graph read lock briefly.
     * "ok" = acquired instantly; "busy" = could not acquire (a writer is parked or
     * the renderer is saturating the lock — if persistent, Gephi needs a restart);
     * "none" = no workspace open.
     */
    public String graphLockProbe() {
        try {
            GraphModel gm = currentGraphModel();
            if (gm == null) return "none";
            Graph g = gm.getGraph();
            java.util.concurrent.locks.ReentrantReadWriteLock.ReadLock rl = readLockHandle(g);
            if (rl == null) return "unknown";
            if (rl.tryLock(150, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                rl.unlock();
                return "ok";
            }
            return "busy";
        } catch (Throwable t) {
            return "unknown";
        }
    }

    /**
     * Live counters from the underlying ReentrantReadWriteLock: active read holds,
     * write-locked flag, and queued threads. Diagnostic companion to graphLockProbe;
     * a nonzero reader count while Gephi is idle means a leaked read hold (the
     * precursor of a permanent wedge). All values -1 when unreachable.
     */
    public JsonObject graphLockStats() {
        JsonObject o = new JsonObject();
        o.addProperty("readers", -1);
        o.addProperty("write_locked", false);
        o.addProperty("queued", -1);
        try {
            GraphModel gm = currentGraphModel();
            if (gm == null) return o;
            org.gephi.graph.api.GraphLock lock = gm.getGraph().getLock();
            if (lock == null) return o;
            java.lang.reflect.Field f = lock.getClass().getDeclaredField("readWriteLock");
            f.setAccessible(true);
            Object v = f.get(lock);
            if (v instanceof java.util.concurrent.locks.ReentrantReadWriteLock) {
                java.util.concurrent.locks.ReentrantReadWriteLock rwl =
                    (java.util.concurrent.locks.ReentrantReadWriteLock) v;
                o.addProperty("readers", rwl.getReadLockCount());
                o.addProperty("write_locked", rwl.isWriteLocked());
                o.addProperty("queued", rwl.getQueueLength());
            }
        } catch (Throwable t) {
            // leave the -1 defaults
        }
        return o;
    }

    // ─── View / camera control (teaching mode) ──────────────────────────

    /**
     * Direct the human viewer's attention in the Gephi window: center the camera on
     * the graph, a node, an edge, or a region; optionally select nodes (visual
     * highlight) and set zoom. No-op modes never touch the graph write lock.
     */
    public JsonObject focusView(String mode, String nodeId, String source, String target,
                                Double x, Double y, Double w, Double h,
                                Double zoom, java.util.List<String> select) {
        org.gephi.visualization.api.VisualizationController vc =
            Lookup.getDefault().lookup(org.gephi.visualization.api.VisualizationController.class);
        if (vc == null) return error("No visualization available (headless or view not started)");
        GraphModel gm = currentGraphModel();
        if (gm == null) return error("No workspace open");
        Graph g = gm.getGraph();
        try {
            String m = mode == null ? "graph" : mode.toLowerCase();
            switch (m) {
                case "graph":
                    vc.centerOnGraph();
                    break;
                case "zero":
                    vc.centerOnZero();
                    break;
                case "node": {
                    if (nodeId == null) return error("Missing 'id' for mode=node");
                    Node n = g.getNode(nodeId);
                    if (n == null) return error("Node not found: " + nodeId);
                    vc.centerOnNode(n);
                    break;
                }
                case "edge": {
                    if (source == null || target == null) return error("Missing 'source'/'target' for mode=edge");
                    Node ns = g.getNode(source), nt = g.getNode(target);
                    if (ns == null || nt == null) return error("Edge endpoints not found");
                    Edge e = g.getEdge(ns, nt, 1);  // directed
                    if (e == null) e = g.getEdge(ns, nt, 0);  // undirected
                    if (e == null) e = g.getEdge(ns, nt);  // default
                    if (e == null) e = g.getEdge(nt, ns, 1);
                    if (e == null) e = g.getEdge(nt, ns, 0);
                    if (e == null) e = g.getEdge(nt, ns);
                    if (e == null) return error("Edge not found: " + source + " -> " + target);
                    vc.centerOnEdge(e);
                    break;
                }
                case "region": {
                    if (x == null || y == null || w == null || h == null)
                        return error("Missing x/y/w/h for mode=region");
                    vc.centerOn(x.floatValue(), y.floatValue(), w.floatValue(), h.floatValue());
                    break;
                }
                default:
                    return error("Unknown mode: " + mode + " (use graph|zero|node|edge|region)");
            }
            if (select != null) {
                if (select.isEmpty()) {
                    vc.resetSelection();
                } else {
                    java.util.List<Node> nodes = new java.util.ArrayList<>();
                    for (String id : select) {
                        Node n = g.getNode(id);
                        if (n != null) nodes.add(n);
                    }
                    vc.selectNodes(nodes.toArray(new Node[0]));
                }
            }
            if (zoom != null) vc.setZoom(zoom.floatValue());
            JsonObject r = success("View focused (" + m + ")");
            r.addProperty("mode", m);
            if (select != null) r.addProperty("selected", select.size());
            return r;
        } catch (Exception e) {
            return error("Focus failed: " + e.getMessage());
        }
    }

}
