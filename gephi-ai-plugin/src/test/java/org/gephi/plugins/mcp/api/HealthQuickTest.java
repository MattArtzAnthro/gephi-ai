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

package org.gephi.plugins.mcp.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

/**
 * The installers ask /health whether Gephi answers and give it a few seconds. The full answer
 * samples the renderer for a quarter of a second (two seconds to confirm a stall) and probes the
 * graph lock, so a stalled Gephi can take longer than the installers wait. The quick answer
 * (?quick=true) does neither.
 */
class HealthQuickTest {

    private final AtomicInteger rendererCalls = new AtomicInteger();
    private final AtomicInteger lockCalls = new AtomicInteger();
    private final AtomicInteger statsCalls = new AtomicInteger();

    private JsonObject health(boolean quick) {
        return GephiAPIServer.health(quick,
            () -> {
                lockCalls.incrementAndGet();
                return "ok";
            },
            () -> {
                statsCalls.incrementAndGet();
                return new JsonObject();
            },
            () -> {
                rendererCalls.incrementAndGet();
                JsonObject r = new JsonObject();
                r.addProperty("state", "ok");
                return r;
            });
    }

    @Test
    void quickHealthSkipsTheRendererSampleAndTheLockProbeButReportsVersionAndStatus() {
        JsonObject r = health(true);

        assertEquals("running", r.get("status").getAsString());
        assertTrue(r.has("version"));
        assertTrue(r.get("success").getAsBoolean());
        assertFalse(r.has("renderer"));
        assertFalse(r.has("graph_lock"));
        assertEquals(0, rendererCalls.get(), "the renderer was sampled");
        assertEquals(0, lockCalls.get(), "the graph lock was probed");
        assertEquals(0, statsCalls.get());
    }

    @Test
    void fullHealthStillSamplesTheRendererAndProbesTheLock() {
        JsonObject r = health(false);

        assertEquals(1, rendererCalls.get());
        assertEquals(1, lockCalls.get());
        assertEquals("ok", r.get("graph_lock").getAsString());
        assertEquals("ok", r.get("renderer").getAsJsonObject().get("state").getAsString());
        assertTrue(r.has("graph_lock_stats"));
    }

    @Test
    void onlyAnExplicitTrueMeansQuick() {
        assertTrue(GephiAPIServer.isQuick(Map.of("quick", "true")));
        assertTrue(GephiAPIServer.isQuick(Map.of("quick", "TRUE")));
        assertFalse(GephiAPIServer.isQuick(Map.of("quick", "false")));
        assertFalse(GephiAPIServer.isQuick(Map.of()));
        assertFalse(GephiAPIServer.isQuick(null));
    }
}
