"""Tests for ``cubism_native_bridge``'s DLL discovery logic.

The Cubism Core DLL itself can't be redistributed, so CI doesn't have
one — we monkeypatch ``Path.cwd`` and ``os.environ`` to exercise the
lookup priority without needing the binary.
"""
from __future__ import annotations

import ctypes

import sys
from pathlib import Path

import pytest

from Imervue.puppet.cubism_native_bridge import (
    LIBRARY_ENV_VAR,
    _candidate_dll_paths,
    _dll_filename,
    _scan_sdk_root,
    find_dll,
)


def _fake_dll_tree(root: Path) -> Path:
    """Lay out a fake SDK at ``root`` so the scanner has a hit. Uses
    the same ``Core/dll/<platform>/<arch>/`` layout the real Cubism
    SDK ships with so the arch-hint sort is exercised too."""
    if sys.platform == "win32":
        rel = Path("Core/dll/windows/x86_64") / _dll_filename()
    elif sys.platform == "darwin":
        rel = Path("Core/dll/macos") / _dll_filename()
    else:
        rel = Path("Core/dll/linux/x86_64") / _dll_filename()
    dll_path = root / rel
    dll_path.parent.mkdir(parents=True, exist_ok=True)
    dll_path.write_bytes(b"")
    return dll_path


def test_explicit_path_wins(tmp_path, monkeypatch):
    explicit_dll = tmp_path / "explicit.dll"
    explicit_dll.write_bytes(b"")
    # Also drop one under <cwd>/sdk so we can verify explicit wins
    sdk_dll = _fake_dll_tree(tmp_path / "sdk")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
    resolved = find_dll(explicit=explicit_dll)
    assert resolved == explicit_dll
    assert resolved != sdk_dll


def test_cwd_sdk_is_default_when_no_explicit(tmp_path, monkeypatch):
    sdk_dll = _fake_dll_tree(tmp_path / "sdk")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
    resolved = find_dll()
    assert resolved == sdk_dll


def test_env_var_used_when_no_explicit_and_no_cwd_sdk(tmp_path, monkeypatch):
    env_dll = tmp_path / "from_env.dll"
    env_dll.write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(LIBRARY_ENV_VAR, str(env_dll))
    resolved = find_dll()
    assert resolved == env_dll


def test_returns_none_when_nothing_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
    assert find_dll() is None


