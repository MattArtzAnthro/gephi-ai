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

    private static List<Integer> sortedDegrees() {
        Graph g = Lookup.getDefault().lookup(GraphController.class).getGraphModel().getGraph();
        List<Integer> d = new ArrayList<>();
        for (Node n : g.getNodes().toArray()) {
            d.add(g.getDegree(n));
        }
        Collections.sort(d);
        return d;
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
        List<Integer> first = sortedDegrees();
        service.generateGraph("preferential_attachment", 300, 3, null, 7L);
        List<Integer> second = sortedDegrees();
        service.generateGraph("preferential_attachment", 300, 3, null, 8L);
        List<Integer> other = sortedDegrees();

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
}
