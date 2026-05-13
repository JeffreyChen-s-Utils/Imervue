# Third-Party Licenses / 第三方授權聲明

---

Imervue is licensed under the MIT License. See `LICENSE` for details.

Imervue 以 MIT 授權條款發佈，詳見 `LICENSE` 檔案。

This application uses the following third-party libraries. Their licenses
are listed below to comply with redistribution requirements.

本應用程式使用了下列第三方函式庫，為符合各授權條款的散布要求，
在此列出相關授權資訊。

The list is split into three buckets:

1. **Bundled at distribution time** — shipped inside the
   PyInstaller / Nuitka EXE on first install. These declarations
   cover the binary itself.
2. **Installed on demand** — optional packages the user may
   `pip install` (or that a plugin auto-installs into
   `<app_dir>/lib/site-packages/`) to unlock specific features.
   They are not present in the base bundle, but their licenses are
   listed for completeness when they get pulled in.
3. **Not bundled / user-supplied** — third-party SDKs Imervue
   integrates with but explicitly does **not** redistribute. The
   user is responsible for obtaining them under the upstream's
   own terms.

授權清單分為三類：

1. **發佈時打包** — PyInstaller / Nuitka 產出的 EXE 內附；下列聲明涵蓋二進位本體。
2. **需要時安裝** — 使用者透過 `pip install`（或 plugin 自動裝到 `<app_dir>/lib/site-packages/`）才會出現的選用套件；不在基本 bundle 內，列在此處以便完整對照。
3. **不打包 / 使用者自備** — Imervue 整合但**不**散布的第三方 SDK；使用者需自行依上游條款取得。

---

## 1. Bundled at distribution time

### PySide6

- **License / 授權:** LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- **Website / 網站:** https://pyside.org
- **Source code / 原始碼:** https://code.qt.io/cgit/pyside/pyside-setup.git/

Imervue uses PySide6 under the terms of the **GNU Lesser General Public
License v3 (LGPLv3)**. PySide6 is dynamically linked and distributed as
separate shared libraries (`.dll` / `.so` / `.dylib`). You may replace
these libraries with a compatible version at any time.

Imervue 依據 **GNU 較寬鬆通用公共授權條款第 3 版（LGPLv3）** 使用 PySide6。
PySide6 以動態連結方式散布，作為獨立的共享函式庫（`.dll` / `.so` / `.dylib`）。
您可隨時將這些函式庫替換為相容的版本。

A copy of the LGPLv3 is available at:
https://www.gnu.org/licenses/lgpl-3.0.html

LGPLv3 全文可於上述連結取得。

To obtain the source code of PySide6, visit:
https://code.qt.io/cgit/pyside/pyside-setup.git/

PySide6 原始碼可於上述連結取得。

### Qt (via PySide6)

- **License / 授權:** LGPL-3.0-only
- **Website / 網站:** https://www.qt.io
- **Source code / 原始碼:** https://code.qt.io/cgit/qt/qtbase.git/

Qt libraries are redistributed as part of PySide6 under the LGPLv3.
Source code is available at the link above.

Qt 函式庫作為 PySide6 的一部分，依據 LGPLv3 一同散布。
原始碼可於上述連結取得。

### qt-material

- **License / 授權:** BSD-2-Clause
- **Website / 網站:** https://github.com/dunderlab/qt-material

### Pillow

- **License / 授權:** MIT-CMU (Historical Permission Notice and Disclaimer)
- **Website / 網站:** https://python-pillow.github.io

### NumPy

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://numpy.org

### PyOpenGL

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://mcfletch.github.io/pyopengl/

### PyOpenGL-accelerate

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://mcfletch.github.io/pyopengl/

### rawpy

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/letmaik/rawpy

rawpy includes LibRaw, which is licensed under LGPL-2.1. LibRaw source
code is available at: https://github.com/LibRaw/LibRaw

rawpy 包含 LibRaw，其授權為 LGPL-2.1。
LibRaw 原始碼可於上述連結取得。

### imageio

- **License / 授權:** BSD-2-Clause
- **Website / 網站:** https://github.com/imageio/imageio

### imageio-ffmpeg

- **License / 授權:** BSD-2-Clause (Python wrapper) + LGPL-2.1 / GPL-2.0 (bundled FFmpeg binary)
- **Website / 網站:** https://github.com/imageio/imageio-ffmpeg
- **FFmpeg source / FFmpeg 原始碼:** https://ffmpeg.org/download.html

