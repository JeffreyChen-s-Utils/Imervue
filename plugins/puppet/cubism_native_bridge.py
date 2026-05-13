"""ctypes binding for ``Live2DCubismCore.dll`` — Live2D's official
Cubism SDK for Native runtime.

We use this *only* on the user's local machine: the DLL is gated
behind Live2D's Free Material License, so the user has to download
the SDK themselves (cannot redistribute). The path comes from the
``CUBISM_CORE_DLL`` environment variable or a small list of common
fallbacks under ``%USERPROFILE%\\Downloads``.

This module exposes the slim subset of the C API we need to turn a
``.moc3`` into a :class:`PuppetDocument`:

* :func:`load_library` — locate + load the DLL, return a handle with
  argtypes wired up.
* :class:`CubismModel` — RAII wrapper that owns the aligned moc /
  model buffers, exposes drawable / parameter inspection, lets the
  caller drive parameter values and read back deformed vertices.

The Cubism SDK and the model files are **never** committed into this
repo — `.gitignore` carries an explicit exclusion. Distribution of
``Live2DCubismCore.dll`` would violate Live2D's EULA.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("Imervue.plugin.puppet.cubism_native_bridge")

# Alignment constants from Live2DCubismCore.h.
CSM_ALIGNOF_MOC: int = 64
CSM_ALIGNOF_MODEL: int = 16

# Env var the user can set so the bridge doesn't have to guess.
LIBRARY_ENV_VAR: str = "CUBISM_CORE_DLL"


class CubismBridgeError(RuntimeError):
    """Raised when the DLL can't be loaded or a Cubism call fails."""


# ---------------------------------------------------------------------------
# Library discovery + binding
# ---------------------------------------------------------------------------


def _candidate_dll_paths() -> list[Path]:
    """Return the ordered list of paths we'll probe for the Core DLL.
    Env var wins; otherwise we sweep common ``Downloads`` install
    locations on Windows."""
    candidates: list[Path] = []
    env = os.environ.get(LIBRARY_ENV_VAR)
    if env:
        candidates.append(Path(env))
    if sys.platform == "win32":
        home = Path(os.environ.get("USERPROFILE", str(Path.home())))
        downloads = home / "Downloads"
        # Sweep every CubismSdkForNative* folder we find — version
        # bumps shouldn't require code changes.
        if downloads.is_dir():
            for sdk_root in sorted(downloads.glob("CubismSdkForNative-*")):
                core_dll = sdk_root / "Core" / "dll" / "windows" / "x86_64" / "Live2DCubismCore.dll"
                candidates.append(core_dll)
    elif sys.platform == "darwin":
        # macOS uses .dylib; user puts SDK in ~/Downloads or /Applications.
        for root in (Path.home() / "Downloads", Path("/Applications")):
            for sdk_root in sorted(root.glob("CubismSdkForNative-*")):
                candidates.append(sdk_root / "Core" / "dll" / "macos" / "libLive2DCubismCore.dylib")
    else:
        # Linux — .so file. Same Downloads convention.
        for sdk_root in sorted((Path.home() / "Downloads").glob("CubismSdkForNative-*")):
            candidates.append(sdk_root / "Core" / "dll" / "linux" / "x86_64" / "libLive2DCubismCore.so")
    return candidates


def find_dll() -> Path | None:
    """Return the first existing candidate path, or ``None`` when the
    user hasn't placed the SDK anywhere we know about."""
    for candidate in _candidate_dll_paths():
        if candidate.is_file():
            return candidate
    return None


def load_library(path: str | Path | None = None) -> ctypes.CDLL:
    """Load the Cubism Core DLL and wire up the argument / return
    types for every function we wrap. Raises
    :class:`CubismBridgeError` when the DLL isn't where we expected."""
    if path is None:
        found = find_dll()
        if found is None:
            raise CubismBridgeError(
                f"Live2DCubismCore.dll not found. Set the {LIBRARY_ENV_VAR} "
                f"environment variable to the absolute path of the DLL.",
            )
        path = found
    path = Path(path)
    if not path.is_file():
        raise CubismBridgeError(f"DLL path {path} does not exist")
    try:
        lib = ctypes.CDLL(str(path))
    except OSError as exc:
        raise CubismBridgeError(f"failed to load {path}: {exc}") from exc
    _bind_signatures(lib)
    return lib


