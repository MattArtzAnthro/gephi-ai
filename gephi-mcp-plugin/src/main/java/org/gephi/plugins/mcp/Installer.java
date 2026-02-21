package org.gephi.plugins.mcp;

import java.util.logging.Level;
import java.util.logging.Logger;
import org.gephi.plugins.mcp.api.GephiAPIServer;
import org.openide.modules.ModuleInstall;

public class Installer extends ModuleInstall {

    private static final Logger LOGGER = Logger.getLogger(Installer.class.getName());
    private static final int DEFAULT_PORT = 8080;
    private GephiAPIServer server;

    @Override
    public void restored() {
        LOGGER.info("########## Gephi MCP Plugin: restored() called ##########");
        System.out.println("########## Gephi MCP Plugin: restored() called ##########");

        // Start server in a new thread to not block module loading
        Thread serverThread = new Thread(() -> {
            try {
                Thread.sleep(2000); // Wait for Gephi to fully initialize
                startServer();
            } catch (Exception e) {
                LOGGER.log(Level.SEVERE, "Failed to start MCP server", e);
                System.err.println("Failed to start MCP server: " + e.getMessage());
                e.printStackTrace();
            }
        }, "MCP-Server-Starter");
        serverThread.setDaemon(true);
        serverThread.start();
    }

    @Override
    public void close() {
        LOGGER.info("########## Gephi MCP Plugin: close() called ##########");
        stopServer();
    }

    @Override
    public boolean closing() {
        LOGGER.info("########## Gephi MCP Plugin: closing() called ##########");
        stopServer();
        return true;
    }

    private void startServer() {
        try {
            int port = Integer.getInteger("gephi.mcp.port", DEFAULT_PORT);
            LOGGER.info("########## Starting MCP server on port " + port + " ##########");
            System.out.println("########## Starting MCP server on port " + port + " ##########");

            server = new GephiAPIServer(port);
            server.startServer();

            LOGGER.info("===========================================");
            LOGGER.info("  Gephi MCP Plugin Active");
            LOGGER.info("  API: http://127.0.0.1:" + port);
            LOGGER.info("===========================================");
            System.out.println("===========================================");
            System.out.println("  Gephi MCP Plugin Active");
            System.out.println("  API: http://127.0.0.1:" + port);
            System.out.println("===========================================");
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Failed to start MCP server", e);
            System.err.println("Failed to start MCP server: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void stopServer() {
        if (server != null) {
            try {
                server.stopServer();
                server = null;
                LOGGER.info("########## MCP server stopped ##########");
            } catch (Exception e) {
                LOGGER.log(Level.WARNING, "Error stopping server", e);
            }
        }
    }
}
