/*
 * Copyright 2026 Matt Artz
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.gephi.plugins.mcp.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import java.util.List;
import java.util.Map;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphController;
import org.gephi.graph.api.GraphModel;
import org.gephi.graph.api.Node;
import org.gephi.project.api.ProjectController;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.openide.util.Lookup;

/** Column tidy-up, time from columns, and combined filters on a small known network. */
class DataToolsTest {

    private final GephiControlService service = GephiControlService.getInstance();
    private GraphModel gm;

    /**
     * A path a-b-c-d plus e joined to a, b and c: degrees a2 b3 c3 d1 e3. Each node has a
     * group (x for a, b, e; y for c, d), a score as text, and a joining year.
     */
    @BeforeEach
    void network() {
        ProjectController pc = Lookup.getDefault().lookup(ProjectController.class);
        pc.closeCurrentProject();
        pc.newProject();
        gm = Lookup.getDefault().lookup(GraphController.class).getGraphModel();
        gm.getNodeTable().addColumn("group", String.class);
        gm.getNodeTable().addColumn("score", String.class);
        gm.getNodeTable().addColumn("joined", Integer.class);
        Graph g = gm.getUndirectedGraph();
        Object[][] rows = {{"a", "x", "1.5", 1990}, {"b", "x", "oops", 1994}, {"c", "y", null, 1998},
                           {"d", "y", "4", 1999}, {"e", "x", "2", 1991}};
        for (Object[] row : rows) {
            Node n = gm.factory().newNode(row[0]);
            n.setAttribute("group", row[1]);
            if (row[2] != null) n.setAttribute("score", row[2]);
            n.setAttribute("joined", row[3]);
            g.addNode(n);
        }
        String[][] edges = {{"a", "b"}, {"b", "c"}, {"c", "d"}, {"e", "a"}, {"e", "b"}, {"e", "c"}};
        for (String[] e : edges) {
            g.addEdge(gm.factory().newEdge(g.getNode(e[0]), g.getNode(e[1]), false));
        }
    }

    private Object value(String node, String column) {
        return gm.getGraph().getNode(node).getAttribute(GephiControlService.findColumn(gm.getNodeTable(), column));
    }

    @Test
    void convertingReportsTheValuesItCouldNotRead() {
        JsonObject r = service.editColumn("node", "score", "convert", null, "double", null);

        assertTrue(r.get("success").getAsBoolean(), r.toString());
        assertEquals(1, r.get("values_lost").getAsInt(), "'oops' is not a number");
        assertEquals(1.5, value("a", "score"));
        assertNull(value("b", "score"));
    }

    @Test
    void fillingEmptyCellsLeavesFilledOnesAlone() {
        JsonObject r = service.editColumn("node", "score", "fill_empty", "0", null, null);

        assertEquals(1, r.get("filled").getAsInt(), r.toString());
        assertEquals("0", value("c", "score"));
        assertEquals("oops", value("b", "score"));
    }

    @Test
    void renamingKeepsTheValues() {
        service.editColumn("node", "group", "rename", null, null, "Team");

        assertNull(GephiControlService.findColumn(gm.getNodeTable(), "group"));
        assertEquals("y", value("d", "Team"));
    }

    @Test
    void gephisOwnColumnsAreRefused() {
        JsonObject r = service.editColumn("node", "Label", "delete", null, null, null);

        assertFalse(r.get("success").getAsBoolean());
        assertNotNull(GephiControlService.findColumn(gm.getNodeTable(), "Label"));
    }

    @Test
    void aCheckChangesNothing() {
        JsonObject ok = service.editColumn("node", "group", "delete", null, null, null, true);
        JsonObject refused = service.editColumn("node", "Label", "delete", null, null, null, true);

        assertTrue(ok.get("success").getAsBoolean());
        assertFalse(refused.get("success").getAsBoolean());
        assertNotNull(GephiControlService.findColumn(gm.getNodeTable(), "group"), "a check deleted the column");
    }

    @Test
    void timeFromAYearColumnGivesEveryNodeAnInterval() {
        JsonObject r = service.setTimeFromColumns("node", "joined", null, null);

        assertTrue(r.get("success").getAsBoolean(), r.toString());
        assertEquals(5, r.get("with_time").getAsInt());
        assertEquals(1990.0, r.get("time_min").getAsDouble());
    }

    @Test
    void textDatesNeedAPatternAndAreCheckedBeforeAnythingChanges() {
        JsonObject r = service.setTimeFromColumns("node", "group", null, null, true);

        assertFalse(r.get("success").getAsBoolean());
        assertTrue(r.get("error").getAsString().contains("date_format"), r.toString());
    }

    private int kept(JsonObject r) {
        assertTrue(r.get("success").getAsBoolean(), r.toString());
        return r.get("nodes_kept").getAsInt();
    }

    @Test
    void combinedFiltersCountAndOrAndNot() {
        Map<String, Object> degree3 = Map.of("name", "Degree Range", "params", Map.of("range", List.of(3, 100)));
        Map<String, Object> groupX = Map.of("name", "Equal: group String (Node)", "params", Map.of("pattern", "x"));
        Map<String, Object> notX = Map.of("name", "Equal: group String (Node)", "params", Map.of("pattern", "x"),
                                          "exclude", true);

        // degree 3: b, c, e. group x: a, b, e.
        assertEquals(2, kept(service.applyFilters(List.of(degree3, groupX), "all", null, null, true)));
        assertEquals(4, kept(service.applyFilters(List.of(degree3, groupX), "any", null, null, true)));
        assertEquals(1, kept(service.applyFilters(List.of(degree3, notX), "all", null, null, true)));
        assertEquals(5, gm.getGraphVisible().getNodeCount(), "a dry run hid nodes");
    }

    @Test
    void anUnknownFilterIsNamed() {
        JsonObject r = service.applyFilters(List.of(Map.of("name", "No Such Filter")), "all", null, null, true);

        assertFalse(r.get("success").getAsBoolean());
        assertTrue(r.get("error").getAsString().contains("No Such Filter"));
    }
}
