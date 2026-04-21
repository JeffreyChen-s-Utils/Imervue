# 使用 PyInstaller 打包 Imervue

本文件說明如何用 PyInstaller 將 Imervue 打包成可獨立執行的應用程式，並提供 **Windows / Linux / macOS** 三種平台的命令與注意事項。

> PyInstaller 基本上是跨平台的，**但只能在目標平台自己打包目標平台的產物**——不能在 Windows 上交叉編譯出 Linux / mac 版。需要三個平台就得跑三台機器（或三個 CI runner）。

## 1. 前置準備

### 1.1 Windows

```bat
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
pip install pyinstaller
pip install auto-py-to-exe   :: 可選，GUI 介面
```

### 1.2 Linux（Ubuntu / Debian / Fedora / Arch）

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install pyinstaller
```

系統依賴（PySide6 / OpenGL 必要）：

```bash
# Debian / Ubuntu
sudo apt install libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 \
                 libfontconfig1 libxcb-cursor0 libxcb-icccm4 \
                 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
                 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
                 libxcb-xkb1 libxkbcommon-x11-0

# Fedora
sudo dnf install mesa-libGL libxkbcommon dbus-libs fontconfig \
                 xcb-util-cursor xcb-util-image xcb-util-keysyms \
                 xcb-util-renderutil xcb-util-wm

# Arch
sudo pacman -S libglvnd libxkbcommon dbus fontconfig xcb-util-cursor \
               xcb-util-image xcb-util-keysyms xcb-util-renderutil \
               xcb-util-wm
```

### 1.3 macOS

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install pyinstaller
```

需要 **Xcode Command Line Tools**（`xcode-select --install`），用來提供 codesign 與一部分 Qt 相依的系統框架。Apple Silicon 機器若要同時支援 Intel，請另外準備 universal Python——一般情況不需要，直接用 arm64 原生版即可。

### 1.4 圖示檔案準備

專案內只附了 Windows 用的 `exe/Imervue.ico`。其他平台需要對應格式：

| 平台 | 檔案 | 生成方式 |
|---|---|---|
| Windows | `exe/Imervue.ico` | 已附 |
| Linux | `exe/Imervue.png` (建議 256×256 或 512×512) | 用 ImageMagick：`convert exe/Imervue.ico[0] -resize 512x512 exe/Imervue.png` |
| macOS | `exe/Imervue.icns` | 用 `iconutil`（見下面 macOS 章節） |

macOS `.icns` 轉檔腳本：

```bash
# 假設你手邊有一張 1024×1024 的 PNG 叫 source.png
mkdir Imervue.iconset
sips -z 16 16     source.png --out Imervue.iconset/icon_16x16.png
sips -z 32 32     source.png --out Imervue.iconset/icon_16x16@2x.png
sips -z 32 32     source.png --out Imervue.iconset/icon_32x32.png
sips -z 64 64     source.png --out Imervue.iconset/icon_32x32@2x.png
sips -z 128 128   source.png --out Imervue.iconset/icon_128x128.png
sips -z 256 256   source.png --out Imervue.iconset/icon_128x128@2x.png
sips -z 256 256   source.png --out Imervue.iconset/icon_256x256.png
sips -z 512 512   source.png --out Imervue.iconset/icon_256x256@2x.png
sips -z 512 512   source.png --out Imervue.iconset/icon_512x512.png
cp source.png                Imervue.iconset/icon_512x512@2x.png
iconutil -c icns Imervue.iconset -o exe/Imervue.icns
```

## 2. 打包命令

專案入口為 `Imervue/__main__.py`。**關鍵差異**：`--add-data` 的路徑分隔符在 Windows 是 `;`，Linux / macOS 是 `:`。

### 2.1 Windows

