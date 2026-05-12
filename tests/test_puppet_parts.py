"""Tests for the Part-tree resolver.

The resolver walks an arbitrary hierarchy and returns the effective
``(visible, opacity)`` for each drawable. Tests cover: flat
single-level Parts, nested Parts, descendant cascade of visibility and
opacity multiplication, missing-drawable resilience, and the cycle
guard that keeps a malformed document from stack-overflowing.
"""
from __future__ import annotations

import pytest

from puppet.document import Drawable, Part, PuppetDocument
from puppet.document_io import from_zip_bytes, to_zip_bytes
from puppet.runtime import resolve_part_state


def _drawable(id_: str) -> Drawable:
    return Drawable(
        id=id_, texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )


def _doc_with_parts(parts: list[Part], drawable_ids: tuple[str, ...]) -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [_drawable(d) for d in drawable_ids]
    doc.parts = parts
    return doc


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def test_no_parts_returns_identity_state():
    doc = _doc_with_parts([], ("a", "b"))
    state = resolve_part_state(doc)
    assert state == {"a": (True, 1.0), "b": (True, 1.0)}


def test_flat_part_applies_opacity_and_visibility():
    doc = _doc_with_parts(
        [Part(id="hair", drawables=["a", "b"], opacity=0.5, visible=True)],
        ("a", "b", "c"),
    )
    state = resolve_part_state(doc)
    assert state["a"] == (True, 0.5)
    assert state["b"] == (True, 0.5)
    # 'c' is not in any Part — keeps identity
    assert state["c"] == (True, 1.0)


def test_hidden_part_hides_all_descendants():
    doc = _doc_with_parts(
        [Part(id="hair", drawables=["a", "b"], visible=False)],
        ("a", "b"),
    )
    state = resolve_part_state(doc)
    assert state["a"][0] is False
    assert state["b"][0] is False


def test_nested_parts_multiply_opacity():
    doc = _doc_with_parts(
        [
            Part(id="root", children=["mid"], opacity=0.5),
            Part(id="mid", drawables=["a"], opacity=0.5),
        ],
        ("a",),
    )
    state = resolve_part_state(doc)
    assert state["a"][1] == pytest.approx(0.25)


def test_nested_parts_propagate_hidden():
    doc = _doc_with_parts(
        [
            Part(id="root", children=["mid"], visible=False),
            Part(id="mid", drawables=["a"], visible=True),
        ],
        ("a",),
    )
    state = resolve_part_state(doc)
    assert state["a"][0] is False


def test_part_pointing_at_missing_drawable_is_silent():
    doc = _doc_with_parts(
        [Part(id="hair", drawables=["a", "ghost"], opacity=0.5)],
        ("a",),
    )
    # ghost is not in document.drawables → silently dropped, no crash
    state = resolve_part_state(doc)
    assert state["a"] == (True, 0.5)
    assert "ghost" not in state


def test_resolver_guards_against_cycles():
    """A Part claiming itself as a child mustn't recurse infinitely."""
    doc = _doc_with_parts(
        [Part(id="loop", drawables=["a"], children=["loop"])],
        ("a",),
    )
    state = resolve_part_state(doc)
    assert state["a"] == (True, 1.0)


def test_mutual_cycle_between_parts_is_safe():
    doc = _doc_with_parts(
        [
            Part(id="alpha", drawables=["a"], children=["beta"]),
            Part(id="beta", drawables=["b"], children=["alpha"]),
        ],
        ("a", "b"),
    )
    # Traversal finishes; both drawables resolved
    state = resolve_part_state(doc)
    assert state["a"] == (True, 1.0)
    assert state["b"] == (True, 1.0)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_parts_round_trip_through_zip():
    doc = _doc_with_parts(
        [Part(id="hair", drawables=["a"], opacity=0.5, visible=False)],
        ("a",),
    )
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert len(restored.parts) == 1
    assert restored.parts[0].id == "hair"
    assert restored.parts[0].opacity == pytest.approx(0.5)
    assert restored.parts[0].visible is False


def test_display_names_round_trip_through_zip():
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [_drawable("x")]
    doc.display_names = {"ParamAngleX": "Head X", "PartHair": "Hair"}
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.display_names == {"ParamAngleX": "Head X", "PartHair": "Hair"}
