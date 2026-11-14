"""Another program answering on Gephi's port.

Port 8080 is a common default. When something else holds it, its error page reached the person as
if Gephi had said it ({"detail": "Not Found"}), with nothing pointing at GEPHI_API_URL.
"""

import httpx

import gephi_mcp


def _answer(monkeypatch, status, **body):
    async def fake(self, method, url, **kwargs):
        return httpx.Response(status, request=httpx.Request(method, url), **body)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake)


async def test_an_error_page_from_another_service_names_the_port_setting(monkeypatch):
    _answer(monkeypatch, 404, json={"detail": "Not Found"})

    out = await gephi_mcp.gephi.request("GET", "/health")

    assert out["success"] is False
    assert "GEPHI_API_URL" in out["error"] and gephi_mcp.gephi.base_url in out["error"]


async def test_a_non_json_error_from_another_service_names_the_port_setting(monkeypatch):
    _answer(monkeypatch, 404, text="<html>nginx</html>")

    out = await gephi_mcp.gephi.request("GET", "/health")

    assert out["success"] is False and "GEPHI_API_URL" in out["error"]


async def test_the_plugins_own_error_reply_is_passed_on(monkeypatch):
    _answer(monkeypatch, 400, json={"success": False, "error": "Unknown endpoint: /nope"})

    out = await gephi_mcp.gephi.request("GET", "/nope")

    assert out == {"success": False, "error": "Unknown endpoint: /nope"}