> **注意 shell**：下面的 `^` 是 **cmd.exe / `.bat` 檔**的行續字元，**PowerShell 跟 Git Bash 都不認得**。在 PowerShell 貼 `^` 版本會整個命令斷掉（PyInstaller 會把 `^` 當成獨立參數）。對策跟 `nuitka.md §2.1` 一樣：存成 `.bat` 檔跑、PowerShell 改用反引號 `` ` ``、或全部寫成一行。

**cmd / `.bat` 版**：

```bat
pyinstaller ^
  --noconfirm ^
  --windowed ^
  --name Imervue ^
  --icon exe\Imervue.ico ^
  --paths .venv ^
  --collect-all imageio ^
  --collect-all rawpy ^
  --collect-submodules PySide6 ^
  --collect-data qt_material ^
  --add-data "Imervue\multi_language;Imervue\multi_language" ^
  --add-data "plugins;plugins" ^
  --add-data "exe;exe" ^
  --add-data "THIRD_PARTY_LICENSES.md;." ^
  --add-data "LICENSE;." ^
  Imervue\__main__.py
```

**PowerShell 版**（換成反引號 `` ` ``）：

```powershell
pyinstaller `
  --noconfirm `
  --windowed `
  --name Imervue `
  --icon exe\Imervue.ico `
  --paths .venv `
  --collect-all imageio `
  --collect-all rawpy `
  --collect-submodules PySide6 `
  --collect-data qt_material `
  --add-data "Imervue\multi_language;Imervue\multi_language" `
  --add-data "plugins;plugins" `
  --add-data "exe;exe" `
  --add-data "THIRD_PARTY_LICENSES.md;." `
  --add-data "LICENSE;." `
  Imervue\__main__.py
```

**一行版**（任何 shell 都能用）：

```
pyinstaller --noconfirm --windowed --name Imervue --icon exe\Imervue.ico --paths .venv --collect-all imageio --collect-all rawpy --collect-submodules PySide6 --collect-data qt_material --add-data "Imervue\multi_language;Imervue\multi_language" --add-data "plugins;plugins" --add-data "exe;exe" --add-data "THIRD_PARTY_LICENSES.md;." --add-data "LICENSE;." Imervue\__main__.py
```

產物：`dist\Imervue\Imervue.exe`。

### 2.2 Linux

```bash
pyinstaller \
  --noconfirm \
  --windowed \
  --name Imervue \
  --icon exe/Imervue.png \
  --paths .venv \
  --collect-all imageio \
  --collect-all rawpy \
  --collect-submodules PySide6 \
  --collect-data qt_material \
  --add-data "Imervue/multi_language:Imervue/multi_language" \
  --add-data "plugins:plugins" \
  --add-data "exe:exe" \
  --add-data "THIRD_PARTY_LICENSES.md:." \
  --add-data "LICENSE:." \
  Imervue/__main__.py
```

產物：`dist/Imervue/Imervue`（可執行二進位）。Linux 上 `--windowed` 實際上是 no-op——本來就沒有 console 視窗——但加上無害，跨平台 spec 統一比較方便。

想要 `.desktop` 桌面捷徑，自己寫一個放 `~/.local/share/applications/imervue.desktop`：

```ini
[Desktop Entry]
Type=Application
Name=Imervue
Exec=/absolute/path/to/dist/Imervue/Imervue %F
Icon=/absolute/path/to/dist/Imervue/_internal/exe/Imervue.png
Categories=Graphics;Viewer;
MimeType=image/png;image/jpeg;image/webp;image/tiff;
```

### 2.3 macOS

```bash
pyinstaller \
  --noconfirm \
  --windowed \
  --name Imervue \
  --icon exe/Imervue.icns \
  --osx-bundle-identifier com.imervue.Imervue \
  --paths .venv \
  --collect-all imageio \
  --collect-all rawpy \
  --collect-submodules PySide6 \
  --collect-data qt_material \
  --add-data "Imervue/multi_language:Imervue/multi_language" \
  --add-data "plugins:plugins" \
  --add-data "exe:exe" \
  --add-data "THIRD_PARTY_LICENSES.md:." \
  --add-data "LICENSE:." \
  Imervue/__main__.py
```

產物：

- `dist/Imervue.app/`（`--windowed` 會讓 PyInstaller 產 `.app` bundle——macOS 上必加，否則按兩下打不開）
- `dist/Imervue/Imervue`（命令列二進位版，當測試用）

**簽章與公證（發佈前必做）**：

```bash
# 1. 簽章（需要 Developer ID Application 憑證）
codesign --deep --force --verify --verbose \
         --sign "Developer ID Application: Your Name (TEAMID)" \
         --options runtime --entitlements exe/entitlements.plist \
         dist/Imervue.app

