"""Similarity (embedding-based) layout: positions from a spectral embedding, not springs.

Nodes are embedded with spectral eigenmaps of the normalized graph Laplacian,
then projected to 2D. Laplacian eigenmaps place closely linked nodes together,
so proximity means "structurally close", which overlaps heavily with the
proximity-means-connected reading of force-directed layouts. It is not a role
embedding: nodes with the same role in distant parts of the graph are not
brought together. A graph in several pieces is laid out one piece at a time and
the pieces packed in rows, largest first, so the result does not depend on the
order the nodes arrive in (beyond the mirror images a symmetric piece allows).

The role basis instead places nodes by role features on the unweighted graph
(edge weights are ignored), across pieces.

Dependency policy: the base path needs only numpy + scipy. If scikit-learn or
umap-learn happen to be installed they are used opportunistically for nicer
projections; they are never required.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _adjacency(graph: dict) -> tuple[list[str], Any]:
    # scipy ships no type information; the matrix is a scipy.sparse csr_matrix.
    import scipy.sparse as sp

    ids = [n["key"] for n in graph["nodes"]]
    idx = {k: i for i, k in enumerate(ids)}
    n = len(ids)
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    for e in graph["edges"]:
        s, t = idx.get(e["source"]), idx.get(e["target"])
        if s is None or t is None or s == t:
            continue
        w = float(e.get("weight", 1.0) or 1.0)
        rows += [s, t]
        cols += [t, s]
        vals += [w, w]
    A = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    return ids, A


def _spectral_embedding(A, dims: int) -> np.ndarray:
    """Eigenvectors of the normalized Laplacian (smallest, minus the trivial ones)."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spl

    n = A.shape[0]
    deg = np.asarray(A.sum(axis=1)).ravel()
    dinv = sp.diags(1.0 / np.sqrt(np.maximum(deg, 1e-12)))
    L = sp.identity(n) - dinv @ A @ dinv
    k = min(dims + 1, n - 1)
    if n <= 1500:
        w, v = np.linalg.eigh(L.toarray())
    else:
        try:
            w, v = spl.eigsh(L.asfptype(), k=k, sigma=0, which="LM")
        except Exception:
            w, v = spl.eigsh(L.asfptype(), k=k, which="SM")
    order = np.argsort(w)
    v = v[:, order][:, 1 : dims + 1]
    # an eigenvector's sign is arbitrary; fix it so a reordered graph is not mirrored
    return v * np.where((v**3).sum(axis=0) < 0, -1.0, 1.0)


def _pieces(ids: list[str], A) -> list[np.ndarray]:
    """Connected pieces as index arrays, largest first, ties broken by smallest node id."""
    from scipy.sparse.csgraph import connected_components

    count, label = connected_components(A, directed=False)
    pieces = [np.flatnonzero(label == c) for c in range(count)]
    return sorted(pieces, key=lambda p: (-len(p), min(ids[i] for i in p)))


