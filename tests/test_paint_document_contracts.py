"""Public state, ownership and notification contracts across document operations."""
from copy import deepcopy

import numpy as np
import pytest

from Imervue.paint.adjustments import Adjustment
from Imervue.paint.binary_layer import BinarySettings
from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.halftone import ToneSettings
from Imervue.paint.layer_effects import LayerEffect


def _document():
    document = PaintDocument()
    document.load_image(np.full((4, 5, 4), 200, dtype=np.uint8))
    return document


@pytest.mark.parametrize(("setter", "argument", "field", "value"), [
    ("set_layer_locked", "locked", "locked", True),
    ("set_layer_lock_alpha", "lock_alpha", "lock_alpha", True),
    ("set_layer_clip", "clip", "clip", True),
    ("set_layer_mask_enabled", "enabled", "mask_enabled", False),
    ("set_layer_tone", "tone", "tone", ToneSettings()),
    ("set_layer_binary", "binary", "binary", BinarySettings()),
    ("set_layer_effects", "effects", "effects", (LayerEffect(kind="stroke"),)),
    ("set_layer_color_label", "label", "color_label", "red"),
])
def test_property_changes_notify_once_and_equal_values_are_noops(setter, argument, field, value):
    document = _document()
    layer = document.active_layer()
    observed = []
    document.listen(lambda: observed.append(getattr(layer, field)))
    change = getattr(document, setter)
    assert change(**{argument: value}) is True
    assert observed == [value]
    assert getattr(layer, field) == value
    assert change(**{argument: value}) is False
    assert observed == [value]


@pytest.mark.parametrize("setter,argument", [
    ("set_layer_locked", "locked"), ("set_layer_lock_alpha", "lock_alpha"),
    ("set_layer_clip", "clip"), ("set_layer_mask_enabled", "enabled"),
    ("set_layer_effects", "effects"),
])
def test_empty_document_does_not_consume_property_input(setter, argument):
    class UnexpectedConversion:
        def __bool__(self):
            raise AssertionError("empty document must not normalize the input")

        def __iter__(self):
            raise AssertionError("empty document must not consume effects")

    document = PaintDocument()
    assert getattr(document, setter)(123, **{argument: UnexpectedConversion()}) is False


@pytest.mark.parametrize("operation", ["property", "selection", "invalidate", "cold_damage", "cached_damage"])
def test_listener_subscription_changes_apply_to_the_next_notification(operation):
    document = _document()
    if operation == "cached_damage":
        document.composite()
    calls = []

    def first():
        calls.append("first")
        unsubscribe()
        document.listen(lambda: calls.append("third"))

    unsubscribe = document.listen(first)
    document.listen(lambda: calls.append("second"))
    actions = {
        "property": lambda: document.set_layer_locked(locked=not document.active_layer().locked),
        "selection": lambda: document.set_selection(np.ones((4, 5), dtype=bool)),
        "invalidate": document.invalidate_composite,
        "cold_damage": lambda: document.mark_composite_dirty((0, 0, 1, 1)),
        "cached_damage": lambda: document.mark_composite_dirty((0, 0, 1, 1)),
    }
    actions[operation]()
    assert calls == ["first", "second"]
    actions[operation]()
    assert calls == ["first", "second", "second", "third"]


@pytest.mark.parametrize("kind", ["raster", "vector", "adjustment"])
@pytest.mark.parametrize("above_active", [False, True])
def test_new_layer_insertion_publishes_consistent_active_and_reference_indices(kind, above_active):
    document = _document()
    document.add_layer(name="middle")
    reference = document.add_layer(name="reference")
    document.set_reference_layer_index(2)
    document.set_active_layer(0)
    observations = []
    document.listen(lambda: observations.append((document.active_layer(), document.reference_layer_index())))
    creators = {
        "raster": document.add_layer,
        "vector": document.add_vector_layer,
        "adjustment": lambda **kwargs: document.add_adjustment_layer(Adjustment(kind="levels"), **kwargs),
    }
    added = creators[kind](name="new", on_top_of_active=above_active)
    assert document.active_layer_index() == (1 if above_active else 3)
    reference_index = 3 if above_active else 2
    assert document.layer_at(reference_index) is reference
    assert observations == [(added, reference_index)]
    assert added.image.shape == (4, 5, 4)
    assert not added.image.any()


@pytest.mark.parametrize("query,expected", [
    ("", [0, 1, 2]), (" \t ", [0, 1, 2]), ("RED ink", [1]), ("藍", [2]),
    ("ink missing", []), ("İ", [2]),
])
def test_layer_search_keeps_and_matching_and_unicode_case_folding(query, expected):
    document = _document()
    document.add_layer(name="Red Ink")
    document.add_layer(name="İ 藍 Ink")
    assert document.find_layers(query) == expected


def test_content_adoption_and_clone_keep_ownership_and_listener_boundaries():
    document = _document()
    document.add_layer_mask(fill=120)
    document.set_selection(np.ones((4, 5), dtype=bool))
    document.save_selection("ink")
    document.set_reference_layer_index(0)
    cached = document.composite()
    events = []
    document.listen(lambda: events.append(document.active_layer().name))
    clone = deepcopy(document)
    clone.active_layer().image[:] = 0
    clone.active_layer().mask[:] = 0
    clone.selection()[:] = False
    clone.set_layer_attribute(0, name="replacement")
    assert events == []
    assert document.active_layer().image.any()
    assert document.active_layer().mask.any()
    assert document.selection().all()
    document.adopt_content(clone)
    assert events == ["replacement"]
    assert document.active_layer() is clone.active_layer()
    assert document.reference_layer_index() == 0
    assert document.composite() is not cached
    saved = document.named_selection("ink")
    saved[:] = False
    assert document.named_selection("ink").all()


@pytest.mark.parametrize("invalid", ["layer_shape", "selection_shape", "selection_dtype"])
def test_invalid_state_replacement_leaves_existing_content_and_listeners_untouched(invalid):
    document = _document()
    original = document.active_layer()
    events = []
    document.listen(lambda: events.append(True))
    layers = [Layer(name="new", image=np.zeros((4, 5, 4), dtype=np.uint8))]
    selection = np.ones((4, 5), dtype=bool)
    if invalid == "layer_shape":
        layers.append(Layer(name="bad", image=np.zeros((1, 1, 4), dtype=np.uint8)))
    elif invalid == "selection_shape":
        selection = np.ones((1, 1), dtype=bool)
    else:
        selection = np.ones((4, 5), dtype=np.uint8)
    with pytest.raises(ValueError):
        document.replace_state(layers=layers, selection=selection)
    assert document.active_layer() is original
    assert document.layer_count == 1
    assert events == []