def _bind_signatures(lib: ctypes.CDLL) -> None:
    """Tell ctypes the calling-convention shapes for every exported
    function we'll touch. Without this, ctypes assumes ``int``
    arguments / return on Windows which mangles pointers on 64-bit."""
    lib.csmGetVersion.restype = ctypes.c_uint
    lib.csmGetVersion.argtypes = []

    lib.csmGetMocVersion.restype = ctypes.c_uint
    lib.csmGetMocVersion.argtypes = [ctypes.c_void_p, ctypes.c_uint]

    lib.csmHasMocConsistency.restype = ctypes.c_int
    lib.csmHasMocConsistency.argtypes = [ctypes.c_void_p, ctypes.c_uint]

    lib.csmReviveMocInPlace.restype = ctypes.c_void_p
    lib.csmReviveMocInPlace.argtypes = [ctypes.c_void_p, ctypes.c_uint]

    lib.csmGetSizeofModel.restype = ctypes.c_uint
    lib.csmGetSizeofModel.argtypes = [ctypes.c_void_p]

    lib.csmInitializeModelInPlace.restype = ctypes.c_void_p
    lib.csmInitializeModelInPlace.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
    ]

    lib.csmUpdateModel.restype = None
    lib.csmUpdateModel.argtypes = [ctypes.c_void_p]

    # Canvas info
    lib.csmReadCanvasInfo.restype = None
    lib.csmReadCanvasInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float * 2),
        ctypes.POINTER(ctypes.c_float * 2),
        ctypes.POINTER(ctypes.c_float),
    ]

    # Parameters
    lib.csmGetParameterCount.restype = ctypes.c_int
    lib.csmGetParameterCount.argtypes = [ctypes.c_void_p]
    lib.csmGetParameterIds.restype = ctypes.POINTER(ctypes.c_char_p)
    lib.csmGetParameterIds.argtypes = [ctypes.c_void_p]
    lib.csmGetParameterMinimumValues.restype = ctypes.POINTER(ctypes.c_float)
    lib.csmGetParameterMinimumValues.argtypes = [ctypes.c_void_p]
    lib.csmGetParameterMaximumValues.restype = ctypes.POINTER(ctypes.c_float)
    lib.csmGetParameterMaximumValues.argtypes = [ctypes.c_void_p]
    lib.csmGetParameterDefaultValues.restype = ctypes.POINTER(ctypes.c_float)
    lib.csmGetParameterDefaultValues.argtypes = [ctypes.c_void_p]
    lib.csmGetParameterValues.restype = ctypes.POINTER(ctypes.c_float)
    lib.csmGetParameterValues.argtypes = [ctypes.c_void_p]

    # Drawables
    lib.csmGetDrawableCount.restype = ctypes.c_int
    lib.csmGetDrawableCount.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableIds.restype = ctypes.POINTER(ctypes.c_char_p)
    lib.csmGetDrawableIds.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableTextureIndices.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableTextureIndices.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableDrawOrders.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableDrawOrders.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableVertexCounts.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableVertexCounts.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableVertexPositions.restype = ctypes.POINTER(
        ctypes.POINTER(ctypes.c_float),
    )
    lib.csmGetDrawableVertexPositions.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableVertexUvs.restype = ctypes.POINTER(
        ctypes.POINTER(ctypes.c_float),
    )
    lib.csmGetDrawableVertexUvs.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableIndexCounts.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableIndexCounts.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableIndices.restype = ctypes.POINTER(
        ctypes.POINTER(ctypes.c_ushort),
    )
    lib.csmGetDrawableIndices.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableOpacities.restype = ctypes.POINTER(ctypes.c_float)
    lib.csmGetDrawableOpacities.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableConstantFlags.restype = ctypes.POINTER(ctypes.c_ubyte)
    lib.csmGetDrawableConstantFlags.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableBlendModes.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableBlendModes.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableMaskCounts.restype = ctypes.POINTER(ctypes.c_int)
    lib.csmGetDrawableMaskCounts.argtypes = [ctypes.c_void_p]
    lib.csmGetDrawableMasks.restype = ctypes.POINTER(ctypes.POINTER(ctypes.c_int))
    lib.csmGetDrawableMasks.argtypes = [ctypes.c_void_p]


