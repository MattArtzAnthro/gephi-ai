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
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.gephi.desktop.statistics.api.StatisticsControllerUI;
import org.gephi.graph.api.GraphModel;
import org.gephi.layout.api.LayoutController;
import org.gephi.layout.api.LayoutModel;
import org.gephi.layout.plugin.forceAtlas2.ForceAtlas2Builder;
import org.gephi.layout.spi.Layout;
import org.gephi.layout.spi.LayoutProperty;
import org.gephi.project.api.Workspace;
import org.gephi.statistics.spi.Statistics;
import org.gephi.statistics.spi.StatisticsUI;
import org.gephi.utils.longtask.api.LongTaskListener;
import org.gephi.utils.longtask.spi.LongTask;
import org.gephi.utils.progress.ProgressTicket;
import org.junit.jupiter.api.Test;

/**
 * Statistics and layouts run through Gephi's own controllers so its Statistics and Layout panels
 * show what Gephi AI is doing. These stand-in controllers pin the waiting, stopping, error and
 * call-order logic without the desktop interface.
 */
class PanelExecutionTest {

    private static final Consumer<Runnable> DIRECT = Runnable::run;

    /** A statistic that runs until cancelled, or for a fixed time. */
    static class SlowStat implements Statistics, LongTask {
        final long millis;
        final AtomicBoolean cancelled = new AtomicBoolean();
        final AtomicBoolean ran = new AtomicBoolean();

        SlowStat(long millis) {
            this.millis = millis;
        }

        @Override public void execute(GraphModel gm) {
            ran.set(true);
            long end = System.currentTimeMillis() + millis;
            while (!cancelled.get() && System.currentTimeMillis() < end) {
                Thread.onSpinWait();
            }
        }

        @Override public String getReport() {
            return "";
        }

        @Override public boolean cancel() {
            cancelled.set(true);
            return true;
        }

        @Override public void setProgressTicket(ProgressTicket t) {
        }
    }

    /** Runs the statistic on its own thread and reports back, as Gephi's panel controller does. */
    static class FakeStatsUI implements StatisticsControllerUI {
        Throwable failWith;

        @Override public void execute(Statistics s) {
            execute(s, null);
        }

        @Override public void execute(Statistics s, LongTaskListener listener) {
            new Thread(() -> {
                if (failWith != null) {
                    try {
                        Method m = listener.getClass().getMethod("fatalError", Throwable.class);
                        m.invoke(listener, failWith);
                    } catch (ReflectiveOperationException e) {
                        throw new AssertionError(e);
                    }
                    return;
                }
                s.execute(null);
                listener.taskFinished(s instanceof LongTask ? (LongTask) s : null);
            }).start();
        }

        @Override public void setStatisticsUIVisible(StatisticsUI ui, boolean visible) {
        }
    }

    @Test
    void statisticRunThroughThePanelIsWaitedFor() throws Exception {
        SlowStat stat = new SlowStat(150);

        boolean stopped = GephiControlService.executeStatistic(stat, null, 0, new FakeStatsUI(), DIRECT);

        assertFalse(stopped);
        assertTrue(stat.ran.get());
        assertFalse(stat.cancelled.get());
    }

    @Test
    void statisticPastItsDeadlineIsStoppedAndReported() throws Exception {
        SlowStat stat = new SlowStat(60_000);

        long start = System.nanoTime();
        boolean stopped = GephiControlService.executeStatistic(stat, null, 200, new FakeStatsUI(), DIRECT);

        assertTrue(stopped);
        assertTrue(stat.cancelled.get());
        assertTrue((System.nanoTime() - start) / 1_000_000 < 10_000);
    }

    @Test
    void failureReportedByGephiEndsTheWaitWithTheError() {
        FakeStatsUI ui = new FakeStatsUI();
        ui.failWith = new IllegalStateException("boom");

        RuntimeException e = assertThrows(RuntimeException.class,
            () -> GephiControlService.executeStatistic(new SlowStat(60_000), null, 0, ui, DIRECT));

        assertTrue(String.valueOf(e.getCause()).contains("boom"), String.valueOf(e));
    }

