"""Which adapter the GPU develop plugin renders on: a discrete GPU only, native API first."""
from __future__ import annotations

import pytest

from gpu_develop.adapter_policy import DISCRETE, backend_order, choose_adapter, describe


def _info(device, adapter_type, backend):
    return {"device": device, "adapter_type": adapter_type, "backend_type": backend}


_HYBRID_LAPTOP = [
    _info("AMD Radeon 760M", "IntegratedGPU", "Vulkan"),
    _info("RTX 5060", DISCRETE, "D3D12"),
    _info("AMD Radeon 760M", "IntegratedGPU", "D3D12"),
    _info("RTX 5060", DISCRETE, "Vulkan"),
    _info("Microsoft Basic Render Driver", "CPU", "D3D12"),
    _info("RTX 5060", "Unknown", "OpenGL"),
]


def test_windows_takes_the_discrete_gpu_on_vulkan_first():
    assert choose_adapter(_HYBRID_LAPTOP, "win32") == 3


def test_windows_falls_back_to_d3d12_for_the_discrete_gpu():
    infos = [info for info in _HYBRID_LAPTOP if info["backend_type"] != "Vulkan"]
    assert infos[choose_adapter(infos, "win32")]["device"] == "RTX 5060"
    assert infos[choose_adapter(infos, "win32")]["backend_type"] == "D3D12"


@pytest.mark.parametrize("kind", ["IntegratedGPU", "CPU", "VirtualGPU", "Unknown"])
def test_anything_but_a_discrete_gpu_is_never_chosen(kind):
    assert choose_adapter([_info("gpu", kind, "Vulkan"), _info("gpu", kind, "D3D12")], "win32") is None


def test_no_adapters_means_no_gpu():
    assert choose_adapter([], "win32") is None


def test_a_discrete_gpu_behind_opengl_only_is_not_used():
    assert choose_adapter([_info("RTX", DISCRETE, "OpenGL")], "linux") is None


@pytest.mark.parametrize(("platform", "backend", "chosen"), [
    ("darwin", "Metal", 0), ("darwin", "Vulkan", None),
    ("linux", "Vulkan", 0), ("linux", "D3D12", None),
])
def test_each_system_uses_its_own_apis(platform, backend, chosen):
    assert choose_adapter([_info("gpu", DISCRETE, backend)], platform) == chosen


def test_backend_order_per_system():
    assert backend_order("win32") == ("Vulkan", "D3D12")
    assert backend_order("darwin") == ("Metal",)
    assert backend_order("freebsd") == ("Vulkan",)


def test_describe_names_the_device_and_its_api():
    assert describe(_info(" RTX 5060 ", DISCRETE, "Vulkan")) == "RTX 5060 (Vulkan)"


@pytest.mark.parametrize(("info", "expected"), [
    ({"backend_type": "Metal"}, "GPU (Metal)"),
    ({"device": "RTX"}, "RTX"),
    ({}, "GPU"),
])
def test_describe_with_missing_fields(info, expected):
    assert describe(info) == expected
