from collections import OrderedDict

from OpenGL.GL import glDeleteTextures

from Imervue.gpu_image_view.texture_upload import prepare_rgba, upload_rgba_texture


_MAX_TILE_CACHE = 256
# Absolute ceiling on cached tiles. The soft cap (``max_cache``) can be smaller
# than one frame's visible tiles at an LOD boundary on a 4K / multi-monitor
# canvas; evicting a tile the current frame still needs just re-uploads it next
# frame (thrash). We let the cache hold the whole working set up to this hard
# cap instead, which bounds pathological growth without the churn.
_HARD_TILE_CACHE = 512


def tiles_to_evict(cache_keys, requested_level: int, max_cache: int,
                   hard_cap: int) -> list:
    """Keys to free before caching a new tile at ``requested_level``.

    ``cache_keys`` is the cache's LRU order (oldest first). Evict other-level
    tiles first — they aren't part of the current frame's working set. Never
    evict a *same-level* tile merely to stay under ``max_cache``: those are
    almost certainly this frame's visible tiles, and dropping one forces a
    re-upload next frame. Only once the cache exceeds ``hard_cap`` do we drop the
    oldest tiles to bound growth.
    """
    keys = list(cache_keys)
    remaining = len(keys)
    victims: list = []
    for key in keys:
        if remaining < max_cache:
            break
        if key[0] != requested_level:
            victims.append(key)
            remaining -= 1
    if remaining < hard_cap:
        return victims
    victim_set = set(victims)
    for key in keys:
        if remaining < hard_cap:
            break
        if key not in victim_set:
            victims.append(key)
            remaining -= 1
    return victims


class TileManager:
    def __init__(self, deep_zoom):
        self.deep_zoom = deep_zoom
        self.cache = OrderedDict()
        self._current_level = -1
        self.max_cache = _MAX_TILE_CACHE

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

        # LRU eviction: drop other-level tiles first, and never evict the
        # current frame's same-level working set below the hard cap (would
        # thrash). Runs inside paintGL, so the GL context is already current.
        for victim in tiles_to_evict(
                self.cache.keys(), level, self.max_cache,
                max(self.max_cache, _HARD_TILE_CACHE)):
            glDeleteTextures([self.cache.pop(victim)])

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
