class ImageModel:
    def __init__(self):
        self.images: list[str] = []
        self.deleted_history = []

    def set_images(self, paths: list[str]):
        self.images = paths.copy()

    def delete_images(self, paths: list[str]):
        paths_set = set(paths)
        # 一次掃描收集所有要刪除的 (path, index)，避免 O(n²) 的 list.index()
        items_to_delete = [
            (p, i) for i, p in enumerate(self.images) if p in paths_set
        ]
        # 從後往前刪除以保持 index 正確
        deleted = []
        for p, idx in sorted(items_to_delete, key=lambda x: x[1], reverse=True):
            self.images.pop(idx)
            deleted.append((p, idx))
        return deleted

    def restore_images(self, deleted_items):
        for path, index in sorted(deleted_items, key=lambda x: x[1]):
            self.images.insert(index, path)
