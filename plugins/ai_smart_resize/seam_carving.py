"""Content-aware resize via seam carving.

Implements the Avidan & Shamir 2007 algorithm with a saliency-derived
energy map sourced from :mod:`Imervue.image.saliency`. Two operations:

* :func:`carve_seams` — remove ``k`` low-energy vertical seams (narrowing
  the image without cropping) or insert ``k`` duplicated seams (widening
  by stretching low-energy regions).
* :func:`smart_resize` — convenience wrapper that resizes to the target
  width by carving / inserting seams until ``out_w`` is reached. Heights
  are handled by transposing, carving, and transposing back.

Pure numpy. Heavy dependency on the plugin side is "long compute time"
rather than an external library — running 200+ seam removals on a 4 MP
image isn't something we want blocking the main viewer thread, so the
plugin executes synchronously inside its dialog and the dialog is
fired off the Extra Tools menu rather than the develop pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.image.saliency import saliency_field

ENERGY_BOOST_MIN = 0.0
ENERGY_BOOST_MAX = 5.0
MAX_SEAM_FRACTION = 0.4


@dataclass(frozen=True)
class SmartResizeOptions:
    """Tuning for :func:`smart_resize`."""

    out_width: int = 0
    out_height: int = 0
    energy_boost: float = 1.0  # multiplies the saliency map; > 1.0 protects subjects more
    protect_alpha: bool = True  # treat fully-transparent pixels as max-energy (never carved)


def smart_resize(arr: np.ndarray, options: SmartResizeOptions) -> np.ndarray:
    """Carve / insert seams until the image matches ``out_width × out_height``.

    Either dimension may be left at 0 to mean "leave unchanged". Raises
    ``ValueError`` if the requested change exceeds
    :data:`MAX_SEAM_FRACTION` of the source dimension — seam carving
    degrades quickly past that and a normal resize is more honest.
    """
    _check_input(arr)
    h, w = arr.shape[:2]
    out_w = options.out_width if options.out_width > 0 else w
    out_h = options.out_height if options.out_height > 0 else h

    _check_resize_budget(w, out_w, "width")
    _check_resize_budget(h, out_h, "height")

    working = arr
    if out_w != w:
        working = carve_seams(
            working, out_w - w,
            energy_boost=options.energy_boost,
            protect_alpha=options.protect_alpha,
        )
    if out_h != h:
        transposed = working.transpose(1, 0, 2)
        transposed = carve_seams(
            transposed, out_h - h,
            energy_boost=options.energy_boost,
            protect_alpha=options.protect_alpha,
        )
        working = transposed.transpose(1, 0, 2)
    return working


def carve_seams(
    arr: np.ndarray,
    delta: int,
    *,
    energy_boost: float = 1.0,
    protect_alpha: bool = True,
) -> np.ndarray:
    """Remove (delta < 0) or insert (delta > 0) ``|delta|`` vertical seams.

    Returns a new HxWx4 array. ``delta == 0`` is a no-op fast path.
    """
    _check_input(arr)
    if delta == 0:
        return arr
    if delta < 0:
        return _remove_seams(arr, -delta, energy_boost, protect_alpha)
    return _insert_seams(arr, delta, energy_boost, protect_alpha)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _remove_seams(arr: np.ndarray, count: int, energy_boost: float,
                  protect_alpha: bool) -> np.ndarray:
    working = arr.copy()
    for _ in range(count):
        if working.shape[1] <= 1:
            break
        seam = _lowest_energy_seam(working, energy_boost, protect_alpha)
        working = _drop_seam(working, seam)
    return working


def _insert_seams(arr: np.ndarray, count: int, energy_boost: float,
                  protect_alpha: bool) -> np.ndarray:
    """Insert ``count`` new columns by duplicating the lowest-energy seams.

    Insertion modifies a *scratch* copy when finding seams (so we don't
    pick the same seam twice) and writes into a separate output canvas
    that grows column by column.
    """
    scratch = arr.copy()
    seams_in_scratch: list[np.ndarray] = []
    for _ in range(count):
        if scratch.shape[1] <= 1:
            break
        seam = _lowest_energy_seam(scratch, energy_boost, protect_alpha)
        seams_in_scratch.append(seam)
        scratch = _drop_seam(scratch, seam)

    # Map each scratch-frame seam back to the original frame and insert.
    seams_in_original = _expand_seams_to_original(seams_in_scratch)
    return _insert_into_original(arr, seams_in_original)


def _lowest_energy_seam(arr: np.ndarray, energy_boost: float,
                        protect_alpha: bool) -> np.ndarray:
    """Return a length-H integer array, the x-coord per row of the seam."""
    energy = _energy_map(arr, energy_boost, protect_alpha)
    h, w = energy.shape
    dp = energy.copy()
    backtrack = np.zeros_like(dp, dtype=np.int32)
    for y in range(1, h):
        for x in range(w):
            lo = max(0, x - 1)
            hi = min(w, x + 2)
            window = dp[y - 1, lo:hi]
            local_idx = int(np.argmin(window))
            backtrack[y, x] = lo + local_idx
            dp[y, x] += window[local_idx]

    seam = np.zeros(h, dtype=np.int32)
    seam[-1] = int(np.argmin(dp[-1]))
    for y in range(h - 2, -1, -1):
        seam[y] = backtrack[y + 1, seam[y + 1]]
    return seam


def _energy_map(arr: np.ndarray, energy_boost: float, protect_alpha: bool) -> np.ndarray:
    field = saliency_field(arr).astype(np.float32)
    if energy_boost != 1.0:
        boost = max(ENERGY_BOOST_MIN, min(ENERGY_BOOST_MAX, float(energy_boost)))
        field = field ** boost if boost > 1.0 else field * boost
    if protect_alpha:
        # Fully-transparent pixels carry no signal — give them max energy
        # so the seam never crosses them.
        field = np.where(arr[..., 3] == 0, field.max() + 1.0, field)
    return field


def _drop_seam(arr: np.ndarray, seam: np.ndarray) -> np.ndarray:
    h, w, c = arr.shape
    out = np.empty((h, w - 1, c), dtype=arr.dtype)
    for y in range(h):
        x = seam[y]
        out[y, :x] = arr[y, :x]
        out[y, x:] = arr[y, x + 1:]
    return out


def _expand_seams_to_original(seams_in_scratch: list[np.ndarray]) -> list[np.ndarray]:
    """Translate each scratch-frame seam back to the original frame.

    When seam ``s_i`` is removed, every later seam ``s_j`` (j > i) was
    located *after* the removal — so its x-coords shift right by 1 for
    each previously-removed seam whose own x at the same row was ≤ s_j[y].
    """
    if not seams_in_scratch:
        return []
    h = seams_in_scratch[0].shape[0]
    expanded: list[np.ndarray] = []
    history: list[np.ndarray] = []
    for seam in seams_in_scratch:
        adjusted = seam.copy()
        for prev in history:
            for y in range(h):
                if prev[y] <= adjusted[y]:
                    adjusted[y] += 1
        expanded.append(adjusted)
        history.append(adjusted)
    return expanded


def _insert_into_original(arr: np.ndarray, seams: list[np.ndarray]) -> np.ndarray:
    """Build an output that has each seam duplicated in place."""
    h, w, c = arr.shape
    insertion_count_per_row = np.zeros((h, w), dtype=np.int32)
    for seam in seams:
        for y in range(h):
            insertion_count_per_row[y, seam[y]] += 1

    new_w = w + sum(seam.shape[0] // h for seam in seams)  # = w + len(seams)
    new_w = w + len(seams)
    out = np.empty((h, new_w, c), dtype=arr.dtype)
    for y in range(h):
        in_x = 0
        out_x = 0
        for in_x in range(w):
            out[y, out_x] = arr[y, in_x]
            out_x += 1
            for _ in range(insertion_count_per_row[y, in_x]):
                if in_x + 1 < w:
                    avg = (arr[y, in_x].astype(np.int32) + arr[y, in_x + 1]) // 2
                else:
                    avg = arr[y, in_x].astype(np.int32)
                out[y, out_x] = avg.astype(arr.dtype)
                out_x += 1
    return out


def _check_input(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"smart_resize expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )


def _check_resize_budget(source: int, target: int, dim_name: str) -> None:
    if target <= 0:
        raise ValueError(f"{dim_name} target must be positive, got {target}")
    delta = abs(target - source)
    if delta > int(source * MAX_SEAM_FRACTION):
        raise ValueError(
            f"{dim_name} change of {delta}px exceeds the seam-carving budget "
            f"({int(MAX_SEAM_FRACTION * 100)}% of source). "
            f"Use a normal resize for larger changes.",
        )
