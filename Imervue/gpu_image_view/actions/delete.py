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

    if not main_gui.selected_tiles:
        return

    images = main_gui.model.images

    # 單趟掃描 + 一次重建清單。逐一 images.index()/pop() 是 O(n·m)，
    # 大量選取時會把 UI 卡住好幾秒。
    doomed = set(main_gui.selected_tiles)
    removed = [(idx, path) for idx, path in enumerate(images) if path in doomed]
    deleted_indices = [idx for idx, _path in removed]
    deleted_paths = [path for _idx, path in removed]
    images[:] = [path for path in images if path not in doomed]

    main_gui.undo_stack.append({
        "mode": "delete",
        "deleted_paths": deleted_paths,
        "indices": deleted_indices,
        "restored": False,
    })

    # Plugin hook: image deleted
    if hasattr(main_gui.main_window, "plugin_manager"):
        main_gui.main_window.plugin_manager.dispatch_image_deleted(deleted_paths, main_gui)

    # GPU — 一次釋放整批紋理，避免逐張呼叫
    textures = [
        tex for tex in (main_gui.tile_textures.pop(p, None) for p in deleted_paths)
        if tex is not None
    ]
    if textures:
        glDeleteTextures(textures)

    # CPU cache
    for path in deleted_paths:
        main_gui.tile_cache.pop(path, None)

    main_gui.selected_tiles.clear()
    main_gui.tile_selection_mode = False
    main_gui.tile_rects.clear()

    main_gui.update()

def _refresh_tree_pending(main_gui) -> None:
    """Re-sync the file tree's hidden rows to the current pending set."""
    tree = getattr(getattr(main_gui, "main_window", None), "tree", None)
    refresh = getattr(tree, "refresh_pending_hidden", None)
    if callable(refresh):
        refresh()


def undo_delete(main_gui: GPUImageView):
    from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker
    from Imervue.gpu_image_view.tile_loader import track_tile_worker

    if not main_gui.undo_stack:
        return

    mode = main_gui.undo_stack[-1].get("mode")
    if mode == "delete_external":
        # A folder / file-tree soft-delete: undo just un-hides it (it was never
        # moved). Popping it also stops the shutdown commit from trashing it.
        main_gui.undo_stack.pop()
        _refresh_tree_pending(main_gui)
        main_gui.update()
        return
    if mode != "delete":
        return

    action = main_gui.undo_stack.pop()
    paths = action["deleted_paths"]
    indices = action["indices"]

    # ===== 依 index 排序插回 =====
    for path, idx in sorted(zip(paths, indices, strict=False), key=lambda x: x[1]):
        main_gui.model.images.insert(idx, path)

        # ===== 重新載入 thumbnail（tile grid 用）=====
        worker = LoadThumbnailWorker(path, main_gui.thumbnail_size, main_gui._load_generation)
        worker.signals.finished.connect(main_gui.add_thumbnail)
        # Track so a folder switch mid-restore cancels these and they self-evict
        # on finish instead of leaking until the next tile-grid load.
        track_tile_worker(main_gui, worker)
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
    from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
    for action in main_gui.undo_stack:
        # 跳過已還原的動作
        if action.get("restored", False):
            continue

        external = action.get("mode") == "delete_external"
        for path in action.get("deleted_paths", []):
            try:
                if not Path(path).exists():
                    continue
                # Folders / file-tree deletions were only hidden, never moved —
                # send them to the OS trash now (recoverable). Viewer-list image
                # soft-deletes are unlinked as before.
                if external:
                    _send_to_trash(path)
                else:
                    Path(path).unlink()
                logger.info(f"Permanent delete: {path}")
            except Exception as e:
                logger.exception(f"Failed to permanently delete {path}: {e}")

    # 程式即將關閉，清除所有 undo 記錄
    main_gui.undo_stack.clear()
