"""Shared test setup.

The caveat register is merged with this machine's probe verdicts (caveats.local.json, beside
the register and never committed). Tests read the shipped register alone, so a developer's local
probe run cannot make a test pass here and fail in CI, or the other way round. Tests that are
about the overlay point it at a file of their own.

Git's repository-locating variables are removed before any test runs. A git hook exports them
(the pre-commit gate runs this suite), and tests that start git in a temporary folder pass
os.environ through, so from a linked worktree they once committed fixtures into the worktree and
set core.bare=true on the real repository. test_git_env_isolation.py guards this.
"""

import os

import pytest

import stats_integrity

for _name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR",
              "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
              "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM"):
    os.environ.pop(_name, None)


@pytest.fixture(autouse=True)
def _shipped_register_only(monkeypatch, tmp_path_factory):
    absent = tmp_path_factory.getbasetemp() / "no-local-overlay.json"
    monkeypatch.setattr(stats_integrity, "local_overlay_path", lambda: absent)
    monkeypatch.setattr(stats_integrity, "_register_cache", None)
