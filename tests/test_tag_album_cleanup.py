"""Tags & Albums refuses names that clash by case and cleans up stale entries.

``user_settings/tag_validator.py`` (name checks, orphan / duplicate detection,
pruning and merging) was tested but unreachable: ``"Foo"`` and ``"foo"`` could
coexist and a deleted file stayed tagged for good. The dialog now checks every
new or renamed name, and **Clean Up…** forgets missing files and merges names
that differ only in case.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.gui import tag_album_dialog as mod
from Imervue.user_settings.tag_validator import (
    CleanupPlan,
    clean_collection,
    name_problem,
    plan_cleanup,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.mark.parametrize(("name", "current", "problem"), [
    ("Beach", None, None),
    ("Holiday", None, "duplicate"),
    ("holiday", None, "duplicate"),
    (" Trip ", None, "invalid"),
    ("a\tb", None, "invalid"),
    ("Trip", "trip", None),           # renaming a name to another case of itself
    ("TRIP", "Holiday", "duplicate"),
])
def test_name_problem(name, current, problem):
    existing = {"Holiday": [], "trip": []}
    assert name_problem(name, existing, current=current) == problem


def test_the_cleanup_plan_counts_orphans_and_keeps_the_fuller_name():
    coll = {"Foo": ["a"], "foo": ["a", "b", "gone"], "Bar": ["gone", "c"]}
    plan = plan_cleanup(coll, {"a", "b", "c"})
    assert plan == CleanupPlan(orphans=2, merges=[("Foo", "foo")])
    assert plan.changes
    assert clean_collection(coll, {"a", "b", "c"}) == {"foo": ["a", "b"], "Bar": ["c"]}


def test_a_clean_collection_needs_no_cleanup():
    assert not plan_cleanup({"A": ["x"], "B": []}, {"x"}).changes


@pytest.fixture
def dialog(qapp, monkeypatch):
    for key in ("image_tags", "albums"):
        monkeypatch.setitem(user_setting_dict, key, {})
    warnings, infos = [], []
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a: warnings.append(a[2]))
    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a: infos.append(a[2]))
    dlg = mod.TagAlbumDialog(SimpleNamespace(main_window=None))
    yield dlg, warnings, infos
    dlg.deleteLater()


def _answer(monkeypatch, text: str) -> None:
    monkeypatch.setattr(mod.QInputDialog, "getText", lambda *a, **k: (text, True))


def test_a_tag_differing_only_in_case_is_refused(dialog, monkeypatch):
    dlg, warnings, _ = dialog
    user_setting_dict["image_tags"] = {"Holiday": ["x.jpg"]}
    _answer(monkeypatch, "holiday")
    dlg._create_tag()  # noqa: SLF001
    assert list(user_setting_dict["image_tags"]) == ["Holiday"]
    assert "differs from an existing name only in case" in warnings[0]


def test_a_new_distinct_tag_is_created(dialog, monkeypatch):
    dlg, warnings, _ = dialog
    _answer(monkeypatch, "  Summer ")
    dlg._create_tag()  # noqa: SLF001
    assert "Summer" in user_setting_dict["image_tags"] and warnings == []


def _select_album(dlg, name: str) -> None:
    dlg._refresh_albums()  # noqa: SLF001
    albums = dlg._album_list  # noqa: SLF001
    albums.setCurrentRow(next(i for i in range(albums.count())
                              if albums.item(i).data(mod.Qt.ItemDataRole.UserRole) == name))


def test_an_album_may_change_only_its_case(dialog, monkeypatch):
    dlg, warnings, _ = dialog
    user_setting_dict["albums"] = {"trip": ["x.jpg"], "Home": []}
    _select_album(dlg, "trip")
    _answer(monkeypatch, "Trip")
    dlg._rename_album()  # noqa: SLF001
    assert set(user_setting_dict["albums"]) == {"Trip", "Home"} and warnings == []
    _select_album(dlg, "Trip")
    _answer(monkeypatch, "home")
    dlg._rename_album()  # noqa: SLF001
    assert set(user_setting_dict["albums"]) == {"Trip", "Home"}
    assert len(warnings) == 1


def test_clean_up_forgets_missing_files_and_merges_case_twins(dialog, monkeypatch, tmp_path):
    dlg, _warnings, _infos = dialog
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    gone = str(tmp_path / "gone.jpg")
    user_setting_dict["image_tags"] = {"Foo": [str(kept), gone], "foo": [gone]}
    user_setting_dict["albums"] = {"Trip": [gone]}
    questions = []
    monkeypatch.setattr(mod, "confirm", lambda parent, title, q: questions.append(q) or True)
    dlg._clean_up()  # noqa: SLF001
    assert "Forget 3 entries" in questions[0] and "foo → Foo" in questions[0]
    assert user_setting_dict["image_tags"] == {"Foo": [str(kept)]}
    assert user_setting_dict["albums"] == {"Trip": []}


def test_clean_up_changes_nothing_when_declined(dialog, monkeypatch, tmp_path):
    dlg, _warnings, _infos = dialog
    user_setting_dict["image_tags"] = {"A": [str(tmp_path / "gone.jpg")]}
    monkeypatch.setattr(mod, "confirm", lambda *a: False)
    dlg._clean_up()  # noqa: SLF001
    assert user_setting_dict["image_tags"] == {"A": [str(tmp_path / "gone.jpg")]}


def test_clean_up_says_when_there_is_nothing_to_do(dialog, monkeypatch, tmp_path):
    dlg, _warnings, infos = dialog
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    user_setting_dict["image_tags"] = {"A": [str(kept)]}
    monkeypatch.setattr(mod, "confirm", lambda *a: pytest.fail("nothing to confirm"))
    dlg._clean_up()  # noqa: SLF001
    assert "Nothing to clean up" in infos[0]
