# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

# Heavy ML weight blobs — kept out of the installer. Plugins that need them
# (e.g. object_splitter via rembg's ``U2NET_HOME``) download on first use to
# ``<app_dir>/plugins/<plugin>/models/`` or the shared ``<app_dir>/models/``.
_MODEL_EXTENSIONS = (
    '.onnx', '.pt', '.pth', '.safetensors', '.gguf',
    '.h5', '.pb', '.tflite', '.ckpt',
)


def _is_model_asset(dest: str) -> bool:
    norm = dest.replace('\\', '/').lower()
    if norm.endswith(_MODEL_EXTENSIONS):
        return True
    # Catch arbitrary weight filenames that live inside a ``models/`` folder.
    return '/models/' in norm


datas = [
    ('Imervue\\multi_language', 'Imervue\\multi_language'),
    # plugins/ — third-party extension folder. Puppet is no longer here:
    # it was promoted to a built-in Imervue subpackage at Imervue/puppet/
    # and gets picked up automatically by PyInstaller's static analysis.
    ('plugins', 'plugins'),
    # examples/ — ships examples/puppet/march_7th.puppet so users can try
    # the Puppet tab's "Open Puppet…" right after install.
    ('examples', 'examples'),
]
binaries = []
hiddenimports = []
datas += collect_data_files('qt_material')
hiddenimports += collect_submodules('PySide6')
# Plugins import Imervue modules the app itself never imports (e.g.
# Imervue.plugin.model_dir, Imervue.image.inpaint). They load from disk at
# runtime, so the bundle must carry every submodule or those plugins fail
# with ModuleNotFoundError.
hiddenimports += collect_submodules('Imervue')
tmp_ret = collect_all('imageio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rawpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['Imervue\\__main__.py'],
    pathex=['.venv'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Drop model weights from the final bundle. PyInstaller TOC tuples are
# ``(dest, src, typecode)``; the destination is what ends up inside the
# installer, so we match on it to catch both explicit ``plugins/`` entries
# and anything collect_all() happened to drag in.
a.datas = [entry for entry in a.datas if not _is_model_asset(entry[0])]
a.binaries = [entry for entry in a.binaries if not _is_model_asset(entry[0])]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Imervue',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['exe\\Imervue.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Imervue',
)
