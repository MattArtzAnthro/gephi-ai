"""The release scripts run against a temporary copy of the files they touch, never the checkout.

bump-version.sh has to move every pin the Desktop bundle carries along with the server version,
and build-mcpb.sh has to refuse a version the bundle does not pin before it builds anything.
"""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
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

# The mcpb packer the build runs, pinned so every build packs the same way.
MCPB_VERSION = "2.1.2"

BUILD_FILES = [
    "scripts/build-mcpb.sh",
    "mcpb/manifest.json",
    "mcpb/pyproject.toml",
]


def _need(tool):
    if os.name == "nt":
        pytest.skip("the release scripts run on macOS and Linux; WSL bash cannot see "
                    "Windows temp paths")
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
        args = json.loads((tmp_path / mcp_json).read_text())["mcpServers"]["gephi-ai"]["args"]
        assert f"gephi-ai=={new}" in args, mcp_json


def _pom_gephi_version(root):
    return re.search(r"<gephi.version>([^<]+)</gephi.version>",
                     (root / "gephi-ai-plugin/pom.xml").read_text()).group(1)


def test_a_java_bump_records_the_gephi_the_plugin_needs(tmp_path):
    # Gephi refuses a plugin built for a newer Gephi, so the health check has to know the
    # minimum before advising an update. It comes from the POM, the build's source of truth.
    _need("bash")
    _need("python3")
    _copy_tree(BUMP_FILES, tmp_path)
    latest = json.loads((tmp_path / "latest.json").read_text())
    latest["nbm_needs_gephi"] = "0.0.1"
    (tmp_path / "latest.json").write_text(json.dumps(latest))
    major, minor, patch = latest["nbm"].split(".")

    run = subprocess.run(["bash", "scripts/bump-version.sh", "--java", f"{major}.{minor}.{int(patch) + 1}"],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)

    assert run.returncode == 0, run.stdout + run.stderr
    written = json.loads((tmp_path / "latest.json").read_text())["nbm_needs_gephi"]
    assert written == _pom_gephi_version(tmp_path)


def test_a_java_bump_moves_the_skills_plugin_minimum_even_when_it_was_stale(tmp_path):
    _need("bash")
    _need("python3")
    _copy_tree(BUMP_FILES, tmp_path)
    skill = tmp_path / "plugins/claude-code/skills/gephi/SKILL.md"
    skill.write_text(re.sub(r"Gephi AI Plugin \([0-9.]+\+\)", "Gephi AI Plugin (0.0.1+)", skill.read_text()))
    major, minor, patch = json.loads((tmp_path / "latest.json").read_text())["nbm"].split(".")
    new = f"{major}.{minor}.{int(patch) + 1}"

    run = subprocess.run(["bash", "scripts/bump-version.sh", "--java", new],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)

    assert run.returncode == 0, run.stdout + run.stderr
    assert f"Gephi AI Plugin ({new}+)" in skill.read_text()


def test_the_bump_check_catches_a_stale_gephi_minimum(tmp_path):
    _need("bash")
    _need("python3")
    _copy_tree(BUMP_FILES, tmp_path)
    latest = json.loads((tmp_path / "latest.json").read_text())
    latest["nbm_needs_gephi"] = "0.0.1"
    (tmp_path / "latest.json").write_text(json.dumps(latest))

    run = subprocess.run(["bash", "scripts/bump-version.sh"],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)

    assert run.returncode != 0
    assert "latest.json nbm_needs_gephi" in run.stdout


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


def _fake_tools(tmp_path, uv_exit=0):
    """Stand-in uv and npx that append their argv to one log, so the call order is visible."""
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    log = tmp_path / "calls.log"
    for name, code in (("uv", uv_exit), ("npx", 0)):
        tool = fake_bin / name
        tool.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit {code}\n')
        tool.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"}
    return env, log


def _pinned_version():
    return json.loads((REPO / "mcpb/manifest.json").read_text())["version"]