    @Test
    void withoutThePanelTheStatisticRunsDirectly() throws Exception {
        SlowStat stat = new SlowStat(10);

        assertFalse(GephiControlService.executeStatistic(stat, null, 0, null, DIRECT));
        assertTrue(stat.ran.get());
    }

    @Test
    void stopRequestCancelsTheRunningStatisticAndMarksItStopped() throws Exception {
        SlowStat stat = new SlowStat(60_000);
        GephiControlService.RUNNING_STATISTICS.put(stat, "Slow");
        try {
            Thread run = new Thread(() -> {
                try {
                    GephiControlService.executeStatistic(stat, null, 0, new FakeStatsUI(), DIRECT);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
            run.start();
            while (!stat.ran.get()) {
                Thread.onSpinWait();
            }

            final com.google.gson.JsonObject r = GephiControlService.getInstance().stopStatistics();

            run.join(10_000);
            assertFalse(run.isAlive(), "the statistic kept running after the stop");
            assertTrue(stat.cancelled.get());
            assertEquals("Slow", r.getAsJsonArray("stopped").get(0).getAsString());
            assertTrue(GephiControlService.STOP_REQUESTED.contains(stat));
        } finally {
            GephiControlService.RUNNING_STATISTICS.remove(stat);
            GephiControlService.STOP_REQUESTED.remove(stat);
        }
    }

    @Test
    void stopWithNothingRunningSaysSo() {
        com.google.gson.JsonObject r = GephiControlService.getInstance().stopStatistics();

        assertTrue(r.get("message").getAsString().contains("No statistic"), r.toString());
    }

    /** Records the order of controller calls and what the layout held at each. */
    static class FakeLayoutController implements LayoutController {
        final List<String> calls = new ArrayList<>();
        Layout selected;

        @Override public LayoutModel getModel() {
            return null;
        }

        @Override public LayoutModel getModel(Workspace w) {
            return null;
        }

        @Override public void setLayout(Layout l) {
            selected = l;
            calls.add("setLayout linLog=" + value(l, "linLogMode"));
        }

        @Override public void executeLayout() {
            calls.add("execute");
        }

        @Override public void executeLayout(int n) {
            calls.add("execute " + n);
        }

        public void executeLayout(Layout l) {
            calls.add("executeNow");
        }

        @Override public boolean canExecute() {
            return true;
        }

        @Override public void stopLayout() {
            calls.add("stop");
        }

        @Override public boolean canStop() {
            return false;
        }
    }

    static Object value(Layout layout, String key) {
        for (LayoutProperty p : layout.getProperties()) {
            if (p.getCanonicalName() != null && p.getCanonicalName().contains("." + key + ".")) {
                try {
                    return p.getProperty().getValue();
                } catch (Exception e) {
                    return null;
                }
            }
        }
        return null;
    }

    @Test
    void layoutIsSelectedThenGivenItsSettingsThenShownAgainThenRun() {
        FakeLayoutController lc = new FakeLayoutController();
        Layout layout = new ForceAtlas2Builder().buildLayout();
        Map<String, Object> props = new LinkedHashMap<>();
        props.put("linLogMode", true);
        props.put("barnesHutOptimize", true);

        List<String> unapplied = GephiControlService.startLayoutThroughController(
            lc, layout, props, 300, DIRECT);

        // Selecting reloads the settings Gephi saved for this layout, so Gephi AI's settings go
        // on after it; selecting again makes the panel show them; then it runs.
        assertEquals(List.of("setLayout linLog=false", "setLayout linLog=true", "execute 300"), lc.calls);
        assertEquals(List.of("barnesHutOptimize"), unapplied);
        assertEquals(true, value(layout, "linLogMode"));
    }

    @Test
    void settingsNotGivenStartFromTheLayoutsDefaults() {
        FakeLayoutController lc = new FakeLayoutController();
        Layout layout = new ForceAtlas2Builder().buildLayout();
        layout.resetPropertiesValues();
        for (LayoutProperty p : layout.getProperties()) {
            if (p.getCanonicalName().contains(".linLogMode.")) {
                try {
                    p.getProperty().setValue(true);
                } catch (Exception e) {
                    throw new AssertionError(e);
                }
            }
        }

        GephiControlService.startLayoutThroughController(lc, layout, Map.of("gravity", 2.0), 10, DIRECT);

        assertEquals(false, value(layout, "linLogMode"), "a leftover setting must not carry into the run");
    }

    /** A dynamic statistic: Gephi steps it through the network's timeline window by window. */
    static class FakeDynamicStat implements org.gephi.statistics.spi.DynamicStatistics {
        double window = 1;
        double tick = 1;

        FakeDynamicStat() {
        }

        FakeDynamicStat(double window, double tick) {
            this.window = window;
            this.tick = tick;
        }

        @Override public void execute(GraphModel gm) {
        }

        @Override public String getReport() {
            return "";
        }

        @Override public void loop(org.gephi.graph.api.GraphView v, org.gephi.graph.api.Interval i) {
        }

        @Override public void end() {
        }

        @Override public double getWindow() {
            return window;
        }

        @Override public void setWindow(double w) {
            window = w;
        }

        @Override public double getTick() {
            return tick;
        }

        @Override public void setTick(double t) {
            tick = t;
        }

        @Override public org.gephi.graph.api.Interval getBounds() {
            return null;
        }

        @Override public void setBounds(org.gephi.graph.api.Interval b) {
        }
    }

    @Test
    void dynamicStatisticIsRefusedOnANetworkWithoutTimeData() {
        GraphModel gm = GraphModel.Factory.newInstance();
        gm.getDirectedGraph().addNode(gm.factory().newNode("a"));

        String problem = GephiControlService.dynamicStatisticProblem(new FakeDynamicStat(), gm);

        assertTrue(problem != null && problem.contains("time data"), String.valueOf(problem));
    }

    @Test
    void dynamicStatisticIsAllowedWhenTheNetworkHasTimeData() {
        org.gephi.graph.api.Configuration config = org.gephi.graph.api.Configuration.builder()
            .timeRepresentation(org.gephi.graph.api.TimeRepresentation.INTERVAL).build();
        GraphModel gm = GraphModel.Factory.newInstance(config);
        org.gephi.graph.api.Node n = gm.factory().newNode("a");
        n.addInterval(new org.gephi.graph.api.Interval(1, 5));
        gm.getDirectedGraph().addNode(n);

        assertEquals(null, GephiControlService.dynamicStatisticProblem(new FakeDynamicStat(), gm));
    }

    private static GraphModel timedNetwork(double low, double high) {
        org.gephi.graph.api.Configuration config = org.gephi.graph.api.Configuration.builder()
            .timeRepresentation(org.gephi.graph.api.TimeRepresentation.INTERVAL).build();
        GraphModel gm = GraphModel.Factory.newInstance(config);
        org.gephi.graph.api.Node n = gm.factory().newNode("a");
        n.addInterval(new org.gephi.graph.api.Interval(low, high));
        gm.getDirectedGraph().addNode(n);
        return gm;
    }

    @Test
    void dynamicStatisticWithoutAStepIsRefusedAndTheTimeSpanIsGiven() {
        // Gephi's dynamic statistics start with window 0 and tick 0; its settings dialog fills
        // them in. Run with tick 0, Gephi's loop never advances.
        String problem = GephiControlService.dynamicStatisticProblem(new FakeDynamicStat(0, 0),
            timedNetwork(1990, 2000));

        assertTrue(problem != null && problem.contains("tick") && problem.contains("1990")
            && problem.contains("2000"), String.valueOf(problem));
    }

    @Test
    void windowWiderThanTheNetworksTimeSpanIsRefused() {
        String problem = GephiControlService.dynamicStatisticProblem(new FakeDynamicStat(50, 1),
            timedNetwork(1990, 2000));

        assertTrue(problem != null && problem.contains("window"), String.valueOf(problem));
    }

    @Test
    void dynamicStatisticWithAWindowAndStepInsideTheSpanRuns() {
        assertEquals(null, GephiControlService.dynamicStatisticProblem(new FakeDynamicStat(2, 1),
            timedNetwork(1990, 2000)));
    }

    @Test
    void anOrdinaryStatisticIsNeverRefusedForLackingTimeData() {
        GraphModel gm = GraphModel.Factory.newInstance();

        assertEquals(null, GephiControlService.dynamicStatisticProblem(new SlowStat(1), gm));
    }
}
