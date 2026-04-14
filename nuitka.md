# 使用 Nuitka 打包 Imervue

本文件說明如何用 Nuitka 將 Imervue 編譯成原生執行檔，並提供 **Windows / Linux / macOS** 三種平台的命令與注意事項。Nuitka 會把 Python 原始碼轉成 C 再編譯，啟動速度與反編譯難度都比 PyInstaller 好，但打包時間較長，也比較挑依賴。

> 跟 PyInstaller 一樣，Nuitka **只能在目標平台自己打包目標平台的產物**——Windows 出 `.exe`、Linux 出 ELF 二進位、macOS 出 `.app` bundle。不能交叉編譯。

## 1. 前置準備

### 1.1 通用（三平台都要裝）

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

### 1.2 Windows — C compiler

- **建議**：安裝 **Visual Studio Build Tools**，勾「使用 C++ 的桌面開發」工作負載。
- **替代**：讓 Nuitka 自動下載 MinGW64（第一次執行時會問，回答 `yes` 即可）。`--assume-yes-for-downloads` 會直接替你按 yes。

### 1.3 Linux — GCC 與系統函式庫

```bash
# Debian / Ubuntu
sudo apt install build-essential patchelf ccache \
                 libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 \
                 libfontconfig1 libxcb-cursor0 libxcb-icccm4 \
                 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
                 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
                 libxcb-xkb1 libxkbcommon-x11-0

# Fedora
sudo dnf install @development-tools patchelf ccache \
                 mesa-libGL libxkbcommon dbus-libs fontconfig \
                 xcb-util-cursor xcb-util-image xcb-util-keysyms \
                 xcb-util-renderutil xcb-util-wm

# Arch
sudo pacman -S base-devel patchelf ccache \
               libglvnd libxkbcommon dbus fontconfig xcb-util-cursor \
               xcb-util-image xcb-util-keysyms xcb-util-renderutil \
               xcb-util-wm
```

`patchelf` 是 Nuitka standalone 必需的——它用來改 ELF 二進位的 `rpath` 讓產物能找到同目錄的 `.so` 檔。沒裝就會在打包最後一步報錯。

### 1.4 macOS — Xcode 與 clang

```bash
xcode-select --install   # 裝 Command Line Tools
```

Apple Silicon (M1+) 預設就用 arm64 clang。要出 Intel 版的話要另外準備 x86_64 Python，這裡不涵蓋。**注意**：Nuitka 無法在單次編譯同時產出 universal binary——需要 arm64 + x86_64 兩版時，分兩次編完再用 `lipo` 合併。

### 1.5 圖示檔案準備

參考 `pyinstaller.md §1.4` 的圖示轉檔說明。三平台需要：

| 平台 | 檔案 | Nuitka 參數 |
|---|---|---|
| Windows | `exe/Imervue.ico` | `--windows-icon-from-ico=exe\Imervue.ico` |
| Linux | `exe/Imervue.png`（256×256 或 512×512） | `--linux-icon=exe/Imervue.png` |
| macOS | `exe/Imervue.icns` | `--macos-app-icon=exe/Imervue.icns` |

## 2. 打包命令

### 2.1 Windows

> **注意 shell**：下面的 `^` 是 **cmd.exe / `.bat` 檔**的行續字元，**PowerShell 跟 Git Bash 都不認得**。如果你把這段 `^` 版本貼到 PowerShell，Nuitka 會報 `FATAL: Error, file '^' is not found.`——它把 `^` 當成獨立的檔名參數了。對策有三種：
>
> 1. **存成 `.bat` 檔跑**（推薦，見 §3.1）
> 2. **PowerShell**：把所有 `^` 換成反引號 `` ` ``（下面的第二個 code block）
> 3. **一行寫完**，把所有換行跟 `^` 移掉，最無腦、任何 shell 都能用

**cmd / `.bat` 版（用 `^`）**：

```bat
python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --enable-plugin=pyside6 ^
  --python-flag=-m ^
  --include-package=qt_material ^
  --include-package=imageio ^
  --include-package=rawpy ^
  --include-package-data=qt_material ^
  --include-package-data=imageio ^
  --include-package-data=rawpy ^
  --include-data-dir=plugins=plugins ^
  --include-data-dir=exe=exe ^
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md ^
  --include-data-files=LICENSE=LICENSE ^
  --windows-icon-from-ico=exe\Imervue.ico ^
  --output-filename=Imervue.exe ^
  --output-dir=build_nuitka ^
  --remove-output ^
  --assume-yes-for-downloads ^
  Imervue
