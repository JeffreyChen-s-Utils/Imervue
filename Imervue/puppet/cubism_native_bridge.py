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

# Dynamic-flag bits from Live2DCubismCore.h. We only need IsVisible
# for the converter — every other bit drives renderer internals.
CSM_IS_VISIBLE: int = 1 << 0
# Constant-flag bits we care about. Bit 2 is the only one that maps
# to a concept our schema keeps (double-sided is informational only).
CSM_BLEND_ADDITIVE: int = 1 << 0
CSM_BLEND_MULTIPLICATIVE: int = 1 << 1

# Env var the user can set so the bridge doesn't have to guess.
LIBRARY_ENV_VAR: str = "CUBISM_CORE_DLL"


class CubismBridgeError(RuntimeError):
    """Raised when the DLL can't be loaded or a Cubism call fails."""


# ---------------------------------------------------------------------------
# Library discovery + binding
# ---------------------------------------------------------------------------


def _dll_filename() -> str:
    """Platform-specific file name the bridge searches for."""
    if sys.platform == "win32":
        return "Live2DCubismCore.dll"
    if sys.platform == "darwin":
        return "libLive2DCubismCore.dylib"
    return "libLive2DCubismCore.so"


def _arch_hint() -> str:
    """Path substring that marks the right-arch build. Used to sort
    multiple matches so an ``rglob`` that finds both ``x86`` and
    ``x86_64`` doesn't pick the 32-bit one."""
    if sys.platform == "darwin":
        return "macos"
    return "x86_64"


def _scan_sdk_root(root: Path) -> list[Path]:
    """Find every Live2DCubismCore library under ``root``. The SDK
    layout is ``Core/dll/<platform>/<arch>/Live2DCubismCore.*`` but
    we ``rglob`` so the user can extract the zip at any depth (or
    rename the wrapping folder) and the bridge still finds it.

    Returns ``[]`` when ``root`` doesn't exist — keeps the candidate
    list short rather than raising on a missing folder."""
    if not root.is_dir():
        return []
    name = _dll_filename()
    hint = _arch_hint()
    results = list(root.rglob(name))
    results.sort(key=lambda p: 0 if hint in str(p) else 1)
    return results


def _candidate_dll_paths(explicit: str | Path | None = None) -> list[Path]:
    """Return the ordered list of paths to probe.

    Priority:

    1. ``explicit`` — caller-supplied path (e.g. the workspace UI
       dialog or a test fixture).
    2. ``<cwd>/sdk/`` — scanned recursively. Drop the unzipped Cubism
       SDK under ``<project>/sdk/`` and the bridge picks it up with
       zero configuration.
    3. ``CUBISM_CORE_DLL`` environment variable.

    No hardcoded user-profile / Downloads sweep — placement decisions
    stay with the user, not the source tree.
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    candidates.extend(_scan_sdk_root(Path.cwd() / "sdk"))
    env = os.environ.get(LIBRARY_ENV_VAR)
    if env:
        candidates.append(Path(env))
    return candidates


def find_dll(explicit: str | Path | None = None) -> Path | None:
    """Return the first existing candidate path, or ``None`` when the
    user hasn't placed the SDK anywhere we know about."""
    for candidate in _candidate_dll_paths(explicit):
        if candidate.is_file():
            return candidate
    return None


def load_library(path: str | Path | None = None) -> ctypes.CDLL:
    """Load the Cubism Core DLL and wire up the argument / return
    types for every function we wrap. Raises
    :class:`CubismBridgeError` when no candidate path resolves."""
    found = find_dll(path)
    if found is None:
        raise CubismBridgeError(
            "Live2DCubismCore library not found. Either:\n"
            "  • drop the extracted Cubism SDK under <cwd>/sdk/ (e.g. "
            "<cwd>/sdk/CubismSdkForNative-5-r.5/),\n"
            f"  • set the {LIBRARY_ENV_VAR} environment variable to "
            "the library file's absolute path, or\n"
            "  • pass the path explicitly to load_library(path).",
        )
    try:
        lib = ctypes.CDLL(str(found))
    except OSError as exc:
        raise CubismBridgeError(f"failed to load {found}: {exc}") from exc
    _bind_signatures(lib)
    return lib


