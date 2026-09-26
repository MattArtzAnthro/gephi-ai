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
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.gephi.layout.plugin.forceAtlas2.ForceAtlas2Builder;
import org.gephi.layout.spi.Layout;
import org.gephi.layout.spi.LayoutProperty;
import org.junit.jupiter.api.Test;

/**
 * A layout setting whose name matches no property used to be dropped without a word, so a
 * misspelled key ran the layout on its defaults. Every name that matched nothing is reported.
 */
class LayoutPropertyNamesTest {

    private static Object value(Layout layout, String key) throws Exception {
        for (LayoutProperty p : layout.getProperties()) {
            if (p.getCanonicalName() != null && p.getCanonicalName().contains("." + key + ".")) {
                return p.getProperty().getValue();
            }
        }
        throw new AssertionError("No such property: " + key);
    }

    @Test
    void namesThatMatchNothingAreReportedAndTheRestApplied() throws Exception {
        Layout layout = new ForceAtlas2Builder().buildLayout();
        Map<String, Object> props = new LinkedHashMap<>();
        props.put("linLogMode", true);
        props.put("barnesHutOptimize", true);
        props.put("preventOverlap", true);
        props.put("strongGravityMode", true);

        List<String> unapplied = GephiControlService.applyLayoutProperties(layout, props);

        assertEquals(List.of("barnesHutOptimize", "preventOverlap"), unapplied);
        assertEquals(true, value(layout, "linLogMode"));
        assertEquals(true, value(layout, "strongGravityMode"));
    }

    @Test
    void displayNamesAndOtherCasesStillCountAsMatches() throws Exception {
        Layout layout = new ForceAtlas2Builder().buildLayout();
        Map<String, Object> props = new LinkedHashMap<>();
        props.put("LinLog mode", true);
        props.put("SCALINGRATIO", 0.5);

        List<String> unapplied = GephiControlService.applyLayoutProperties(layout, props);

        assertTrue(unapplied.isEmpty(), "unexpected: " + unapplied);
        assertEquals(true, value(layout, "linLogMode"));
        assertEquals(0.5, ((Number) value(layout, "scalingRatio")).doubleValue(), 1e-9);
    }
}
