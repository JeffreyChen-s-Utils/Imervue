"""Tests for the puppet plugin's optional-dependency manifest.

The actual ``ensure_dependencies`` install path runs pip subprocesses
and is unit-tested in ``test_pip_installer.py`` against the main app.
Here we only verify that:

* The per-feature lists have the right shape.
* ``missing_packages`` returns the subset whose ``import_name`` isn't
  importable — monkeypatched so the test stays deterministic in CI
  where ``cv2`` / ``mediapipe`` / ``sounddevice`` may or may not be
  present.
* ``all_optional_packages`` dedupes by import name so the bulk
  installer doesn't try to install the same package twice.
"""
from __future__ import annotations

import importlib.util

from puppet.requirements import (
    FEATURE_PACKAGES,
    LIPSYNC_PACKAGES,
    WEBCAM_PACKAGES,
    all_optional_packages,
    missing_packages,
)


def test_feature_packages_lists_have_tuple_shape():
    for packages in FEATURE_PACKAGES.values():
        for entry in packages:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            import_name, pip_name = entry
            assert isinstance(import_name, str) and import_name
            assert isinstance(pip_name, str) and pip_name


def test_webcam_packages_cover_cv2_and_mediapipe():
    import_names = {p[0] for p in WEBCAM_PACKAGES}
    assert {"cv2", "mediapipe"} == import_names


def test_lipsync_packages_cover_sounddevice():
    import_names = {p[0] for p in LIPSYNC_PACKAGES}
    assert import_names == {"sounddevice"}


def test_missing_packages_returns_empty_when_all_present(monkeypatch):
    """When every import name resolves, ``missing_packages`` returns
    an empty list — we monkeypatch ``find_spec`` so the test doesn't
    depend on the runner's actual installs."""
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name: object(),
    )
    assert missing_packages([("cv2", "opencv-python")]) == []


def test_missing_packages_returns_the_missing_subset(monkeypatch):
    """When only one of two packages resolves, only the other is
    returned."""
    def fake_find_spec(name):
        return object() if name == "cv2" else None
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    out = missing_packages(WEBCAM_PACKAGES)
    assert out == [("mediapipe", "mediapipe")]


def test_missing_packages_returns_everything_when_none_present(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    assert missing_packages(WEBCAM_PACKAGES) == WEBCAM_PACKAGES


def test_all_optional_packages_dedupes_by_import_name():
    """If a future feature happens to list a package already covered
    by another feature, the bulk installer must not run pip on it
    twice. We add a duplicate entry temporarily to exercise the
    dedupe path without monkeypatching."""
    original = dict(FEATURE_PACKAGES)
    try:
        FEATURE_PACKAGES["dupe"] = [("cv2", "opencv-python")]
        names = [p[0] for p in all_optional_packages()]
        assert names.count("cv2") == 1
    finally:
        FEATURE_PACKAGES.clear()
        FEATURE_PACKAGES.update(original)


def test_all_optional_packages_covers_every_feature():
    """Every package that appears in any feature list must appear in
    the union — protects against a refactor that forgets to plumb a
    new feature into the bulk install."""
    expected = set()
    for packages in FEATURE_PACKAGES.values():
        for import_name, _ in packages:
            expected.add(import_name)
    union_names = {p[0] for p in all_optional_packages()}
    assert union_names == expected
