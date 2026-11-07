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
}
