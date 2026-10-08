"""Pixel sharing stays immutable across every array geometry and dtype."""
from __future__ import annotations

import copy
import gc
import weakref

import numpy as np
import pytest

from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument
from Imervue.paint.history_pixels import PixelStore, arrays_in, owned_bytes


@pytest.mark.parametrize("shape", [(), (0,), (5,), (0, 3), (3, 0), (3, 5), (257, 259, 4)])
@pytest.mark.parametrize("dtype", [np.uint8, np.bool_, np.float32])
def test_owned_tiles_roundtrip_strides_empty_scalars_and_types(shape, dtype):
    original = np.ones(shape, dtype=dtype)
    if len(shape) > 1:
        original = original[::-1]
    snapshot = PixelStore().freeze(original)
    original[...] = 0
    restored = copy.deepcopy(snapshot)
    np.testing.assert_array_equal(restored, np.ones(shape, dtype=dtype))
    restored[...] = 2
    np.testing.assert_array_equal(copy.deepcopy(snapshot), np.ones(shape, dtype=dtype))


def test_one_dirty_tile_shares_the_rest_and_full_capture_detects_unmarked_edits():
    array = np.zeros((512, 512, 4), dtype=np.uint8)
    store = PixelStore()
    before = store.freeze(array)
    array[250:270, 10:20] = 123
    after = store.freeze(array, before, region=DamageRect(10, 250, 10, 20))
    assert after.chunks[0] is not before.chunks[0]
    assert after.chunks[2] is not before.chunks[2]
    assert after.chunks[1] is before.chunks[1]
    assert after.chunks[3] is before.chunks[3]
    array[400, 400] = 99
    full = store.freeze(array, after)
    np.testing.assert_array_equal(copy.deepcopy(full), array)
    assert full.chunks[3] is not after.chunks[3]


def test_interning_releases_abandoned_tiles():
    store = PixelStore()
    array = np.zeros((8, 8), dtype=np.uint8)
    first = store.freeze(array)
    second = store.freeze(array.copy())
    assert first.chunks[0] is second.chunks[0]
    ref = weakref.ref(first.chunks[0])
    del first, second
    gc.collect()
    assert ref() is None
    assert not store._chunks


def test_changed_shape_or_dtype_ignores_regional_hint_and_restores_all_pixels():
    store = PixelStore()
    before = store.freeze(np.zeros((2, 3), dtype=np.uint8))
    array = np.ones((3, 2), dtype=np.float32)
    snapshot = store.freeze(array, before, region=DamageRect(0, 0, 1, 1))
    np.testing.assert_array_equal(copy.deepcopy(snapshot), array)


def test_object_arrays_are_rejected():
    with pytest.raises(ValueError, match="Python objects"):
        PixelStore().freeze(np.array([object()], dtype=object))


def test_content_walk_does_not_follow_composite_runtime_callbacks_or_cycles():
    doc = PaintDocument()
    doc.load_image(np.zeros((2, 3, 4), dtype=np.uint8))
    runtime = np.ones((5, 5), dtype=np.uint8)
    doc._composite_cache = runtime
    doc.listen(lambda: runtime)
    arrays = list(arrays_in(doc))
    assert len(arrays) == 1
    assert arrays[0] is doc.active_layer().image
    cycle = [runtime]
    cycle.append(cycle)
    assert list(arrays_in(cycle))[0] is runtime
    assert owned_bytes(cycle) > runtime.nbytes


def test_accounting_counts_shared_tiles_once():
    store = PixelStore()
    array = np.zeros((256, 256, 4), dtype=np.uint8)
    first = store.freeze(array)
    second = store.freeze(array.copy())
    assert owned_bytes((first, second)) < array.nbytes * 1.1
