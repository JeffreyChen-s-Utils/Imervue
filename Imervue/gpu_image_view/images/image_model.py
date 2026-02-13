class ImageModel:
    def __init__(self):
        self.images: list[str] = []
        self.deleted_history = []

    def set_images(self, paths: list[str]):
        self.images = paths.copy()

    def delete_images(self, paths: list[str]):
        deleted = []
        for p in paths:
            if p in self.images:
                index = self.images.index(p)
                self.images.remove(p)
                deleted.append((p, index))
        return deleted

    def restore_images(self, deleted_items):
        for path, index in sorted(deleted_items, key=lambda x: x[1]):
            self.images.insert(index, path)