def test_build_mcpb_locks_the_bundle_before_packing(tmp_path):
    _need("bash")
    _copy_tree(BUILD_FILES, tmp_path)
    env, log = _fake_tools(tmp_path)
    version = _pinned_version()

    run = subprocess.run(["bash", "scripts/build-mcpb.sh", version],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    calls = log.read_text().splitlines()
    assert calls == [
        "uv lock --directory mcpb",
        f"npx -y @anthropic-ai/mcpb@{MCPB_VERSION} pack mcpb dist/gephi-ai-{version}.mcpb",
    ]


def test_build_mcpb_stops_when_the_lock_fails(tmp_path):
    _need("bash")
    _copy_tree(BUILD_FILES, tmp_path)
    env, log = _fake_tools(tmp_path, uv_exit=1)
    version = _pinned_version()

    run = subprocess.run(["bash", "scripts/build-mcpb.sh", version],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert run.returncode != 0
    out = run.stdout + run.stderr
    assert "could not lock the bundle's dependencies" in out
    assert f"gephi-ai=={version}" in out and "PyPI" in out
    assert log.read_text().splitlines() == ["uv lock --directory mcpb"], "the script reached npx"


def test_build_mcpb_stops_when_uv_is_missing(tmp_path):
    _need("bash")
    _copy_tree(BUILD_FILES, tmp_path)
    env, log = _fake_tools(tmp_path)
    (tmp_path / "fake-bin" / "uv").unlink()
    # Only the fake tools and the system directories, so a real uv cannot be found either.
    env["PATH"] = os.pathsep.join([str(tmp_path / "fake-bin"), "/usr/bin", "/bin"])
    if any(Path(d, "uv").exists() for d in ("/usr/bin", "/bin")):
        pytest.skip("uv is installed in a system directory")

    run = subprocess.run(["bash", "scripts/build-mcpb.sh", _pinned_version()],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert run.returncode != 0
    assert "uv is not on PATH" in run.stdout + run.stderr
    assert not log.exists(), "the script reached npx"


def _ignore_patterns():
    lines = (REPO / "mcpb/.mcpbignore").read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def test_mcpbignore_ships_the_lock():
    for pattern in _ignore_patterns():
        assert not fnmatch.fnmatch("uv.lock", pattern.rstrip("/")), pattern


def test_gitignore_ignores_the_bundle_lock():
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    run = subprocess.run(["git", "check-ignore", "-q", "--no-index", "mcpb/uv.lock"],
                         cwd=REPO, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, "mcpb/uv.lock is not gitignored"


def _pypi_reachable():
    try:
        with urllib.request.urlopen("https://pypi.org/simple/gephi-ai/", timeout=10) as r:
            return r.status == 200
    except OSError:
        return False


def test_real_build_ships_the_locked_bundle(tmp_path):
    """Packs a temp copy with the real uv and npx, which reach PyPI and npm, so it runs only
    when GEPHI_AI_REQUIRE_REAL_BUILD=1; then anything that stops it is a failure."""
    if os.environ.get("GEPHI_AI_REQUIRE_REAL_BUILD") != "1":
        pytest.skip("uses the network; set GEPHI_AI_REQUIRE_REAL_BUILD=1 to run it")
    missing = [t for t in ("bash", "uv", "npx") if shutil.which(t) is None]
    if os.name == "nt":
        pytest.fail("the release scripts run on macOS and Linux")
    if missing:
        pytest.fail(f"{', '.join(missing)} not on PATH")
    if not _pypi_reachable():
        pytest.fail("PyPI is unreachable")

    _copy_tree(BUILD_FILES + ["mcpb/.mcpbignore", "mcpb/src/server.py"], tmp_path)
    version = _pinned_version()
    run = subprocess.run(["bash", "scripts/build-mcpb.sh", version],
                         cwd=tmp_path, capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stdout + run.stderr

    bundle = tmp_path / "dist" / f"gephi-ai-{version}.mcpb"
    with zipfile.ZipFile(bundle) as z:
        names = {n for n in z.namelist() if not n.endswith("/")}
        lock = z.read("uv.lock").decode()
    assert names == {"manifest.json", "pyproject.toml", "src/server.py", "uv.lock"}
    assert f'name = "gephi-ai"\nversion = "{version}"' in lock


def test_mcpbignore_has_no_server_line():
    assert "server/" not in _ignore_patterns()


def test_manifest_is_in_bump_format():
    raw = (REPO / "mcpb/manifest.json").read_text()
    assert raw == json.dumps(json.loads(raw), indent=2) + "\n"


def test_bump_changes_only_the_manifest_version_line(tmp_path):
    _need("bash")
    _need("python3")
    _copy_tree(BUMP_FILES, tmp_path)
    old = (tmp_path / "mcpb/manifest.json").read_text().splitlines()
    major, minor, patch = _server_version().split(".")
    new_version = f"{major}.{minor}.{int(patch) + 1}"

    run = subprocess.run(["bash", "scripts/bump-version.sh", "--server", new_version],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr

    new = (tmp_path / "mcpb/manifest.json").read_text().splitlines()
    assert set(old) - set(new) == {f'  "version": "{_server_version()}",'}
    assert set(new) - set(old) == {f'  "version": "{new_version}",'}
    assert len(old) == len(new)
