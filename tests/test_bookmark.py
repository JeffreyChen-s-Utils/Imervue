"""Tests for bookmark / collection management."""
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.user_settings.bookmark import (
    add_bookmark, remove_bookmark, is_bookmarked, get_bookmarks, clear_bookmarks,
    MAX_BOOKMARKS,
)


class TestBookmark:
    def setup_method(self):
        user_setting_dict["bookmarks"] = []

    def test_add_bookmark(self):
        assert add_bookmark("/img/a.png")
        assert is_bookmarked("/img/a.png")
        assert get_bookmarks() == ["/img/a.png"]

    def test_add_duplicate_returns_false(self):
        add_bookmark("/img/a.png")
        assert not add_bookmark("/img/a.png")
        assert len(get_bookmarks()) == 1

    def test_remove_bookmark(self):
        add_bookmark("/img/a.png")
        assert remove_bookmark("/img/a.png")
        assert not is_bookmarked("/img/a.png")

    def test_remove_nonexistent(self):
        assert not remove_bookmark("/img/z.png")

    def test_clear_bookmarks(self):
        add_bookmark("/img/a.png")
        add_bookmark("/img/b.png")
        clear_bookmarks()
        assert get_bookmarks() == []

    def test_max_limit(self):
        for i in range(MAX_BOOKMARKS + 10):
            add_bookmark(f"/img/{i}.png")
        assert len(get_bookmarks()) == MAX_BOOKMARKS

    def test_is_bookmarked_empty(self):
        assert not is_bookmarked("/anything")
