"""Tests for layer-group support."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import (
    GROUP_BLEND_MODES,
    Layer,
    LayerGroup,
    PaintDocument,
)


@pytest.fixture
def document():
    doc = PaintDocument()
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    base[..., 3] = 255
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (200, 100, 50)
    above.image[..., 3] = 255
    return doc


# ---------------------------------------------------------------------------
# LayerGroup defaults + validation
# ---------------------------------------------------------------------------


def test_layer_group_defaults():
    g = LayerGroup(name="G")
    assert g.visible is True
    assert g.opacity == pytest.approx(1.0)
    assert g.blend_mode == "pass_through"
    assert g.locked is False
    assert g.expanded is True


def test_layer_group_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        LayerGroup(name="   ")


def test_layer_group_rejects_unknown_blend():
    with pytest.raises(ValueError, match="blend_mode"):
        LayerGroup(name="G", blend_mode="quantum")


def test_layer_group_clamps_opacity():
    g = LayerGroup(name="G", opacity=2.0)
    assert g.opacity == pytest.approx(1.0)


def test_group_blend_modes_includes_pass_through():
    assert "pass_through" in GROUP_BLEND_MODES
    assert "normal" in GROUP_BLEND_MODES


def test_layer_default_group_is_none():
    layer = Layer(name="L", image=np.zeros((4, 4, 4), dtype=np.uint8))
    assert layer.group is None


# ---------------------------------------------------------------------------
# create_group / delete_group
# ---------------------------------------------------------------------------


def test_create_group_registers_new_group(document):
    g = document.create_group("Inks")
    assert g.name == "Inks"
    assert document.group("Inks") is g
    assert "Inks" in [grp.name for grp in document.groups()]


def test_create_group_rejects_duplicate(document):
    document.create_group("Inks")
    with pytest.raises(ValueError, match="already exists"):
        document.create_group("Inks")


def test_create_group_passes_attrs(document):
    g = document.create_group("Inks", opacity=0.5, blend_mode="multiply")
    assert g.opacity == pytest.approx(0.5)
    assert g.blend_mode == "multiply"


def test_delete_group_dissolves_layer_membership(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    assert document.delete_group("Inks") is True
    # Layer's group tag was cleared (dissolve = default).
    assert document.active_layer().group is None


def test_delete_group_non_dissolve_removes_member_layers(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    pre_count = document.layer_count
    document.delete_group("Inks", dissolve=False)
    assert document.layer_count == pre_count - 1


def test_delete_unknown_group_returns_false(document):
    assert document.delete_group("Ghost") is False


# ---------------------------------------------------------------------------
# set_layer_group
# ---------------------------------------------------------------------------


def test_set_layer_group_assigns_membership(document):
    document.create_group("Inks")
    assert document.set_layer_group(group="Inks") is True
    assert document.active_layer().group == "Inks"


def test_set_layer_group_can_clear_membership(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    assert document.set_layer_group(group=None) is True
    assert document.active_layer().group is None


def test_set_layer_group_idempotent_returns_false(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    assert document.set_layer_group(group="Inks") is False


def test_set_layer_group_rejects_unknown(document):
    with pytest.raises(ValueError, match="unknown group"):
        document.set_layer_group(group="Phantom")


# ---------------------------------------------------------------------------
# set_group_attribute
# ---------------------------------------------------------------------------


def test_set_group_attribute_updates_field(document):
    document.create_group("Inks")
    assert document.set_group_attribute("Inks", opacity=0.5) is True
    assert document.group("Inks").opacity == pytest.approx(0.5)


def test_set_group_attribute_clamps_opacity(document):
    document.create_group("Inks")
    document.set_group_attribute("Inks", opacity=2.5)
    assert document.group("Inks").opacity == pytest.approx(1.0)


def test_set_group_attribute_idempotent(document):
    document.create_group("Inks", opacity=0.5)
    assert document.set_group_attribute("Inks", opacity=0.5) is False


def test_set_group_attribute_rejects_unknown_group(document):
    with pytest.raises(ValueError, match="unknown group"):
        document.set_group_attribute("Ghost", visible=False)


def test_set_group_attribute_rejects_unknown_field(document):
    document.create_group("Inks")
    with pytest.raises(ValueError, match="unknown"):
        document.set_group_attribute("Inks", thickness=4)


def test_set_group_attribute_rejects_unknown_blend(document):
    document.create_group("Inks")
    with pytest.raises(ValueError, match="blend_mode"):
        document.set_group_attribute("Inks", blend_mode="quantum")


def test_set_group_attribute_rejects_renaming_via_attribute(document):
    document.create_group("Inks")
    with pytest.raises(ValueError, match="immutable"):
        document.set_group_attribute("Inks", name="Renamed")


# ---------------------------------------------------------------------------
# rename_group
# ---------------------------------------------------------------------------


def test_rename_group_updates_member_tags(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    document.rename_group("Inks", "Pencils")
    assert document.group("Inks") is None
    assert document.group("Pencils") is not None
    assert document.active_layer().group == "Pencils"


def test_rename_group_to_existing_raises(document):
    document.create_group("Inks")
    document.create_group("Pencils")
    with pytest.raises(ValueError, match="already exists"):
        document.rename_group("Inks", "Pencils")


def test_rename_group_idempotent(document):
    document.create_group("Inks")
    assert document.rename_group("Inks", "Inks") is False


def test_rename_unknown_group_raises(document):
    with pytest.raises(ValueError, match="unknown group"):
        document.rename_group("Ghost", "X")


def test_rename_to_blank_raises(document):
    document.create_group("Inks")
    with pytest.raises(ValueError, match="non-empty"):
        document.rename_group("Inks", "  ")


# ---------------------------------------------------------------------------
# Compositing respects groups
# ---------------------------------------------------------------------------


def test_composite_skips_layers_in_hidden_group(document):
    document.create_group("Inks", visible=False)
    document.set_layer_group(group="Inks")
    # active layer is the "Above" layer with red pixels — invisible
    # via group.
    out = document.composite()
    # Background was zero RGB, fully opaque; result should still be zero RGB.
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_composite_multiplies_group_opacity(document):
    # Move "Above" into a group with 0.5 opacity. The above layer is
    # red (200, 100, 50) opaque-on-black. With group opacity 0.5 the
    # final pixel should be ~100, 50, 25.
    document.create_group("Inks", opacity=0.5)
    document.set_layer_group(group="Inks")
    out = document.composite()
    assert abs(int(out[0, 0, 0]) - 100) <= 2


def test_composite_layers_outside_groups_unaffected(document):
    document.create_group("Inks", visible=False)
    # Don't assign — group exists but no layer is in it.
    out = document.composite()
    # Above (red) is unaffected by hidden group it doesn't belong to.
    assert tuple(out[0, 0, :3]) == (200, 100, 50)


# ---------------------------------------------------------------------------
# Layer-stack ops play nicely with groups
# ---------------------------------------------------------------------------


def test_duplicate_layer_carries_group(document):
    document.create_group("Inks")
    document.set_layer_group(group="Inks")
    document.duplicate_active_layer()
    copies = [layer for layer in document.layers() if layer.group == "Inks"]
    assert len(copies) == 2


def test_merge_visible_skips_hidden_group_members(document):
    """Layers inside a hidden group are not included in merge_visible."""
    document.add_layer(name="Third")
    document.layers()[2].image[..., :3] = (10, 10, 10)
    document.layers()[2].image[..., 3] = 255
    document.create_group("Hidden", visible=False)
    document.set_layer_group(index=1, group="Hidden")
    document.merge_visible()
    # The hidden group's member layer must survive, since merge_visible
    # only collapses layers that were actually in the visible composite.
    names = [layer.name for layer in document.layers()]
    assert "Above" in names


def test_flatten_drops_hidden_group_members(document):
    document.create_group("Hidden", visible=False)
    document.set_layer_group(group="Hidden")
    document.flatten()
    # After flatten, only the Background contribution is in the final
    # layer; the hidden group's layer was dropped.
    out = document.layers()[0].image
    # Background was zero-RGB opaque; hidden red layer dropped.
    assert tuple(out[0, 0, :3]) == (0, 0, 0)