# 2. 打包成 zip 送 notary（不要用 tar/gz，notary 只吃 zip/pkg/dmg）
ditto -c -k --keepParent dist/Imervue.app Imervue.zip

# 3. 送 Apple 公證
xcrun notarytool submit Imervue.zip \
      --apple-id you@example.com \
      --team-id TEAMID \
      --password "@keychain:AC_PASSWORD" \
      --wait

# 4. 公證完把 ticket 裝訂回 .app
xcrun stapler staple dist/Imervue.app
```

沒簽章 / 沒公證的 `.app` 在 Catalina (10.15) 以後的 macOS 上會跳「無法驗證開發者」的 Gatekeeper 警告，使用者得右鍵 → 打開才能繞過。個人玩可以，發佈請走完公證流程。

### 2.4 命令重點說明（三平台共通）

- `--windowed`：GUI 應用必加。Windows 不跳 console、macOS 產 `.app` bundle、Linux 無影響。
- `--paths .venv`：確保虛擬環境中的套件可被搜尋到。
- `--collect-all imageio`、`--collect-all rawpy`：這兩個套件內含動態載入的 plugin / 原生函式庫，必須整包收集。
- `--collect-submodules PySide6`：避免少數 Qt 子模組漏掉。
- `--collect-data qt_material`：qt-material 的 QSS / 資源。
- `--add-data`：語言檔和 plugins 目錄。**Windows 用 `;`，Linux / macOS 用 `:`** 分隔來源與目的。
- `defusedxml`：`Imervue/image/xmp_sidecar.py` 會用 `defusedxml` 做 XMP sidecar 的安全 XML 解析（bandit `B405`–`B411`）。PyInstaller 的靜態 import 分析會自動把它收進來，不需要額外 `--collect-all defusedxml`。但**務必確認 venv 已 `pip install defusedxml`**——沒裝的話 XMP 讀寫功能在 frozen 產物中會拋 `ModuleNotFoundError: defusedxml` 而非 silent fallback。

## 3. 使用 auto-py-to-exe（僅 Windows，GUI 方式）

專案內已附帶設定檔 `packaging/auto_py_to_exe_config.json`：

```bat
auto-py-to-exe
```

1. `Settings` → `Import Config From JSON File` → 選擇 `packaging/auto_py_to_exe_config.json`
2. 調整 `Script Location` 為本機 `Imervue\__main__.py` 絕對路徑
3. Additional Files 加入：
   - `Imervue\multi_language` → `Imervue\multi_language`
   - `plugins` → `plugins`
4. Advanced → `--collect-all` 加上 `rawpy`
5. 點 `CONVERT .PY TO .EXE`

auto-py-to-exe 只支援 Windows；Linux / macOS 請直接用命令列或 `.spec` 檔。

## 4. 常見問題

| 症狀 | 平台 | 解法 |
|---|---|---|
| 啟動閃退，log 顯示 `qt_material` css 找不到 | 全平台 | 加 `--collect-data qt_material` |
| 讀 RAW 檔（CR2/NEF/ARW）失敗 | 全平台 | 加 `--collect-all rawpy` |
| GIF / WEBP 無法播放 | 全平台 | 加 `--collect-all imageio` |
| plugin 不見 | 全平台 | `--add-data plugins` 分隔符寫錯（Windows `;` vs Unix `:`） |
| CJK 字串顯示成問號 | Windows | 用 `--windowed`，並確保 `PYTHONIOENCODING=utf-8` |
| 遞迴深度錯誤 | 全平台 | 在 `.spec` 裡加 `import sys; sys.setrecursionlimit(5000)` |
| 啟動時 `libGL.so.1 not found` | Linux | 裝 `libgl1`（§1.2 的 apt 列表） |
| 啟動時 `Could not load the Qt platform plugin "xcb"` | Linux | 缺 `libxkbcommon` 或 `xcb-util-cursor` 家族（見 §1.2） |
| `.app` 按兩下沒反應 | macOS | 少了 `--windowed`；或者先用 `dist/Imervue.app/Contents/MacOS/Imervue` 從 terminal 跑看看錯誤 |
| Gatekeeper 跳「無法驗證開發者」 | macOS | 需要 codesign + notarize（見 §2.3） |
| `ModuleNotFoundError: onnxruntime` 啟動後執行 plugin 才噴 | 全平台 | plugin 的執行期 pip 安裝走 `<app_dir>/lib/site-packages`，PyInstaller 自動處理；若未處理先看 plugin 日誌 |
| `KeyError: '__reduce_cython__'`（OpenGL_accelerate） | 全平台 | `PyOpenGL_accelerate` 的 Cython 擴展在打包後可能無法正常初始化。`__main__.py` 已在偵測到打包環境（`sys.frozen` / `__compiled__`）時自動設定 `OpenGL.USE_ACCELERATE = False`，改用純 Python 的 PyOpenGL。效能影響極小 |

## 5. 從 .spec 檔打包（進階）

若要長期維護打包設定，建議第一次跑完 PyInstaller 後直接編輯產生的 `Imervue.spec`，之後每次打包：

```bash
pyinstaller --noconfirm Imervue.spec
```

在 `.spec` 中可用 `datas=[...]`、`hiddenimports=[...]` 管理資源與隱藏匯入。同一份 `.spec` 在三個平台通常都能跑——只要把 `Analysis` 裡的 `datas` 路徑用 Python 的 `os.path.join()` 組起來就行，分隔符由 OS 決定，不會卡 `;` / `:`。

```python
import os
datas = [
    (os.path.join('Imervue', 'multi_language'),
     os.path.join('Imervue', 'multi_language')),
    ('plugins', 'plugins'),
    ('exe', 'exe'),
    ('THIRD_PARTY_LICENSES.md', '.'),
    ('LICENSE', '.'),
]
```

### 5.1 排除模型權重（必做）

`plugins/object_splitter/models/*.onnx`（~340 MB）、`models/clip_vit_b32.onnx` 之類的
ML 權重**不該**塞進安裝檔。它們是 plugin 執行期才需要的資源——`rembg` 的 `new_session()`
會自動透過 `U2NET_HOME` 下載缺失的 `.onnx`；`Imervue.library.auto_tag.try_clip_labels`
沒模型就自動 fallback 到 heuristic classifier。

`Imervue.spec` 已經在 `Analysis` 後面加了這段 post-filter：

```python
_MODEL_EXTENSIONS = (
    '.onnx', '.pt', '.pth', '.safetensors', '.gguf',
    '.h5', '.pb', '.tflite', '.ckpt',
)

def _is_model_asset(dest: str) -> bool:
    norm = dest.replace('\\', '/').lower()
    if norm.endswith(_MODEL_EXTENSIONS):
        return True
    return '/models/' in norm

a.datas = [e for e in a.datas if not _is_model_asset(e[0])]
a.binaries = [e for e in a.binaries if not _is_model_asset(e[0])]
```

如果是走 CLI 不用 spec，改成 `--add-data "plugins;plugins"` 之後手動把
`dist/Imervue/_internal/plugins/object_splitter/models/*.onnx` 刪掉，或先移走 `models/`
子目錄再打包。驗證方式：

```bash
# Windows
dir /s dist\Imervue\*.onnx
# Linux / macOS
find dist/Imervue -name '*.onnx' -o -name '*.pt' -o -name '*.safetensors'
```

應該**完全沒有輸出**。若有，代表 `_is_model_asset` 漏掉副檔名或路徑樣式，補進 `_MODEL_EXTENSIONS`。

## 6. 驗證產物

- **Windows**：`dist\Imervue\Imervue.exe --debug`
- **Linux**：`./dist/Imervue/Imervue --debug`
- **macOS**：`./dist/Imervue.app/Contents/MacOS/Imervue --debug`（從 terminal 跑才看得到 log）

三個平台都請覆蓋以下情境：

1. 開啟一般 PNG / JPEG
2. 開啟 RAW（CR2 / NEF / ARW）——驗證 `rawpy`
3. 播放 GIF / APNG——驗證 `imageio`
4. 切換語言——驗證 `multi_language` 資料夾
5. 載入至少一個 plugin（例如 `plugins/object_splitter`）——驗證 plugin 目錄與 `models/` 子目錄
6. 新增 / 列出書籤——驗證 `user_setting.json` 讀寫路徑
7. 執行期 pip 安裝：跑一個帶依賴的 plugin（如 AI 背景移除），安裝成功後 **關閉 app → 重開 → 不用再安裝就能用** ⇒ 代表 `lib/site-packages` 有正確被加進 `sys.path`
8. 修改面板（Develop）：調整曝光 / 亮度 / **白平衡（色溫、色調）/ 色調分區（Shadows、Midtones、Highlights）/ Vibrance** 滑桿——畫布即時預覽，不修改原檔；儲存後才寫入磁碟
9. AI 圖片放大：選擇傳統方法（Lanczos / Bicubic / Nearest）放大，不需安裝 ONNX 依賴即可運作
10. 圖片淨化重繪：選擇傳統放大方法搭配目標解析度，確認輸出圖片尺寸正確且 EXIF 已清除
11. 命令面板（`Ctrl+Shift+P`）：鍵入動作名稱、模糊匹配並執行——驗證快捷鍵對照表與動作註冊表在 frozen 環境載入完整
12. 巨集錄製／回放、Session 儲存／還原：錄一段巨集並存檔、開幾張圖存 session → 關 app → 重開後回放／載入——驗證使用者設定目錄下 JSON 的讀寫路徑
13. 外部編輯器：設定系統上的 Photoshop／GIMP／Krita → 右鍵「在外部編輯器開啟」——驗證 `subprocess` 在 frozen 環境下能 spawn 外部程式
14. 匯出 Contact sheet（PNG／PDF）／ HTML gallery／MP4 投影片——驗證 `imageio-ffmpeg` 的 ffmpeg binary 能被找到，且 PIL 字型資源被完整收集
15. Library 索引與智慧相簿：重建索引、建一個規則式相簿（例如「ISO ≥ 800」）——驗證 sqlite 檔寫入使用者設定目錄、EXIF 讀取正常
16. Culling 標記（`P` / `X` / `U`）、色彩標籤（`F1`-`F5`）、**星等評分（`1`-`5` 在 list view 欄位與 EXIF 側欄星條顯示）**、重複圖片偵測、EXIF 剝除——驗證 sidecar（`.imervue.json`）讀寫與 `imagehash` / `piexif` 被打包
17. Timeline 時間軸檢視與模糊搜尋（`Ctrl+F`）——驗證 EXIF 日期解析與搜尋索引建置
18. Compare overlay：選兩張圖 → 開啟疊合比對，切換融合／差異模式，**切到 A|B split 分頁驗證前後對比拖曳條**——驗證 GPU shader 在 frozen 下編譯成功
19. 分頁（`,` / `.`）／雙頁（`Tab`）／列表（`L`）三種檢視切換，並在列表中 hover 預覽——驗證 OpenGL 替代佈局貼圖建置與 hover 視窗渲染
20. 歷史返回／前進（`Alt+←` / `Alt+→`）、裁切工具、非破壞性 develop：裁切＋調整後關閉並重開，狀態保留——驗證 `.imervue.json` recipe 寫回
21. **浮水印疊加**：開啟浮水印對話框，套用文字 / 圖片浮水印於輸出——驗證 PIL 的 `ImageDraw` / `ImageFont` 在 frozen 下能載入字型資源
22. **Export presets**：用 Web 1600px / Print 300dpi / Instagram 1080×1080 三種預設匯出——驗證 PIL 的 resample / DPI metadata 寫入正常
23. **XMP sidecar**：載入含 Lightroom／Capture One 產生的 `.xmp` 圖片，確認星等 / 色彩標籤 / 開發參數被讀取；編輯後存檔再用 LR/C1 開啟，確認 sidecar 能被對方讀回——驗證 `defusedxml` 被打包進產物
