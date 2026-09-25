"""The release scripts run against a temporary copy of the files they touch, never the checkout.

bump-version.sh has to move every pin the Desktop bundle carries along with the server version,
and build-mcpb.sh has to refuse a version the bundle does not pin before it builds anything.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Everything bump-version.sh reads or writes, including its verification block.
BUMP_FILES = [
    "scripts/bump-version.sh",
    "mcp-server/pyproject.toml",
    "gephi-ai-plugin/pom.xml",
    "gephi-ai-plugin/src/main/java/org/gephi/plugins/mcp/api/GephiAPIServer.java",
    "plugins/claude-code/.claude-plugin/plugin.json",
    "plugins/claude-code/.mcp.json",
    "plugins/claude-code/skills/gephi/SKILL.md",
    "plugins/gephi-network-analysis/.mcp.json",
    "plugins/gephi-network-analysis/.codex-plugin/plugin.json",
    "plugins/gephi-network-analysis/skills/gephi/SKILL.md",
    "mcpb/manifest.json",
    "mcpb/pyproject.toml",
    "latest.json",
    "README.md",
    ".claude-plugin/marketplace.json",
]

BUILD_FILES = [
    "scripts/build-mcpb.sh",
    "mcpb/manifest.json",
    "mcpb/pyproject.toml",
]


def _need(tool):
    if shutil.which(tool) is None:
        pytest.skip(f"{tool} is not on PATH")


def _copy_tree(files, dest):
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)


def _server_version():
    text = (REPO / "mcp-server/pyproject.toml").read_text()
    return re.search(r'^version = "(\d+\.\d+\.\d+)"', text, re.M).group(1)


def test_bump_version_moves_every_bundle_pin(tmp_path):
    _need("bash")
    _need("python3")
    _copy_tree(BUMP_FILES, tmp_path)
    major, minor, patch = _server_version().split(".")
    new = f"{major}.{minor}.{int(patch) + 1}"

    run = subprocess.run(["bash", "scripts/bump-version.sh", "--server", new],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr

    assert json.loads((tmp_path / "mcpb/manifest.json").read_text())["version"] == new
    bundle = (tmp_path / "mcpb/pyproject.toml").read_text()
    assert re.search(r'^version = "(.+)"', bundle, re.M).group(1) == new
    assert re.search(r'"gephi-ai==([^"]+)"', bundle).group(1) == new
    for mcp_json in ("plugins/claude-code/.mcp.json", "plugins/gephi-network-analysis/.mcp.json"):
        args = json.loads((tmp_path / mcp_json).read_text())["mcpServers"]["gephi-mcp"]["args"]
        assert f"gephi-ai=={new}" in args, mcp_json


def test_build_mcpb_refuses_a_version_the_bundle_does_not_pin(tmp_path):
    _need("bash")
    _copy_tree(BUILD_FILES, tmp_path)
    # A stand-in npx that leaves a mark, so reaching the pack step is visible without node.
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    npx = fake_bin / "npx"
    npx.write_text('#!/bin/sh\ntouch "$(dirname "$0")/npx-was-called"\n')
    npx.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"}

    run = subprocess.run(["bash", "scripts/build-mcpb.sh", "0.0.0-not-pinned"],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert run.returncode != 0
    assert "does not pin gephi-ai==0.0.0-not-pinned" in run.stdout + run.stderr
    assert not (fake_bin / "npx-was-called").exists(), "the script reached npx"
    assert not (tmp_path / "dist").exists()
