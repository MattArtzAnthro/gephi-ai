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
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.gephi.graph.api.Graph;
import org.gephi.graph.api.GraphModel;
import org.junit.jupiter.api.Test;

/**
 * Contention tests for the deadlock-safe lock helpers, against the real
 * ReentrantReadWriteLock behind a standalone GraphModel (two threads, no running
 * Gephi). lockWrite and lockRead poll a timed tryLock instead of parking in the
 * lock's wait queue (see the comments on those helpers); what matters under
 * contention is that they wait through a held lock and then genuinely acquire,
 * rather than failing fast, wedging forever, or reporting a hold they do not have.
 *
 * <p>Contention is established by a latch the test itself controls, never by a
 * sleep. The holder keeps the lock until this test releases it, so "the contender
 * is still blocked" is a fact about the lock rather than a guess about scheduling.
 * The only wall-clock value here is the probe below, and it can fail in one
 * direction only: if the contender acquires while the holder provably still holds,
 * which is the defect these tests exist to catch.
 */
class LockContentionTest {

    /** How long to watch a contender that must not succeed yet. */
    private static final long BLOCKED_PROBE_MS = 300;

    /** Generous ceiling for an acquisition that should follow release almost at once. */
    private static final long ACQUIRE_TIMEOUT_S = 15;

    private static Graph newGraph() {
        return GraphModel.Factory.newInstance().getGraph();
    }

    @Test
    void lockWriteWaitsOutAContendingReaderAndActuallyAcquires() throws Exception {
        Graph g = newGraph();

        CountDownLatch readerHolds = new CountDownLatch(1);
        CountDownLatch releaseReader = new CountDownLatch(1);
        Thread reader = new Thread(() -> {
            g.readLock();
            try {
                readerHolds.countDown();
                releaseReader.await(30, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                g.readUnlock();
            }
        }, "contending-reader");
        reader.setDaemon(true);
        reader.start();
        assertTrue(readerHolds.await(5, TimeUnit.SECONDS), "reader thread failed to start");

        // lockWrite runs on its own thread because a write hold count is per-thread,
        // and because the main thread must stay free to release the reader.
        CountDownLatch acquired = new CountDownLatch(1);
        AtomicInteger holdCountWhileHeld = new AtomicInteger(-1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread writer = new Thread(() -> {
            try {
                GephiControlService.lockWrite(g);
                try {
                    holdCountWhileHeld.set(g.getLock().getWriteHoldCount());
                } finally {
                    GephiControlService.unlockWrite(g);
                }
            } catch (Throwable t) {
                failure.set(t);
            } finally {
                acquired.countDown();
            }
        }, "contending-writer");
        writer.setDaemon(true);
        writer.start();

        // The reader still holds, and only this thread can release it, so a writer
        // that finishes here acquired a write lock over a live read hold.
        assertFalse(acquired.await(BLOCKED_PROBE_MS, TimeUnit.MILLISECONDS),
            "lockWrite acquired while a reader still held the lock");

        releaseReader.countDown();

        assertTrue(acquired.await(ACQUIRE_TIMEOUT_S, TimeUnit.SECONDS),
            "lockWrite never acquired after the reader released");
        assertNull(failure.get(), () -> "lockWrite threw: " + failure.get());
        assertEquals(1, holdCountWhileHeld.get(),
            "lockWrite returned without actually holding the write lock");

        reader.join(5_000);
        writer.join(5_000);
        assertFalse(reader.isAlive(), "reader thread leaked");
        assertFalse(writer.isAlive(), "writer thread leaked");
    }

    @Test
    void lockReadWaitsOutAHeldWriterAndActuallyAcquires() throws Exception {
        Graph g = newGraph();

        CountDownLatch writerHolds = new CountDownLatch(1);
        CountDownLatch releaseWriter = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            g.writeLock();
            try {
                writerHolds.countDown();
                releaseWriter.await(30, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                g.writeUnlock();
            }
        }, "holding-writer");
        writer.setDaemon(true);
        writer.start();
        assertTrue(writerHolds.await(5, TimeUnit.SECONDS), "writer thread failed to start");

        CountDownLatch acquired = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread readerThread = new Thread(() -> {
            try {
                GephiControlService.lockRead(g);
                g.readUnlock();
            } catch (Throwable t) {
                failure.set(t);
            } finally {
                acquired.countDown();
            }
        }, "contending-reader");
        readerThread.setDaemon(true);
        readerThread.start();

        assertFalse(acquired.await(BLOCKED_PROBE_MS, TimeUnit.MILLISECONDS),
            "lockRead acquired while a writer still held the lock");

        releaseWriter.countDown();

        assertTrue(acquired.await(ACQUIRE_TIMEOUT_S, TimeUnit.SECONDS),
            "lockRead never acquired after the writer released");
        assertNull(failure.get(), () -> "lockRead threw: " + failure.get());

        writer.join(5_000);
        readerThread.join(5_000);
        assertFalse(writer.isAlive(), "writer thread leaked");
        assertFalse(readerThread.isAlive(), "reader thread leaked");
    }

    /**
     * A long reader (a running statistic, in Gephi) must not let a waiting plugin write freeze
     * every other reader, and the write must give up with an error that does not blame the
     * renderer. A blocking writeLock() here parks at the head of the queue and new readers
     * (the renderer, layouts, the interface thread) wait behind it until the long reader ends.
     */
    @Test
    void lockWriteGivesUpBehindALongReaderWithoutBlockingOtherReaders() throws Exception {
        Graph g = newGraph();

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

        AtomicReference<Throwable> failure = new AtomicReference<>();
        CountDownLatch writerDone = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            try {
                GephiControlService.lockWrite(g);
                GephiControlService.unlockWrite(g);
            } catch (Throwable t) {
                failure.set(t);
            } finally {
                writerDone.countDown();
            }
        }, "waiting-writer");
        writer.setDaemon(true);
        writer.start();

