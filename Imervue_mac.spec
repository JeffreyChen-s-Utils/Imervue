# -*- mode: python ; coding: utf-8 -*-
# macOS .app build. Mirrors Imervue.spec but uses POSIX-separator data paths
# and adds a BUNDLE step whose Info.plist declares the image file associations
# (so Finder offers "Open With Imervue"). Build on macOS:
#
#     pyinstaller Imervue_mac.spec --noconfirm
#
# Note: this cannot be build-validated on Windows; the document-type
# declaration it relies on is unit-tested via Imervue/system/macos_bundle.py.
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

from Imervue.system.file_association import ASSOC_EXTENSIONS
from Imervue.system.macos_bundle import BUNDLE_IDENTIFIER, info_plist

_MODEL_EXTENSIONS = (
    '.onnx', '.pt', '.pth', '.safetensors', '.gguf',
    '.h5', '.pb', '.tflite', '.ckpt',
)


def _is_model_asset(dest: str) -> bool:
    norm = dest.replace('\\', '/').lower()
    if norm.endswith(_MODEL_EXTENSIONS):
        return True
    return '/models/' in norm


datas = [
    ('Imervue/multi_language', 'Imervue/multi_language'),
    ('plugins', 'plugins'),
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
    ['Imervue/__main__.py'],
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,   # let the .app receive file-open / dropped-file events
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # add 'Imervue.icns' once converted from Imervue.ico
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Imervue',
)
app = BUNDLE(
    coll,
    name='Imervue.app',
    icon=None,             # add 'Imervue.icns' here too
    bundle_identifier=BUNDLE_IDENTIFIER,
    info_plist=info_plist(ASSOC_EXTENSIONS, version='1.0.53'),
)
