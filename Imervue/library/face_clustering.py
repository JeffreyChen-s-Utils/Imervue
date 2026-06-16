"""Group face embeddings into people — the algorithmic core of People Albums.

Face *detection* (bounding boxes) already lives in
:mod:`Imervue.image.face_detection`. Turning detected faces into "people"
needs a face-embedding model (an optional, heavy dependency) to produce one
vector per face; this module is the model-agnostic part — it clusters whatever
embeddings it is handed by cosine similarity, so the grouping is pure numpy and
fully unit-testable.

The clustering is a single greedy pass (online agglomerative): each face joins
the most similar existing cluster when their cosine similarity meets the
threshold, otherwise it seeds a new cluster. That is O(N·K) for K people —
plenty for a personal library and, unlike k-means, needs no preset cluster
count.
"""
from __future__ import annotations

import numpy as np

# Cosine-similarity threshold above which two faces are the same person. 0.5 is
# a deliberately loose default for arbitrary embedders; callers tune per model.
DEFAULT_THRESHOLD = 0.5


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def cluster_embeddings(
    embeddings: np.ndarray,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[list[int]]:
    """Group rows of *embeddings* into clusters of similar faces.

    *embeddings* is an ``(N, D)`` array (any scale — rows are L2-normalised
    internally). Returns a list of clusters, each a list of row indices, in
    first-seen order. An empty or non-2-D input yields ``[]``.
    """
    matrix = np.asarray(embeddings, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        return []
    unit = _normalise_rows(matrix)
    clusters: list[list[int]] = []
    centroids: list[np.ndarray] = []  # unit-length running cluster directions
    for row in range(unit.shape[0]):
        vec = unit[row]
        best_cluster, best_sim = -1, -1.0
        for cluster_idx, centroid in enumerate(centroids):
            sim = float(np.dot(vec, centroid))
            if sim > best_sim:
                best_sim, best_cluster = sim, cluster_idx
        if best_cluster >= 0 and best_sim >= threshold:
            clusters[best_cluster].append(row)
            members = matrix[clusters[best_cluster]]
            centroids[best_cluster] = _normalise_rows(
                members.mean(axis=0, keepdims=True))[0]
        else:
            clusters.append([row])
            centroids.append(vec.copy())
    return clusters


def cluster_labels(
    embeddings: np.ndarray,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[int]:
    """Per-row cluster label (0-based, first-seen order); ``[]`` for no input."""
    matrix = np.asarray(embeddings, dtype=np.float64)
    count = matrix.shape[0] if matrix.ndim == 2 else 0
    labels = [-1] * count
    for label, group in enumerate(cluster_embeddings(matrix, threshold=threshold)):
        for index in group:
            labels[index] = label
    return labels
