package org.gephi.plugins.mcp.api;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** Unit tests for the DNS-rebinding Host-header guard. */
class HostHeaderTest {

    @Test
    void loopbackHostsAreAccepted() {
        assertTrue(GephiAPIServer.isLoopbackHost("127.0.0.1:8080"));
        assertTrue(GephiAPIServer.isLoopbackHost("127.0.0.1"));
        assertTrue(GephiAPIServer.isLoopbackHost("localhost:8080"));
        assertTrue(GephiAPIServer.isLoopbackHost("localhost"));
        assertTrue(GephiAPIServer.isLoopbackHost("LOCALHOST:8080"));
        assertTrue(GephiAPIServer.isLoopbackHost("[::1]:8080"));
        assertTrue(GephiAPIServer.isLoopbackHost("[::1]"));
    }

    @Test
    void missingHostHeaderIsAllowed() {
        // Non-browser clients (e.g. the MCP server) may omit Host; browsers never do,
        // so this does not open a browser bypass.
        assertTrue(GephiAPIServer.isLoopbackHost(null));
        assertTrue(GephiAPIServer.isLoopbackHost(""));
    }

    @Test
    void rebindingAndRemoteHostsAreRejected() {
        assertFalse(GephiAPIServer.isLoopbackHost("evil.com"));
        assertFalse(GephiAPIServer.isLoopbackHost("evil.com:8080"));
        assertFalse(GephiAPIServer.isLoopbackHost("attacker.localhost.evil.com"));
        assertFalse(GephiAPIServer.isLoopbackHost("127.0.0.1.evil.com"));
        assertFalse(GephiAPIServer.isLoopbackHost("192.168.1.5:8080"));
        assertFalse(GephiAPIServer.isLoopbackHost("0.0.0.0:8080"));
    }
}