```

**PowerShell 版（用反引號 `` ` ``）**：

```powershell
python -m nuitka `
  --standalone `
  --windows-console-mode=disable `
  --enable-plugin=pyside6 `
  --python-flag=-m `
  --include-package=qt_material `
  --include-package=imageio `
  --include-package=rawpy `
  --include-package-data=qt_material `
  --include-package-data=imageio `
  --include-package-data=rawpy `
  --include-data-dir=plugins=plugins `
  --include-data-dir=exe=exe `
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md `
  --include-data-files=LICENSE=LICENSE `
  --windows-icon-from-ico=exe\Imervue.ico `
  --output-filename=Imervue.exe `
  --output-dir=build_nuitka `
  --remove-output `
  --assume-yes-for-downloads `
  Imervue
```

**一行版（任何 shell 都能用，最保險）**：

```
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=pyside6 --python-flag=-m --include-package=qt_material --include-package=imageio --include-package=rawpy --include-package-data=qt_material --include-package-data=imageio --include-package-data=rawpy --include-data-dir=plugins=plugins --include-data-dir=exe=exe --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md --include-data-files=LICENSE=LICENSE --windows-icon-from-ico=exe\Imervue.ico --output-filename=Imervue.exe --output-dir=build_nuitka --remove-output --assume-yes-for-downloads Imervue
```

產物：`build_nuitka\Imervue.dist\Imervue.exe`（standalone）或 `build_nuitka\Imervue.exe`（onefile）。

> **為什麼結尾是 `Imervue` 而不是 `Imervue\__main__.py`？** Nuitka 對「含 `__main__.py` 的套件」會跳警告：
> ```
> Nuitka:WARNING: To compile a package with a '__main__' module, specify its
> containing directory but, not the '__main__.py' itself, also consider if
> '--python-flag=-m' should be used.
> ```
> 解法是把套件目錄 `Imervue` 當編譯目標、加 `--python-flag=-m`，等同於 `python -m Imervue` 的語意。順帶一提，輸出資料夾名也會從 `__main__.dist` 變成 `Imervue.dist`，看起來乾淨得多。
>
> **為什麼移除 `--include-data-dir=Imervue\multi_language=...`？** 那個目錄底下全是 `.py`（`english.py`、`japanese.py`、`__init__.py`...），是個正常的 Python 子套件，沒有任何資料檔。Nuitka 看到會跳：
> ```
> Nuitka-Options:WARNING: No data files in directory 'Imervue\multi_language'.
> ```
> 而且這些語言檔早就被 `--include-package=Imervue` 透過靜態 import 分析（`from Imervue.multi_language.chinese import chinese_word_dict` 之類）自動帶進來了，根本不需要再 `--include-data-dir`。

### 2.2 Linux

```bash
python -m nuitka \
  --standalone \
  --disable-console \
  --enable-plugin=pyside6 \
  --python-flag=-m \
  --include-package=qt_material \
  --include-package=imageio \
  --include-package=rawpy \
  --include-package-data=qt_material \
  --include-package-data=imageio \
  --include-package-data=rawpy \
  --include-data-dir=plugins=plugins \
  --include-data-dir=exe=exe \
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md \
  --include-data-files=LICENSE=LICENSE \
  --linux-icon=exe/Imervue.png \
  --output-filename=Imervue \
  --output-dir=build_nuitka \
  --remove-output \
  --assume-yes-for-downloads \
  Imervue
```

