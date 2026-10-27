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

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphModel;
import org.gephi.graph.api.GraphView;
import org.gephi.graph.api.Node;
import org.gephi.graph.api.Subgraph;
import org.junit.jupiter.api.Test;

/**
 * The visible graph is read under the plugin's timed read lock, taken before the visible graph is
 * fetched. On graphstore 0.8.8 getGraphVisible() takes Gephi's blocking read lock itself, so an
 * unguarded read queued behind a parked writer waits for as long as the reader ahead of that
 * writer runs; and a filter destroys the previous result view under the write lock, which the
 * read hold keeps out until the counts are read. Contention is set up with latches, as in
 * LockContentionTest.
 */
class VisibleGraphLockTest {

    /** A model with three nodes and two edges, whose visible view hides one node and its edge. */
    private static GraphModel filteredModel() {
        GraphModel gm = GraphModel.Factory.newInstance();
        Graph g = gm.getGraph();
        Node a = gm.factory().newNode("a");
        Node b = gm.factory().newNode("b");
        Node c = gm.factory().newNode("c");
        g.addNode(a);
        g.addNode(b);
        g.addNode(c);
        g.addEdge(gm.factory().newEdge(a, b, true));
        g.addEdge(gm.factory().newEdge(b, c, true));
        GraphView view = gm.createView();
        Subgraph sub = gm.getGraph(view);
        sub.fill();
        sub.removeNode(sub.getNode("c"));
        gm.setVisibleView(view);
        return gm;
    }

    @Test
    void visibleCountsReadTheVisibleView() {
        assertArrayEquals(new int[] {2, 1}, GephiControlService.visibleCounts(filteredModel()));
    }

    /**
     * A long reader (a running statistic) holds the lock and a Gephi write queues behind it. A
     * visible-graph read must give up with "Graph is busy" rather than park behind the writer
     * until the statistic ends.
     */
    @Test
    void visibleCountsGiveUpBehindAQueuedWriterInsteadOfParking() throws Exception {
        GraphModel gm = filteredModel();
        Graph g = gm.getGraph();

        CountDownLatch readerHolds = new CountDownLatch(1);
        CountDownLatch releaseReader = new CountDownLatch(1);
        Thread longReader = new Thread(() -> {
            g.readLock();
            try {
                readerHolds.countDown();
                releaseReader.await(60, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                g.readUnlock();
            }
        }, "long-reader");
        longReader.setDaemon(true);
        longReader.start();
        assertTrue(readerHolds.await(5, TimeUnit.SECONDS), "reader thread failed to start");

        Thread writer = new Thread(() -> {
            g.writeLock();
            g.writeUnlock();
        }, "queued-writer");
        writer.setDaemon(true);
        writer.start();

        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread counter = new Thread(() -> {
            try {
                GephiControlService.visibleCounts(gm);
            } catch (Throwable t) {
                failure.set(t);
            } finally {
                done.countDown();
            }
        }, "counting-reader");
        counter.setDaemon(true);

        try {
            long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            // graphstore 0.8.8 has no queue length, so a writer parked in the lock is one waiting.
            while (writer.getState() != Thread.State.WAITING) {
                assertTrue(System.nanoTime() < until, "the writer never queued");
                Thread.sleep(5);
            }
            counter.start();

            // Only this thread can release the long reader, so a read still waiting at the
            // ceiling is parked behind the writer.
            assertTrue(done.await(15, TimeUnit.SECONDS), "the visible-graph read parked behind the queued writer");
            assertTrue(failure.get() instanceof RuntimeException, () -> "expected a busy error, got " + failure.get());
            assertTrue(String.valueOf(failure.get().getMessage()).contains("Graph is busy"),
                failure.get().getMessage());
        } finally {
            releaseReader.countDown();
            longReader.join(5_000);
            writer.join(5_000);
            counter.join(5_000);
        }
        assertFalse(counter.isAlive(), "counting thread leaked");
    }
}
