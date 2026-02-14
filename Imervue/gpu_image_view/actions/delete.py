from __future__ import annotations

import os
from typing import TYPE_CHECKING

from OpenGL.GL import glDeleteTextures

from Imervue.gpu_image_view.images.load_thumbnail_worker import LoadThumbnailWorker

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def delete_current_image(main_gui: GPUImageView):
    images = main_gui.model.images

    if not images or main_gui.current_index >= len(images):
        return

    # 1️⃣ 取得要刪除的 path
    path_to_delete = images[main_gui.current_index]
    deleted_index = main_gui.current_index

    # 2️⃣ 從 model 刪除
    images.pop(deleted_index)

    # 3️⃣ 存入 undo stack
    main_gui.undo_stack.append({
        "mode": "deep_zoom",
        "path": path_to_delete,
        "index": deleted_index
    })

    # 4️⃣ 清 GPU texture
    if path_to_delete in main_gui.tile_textures:
        glDeleteTextures([main_gui.tile_textures[path_to_delete]])
        del main_gui.tile_textures[path_to_delete]

    # 5️⃣ 更新 current_index
    if images:
        if deleted_index >= len(images):
            main_gui.current_index = len(images) - 1
        else:
            main_gui.current_index = deleted_index

        main_gui.load_deep_zoom_image(images[main_gui.current_index])

    else:
        # 沒圖了 → 回 Grid
        main_gui.deep_zoom = None
        main_gui.current_index = 0
        main_gui.tile_grid_mode = True

    main_gui.update()


def delete_selected_tiles(main_gui):
    paths = list(main_gui.selected_tiles)
    if not paths:
        return

    # ===== 先存 snapshot =====
    snapshot = main_gui.model.images.copy()

    # ===== 從 model 刪除 =====
    for path in paths:
        if path in main_gui.model.images:
            main_gui.model.images.remove(path)

    main_gui.undo_stack.append({
        "mode": "tile_grid",
        "image_list_snapshot": snapshot
    })

    # ===== 清 GPU texture =====
    for path in paths:
        if path in main_gui.tile_textures:
            glDeleteTextures([main_gui.tile_textures[path]])
            del main_gui.tile_textures[path]

    # ===== 清 CPU cache =====
    for path in paths:
        if path in main_gui.tile_cache:
            del main_gui.tile_cache[path]

    # ===== 清選取 =====
    main_gui.selected_tiles.clear()
    main_gui.tile_selection_mode = False

    # ===== 強制重新排版 =====
    main_gui.tile_rects = []
    main_gui.update()


def undo_delete(main_gui: GPUImageView):
    if not main_gui.undo_stack:
        return

    action = main_gui.undo_stack.pop()

    mode = action.get("mode")

    # ==========================
    # deep zoom undo
    # ==========================
    if mode == "deep_zoom":

        path = action["path"]
        index = action["index"]

        main_gui.model.images.insert(index, path)
        main_gui.current_index = index
        main_gui.load_deep_zoom_image(path)

    # ==========================
    # tile grid undo
    # ==========================
    elif mode == "tile_grid":
        snapshot = action["image_list_snapshot"]
        main_gui.model.images = snapshot

        # Restore deleted tiles cache
        restored_paths = set(snapshot) - set(main_gui.tile_cache.keys())
        for path in restored_paths:
            # 重新載入縮圖
            worker = LoadThumbnailWorker(path, main_gui.thumbnail_size)
            worker.signals.finished.connect(main_gui.add_thumbnail)
            main_gui.thread_pool.start(worker)

        main_gui.selected_tiles.clear()
        main_gui.tile_selection_mode = False


    else:
        print("⚠ Unknown undo mode:", mode)

    main_gui.update()


def clear_thumbnail_cache(main_gui: GPUImageView):
    for tex in main_gui.tile_textures.values():
        glDeleteTextures([tex])
    main_gui.tile_textures.clear()


def commit_pending_deletions(main_gui: GPUImageView):
    """
    真正刪除所有尚未復原的檔案
    在程式關閉時呼叫
    """
    for item in main_gui.deleted_stack:
        path = item["path"]
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Permanent delete: {path}")
        except Exception as e:
            print(f"Failed to permanently delete {path}: {e}")

    # 清空 stack
    main_gui.deleted_stack.clear()
