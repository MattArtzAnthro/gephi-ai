"""The Lean model in formal/GephiModel/Endpoints.lean proves its theorems about three lists of
endpoint prefixes. This holds stats_integrity's tuples to those lists, so the proofs speak of
the code that ships. It needs no Lean."""

import re
from pathlib import Path

import stats_integrity

MODEL = Path(__file__).resolve().parents[2] / "formal" / "GephiModel" / "Endpoints.lean"


def lean_list(name: str) -> tuple[str, ...]:
    body = re.search(rf"def {name} : List String := \[(.*?)\]", MODEL.read_text(encoding="utf-8"),
                     re.S)
    assert body, f"{name} not found in {MODEL}"
    return tuple(re.findall(r'"([^"]*)"', body.group(1)))


def test_the_model_proves_over_the_prefixes_the_server_uses():
    assert lean_list("nonStructural") == stats_integrity._NON_STRUCTURAL
    assert lean_list("replacesPrefixes") == stats_integrity._REPLACES_GRAPH
    assert lean_list("keepsGraph") == stats_integrity._KEEPS_GRAPH


def test_a_changed_prefix_would_be_caught(monkeypatch):
    monkeypatch.setattr(stats_integrity, "_REPLACES_GRAPH",
                        stats_integrity._REPLACES_GRAPH + ("/layout/reset",))
    assert lean_list("replacesPrefixes") != stats_integrity._REPLACES_GRAPH
