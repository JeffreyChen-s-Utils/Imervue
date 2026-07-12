"""Tests for the configurable detection class scheme and custom model.

``_class_config`` is pure/settings-backed (isolated by the autouse settings
fixture); ``_detection`` custom-model routing is tested with the ML loads
monkeypatched. ``ModelSettingsDialog`` is a plain QDialog — no skip marker.
"""
from __future__ import annotations

from safety_review import _class_config, _detection


# ---------------------------------------------------------------------------
# _class_config
# ---------------------------------------------------------------------------

def test_defaults_when_unset():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop(_class_config.CLASSES_SETTING, None)
    user_setting_dict.pop(_class_config.CENSOR_SETTING, None)
    assert _class_config.get_classes() == _class_config.DEFAULT_CLASSES
    assert _class_config.get_censor_classes() == _class_config.DEFAULT_CENSOR_CLASSES


def test_default_censor_ids_match_erax_genitalia_and_anus():
    # anus=0, penis=3, vagina=4 in the default order.
    assert _class_config.censor_class_ids(
        _class_config.DEFAULT_CLASSES, _class_config.DEFAULT_CENSOR_CLASSES
    ) == frozenset({0, 3, 4})


def test_set_and_read_back_classes_and_censor():
    _class_config.set_classes(["anus", "make_love", "nipple", "penis", "vagina",
                               "toy"])
    _class_config.set_censor_classes(["penis", "vagina", "toy"])
    assert _class_config.get_classes()[-1] == "toy"
    # New class 'toy' is id 5 and is censored.
    assert _class_config.censor_class_ids() == frozenset({3, 4, 5})


def test_set_classes_strips_blanks():
    _class_config.set_classes(["a", "  ", " b ", ""])
    assert _class_config.get_classes() == ["a", "b"]


def test_censor_ignores_unknown_names():
    assert _class_config.censor_class_ids(["a", "b"], ["b", "ghost"]) == frozenset({1})


def test_scene_class_id_tracks_the_list():
    assert _class_config.scene_class_id(_class_config.DEFAULT_CLASSES) == 1
    assert _class_config.scene_class_id(["penis", "vagina"]) is None


# ---------------------------------------------------------------------------
# _detection — custom model routing
# ---------------------------------------------------------------------------

def test_custom_model_path_none_when_unset():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop(_detection.CUSTOM_MODEL_SETTING, None)
    assert _detection._custom_model_path() is None


def test_custom_model_path_returns_existing_file(tmp_path):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    weights = tmp_path / "mine.pt"
    weights.write_bytes(b"x")
    user_setting_dict[_detection.CUSTOM_MODEL_SETTING] = str(weights)
    assert _detection._custom_model_path() == str(weights)
    # A configured-but-missing path is ignored (falls back to EraX).
    user_setting_dict[_detection.CUSTOM_MODEL_SETTING] = str(tmp_path / "gone.pt")
    assert _detection._custom_model_path() is None


def test_get_anime_model_loads_custom_then_reloads_on_change(tmp_path, monkeypatch):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    loaded: list = []
    monkeypatch.setattr(_detection, "_cached_anime_model", None, raising=False)
    monkeypatch.setattr(_detection, "_cached_anime_key", None, raising=False)

    class _FakeYOLO:
        def __init__(self, path):
            loaded.append(path)

    import ultralytics
    monkeypatch.setattr(ultralytics, "YOLO", _FakeYOLO, raising=False)

    a = tmp_path / "a.pt"
    a.write_bytes(b"a")
    user_setting_dict[_detection.CUSTOM_MODEL_SETTING] = str(a)
    _detection._get_anime_model()
    assert loaded == [str(a)]

    # Same path → cached, no reload.
    _detection._get_anime_model()
    assert loaded == [str(a)]

    # Change the path → reloads from the new file.
    b = tmp_path / "b.pt"
    b.write_bytes(b"b")
    user_setting_dict[_detection.CUSTOM_MODEL_SETTING] = str(b)
    _detection._get_anime_model()
    assert loaded == [str(a), str(b)]


# ---------------------------------------------------------------------------
# ModelSettingsDialog — Qt smoke
# ---------------------------------------------------------------------------

def test_model_settings_dialog_saves_classes_and_censor(qapp, tmp_path):
    from safety_review._model_settings_dialog import ModelSettingsDialog
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    weights = tmp_path / "m.pt"
    weights.write_bytes(b"x")

    dlg = ModelSettingsDialog(None)
    dlg._model_edit.setText(str(weights))
    dlg._classes_edit.setPlainText("anus\nmake_love\nnipple\npenis\nvagina\ntoy")
    # The censor checks were rebuilt from the class text; tick two.
    dlg._censor_checks["penis"].setChecked(True)
    dlg._censor_checks["toy"].setChecked(True)
    for name in ("anus", "make_love", "nipple", "vagina"):
        dlg._censor_checks[name].setChecked(False)
    dlg._save()

    assert user_setting_dict[_detection.CUSTOM_MODEL_SETTING] == str(weights)
    assert _class_config.get_classes()[-1] == "toy"
    assert set(_class_config.get_censor_classes()) == {"penis", "toy"}
    dlg.deleteLater()


def test_model_settings_dialog_blank_path_clears_custom_model(qapp, tmp_path):
    from safety_review._model_settings_dialog import ModelSettingsDialog
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict[_detection.CUSTOM_MODEL_SETTING] = "old.pt"
    dlg = ModelSettingsDialog(None)
    dlg._model_edit.clear()
    dlg._save()
    assert _detection.CUSTOM_MODEL_SETTING not in user_setting_dict
    dlg.deleteLater()
