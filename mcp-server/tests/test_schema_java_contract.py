"""Every value a tool offers for a fixed-choice parameter is one the Java code accepts.

The schema enum comes from the Python Literal types; the plugin decides what it accepts. They
once disagreed: gephi_apply_filters offered action "visible" and /filter/combine answered
"Unknown action: visible". This test reads the Java source text, so it needs no Gephi and no
build, and it compares the two for every enum parameter in the live tool schema.

A value counts as accepted when the receiving Java method names it in a `case "x":` label or an
equals / equalsIgnoreCase check, or when the table below lists it as the fall-through branch
(for example target "node", which every method treats as "anything that is not edge")."""
import re
from pathlib import Path

import gephi_mcp

JAVA = (Path(__file__).resolve().parents[2] / "gephi-ai-plugin" / "src" / "main" / "java"
        / "org" / "gephi" / "plugins" / "mcp" / "service" / "GephiControlService.java")

# (tool, parameter) -> (Java methods that receive and check it, values the code accepts by
# falling through its default branch). Methods are searched together, because a handler may pass
# the value on to a helper.
_TABLE_TARGET = (["tableFor", "getColumns"], {"node"})
JAVA_CONTRACT = {
    ("gephi_get_columns", "target"): (["getColumns"], {"node"}),
    ("gephi_add_column", "type"): (["typeStringToClass"], set()),
    ("gephi_add_column", "target"): (["addColumnToModel"], {"node"}),
    ("gephi_find_shortest_path", "weighting"): (["findShortestPath"], set()),
    ("gephi_apply_filter", "action"): (["applyFilter"], set()),
    ("gephi_apply_filters", "combine"): (["applyFilters"], set()),
    ("gephi_apply_filters", "action"): (["applyFilters"], set()),
    ("gephi_set_time_from_columns", "target"): _TABLE_TARGET,
    ("gephi_edit_column", "action"): (["editColumn"], set()),
    ("gephi_edit_column", "target"): _TABLE_TARGET,
    ("gephi_edit_column", "type"): (["typeStringToClass"], set()),
    ("gephi_column_value_frequencies", "target"): (["columnValueFrequenciesCore"], {"node"}),
    ("gephi_detect_duplicates", "target"): (["detectDuplicatesCore", "elementsFor", "tableFor"], {"node"}),
    ("gephi_create_regex_column", "target"): _TABLE_TARGET,
    ("gephi_export_csv", "target"): (["buildCsv"], {"nodes"}),
    ("gephi_focus_view", "mode"): (["focusView"], set()),
    ("gephi_set_selection_mode", "mode"): (["setSelectionMode"], set()),
    ("gephi_import_gexf", "mode"): (["loadContainer"], set()),
    ("gephi_import_graphml", "mode"): (["loadContainer"], set()),
    ("gephi_import_csv", "mode"): (["loadContainer"], set()),
    ("gephi_import_file", "mode"): (["loadContainer"], set()),
    ("gephi_generate_graph", "model"): (["generateGraph"], set()),
}
# Enum parameters the Python server resolves itself and never sends to Java.
PYTHON_ONLY = {
    ("gephi_similarity_layout", "projection"): "the projection runs in Python; only positions go to Gephi",
    ("gephi_similarity_layout", "basis"): "the basis runs in Python; only positions go to Gephi",
}


def _enum(schema):
    if "enum" in schema:
        return schema["enum"]
    for option in schema.get("anyOf", []):
        if "enum" in option:
            return option["enum"]
    return None


def offered_values():
    """{(tool, parameter): [values]} for every enum parameter in the live tool schema."""
    found = {}
    for tool in gephi_mcp.mcp._tool_manager.list_tools():
        for param, schema in tool.parameters.get("properties", {}).items():
            values = _enum(schema)
            if values:
                found[(tool.name, param)] = list(values)
    return found


def _method_bodies(source, name):
    """The text of every method or overload called `name`, up to its closing brace."""
    start = re.compile(rf"^    (?!return )(?:[\w<>\[\].?, ]+ )?{re.escape(name)}\(", re.MULTILINE)
    bodies = []
    for m in start.finditer(source):
        end = source.find("\n    }\n", m.end())
        bodies.append(source[m.start(): end if end != -1 else len(source)])
    return bodies


def accepted_literals(source, methods):
    text = "\n".join(b for name in methods for b in _method_bodies(source, name))
    assert text, f"no Java method found for {methods}; the table is out of date"
    found = set(re.findall(r'case "([^"]+)"', text))
    found |= set(re.findall(r'"([^"]+)"\s*\.equals(?:IgnoreCase)?\(', text))
    found |= set(re.findall(r'\.equals(?:IgnoreCase)?\(\s*"([^"]+)"\s*\)', text))
    return found


def rejected_by_java(offered, source):
    """{'tool.param': [values Java does not accept]} for the offered values."""
    bad = {}
    for key, values in offered.items():
        if key in PYTHON_ONLY:
            continue
        methods, fallthrough = JAVA_CONTRACT[key]
        accepted = accepted_literals(source, methods) | fallthrough
        missing = [v for v in values if v not in accepted]
        if missing:
            bad[f"{key[0]}.{key[1]}"] = missing
    return bad


def test_every_value_a_tool_offers_is_accepted_by_the_java_endpoint():
    offered = offered_values()
    assert rejected_by_java(offered, JAVA.read_text(encoding="utf-8")) == {}


def test_every_enum_parameter_is_mapped_to_its_java_method():
    # A new Literal parameter must be added to JAVA_CONTRACT (or to PYTHON_ONLY with a reason),
    # so it cannot ship unchecked. Stale rows are caught too.
    offered = set(offered_values())
    assert offered - set(JAVA_CONTRACT) - set(PYTHON_ONLY) == set(), "enum parameters with no mapping"
    assert (set(JAVA_CONTRACT) | set(PYTHON_ONLY)) - offered == set(), "mapped parameters that no longer exist"
    assert len(PYTHON_ONLY) <= 3, "Python-only enums should stay rare; most reach Java"


def test_the_contract_check_can_fail():
    # The old defect: the combining tool offered "visible", which /filter/combine refuses.
    offered = offered_values()
    offered[("gephi_apply_filters", "action")] = ["select", "visible", "new_workspace", "column"]
    bad = rejected_by_java(offered, JAVA.read_text(encoding="utf-8"))
    assert bad == {"gephi_apply_filters.action": ["visible"]}


def test_the_contract_check_reads_the_java_it_is_given():
    # An endpoint that stopped accepting a value is reported, whatever the Python offers.
    source = JAVA.read_text(encoding="utf-8").replace('case "region"', 'case "regionx"')
    bad = rejected_by_java(offered_values(), source)
    assert bad == {"gephi_focus_view.mode": ["region"]}
