"""Openers for the tone and colour entries of the Extra Tools Develop submenu.

Each opener imports its dialog lazily, so building the menu loads none of them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def _open_before_after(ui: ImervueMainWindow):
    from Imervue.gui.before_after_dialog import open_before_after_dialog
    open_before_after_dialog(ui.viewer)


def _open_develop_presets(ui: ImervueMainWindow):
    from Imervue.gui.develop_presets_dialog import open_develop_presets_dialog
    open_develop_presets_dialog(ui.viewer)


def _open_tone_curve(ui: ImervueMainWindow):
    from Imervue.gui.tone_curve_dialog import open_tone_curve
    open_tone_curve(ui.viewer)


def _open_lut(ui: ImervueMainWindow):
    from Imervue.gui.lut_dialog import open_lut
    open_lut(ui.viewer)


def _open_graduated_density(ui: ImervueMainWindow) -> None:
    from Imervue.gui.graduated_density_dialog import open_graduated_density
    open_graduated_density(ui.viewer)


def _open_velvia(ui: ImervueMainWindow) -> None:
    from Imervue.gui.velvia_dialog import open_velvia
    open_velvia(ui.viewer)


def _open_defringe(ui: ImervueMainWindow) -> None:
    from Imervue.gui.defringe_dialog import open_defringe
    open_defringe(ui.viewer)


def _open_film_negative(ui: ImervueMainWindow) -> None:
    from Imervue.gui.film_negative_dialog import open_film_negative
    open_film_negative(ui.viewer)


def _open_filmic_tonemap(ui: ImervueMainWindow) -> None:
    from Imervue.gui.filmic_tonemap_dialog import open_filmic_tonemap
    open_filmic_tonemap(ui.viewer)


def _open_tone_equalizer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.tone_equalizer_dialog import open_tone_equalizer
    open_tone_equalizer(ui.viewer)


def _open_detail_equalizer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.detail_equalizer_dialog import open_detail_equalizer
    open_detail_equalizer(ui.viewer)


def _open_levels(ui: ImervueMainWindow) -> None:
    from Imervue.gui.levels_dialog import open_levels_dialog
    open_levels_dialog(ui.viewer)


def _open_channel_mixer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.channel_mixer_dialog import open_channel_mixer_dialog
    open_channel_mixer_dialog(ui.viewer)


def _open_gradient_map(ui: ImervueMainWindow) -> None:
    from Imervue.gui.gradient_map_dialog import open_gradient_map_dialog
    open_gradient_map_dialog(ui.viewer)


def _open_auto_balance(ui: ImervueMainWindow) -> None:
    from Imervue.gui.auto_color_balance_dialog import open_auto_color_balance_dialog
    open_auto_color_balance_dialog(ui.viewer)


def _open_local_contrast(ui: ImervueMainWindow) -> None:
    from Imervue.gui.local_contrast_dialog import open_local_contrast
    open_local_contrast(ui.viewer)


def _open_hsl_mixer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.hsl_mixer_dialog import open_hsl_mixer
    open_hsl_mixer(ui.viewer)


def _open_clahe(ui: ImervueMainWindow) -> None:
    from Imervue.gui.clahe_dialog import open_clahe
    open_clahe(ui.viewer)


def _open_flatten_field(ui: ImervueMainWindow) -> None:
    from Imervue.gui.flatten_field_dialog import open_flatten_field
    open_flatten_field(ui.viewer)


def _open_layers(ui: ImervueMainWindow) -> None:
    from Imervue.gui.layers_dialog import open_layers_dialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store
    viewer = ui.viewer
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    path = images[idx]
    recipe = recipe_store.get_for_path(path) or Recipe()
    new_layers = open_layers_dialog(recipe, parent=ui)
    if new_layers is None:
        return
    new_recipe = Recipe(
        **{f.name: getattr(recipe, f.name) for f in recipe.__dataclass_fields__.values()}
    )
    new_recipe.extra = dict(recipe.extra)
    new_recipe.extra["layers"] = new_layers
    recipe_store.set_for_path(path, new_recipe)
    hook = getattr(viewer, "reload_current_image_with_recipe", None)
    if callable(hook):
        hook(path)


def _open_masks(ui: ImervueMainWindow):
    from Imervue.gui.masks_dialog import open_masks
    open_masks(ui.viewer)


def _open_split_toning(ui: ImervueMainWindow):
    from Imervue.gui.split_toning_dialog import open_split_toning
    open_split_toning(ui.viewer)


def _open_soft_proof(ui: ImervueMainWindow):
    from Imervue.gui.soft_proof_dialog import open_soft_proof
    open_soft_proof(ui.viewer)

