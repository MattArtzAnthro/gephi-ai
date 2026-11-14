"""Every endpoint the server calls is one the Gephi plugin serves.

The server and the plugin are released separately and people update them at different times
(RELEASING.md, "The server and the Gephi plugin update at different times"). A plugin change
that removes or renames an endpoint the server still calls breaks every tool behind it, and no
unit test sees it, because the unit suite replaces the HTTP client. This reads both sides from
source: the paths `gephi_mcp.py` requests, and the paths the plugin's router answers.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "mcp-server" / "gephi_mcp.py"
ROUTER = (REPO / "gephi-ai-plugin" / "src" / "main" / "java" / "org" / "gephi" / "plugins"
          / "mcp" / "api" / "GephiAPIServer.java")

_PATH = r"(/[A-Za-z_/\-]+)"


def server_calls(source: str) -> set[str]:
    """Paths passed to gephi.request, e.g. request("POST", "/layout/run", ...)."""
    return set(re.findall(r'"(?:GET|POST|PUT|DELETE)",\s*f?"' + _PATH + '"', source))


def plugin_routes(source: str) -> set[str]:
    """Paths the router matches, e.g. "/layout/run".equals(uri)."""
    return set(re.findall('"' + _PATH + r'"\.equals\(uri\)', source))


def unserved(calls: set[str], routes: set[str]) -> list[str]:
    return sorted(calls - routes)


def test_the_plugin_serves_every_endpoint_the_server_calls():
    calls = server_calls(SERVER.read_text(encoding="utf-8"))
    routes = plugin_routes(ROUTER.read_text(encoding="utf-8"))
    # Guards against a pattern that stops matching and passes on two empty sets.
    assert len(calls) >= 80, f"only {len(calls)} server calls found; the pattern has drifted"
    assert len(routes) >= len(calls)
    assert unserved(calls, routes) == []


def test_a_removed_or_renamed_endpoint_is_reported():
    server = 'await gephi.request("POST", "/layout/run", json_data=body)\n' \
             'await gephi.request("GET", "/graph/columns", params=p)'
    router = 'if ("/layout/start".equals(uri)) {}\nif ("/graph/columns".equals(uri)) {}'
    assert unserved(server_calls(server), plugin_routes(router)) == ["/layout/run"]