`imageio-ffmpeg` ships a precompiled **FFmpeg** binary used for MP4
slideshow export. The default FFmpeg build is LGPL-2.1; if the user
replaces it with a GPL-licensed build, the GPL applies. Replacement
is supported via the `IMAGEIO_FFMPEG_EXE` environment variable.

`imageio-ffmpeg` 內附預編譯的 **FFmpeg** 二進位（供 MP4 投影片匯出使用）。
預設 FFmpeg 構建為 LGPL-2.1；若使用者替換為 GPL 構建，則套用 GPL。
可透過 `IMAGEIO_FFMPEG_EXE` 環境變數指定替換的 FFmpeg。

### defusedxml

- **License / 授權:** Python Software Foundation License 2.0
- **Website / 網站:** https://github.com/tiran/defusedxml

Used for XMP sidecar parsing — defends against XML attack vectors
(billion-laughs, external-entity expansion) that `xml.etree` is
vulnerable to.

用於 XMP sidecar 解析；可抵禦 `xml.etree` 易遭受的 XML 攻擊向量（如 billion-laughs、外部實體擴展）。

### watchdog

- **License / 授權:** Apache-2.0
- **Website / 網站:** https://github.com/gorakhargosh/watchdog

Used by the file-tree watcher to auto-refresh when the user
modifies the on-disk folder from outside Imervue.

用於檔案樹監視；使用者在 Imervue 以外修改磁碟資料夾時觸發自動重新整理。

---

## 2. Installed on demand (optional)

The following packages are **not** bundled in the base EXE. They
are installed when the user enables a feature that needs them —
either by `pip install`-ing them into the venv, or by the plugin
system's pip installer placing them under
`<app_dir>/lib/site-packages/`.

以下套件**未**內附於基本 EXE。當使用者啟用對應功能時才會安裝 — 由 venv 的 `pip install` 或外掛系統的 pip 安裝器寫入 `<app_dir>/lib/site-packages/`。

### OpenCV (opencv-python)

- **License / 授權:** Apache-2.0
- **Website / 網站:** https://opencv.org
- **Feature triggers / 功能觸發:** Puppet webcam tracking, HDR merge,
  panorama stitching, focus stacking, healing brush, face detection,
  auto-straighten

### MediaPipe

- **License / 授權:** Apache-2.0
- **Website / 網站:** https://github.com/google-ai-edge/mediapipe
- **Feature triggers / 功能觸發:** Puppet webcam face-mesh + iris tracking

### sounddevice

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/spatialaudio/python-sounddevice
- **Feature triggers / 功能觸發:** Puppet microphone lip-sync

`sounddevice` is a Python binding for the PortAudio library
(MIT). PortAudio is dynamically linked, not bundled.

`sounddevice` 是對 PortAudio（MIT）的 Python 綁定；PortAudio 為動態連結，未隨附。

### pyvirtualcam

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/letmaik/pyvirtualcam
- **Feature triggers / 功能觸發:** Puppet virtual-camera output (streaming
  the puppet canvas into OBS / Zoom / Teams)

On Windows / macOS, `pyvirtualcam` relies on a separately installed
OBS Virtual Camera or similar virtual-camera driver. Those drivers
are governed by their own licenses (typically GPLv2 for OBS).

Windows / macOS 平台需另行安裝 OBS Virtual Camera 等虛擬攝影機驅動；該驅動依其自身授權（OBS 為 GPLv2）規範。

### NDI Python (ndi-python)

- **License / 授權:** MIT (Python wrapper)
- **Website / 網站:** https://github.com/buresu/ndi-python
- **Feature triggers / 功能觸發:** Puppet NDI® output (OBS / vMix / NDI Tools)

The Python wrapper is MIT. The underlying **NDI® SDK by Vizrt
Group** is proprietary and governed by its own EULA at
https://ndi.video/legal/ndi-sdk-license-agreement/ — users must
install the SDK separately and accept the EULA.

Python wrapper 為 MIT；底層的 **NDI® SDK by Vizrt Group** 為專利軟體，由其自身 EULA（https://ndi.video/legal/ndi-sdk-license-agreement/） 規範。使用者需另行安裝 SDK 並同意 EULA。

### ONNX Runtime

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/microsoft/onnxruntime
- **Feature triggers / 功能觸發:** AI image upscale (Real-ESRGAN), CLIP
  ONNX auto-tag, AI background removal

### Hugging Face Hub (huggingface_hub)

