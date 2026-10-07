"""Byte admission covers real buffers, retained cancellation and multiple windows."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view.ram_budget import (
    FALLBACK_BYTES, MIB, RamBudget, auxiliary_ram_limit, decode_reservation, image_bytes,
)


def test_actual_pyramid_bytes_deduplicate_shared_views():
    base = np.zeros((20, 30, 4), dtype=np.uint8)
    smaller = np.zeros((10, 15, 4), dtype=np.uint8)
    pyramid = SimpleNamespace(levels=[base, base[::2], smaller])
    assert image_bytes(pyramid) == base.nbytes + smaller.nbytes
    assert image_bytes(base[::2]) == base.nbytes
    assert image_bytes(object()) == 0


def test_decode_and_cache_share_the_same_exact_byte_limit():
    budget = RamBudget(100)
    first, second = object(), object()
    assert budget.reserve(first, 60)
    assert budget.reserve(second, 40)
    assert not budget.reserve(object(), 1)
    assert budget.store("first", 60, ticket=first)
    assert budget.used_bytes == 100
    budget.release(second)
    assert not budget.store("too-big", 41)
    assert budget.store("exact", 40)
    assert budget.used_bytes == 100
    budget.discard("first")
    assert budget.used_bytes == 40


def test_rejected_resize_keeps_old_reservation_until_actual_completion():
    budget = RamBudget(100)
    ticket = object()
    assert budget.reserve(ticket, 90)
    assert not budget.reserve(ticket, 101)
    assert budget.used_bytes == 90
    budget.release(ticket)
    budget.release(ticket)
    assert budget.used_bytes == 0


def test_multiple_windows_share_process_cap_and_drain_old_excess(monkeypatch):
    import weakref
    monkeypatch.setattr(RamBudget, "_windows", weakref.WeakSet())
    monkeypatch.setattr(RamBudget, "_process_limit", 100)
    first = RamBudget()
    assert first.store("existing", 80)
    second = RamBudget()
    assert first.limit_bytes == second.limit_bytes == 50
    assert not first.reserve(object(), 1)
    assert not second.reserve(object(), 21)
    assert second.reserve("job", 20)
    first.discard("existing")
    assert second.reserve("job", 50)
    assert first.reserve("job", 50)
    assert first.used_bytes + second.used_bytes == 100


def test_missing_optional_probe_preserves_byte_admission(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert auxiliary_ram_limit() == FALLBACK_BYTES
    budget = RamBudget(100)
    assert budget.store("array", image_bytes(np.zeros(100, dtype=np.uint8)))
    assert not budget.reserve("decode", 1)


@pytest.mark.parametrize("extension,recipe,expected", [
    ("jpg", None, 24), ("NEF", None, 48),
    ("jpg", SimpleNamespace(is_identity=lambda: False), 160),
    ("nef", SimpleNamespace(is_identity=lambda: True), 48),
])
def test_reservations_use_sensor_pixels_and_recipe_scratch(monkeypatch, extension, recipe, expected):
    from Imervue.image import dimensions
    monkeypatch.setattr(dimensions, "image_dimensions", lambda _path: (10000, 6000))
    assert decode_reservation(f"image.{extension}", recipe) == 60000000 * expected


def test_unknown_header_reservation_and_small_image_floor(monkeypatch):
    from Imervue.image import dimensions
    monkeypatch.setattr(dimensions, "image_dimensions", lambda _path: None)
    assert decode_reservation("unknown.svg") == 512 * MIB
    monkeypatch.setattr(dimensions, "image_dimensions", lambda _path: (1, 1))
    assert decode_reservation("tiny.png") == MIB


def test_optional_probe_errors_and_capacity_clamps(monkeypatch):
    class ProbeError(Exception):
        pass

    probe = SimpleNamespace(Error=ProbeError)
    monkeypatch.setitem(sys.modules, "psutil", probe)

    def denied():
        raise ProbeError("denied")

    probe.virtual_memory = denied
    assert auxiliary_ram_limit() == FALLBACK_BYTES
    probe.virtual_memory = lambda: SimpleNamespace(total=1024 * MIB)
    assert auxiliary_ram_limit() == 256 * MIB
    probe.virtual_memory = lambda: SimpleNamespace(total=128 * 1024 * MIB)
    assert auxiliary_ram_limit() == 8192 * MIB


def test_byte_cache_evicts_oldest_and_rejects_one_oversized_pyramid():
    from Imervue.gpu_image_view.prefetch_scheduler import PrefetchScheduler
    view = SimpleNamespace()
    scheduler = PrefetchScheduler(view)
    scheduler.budget = RamBudget(100)
    scheduler.store("a", np.zeros(60, dtype=np.uint8))
    scheduler.store("b", np.zeros(60, dtype=np.uint8))
    assert list(scheduler.cache) == ["b"]
    assert scheduler.budget.used_bytes == 60
    scheduler.store("oversize", np.zeros(101, dtype=np.uint8))
    assert list(scheduler.cache) == ["b"]
    assert scheduler.budget.used_bytes == 60
