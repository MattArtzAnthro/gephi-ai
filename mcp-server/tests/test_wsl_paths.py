"""The server runs under WSL while Gephi runs on Windows.

The two share the files but not the paths: a server-side /tmp path handed to a Windows Gephi is
read as C:\\tmp, so Gephi wrote every export (and the temporary GEXF behind gephi_visual_qa,
gephi_label_clusters and gephi_view_graph) where the server never looks. Under WSL, with a Gephi
that reports a Windows os, the client rewrites each "file" path to the Windows form of the same
file: /mnt/<drive>/... becomes <DRIVE>:\\..., any other absolute path \\\\wsl$\\<distro>\\...
"""

from __future__ import annotations

import httpx

import gephi_mcp
from wsl_paths import windows_path


def test_a_mounted_windows_drive_becomes_a_drive_letter_path():
    assert windows_path("/mnt/c/Users/me/map.png", "Ubuntu") == "C:\\Users\\me\\map.png"


def test_a_linux_path_becomes_a_wsl_share_path():
    assert windows_path("/tmp/qa.gexf", "Ubuntu-26.04") == "\\\\wsl$\\Ubuntu-26.04\\tmp\\qa.gexf"


def test_a_relative_or_windows_path_is_left_alone():
    assert windows_path("map.png", "Ubuntu") == "map.png"
    assert windows_path("C:\\maps\\map.png", "Ubuntu") == "C:\\maps\\map.png"


def _fake_gephi(monkeypatch, gephi_os):
    sent = []

    async def fake_request(self, method, url, params=None, json=None, headers=None):
        if url.endswith("/health"):
            body = {"success": True, "service": "Gephi AI API"}
            if gephi_os:
                body["os"] = gephi_os
            return httpx.Response(200, json=body, request=httpx.Request(method, url))
        sent.append(json)
        return httpx.Response(200, json={"success": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return sent


async def test_file_paths_are_rewritten_for_a_windows_gephi_under_wsl(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-26.04")
    sent = _fake_gephi(monkeypatch, "Windows 11")
    client = gephi_mcp.GephiClient("http://127.0.0.1:1")
    await client.request("POST", "/export/gexf", json_data={"file": "/tmp/qa.gexf"})
    assert sent == [{"file": "\\\\wsl$\\Ubuntu-26.04\\tmp\\qa.gexf"}]


async def test_file_paths_are_untouched_for_a_linux_gephi_under_wsl(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-26.04")
    sent = _fake_gephi(monkeypatch, "Linux")
    client = gephi_mcp.GephiClient("http://127.0.0.1:1")
    await client.request("POST", "/export/gexf", json_data={"file": "/tmp/qa.gexf"})
    assert sent == [{"file": "/tmp/qa.gexf"}]


async def test_file_paths_are_untouched_outside_wsl(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    sent = _fake_gephi(monkeypatch, "Windows 11")
    client = gephi_mcp.GephiClient("http://127.0.0.1:1")
    await client.request("POST", "/export/gexf", json_data={"file": "/tmp/qa.gexf"})
    assert sent == [{"file": "/tmp/qa.gexf"}]
