"""
Undo/Redo 命令
QUndoCommand implementations for various operations.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class RotateCommand(QUndoCommand):
    """旋轉操作的 undo/redo 命令"""

    def __init__(self, main_gui: GPUImageView, clockwise: bool):
        super().__init__("Rotate " + ("CW" if clockwise else "CCW"))
        self._gui = main_gui
        self._clockwise = clockwise

    def redo(self):
        from Imervue.gpu_image_view.actions.keyboard_actions import rotate_current_image
        rotate_current_image(self._gui, clockwise=self._clockwise)

    def undo(self):
        from Imervue.gpu_image_view.actions.keyboard_actions import rotate_current_image
        rotate_current_image(self._gui, clockwise=not self._clockwise)


class RatingCommand(QUndoCommand):
    """評分操作的 undo/redo 命令"""

    def __init__(self, path: str, old_rating: int | None, new_rating: int | None):
        super().__init__(f"Rate {Path(path).name}")
        self._path = path
        self._old = old_rating
        self._new = new_rating

    def redo(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        ratings = user_setting_dict.get("image_ratings", {})
        if self._new is None:
            ratings.pop(self._path, None)
        else:
            ratings[self._path] = self._new
        user_setting_dict["image_ratings"] = ratings

    def undo(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        ratings = user_setting_dict.get("image_ratings", {})
        if self._old is None:
            ratings.pop(self._path, None)
        else:
            ratings[self._path] = self._old
        user_setting_dict["image_ratings"] = ratings


class FavoriteCommand(QUndoCommand):
    """收藏切換的 undo/redo 命令"""

    def __init__(self, path: str, was_fav: bool):
        super().__init__(f"Toggle favorite {Path(path).name}")
        self._path = path
        self._was_fav = was_fav

    def redo(self):
        self._toggle()

    def undo(self):
        self._toggle()

    def _toggle(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        favorites = set(user_setting_dict.get("image_favorites", []))
        if self._path in favorites:
            favorites.discard(self._path)
        else:
            favorites.add(self._path)
        user_setting_dict["image_favorites"] = list(favorites)
