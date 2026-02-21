package org.gephi.plugins.mcp.api;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fi.iki.elonen.NanoHTTPD;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.gephi.plugins.mcp.service.GephiControlService;

public class GephiAPIServer extends NanoHTTPD {

    private static final Logger LOGGER = Logger.getLogger(GephiAPIServer.class.getName());
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private final GephiControlService service;

    public GephiAPIServer(int port) {
        super("127.0.0.1", port);
        this.service = GephiControlService.getInstance();
    }

    @Override
    public Response serve(IHTTPSession session) {
        String uri = session.getUri();
        Method method = session.getMethod();

        LOGGER.info("MCP API: " + method + " " + uri);

        if (Method.OPTIONS.equals(method)) {
            Response response = newFixedLengthResponse(Response.Status.OK, "text/plain", "");
            addCorsHeaders(response);
            return response;
        }

        try {
            JsonObject requestBody = null;
            if (Method.POST.equals(method) || Method.PUT.equals(method)) {
                Map<String, String> files = new HashMap<>();
                session.parseBody(files);
                String body = files.get("postData");
                if (body != null && !body.isEmpty()) {
                    requestBody = JsonParser.parseString(body).getAsJsonObject();
                }
            }

            JsonObject result = routeRequest(uri, method, session.getParms(), requestBody);

            Response.Status status = result.has("success") && result.get("success").getAsBoolean()
                ? Response.Status.OK : Response.Status.BAD_REQUEST;

            Response response = newFixedLengthResponse(status, "application/json", GSON.toJson(result));
            addCorsHeaders(response);
            return response;

        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "API error", e);
            JsonObject error = new JsonObject();
            error.addProperty("success", false);
            error.addProperty("error", e.getMessage());
            Response response = newFixedLengthResponse(Response.Status.INTERNAL_ERROR, "application/json", GSON.toJson(error));
            addCorsHeaders(response);
            return response;
        }
    }

    @SuppressWarnings("unchecked")
    private JsonObject routeRequest(String uri, Method method, Map<String, String> params, JsonObject body) {

        // ─── Health ──────────────────────────────────────────────────

        if ("/health".equals(uri) || "/".equals(uri)) {
            JsonObject result = new JsonObject();
            result.addProperty("success", true);
            result.addProperty("service", "Gephi MCP API");
            result.addProperty("version", "2.0.0");
            result.addProperty("status", "running");
            return result;
        }

        // ─── Project ─────────────────────────────────────────────────

        if ("/project/new".equals(uri) && Method.POST.equals(method)) {
            String name = body != null && body.has("name") ? body.get("name").getAsString() : "New Project";
            return service.createProject(name);
        }

        if ("/project/open".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file' parameter");
            return service.openProject(body.get("file").getAsString());
        }

        if ("/project/save".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file' parameter");
            return service.saveProject(body.get("file").getAsString());
        }

        if ("/project/info".equals(uri) && Method.GET.equals(method)) {
            return service.getProjectInfo();
        }

        // ─── Workspace ───────────────────────────────────────────────

        if ("/workspace/new".equals(uri) && Method.POST.equals(method)) {
            return service.newWorkspace();
        }

        if ("/workspace/list".equals(uri) && Method.GET.equals(method)) {
            return service.listWorkspaces();
        }

        if ("/workspace/switch".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("index")) return errorResult("Missing 'index'");
            return service.switchWorkspace(body.get("index").getAsInt());
        }

        if ("/workspace/delete".equals(uri) && Method.DELETE.equals(method)) {
            int index = params.containsKey("index") ? Integer.parseInt(params.get("index")) : -1;
            if (index < 0 && body != null && body.has("index")) index = body.get("index").getAsInt();
            if (index < 0) return errorResult("Missing 'index'");
            return service.deleteWorkspace(index);
        }

        // ─── Nodes ───────────────────────────────────────────────────

        if ("/graph/node/add".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id")) return errorResult("Missing 'id' parameter");
            String id = body.get("id").getAsString();
            String label = body.has("label") ? body.get("label").getAsString() : null;
            Map<String, Object> attrs = null;
            if (body.has("attributes") && body.get("attributes").isJsonObject()) {
                attrs = GSON.fromJson(body.get("attributes"), Map.class);
            }
            return service.addNode(id, label, attrs);
        }

        if ("/graph/nodes/add".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("nodes")) return errorResult("Missing 'nodes' array");
            List<Map<String, Object>> nodes = GSON.fromJson(body.get("nodes"), List.class);
            return service.addNodes(nodes);
        }

        if (uri.startsWith("/graph/node/") && uri.length() > "/graph/node/".length() && Method.DELETE.equals(method)) {
            String nodeId = uri.substring("/graph/node/".length());
            if (nodeId.isEmpty()) return errorResult("Missing node ID");
            return service.removeNode(nodeId);
        }

        if ("/graph/nodes/remove".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("ids")) return errorResult("Missing 'ids' array");
            List<String> ids = GSON.fromJson(body.get("ids"), List.class);
            return service.bulkRemoveNodes(ids);
        }

        if ("/graph/nodes".equals(uri) && Method.GET.equals(method)) {
            int limit = parseIntParam(params.get("limit"), 100);
            int offset = parseIntParam(params.get("offset"), 0);
            return service.queryNodes(null, null, limit, offset);
        }

        if ("/graph/node/label".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id") || !body.has("label")) return errorResult("Missing 'id' or 'label'");
            return service.setNodeLabel(body.get("id").getAsString(), body.get("label").getAsString());
        }

        if ("/graph/node/position".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id")) return errorResult("Missing 'id'");
            float x = body.has("x") ? body.get("x").getAsFloat() : 0;
            float y = body.has("y") ? body.get("y").getAsFloat() : 0;
            return service.setNodePosition(body.get("id").getAsString(), x, y);
        }

        if ("/graph/nodes/positions".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("positions")) return errorResult("Missing 'positions' array");
            List<Map<String, Object>> positions = GSON.fromJson(body.get("positions"), List.class);
            return service.batchSetPositions(positions);
        }

        // ─── Edges ───────────────────────────────────────────────────

        if ("/graph/edge/add".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target"))
                return errorResult("Missing 'source' or 'target'");
            String source = body.get("source").getAsString();
            String target = body.get("target").getAsString();
            Double weight = body.has("weight") ? body.get("weight").getAsDouble() : 1.0;
            boolean directed = !body.has("directed") || body.get("directed").getAsBoolean();
            return service.addEdge(source, target, weight, directed);
        }

        if ("/graph/edges/add".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("edges")) return errorResult("Missing 'edges' array");
            List<Map<String, Object>> edges = GSON.fromJson(body.get("edges"), List.class);
            return service.addEdges(edges);
        }

        if ("/graph/edge/remove".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target"))
                return errorResult("Missing 'source' or 'target'");
            return service.removeEdge(body.get("source").getAsString(), body.get("target").getAsString());
        }

        if ("/graph/edge/weight".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target") || !body.has("weight"))
                return errorResult("Missing 'source', 'target', or 'weight'");
            return service.setEdgeWeight(
                body.get("source").getAsString(),
                body.get("target").getAsString(),
                body.get("weight").getAsDouble()
            );
        }

        if ("/graph/edge/label".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target") || !body.has("label"))
                return errorResult("Missing 'source', 'target', or 'label'");
            return service.setEdgeLabel(
                body.get("source").getAsString(),
                body.get("target").getAsString(),
                body.get("label").getAsString()
            );
        }

        if ("/graph/edges".equals(uri) && Method.GET.equals(method)) {
            int limit = parseIntParam(params.get("limit"), 100);
            int offset = parseIntParam(params.get("offset"), 0);
            return service.queryEdges(limit, offset);
        }

        // ─── Graph Stats & Type ──────────────────────────────────────

        if ("/graph/stats".equals(uri) && Method.GET.equals(method)) {
            return service.getGraphStats();
        }

        if ("/graph/type".equals(uri) && Method.GET.equals(method)) {
            return service.getGraphType();
        }

        // ─── Attributes / Columns ────────────────────────────────────

        if ("/graph/columns".equals(uri) && Method.GET.equals(method)) {
            String target = params.getOrDefault("target", "node");
            return service.getColumns(target);
        }

        if ("/graph/columns/add".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("name") || !body.has("type"))
                return errorResult("Missing 'name' or 'type'");
            String target = body.has("target") ? body.get("target").getAsString() : "node";
            return service.addColumn(body.get("name").getAsString(), body.get("type").getAsString(), target);
        }

        if ("/graph/node/attributes".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id") || !body.has("attributes"))
                return errorResult("Missing 'id' or 'attributes'");
            Map<String, Object> attrs = GSON.fromJson(body.get("attributes"), Map.class);
            return service.setNodeAttributes(body.get("id").getAsString(), attrs);
        }

        if ("/graph/nodes/attributes".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("updates")) return errorResult("Missing 'updates' array");
            List<Map<String, Object>> updates = GSON.fromJson(body.get("updates"), List.class);
            return service.batchSetNodeAttributes(updates);
        }

        if ("/graph/edge/attributes".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target") || !body.has("attributes"))
                return errorResult("Missing 'source', 'target', or 'attributes'");
            Map<String, Object> attrs = GSON.fromJson(body.get("attributes"), Map.class);
            return service.setEdgeAttributes(
                body.get("source").getAsString(),
                body.get("target").getAsString(),
                attrs
            );
        }

        // ─── Appearance ──────────────────────────────────────────────

        if ("/appearance/node/color".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id")) return errorResult("Missing 'id'");
            int r = body.has("r") ? body.get("r").getAsInt() : 0;
            int g = body.has("g") ? body.get("g").getAsInt() : 0;
            int b = body.has("b") ? body.get("b").getAsInt() : 0;
            int a = body.has("a") ? body.get("a").getAsInt() : 255;
            return service.setNodeColor(body.get("id").getAsString(), r, g, b, a);
        }

        if ("/appearance/node/size".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("id") || !body.has("size")) return errorResult("Missing 'id' or 'size'");
            return service.setNodeSize(body.get("id").getAsString(), body.get("size").getAsFloat());
        }

        if ("/appearance/edge/color".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("source") || !body.has("target"))
                return errorResult("Missing 'source' or 'target'");
            int r = body.has("r") ? body.get("r").getAsInt() : 0;
            int g = body.has("g") ? body.get("g").getAsInt() : 0;
            int b = body.has("b") ? body.get("b").getAsInt() : 0;
            int a = body.has("a") ? body.get("a").getAsInt() : 255;
            return service.setEdgeColor(body.get("source").getAsString(), body.get("target").getAsString(), r, g, b, a);
        }

        if ("/appearance/nodes/color".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("nodes")) return errorResult("Missing 'nodes' array");
            List<Map<String, Object>> nodes = GSON.fromJson(body.get("nodes"), List.class);
            return service.batchSetNodeColors(nodes);
        }

        if ("/appearance/reset".equals(uri) && Method.POST.equals(method)) {
            int r = body != null && body.has("r") ? body.get("r").getAsInt() : 153;
            int g = body != null && body.has("g") ? body.get("g").getAsInt() : 153;
            int b = body != null && body.has("b") ? body.get("b").getAsInt() : 153;
            float size = body != null && body.has("size") ? body.get("size").getAsFloat() : 10f;
            return service.resetAppearance(r, g, b, size);
        }

        if ("/appearance/partition/color".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("column")) return errorResult("Missing 'column'");
            String column = body.get("column").getAsString();
            Map<String, int[]> colorMap = null;
            if (body.has("colors") && body.get("colors").isJsonObject()) {
                colorMap = new HashMap<>();
                JsonObject colors = body.getAsJsonObject("colors");
                for (String key : colors.keySet()) {
                    List<Number> rgb = GSON.fromJson(colors.get(key), List.class);
                    colorMap.put(key, new int[]{rgb.get(0).intValue(), rgb.get(1).intValue(), rgb.get(2).intValue()});
                }
            }
            return service.colorByPartition(column, colorMap);
        }

        if ("/appearance/ranking/color".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("column")) return errorResult("Missing 'column'");
            String column = body.get("column").getAsString();
            int rMin = body.has("r_min") ? body.get("r_min").getAsInt() : 255;
            int gMin = body.has("g_min") ? body.get("g_min").getAsInt() : 255;
            int bMin = body.has("b_min") ? body.get("b_min").getAsInt() : 200;
            int rMax = body.has("r_max") ? body.get("r_max").getAsInt() : 255;
            int gMax = body.has("g_max") ? body.get("g_max").getAsInt() : 0;
            int bMax = body.has("b_max") ? body.get("b_max").getAsInt() : 0;
            return service.colorByRanking(column, rMin, gMin, bMin, rMax, gMax, bMax);
        }

        if ("/appearance/ranking/size".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("column")) return errorResult("Missing 'column'");
            float minSize = body.has("min_size") ? body.get("min_size").getAsFloat() : 5f;
            float maxSize = body.has("max_size") ? body.get("max_size").getAsFloat() : 50f;
            return service.sizeByRanking(body.get("column").getAsString(), minSize, maxSize);
        }

        // ─── Layout ──────────────────────────────────────────────────

        if ("/layout/run".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("algorithm")) return errorResult("Missing 'algorithm'");
            String algo = body.get("algorithm").getAsString();
            int iterations = body.has("iterations") ? body.get("iterations").getAsInt() : 1000;
            // Check if properties are provided - use setLayoutProperties for that
            if (body.has("properties") && body.get("properties").isJsonObject()) {
                Map<String, Object> properties = GSON.fromJson(body.get("properties"), Map.class);
                return service.setLayoutProperties(algo, properties, iterations);
            }
            return service.runLayout(algo, iterations);
        }

        if ("/layout/stop".equals(uri) && Method.POST.equals(method)) {
            return service.stopLayout();
        }

        if ("/layout/status".equals(uri) && Method.GET.equals(method)) {
            return service.getLayoutStatus();
        }

        if ("/layout/available".equals(uri) && Method.GET.equals(method)) {
            return service.getAvailableLayouts();
        }

        if ("/layout/properties".equals(uri) && Method.GET.equals(method)) {
            String algo = params.get("algorithm");
            if (algo == null || algo.isEmpty()) return errorResult("Missing 'algorithm' parameter");
            return service.getLayoutProperties(algo);
        }

        if ("/layout/properties".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("algorithm") || !body.has("properties"))
                return errorResult("Missing 'algorithm' or 'properties'");
            String algo = body.get("algorithm").getAsString();
            Map<String, Object> properties = GSON.fromJson(body.get("properties"), Map.class);
            int iterations = body.has("iterations") ? body.get("iterations").getAsInt() : 1000;
            return service.setLayoutProperties(algo, properties, iterations);
        }

        // ─── Statistics ──────────────────────────────────────────────

        if ("/statistics/modularity".equals(uri) && Method.POST.equals(method)) {
            double res = body != null && body.has("resolution") ? body.get("resolution").getAsDouble() : 1.0;
            return service.computeModularity(res);
        }

        if ("/statistics/degree".equals(uri) && Method.POST.equals(method)) {
            return service.computeDegree();
        }

        if ("/statistics/betweenness".equals(uri) && Method.POST.equals(method)) {
            return service.computeBetweenness();
        }

        if ("/statistics/pagerank".equals(uri) && Method.POST.equals(method)) {
            return service.computePageRank();
        }

        if ("/statistics/connected-components".equals(uri) && Method.POST.equals(method)) {
            return service.computeConnectedComponents();
        }

        if ("/statistics/clustering-coefficient".equals(uri) && Method.POST.equals(method)) {
            return service.computeClusteringCoefficient();
        }

        if ("/statistics/avg-path-length".equals(uri) && Method.POST.equals(method)) {
            return service.computeAvgPathLength();
        }

        if ("/statistics/hits".equals(uri) && Method.POST.equals(method)) {
            return service.computeHITS();
        }

        if ("/statistics/eigenvector".equals(uri) && Method.POST.equals(method)) {
            return service.computeEigenvectorCentrality();
        }

        // ─── Graph Operations ────────────────────────────────────────

        if ("/graph/clear".equals(uri) && Method.POST.equals(method)) {
            return service.clearGraph();
        }

        // ─── Filters ─────────────────────────────────────────────────

        if ("/filter/degree".equals(uri) && Method.POST.equals(method)) {
            int min = body != null && body.has("min") ? body.get("min").getAsInt() : 0;
            int max = body != null && body.has("max") ? body.get("max").getAsInt() : 0;
            return service.filterByDegreeRange(min, max);
        }

        if ("/filter/edge-weight".equals(uri) && Method.POST.equals(method)) {
            double min = body != null && body.has("min") ? body.get("min").getAsDouble() : 0;
            double max = body != null && body.has("max") ? body.get("max").getAsDouble() : 0;
            return service.filterByEdgeWeight(min, max);
        }

        if ("/filter/remove-isolates".equals(uri) && Method.POST.equals(method)) {
            return service.removeIsolates();
        }

        if ("/filter/ego-network".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("node_id")) return errorResult("Missing 'node_id'");
            String nodeId = body.get("node_id").getAsString();
            int depth = body.has("depth") ? body.get("depth").getAsInt() : 1;
            return service.extractEgoNetwork(nodeId, depth);
        }

        if ("/filter/giant-component".equals(uri) && Method.POST.equals(method)) {
            return service.extractGiantComponent();
        }

        if ("/filter/reset".equals(uri) && Method.POST.equals(method)) {
            return service.resetFilters();
        }

        // ─── Edge Appearance ────────────────────────────────────────

        if ("/appearance/edge/thickness-by-weight".equals(uri) && Method.POST.equals(method)) {
            float minThickness = body != null && body.has("min_thickness") ? body.get("min_thickness").getAsFloat() : 1f;
            float maxThickness = body != null && body.has("max_thickness") ? body.get("max_thickness").getAsFloat() : 5f;
            return service.setEdgeThicknessByWeight(minThickness, maxThickness);
        }

        // ─── Preview ─────────────────────────────────────────────────

        if ("/preview/settings".equals(uri) && Method.GET.equals(method)) {
            return service.getPreviewSettings();
        }

        if ("/preview/settings".equals(uri) && Method.POST.equals(method)) {
            if (body == null) return errorResult("Missing request body");
            Map<String, Object> settings = GSON.fromJson(body, Map.class);
            return service.setPreviewSettings(settings);
        }

        // ─── Export ──────────────────────────────────────────────────

        if ("/export/gexf".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.exportGexf(body.get("file").getAsString());
        }

        if ("/export/png".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            String file = body.get("file").getAsString();
            int w = body.has("width") ? body.get("width").getAsInt() : 1920;
            int h = body.has("height") ? body.get("height").getAsInt() : 1080;
            return service.exportPng(file, w, h);
        }

        if ("/export/pdf".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            String file = body.get("file").getAsString();
            int w = body.has("width") ? body.get("width").getAsInt() : 0;
            int h = body.has("height") ? body.get("height").getAsInt() : 0;
            return service.exportPdf(file, w, h);
        }

        if ("/export/svg".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.exportSvg(body.get("file").getAsString());
        }

        if ("/export/graphml".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.exportGraphml(body.get("file").getAsString());
        }

        if ("/export/csv".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            String file = body.get("file").getAsString();
            String separator = body.has("separator") ? body.get("separator").getAsString() : ",";
            String target = body.has("target") ? body.get("target").getAsString() : "nodes";
            return service.exportCsv(file, separator, target);
        }

        // ─── Import ──────────────────────────────────────────────────

        if ("/import/gexf".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.importFile(body.get("file").getAsString());
        }

        if ("/import/graphml".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.importFile(body.get("file").getAsString());
        }

        if ("/import/csv".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.importFile(body.get("file").getAsString());
        }

        if ("/import/file".equals(uri) && Method.POST.equals(method)) {
            if (body == null || !body.has("file")) return errorResult("Missing 'file'");
            return service.importFile(body.get("file").getAsString());
        }

        return errorResult("Unknown endpoint: " + method + " " + uri);
    }

    private int parseIntParam(String value, int defaultValue) {
        if (value == null) return defaultValue;
        try { return Integer.parseInt(value); }
        catch (NumberFormatException e) { return defaultValue; }
    }

    private JsonObject errorResult(String message) {
        JsonObject result = new JsonObject();
        result.addProperty("success", false);
        result.addProperty("error", message);
        return result;
    }

    private void addCorsHeaders(Response response) {
        response.addHeader("Access-Control-Allow-Origin", "*");
        response.addHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        response.addHeader("Access-Control-Allow-Headers", "Content-Type");
    }

    public void startServer() throws IOException {
        start(NanoHTTPD.SOCKET_READ_TIMEOUT, false);
        LOGGER.info("Gephi MCP API started on http://127.0.0.1:" + getListeningPort());
    }

    public void stopServer() {
        stop();
        service.shutdown();
        LOGGER.info("Gephi MCP API stopped");
    }
}
