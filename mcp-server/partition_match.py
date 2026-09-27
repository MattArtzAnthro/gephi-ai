"""Agreement between two groupings of the same nodes.

A partition from community detection is often read against a grouping the researcher already has:
factions, departments, field sites. The answer needs three things: the cross-table of who falls
where, which known value each detected group mostly holds, and a score for the overall agreement.

Two scores, because they answer slightly different questions. The adjusted Rand index (Hubert and
Arabie 1985) asks how often two nodes placed together in one grouping are together in the other,
corrected so that chance scores about 0 and identical groupings score 1; it can go below 0.
Normalized mutual information (Danon et al. 2005) asks how much knowing one grouping tells you
about the other, from 0 (nothing) to 1 (everything). Both ignore the names of the groups.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from math import comb, log
from typing import Any


def compare_partitions(pairs: Iterable[tuple[Any, Any]]) -> dict[str, Any]:
    """Compare two groupings given as one (first, second) pair of values per node.

    Nodes missing either value are left out and counted, since a grouping cannot agree or
    disagree about a node it never placed.
    """
    kept, left_out = [], 0
    for first, second in pairs:
        if first is None or second is None:
            left_out += 1
        else:
            kept.append((str(first), str(second)))
    if not kept:
        raise ValueError("No node carries a value in both columns, so there is nothing to compare.")

    n = len(kept)
    cells = Counter(kept)
    rows = Counter(a for a, _ in kept)
    cols = Counter(b for _, b in kept)

    table: dict[str, dict[str, int]] = {}
    for (a, b), count in sorted(cells.items()):
        table.setdefault(a, {})[b] = count

    groups = []
    for a, size in sorted(rows.items(), key=lambda item: (-item[1], item[0])):
        mostly, count = max(table[a].items(), key=lambda item: (item[1], item[0]))
        groups.append({"group": a, "size": size, "mostly": mostly, "share": count / size})

    return {
        "compared": n,
        "left_out": left_out,
        "adjusted_rand": _adjusted_rand(cells, rows, cols, n),
        "normalized_mutual_information": _nmi(cells, rows, cols, n),
        "table": table,
        "groups": groups,
    }


def _adjusted_rand(cells: Counter, rows: Counter, cols: Counter, n: int) -> float:
    index = sum(comb(c, 2) for c in cells.values())
    sum_rows = sum(comb(c, 2) for c in rows.values())
    sum_cols = sum(comb(c, 2) for c in cols.values())
    pairs = comb(n, 2)
    if pairs == 0:
        return 1.0
    expected = sum_rows * sum_cols / pairs
    maximum = (sum_rows + sum_cols) / 2
    if maximum == expected:
        return 1.0
    return (index - expected) / (maximum - expected)


def _entropy(counts: Counter, n: int) -> float:
    return -sum(c / n * log(c / n) for c in counts.values() if c)


def _nmi(cells: Counter, rows: Counter, cols: Counter, n: int) -> float:
    h_rows, h_cols = _entropy(rows, n), _entropy(cols, n)
    if h_rows == 0 and h_cols == 0:
        return 1.0
    mutual = sum(c / n * log(c * n / (rows[a] * cols[b])) for (a, b), c in cells.items())
    return max(0.0, mutual / ((h_rows + h_cols) / 2))
