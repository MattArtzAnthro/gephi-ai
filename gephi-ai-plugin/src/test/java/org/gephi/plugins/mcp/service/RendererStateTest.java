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
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.OptionalLong;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

/**
 * Reading Gephi 0.11.4's renderer counters. Measured on a live Gephi: an idle graph draws about
 * 64 frames and commits about 44 world updates a second, so world updates that stop while frames
 * continue are a hang, not an idle graph.
 */
class RendererStateTest {

    @Test
    void framesAndWorldUpdatesAdvancingIsHealthy() {
        assertEquals("ok", GephiControlService.rendererState(16, 11));
    }

    @Test
    void framesWithoutWorldUpdatesIsAStall() {
        assertEquals("stalled", GephiControlService.rendererState(16, 0));
    }

    @Test
    void noFramesIsNotDrawing() {
        assertEquals("not_drawing", GephiControlService.rendererState(0, 0));
        assertEquals("not_drawing", GephiControlService.rendererState(0, 5));
    }

    @Test
    void readyOnceTheEngineExistsAndDrawsAFrame() throws Exception {
        AtomicLong calls = new AtomicLong();
        // No engine for the first checks, then an engine whose frame count rises.
        boolean ready = GephiControlService.awaitRendererReady(() -> {
            long n = calls.incrementAndGet();
            return n < 3 ? OptionalLong.empty() : OptionalLong.of(n);
        }, 5_000);

        assertTrue(ready);
    }

    @Test
    void notReadyWhileThereIsNoEngine() throws Exception {
        assertFalse(GephiControlService.awaitRendererReady(OptionalLong::empty, 100));
    }

    @Test
    void notReadyWhileTheFrameCountStandsStill() throws Exception {
        assertFalse(GephiControlService.awaitRendererReady(() -> OptionalLong.of(42), 100));
    }

    /** Counters that advance by fixed steps per read; world updates stop for the first reads. */
    private static java.util.function.Supplier<java.util.Optional<long[]>> counters(int frozenReads,
        boolean everResume) {
        long[] state = {0, 0};
        java.util.concurrent.atomic.AtomicInteger reads = new java.util.concurrent.atomic.AtomicInteger();
        return () -> {
            int n = reads.getAndIncrement();
            state[0] += 16;
            if (n >= frozenReads && everResume) {
                state[1] += 11;
            }
            return java.util.Optional.of(new long[] {state[0], state[1]});
        };
    }

    @Test
    void sampledHealthyRendererIsOk() throws Exception {
        assertEquals("ok", GephiControlService.rendererStats(counters(0, true), 20, 200).get("state").getAsString());
    }

    /** One slow world update (a large graph, a screenshot pausing updates) is not a hang. */
    @Test
    void worldUpdatesThatResumeWithinTheConfirmationAreNotAStall() throws Exception {
        assertEquals("ok", GephiControlService.rendererStats(counters(3, true), 20, 400).get("state").getAsString());
    }

    @Test
    void worldUpdatesFrozenThroughTheConfirmationAreAStall() throws Exception {
        com.google.gson.JsonObject r = GephiControlService.rendererStats(counters(0, false), 20, 200);

        assertEquals("stalled", r.get("state").getAsString());
        assertTrue(r.get("stalled_for_ms").getAsLong() >= 200, r.toString());
    }

    @Test
    void noEngineIsNotStarted() throws Exception {
        assertEquals("not_started",
            GephiControlService.rendererStats(java.util.Optional::empty, 20, 200).get("state").getAsString());
    }

    @Test
    void anUnreadableEngineIsUnknown() throws Exception {
        assertEquals("unknown", GephiControlService.rendererStats(() -> {
            throw new IllegalStateException("engine gone");
        }, 20, 200).get("state").getAsString());
    }
}
