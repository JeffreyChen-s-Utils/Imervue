"""Tests for the pet pointer-interaction pure helpers.

The drag / press / release event handlers in
:class:`Imervue.desktop_pet.pet_interaction.PetInteraction` are Qt-only
and exercised through :class:`PetWindow`; the two pure helpers extracted
alongside them — the inverse pan/zoom transform and the LLM situation
tag — are deterministic maths / string logic and tested directly here
without a live GL canvas.
"""
from __future__ import annotations

import math

from Imervue.desktop_pet.pet_interaction import (
    CLICK_RADIUS_PX,
    llm_situation_tag,
    widget_to_image,
)


# ---------------------------------------------------------------
# widget_to_image — inverse pan + zoom
# ---------------------------------------------------------------


def test_widget_to_image_identity_transform():
    """Zoom 1, no pan → widget coords pass straight through."""
    assert widget_to_image(10.0, 20.0, 1.0, 0.0, 0.0) == (10.0, 20.0)


def test_widget_to_image_applies_pan_then_zoom():
    """The transform subtracts pan first, then divides by zoom."""
    x, y = widget_to_image(30.0, 50.0, 2.0, 10.0, 20.0)
    assert math.isclose(x, (30.0 - 10.0) / 2.0)
    assert math.isclose(y, (50.0 - 20.0) / 2.0)


def test_widget_to_image_negative_pan():
    x, y = widget_to_image(0.0, 0.0, 1.0, -5.0, -7.0)
    assert (x, y) == (5.0, 7.0)


def test_widget_to_image_zero_zoom_is_none():
    """A degenerate (zero) zoom yields no document coordinate rather
    than a ZeroDivisionError."""
    assert widget_to_image(1.0, 1.0, 0.0, 0.0, 0.0) is None


def test_widget_to_image_negative_zoom_is_none():
    assert widget_to_image(1.0, 1.0, -1.0, 0.0, 0.0) is None


def test_widget_to_image_tiny_positive_zoom_ok():
    """Just above the zero boundary still computes."""
    result = widget_to_image(1.0, 0.0, 0.5, 0.0, 0.0)
    assert result == (2.0, 0.0)


# ---------------------------------------------------------------
# llm_situation_tag — priority chain
# ---------------------------------------------------------------


def test_llm_tag_prefers_hit_area():
    assert llm_situation_tag("head", "Wave") == "hit:head"


def test_llm_tag_falls_back_to_motion():
    assert llm_situation_tag(None, "Wave") == "motion:Wave"
    assert llm_situation_tag("", "Wave") == "motion:Wave"


def test_llm_tag_greeting_when_empty():
    assert llm_situation_tag(None, None) == "greeting"
    assert llm_situation_tag("", "") == "greeting"


# ---------------------------------------------------------------
# constants
# ---------------------------------------------------------------


def test_click_radius_is_small_positive():
    assert isinstance(CLICK_RADIUS_PX, int)
    assert 0 < CLICK_RADIUS_PX < 20
