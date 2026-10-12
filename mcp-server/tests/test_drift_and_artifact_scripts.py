"""check-drift.sh and verify-artifact.sh, each run in a throwaway repository.

Neither script may touch the network or the real checkout here. check-drift.sh gets a local bare
repository as its origin and stand-in curl and gh; verify-artifact.sh gets a stand-in uv whose
"build" drops a prepared wheel and sdist into place, so the checks it runs on the artifact are
exercised on contents chosen to pass or to fail.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _need(*tools):
    if os.name == "nt":
        pytest.skip("the release scripts run on macOS and Linux")
    for tool in tools:
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is not on PATH")


def _env(tmp_path, fake_bin):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        **os.environ,
        # A home of its own: no global git hooks or config, no real plugin installs.
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Ada Fennimore", "GIT_AUTHOR_EMAIL": "ada@example.org",
        "GIT_COMMITTER_NAME": "Ada Fennimore", "GIT_COMMITTER_EMAIL": "ada@example.org",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INDEX": "1",
    }


def _tool(fake_bin, name, script):
    path = fake_bin / name
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(0o755)


def _git(cwd, env, *args):
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


# ─── check-drift.sh ──────────────────────────────────────────────

LATEST = {"server": "9.1.0", "nbm": "9.0.2", "plugin": "9.1.0"}


def _drift_repo(tmp_path, pypi_status="200", release=True, asset=True):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True)
    _tool(fake_bin, "curl", f'echo "{pypi_status}"\n')
    asset_line = f'echo "gephi-ai-{LATEST["nbm"]}.nbm"' if asset else "true"
    _tool(fake_bin, "gh", f'case "$1" in\n  release) exit {0 if release else 1} ;;\n'
                          f'  api) {asset_line} ;;\nesac\n')
    env = _env(tmp_path, fake_bin)

    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    (work / "scripts").mkdir(parents=True)
    (work / "plugins/claude-code").mkdir(parents=True)
    shutil.copy2(REPO / "scripts/check-drift.sh", work / "scripts/check-drift.sh")
    (work / "plugins/claude-code/.mcp.json").write_text(json.dumps(
        {"mcpServers": {"gephi-ai": {"command": "uvx", "args": ["--from", "gephi-ai==9.1.0", "gephi-ai"]}}}))
    (work / "latest.json").write_text(json.dumps(LATEST))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=env, check=True)
    _git(work, env, "init", "-q", "-b", "main")
    _git(work, env, "add", ".")
    _git(work, env, "commit", "-q", "-m", "start")
    _git(work, env, "remote", "add", "origin", str(origin))
    _git(work, env, "push", "-q", "origin", "main")
    return work, env


def _drift(work, env):
    return subprocess.run(["bash", "scripts/check-drift.sh"], cwd=work, env=env,
                          capture_output=True, text=True, timeout=60)


def test_drift_check_passes_when_every_channel_agrees(tmp_path):
    _need("bash", "git", "python3")
    work, env = _drift_repo(tmp_path)

    run = _drift(work, env)

    assert run.returncode == 0, run.stdout + run.stderr
    assert "=== 0 issue(s) found ===" in run.stdout


def test_drift_check_fails_when_the_pinned_version_is_not_on_pypi(tmp_path):
    _need("bash", "git", "python3")
    work, env = _drift_repo(tmp_path, pypi_status="404")

    run = _drift(work, env)

    assert run.returncode == 1
    assert "DEAD ON INSTALL" in run.stdout and "gephi-ai==9.1.0" in run.stdout


def test_drift_check_fails_on_a_release_missing_or_without_its_plugin(tmp_path):
    _need("bash", "git", "python3")
    work, env = _drift_repo(tmp_path, release=False)
    run = _drift(work, env)
    assert run.returncode == 1
    assert "there is no release v9.1.0" in run.stdout

    work, env = _drift_repo(tmp_path / "second", asset=False)
    run = _drift(work, env)
    assert run.returncode == 1
    assert "missing asset gephi-ai-9.0.2.nbm" in run.stdout


def test_drift_check_fails_on_uncommitted_work_unpushed_commits_and_a_root_nbm(tmp_path):
    _need("bash", "git", "python3")
    work, env = _drift_repo(tmp_path)
    (work / "notes.txt").write_text("draft")
    _git(work, env, "add", "notes.txt")
    _git(work, env, "commit", "-q", "-m", "local only")
    (work / "gephi-ai-9.0.2.nbm").write_bytes(b"binary")

    run = _drift(work, env)

    assert run.returncode == 1
    assert "uncommitted changes present" in run.stdout
    assert "1 commit(s) not pushed" in run.stdout
    assert ".nbm at the repo root" in run.stdout


def test_drift_check_names_a_stale_installed_plugin(tmp_path):
    _need("bash", "git", "python3")
    work, env = _drift_repo(tmp_path)
    plugins = Path(env["HOME"]) / ".claude/plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps(
        {"plugins": {"gephi-network-analysis@gephi-ai": [{"version": "9.0.0"}]}}))

    run = _drift(work, env)

    assert run.returncode == 1
    assert "host installed_plugins.json is STALE (9.0.0 vs 9.1.0)" in run.stdout


# ─── verify-artifact.sh ──────────────────────────────────────────

GOOD_REGISTER = {"caveats": [{"id": "gephi-0001", "says": "A known defect.",
                              "verification": {"status": "unverified", "probe": "probe_x"}}]}

STUB_SERVER = '''
class _Tool:
    def __init__(self, name):
        self.name = name


class _Manager:
    def list_tools(self):
        return [_Tool("gephi_health_check"), _Tool("gephi_get_graph_stats")]


class _Mcp:
    _tool_manager = _Manager()


mcp = _Mcp()
'''

STUB_INTEGRITY = '''
import json
from pathlib import Path

REGISTER_PATH = Path(__file__).with_name("caveats.json")


def local_overlay_path():
    return REGISTER_PATH.with_name("caveats.local.json")


def load_register():
    return json.loads(REGISTER_PATH.read_text())["caveats"]
'''


def _wheel(path, register, extra=None):
    files = {"gephi_mcp.py": STUB_SERVER, "stats_integrity.py": STUB_INTEGRITY,
             "caveats.json": json.dumps(register), **(extra or {})}
    info = "gephi_ai-9.1.0.dist-info"
    files[f"{info}/METADATA"] = "Metadata-Version: 2.1\nName: gephi-ai\nVersion: 9.1.0\n"
    files[f"{info}/WHEEL"] = "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    files[f"{info}/RECORD"] = "".join(f"{name},,\n" for name in files) + f"{info}/RECORD,,\n"
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)


def _sdist(path, names):
    with tarfile.open(path, "w:gz") as t:
        for name in names:
            data = b"{}"
            member = tarfile.TarInfo(f"gephi_ai-9.1.0/{name}")
            member.size = len(data)
            t.addfile(member, io.BytesIO(data))


def _artifact_repo(tmp_path, register=GOOD_REGISTER, wheel_extra=None,
                   sdist_names=("caveats.json", "gephi_mcp.py"), readme="Two tools: 2 tools."):
    staged = tmp_path / "staged"
    staged.mkdir()
    _wheel(staged / "gephi_ai-9.1.0-py3-none-any.whl", register, wheel_extra)
    _sdist(staged / "gephi_ai-9.1.0.tar.gz", sdist_names)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _tool(fake_bin, "uv", f'mkdir -p dist && cp "{staged}"/* dist/\n')
    env = _env(tmp_path, fake_bin)
    work = tmp_path / "work"
    (work / "scripts").mkdir(parents=True)
    (work / "mcp-server").mkdir()
    shutil.copy2(REPO / "scripts/verify-artifact.sh", work / "scripts/verify-artifact.sh")
    (work / "README.md").write_text(readme)
    _git(work, env, "init", "-q", "-b", "main")
    return work, env


def _verify(work, env):
    return subprocess.run(["bash", "scripts/verify-artifact.sh"], cwd=work, env=env,
                          capture_output=True, text=True, timeout=180)


def test_a_clean_artifact_passes_and_is_stamped(tmp_path):
    _need("bash", "git", "python3")
    work, env = _artifact_repo(tmp_path)

    run = _verify(work, env)

    assert run.returncode == 0, run.stdout + run.stderr
    assert "Artifact verification passed." in run.stdout
    assert "README.md agrees (2)" in run.stdout
    assert (work / ".artifact-verified").exists()


def test_a_probe_overlay_in_the_sdist_fails_the_artifact(tmp_path):
    _need("bash", "git", "python3")
    work, env = _artifact_repo(tmp_path, sdist_names=("caveats.json", "caveats.local.json"))
    (work / ".artifact-verified").write_text("")

    run = _verify(work, env)

    assert run.returncode == 1
    assert "caveats.local.json is in the sdist" in run.stdout
    assert not (work / ".artifact-verified").exists(), "a failed run left the publish marker"


def test_a_register_carrying_a_verdict_fails_the_artifact(tmp_path):
    _need("bash", "git", "python3")
    stamped = {"caveats": [{"id": "gephi-0001", "says": "Reproduced on this Gephi on 2026-01-02.",
                            "verification": {"status": "reproduced", "checked_on": "2026-01-02"}}]}
    work, env = _artifact_repo(tmp_path, register=stamped)

    run = _verify(work, env)

    assert run.returncode == 1
    assert "the shipped register asserts verdicts for ['gephi-0001']" in run.stdout
    assert "a fresh install already asserts" in run.stdout


def test_a_probe_overlay_in_the_wheel_fails_the_artifact(tmp_path):
    _need("bash", "git", "python3")
    work, env = _artifact_repo(tmp_path, wheel_extra={"caveats.local.json": "{}"})

    run = _verify(work, env)

    assert run.returncode == 1
    assert "caveats.local.json is in the wheel" in run.stdout


def test_a_documented_tool_count_that_disagrees_fails_the_artifact(tmp_path):
    _need("bash", "git", "python3")
    work, env = _artifact_repo(tmp_path, readme="The server exposes 3 tools.")

    run = _verify(work, env)

    assert run.returncode == 1
    assert "README.md does not say 2 tools" in run.stdout
