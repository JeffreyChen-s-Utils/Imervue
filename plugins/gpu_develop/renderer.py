"""The wgpu develop renderer: the basic develop stages on the discrete GPU, the rest on the CPU.

:func:`probe` names the discrete GPU (or ``None``); :class:`GpuDevelopRenderer`
opens a device on it and renders recipes: geometry on the CPU, the stages from
white balance to the tone curve in the shader, the stages after them through
``Recipe.apply_stages``. Images larger than one storage buffer are processed in
slices; contrast, which pivots on the whole image's mean luminance, takes a
second pass once every slice has reported its sum. A wgpu failure surfaces as
``RuntimeError``, which ``develop_backends.render`` answers by rendering that
image on the CPU.
"""
from __future__ import annotations

import logging

import numpy as np

from Imervue.image.recipe import STAGE_NAMES, Recipe

from gpu_develop.adapter_policy import choose_adapter, describe, instance_backends
from gpu_develop.develop_shader import SHADER, WORKGROUP_SIZE
from gpu_develop.params import (
    FIRST_STAGE,
    LAST_STAGE,
    TABLE_WORDS,
    GpuPlan,
    contrast_mean,
    gpu_plan,
    stages_supported,
)

logger = logging.getLogger("Imervue.plugin.gpu_develop")

_MAX_GROUPS_PER_ROW = 65535
_MAX_SLICE_BYTES = 256 * 1024 * 1024
_UNIFORM_BYTES = 32
_UNSUPPORTED = "this Imervue's develop stages differ from the ones the GPU renders; update the plugin"


def _before(stage: str) -> str:
    return STAGE_NAMES[STAGE_NAMES.index(stage) - 1]


def _after(stage: str) -> str:
    return STAGE_NAMES[STAGE_NAMES.index(stage) + 1]


def _gpu_errors() -> tuple[type[BaseException], ...]:
    import wgpu
    return wgpu.GPUError, wgpu.GPUPipelineError


def limit_backends() -> None:
    """Create wgpu's instance with only the APIs the adapter policy can choose.

    By default wgpu probes every API, OpenGL included; with Vulkan and OpenGL
    probed together, instance creation crashed (an access violation inside
    ``wgpuCreateInstance``) on a machine where either one alone worked. The
    instance is process-wide: when one already exists it is kept.
    """
    try:
        from wgpu.backends.wgpu_native.extras import set_instance_extras
    except ImportError:   # another wgpu backend, without instance extras
        return
    try:
        set_instance_extras(backends=instance_backends())
    except RuntimeError as exc:   # the instance was created earlier in this process
        logger.debug("wgpu instance already exists, keeping its backends: %s", exc)


def _discrete_adapter():
    import wgpu
    limit_backends()
    adapters = list(wgpu.gpu.enumerate_adapters_sync())
    index = choose_adapter([dict(adapter.info) for adapter in adapters])
    return None if index is None else adapters[index]


def probe() -> str | None:
    """The discrete GPU's name; ``None`` without wgpu, a discrete GPU or a pipeline it can render."""
    if not stages_supported():
        logger.warning(_UNSUPPORTED)
        return None
    try:
        adapter = _discrete_adapter()
    except ImportError:
        return None
    return None if adapter is None else describe(dict(adapter.info))