_MODEL = (ctypes.c_void_p,)          # every per-model array getter takes the model only
_MOC_BUFFER = (ctypes.c_void_p, ctypes.c_uint)
_FLOATS = ctypes.POINTER(ctypes.c_float)
_INTS = ctypes.POINTER(ctypes.c_int)
_BYTES = ctypes.POINTER(ctypes.c_ubyte)
_NAMES = ctypes.POINTER(ctypes.c_char_p)

# exported function -> (restype, argtypes), grouped as the Cubism Core header does.
_SIGNATURES: dict[str, tuple] = {
    "csmGetVersion": (ctypes.c_uint, ()),
    "csmGetMocVersion": (ctypes.c_uint, _MOC_BUFFER),
    "csmHasMocConsistency": (ctypes.c_int, _MOC_BUFFER),
    "csmReviveMocInPlace": (ctypes.c_void_p, _MOC_BUFFER),
    "csmGetSizeofModel": (ctypes.c_uint, _MODEL),
    "csmInitializeModelInPlace": (
        ctypes.c_void_p, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint)),
    "csmUpdateModel": (None, _MODEL),
    # Canvas info
    "csmReadCanvasInfo": (None, (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float * 2),
        ctypes.POINTER(ctypes.c_float * 2),
        _FLOATS,
    )),
    # Parameters
    "csmGetParameterCount": (ctypes.c_int, _MODEL),
    "csmGetParameterIds": (_NAMES, _MODEL),
    "csmGetParameterMinimumValues": (_FLOATS, _MODEL),
    "csmGetParameterMaximumValues": (_FLOATS, _MODEL),
    "csmGetParameterDefaultValues": (_FLOATS, _MODEL),
    "csmGetParameterValues": (_FLOATS, _MODEL),
    # Drawables
    "csmGetDrawableCount": (ctypes.c_int, _MODEL),
    "csmGetDrawableIds": (_NAMES, _MODEL),
    "csmGetDrawableTextureIndices": (_INTS, _MODEL),
    "csmGetDrawableDrawOrders": (_INTS, _MODEL),
    "csmGetRenderOrders": (_INTS, _MODEL),
    "csmGetDrawableDynamicFlags": (_BYTES, _MODEL),
    "csmGetDrawableVertexCounts": (_INTS, _MODEL),
    "csmGetDrawableVertexPositions": (ctypes.POINTER(_FLOATS), _MODEL),
    "csmGetDrawableVertexUvs": (ctypes.POINTER(_FLOATS), _MODEL),
    "csmGetDrawableIndexCounts": (_INTS, _MODEL),
    "csmGetDrawableIndices": (ctypes.POINTER(ctypes.POINTER(ctypes.c_ushort)), _MODEL),
    "csmGetDrawableOpacities": (_FLOATS, _MODEL),
    "csmGetDrawableConstantFlags": (_BYTES, _MODEL),
    "csmGetDrawableBlendModes": (_INTS, _MODEL),
    "csmGetDrawableMaskCounts": (_INTS, _MODEL),
    "csmGetDrawableMasks": (ctypes.POINTER(_INTS), _MODEL),
}


def _bind_signatures(lib: ctypes.CDLL) -> None:
    """Tell ctypes the calling-convention shapes for every exported
    function we'll touch. Without this, ctypes assumes ``int``
    arguments / return on Windows which mangles pointers on 64-bit."""
    for name, (restype, argtypes) in _SIGNATURES.items():
        function = getattr(lib, name)
        function.restype = restype
        function.argtypes = list(argtypes)


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
    render_order: int
    is_visible: bool
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
        render_orders = self._lib.csmGetRenderOrders(self._model_ptr)
        dynamic_flags = self._lib.csmGetDrawableDynamicFlags(self._model_ptr)
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
                render_order=int(render_orders[i]),
                is_visible=bool(int(dynamic_flags[i]) & CSM_IS_VISIBLE),
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

    def visibility_flags(self) -> list[bool]:
        """Per-drawable ``IsVisible`` bit at the current parameter
        state. Used by the converter to detect parameter-driven
        visibility transitions that vertex sampling alone misses —
        e.g. hand-gesture poses Cubism toggles via dynamic flags
        rather than vertex deltas. One C call regardless of drawable
        count, so cheap enough to call in the sample-and-reconstruct
        inner loop."""
        count = self.drawable_count()
        flags = self._lib.csmGetDrawableDynamicFlags(self._model_ptr)
        return [bool(int(flags[i]) & CSM_IS_VISIBLE) for i in range(count)]

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
