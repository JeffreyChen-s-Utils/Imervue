#!/usr/bin/env bash
# Build a Linux AppImage for Imervue.
#
# Prerequisites on PATH: pyinstaller, appimagetool, and a Python with the
# project installed (so the .desktop generator can import Imervue). Run from
# the repository root:
#
#     bash packaging/build_appimage.sh
#
# This script cannot be build-validated on Windows. The .desktop body it writes
# comes from Imervue.system.file_association.desktop_entry_content, which is
# unit-tested, so the file-association metadata is at least verified.
set -euo pipefail

APP="Imervue"
DIST="dist/${APP}"

# 1. One-folder PyInstaller build (POSIX ':' data separators, windowed app).
pyinstaller "Imervue/__main__.py" --noconfirm --windowed --name "${APP}" \
  --collect-submodules PySide6 \
  --collect-all imageio \
  --collect-all rawpy \
  --collect-data qt_material \
  --add-data "Imervue/multi_language:Imervue/multi_language" \
  --add-data "plugins:plugins" \
  --add-data "examples:examples"

# 2. Desktop entry + icon at the AppDir root (what appimagetool expects).
python - "${DIST}/${APP}.desktop" <<'PY'
import sys
from Imervue.system.file_association import (
    ASSOC_EXTENSIONS, desktop_entry_content, mime_types_for_extensions,
)
content = desktop_entry_content(
    "Imervue %f", "Imervue", mime_types_for_extensions(ASSOC_EXTENSIONS),
)
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write(content)
PY
# A PNG named after the app makes a crisper icon than the .ico; optional.
cp Imervue.ico "${DIST}/${APP}.png" 2>/dev/null || true

# 3. Pack the AppDir into a single-file AppImage.
ARCH=x86_64 appimagetool "${DIST}" "${APP}-x86_64.AppImage"
echo "Built ${APP}-x86_64.AppImage"
