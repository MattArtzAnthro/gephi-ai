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
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphController;
import org.gephi.graph.api.Node;
import org.gephi.project.api.ProjectController;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.openide.util.Lookup;

/** Graphs made by Gephi's own generators, loaded the way an imported file is. */
class GenerateGraphTest {

    private final GephiControlService service = GephiControlService.getInstance();

    @BeforeEach
    void freshProject() {
        ProjectController pc = Lookup.getDefault().lookup(ProjectController.class);
        pc.closeCurrentProject();
        pc.newProject();
    }

    /**
     * The graph's edges as sorted pairs of node positions (the order the generator added them), so
     * two graphs compare edge for edge. Gephi numbers each generated graph's ids from a counter that
     * keeps rising, so raw ids differ between two identical graphs.
     */
    private static List<String> edgeSet() {
        Graph g = Lookup.getDefault().lookup(GraphController.class).getGraphModel().getGraph();
        java.util.Map<Node, Integer> position = new java.util.HashMap<>();
        for (Node n : g.getNodes().toArray()) {
            position.put(n, position.size());
        }
        List<String> edges = new ArrayList<>();
        for (org.gephi.graph.api.Edge e : g.getEdges().toArray()) {
            int a = position.get(e.getSource());
            int b = position.get(e.getTarget());
            edges.add(Math.min(a, b) + "-" + Math.max(a, b));
        }
        Collections.sort(edges);
        return edges;
    }

    @Test
    void preferentialAttachmentHasTheModelsEdgeCount() {
        JsonObject r = service.generateGraph("preferential_attachment", 200, 2, null, 42L);

        assertTrue(r.get("success").getAsBoolean(), r.toString());
        assertEquals(200, r.get("node_count").getAsInt());
        // A star of m + 1 nodes, then m edges for each later node.
        assertEquals(2 + (200 - 2 - 1) * 2, r.get("edge_count").getAsInt());
        assertTrue(r.get("reproducible").getAsBoolean());
        assertEquals(42L, r.get("seed").getAsLong());
    }

    @Test
    void theSameSeedGivesTheSameGraph() {
        service.generateGraph("preferential_attachment", 300, 3, null, 7L);
        List<String> first = edgeSet();
        service.generateGraph("preferential_attachment", 300, 3, null, 7L);
        List<String> second = edgeSet();
        service.generateGraph("preferential_attachment", 300, 3, null, 8L);
        List<String> other = edgeSet();

        assertEquals(first, second);
        assertNotEquals(first, other);
    }

    @Test
    void randomGraphSaysItCannotBeReproduced() {
        JsonObject r = service.generateGraph("random", 100, null, 0.1, null);

        assertTrue(r.get("success").getAsBoolean(), r.toString());
        assertEquals(100, r.get("node_count").getAsInt());
        assertTrue(r.get("edge_count").getAsInt() > 0 && r.get("edge_count").getAsInt() < 100 * 99 / 2);
        assertFalse(r.get("reproducible").getAsBoolean());
    }

    @Test
    void eachGraphGetsItsOwnWorkspaceNamedAfterTheModel() {
        service.generateGraph("preferential_attachment", 50, 1, null, 1L);
        ProjectController pc = Lookup.getDefault().lookup(ProjectController.class);
        String name = pc.getCurrentWorkspace().getLookup()
            .lookup(org.gephi.project.api.WorkspaceInformation.class).getName();

        assertTrue(name.startsWith("Preferential attachment"), name);
        assertTrue(name.contains("seed 1"), name);
    }

    @Test
    void badSettingsAreRefusedWithTheReason() {
        assertTrue(service.generateGraph("small_world", 50, 2, null, null).get("error").getAsString()
            .contains("preferential_attachment"));
        assertTrue(service.generateGraph("preferential_attachment", 10, 10, null, null).get("error")
            .getAsString().contains("edges_per_node"));
        assertTrue(service.generateGraph("random", 10, null, 1.5, null).get("error").getAsString()
            .contains("wiring_probability"));
        assertTrue(service.generateGraph("random", 1, null, 0.5, null).get("error").getAsString()
            .contains("nodes"));
        assertTrue(service.generateGraph("random", GephiControlService.GENERATE_MAX_RANDOM_NODES + 1, null, 0.01,
            null).get("error").getAsString().contains("nodes"));
    }

    /** One request must not be able to run Gephi out of memory. */
    @Test
    void preferentialAttachmentRefusesAnEdgeCountOverTheCap() {
        JsonObject r = service.generateGraph("preferential_attachment", 100_000, 50_000, null, 1L);

        assertFalse(r.get("success").getAsBoolean());
        String error = r.get("error").getAsString();
        String cap = String.valueOf(GephiControlService.GENERATE_MAX_EXPECTED_EDGES);
        assertTrue(error.contains("edges") && error.contains(cap), error);
    }

    @Test
    void preferentialAttachmentRefusesTooManyNodes() {
        JsonObject r = service.generateGraph("preferential_attachment", GephiControlService.GENERATE_MAX_NODES + 1, 2,
            null, 1L);

        assertTrue(r.get("error").getAsString().contains("nodes"), r.toString());
    }

    @Test
    void randomGraphRefusesAnExpectedEdgeCountOverTheCap() {
        JsonObject r = service.generateGraph("random", 20_000, null, 0.5, null);

        assertTrue(r.get("error").getAsString().contains("expects about"), r.toString());
    }
}
