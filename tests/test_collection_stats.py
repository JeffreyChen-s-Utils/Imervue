"""Tests for the library collection-stats summariser."""
from __future__ import annotations

from Imervue.library import image_index
from Imervue.library.collection_stats import _summarize, summarize
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Pure aggregation core
# ---------------------------------------------------------------------------


def test_summarize_empty_collection():
    stats = _summarize([], {}, [], {}, {})
    assert stats["total"] == 0
    assert stats["rated"] == 0
    assert stats["unrated"] == 0
    assert stats["average_rating"] == 0.0
    assert set(stats["rating_distribution"]) == {0, 1, 2, 3, 4, 5}
    assert stats["favorites"] == 0
    assert stats["color_labels"]["none"] == 0
    assert stats["cull"]["unflagged"] == 0


def test_summarize_rating_distribution_and_average():
    paths = ["a", "b", "c", "d"]
    ratings = {"a": 5, "b": 3, "c": 0}  # d missing -> 0
    stats = _summarize(paths, ratings, [], {}, {})
    assert stats["total"] == 4
    assert stats["rated"] == 2          # a, b
    assert stats["unrated"] == 2        # c (0), d (missing)
    assert stats["rating_distribution"][5] == 1
    assert stats["rating_distribution"][3] == 1
    assert stats["rating_distribution"][0] == 2
    assert stats["average_rating"] == 4.0   # (5 + 3) / 2


def test_summarize_negative_rating_counts_as_unrated():
    stats = _summarize(["a"], {"a": -1}, [], {}, {})
    assert stats["rating_distribution"][0] == 1
    assert stats["rated"] == 0


def test_summarize_distribution_sums_to_total():
    paths = ["a", "b", "c", "d", "e"]
    ratings = {"a": 1, "b": 2, "c": 2, "d": 5}
    stats = _summarize(paths, ratings, [], {}, {})
    assert sum(stats["rating_distribution"].values()) == 5


def test_summarize_favorites_labels_and_cull():
    paths = ["a", "b", "c"]
    labels = {"a": "red", "b": "red", "c": None}
    culls = {"a": "pick", "b": "reject"}  # c missing -> unflagged
    stats = _summarize(paths, {}, ["a", "c"], labels, culls)
    assert stats["favorites"] == 2
    assert stats["color_labels"]["red"] == 2
    assert stats["color_labels"]["none"] == 1
    assert stats["cull"] == {"pick": 1, "reject": 1, "unflagged": 1}


def test_summarize_unknown_label_counts_as_none():
    stats = _summarize(["a"], {}, [], {"a": "chartreuse"}, {})
    assert stats["color_labels"]["none"] == 1


def test_summarize_handles_non_list_favourites():
    stats = _summarize(["a"], {}, None, {}, {})
    assert stats["favorites"] == 0


# ---------------------------------------------------------------------------
# Live wiring over isolated settings + index
# ---------------------------------------------------------------------------


def test_summarize_reads_live_sources(tmp_path):
    from Imervue.user_settings.color_labels import set_color_label
    image_index.set_db_path(tmp_path / "lib.db")
    a = str(tmp_path / "a.png")
    b = str(tmp_path / "b.png")
    try:
        image_index.set_cull_state(a, "pick")
        user_setting_dict["image_ratings"] = {a: 4}
        user_setting_dict["image_favorites"] = [b]
        set_color_label(a, "red")
        stats = summarize([a, b])
        assert stats["total"] == 2
        assert stats["rated"] == 1
        assert stats["average_rating"] == 4.0
        assert stats["favorites"] == 1
        assert stats["color_labels"]["red"] == 1
        assert stats["cull"]["pick"] == 1
        assert stats["cull"]["unflagged"] == 1
    finally:
        user_setting_dict["image_ratings"] = {}
        user_setting_dict["image_favorites"] = []
        user_setting_dict["image_color_labels"] = {}
        image_index.close()
