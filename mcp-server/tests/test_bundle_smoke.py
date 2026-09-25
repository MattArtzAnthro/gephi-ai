"""The Claude Desktop bundle's entry point starts and serves the full tool set over stdio.

The server is launched with the manifest's own mcp_config, as Claude Desktop launches it. The
bundle pins a released gephi-ai, which may not be on PyPI yet on an unreleased branch, so the
test injects --no-project --with <this checkout's server> into that command; nothing else about
the command changes. Set GEPHI_AI_REQUIRE_BUNDLE_SMOKE to fail, not skip, when uv is missing.
"""
import json
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


def _desktop_command():
    """The manifest's command and args, with ${__dirname} filled in as Claude Desktop does."""
    config = json.loads((BUNDLE_DIR / "manifest.json").read_text())["server"]["mcp_config"]
    args = [a.replace("${__dirname}", str(BUNDLE_DIR)) for a in config["args"]]
    return config["command"], args


def _with_this_checkout(args):
    """Resolve the server from this checkout instead of the unpublished PyPI pin."""
    assert args[0] == "run", f"the manifest no longer launches with `uv run`: {args}"
    return ["run", "--no-project", "--with", str(SERVER_DIR), *args[1:]]


async def test_bundle_entry_point_serves_every_tool():
    command, args = _desktop_command()
    executable = shutil.which(command)
    if executable is None:
        reason = f"{command} is not on PATH; the Desktop bundle runs on the uv runtime"
        (pytest.fail if os.environ.get("GEPHI_AI_REQUIRE_BUNDLE_SMOKE") else pytest.skip)(reason)
    params = StdioServerParameters(
        command=executable,
        args=_with_this_checkout(args),
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
