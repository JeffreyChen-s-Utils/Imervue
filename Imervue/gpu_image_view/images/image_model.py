class ImageModel:
    def __init__(self):
        self.images: list[str] = []
        self.deleted_history = []

    def set_images(self, paths: list[str]):
        self.images = paths.copy()

    def delete_images(self, paths: list[str]):
        items_to_delete = []
        for p in paths:
            if p in self.images:
                idx = self.images.index(p)
                items_to_delete.append((p, idx))
        # 從後往前刪除以保持 index 正確
        deleted = []
        for p, idx in sorted(items_to_delete, key=lambda x: x[1], reverse=True):
            self.images.pop(idx)
            deleted.append((p, idx))
        return deleted

    def restore_images(self, deleted_items):
        for path, index in sorted(deleted_items, key=lambda x: x[1]):
            self.images.insert(index, path)
