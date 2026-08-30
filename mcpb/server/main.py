"""MCPB entry point: run the bundled gephi-ai server (stdio)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from gephi_mcp import mcp  # noqa: E402

if __name__ == "__main__":
    mcp.run()
