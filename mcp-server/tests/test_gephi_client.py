"""What the agent is told when Gephi is down, slow, or refuses a request.

GephiClient.request turns every transport failure into a JSON error the tools pass on. These
tests drive it against real local sockets (never port 8080, where a user's Gephi listens): a port
nothing listens on, a listener that never answers, and a small HTTP server that answers with an
error status.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import gephi_mcp


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def silent_listener():
    """A socket that accepts connections and never sends a byte."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    held = []
    stop = threading.Event()

    def accept():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
                held.append(conn)
            except OSError:
                continue

    t = threading.Thread(target=accept, daemon=True)
    t.start()
    yield sock.getsockname()[1]
    stop.set()
    t.join(2)
    for c in held:
        c.close()
    sock.close()


class _Handler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, str, str]] = {}

    def _answer(self):
        status, ctype, body = self.routes[self.path]
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _answer  # noqa: N815 (the name http.server dispatches to)
    do_POST = _answer  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.fixture
def http_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


async def test_gephi_not_running_is_reported_with_what_to_do():
    client = gephi_mcp.GephiClient(f"http://127.0.0.1:{_free_port()}")

    out = await client.request("GET", "/health")

    assert out["success"] is False
    assert "Cannot connect to Gephi" in out["error"]
    assert "running" in out["error"]


async def test_the_health_tool_passes_the_connection_error_on(monkeypatch):
    monkeypatch.setattr(gephi_mcp, "gephi", gephi_mcp.GephiClient(f"http://127.0.0.1:{_free_port()}"))

    out = json.loads(await gephi_mcp.gephi_health_check())

    assert out["success"] is False
    assert "Cannot connect to Gephi" in out["error"]
    assert "server_version" not in out


async def test_a_slow_gephi_is_reported_as_possibly_still_running(silent_listener):
    client = gephi_mcp.GephiClient(f"http://127.0.0.1:{silent_listener}")

    out = await client.request("POST", "/layout/run", json_data={"algorithm": "x"}, timeout=0.3)

    assert out == {"success": False, "error": gephi_mcp.TIMEOUT_ERROR}
    assert gephi_mcp._timed_out(out)


async def test_a_refusal_with_a_json_body_is_passed_on_as_gephi_wrote_it(http_server):
    _Handler.routes = {"/graph/node/get/zz": (
        400, "application/json", json.dumps({"success": False, "error": "Node not found: zz"}))}
    client = gephi_mcp.GephiClient(f"http://127.0.0.1:{http_server}")

    out = await client.request("GET", "/graph/node/get/zz")

    assert out == {"success": False, "error": "Node not found: zz"}


async def test_an_error_page_that_is_not_json_is_reported_with_its_status(http_server):
    _Handler.routes = {"/health": (502, "text/html", "<h1>Bad Gateway</h1>")}
    client = gephi_mcp.GephiClient(f"http://127.0.0.1:{http_server}")

    out = await client.request("GET", "/health")

    assert out["success"] is False
    assert out["error"].startswith("HTTP 502")
    assert "Bad Gateway" in out["error"]


async def test_a_success_status_with_a_body_that_is_not_json_is_a_request_failure(http_server):
    _Handler.routes = {"/health": (200, "text/plain", "not json")}
    client = gephi_mcp.GephiClient(f"http://127.0.0.1:{http_server}")

    out = await client.request("GET", "/health")

    assert out["success"] is False
    assert out["error"].startswith("Request failed")


async def test_a_body_is_sent_as_utf8_json():
    seen = {}

    class Capture(_Handler):
        def do_POST(self):
            seen["type"] = self.headers.get("Content-Type")
            seen["body"] = self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8")
            self.routes = {self.path: (200, "application/json", '{"success": true}')}
            self._answer()

    server = HTTPServer(("127.0.0.1", 0), Capture)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        client = gephi_mcp.GephiClient(f"http://127.0.0.1:{server.server_address[1]}")
        out = await client.request("POST", "/graph/node/label", json_data={"id": "a", "label": "Wójcik"})
    finally:
        server.shutdown()
        server.server_close()

    assert out == {"success": True}
    assert seen["type"] == "application/json; charset=utf-8"
    assert json.loads(seen["body"]) == {"id": "a", "label": "Wójcik"}
