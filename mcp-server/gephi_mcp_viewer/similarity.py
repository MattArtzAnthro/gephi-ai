"""Similarity (embedding-based) layout: positions from structural role, not springs.

Nodes are embedded with spectral eigenmaps of the normalized graph Laplacian,
then projected to 2D. Proximity in the result means "similar position in the
network's structure", which is different from (and complementary to) the
proximity-means-connected reading of force-directed layouts.

Dependency policy: the base path needs only numpy + scipy. If scikit-learn or
umap-learn happen to be installed they are used opportunistically for nicer
projections; they are never required.
"""

from __future__ import annotations

import numpy as np


def _adjacency(graph: dict) -> tuple[list[str], np.ndarray | object]:
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
    v = v[:, order]
    return v[:, 1 : dims + 1]


def _project(emb: np.ndarray, projection: str) -> tuple[np.ndarray, str]:
    """2D projection ladder: umap -> tsne -> spectral (first two dims, PCA-rotated)."""
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
    # base path: the two lowest-frequency non-trivial eigenvectors ARE the
    # classic spectral layout (they preserve coarse geometry; PCA over the
    # equal-variance eigenvector set would scramble frequencies instead)
    xy = emb[:, :2].copy()
    return xy - xy.mean(axis=0), "spectral"


def compute_similarity_positions(
    graph: dict, dims: int = 8, projection: str = "auto", extent: float = 900.0
) -> tuple[list[dict], str]:
    """Positions for every node, by structural similarity.

    graph: the dict produced by parse_gexf. Returns ([{id, x, y}, ...], method),
    where method names the projection actually used.
    """
    ids, A = _adjacency(graph)
    n = len(ids)
    if n < 5:
        raise ValueError("similarity layout needs at least 5 nodes")
    if A.nnz == 0:
        raise ValueError("similarity layout needs edges (the graph has none)")
    dims = max(2, min(dims, n - 2))
    emb = _spectral_embedding(A, dims)
    xy, method = _project(emb, projection)
    xy = xy - xy.mean(axis=0)
    spread = float(max(xy.std(axis=0).max(), 1e-9))
    xy = xy * (extent / (spread * 4.0))
    return (
        [{"id": ids[i], "x": float(xy[i, 0]), "y": float(xy[i, 1])} for i in range(n)],
        method,
    )
