"""Tests for the pure face-embedding clustering (no model needed)."""
from __future__ import annotations

import numpy as np

from Imervue.library.face_clustering import cluster_embeddings, cluster_labels


class TestClusterEmbeddings:
    def test_empty_input(self):
        assert cluster_embeddings(np.zeros((0, 4))) == []
        assert cluster_embeddings(np.zeros((0, 0))) == []

    def test_single_face(self):
        assert cluster_embeddings(np.array([[1.0, 0.0]])) == [[0]]

    def test_near_identical_faces_merge(self):
        emb = np.array([[1.0, 0.0], [0.99, 0.01]])
        assert cluster_embeddings(emb, threshold=0.5) == [[0, 1]]

    def test_orthogonal_faces_split(self):
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])
        assert cluster_embeddings(emb, threshold=0.5) == [[0], [1]]

    def test_two_people_three_faces(self):
        # rows 0 and 2 are one person; row 1 is another.
        emb = np.array([[1.0, 0.0], [0.0, 1.0], [0.96, 0.05]])
        assert cluster_embeddings(emb, threshold=0.5) == [[0, 2], [1]]

    def test_scale_invariance(self):
        # Magnitude must not matter — only direction (cosine).
        emb = np.array([[2.0, 0.0], [5.0, 0.0]])
        assert cluster_embeddings(emb) == [[0, 1]]

    def test_threshold_controls_granularity(self):
        emb = np.array([[1.0, 0.0], [0.8, 0.6]])  # cosine 0.8
        assert cluster_embeddings(emb, threshold=0.7) == [[0, 1]]   # merge
        assert cluster_embeddings(emb, threshold=0.9) == [[0], [1]]  # split

    def test_zero_vector_does_not_crash(self):
        emb = np.array([[0.0, 0.0], [1.0, 0.0]])
        clusters = cluster_embeddings(emb)
        # A zero vector has no direction; it just seeds its own cluster.
        assert sorted(len(c) for c in clusters) == [1, 1]

    def test_first_seen_order_preserved(self):
        emb = np.array([[0.0, 1.0], [1.0, 0.0], [0.02, 0.99]])
        assert cluster_embeddings(emb, threshold=0.5) == [[0, 2], [1]]


class TestClusterLabels:
    def test_labels_match_clusters(self):
        emb = np.array([[1.0, 0.0], [0.0, 1.0], [0.96, 0.05]])
        assert cluster_labels(emb, threshold=0.5) == [0, 1, 0]

    def test_empty(self):
        assert cluster_labels(np.zeros((0, 4))) == []