def _small_piece_block(cells: list[tuple[np.ndarray, np.ndarray]]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Pieces under 5 nodes gathered into one square grid, so many isolates form a block, not a row."""
    if not cells:
        return []
    size = max(float(np.ptp(c, axis=0).max()) for _, c in cells) + 1.0
    columns = int(np.ceil(np.sqrt(len(cells))))
    placed = [local + np.array([(j % columns) * size, -(j // columns) * size])
              for j, (_, local) in enumerate(cells)]
    return [(np.concatenate([p for p, _ in cells]), np.vstack(placed))]


def _spectral_layout(ids: list[str], A, dims: int, projection: str) -> tuple[np.ndarray, str]:
    """Spectral positions, one piece at a time, packed in rows.

    Each extra piece adds a zero eigenvalue, and a solver returns those in an arbitrary mix,
    so embedding a graph in pieces whole gives a layout that depends on node order. Pieces
    under 5 nodes sit on a small circle in id order, gathered into one block; each piece's area
    follows its node count.
    """
    xy = np.zeros((len(ids), 2))
    method = "spectral"
    cells = []
    for j, p in enumerate(_pieces(ids, A)):
        if len(p) >= 5:
            emb = _spectral_embedding(A[p][:, p], max(2, min(dims, len(p) - 2)))
            local, used = _project(emb, projection, "spectral")
            if j == 0:
                method = used
        else:
            angle = np.zeros(len(p))
            angle[sorted(range(len(p)), key=lambda i: ids[p[i]])] = 2 * np.pi * np.arange(len(p)) / len(p)
            local = np.column_stack([np.cos(angle), np.sin(angle)]) if len(p) > 1 else np.zeros((1, 2))
        local = local - local.mean(axis=0)
        spread = float(local.std(axis=0).max())
        cells.append((p, local * (np.sqrt(len(p)) / spread) if spread > 0 else local))
    cells = [c for c in cells if len(c[0]) >= 5] + _small_piece_block([c for c in cells if len(c[0]) < 5])
    # shelf packing: left to right, a new row when the next piece would overflow
    gap = 2.0
    boxes = [(c.min(axis=0), c.max(axis=0)) for _, c in cells]
    area = sum(float(np.prod(hi - lo + gap)) for lo, hi in boxes)
    row_width = max(max(float(hi[0] - lo[0]) for lo, hi in boxes), 1.3 * np.sqrt(area))
    x = y = row_height = 0.0
    for (p, local), (lo, hi) in zip(cells, boxes):
        w, h = float(hi[0] - lo[0]), float(hi[1] - lo[1])
        if x > 0 and x + w > row_width:
            x, y, row_height = 0.0, y - row_height - gap, 0.0
        xy[p] = local + np.array([x - lo[0], y - hi[1]])
        x += w + gap
        row_height = max(row_height, h)
    return xy, method


def _role_feature_table(A) -> np.ndarray:
    """Twelve raw role features per node, on the unweighted graph (edge weights are ignored).

    Six local ones (log degree, mean and max neighbour log degree, clustering, log triangles,
    log two-hop neighbourhood size) and the neighbour mean of each (one ReFeX-style recursion).
    Nodes in the same position in distant parts of the graph get the same features, which is
    what lets a hub sit next to another hub it shares no neighbours with.
    """
    import scipy.sparse as sp

    B = (A > 0).astype(float).tocsr()
    deg = np.asarray(B.sum(axis=1)).ravel()
    safe = np.maximum(deg, 1.0)
    logdeg = np.log1p(deg)
    nbr_mean = (B @ logdeg) / safe
    nbr_max = np.zeros(len(deg))
    for i in range(B.shape[0]):
        row = B.indices[B.indptr[i]:B.indptr[i + 1]]
        if len(row):
            nbr_max[i] = logdeg[row].max()
    B2 = B @ B
    tri = np.asarray(B2.multiply(B).sum(axis=1)).ravel() / 2.0
    pairs = deg * (deg - 1) / 2.0
    clustering = np.divide(tri, pairs, out=np.zeros_like(tri), where=pairs > 0)
    reach = (B2 + B).tocsr()
    reach.setdiag(0)
    reach.eliminate_zeros()
    two_hop = np.diff(reach.indptr).astype(float)
    local = np.column_stack([logdeg, nbr_mean, nbr_max, clustering, np.log1p(tri), np.log1p(two_hop)])
    recursive = sp.diags(1.0 / safe) @ (B @ local)
    return np.hstack([local, recursive])


def _role_features(A) -> np.ndarray:
    """The role feature table, each column z-scored (constant columns become zero)."""
    F = _role_feature_table(A)
    sd = F.std(axis=0)
    return np.divide(F - F.mean(axis=0), sd, out=np.zeros_like(F), where=sd > 0)


def _pca2(emb: np.ndarray) -> np.ndarray:
    centred = emb - emb.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    return np.asarray(centred @ vt[:2].T, dtype=float)


def _project(emb: np.ndarray, projection: str, base: str = "spectral") -> tuple[np.ndarray, str]:
    """2D projection ladder: umap -> tsne -> base.

    base "spectral": the first two embedding dims (the classic spectral layout).
    base "pca": the first two principal components (for feature embeddings).
    """
    n = emb.shape[0]
    if projection in ("auto", "umap"):
        try:
            import umap  # type: ignore

            xy = umap.UMAP(
                n_neighbors=min(15, max(2, n - 1)), min_dist=0.3, random_state=7
            ).fit_transform(emb)
            return np.asarray(xy, dtype=float), "umap"
        except ImportError:
            if projection == "umap":
                raise
    if projection in ("auto", "tsne"):
        try:
            from sklearn.manifold import TSNE  # type: ignore

            xy = TSNE(
                n_components=2, perplexity=min(30.0, max(2.0, (n - 1) / 3.0)), random_state=7
            ).fit_transform(emb)
            return np.asarray(xy, dtype=float), "tsne"
        except ImportError:
            if projection == "tsne":
                raise
    if base == "pca":
        return _pca2(emb), "pca"
    # base path: the two lowest-frequency non-trivial eigenvectors ARE the
    # classic spectral layout (they preserve coarse geometry; PCA over the
    # equal-variance eigenvector set would scramble frequencies instead)
    xy = emb[:, :2].copy()
    return xy - xy.mean(axis=0), "spectral"


BASES = ("role", "spectral")


def compute_similarity_positions(
    graph: dict, dims: int = 8, projection: str = "auto", extent: float = 900.0,
    basis: str = "spectral",
) -> tuple[list[dict], str]:
    """Positions for every node, by structural similarity.

    graph: the dict produced by parse_gexf. basis: "role" (role features) or "spectral"
    (Laplacian eigenmaps). projection: "auto", "umap", "tsne", or the base projection,
    named "spectral" or "pca" (either name gives the basis's own base). Returns
    ([{id, x, y}, ...], method), where method names the projection actually used.
    """
    if basis not in BASES:
        raise ValueError(f"basis must be one of {', '.join(BASES)}, not {basis!r}")
    ids, A = _adjacency(graph)
    n = len(ids)
    if n < 5:
        raise ValueError("similarity layout needs at least 5 nodes")
    if A.nnz == 0:
        raise ValueError("similarity layout needs edges (the graph has none)")
    if basis == "role":
        xy, method = _project(_role_features(A), projection, "pca")
    else:
        xy, method = _spectral_layout(ids, A, dims, projection)
    xy = xy - xy.mean(axis=0)
    spread = float(max(xy.std(axis=0).max(), 1e-9))
    xy = xy * (extent / (spread * 4.0))
    return (
        [{"id": ids[i], "x": float(xy[i, 0]), "y": float(xy[i, 1])} for i in range(n)],
        method,
    )
