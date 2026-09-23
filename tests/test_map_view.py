"""Tests for map-view place grouping (nearest-city clustering)."""
from __future__ import annotations

from Imervue.gui.map_view_dialog import (
    _render_html,
    group_points_by_place,
)


def test_group_empty_returns_empty():
    assert group_points_by_place([]) == []


def test_group_clusters_same_city():
    points = [
        ("a.jpg", 48.85, 2.35),    # Paris
        ("b.jpg", 48.86, 2.34),    # Paris
        ("c.jpg", 35.68, 139.69),  # Tokyo
    ]
    counts = {g.place: g.count for g in group_points_by_place(points)}
    assert counts["Paris, France"] == 2
    assert counts["Tokyo, Japan"] == 1


def test_group_sorted_by_count_descending():
    points = [
        ("a", 35.68, 139.69),  # Tokyo (1)
        ("b", 48.85, 2.35),    # Paris (2)
        ("c", 48.86, 2.34),
    ]
    groups = group_points_by_place(points)
    assert groups[0].place == "Paris, France"
    assert groups[0].count == 2


def test_group_centroid_is_mean_of_members():
    group = group_points_by_place([("a", 48.80, 2.30), ("b", 48.90, 2.40)])[0]
    assert abs(group.lat - 48.85) < 1e-6
    assert abs(group.lon - 2.35) < 1e-6
    assert group.paths == ("a", "b")


def test_render_html_embeds_place_label():
    out = _render_html(group_points_by_place([("a.jpg", 48.85, 2.35)]))
    assert "Paris, France (1)" in out
    assert "__POINTS__" not in out


def test_render_html_pins_leaflet_with_subresource_integrity():
    # Hashes as published on leafletjs.com for 1.9.4; a tampered CDN copy is refused.
    out = _render_html([])
    for name, digest in (("leaflet.css", "p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="),
                         ("leaflet.js", "20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=")):
        start = out.index(f"leaflet@1.9.4/dist/{name}")
        tag_end = out.index(">", start)
        assert f'integrity="sha256-{digest}" crossorigin=""' in out[start:tag_end]


def test_render_html_caps_the_fit_zoom():
    out = _render_html(group_points_by_place([("a.jpg", 48.85, 2.35)]))
    assert "{maxZoom: 12}" in out
    assert "__FIT_MAX_ZOOM__" not in out
