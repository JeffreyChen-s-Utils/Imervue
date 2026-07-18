"""Regression guard: filter / effect / utility dialogs that run a background
QThread use the shared WorkerHostMixin for teardown.

Each of these dialogs applies its effect on a ``self._worker`` QThread (many
share ``EffectWorker``) and is shown as a throwaway ``exec()`` dialog. None had
a closeEvent or reject override, so cancelling or closing mid-run destroyed the
live thread and could abort the process (0xC0000409). They now inherit
:class:`WorkerHostMixin`, whose reject and closeEvent both join the worker.
This fails if any dialog stops inheriting the mixin or re-introduces a
shadowing ``closeEvent``.
"""
from __future__ import annotations

import importlib

import pytest

from Imervue.plugin.worker_host import WorkerHostMixin

_DIALOGS = [
    ("anaglyph_dialog", "AnaglyphDialog"),
    ("animation_edit_dialog", "AnimationEditDialog"),
    ("binarize_dialog", "BinarizeDialog"),
    ("clahe_dialog", "ClaheDialog"),
    ("collage_dialog", "CollageDialog"),
    ("colormap_dialog", "ColormapDialog"),
    ("culling_dialog", "CullingDialog"),
    ("defringe_dialog", "DefringeDialog"),
    ("detail_equalizer_dialog", "DetailEqualizerDialog"),
    ("distort_dialog", "DistortDialog"),
    ("dither_dialog", "DitherDialog"),
    ("emboss_dialog", "EmbossDialog"),
    ("film_negative_dialog", "FilmNegativeDialog"),
    ("filmic_tonemap_dialog", "FilmicTonemapDialog"),
    ("flatten_field_dialog", "FlattenFieldDialog"),
    ("frosted_glass_dialog", "FrostedGlassDialog"),
    ("glow_dialog", "GlowDialog"),
    ("graduated_density_dialog", "GraduatedDensityDialog"),
    ("hsl_mixer_dialog", "HslMixerDialog"),
    ("id_photo_sheet_dialog", "IdPhotoSheetDialog"),
    ("kaleidoscope_dialog", "KaleidoscopeDialog"),
    ("local_contrast_dialog", "LocalContrastDialog"),
    ("meme_dialog", "MemeDialog"),
    ("otsu_dialog", "OtsuDialog"),
    ("photo_frame_dialog", "PhotoFrameDialog"),
    ("pixel_sort_dialog", "PixelSortDialog"),
    ("polar_dialog", "PolarDialog"),
    ("scale_bar_dialog", "ScaleBarDialog"),
    ("solarize_dialog", "SolarizeDialog"),
    ("steganography_dialog", "SteganographyDialog"),
    ("tiny_planet_dialog", "TinyPlanetDialog"),
    ("tone_equalizer_dialog", "ToneEqualizerDialog"),
    ("velvia_dialog", "VelviaDialog"),
]


def _dialog_class(module_name, cls_name):
    return getattr(importlib.import_module(f"Imervue.gui.{module_name}"), cls_name)


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_inherits_worker_host_mixin(module_name, cls_name):
    assert issubclass(_dialog_class(module_name, cls_name), WorkerHostMixin)


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_defers_teardown_to_the_mixin(module_name, cls_name):
    assert "closeEvent" not in _dialog_class(module_name, cls_name).__dict__
