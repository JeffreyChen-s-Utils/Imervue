"""Keys the UI builds at runtime (``lang.get(f"paint_tool_{tool}", ...)``) exist too.

``tests/test_translation_keys_defined.py`` only sees literal keys. These
families are formatted from a constant list, so each list is expanded here and
every resulting key must be in ``english.py`` (``tests/test_translations.py``
then requires it in every other language). A missing one showed English in
every language, or, for page templates, the raw template id.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view.cull_actions import _CULL_FALLBACKS
from Imervue.image.quality_metrics import quality_metrics
from Imervue.multi_language.english import english_word_dict
from Imervue.paint import tool_state as ts
from Imervue.paint.adjustments import ADJUSTMENT_KINDS
from Imervue.paint.comic_stamps import STAMP_LIBRARY
from Imervue.paint.liquify import WARP_KINDS
from Imervue.paint.material_library import MATERIAL_CATEGORIES
from Imervue.paint.page_templates import available_template_names
from Imervue.paint.tool_bar import TOOL_ORDER


def _tools() -> list[str]:
    return [t for t in TOOL_ORDER if t]


_FAMILIES = {
    "paint_tool_": _tools,
    "paint_template_": available_template_names,
    "paint_pages_template_": available_template_names,
    "paint_adjustment_": lambda: ADJUSTMENT_KINDS,
    "paint_blend_": lambda: ts.BLEND_MODES,
    "paint_brush_kind_": lambda: ts.BRUSH_KINDS,
    "paint_liquify_kind_": lambda: WARP_KINDS,
    "paint_material_cat_": lambda: MATERIAL_CATEGORIES,
    "cull_toast_": lambda: _CULL_FALLBACKS,
    "quality_": lambda: quality_metrics(np.zeros((8, 8, 4), np.uint8)),
    "timeline_by_": lambda: ("day", "month", "year"),
    "paint_history_": lambda: ("undo", "redo", "undo_empty", "redo_empty"),
}


@pytest.mark.parametrize("prefix", sorted(_FAMILIES))
def test_family_keys_are_defined(prefix):
    values = list(_FAMILIES[prefix]())
    assert values
    assert [v for v in values if f"{prefix}{v}" not in english_word_dict] == []


def test_comic_stamp_names_and_tooltips_are_defined():
    keys = [k for stamp in STAMP_LIBRARY for k in (stamp.key, f"{stamp.key}_tooltip")]
    assert [k for k in keys if k not in english_word_dict] == []


def test_builtin_material_names_are_translated():
    from Imervue.paint.docks.materials import material_display_name
    from Imervue.paint.material_procedural import DEFAULT_PROCEDURAL_CATALOG
    from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict

    names = [spec[0] for spec in DEFAULT_PROCEDURAL_CATALOG]
    assert names
    assert [n for n in names if material_display_name(n, english_word_dict) != n] == []
    translated = [material_display_name(n, traditional_chinese_word_dict) for n in names]
    assert [n for n, shown in zip(names, translated, strict=True) if shown == n] == []
    # A user's own material keeps its file name, even one that reads like a key.
    assert material_display_name("All", traditional_chinese_word_dict) == "All"

