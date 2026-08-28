"""Rendering a legend as SVG, so an exported map explains itself without its author present.

Gephi has never shipped a legend. gephi/gephi#511 asked for one in 2012 and the request has been
made again in three other repositories since. It is hard in the application because a legend has
to be reconstructed from the appearance model after the fact, and the intent behind a mapping is
not stored. It is easy here because the mapping was a decision, and the decision was recorded.

SVG rather than a raster format: it is text, so it needs no imaging dependency, and it is what a
figure destined for print wants anyway.
"""

import re

import defusedxml.ElementTree as ET  # noqa: N817 — stdlib-conventional alias; stdlib ET is XXE-vulnerable

from legend import legend_document, legend_fragment

PARTITION = {"channel": "node colour", "column": "Modularity Class",
             "groups": {"Editors": "#4e79a7", "Reviewers": "#e15759"}}
SIZE = {"channel": "node size", "column": "Degree", "range": [10, 50]}
RANKING = {"channel": "node colour", "column": "PageRank",
           "palette": ["#f7fbff", "#08306b"]}


def test_nothing_to_explain_produces_no_legend():
    """An empty legend box is worse than none: it implies the map has no encoding."""
    assert legend_fragment([]) is None
    assert legend_document([]) is None


def test_a_partition_legend_names_its_column_and_every_group():
    svg = legend_fragment([PARTITION])

    assert "Modularity Class" in svg
    assert "Editors" in svg and "Reviewers" in svg


def test_a_partition_legend_draws_a_swatch_in_each_group_colour():
    svg = legend_fragment([PARTITION])

    assert "#4e79a7" in svg and "#e15759" in svg


def test_a_size_legend_reports_the_range_it_maps_onto():
    svg = legend_fragment([SIZE])

    assert "Degree" in svg
    assert "10" in svg and "50" in svg


def test_a_ranking_legend_draws_a_gradient_between_its_palette_ends():
    svg = legend_fragment([RANKING])

    assert "linearGradient" in svg
    assert "#f7fbff" in svg and "#08306b" in svg


def test_several_channels_all_appear():
    svg = legend_fragment([PARTITION, SIZE])

    assert "Modularity Class" in svg and "Degree" in svg


def test_a_standalone_legend_is_a_parseable_svg_document():
    doc = legend_document([PARTITION, SIZE])

    root = ET.fromstring(doc)
    assert root.tag.endswith("svg")
    assert root.get("width") and root.get("height")


def test_the_fragment_parses_as_xml_so_it_can_be_spliced_into_an_export():
    fragment = legend_fragment([PARTITION, SIZE, RANKING])

    root = ET.fromstring(fragment)
    assert root.tag.endswith("g")


# ── Values come from user data and must never be able to break the document ──

def test_a_column_name_containing_markup_is_escaped_not_interpreted():
    hostile = {"channel": "node colour", "column": "<script>alert(1)</script>",
               "groups": {"a": "#111111"}}

    svg = legend_fragment([hostile])

    assert "<script>" not in svg
    ET.fromstring(svg)


def test_an_ampersand_in_a_group_name_does_not_break_the_document():
    awkward = {"channel": "node colour", "column": "Team",
               "groups": {"R & D": "#111111"}}

    svg = legend_fragment([awkward])

    ET.fromstring(svg)
    assert "R &amp; D" in svg


def test_a_colour_that_is_not_a_colour_is_refused_rather_than_written_out():
    """Attribute values are the other injection surface, and a bad fill silently voids the SVG."""
    hostile = {"channel": "node colour", "column": "Team",
               "groups": {"a": '"/><script>x</script>'}}

    svg = legend_fragment([hostile])

    assert "<script>" not in svg
    ET.fromstring(svg)


def test_the_legend_grows_with_the_number_of_groups():
    small = legend_document([{"channel": "node colour", "column": "T",
                              "groups": {"a": "#111111"}}])
    large = legend_document([{"channel": "node colour", "column": "T",
                              "groups": {str(i): "#111111" for i in range(12)}}])

    def height(doc):
        return float(re.search(r'height="([0-9.]+)"', doc).group(1))

    assert height(large) > height(small), "twelve groups must not overflow a one-group box"
