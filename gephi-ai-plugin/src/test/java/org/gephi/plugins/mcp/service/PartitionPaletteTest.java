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

import com.google.gson.JsonObject;
import java.awt.Color;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** Every group gets its own colour, and the largest groups get the base colours. */
class PartitionPaletteTest {

    @Test
    void moreThanTwelveGroupsStillGetDistinctColours() {
        Map<String, Integer> counts = new HashMap<>();
        for (int i = 0; i < 40; i++) counts.put("g" + i, 100 - i);

        Map<String, Color> palette = GephiControlService.partitionPalette(counts);

        Set<Integer> rgb = new HashSet<>();
        for (Color c : palette.values()) rgb.add(c.getRGB());
        assertEquals(40, rgb.size(), "a colour was reused");
    }

    @Test
    void theLargestGroupGetsTheFirstColour() {
        Map<String, Integer> counts = Map.of("small", 2, "big", 50, "middle", 10);

        Map<String, Color> palette = GephiControlService.partitionPalette(counts);

        assertEquals(List.of("big", "middle", "small"), List.copyOf(palette.keySet()));
        assertEquals(GephiControlService.BASE_PALETTE[0], palette.get("big"));
    }

    @Test
    void manyGroupsComeWithANote() {
        JsonObject few = new JsonObject();
        GephiControlService.addPaletteNote(few, 12);
        JsonObject many = new JsonObject();
        GephiControlService.addPaletteNote(many, 13);

        assertFalse(few.has("palette_note"));
        assertTrue(many.has("palette_note"));
    }
}