- **License / 授權:** Apache-2.0
- **Website / 網站:** https://github.com/huggingface/huggingface_hub
- **Feature triggers / 功能觸發:** Downloading pinned model revisions
  for AI upscale / CLIP

### OpenCLIP (open_clip_torch)

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/mlfoundations/open_clip
- **Feature triggers / 功能觸發:** Semantic search (natural-language
  image queries)

### PyTorch (torch)

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://pytorch.org
- **Feature triggers / 功能觸發:** CLIP semantic search backend

### rembg

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/danielgatis/rembg
- **Feature triggers / 功能觸發:** AI background removal (U²-Net / IS-Net)

Pulls in `onnxruntime` and downloads model weights to
`U2NET_HOME` on first use. Weights themselves are governed by
each model's individual license (U²-Net / IS-Net are MIT or
Apache-2.0 — verify per model).

依賴 `onnxruntime`；首次使用會把模型權重下載到 `U2NET_HOME`。權重本身由各模型授權規範（U²-Net / IS-Net 多為 MIT 或 Apache-2.0，請逐一查驗）。

### piexif

- **License / 授權:** MIT
- **Website / 網站:** https://github.com/hMatoba/Piexif
- **Feature triggers / 功能觸發:** Lossless JPEG rotation, GPS geotag
  editor, EXIF write

### reportlab

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://www.reportlab.com/opensource/
- **Feature triggers / 功能觸發:** Print Layout multi-page PDF export

### Send2Trash

- **License / 授權:** BSD-3-Clause
- **Website / 網站:** https://github.com/arsenetar/send2trash
- **Feature triggers / 功能觸發:** Cross-platform "move to trash" for
  the delete-key + culling-reject workflow

---

## 3. Not bundled / user-supplied

The following SDKs / models are **never** redistributed by Imervue.
The user is responsible for obtaining and installing them under
the upstream's own terms.

下列 SDK / 模型**不**隨 Imervue 散布。使用者需依上游條款自行取得並安裝。

### Live2D Cubism Native SDK

- **License / 授權:** Live2D Cubism SDK Free Material License
- **Website / 網站:** https://www.live2d.com/sdk/license/
- **Imervue integration / Imervue 整合方式:** ctypes binding in
  `Imervue/puppet/cubism_native_bridge.py`; the runtime probes
  `<cwd>/sdk/` and the `CUBISM_CORE_DLL` environment variable to
  locate `Live2DCubismCore.dll` / `.so` / `.dylib`.

The Live2D Cubism SDK's **Free Material License explicitly
forbids redistributing the SDK binaries** as part of another
product. Users who want the Puppet tab's `.moc3 → .puppet`
conversion feature must download the Cubism SDK themselves from
the official site and accept Live2D's EULA. The Puppet tab's
standalone runtime (loading and playing already-converted
`.puppet` files) does NOT require the SDK and works on every
default-deps install.

Live2D Cubism SDK 的 **Free Material License 明確禁止將 SDK 二進位作為其他產品一部分散布**。要使用 Puppet 分頁的 `.moc3 → .puppet` 轉換功能的使用者需自行從官方網站下載 Cubism SDK 並同意 Live2D EULA。Puppet 分頁的 standalone 執行期（載入並播放已轉換的 `.puppet` 檔）**不**需要 SDK，預設依賴安裝即可運作。

### ML model weights

- **`.onnx` / `.pt` / `.pth` / `.safetensors` / `.gguf` files**
- **License / 授權:** Per-model (varies)

Pretrained model weights for AI upscale (Real-ESRGAN), background
removal (U²-Net / IS-Net), and CLIP variants are downloaded by
each feature's first-use code path (typically via Hugging Face
Hub with pinned revisions, or `rembg`'s `U2NET_HOME` cache). Their
licenses vary per model and are governed by the upstream model
card. Imervue's packaging deliberately excludes them — see
`nuitka.md` § 2.4 and `pyinstaller.md` § 5.1 for the build-time
filters that keep weights out of the EXE.

AI 放大（Real-ESRGAN）、背景移除（U²-Net / IS-Net）與各 CLIP 變體的預訓練權重，由各功能首次使用時的程式碼下載（多透過 Hugging Face Hub 並 pin 版本，或 `rembg` 的 `U2NET_HOME` 快取）。授權因模型而異，依上游 model card 為準。Imervue 打包時刻意排除權重檔 — 詳見 `nuitka.md` § 2.4 與 `pyinstaller.md` § 5.1 的構建時過濾條件。
