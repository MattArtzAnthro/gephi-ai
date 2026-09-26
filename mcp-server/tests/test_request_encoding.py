"""
Request bodies carry node ids, labels, and attribute values, and people's names are not ASCII.
The Gephi plugin's HTTP server (NanoHTTPD) decodes a body in the charset its Content-Type names,
and as US-ASCII when it names none, so "Tomás" arrived as "Tom��s". Plugin builds from
this release read bodies as UTF-8 regardless; declaring the charset fixes older plugins too.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import gephi_mcp as g


class _Recorder(BaseHTTPRequestHandler):
    seen: dict = {}

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        _Recorder.seen = {"content_type": self.headers.get("Content-Type", ""), "raw": raw}
        body = b'{"success": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def recorder():
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


async def test_json_bodies_declare_utf8_and_carry_utf8_bytes(recorder):
    client = g.GephiClient(base_url=recorder)
    nodes = [{"id": "Tomás", "label": "Zoë Wójcik"}]

    result = await client.request("POST", "/graph/nodes/add", json_data={"nodes": nodes})

    assert result == {"success": True}
    seen = _Recorder.seen
    assert "charset=utf-8" in seen["content_type"].lower().replace(" ", "")
    assert json.loads(seen["raw"].decode("utf-8"))["nodes"] == nodes