def dispatch_shape(groups: int) -> tuple[int, int]:
    """Workgroups as ``(x, y)`` within the 65535-per-dimension limit."""
    if groups <= _MAX_GROUPS_PER_ROW:
        return max(groups, 1), 1
    return _MAX_GROUPS_PER_ROW, -(-groups // _MAX_GROUPS_PER_ROW)


def slices(count: int, slice_pixels: int) -> list[tuple[int, int]]:
    """``(start, stop)`` pixel ranges of at most *slice_pixels* (whole workgroups) covering *count*."""
    step = max(WORKGROUP_SIZE, slice_pixels - slice_pixels % WORKGROUP_SIZE)
    return [(start, min(start + step, count)) for start in range(0, count, step)]


class GpuDevelopRenderer:
    """Renders develop recipes on one GPU; use it from one thread at a time.

    Without *adapter* it opens the discrete GPU :func:`probe` names and raises
    ``RuntimeError`` when there is none. Tests pass another adapter.
    """

    def __init__(self, adapter=None) -> None:
        if not stages_supported():
            raise RuntimeError(_UNSUPPORTED)
        import wgpu
        self._usage = wgpu.BufferUsage
        adapter = adapter or _discrete_adapter()
        if adapter is None:
            raise RuntimeError("no discrete GPU found; integrated GPUs are not used")
        self.label = describe(dict(adapter.info))
        try:
            self._open(adapter)
        except _gpu_errors() as exc:
            raise RuntimeError(f"{self.label} could not be opened: {exc}") from exc
        self._pixels = self._sums = self._bind_group = None
        self._capacity = 0

    def _open(self, adapter) -> None:
        usage = self._usage
        limit = min(int(adapter.limits["max-storage-buffer-binding-size"]),
                    int(adapter.limits["max-buffer-size"]))
        self._slice_pixels = min(limit, _MAX_SLICE_BYTES) // 4
        self._device = adapter.request_device_sync(required_limits={
            "max-storage-buffer-binding-size": limit, "max-buffer-size": limit})
        module = self._device.create_shader_module(code=SHADER)
        self._pipeline = self._device.create_compute_pipeline(
            layout="auto", compute={"module": module, "entry_point": "main"})
        self._uniform = self._device.create_buffer(
            size=_UNIFORM_BYTES, usage=usage.UNIFORM | usage.COPY_DST)
        self._tables = self._device.create_buffer(
            size=TABLE_WORDS * 4, usage=usage.STORAGE | usage.COPY_DST)

    def render(self, arr: np.ndarray, recipe: Recipe) -> np.ndarray:
        """``recipe.apply(arr)``, with the basic stages computed on the GPU."""
        if recipe.is_identity():
            return arr
        if arr.ndim != 3 or arr.shape[2] != 4:
            raise ValueError(f"Recipe.apply expects HxWx4 RGBA, got shape={arr.shape}")
        recipe = recipe.normalized()
        arr = recipe.apply_stages(np.ascontiguousarray(arr, dtype=np.uint8), last=_before(FIRST_STAGE))
        plan = gpu_plan(recipe)
        if not plan.empty:
            try:
                arr = self._run(np.ascontiguousarray(arr), plan)
            except _gpu_errors() as exc:
                raise RuntimeError(f"{self.label} failed: {exc}") from exc
        return recipe.apply_stages(arr, first=_after(LAST_STAGE))

    def close(self) -> None:
        """Release the buffers and the device."""
        for buffer in (self._pixels, self._sums, self._uniform, self._tables):
            if buffer is not None:
                buffer.destroy()
        self._pixels = self._sums = self._bind_group = None
        self._capacity = 0
        self._device.destroy()

    def _run(self, arr: np.ndarray, plan: GpuPlan) -> np.ndarray:
        flat = arr.view(np.uint32).reshape(-1).copy()
        ranges = slices(flat.size, self._slice_pixels)
        self._ensure_capacity(ranges[0][1] - ranges[0][0])
        luma_sum = self._sweep(flat, ranges, plan, plan.first_pass())
        second = plan.second_pass(contrast_mean(luma_sum, flat.size))
        if second is not None:
            self._sweep(flat, ranges, plan, second)
        return flat.view(np.uint8).reshape(arr.shape)

    def _sweep(self, flat: np.ndarray, ranges: list[tuple[int, int]], plan: GpuPlan,
               step: tuple[int, np.ndarray]) -> int:
        """One pass over every slice of *flat*; the luminance sum of the whole image."""
        flags, tables = step
        self._device.queue.write_buffer(self._tables, 0, tables.tobytes())
        return sum(self._dispatch(flat, start, stop, plan, flags) for start, stop in ranges)

    def _dispatch(self, flat: np.ndarray, start: int, stop: int, plan: GpuPlan, flags: int) -> int:
        """Run the shader over ``flat[start:stop]`` in place; return the slice's luminance sum."""
        queue = self._device.queue
        count = stop - start
        groups = -(-count // WORKGROUP_SIZE)
        groups_x, groups_y = dispatch_shape(groups)
        queue.write_buffer(self._pixels, 0, flat[start:stop].tobytes())
        queue.write_buffer(self._uniform, 0, plan.uniform(count, flags, groups_x))
        encoder = self._device.create_command_encoder()
        encoder.clear_buffer(self._sums)
        compute = encoder.begin_compute_pass()
        compute.set_pipeline(self._pipeline)
        compute.set_bind_group(0, self._bind_group)
        compute.dispatch_workgroups(groups_x, groups_y, 1)
        compute.end()
        queue.submit([encoder.finish()])
        flat[start:stop] = np.frombuffer(queue.read_buffer(self._pixels, 0, count * 4), np.uint32)
        sums = np.frombuffer(queue.read_buffer(self._sums, 0, groups * 4), np.uint32)
        return int(sums.sum(dtype=np.uint64))

    def _ensure_capacity(self, pixels: int) -> None:
        """Grow the pixel and sum buffers to hold *pixels* (they never shrink)."""
        if pixels <= self._capacity:
            return
        for buffer in (self._pixels, self._sums):
            if buffer is not None:
                buffer.destroy()
        usage = self._usage.STORAGE | self._usage.COPY_DST | self._usage.COPY_SRC
        self._pixels = self._device.create_buffer(size=pixels * 4, usage=usage)
        self._sums = self._device.create_buffer(size=-(-pixels // WORKGROUP_SIZE) * 4, usage=usage)
        self._bind_group = self._device.create_bind_group(
            layout=self._pipeline.get_bind_group_layout(0),
            entries=[{"binding": binding, "resource": {"buffer": buffer}} for binding, buffer in
                     enumerate((self._pixels, self._uniform, self._tables, self._sums))])
        self._capacity = pixels
