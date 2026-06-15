from collections import OrderedDict

from OpenGL.GL import glDeleteTextures

from Imervue.gpu_image_view.texture_upload import prepare_rgba, upload_rgba_texture


_MAX_TILE_CACHE = 256


class TileManager:
    def __init__(self, deep_zoom):
        self.deep_zoom = deep_zoom
        self.cache = OrderedDict()
        self._current_level = -1

    def clear(self):
        """釋放所有 GPU texture"""
        if self.cache:
            glDeleteTextures(list(self.cache.values()))
            self.cache.clear()

    def get_tile(self, level, tx, ty, tile_size):
        self._current_level = level

        key = (level, tx, ty)

        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]

        # LRU 淘汰：優先淘汰不同 level 的 tile，再淘汰同 level 最舊的
        while len(self.cache) >= _MAX_TILE_CACHE:
            victim = next((k for k in self.cache if k[0] != level), None)
            if victim is not None:
                glDeleteTextures([self.cache.pop(victim)])
            else:
                _, tex = self.cache.popitem(last=False)
                glDeleteTextures([tex])

        image = self.deep_zoom.levels[level]
        h, w = image.shape[:2]

        x0 = tx * tile_size
        y0 = ty * tile_size
        x1 = min(x0 + tile_size, w)
        y1 = min(y0 + tile_size, h)

        if x0 >= w or y0 >= h:
            return None

        tile = prepare_rgba(image[y0:y1, x0:x1])
        tex = upload_rgba_texture(tile)

        self.cache[key] = tex
        return tex
