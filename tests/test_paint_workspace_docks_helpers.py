"""Pure-helper unit tests for the workspace dock-layout collaborator.

``DockLayoutMixin._ordered_docks`` flattens the three workflow clusters
into their canonical left-to-right order; it is shared by toggle-all and
reset-layout, so a regression here would silently reorder the dock column
or drop a cluster. Tested directly on a synthetic cluster dict — no Qt
widgets, no GL surface.
"""
from __future__ import annotations

from Imervue.paint.workspace_docks import (
    _CLUSTER_ORDER,
    _DOCK_OBJECT_NAMES,
    DockLayoutMixin,
)


def _clusters(drawing, canvas, library) -> dict:
    return {"drawing": drawing, "canvas": canvas, "library": library}


def test_ordered_docks_concatenates_in_cluster_order():
    clusters = _clusters(("a", "b"), ("c",), ("d", "e"))
    assert DockLayoutMixin._ordered_docks(clusters) == ("a", "b", "c", "d", "e")


def test_ordered_docks_empty_clusters():
    assert DockLayoutMixin._ordered_docks(_clusters((), (), ())) == ()


def test_ordered_docks_missing_keys_are_skipped():
    # A partial dict (e.g. a future layout that drops a cluster) must not
    # raise — ``.get`` defaults to an empty tuple.
    assert DockLayoutMixin._ordered_docks({"drawing": ("only",)}) == ("only",)


def test_ordered_docks_single_dock_per_cluster():
    clusters = _clusters(("x",), ("y",), ("z",))
    assert DockLayoutMixin._ordered_docks(clusters) == ("x", "y", "z")


def test_cluster_order_matches_known_clusters():
    assert _CLUSTER_ORDER == ("drawing", "canvas", "library")


def test_dock_object_names_are_unique():
    # saveState/restoreState rely on these ids being distinct per dock.
    names = list(_DOCK_OBJECT_NAMES.values())
    assert len(names) == len(set(names))
    assert all(name.startswith("paint_dock_") for name in names)
