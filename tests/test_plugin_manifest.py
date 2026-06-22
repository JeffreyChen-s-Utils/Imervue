"""Tests for the plugin manifest + compatibility checks."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.plugin.plugin_manifest import (
    PluginManifest,
    check_compatibility,
    installed_packages,
    manifest_from_plugin,
    parse_version,
    validate_manifest,
    version_satisfies,
)


# ---------------------------------------------------------------------------
# parse_version
# ---------------------------------------------------------------------------


def test_parse_version_basic():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("2") == (2,)


def test_parse_version_drops_pre_release_suffix():
    assert parse_version("1.0.0-rc1") == (1, 0, 0)


def test_parse_version_unparseable_is_empty():
    assert parse_version("") == ()
    assert parse_version("abc") == ()
    assert parse_version(None) == ()  # NOSONAR: negative test of the non-str guard


# ---------------------------------------------------------------------------
# version_satisfies
# ---------------------------------------------------------------------------


def test_empty_constraint_always_passes():
    assert version_satisfies("1.2.3", "")
    assert version_satisfies("1.2.3", None)


@pytest.mark.parametrize("version,constraint,ok", [
    ("1.5.0", ">=1.0", True),
    ("0.9.0", ">=1.0", False),
    ("1.5.0", ">=1.0,<2.0", True),
    ("2.0.0", ">=1.0,<2.0", False),
    ("1.2.3", "==1.2.3", True),
    ("1.2.4", "==1.2.3", False),
    ("1.2.3", "!=1.2.3", False),
    ("2.0.0", ">1.0", True),
])
def test_version_satisfies_ops(version, constraint, ok):
    assert version_satisfies(version, constraint) is ok


def test_version_satisfies_zero_pads_for_comparison():
    # "1.2" should be treated as "1.2.0".
    assert version_satisfies("1.2", ">=1.2.0")
    assert version_satisfies("1.2.0", ">=1.2")


def test_invalid_constraint_raises():
    with pytest.raises(ValueError, match="invalid version constraint"):
        version_satisfies("1.0.0", "~=1.0")


# ---------------------------------------------------------------------------
# manifest_from_plugin
# ---------------------------------------------------------------------------


def test_manifest_from_plugin_reads_attributes():
    plugin = SimpleNamespace(
        plugin_name="Cool", plugin_version="1.2.0",
        plugin_description="does cool", plugin_author="me",
        plugin_requires_imervue=">=1.0",
        plugin_requires_packages=["numpy", "pillow"],
    )
    manifest = manifest_from_plugin(plugin)
    assert manifest.name == "Cool"
    assert manifest.version == "1.2.0"
    assert manifest.requires_imervue == ">=1.0"
    assert manifest.requires_packages == ["numpy", "pillow"]


def test_manifest_from_plugin_uses_defaults():
    manifest = manifest_from_plugin(SimpleNamespace())
    assert manifest.name == ""
    assert manifest.version == "0.0.0"
    assert manifest.requires_packages == []


def test_manifest_from_plugin_ignores_non_list_packages():
    plugin = SimpleNamespace(plugin_name="x", plugin_requires_packages="numpy")
    assert manifest_from_plugin(plugin).requires_packages == []


# ---------------------------------------------------------------------------
# validate_manifest
# ---------------------------------------------------------------------------


def test_validate_clean_manifest_has_no_errors():
    assert validate_manifest(PluginManifest(name="x", version="1.0.0")) == []


def test_validate_flags_missing_name():
    assert "plugin name is required" in validate_manifest(PluginManifest(name="  "))


def test_validate_flags_bad_version():
    errors = validate_manifest(PluginManifest(name="x", version="not-a-version"))
    assert any("not a valid dotted version" in e for e in errors)


def test_validate_flags_bad_constraint():
    errors = validate_manifest(
        PluginManifest(name="x", version="1.0.0", requires_imervue="~=1.0"))
    assert any("requires_imervue" in e for e in errors)


# ---------------------------------------------------------------------------
# check_compatibility
# ---------------------------------------------------------------------------


def test_no_requirements_always_loads():
    ok, reasons = check_compatibility(
        PluginManifest(name="x"), "1.0.69", set())
    assert ok and reasons == []


def test_host_version_too_old_is_blocked():
    manifest = PluginManifest(name="x", requires_imervue=">=2.0")
    ok, reasons = check_compatibility(manifest, "1.0.69", set())
    assert not ok
    assert any("needs Imervue" in r for r in reasons)


def test_missing_package_is_blocked():
    manifest = PluginManifest(name="x", requires_packages=["torch"])
    ok, reasons = check_compatibility(manifest, "1.0.69", {"numpy"})
    assert not ok
    assert any("missing packages: torch" in r for r in reasons)


def test_package_names_compare_normalised():
    manifest = PluginManifest(name="x", requires_packages=["Open_CLIP_Torch"])
    ok, _ = check_compatibility(manifest, "1.0.69", {"open-clip-torch"})
    assert ok


def test_all_requirements_met_loads():
    manifest = PluginManifest(
        name="x", requires_imervue=">=1.0,<2.0", requires_packages=["numpy"])
    ok, reasons = check_compatibility(manifest, "1.5.0", {"numpy", "pillow"})
    assert ok and reasons == []


# ---------------------------------------------------------------------------
# installed_packages
# ---------------------------------------------------------------------------


def test_installed_packages_includes_a_core_dependency():
    packages = installed_packages()
    assert isinstance(packages, set)
    assert "numpy" in packages  # a hard dependency, always present
