"""Characterisation tests for the main window's Filter menu.

Pins every entry in order (submenus, actions, separators), its text, and the
filter call each one makes, so splitting ``build_filter_menu`` cannot drop,
reorder or rewire an entry.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMainWindow

from Imervue.gui.menu_tree import submenu_index, submenu_of
from Imervue.menu import filter_menu as mod
from Imervue.user_settings.user_setting_dict import user_setting_dict

_STARS = ["★" * n for n in range(1, 6)]

# (entry text, [(action text, expected call) ...]) for every submenu, in order;
# a plain string is a top-level action, None a separator.
_EXPECTED = [
    ("By Extension", [(label, ("ext", key)) for label, key in (
        ("All", "all"), ("JPG", "jpg"), ("PNG", "png"), ("BMP", "bmp"), ("TIFF", "tiff"),
        ("SVG", "svg"), ("RAW", "raw"))]),
    ("By Color Label", [("All", ("color", None)), ("Any label", ("color", "any")),
                        ("No label", ("color", "none")), None,
                        ("Red", ("color", "red")), ("Yellow", ("color", "yellow")),
                        ("Green", ("color", "green")), ("Blue", ("color", "blue")),
                        ("Purple", ("color", "purple"))]),
    ("By Rating", [("All", ("rating", 0)), ("Favorited", ("rating", -1))]
     + [(s, ("rating", n)) for n, s in enumerate(_STARS, start=1)]),
    ("By Tag", None),
    ("By Album", None),
    None,
    ("Multi-Tag Filter…", ("multi_tag",)),
    ("Advanced Filter…", ("advanced",)),
    None,
    ("By Cull State", [("All", ("cull", None)), ("Picks only", ("cull", "pick")),
                       ("Rejects only", ("cull", "reject")),
                       ("Unflagged only", ("cull", "unflagged"))]),
    ("Stack RAW+JPEG pairs", "stack"),
    ("Clear Filter", ("clear",)),
]


@pytest.fixture
def built(qapp, monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    calls: list[tuple] = []
    monkeypatch.setattr(mod, "_apply_ext_filter", lambda ui, k: calls.append(("ext", k)))
    monkeypatch.setattr(mod, "_apply_color_filter", lambda ui, c: calls.append(("color", c)))
    monkeypatch.setattr(mod, "_apply_rating_filter", lambda ui, r: calls.append(("rating", r)))
    monkeypatch.setattr(mod, "_apply_cull_filter", lambda ui, s: calls.append(("cull", s)))
    monkeypatch.setattr(mod, "_open_multi_tag", lambda ui: calls.append(("multi_tag",)))
    monkeypatch.setattr(mod, "_open_advanced", lambda ui: calls.append(("advanced",)))
    monkeypatch.setattr(mod, "_clear_filter", lambda ui: calls.append(("clear",)))
    monkeypatch.setattr(mod, "_toggle_stack_mode", lambda ui, on: calls.append(("stack", on)))
    tagged: list[tuple] = []
    monkeypatch.setattr(mod, "_build_tag_filter", lambda ui, menu: tagged.append(("tag", menu)))
    monkeypatch.setattr(mod, "_build_album_filter", lambda ui, menu: tagged.append(("album", menu)))
    window = QMainWindow()
    menu = mod.build_filter_menu(window)
    yield window, menu, calls, tagged
    window.deleteLater()


def test_menu_is_added_to_the_menu_bar(built):
    window, menu, _calls, _tagged = built
    assert menu.title() == "Filter"
    assert window._filter_menu is menu  # noqa: SLF001
    assert window.menuBar().actions() == [menu.menuAction()]


def test_entries_in_order_and_their_calls(built):
    window, menu, calls, _tagged = built
    index = submenu_index(window)
    top = menu.actions()
    assert len(top) == len(_EXPECTED)
    for action, expected in zip(top, _EXPECTED, strict=True):
        if expected is None:
            assert action.isSeparator()
            continue
        text, spec = expected
        assert action.text() == text
        submenu = submenu_of(action, index)
        if isinstance(spec, list):
            children = submenu.actions()
            assert len(children) == len(spec), text
            for child, child_spec in zip(children, spec, strict=True):
                if child_spec is None:
                    assert child.isSeparator()
                    continue
                child_text, call = child_spec
                assert child.text() == child_text
                child.trigger()
                assert calls[-1] == call, (text, child_text)
        elif spec is None:
            assert submenu is not None and submenu.actions() == []
        elif spec != "stack":
            assert submenu is None
            action.trigger()
            assert calls[-1] == spec, text


def test_tag_and_album_submenus_are_filled_by_their_builders(built):
    window, menu, _calls, tagged = built
    index = submenu_index(window)
    by_text = {a.text(): submenu_of(a, index) for a in menu.actions()}
    assert tagged == [("tag", by_text["By Tag"]), ("album", by_text["By Album"])]


@pytest.mark.parametrize("saved", [False, True])
def test_stack_toggle_starts_from_the_setting(qapp, monkeypatch, saved):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    monkeypatch.setitem(user_setting_dict, "stack_raw_jpeg_pairs", saved)
    calls: list[tuple] = []
    monkeypatch.setattr(mod, "_toggle_stack_mode", lambda ui, on: calls.append(("stack", on)))
    window = QMainWindow()
    try:
        menu = mod.build_filter_menu(window)
        stack = next(a for a in menu.actions() if a.text() == "Stack RAW+JPEG pairs")
        assert stack.isCheckable() and stack.isChecked() is saved
        stack.trigger()
        assert calls == [("stack", not saved)]
    finally:
        window.deleteLater()
