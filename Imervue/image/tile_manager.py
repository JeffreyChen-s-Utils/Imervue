from collections import OrderedDict

import numpy as np
from OpenGL.GL import glDeleteTextures, glGenTextures, glTexImage2D
from OpenGL.raw.GL.ARB.internalformat_query2 import GL_TEXTURE_2D
from OpenGL.raw.GL.VERSION.GL_1_0 import GL_RGBA, GL_UNSIGNED_BYTE, glTexParameteri, GL_TEXTURE_MIN_FILTER, \
    GL_TEXTURE_MAG_FILTER, glPixelStorei, GL_UNPACK_ALIGNMENT, GL_LINEAR, GL_TEXTURE_WRAP_T, \
    GL_TEXTURE_WRAP_S
from OpenGL.raw.GL.VERSION.GL_1_1 import glBindTexture
from OpenGL.raw.GL.VERSION.GL_1_2 import GL_CLAMP_TO_EDGE


class TileManager:
    def __init__(self, deep_zoom):
        self.deep_zoom = deep_zoom
        self.cache = OrderedDict()

    def get_tile(self, level, tx, ty, tile_size):
        key = (level, tx, ty)

        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]

        if len(self.cache) > 128:
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