# ---------------------------------------------------------------------------
# Aligned-buffer helper
# ---------------------------------------------------------------------------


def _aligned_copy(data: bytes, alignment: int) -> tuple[ctypes.Array, int]:
    """Allocate a buffer big enough to fit ``data`` aligned to
    ``alignment`` bytes. Returns ``(backing_array, aligned_address)``
    — caller must keep ``backing_array`` alive so the GC doesn't
    free the underlying memory."""
    size = len(data)
    raw = (ctypes.c_char * (size + alignment))()
    base = ctypes.addressof(raw)
    offset = (-base) % alignment
    ctypes.memmove(base + offset, data, size)
    return raw, base + offset


def _aligned_zero(size: int, alignment: int) -> tuple[ctypes.Array, int]:
    raw = (ctypes.c_char * (size + alignment))()
    base = ctypes.addressof(raw)
    offset = (-base) % alignment
    return raw, base + offset


# ---------------------------------------------------------------------------
# Model wrapper
# ---------------------------------------------------------------------------


@dataclass
class ParameterInfo:
    """Snapshot of one Cubism parameter's metadata."""

    id: str
    minimum: float
    maximum: float
    default: float


@dataclass
class DrawableInfo:
    """Per-drawable mesh + texture binding at the current model
    state. ``positions`` and ``uvs`` are flat float arrays of length
    ``vertex_count * 2``; ``indices`` is length ``index_count``."""

    id: str
    texture_index: int
    draw_order: int
    opacity: float
    blend_mode: int
    constant_flags: int
    vertex_count: int
    index_count: int
    positions: list[float]
    uvs: list[float]
    indices: list[int]
    mask_drawable_indices: list[int]