        try {
            // While the write waits, fresh readers must still get in, as the renderer does
            // every frame. Each gets well under a second; a parked writer would hold them
            // until the long reader ended.
            for (int i = 0; i < 5; i++) {
                Thread.sleep(500);
                CountDownLatch got = new CountDownLatch(1);
                Thread probe = new Thread(() -> {
                    g.readLock();
                    g.readUnlock();
                    got.countDown();
                }, "probe-reader");
                probe.setDaemon(true);
                probe.start();
                assertTrue(got.await(1, TimeUnit.SECONDS),
                    "a new reader waited behind the pending write");
            }

            assertTrue(writerDone.await(30, TimeUnit.SECONDS), "lockWrite never gave up");
            assertNotNull(failure.get(), "lockWrite acquired over a live read hold");
            String message = String.valueOf(failure.get().getMessage());
            assertTrue(message.contains("Graph is busy"), message);
            assertFalse(message.contains("renderer"), "the busy message blames the renderer: " + message);
        } finally {
            releaseReader.countDown();
            longReader.join(5_000);
            writer.join(5_000);
        }
    }

    /** A request thread whose interrupt flag is already set must fail cleanly and hold nothing. */
    @Test
    void lockReadOnAnInterruptedThreadThrowsAndHoldsNothing() {
        Graph g = newGraph();
        Thread.currentThread().interrupt();
        try {
            assertThrows(RuntimeException.class, () -> GephiControlService.lockRead(g));
        } finally {
            assertTrue(Thread.interrupted(), "lockRead swallowed the interrupt");
        }
        assertEquals(0, g.getLock().getReadHoldCount(), "lockRead left a read hold behind");
    }

    /**
     * A thread that already reads re-enters at once even when another thread's writer is queued:
     * the writer waits on this thread's first hold, so refusing the second would only turn a
     * nested read into a "busy" error.
     */
    @Test
    void lockReadReentersUnderAQueuedWriter() throws Exception {
        Graph g = newGraph();

        CountDownLatch readerHolds = new CountDownLatch(1);
        CountDownLatch reenter = new CountDownLatch(1);
        CountDownLatch reentered = new CountDownLatch(1);
        AtomicInteger holdCount = new AtomicInteger(-1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread reader = new Thread(() -> {
            g.readLock();
            try {
                readerHolds.countDown();
                reenter.await(30, TimeUnit.SECONDS);
                GephiControlService.lockRead(g);
                try {
                    holdCount.set(g.getLock().getReadHoldCount());
                } finally {
                    g.readUnlock();
                }
            } catch (Throwable t) {
                failure.set(t);
            } finally {
                g.readUnlock();
                reentered.countDown();
            }
        }, "reentering-reader");
        reader.setDaemon(true);
        reader.start();
        assertTrue(readerHolds.await(5, TimeUnit.SECONDS), "reader thread failed to start");

        Thread writer = new Thread(() -> {
            g.writeLock();
            g.writeUnlock();
        }, "queued-writer");
        writer.setDaemon(true);
        writer.start();
        try {
            long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while (g.getLock().getQueueLength() != 1) {
                assertTrue(System.nanoTime() < until, "the writer never queued");
                Thread.sleep(5);
            }

            reenter.countDown();
            assertTrue(reentered.await(1, TimeUnit.SECONDS), "a nested read waited behind the queued writer");
            assertNull(failure.get(), () -> "lockRead threw: " + failure.get());
            assertEquals(2, holdCount.get(), "lockRead returned without a second read hold");
        } finally {
            reenter.countDown();
            reader.join(5_000);
            writer.join(5_000);
        }
        assertFalse(reader.isAlive(), "reader thread leaked");
        assertFalse(writer.isAlive(), "writer thread leaked");
    }

    /** Gephi-internal code reads inside the plugin's own write hold; that read must not wait. */
    @Test
    void lockReadInsideLockWriteAcquiresAtOnce() {
        Graph g = newGraph();
        GephiControlService.lockWrite(g);
        try {
            GephiControlService.lockRead(g);
            try {
                assertEquals(1, g.getLock().getReadHoldCount());
            } finally {
                g.readUnlock();
            }
        } finally {
            GephiControlService.unlockWrite(g);
        }
    }
}
