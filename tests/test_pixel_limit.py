"""Tests for fitting Pillow's pixel limit to the machine and serialising giant decodes."""
from __future__ import annotations

import sys
import threading

import pytest
from PIL import Image

from Imervue.system import pixel_limit as mod
from Imervue.system.pixel_limit import (
    DEFAULT_MAX_IMAGE_PIXELS,
    decode_slot,
    pixel_limit_for,
    raise_pixel_limit,
    total_memory_bytes,
)

_GIANT = DEFAULT_MAX_IMAGE_PIXELS + 1


def test_the_default_matches_pillows_own():
    assert DEFAULT_MAX_IMAGE_PIXELS == 89_478_485


@pytest.mark.parametrize("memory", [None, 0, -5])
def test_unknown_memory_keeps_pillows_limit(memory):
    assert pixel_limit_for(memory) == DEFAULT_MAX_IMAGE_PIXELS


def test_little_memory_never_goes_below_pillows_limit():
    assert pixel_limit_for(1_000_000_000) == DEFAULT_MAX_IMAGE_PIXELS


def test_the_refusal_lands_where_a_decode_needs_all_the_memory():
    sixteen_gb = 16 * 1024 ** 3
    limit = pixel_limit_for(sixteen_gb)
    assert limit == sixteen_gb // 24
    assert 2 * limit * 12 <= sixteen_gb             # Pillow refuses at twice the limit


def test_this_machine_reports_its_memory():
    memory = total_memory_bytes()
    assert memory is None or memory > 0


def test_outside_windows_memory_comes_from_sysconf(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    values = {"SC_PAGE_SIZE": 4096, "SC_PHYS_PAGES": 1000}
    monkeypatch.setattr(mod.os, "sysconf", values.__getitem__, raising=False)
    assert total_memory_bytes() == 4_096_000


def test_without_sysconf_memory_is_unknown(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    def missing(_name):
        raise ValueError("unrecognized configuration name")

    monkeypatch.setattr(mod.os, "sysconf", missing, raising=False)
    assert total_memory_bytes() is None


def test_raise_pixel_limit_sets_pillows_limit(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", Image.MAX_IMAGE_PIXELS)   # restored after
    monkeypatch.setattr(mod, "total_memory_bytes", lambda: 48 * 1024 ** 3)
    assert raise_pixel_limit() == 48 * 1024 ** 3 // 24
    assert Image.MAX_IMAGE_PIXELS == 48 * 1024 ** 3 // 24


def _holding_a_giant_slot():
    held, release = threading.Event(), threading.Event()

    def hold():
        with decode_slot(_GIANT):
            held.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(5)
    return holder, release


def test_a_second_giant_waits_for_the_first():
    holder, release = _holding_a_giant_slot()
    entered = threading.Event()

    def second():
        with decode_slot(_GIANT):
            entered.set()

    waiter = threading.Thread(target=second)
    try:
        waiter.start()
        assert not entered.wait(0.2)
        release.set()
        assert entered.wait(5)
    finally:
        release.set()
        holder.join(5)
        waiter.join(5)


def test_an_ordinary_picture_never_waits():
    holder, release = _holding_a_giant_slot()
    try:
        with decode_slot(DEFAULT_MAX_IMAGE_PIXELS):
            pass                                        # would block forever if it took the slot
    finally:
        release.set()
        holder.join(5)