產物：`build_nuitka/Imervue.dist/Imervue`。

**發佈格式選擇**（Linux 沒有「單一標準」，看你的客群）：

- **AppImage**（最常見，無需安裝）：用 `appimagetool` 把 `__main__.dist/` 包起來。Nuitka 沒內建 AppImage 產生器，需要手動跑 `linuxdeploy` 或 `appimagetool`。
- **Flatpak / Snap**：社群發行推薦，但需要額外寫 manifest，不在本文件範圍。
- **`.tar.gz` 裸散布**：最簡單，直接把 `__main__.dist/` 打包就好。使用者 `tar xf` 然後執行 `Imervue`。

### 2.3 macOS

```bash
python -m nuitka \
  --standalone \
  --macos-create-app-bundle \
  --enable-plugin=pyside6 \
  --python-flag=-m \
  --include-package=qt_material \
  --include-package=imageio \
  --include-package=rawpy \
  --include-package-data=qt_material \
  --include-package-data=imageio \
  --include-package-data=rawpy \
  --include-data-dir=plugins=plugins \
  --include-data-dir=exe=exe \
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md \
  --include-data-files=LICENSE=LICENSE \
  --macos-app-icon=exe/Imervue.icns \
  --macos-app-name=Imervue \
  --macos-app-version=1.0.0 \
  --macos-signed-app-name=com.imervue.Imervue \
  --output-dir=build_nuitka \
  --remove-output \
  --assume-yes-for-downloads \
  Imervue
```

產物：`build_nuitka/Imervue.app/`。

**簽章與公證（發佈前必做）**：

Nuitka 的 `--macos-sign-identity` 可以直接在編譯時簽章：

```bash
  --macos-sign-identity="Developer ID Application: Your Name (TEAMID)"
```

加上後 Nuitka 會自動對產物跑 `codesign`。但 **notarize（Apple 公證）Nuitka 不會代勞**，要自己跑：

```bash
ditto -c -k --keepParent build_nuitka/Imervue.app Imervue.zip
xcrun notarytool submit Imervue.zip \
      --apple-id you@example.com \
      --team-id TEAMID \
      --password "@keychain:AC_PASSWORD" \
      --wait
xcrun stapler staple build_nuitka/Imervue.app
```

細節跟 PyInstaller 一樣，參考 `pyinstaller.md §2.3`。

### 2.4 命令重點說明（三平台共通）

- `--standalone`：產生可獨立散布的資料夾（不需要目標機器裝 Python）。所有平台一律用這個。
- 隱藏 console：
  - Windows：`--windows-console-mode=disable`
  - Linux：`--disable-console`（實際上 GUI 應用本來就沒 console，這行無害）
  - macOS：`--macos-create-app-bundle`（.app 沒有 console，自動處理）
