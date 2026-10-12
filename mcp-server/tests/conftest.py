"""Shared test setup.

The caveat register is merged with this machine's probe verdicts (caveats.local.json, beside
the register and never committed). Tests read the shipped register alone, so a developer's local
probe run cannot make a test pass here and fail in CI, or the other way round. Tests that are
about the overlay point it at a file of their own.
"""

import pytest

import stats_integrity


@pytest.fixture(autouse=True)
def _shipped_register_only(monkeypatch, tmp_path_factory):
    absent = tmp_path_factory.getbasetemp() / "no-local-overlay.json"
    monkeypatch.setattr(stats_integrity, "local_overlay_path", lambda: absent)
    monkeypatch.setattr(stats_integrity, "_register_cache", None)
