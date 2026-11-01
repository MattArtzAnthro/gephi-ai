"""Tests that run git must never reach the repository they are run from.

A git hook runs with GIT_DIR, GIT_INDEX_FILE and similar variables pointing at the repository
being committed to. The pre-commit gate runs this suite, and several tests start git in a
temporary folder with os.environ passed through. From a linked worktree that once wrote fixture
commits into the worktree and set core.bare=true on the real repository. conftest.py removes
those variables before any test runs; this test commits from a linked worktree of a throwaway
repository, the way the hook does, and checks that the repository is left alone.
"""

import os
import subprocess
import sys
from pathlib import Path

MCP_SERVER = Path(__file__).resolve().parent.parent
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def _git(cwd, *args, env=None):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**clean, **IDENTITY, **(env or {})}).stdout.strip()


def test_a_hook_environment_cannot_reach_the_repository(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "f.txt").write_text("x\n")
    _git(main, "add", "f.txt")
    _git(main, "commit", "-q", "--no-verify", "-m", "base")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-q", "--detach", str(linked))
    head_before = _git(linked, "rev-parse", "HEAD")

    # What git exports to a hook run in a linked worktree.
    git_dir = _git(linked, "rev-parse", "--absolute-git-dir")
    hook_env = {"GIT_DIR": git_dir, "GIT_INDEX_FILE": str(Path(git_dir) / "index"),
                "GIT_PREFIX": ""}
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-cov",
         "tests/test_fix_tests_check.py"],
        cwd=MCP_SERVER, capture_output=True, text=True, timeout=300,
        env={**os.environ, **hook_env, "PYTHONPATH": str(MCP_SERVER)})

    assert _git(main, "config", "--bool", "--default", "false", "core.bare") == "false", run.stdout
    assert _git(linked, "rev-parse", "HEAD") == head_before, run.stdout
    assert run.returncode == 0, run.stdout + run.stderr
