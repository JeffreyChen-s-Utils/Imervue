"""User-configurable detection class scheme for the safety_review plugin.

The default EraX model detects five fixed classes, but a user who fine-tunes
their own model may add new classes. The class list (index = YOLO class id) and
the subset to censor are therefore kept in ``user_setting_dict`` rather than
hard-coded, so a custom model with extra classes works without code changes.

Pure/settings-backed — no Qt, no ML. ``censor_class_ids`` and the getters are
unit-tested against the isolated settings fixture.
"""
from __future__ import annotations

# EraX order — index is the YOLO class id: 0=anus 1=make_love 2=nipple
# 3=penis 4=vagina. A fine-tuned model must keep this order and append new
# classes after index 4.
DEFAULT_CLASSES = ["anus", "make_love", "nipple", "penis", "vagina"]
# Names censored out of the box (genitalia + anus); nipple and the scene-level
# make_love box are left off by default.
DEFAULT_CENSOR_CLASSES = ["anus", "penis", "vagina"]
# The scene-level class whose box is shrunk to its centre (see _detection).
SCENE_CLASS_NAME = "make_love"

CLASSES_SETTING = "safety_review_classes"
CENSOR_SETTING = "safety_review_censor_classes"


def _settings():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return user_setting_dict


def get_classes() -> list[str]:
    """The configured class list (index = class id), or the EraX default."""
    try:
        value = _settings().get(CLASSES_SETTING)
    except Exception:  # noqa: BLE001 — settings unavailable → default
        return list(DEFAULT_CLASSES)
    if isinstance(value, list) and value:
        return [str(name) for name in value]
    return list(DEFAULT_CLASSES)


def set_classes(names) -> None:
    from Imervue.user_settings.user_setting_dict import schedule_save
    cleaned = [str(n).strip() for n in names if str(n).strip()]
    _settings()[CLASSES_SETTING] = cleaned
    schedule_save()


def get_censor_classes() -> list[str]:
    """Names of the classes to censor, or the default genitalia+anus set."""
    try:
        value = _settings().get(CENSOR_SETTING)
    except Exception:  # noqa: BLE001
        return list(DEFAULT_CENSOR_CLASSES)
    if isinstance(value, list):
        return [str(name) for name in value]
    return list(DEFAULT_CENSOR_CLASSES)


def set_censor_classes(names) -> None:
    from Imervue.user_settings.user_setting_dict import schedule_save
    _settings()[CENSOR_SETTING] = [str(n).strip() for n in names if str(n).strip()]
    schedule_save()


def censor_class_ids(classes=None, censor=None) -> frozenset[int]:
    """Class ids to censor: the indices in the class list whose names are in
    the censor set. Unknown censor names are ignored."""
    class_list = classes if classes is not None else get_classes()
    censor_names = set(censor if censor is not None else get_censor_classes())
    return frozenset(i for i, name in enumerate(class_list) if name in censor_names)


def scene_class_id(classes=None) -> int | None:
    """Class id of the scene-level (make_love) class, or None if absent."""
    class_list = classes if classes is not None else get_classes()
    return class_list.index(SCENE_CLASS_NAME) if SCENE_CLASS_NAME in class_list else None
