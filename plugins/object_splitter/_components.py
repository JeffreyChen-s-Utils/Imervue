"""4-connected component labelling shared by the plugin and ``_runner.py``.

``_runner.py`` runs in an external Python for the frozen build and loads this
file as a plain sibling, so it must not import Qt, Imervue or the plugin
package — only NumPy, and SciPy when it is there. Both are imported inside the
functions: the runner adds the environment's site-packages to ``sys.path``
only after it has loaded this module.
"""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def _connected_components(binary: np.ndarray) -> tuple[np.ndarray, int]:
    """Label the 4-connected regions of *binary*; returns ``(labels, count)``.

    Labels are ``int32``, numbered from 1 in raster order of each region's first
    pixel, with 0 for background. ``scipy.ndimage.label`` does this in C (rembg,
    which this plugin needs, depends on SciPy); without SciPy a pure-Python BFS
    gives the identical result, roughly 170x slower.
    """
    try:
        from scipy import ndimage
    except ImportError:
        return _bfs_components(binary)
    import numpy as np
    labels, count = ndimage.label(binary)
    return labels.astype(np.int32, copy=False), int(count)


def _bfs_components(binary: np.ndarray) -> tuple[np.ndarray, int]:
    """Pure-Python fallback for :func:`_connected_components`."""
    import numpy as np
    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current_label = 0

    for y in range(h):
        for x in range(w):
            if binary[y, x] and labels[y, x] == 0:
                current_label += 1
                queue = deque()
                queue.append((y, x))
                labels[y, x] = current_label
                while queue:
                    cy, cx = queue.popleft()
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = current_label
                            queue.append((ny, nx))

    return labels, current_label
