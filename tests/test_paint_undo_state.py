"""Undo restores document structure and editable state, including file content."""
from __future__ import annotations

import gc
import weakref

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.document_io import _document_to_arrays, load_document, save_document
from Imervue.paint.undo_stack import UndoStack
from Imervue.paint.vector_layer import VectorStroke


def _document():
    document = PaintDocument()
    document.load_image(np.full((4, 6, 4), (20, 30, 40, 255), dtype=np.uint8))
    layer = document.add_layer(name="ink")
    layer.image[1, 2] = (200, 100, 50, 255)
    document.create_group("art", opacity=0.75)
    document.set_layer_group(group="art")
    document.add_layer_mask(fill=180)
    document.set_reference_layer_index(0)
    document.set_selection(np.ones(document.shape, dtype=np.bool_))
    document.save_selection("all")
    return document


def _assert_content(document, expected):
    actual = _document_to_arrays(document)
    assert actual.keys() == expected.keys()
    for name, array in expected.items():
        np.testing.assert_array_equal(actual[name], array, err_msg=name)


def _properties(document):
    document.set_layer_attribute(1, name="renamed", opacity=0.3, blend_mode="multiply",
                                 visible=False, locked=True)
    document.set_layer_lock_alpha(lock_alpha=True)
    document.set_layer_clip(clip=True)
    document.set_layer_mask_enabled(enabled=False)
    document.active_layer().mask[0, 0] = 20
    document.set_group_attribute("art", opacity=0.2, visible=False)
    document.rename_group("art", "renamed group")
    document.set_reference_layer_index(1)
    document.set_selection(None)
    document.delete_named_selection("all")


def _vector(document):
    layer = document.add_vector_layer(name="lines")
    layer.vector_data.add(VectorStroke(points=((0., 0.), (3., 2.))))


@pytest.mark.parametrize("operation", [
    lambda doc: doc.add_layer(name="new"),
    lambda doc: doc.remove_active_layer(),
    lambda doc: doc.move_active_layer(up=False),
    lambda doc: doc.duplicate_active_layer(),
    lambda doc: doc.merge_down(),
    lambda doc: doc.apply_layer_mask(),
    _properties,
    _vector,
])
def test_full_document_undo_redo_and_native_roundtrip(operation, tmp_path):
    document = _document()
    before = {name: arr.copy() for name, arr in _document_to_arrays(document).items()}
    stack = UndoStack(document)
    operation(document)
    after = {name: arr.copy() for name, arr in _document_to_arrays(document).items()}
    stack.commit()
    for _ in range(3):
        assert stack.undo()
        _assert_content(document, before)
        assert stack.redo()
        _assert_content(document, after)
    path = tmp_path / "restored.imervue"
    save_document(document, path)
    _assert_content(load_document(path), after)


def test_deleted_collected_layer_is_recreated_with_its_state():
    document = _document()
    before = _document_to_arrays(document)
    layer = document.active_layer()
    ref = weakref.ref(layer)
    stack = UndoStack(document)
    document.remove_active_layer()
    del layer
    gc.collect()
    assert ref() is None
    stack.commit()
    assert stack.undo()
    _assert_content(document, before)


def test_restore_keeps_document_listeners_and_live_layer_identity():
    document = _document()
    layer = document.active_layer()
    notifications = []
    document.listen(lambda: notifications.append(document.layer_count))
    stack = UndoStack(document)
    document.move_active_layer(up=False)
    stack.commit()
    notifications.clear()
    assert stack.undo()
    assert document.active_layer() is layer
    assert notifications == [2]
    assert stack.redo()
    assert notifications == [2, 2]


def test_empty_document_baseline_and_geometry_restore():
    document = PaintDocument()
    stack = UndoStack(document)
    document.load_image(np.zeros((2, 3, 4), dtype=np.uint8))
    stack.commit()
    assert stack.undo()
    assert document.layer_count == 0
    assert stack.redo()
    assert document.shape == (2, 3)
    document.rotate_90_cw()
    stack.commit()
    assert stack.undo()
    assert document.shape == (2, 3)
    assert stack.redo()
    assert document.shape == (3, 2)
