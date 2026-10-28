"""Saved develop preset lookup and batch application."""
from __future__ import annotations

import sys
from PIL import Image
from pathlib import Path
from Imervue.cli_batch import _write
from Imervue.cli_paths import _NO_INPUTS, iter_image_paths
from Imervue.image.shown import load_shown_rgba


def op_preset(src: Path, target: Path, args) -> None:
    Image.fromarray(args.recipe.apply(load_shown_rgba(src)), mode="RGBA").save(target)


def cmd_preset(args) -> int:
    """Apply a saved develop preset (by name) to each input image."""
    from Imervue.image.develop_presets import PRESETS_KEY, DevelopPresetStore
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    if PRESETS_KEY not in user_setting_dict:
        from Imervue.user_settings.user_setting_dict import read_user_setting
        read_user_setting()
    store = DevelopPresetStore(user_setting_dict)
    recipe = store.get(args.name)
    if recipe is None:
        print(f"unknown preset {args.name!r}; available: {store.names()}", file=sys.stderr)
        return 1
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    args.recipe = recipe
    return _write(args, paths, op_preset, "_preset", lambda _a: ".png")
