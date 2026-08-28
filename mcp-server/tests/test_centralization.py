"""Freeman centralization: how centralised a whole network is, as one number.

gephi#984 asked for this in 2014 and never got an answer. Gephi can tell you which node is most
central; it cannot tell you how centralised the network is, which is the number you need to compare
one network against another rather than nodes within one.

Freeman's degree centralization is the observed concentration of degree over the most concentrated
possible arrangement on the same number of nodes, which is the star:

    C = sum(d_max - d_i) / ((n - 1) * (n - 2))

Every expected value below is computed by hand in the test that uses it.
"""

import pytest

from gephi_mcp_viewer.profile import freeman_degree_centralization, structural_profile


def star(n):
    """One hub joined to every other node. The maximally centralised graph."""
    return {"nodes": [{"key": f"n{i}"} for i in range(n)],
            "edges": [{"source": "n0", "target": f"n{i}"} for i in range(1, n)]}


def complete(n):
    """Every node joined to every other. The least centralised connected graph."""
    return {"nodes": [{"key": f"n{i}"} for i in range(n)],
            "edges": [{"source": f"n{i}", "target": f"n{j}"}
                      for i in range(n) for j in range(i + 1, n)]}


# ── The pure calculation ──

def test_a_star_is_maximally_centralised():
    """Hub has degree n-1, each of the n-1 leaves has degree 1.

    sum(d_max - d_i) = 0 + (n-1)*((n-1) - 1) = (n-1)(n-2), which is the denominator, so C = 1.
    """
    assert freeman_degree_centralization([4, 1, 1, 1, 1], n=5) == pytest.approx(1.0)


def test_a_complete_graph_is_not_centralised_at_all():
    """Every degree equals d_max, so the numerator is 0."""
    assert freeman_degree_centralization([4, 4, 4, 4, 4], n=5) == pytest.approx(0.0)


def test_a_ring_is_not_centralised_at_all():
    """Every node has degree 2. Uniform, so 0 like the complete graph, at a different density."""
    assert freeman_degree_centralization([2, 2, 2, 2, 2], n=5) == pytest.approx(0.0)


def test_a_star_with_an_isolate_sits_between_the_extremes():
    """n=5: hub 3, three leaves 1, one isolate 0. d_max = 3.

    numerator   = (3-3) + (3-1)*3 + (3-0) = 0 + 6 + 3 = 9
    denominator = (5-1)(5-2) = 12
    C = 9/12 = 0.75
    """
    assert freeman_degree_centralization([3, 1, 1, 1, 0], n=5) == pytest.approx(0.75)


def test_centralization_is_undefined_below_three_nodes():
    """The denominator (n-1)(n-2) is zero, and the measure has no meaning. Undefined, not zero."""
    assert freeman_degree_centralization([1, 1], n=2) is None
    assert freeman_degree_centralization([0], n=1) is None
    assert freeman_degree_centralization([], n=0) is None


def test_an_empty_graph_of_three_nodes_is_not_centralised():
    """Three nodes, no edges: all degrees 0, numerator 0. Defined, and zero."""
    assert freeman_degree_centralization([0, 0, 0], n=3) == pytest.approx(0.0)


# ── Wired into the profile ──

def test_the_profile_reports_centralization_for_a_star():
    profile = structural_profile(star(6))

    assert profile["centralization"]["degree"] == pytest.approx(1.0)


def test_the_profile_reports_zero_centralization_for_a_complete_graph():
    profile = structural_profile(complete(6))

    assert profile["centralization"]["degree"] == pytest.approx(0.0)


def test_the_profile_reports_centralization_as_none_when_undefined():
    two_nodes = {"nodes": [{"key": "a"}, {"key": "b"}],
                 "edges": [{"source": "a", "target": "b"}]}

    profile = structural_profile(two_nodes)

    assert profile["centralization"]["degree"] is None