- `--enable-plugin=pyside6`：啟用 Nuitka 的 PySide6 plugin，自動處理 Qt 的 resource、plugin 目錄、translations。
- 為什麼**沒有** `--include-package=Imervue`：當 `Imervue` 本身就是編譯目標（package-as-entry-point 模式），Nuitka 會自動 walk 整個套件，再加上 `--include-package=Imervue` 反而會跳 `Not allowed to include module 'Imervue.__main__' due to 'Main program is already included in package mode.'` 的警告——它試圖把已經是 entry point 的 `__main__` 再 include 一次。如果哪天 Imervue 內部出現「靜態分析看不到的動態 import」，補單一模組用 `--include-module=Imervue.foo` 即可，不要對整個 `Imervue` 用 `--include-package`。
- `--include-package-data=...`：把 `qt_material`、`imageio`、`rawpy` 的非 `.py` 資源（QSS、entry-point、原生 DLL / `.so` / `.dylib`）一起帶上。
- `--include-data-dir=plugins=plugins`：把整個 `plugins/` 目錄當作**純資料**鏡射進產物。**不要**對 `plugins` 用 `--include-package`——`plugins/` 底下沒有 `__init__.py`，不是 Python 套件；而且每個 plugin 的 `__init__.py` 是以「頂層模組」的方式自我 import（例如 `from ai_background_remover.ai_background_remover import ...`），把它們編譯成 `plugins.xxx` 子模組反而會破壞這條路徑。執行期 `plugin_manager.py` 會把 `<app_dir>/plugins` 插到 `sys.path`，再透過標準 `FileFinder` 從資料夾載入 `.py` 檔，因此 plugin 永遠是走 interpreter 路線，**不經過 Nuitka 的 frozen importer**。這同時也保留了使用者後續從 plugin 下載器新增 / 更新 plugin 的能力（不需要重新編譯整個 app）。
- `--python-flag=-m` + 結尾的 `Imervue`（套件目錄）：對含有 `__main__.py` 的套件，這是 Nuitka 官方推薦寫法，等同於 `python -m Imervue`。直接寫 `Imervue/__main__.py` 會跳警告。
- 為什麼**沒有** `--include-data-dir=Imervue/multi_language=...`：那個目錄底下全是 `.py`（沒有 JSON / qm / po 之類的資料檔），是個正常的 Python 子套件，已經被 `--include-package=Imervue` 透過靜態 import 分析帶進去了。硬加 `--include-data-dir` 會跳「No data files in directory」警告，而且毫無作用。
- 若想要單一檔案發佈，把 `--standalone` 換成 `--onefile`（啟動時會先解壓到 temp dir，啟動較慢；Linux / macOS 的 onefile 支援也比較新，發佈前請充分測試）。

## 3. 推薦的一鍵腳本

### 3.1 Windows — `build_nuitka.bat`

```bat
@echo off
setlocal
call .venv\Scripts\activate
python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --enable-plugin=pyside6 ^
  --python-flag=-m ^
  --include-package=qt_material ^
  --include-package=imageio ^
  --include-package=rawpy ^
  --include-package-data=qt_material ^
  --include-package-data=imageio ^
  --include-package-data=rawpy ^
  --include-data-dir=plugins=plugins ^
  --include-data-dir=exe=exe ^
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md ^
  --include-data-files=LICENSE=LICENSE ^
  --windows-icon-from-ico=exe\Imervue.ico ^
  --output-filename=Imervue.exe ^
  --output-dir=build_nuitka ^
  --remove-output ^
  --assume-yes-for-downloads ^
  Imervue
endlocal
```

### 3.2 Linux / macOS — `build_nuitka.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate

COMMON_ARGS=(
  --standalone
  --enable-plugin=pyside6
  --python-flag=-m
  --include-package=qt_material
  --include-package=imageio
  --include-package=rawpy
  --include-package-data=qt_material
  --include-package-data=imageio
  --include-package-data=rawpy
  --include-data-dir=plugins=plugins
  --include-data-dir=exe=exe
  --include-data-files=THIRD_PARTY_LICENSES.md=THIRD_PARTY_LICENSES.md
  --include-data-files=LICENSE=LICENSE
  --output-dir=build_nuitka
  --remove-output
  --assume-yes-for-downloads
)

case "$(uname -s)" in
  Linux*)
    python -m nuitka \
      "${COMMON_ARGS[@]}" \
      --disable-console \
      --linux-icon=exe/Imervue.png \
      --output-filename=Imervue \
      Imervue
    ;;
  Darwin*)
    python -m nuitka \
      "${COMMON_ARGS[@]}" \
      --macos-create-app-bundle \
      --macos-app-icon=exe/Imervue.icns \
      --macos-app-name=Imervue \
      --macos-app-version=1.0.0 \
      --macos-signed-app-name=com.imervue.Imervue \
      Imervue
    ;;
  *)
    echo "Unsupported OS: $(uname -s)"
    exit 1
    ;;
