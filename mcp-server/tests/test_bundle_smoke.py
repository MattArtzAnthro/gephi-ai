"""The Claude Desktop bundle's entry point starts and serves the full tool set over stdio.

The bundle pins a released gephi-ai, which may not be on PyPI yet on an unreleased branch, so the
test runs the entry point with --no-project and installs this checkout's server with --with.
"""
import os
import shutil
from pathlib import Path

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import PaginatedRequestParams

REPO = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO / "mcp-server"
BUNDLE_DIR = REPO / "mcpb"

# The first run resolves and installs the server's dependencies, which can take a while.
TIMEOUT_SECONDS = 300


async def test_bundle_entry_point_serves_every_tool():
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH; the Desktop bundle runs on the uv runtime")
    params = StdioServerParameters(
        command=uv,
        args=["run", "--no-project", "--with", str(SERVER_DIR),
              "--directory", str(BUNDLE_DIR), "python", str(Path("src") / "server.py")],
        # The SDK passes only a minimal environment by default; the runner's uv settings
        # (UV_CACHE_DIR and the like) have to reach uv, on Windows especially.
        env={**os.environ},
    )
    with anyio.fail_after(TIMEOUT_SECONDS):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = []
                cursor = None
                while True:
                    page = await session.list_tools(
                        params=PaginatedRequestParams(cursor=cursor) if cursor else None)
                    tools.extend(page.tools)
                    cursor = page.next_cursor
                    if not cursor:
                        break

    assert init.server_info.name == "gephi_mcp"
    assert len(tools) == 113, f"expected 113 tools, found {len(tools)}"
