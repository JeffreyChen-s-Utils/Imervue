from collections import OrderedDict

import numpy as np
from OpenGL.GL import (
    glDeleteTextures, glGenTextures, glTexImage2D, glBindTexture,
    glTexParameteri, glPixelStorei,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_UNPACK_ALIGNMENT, GL_LINEAR,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
)


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
            # 嘗試找不同 level 的最舊 tile
            evicted = False
            for k in list(self.cache):
                if k[0] != level:
                    glDeleteTextures([self.cache.pop(k)])
                    evicted = True
                    break
            if not evicted:
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

        tile = image[y0:y1, x0:x1]

        tile = tile.astype(np.uint8)
        if tile.ndim == 2:
            tile = np.stack([tile, tile, tile], axis=2)
        if tile.shape[2] == 3:
            alpha = np.full((tile.shape[0], tile.shape[1], 1), 255, dtype=np.uint8)
            tile = np.concatenate([tile, alpha], axis=2)

        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            tile.shape[1],
            tile.shape[0],
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            tile
        )
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        self.cache[key] = tex
        return tex