esac
```

記得 `chmod +x build_nuitka.sh`。

## 4. 常見問題

| 症狀 | 平台 | 解法 |
|---|---|---|
| 執行時噴 `ModuleNotFoundError: <某套件>` | 全平台 | 動態 import 漏掉，補 `--include-package=<套件名>` 或 `--include-module=<模組名>` |
| `qt_material` / 主題 QSS 找不到 | 全平台 | 缺 `--include-package-data=qt_material` |
| RAW 檔解碼失敗（rawpy） | 全平台 | Nuitka 預設不會帶 rawpy 的原生函式庫，必須 `--include-package-data=rawpy` |
| GIF / WEBP 讀不到（imageio） | 全平台 | `--include-package=imageio` 加 `--include-package-data=imageio` |
| OpenGL 初始化失敗 | 全平台 | 用軟體 OpenGL 測試：`Imervue --software_opengl`；檢查 `PyOpenGL` / `PyOpenGL_accelerate` 被 Nuitka 收集到；可加 `--include-package=OpenGL` |
| `KeyError: '__reduce_cython__'`（OpenGL_accelerate） | 全平台 | `PyOpenGL_accelerate` 的 Cython 擴展（`.pyx`）在 Nuitka 打包後無法正常初始化。`__main__.py` 已在偵測到打包環境（`__compiled__` / `sys.frozen`）時自動設定 `OpenGL.USE_ACCELERATE = False`，改用純 Python 的 PyOpenGL。效能影響極小。若未來 Nuitka 或 PyOpenGL_accelerate 修復此相容性問題，可移除該段程式碼以重新啟用 accelerate |
| 打包非常慢 | 全平台 | 正常現象。第一次冷編 10+ 分鐘；`--jobs=<N>` 增加平行度、`ccache`（Linux / macOS）可以讓重編快很多；`--lto=yes` 會更慢但產物更小 |
| 執行檔超大 | 全平台 | `--standalone` 產物 300MB+ 是正常的（Qt + numpy + rawpy）。`--onefile` + `zstandard` 可再壓一些 |
| `FATAL: Error, file '^' is not found.` | Windows | `^` 是 cmd / `.bat` 專用行續字元，你在 PowerShell / Git Bash 跑就會這樣。用 §2.1 的 PowerShell 版（反引號）、一行版，或存成 `.bat` 檔跑 |
| `WARNING: To compile a package with a '__main__' module, specify its containing directory but, not the '__main__.py' itself` | 全平台 | 結尾改成套件目錄 `Imervue`（而不是 `Imervue/__main__.py`），並加 `--python-flag=-m`。見 §2.1 命令範例 |
| `Nuitka-Options:WARNING: No data files in directory 'Imervue\multi_language'.` | 全平台 | 拿掉 `--include-data-dir=Imervue/multi_language=...`。那目錄裡只有 `.py`，不是資料，Nuitka 會透過靜態 import 分析自動帶進去 |
| `Nuitka-Inclusion:WARNING: Not allowed to include module 'Imervue.__main__' due to 'Main program is already included in package mode.'` | 全平台 | 拿掉 `--include-package=Imervue`。當 `Imervue` 本身是編譯目標時，Nuitka 已經自動 walk 整個套件，再 `--include-package=Imervue` 會試著重複 include `__main__` 而觸發此警告 |
| `patchelf not found` | Linux | 裝 `patchelf`（§1.3） |
| `Could not load the Qt platform plugin "xcb"` | Linux | 缺 `libxkbcommon` 或 `xcb-util-cursor` 家族（§1.3） |
| `.app` 無法啟動或跳 crash | macOS | 從 terminal 跑 `./build_nuitka/Imervue.app/Contents/MacOS/Imervue` 看實際錯誤 |
| Gatekeeper 跳「無法驗證開發者」 | macOS | 需要 codesign + notarize（§2.3） |
| Apple Silicon 上簽章完還是被擋 | macOS | 確認加了 `--options runtime`（runtime hardening），沒有的話 notarize 會拒收 |

## 5. 執行期 pip 安裝（plugin 依賴）

Imervue 的 plugin 系統（例如 `ai_background_remover` 需要 `onnxruntime`、`rembg`）會在執行期彈視窗下載缺少的套件，安裝到 **`<app_dir>/lib/site-packages/`**，下次啟動自動加進 `sys.path`。在 Nuitka 打包產物中這條鏈路需要特別留意四件事——**三平台行為一致**，下面寫的規則在 Windows / Linux / macOS 都一樣。

### 5.1 `is_frozen()` 必須偵測到 Nuitka

Nuitka **不會**設 `sys.frozen`，只有 PyInstaller 會。Imervue 的 `Imervue/system/app_paths.py:is_frozen()` 已同時檢查：

```python
getattr(sys, "frozen", False) or "__compiled__" in globals()
```

Nuitka 在每個被編譯的模組 globals 裡都會注入 `__compiled__`，所以這個判斷在 standalone 產物裡會 `True`。如果你改了這個函式、或把 Imervue 的系統模組排除在 `--include-package` 之外（例如用 `--nofollow-import-to=Imervue.system.*`），`is_frozen()` 會退回 `False`，plugin 安裝完的套件**在下次啟動時 import 失敗**。

### 5.2 `lib/site-packages` 要在 `sys.path` 上

`app_paths.py` 在被 import 時會呼叫 `ensure_frozen_site_packages_on_path()`，把 `<app_dir>/lib/site-packages` 插到 `sys.path[0]`。由於 `app_paths` 是 Imervue 最早被載入的模組之一（log 初始化、主視窗、plugin manager 都 import 它），這條路徑在任何 plugin 試圖 import 依賴之前就就緒了。

`<app_dir>` 在三平台的實際位置：

| 平台 | `<app_dir>` |
|---|---|
| Windows standalone | `build_nuitka\Imervue.dist\` |
| Linux standalone | `build_nuitka/Imervue.dist/` |
| macOS `.app` bundle | `Imervue.app/Contents/MacOS/` |

如果你看到「套件已安裝但 import 失敗」，先在程式裡加一行 debug：

```python
from Imervue.system.app_paths import is_frozen, frozen_site_packages
print(is_frozen(), frozen_site_packages(), frozen_site_packages().is_dir())
```

應該要看到 `True <app_dir>/lib/site-packages True`。

### 5.3 含原生函式庫的套件（onnxruntime, torch, opencv）

Nuitka standalone 啟動後 import 這類含 C extension 的套件通常沒問題，因為：

- `lib/site-packages/onnxruntime/` 內部的 `.pyd` / `.so` / `.dylib` 是**在 app 啟動之後**由 pip 放進去的；
- Python 的 `importlib` 會用一般的 FileFinder 從 `sys.path` 找；
- Nuitka 的 frozen importer 只處理編譯時就打包進去的模組，對執行期新增的檔案不會干擾。

但**絕對不要在背景執行緒 import 這類套件**——在 frozen 環境下 onnxruntime 的原生初始化必須在主執行緒跑，否則會直接 segfault。`pip_installer.py:_check_missing_frozen()` 已經特別針對這點改用檔案系統檢查，而不是真的 `import`。plugin 自己寫的 `ensure_dependencies` callback 請務必放在主執行緒。

### 5.4 平台特有的原生函式庫坑

- **macOS**：簽章過的 `.app` bundle 內部若新增未簽章的 `.dylib`（例如 pip 剛裝進去的 onnxruntime），**不會**觸發 Gatekeeper 拒絕——Gatekeeper 只檢查 app 本體的簽章，不檢查執行期寫入的檔案。但如果你啟用了 **Library Validation**（`--options runtime` 加上 `com.apple.security.cs.disable-library-validation` **沒開**），動態載入未簽章的 `.dylib` 會被系統拒絕。entitlements 請務必加：
  ```xml
  <key>com.apple.security.cs.disable-library-validation</key>
  <true/>
  ```
  這是執行期 pip 安裝 plugin 在 macOS 上能 work 的**關鍵**。

- **Linux**：pip 安裝的 `.so` 檔會帶自己的 `rpath`，有時候跟 Nuitka 給 Imervue 本體設的 `rpath` 衝突。遇到 `symbol not found` 類錯誤，先用 `ldd lib/site-packages/onnxruntime/capi/*.so` 看缺什麼，通常是系統層級的 `libstdc++` 版本太舊。

- **Windows**：`.pyd` / `.dll` 載入通常 straightforward，但要注意 plugin 用 `subprocess` 呼叫外部 Python 時，**不要把 `<app_dir>\python_embedded\python.exe` 當成「可以隨便 pip 的 Python」**——embedded Python 的 `._pth` 機制會鎖 `sys.path`，要改的話見 `pip_installer.py:_DownloadPythonWorker` 裡的 `._pth` patch 邏輯。

### 5.5 驗證清單

打包完後請手動跑一次（**三平台都要做**）：

1. 啟動 Imervue，開任一張圖 → 確認基本渲染正常。
2. 進 plugin 選單 → 選一個**帶 pip 依賴**的 plugin（例如 AI 背景移除）。第一次使用會彈「安裝依賴」對話框；點安裝，確認成功。
3. **完全關閉 Imervue**。
4. 重新開啟 Imervue，**不用彈安裝對話框**就能直接用那個 plugin → 代表 `sys.path` 與 `is_frozen()` 都正確。
5. 打開 `<app_dir>/lib/site-packages/` 看一眼，應該有 `onnxruntime/` 等資料夾。

如果第 4 步仍然彈安裝對話框，表示 `ensure_frozen_site_packages_on_path()` 沒在啟動時跑，或 `is_frozen()` 回傳 `False`——回到 5.1、5.2 debug。

## 6. 驗證產物

- **Windows**：`build_nuitka\Imervue.dist\Imervue.exe --debug`
- **Linux**：`./build_nuitka/Imervue.dist/Imervue --debug`
- **macOS**：`./build_nuitka/Imervue.app/Contents/MacOS/Imervue --debug`

至少覆蓋以下情境（三平台都要跑一次）：

1. 開啟一般 PNG / JPEG
2. 開啟 RAW（CR2 / NEF / ARW）——驗證 `rawpy`
3. 播放 GIF / APNG——驗證 `imageio`
4. 切換語言——驗證 `multi_language` 資料夾
5. 載入至少一個 plugin（例如 `plugins/object_splitter`）——驗證 plugin 目錄與其 `models/` 子目錄
6. 新增 / 列出書籤——驗證 `user_setting.json` 讀寫路徑正確
7. 執行期 pip 安裝：跑完第 5 節驗證清單
8. 修改面板（Develop）：調整曝光 / 亮度滑桿——畫布即時預覽，不修改原檔；儲存後才寫入磁碟
9. AI 圖片放大：選擇傳統方法（Lanczos / Bicubic / Nearest）放大，不需安裝 ONNX 依賴即可運作
10. 圖片淨化重繪：選擇傳統放大方法搭配目標解析度，確認輸出圖片尺寸正確且 EXIF 已清除

## 7. PyInstaller vs Nuitka 怎麼選

| 項目 | PyInstaller | Nuitka |
|---|---|---|
| 打包速度 | 快 | 慢（要 C 編譯） |
| 啟動速度 | 普通 | 較快 |
| 產物大小 | 普通 | 略小（尤其開 lto） |
| 反編譯難度 | 低（可還原 .pyc） | 高（真的是 native code） |
| 處理動態匯入 | 經驗豐富、工具成熟 | 需要手動指定 include |
| 跨平台支援 | 成熟（三平台都老牌）| 成熟（三平台都有，但 macOS bundle 是較新加入）|
| 建議用途 | 快速迭代、CI 出 nightly | 發 release、對體積/效能敏感 |

日常開發用 PyInstaller，正式 release 再用 Nuitka 重新打一份即可。CI 裡建議三平台各跑一個 runner（GitHub Actions 的 `windows-latest` / `ubuntu-latest` / `macos-latest` 就夠用），Nuitka 跟 PyInstaller 都不支援交叉編譯，想偷懶省 runner 沒辦法。