class CubismModel:
    """High-level wrapper around a loaded .moc3 + model pair.

    Keeps the aligned moc and model buffers alive for the wrapper's
    lifetime; everything else (drawables, parameters) is read on
    demand from the Cubism Core API."""

    def __init__(self, lib: ctypes.CDLL, moc_bytes: bytes):
        self._lib = lib
        self._moc_backing, moc_addr = _aligned_copy(moc_bytes, CSM_ALIGNOF_MOC)
        moc_ptr = lib.csmReviveMocInPlace(
            ctypes.c_void_p(moc_addr), ctypes.c_uint(len(moc_bytes)),
        )
        if not moc_ptr:
            raise CubismBridgeError(
                "csmReviveMocInPlace returned NULL — moc3 likely "
                "corrupt or from an unsupported Cubism version.",
            )
        self._moc_ptr = ctypes.c_void_p(moc_ptr)
        model_size = lib.csmGetSizeofModel(self._moc_ptr)
        self._model_backing, model_addr = _aligned_zero(model_size, CSM_ALIGNOF_MODEL)
        model_ptr = lib.csmInitializeModelInPlace(
            self._moc_ptr, ctypes.c_void_p(model_addr), ctypes.c_uint(model_size),
        )
        if not model_ptr:
            raise CubismBridgeError("csmInitializeModelInPlace returned NULL")
        self._model_ptr = ctypes.c_void_p(model_ptr)
        lib.csmUpdateModel(self._model_ptr)

    # ---- parameter inspection ---------------------------------------

    def parameter_count(self) -> int:
        return int(self._lib.csmGetParameterCount(self._model_ptr))

    def parameters(self) -> list[ParameterInfo]:
        count = self.parameter_count()
        ids = self._lib.csmGetParameterIds(self._model_ptr)
        mins = self._lib.csmGetParameterMinimumValues(self._model_ptr)
        maxs = self._lib.csmGetParameterMaximumValues(self._model_ptr)
        defs = self._lib.csmGetParameterDefaultValues(self._model_ptr)
        out: list[ParameterInfo] = []
        for i in range(count):
            out.append(ParameterInfo(
                id=ids[i].decode("utf-8", errors="replace"),
                minimum=float(mins[i]),
                maximum=float(maxs[i]),
                default=float(defs[i]),
            ))
        return out

    def parameter_values(self) -> list[float]:
        count = self.parameter_count()
        values = self._lib.csmGetParameterValues(self._model_ptr)
        return [float(values[i]) for i in range(count)]

    def set_parameter_values(self, values: list[float]) -> None:
        count = self.parameter_count()
        if len(values) != count:
            raise CubismBridgeError(
                f"set_parameter_values: got {len(values)} values, "
                f"model has {count} parameters.",
            )
        slot = self._lib.csmGetParameterValues(self._model_ptr)
        for i in range(count):
            slot[i] = ctypes.c_float(float(values[i]))

    def reset_to_defaults(self) -> None:
        self.set_parameter_values([p.default for p in self.parameters()])

    def update(self) -> None:
        self._lib.csmUpdateModel(self._model_ptr)

    # ---- drawable inspection ----------------------------------------

    def drawable_count(self) -> int:
        return int(self._lib.csmGetDrawableCount(self._model_ptr))

    def drawables(self) -> list[DrawableInfo]:
        count = self.drawable_count()
        ids = self._lib.csmGetDrawableIds(self._model_ptr)
        textures = self._lib.csmGetDrawableTextureIndices(self._model_ptr)
        draw_orders = self._lib.csmGetDrawableDrawOrders(self._model_ptr)
        opacities = self._lib.csmGetDrawableOpacities(self._model_ptr)
        blend_modes = self._lib.csmGetDrawableBlendModes(self._model_ptr)
        const_flags = self._lib.csmGetDrawableConstantFlags(self._model_ptr)
        vertex_counts = self._lib.csmGetDrawableVertexCounts(self._model_ptr)
        positions = self._lib.csmGetDrawableVertexPositions(self._model_ptr)
        uvs = self._lib.csmGetDrawableVertexUvs(self._model_ptr)
        index_counts = self._lib.csmGetDrawableIndexCounts(self._model_ptr)
        indices = self._lib.csmGetDrawableIndices(self._model_ptr)
        mask_counts = self._lib.csmGetDrawableMaskCounts(self._model_ptr)
        masks = self._lib.csmGetDrawableMasks(self._model_ptr)
        out: list[DrawableInfo] = []
        for i in range(count):
            vc = int(vertex_counts[i])
            ic = int(index_counts[i])
            mc = int(mask_counts[i])
            pos_ptr = positions[i]
            uv_ptr = uvs[i]
            idx_ptr = indices[i]
            mask_ptr = masks[i]
            out.append(DrawableInfo(
                id=ids[i].decode("utf-8", errors="replace"),
                texture_index=int(textures[i]),
                draw_order=int(draw_orders[i]),
                opacity=float(opacities[i]),
                blend_mode=int(blend_modes[i]),
                constant_flags=int(const_flags[i]),
                vertex_count=vc,
                index_count=ic,
                positions=[float(pos_ptr[j]) for j in range(vc * 2)],
                uvs=[float(uv_ptr[j]) for j in range(vc * 2)],
                indices=[int(idx_ptr[j]) for j in range(ic)],
                mask_drawable_indices=[int(mask_ptr[j]) for j in range(mc)],
            ))
        return out

    def vertex_positions(self) -> list[list[float]]:
        """Cheaper than :meth:`drawables` when you only need
        deformed vertex positions — used in sample-and-reconstruct
        loops where everything else is constant per-iteration."""
        count = self.drawable_count()
        vertex_counts = self._lib.csmGetDrawableVertexCounts(self._model_ptr)
        positions = self._lib.csmGetDrawableVertexPositions(self._model_ptr)
        out: list[list[float]] = []
        for i in range(count):
            vc = int(vertex_counts[i])
            ptr = positions[i]
            out.append([float(ptr[j]) for j in range(vc * 2)])
        return out

    # ---- canvas ------------------------------------------------------

    def canvas_info(self) -> dict[str, float]:
        size = (ctypes.c_float * 2)()
        origin = (ctypes.c_float * 2)()
        ppu = ctypes.c_float()
        self._lib.csmReadCanvasInfo(
            self._model_ptr,
            ctypes.byref(size), ctypes.byref(origin), ctypes.byref(ppu),
        )
        return {
            "width": float(size[0]),
            "height": float(size[1]),
            "origin_x": float(origin[0]),
            "origin_y": float(origin[1]),
            "pixels_per_unit": float(ppu.value),
        }


def load_model_file(lib: ctypes.CDLL, moc_path: str | Path) -> CubismModel:
    """Convenience: read the .moc3 file bytes and hand them to
    :class:`CubismModel`."""
    data = Path(moc_path).read_bytes()
    return CubismModel(lib, data)
