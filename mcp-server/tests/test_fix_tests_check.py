"""scripts/check-fix-tests.sh warns about fix commits that change no test.

Every fix should carry a test that fails without it. The check reads the commits of a
pull request and names each fix commit that touches no test file.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check-fix-tests.sh"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                        "GIT_CONFIG_GLOBAL": os.devnull})


def _commit(repo, path, subject):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(target.read_text() + "x\n" if target.exists() else "x\n")
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "--no-verify", "-m", subject)


@pytest.fixture
def repo(tmp_path):
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("the check runs under bash on macOS and Linux")
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "README.md", "chore: start")
    return tmp_path


def _run(repo, env=None):
    return subprocess.run(["bash", str(SCRIPT), "HEAD~3", "HEAD"], cwd=repo, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def test_a_fix_without_a_test_is_named_and_one_with_a_test_is_not(repo):
    _commit(repo, "mcp-server/gephi_mcp.py", "fix: round the size cap")
    _commit(repo, "gephi-ai-plugin/src/test/java/A.java", "fix(plugin): release the lock in finally")
    _commit(repo, "README.md", "docs: explain the cap")

    run = _run(repo, {"GITHUB_ACTIONS": ""})

    assert run.returncode == 0, run.stderr
    assert "round the size cap" in run.stdout
    assert "release the lock" not in run.stdout
    assert "explain the cap" not in run.stdout
    assert "1 fix commit(s) without a test change." in run.stdout


def test_in_github_actions_it_is_an_annotation(repo):
    _commit(repo, "mcp-server/gephi_mcp.py", "fix: round the size cap")
    _commit(repo, "README.md", "docs: a")
    _commit(repo, "README.md", "docs: b")

    run = _run(repo, {"GITHUB_ACTIONS": "true"})

    assert "::warning title=Fix without a test::" in run.stdout


def test_every_test_folder_counts(repo):
    _commit(repo, "mcp-server/tests/test_cap.py", "fix: a")
    _commit(repo, "plugins/gephi-network-analysis/tests/test_x.py", "fix: b")
    _commit(repo, "gephi-ai-plugin/src/test/java/B.java", "fix: c")

    run = _run(repo, {"GITHUB_ACTIONS": ""})

    assert "0 fix commit(s) without a test change." in run.stdout
