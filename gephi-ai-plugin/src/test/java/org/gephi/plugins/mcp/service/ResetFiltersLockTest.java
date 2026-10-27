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

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphController;
import org.gephi.graph.api.GraphModel;
import org.gephi.graph.api.GraphView;
import org.gephi.graph.api.Node;
import org.gephi.graph.api.Subgraph;
import org.gephi.project.api.ProjectController;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.openide.util.Lookup;

/**
 * Restoring the full graph takes no graph lock from graphstore 0.8.11 (gephi/graphstore#357), so
 * resetting filters must not wait for a running statistic, which holds the read lock for as long
 * as it runs. Contention is set up with latches, as in LockContentionTest.
 */
class ResetFiltersLockTest {

    private final GephiControlService service = GephiControlService.getInstance();
    private GraphModel gm;

    /** Two nodes, with a filtered view that hides one of them made visible. */
    @BeforeEach
    void filteredGraph() {
        ProjectController pc = Lookup.getDefault().lookup(ProjectController.class);
        pc.closeCurrentProject();
        pc.newProject();
        gm = Lookup.getDefault().lookup(GraphController.class).getGraphModel();
        Graph g = gm.getGraph();
        Node a = gm.factory().newNode("a");
        Node b = gm.factory().newNode("b");
        g.addNode(a);
        g.addNode(b);
        GraphView view = gm.createView();
        Subgraph sub = gm.getGraph(view);
        sub.fill();
        sub.removeNode(sub.getNode("b"));
        gm.setVisibleView(view);
    }

    @Test
    void resetFiltersDoesNotWaitForARunningStatistic() throws Exception {
        Graph g = gm.getGraph();

        CountDownLatch readerHolds = new CountDownLatch(1);
        CountDownLatch releaseReader = new CountDownLatch(1);
        Thread statistic = new Thread(() -> {
            g.readLock();
            try {
                readerHolds.countDown();
                releaseReader.await(60, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                g.readUnlock();
            }
        }, "running-statistic");
        statistic.setDaemon(true);
        statistic.start();
        assertTrue(readerHolds.await(5, TimeUnit.SECONDS), "statistic thread failed to start");

        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<JsonObject> result = new AtomicReference<>();
        Thread request = new Thread(() -> {
            try {
                result.set(service.resetFilters());
            } finally {
                done.countDown();
            }
        }, "reset-request");
        request.setDaemon(true);
        request.start();

        try {
            // Only this thread can end the statistic, so a reset still waiting here is waiting on it.
            assertTrue(done.await(3, TimeUnit.SECONDS), "resetting filters waited for the running statistic");
            assertTrue(result.get().get("success").getAsBoolean(), result.get().toString());
            assertTrue(gm.getVisibleView().isMainView(), "the full graph is not visible after the reset");
        } finally {
            releaseReader.countDown();
            statistic.join(5_000);
            request.join(20_000);
        }
    }
}
