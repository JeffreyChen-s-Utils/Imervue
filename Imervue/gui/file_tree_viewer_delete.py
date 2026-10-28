"""Apply indexed image removals to undo, caches, navigation, and plugins."""

from __future__ import annotations


def _batch_delete_from_viewer_list(self, paths: list[str], viewer) -> None:
    """Soft-delete many viewer-list files in one pass.

    One list rebuild, one undo entry, and one GL pass — the per-file
    variant costs O(images) per path plus a GL context switch each,
    which visibly hangs the UI on large selections.
    """
    images = viewer.model.images
    doomed = set(paths)
    removed = [(idx, path) for idx, path in enumerate(images) if path in doomed]
    if not removed:
        return
    images[:] = [path for path in images if path not in doomed]
    _apply_removed_entries(self, viewer, images, removed)


def _delete_from_viewer_list(self, path: str, viewer, images: list[str]) -> None:
    idx = images.index(path)
    images.pop(idx)
    _apply_removed_entries(self, viewer, images, [(idx, path)])
    self._notify_deleted(path)


def _apply_removed_entries(self, viewer, images: list[str], removed: list[tuple[int, str]]) -> None:
    """Record the exact removed positions and update the viewer once."""
    indices, paths = zip(*removed, strict=True)
    viewer.undo_stack.append(
        {
            "mode": "delete",
            "deleted_paths": list(paths),
            "indices": list(indices),
            "restored": False,
        }
    )
    self._release_tile_textures(viewer, list(paths))
    for path in paths:
        viewer.tile_cache.pop(path, None)
    self._refresh_viewer_after_delete(viewer, images, indices[0])
    self._notify_plugins_deleted(list(paths), viewer)


def _notify_plugins_deleted(self, paths: list[str], viewer) -> None:
    """Run the plugins' ``on_image_deleted`` for list images this tree soft-deleted."""
    manager = getattr(self._main_window, "plugin_manager", None)
    if manager is not None:
        manager.dispatch_image_deleted(paths, viewer)


def _refresh_viewer_after_delete(viewer, images: list[str], idx: int) -> None:
    if viewer.tile_grid_mode:
        viewer.tile_rects.clear()
        viewer.update()
        return
    if not viewer.deep_zoom:
        return
    if images:
        viewer.current_index = min(idx, len(images) - 1)
        viewer.load_deep_zoom_image(images[viewer.current_index])
    else:
        viewer.deep_zoom = None
        viewer.current_index = 0
        viewer.tile_grid_mode = True
        viewer.update()
