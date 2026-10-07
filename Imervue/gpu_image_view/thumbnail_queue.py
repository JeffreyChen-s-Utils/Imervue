"""Pure bounded thumbnail planning; unvisited rows create no decode jobs."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Collection, Mapping

from Imervue.gpu_image_view.tile_viewport import TileViewport


class ThumbnailQueue:
    """Prioritize the current viewport and explicit requests within worker slots."""

    def __init__(self, images: list[str], generation: int, *, limit: int = 8):
        self.generation = generation
        self.limit = max(1, int(limit))
        self.active: dict[str, object] = {}
        self.urgent: OrderedDict[str, str] = OrderedDict()
        self.requested: set[str] = set()
        self._bind(images)

    def _bind(self, images: list[str]) -> None:
        self.images = images
        self._length = len(images)
        self.positions: dict[str, int] = {}
        for index, path in enumerate(images):
            self.positions.setdefault(path, index)
        self._background_cursor = 0
        self._background: dict[str, None] = {}

    def sync(self, images: list[str]) -> None:
        """Rebind after a source-list replacement or insertion/deletion."""
        if images is not self.images or len(images) != self._length:
            self._bind(images)

    def contains(self, images: list[str], path: str) -> bool:
        """Check membership in O(1), rebuilding after legacy list mutations."""
        self.sync(images)
        position = self.positions.get(path)
        if position is not None and images[position] == path:
            return True
        # Direct rename/reorder callers retain the list object and length.
        # A mismatch triggers one rebuild, not a scan for each completed tile.
        if position is not None or path in images:
            self._bind(images)
        return path in self.positions

    def request(self, path: str, *, filmstrip: bool = False, replay: bool = False) -> None:
        """Queue an explicit decode/retry ahead of ordinary wall candidates."""
        if path not in self.active or replay:
            self.urgent[path] = "filmstrip" if filmstrip else "wall"

    def plan(self, viewport: TileViewport, cached: Mapping[str, object],
             failed: Mapping[str, object], offline: Collection[str], *,
             wall: bool = True, hover: str | None = None,
             full_resolution: bool = False) -> list[str]:
        """Replace unstarted work after a pan, keeping only bounded active jobs."""
        indices = list(viewport.indices()) if wall else []
        center = (indices[0] + indices[-1]) / 2 if indices else 0
        indices.sort(key=lambda i: (self.images[i] != hover, abs(i - center)))
        paths = list(dict.fromkeys(self.images[i] for i in indices))
        candidates = list(self.urgent)
        candidates.extend(path for path in paths if path not in self.urgent
                          and path not in cached and path not in failed and path not in offline)
        if wall and full_resolution:
            # Full-size tiles may overlap distant cells; bounded backfill
            # preserves discovering those extents without N queued runnables.
            candidates.extend(self._backfill(cached, failed, offline))
        self.requested = set(paths) | set(self.active) | set(self.urgent) | set(self._background)
        return list(dict.fromkeys(path for path in candidates if path not in self.active))

    def _backfill(self, cached, failed, offline) -> list[str]:
        for path in tuple(self._background):
            if path in cached or path in failed or path in offline:
                self._background.pop(path)
        while self._background_cursor < len(self.images) and len(self._background) < self.limit:
            path = self.images[self._background_cursor]
            self._background_cursor += 1
            if (path not in self.active and path not in cached
                    and path not in failed and path not in offline):
                self._background[path] = None
        return list(self._background)

    def started(self, path: str, worker: object) -> str:
        """Register one admitted worker and return its result callback mode."""
        self.active[path] = worker
        self._background.pop(path, None)
        return self.urgent.pop(path, "wall")

    def completed_count(self, cached: Mapping[str, object], failed: Mapping[str, object],
                        offline: Collection[str]) -> int:
        """Count terminal requested paths without traversing the library/cache."""
        return sum(path in cached or path in failed or path in offline for path in self.requested)