def test_no_hardcoded_user_profile_scan(tmp_path, monkeypatch):
    """A clean cwd + no env var + no explicit path must yield zero
    candidates — confirms we don't fall back to scanning ~/Downloads
    or any other user-profile location."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
    candidates = _candidate_dll_paths()
    assert candidates == []


def test_scan_prefers_arch_hint_when_multiple_matches(tmp_path):
    """Some SDK versions ship both 32- and 64-bit DLLs. The scanner
    sorts arch-hint matches first so we never accidentally load the
    wrong build."""
    if sys.platform != "win32":
        pytest.skip("arch hint only meaningful on Windows in this test")
    sdk_root = tmp_path / "sdk"
    wrong = sdk_root / "Core" / "dll" / "windows" / "x86" / "Live2DCubismCore.dll"
    wrong.parent.mkdir(parents=True)
    wrong.write_bytes(b"")
    right = sdk_root / "Core" / "dll" / "windows" / "x86_64" / "Live2DCubismCore.dll"
    right.parent.mkdir(parents=True)
    right.write_bytes(b"")
    results = _scan_sdk_root(sdk_root)
    # x86_64 build comes first
    assert results[0] == right


def test_scan_handles_arbitrary_nesting(tmp_path):
    """The user might extract ``CubismSdkForNative-5-r.5.zip`` so the
    DLL ends up at ``sdk/CubismSdkForNative-5-r.5/Core/dll/...``.
    ``rglob`` finds it regardless of the wrapping folder depth."""
    nested = tmp_path / "sdk" / "CubismSdkForNative-5-r.5"
    dll = _fake_dll_tree(nested)
    results = _scan_sdk_root(tmp_path / "sdk")
    assert dll in results


def test_load_library_raises_with_actionable_message(tmp_path, monkeypatch):
    from Imervue.puppet.cubism_native_bridge import CubismBridgeError, load_library
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
    with pytest.raises(CubismBridgeError, match="<cwd>/sdk/"):
        load_library()


# ---------------------------------------------------------------------------
# ctypes signatures: every exported function's restype / argtypes, generated
# before ``_bind_signatures`` became table-driven.
# ---------------------------------------------------------------------------

def _describe(ctype) -> str:
    """Name a ctypes type the same way on every Python version.

    ``repr`` is not stable: Python 3.10 shows ``POINTER(c_float)`` as
    ``ctypes.wintypes.LP_c_float`` once ``ctypes.wintypes`` is imported, while
    later versions show ``ctypes.LP_c_float``. Pointers become ``*``, arrays
    ``type[length]``.
    """
    if ctype is None:
        return "None"
    if issubclass(ctype, ctypes._Pointer):  # noqa: SLF001
        return "*" + _describe(ctype._type_)  # noqa: SLF001
    if issubclass(ctype, ctypes.Array):
        return f"{_describe(ctype._type_)}[{ctype._length_}]"  # noqa: SLF001
    return ctype.__name__


_EXPECTED_SIGNATURES = {'csmGetDrawableBlendModes': ('*c_long', ['c_void_p']),
 'csmGetDrawableConstantFlags': ('*c_ubyte', ['c_void_p']),
 'csmGetDrawableCount': ('c_long', ['c_void_p']),
 'csmGetDrawableDrawOrders': ('*c_long', ['c_void_p']),
 'csmGetDrawableDynamicFlags': ('*c_ubyte', ['c_void_p']),
 'csmGetDrawableIds': ('*c_char_p', ['c_void_p']),
 'csmGetDrawableIndexCounts': ('*c_long', ['c_void_p']),
 'csmGetDrawableIndices': ('**c_ushort', ['c_void_p']),
 'csmGetDrawableMaskCounts': ('*c_long', ['c_void_p']),
 'csmGetDrawableMasks': ('**c_long', ['c_void_p']),
 'csmGetDrawableOpacities': ('*c_float', ['c_void_p']),
 'csmGetDrawableTextureIndices': ('*c_long', ['c_void_p']),
 'csmGetDrawableVertexCounts': ('*c_long', ['c_void_p']),
 'csmGetDrawableVertexPositions': ('**c_float', ['c_void_p']),
 'csmGetDrawableVertexUvs': ('**c_float', ['c_void_p']),
 'csmGetMocVersion': ('c_ulong', ['c_void_p', 'c_ulong']),
 'csmGetParameterCount': ('c_long', ['c_void_p']),
 'csmGetParameterDefaultValues': ('*c_float', ['c_void_p']),
 'csmGetParameterIds': ('*c_char_p', ['c_void_p']),
 'csmGetParameterMaximumValues': ('*c_float', ['c_void_p']),
 'csmGetParameterMinimumValues': ('*c_float', ['c_void_p']),
 'csmGetParameterValues': ('*c_float', ['c_void_p']),
 'csmGetRenderOrders': ('*c_long', ['c_void_p']),
 'csmGetSizeofModel': ('c_ulong', ['c_void_p']),
 'csmGetVersion': ('c_ulong', []),
 'csmHasMocConsistency': ('c_long', ['c_void_p', 'c_ulong']),
 'csmInitializeModelInPlace': ('c_void_p', ['c_void_p', 'c_void_p', 'c_ulong']),
 'csmReadCanvasInfo': ('None', ['c_void_p', '*c_float[2]', '*c_float[2]', '*c_float']),
 'csmReviveMocInPlace': ('c_void_p', ['c_void_p', 'c_ulong']),
 'csmUpdateModel': ('None', ['c_void_p'])}


def test_bind_signatures_declares_every_function_exactly():
    from Imervue.puppet import cubism_native_bridge as bridge

    class _Fn:
        pass

    class _Lib:
        def __getattr__(self, name):
            fn = _Fn()
            object.__setattr__(self, name, fn)
            return fn

    lib = _Lib()
    bridge._bind_signatures(lib)  # noqa: SLF001
    actual = {name: (_describe(fn.restype), [_describe(a) for a in fn.argtypes])
              for name, fn in sorted(vars(lib).items())}
    assert actual == _EXPECTED_SIGNATURES
