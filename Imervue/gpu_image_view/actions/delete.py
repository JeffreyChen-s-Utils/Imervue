from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

# Heavy imports (OpenGL, rawpy via LoadThumbnailWorker) are deferred so this
# module is importable in environments that ship neither — including the
# unit tests for ``commit_pending_deletions`` which only touches the undo
# stack and ``Path.unlink``.

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.delete")


class _UndoStackOwner(Protocol):
    """Minimal duck-typed surface that ``commit_pending_deletions`` requires.

    The real caller is ``GPUImageView`` but the function only reads / clears
    the undo stack, so any object exposing that attribute satisfies it.
    Declared as a ``Protocol`` so unit tests can hand in a lightweight stub
    without a full OpenGL / rawpy import chain.
    """

    undo_stack: list[dict]


def delete_current_image(main_gui: GPUImageView):
    from OpenGL.GL import glDeleteTextures

    images = main_gui.model.images

    if not images or main_gui.current_index >= len(images):
        return

    deleted_index = main_gui.current_index
    path_to_delete = images[deleted_index]

    # ===== 從 model 刪除 =====
    images.pop(deleted_index)

    # ===== 存入 undo stack（統一格式）=====
    main_gui.undo_stack.append({
        "mode": "delete",
        "deleted_paths": [path_to_delete],
        "indices": [deleted_index],
        "restored": False,
    })

    # Plugin hook: image deleted
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_deleted([path_to_delete], main_gui)

    # ===== 清 GPU texture =====
    tex = main_gui.tile_textures.pop(path_to_delete, None)
    if tex is not None:
        glDeleteTextures([tex])

    # ===== 更新 current_index =====
    if images:
        main_gui.current_index = min(deleted_index, len(images) - 1)
        main_gui.load_deep_zoom_image(images[main_gui.current_index])
    else:
        main_gui.deep_zoom = None
        main_gui.current_index = 0
        main_gui.tile_grid_mode = True

    main_gui.update()


def delete_selected_tiles(main_gui):
    from OpenGL.GL import glDeleteTextures

    paths = list(main_gui.selected_tiles)
    if not paths:
        return

    images = main_gui.model.images

    deleted_paths = []
    deleted_indices = []

    # 先收集所有要刪除的 index，再從後往前刪除以保持 index 正確
    items_to_delete = []
    for path in paths:
        if path in images:
            idx = images.index(path)
            items_to_delete.append((path, idx))

    # 按 index 從大到小排序後刪除
    for path, idx in sorted(items_to_delete, key=lambda x: x[1], reverse=True):
        images.pop(idx)
        deleted_paths.append(path)
        deleted_indices.append(idx)

    main_gui.undo_stack.append({
        "mode": "delete",
        "deleted_paths": deleted_paths,
        "indices": deleted_indices,
        "restored": False,
    })

    # Plugin hook: image deleted
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_deleted(deleted_paths, main_gui)

    # GPU
    for path in deleted_paths:
        tex = main_gui.tile_textures.pop(path, None)
        if tex is not None:
            glDeleteTextures([tex])  # noqa: F821 — imported above

    # CPU cache
    for path in deleted_paths:
        main_gui.tile_cache.pop(path, None)

    main_gui.selected_tiles.clear()
    main_gui.tile_selection_mode = False
    main_gui.tile_rects.clear()

    main_gui.update()

def undo_delete(main_gui: GPUImageView):
    from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker

    if not main_gui.undo_stack:
        return

    action = main_gui.undo_stack.pop()

    if action.get("mode") != "delete":
        return

    paths = action["deleted_paths"]
    indices = action["indices"]

    # ===== 依 index 排序插回 =====
    for path, idx in sorted(zip(paths, indices, strict=False), key=lambda x: x[1]):
        main_gui.model.images.insert(idx, path)

        # ===== 重新載入 thumbnail（tile grid 用）=====
        worker = LoadThumbnailWorker(path, main_gui.thumbnail_size, main_gui._load_generation)
        worker.signals.finished.connect(main_gui.add_thumbnail)
        main_gui.thread_pool.start(worker)

    # ===== 如果在 deep zoom 模式，重新載入當前圖 =====
    if main_gui.deep_zoom and main_gui.model.images:
        main_gui.current_index = min(main_gui.current_index, len(main_gui.model.images) - 1)
        current_path = main_gui.model.images[main_gui.current_index]
        main_gui.load_deep_zoom_image(current_path)

    # ===== 標記這個 action 已被還原 =====
    action["restored"] = True

    main_gui.update()


def commit_pending_deletions(main_gui: _UndoStackOwner):
    for action in main_gui.undo_stack:
        # 跳過已還原的動作
        if action.get("restored", False):
            continue

        for path in action.get("deleted_paths", []):
            try:
                if Path(path).exists():
                    Path(path).unlink()
                    logger.info(f"Permanent delete: {path}")
            except Exception as e:
                logger.error(f"Failed to permanently delete {path}: {e}")

    # 程式即將關閉，清除所有 undo 記錄
    main_gui.undo_stack.clear()
