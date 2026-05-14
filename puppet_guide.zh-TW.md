# Puppet 指南 — 直播與動畫製作

從「我想做 VTuber 風直播或短動畫」走到「我已經在 OBS 上直播 / 我手上有一個 MP4 檔」的完整流程，用 Imervue 的 **Puppet** 分頁完成。

兩條路：

1. **直播** — 用滑鼠 / 麥克風 / 攝影機驅動 puppet rig，把結果送進 OBS 串流或錄影。
2. **動畫製作** — 錄一段 take、編輯動作時間軸、輸出 GIF / MP4 / WebM。

兩者共用同一個 rig 跟參數系統，差別只在輸出端是直播虛擬鏡頭還是磁碟上的檔案。

---

## 目錄

- [快速開始](#快速開始)
- [Part 1 — OBS 直播整合](#part-1--obs-直播整合)
- [Part 2 — 製作動畫](#part-2--製作動畫)
- [匯入 rig](#匯入-rig)
- [進階功能](#進階功能)
- [選用依賴](#選用依賴)
- [鍵盤快捷鍵](#鍵盤快捷鍵)
- [疑難排解](#疑難排解)

---

## 快速開始

1. 啟動 Imervue（從原始碼跑就 `python -m Imervue`）。
2. 點視窗頂端的 **Puppet** 分頁。
3. **File > Examples > March 7Th**（或工具列的 **Examples ▾** 下拉）。內附的 307-drawable Cubism rig 居中載入。
4. 在底部 **Motions** 擺放欄點任一個動作 — rig 立刻動起來。
5. 工具列的 **Reset to rest** 按鈕把 rig 拉回靜止姿勢。

這是基本款。下面解釋怎麼把這個 idle rig 變成直播或影片檔。

---

## Part 1 — OBS 直播整合

目標：在 OBS 上有一個 webcam 風視窗顯示你的 puppet，被你的臉 / 麥克風 / 滑鼠驅動，準備好放進直播。

### 1.1 輸入端（什麼驅動 rig）

Puppet 工具列有 5 個即時輸入 toggle，可以同時開（彼此不衝突、只要驅動不同參數）。

| Toggle | 驅動 | 選用依賴 |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`、`ParamEyeBallX/Y` 跟著滑鼠游標 | 無 |
| **Auto-blink** | `ParamEyeLOpen/ROpen` 每 ~4.5 秒眨一次眼 | 無 |
| **Mic lip-sync** | `ParamMouthOpenY` 跟著麥克風 RMS | `sounddevice` |
| **Webcam tracking** | 臉部 landmark 驅動頭部 yaw/pitch/roll + 眼 / 嘴開合 | `opencv-python` + `mediapipe` |
| **Auto idle** | 呼吸循環 + 頭 / 身體輕微 drift | 無 |
| **Idle motions** | 隨機循環播 Idle 群組的動作 | 無 |

典型臉部追蹤 VTuber 設定：開 **Webcam tracking** + **Auto-blink** + **Mic lip-sync**。打開 *Webcam tracking* 時會跳出預覽視窗，顯示攝影機畫面 + 偵測到的 landmark — 用來確認 tracker 真的有看到你。

> **首次使用注意** — webcam tracking 需要 `mediapipe` 的 face-landmark 模型。Imervue 第一次啟用會自動下載（~3.7 MB，從 Google Cloud Storage）到 `<app_dir>/models/face_landmarker.task`，之後直接用快取。

### 1.2 輸出端（OBS 怎麼看到 rig）

兩條路。新手用 **A**，要 pixel-perfect alpha 合成用 **B**。

#### Path A — Virtual Camera

Puppet canvas 變成 OBS「視訊擷取裝置」來源清單裡的一台 webcam。

```bash
pip install pyvirtualcam
```

加上平台對應的虛擬攝影機驅動：

- **Windows**：裝 OBS Studio 26+，自帶 *OBS Virtual Camera* 驅動。第一次打開 OBS、右下角點 **Start Virtual Camera** 註冊驅動，之後 `pyvirtualcam` 才找得到。
- **macOS**：OBS for Mac 自帶 system extension，首次執行會要求在「系統設定 → 隱私權與安全性」啟用。
- **Linux**：`sudo apt install v4l2loopback-dkms` 然後 `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`。

接線：

1. Puppet 分頁開啟 rig，工具列 / **Output > Virtual camera** 打勾。狀態列會告訴你實際裝置名（通常是 *OBS Virtual Camera*）。
2. OBS：**Sources > + > Video Capture Device**，下拉選步驟 1 印出的裝置名。

**為什麼背景是洋紅色？**

虛擬攝影機走 DirectShow / AVFoundation / v4l2loopback，三個傳輸層**只有 RGB、沒有 alpha 通道**。OBS 把進來的影像當不透明 RGB 處理，所以 Imervue 在角色以外填什麼顏色，OBS 就顯示什麼顏色。挑 `#FF00FF` 是業界標準 chroma-key 色 — 幾乎不會出現在自然膚色 / 髮色 / 瞳色裡，去背容差可以開很寬。

**OBS 端去背：**

1. *Video Capture Device* 來源右鍵 → **Filters**
2. **Effect Filters → + → Color Key**
3. 設定：
   - **Key Color Type**：`Custom Color`
   - **Custom Color**：HEX `FF00FF`
   - **Similarity**：從 `80` 起跳，邊緣有殘留洋紅色就拉到 `200–300`
   - **Smoothness**：`30–50`，邊緣不會太硬
4. 關閉對話框 — 濾鏡會跟著來源，之後重啟虛擬攝影機都自動套用

#### Path B — NDI（專業、真實 alpha）

NDI 在 LAN 上以 < 50 ms 延遲傳 RGBA。不用色鍵 — alpha 通道整條傳過去。

```bash
pip install ndi-python
```

加上：

1. 從 <https://ndi.video/tools/> 下載 **NDI Tools** — installer 包含 runtime DLL，`ndi-python` 會 link 進去。
2. OBS 端裝 **obs-ndi** 插件：<https://github.com/obs-ndi/obs-ndi/releases>

接線：

1. Puppet 分頁工具列 / **Output > NDI output** 打勾。狀態列顯示來源名（預設 *Imervue Puppet*）。
2. OBS：**Sources > + > NDI Source**，下拉選步驟 1 的來源名。

角色直接合成到 OBS 場景，零色鍵濾鏡。Off-screen render 把角色外的區域填成完全透明。

**`ndi-python` Windows 編譯前置**

`ndi-python` 只 ship source distribution，pip 拿到後從 C++ 編。Windows 上要：

- **Visual Studio Build Tools 2022** 勾「**使用 C++ 的桌面開發**」工作負載
- **CMake**（安裝時勾 *Add to system PATH*）
- **NDI SDK**（跟 NDI Tools 不同，去 <https://ndi.video/for-developers/ndi-sdk/> 抓）裝在預設 `C:\Program Files\NDI\NDI 6 SDK\`
- 環境變數 `NDI_SDK_DIR` 指向 SDK 安裝路徑

嫌麻煩就走 Path A。

#### Path C — Window Capture（零安裝）

OBS **Sources > + > Window Capture** 可以直接抓 Imervue 視窗。沒有虛擬攝影機驅動、沒有 SDK。Trade-off：

- 抓整個 Imervue 視窗（含外殼），要加 OBS *Crop/Pad* filter 裁到只剩 puppet 區。
- Puppet 工作區的棋盤格背景也會跟著串。
- 受 Imervue 視窗大小限制。

只適合臨時 demo。要正式直播用 A 或 B。

### 1.3 角色獨立渲染路徑

Virtual Camera 與 NDI 都用 off-screen framebuffer 重畫，**不含棋盤格背景跟任何編輯器外殼**。Imervue 視窗裡的工具列 / 擺放欄 / 狀態列純粹是給你編輯用的，串流只有角色 drawable 本身。輸出長邊上限 1080 px（避免 3503×7777 的 Cubism canvas 把 DirectShow 驅動搞掛）。

### 1.4 兩段 take 之間重置

動作結束（或中途暫停）後 rig 會停在最後一個取樣姿勢。點工具列 **Reset to rest**（或 **Edit > Reset to rest**）一鍵歸零：

- Motion player 直接停（不走淡出）
- 所有即時輸入 toggle 取消勾
- Active expressions 清空
- Pose groups 還原第一個 member
- 參數值還原到 authored defaults

狀態列確認：「*Rig reset to neutral pose.*」

---

## Part 2 — 製作動畫

目標：磁碟上有一個 `.mp4` / `.webm` / `.gif` / `.png` 檔。

### 2.1 從即時 take 錄製動作

最簡單的路徑：用臉 / 麥克風 / 滑鼠驅動 rig、即時錄下參數值，Imervue 烘焙成一個之後可以播 / 循環 / 儲存的 `Motion`。

1. 開啟 rig。
2. 啟用想驅動 rig 的即時輸入（webcam / drag / blink / lip-sync / idle）。
3. **Output > Record motion** — 工具列按鈕打勾。
4. 表演 — 動臉 / 講話 / 拖滑鼠 — 持續多久都可以。
5. **Record motion** 取消勾。對話框問你動作名稱跟可選的群組標籤（例如 *"wave"*、*"Idle"*）。
6. 新動作出現在 **Motions** 擺放欄。點它播放，或 **File > Save As…** 把它存進 `.puppet` 檔。

錄製速率 30 Hz。沒變動的軌（整段都不變的參數）自動丟掉，檔案大小不會爆。每個保留的軌每個參數變動產生一個 linear segment。

### 2.2 編輯錄好的動作

**Motion Timeline** 對話框可以事後微調已錄製的動作。

1. Motions 擺放欄右鍵動作 → **Edit timeline…**（或 double-click）。
2. 對話框每個參數軌一條曲線。Y 軸是參數值範圍，X 軸是時間。
3. 點關鍵點選取。拖曳移動。右鍵 *delete* / *insert key* / *change segment type*。
4. 支援的 segment 類型：`linear`、`stepped`、`inverse-stepped`、`cubic-bezier`（拖控制點塑形）。
5. 用時間軸 transport（play / loop / scrub）即時預覽。

提示：臉部動作自然感的話，`ParamEyeLOpen/ROpen`（眨眼）跟 `ParamMouthOpenY`（說話）用 cubic-bezier 比較好，其他用 linear 就夠了。

### 2.3 手動 keyframe 編輯（不錄 take）

如果你心裡有特定的 keyframe 序列：

1. **Edit > Add Parameter** 加入需要的新參數。
2. **Parameters** 擺放欄拖滑桿到 t=0 時的值 → 按 **Set Key**。Imervue 在 t=0 標記目前參數快照。
3. 在 t=1.0、t=2.0… 重複。
4. Recipe 串接 Motion Timeline 對話框 — 右鍵 → **New motion** 從你已 author 的 key 開始建新動作。

跨多參數的姿勢，parameter-blends 功能可以把一個輸入綁到 N 維 keyframe（例如 `ParamAngleX × ParamAngleY` 控制 2D 網格上的頭部方向）。

### 2.4 輸出

| 動作 | 輸出 |
|---|---|
| **Output > Capture frame…** | 用 `glReadPixels` 存目前 frame 成單張 PNG。適合做縮圖 / 靜態頭像。 |
| **Output > Record…** | 用 `imageio` 把影格序列寫成 GIF / WebM / MP4。工具列按鈕是 toggle：開始 → 表演 → 結束 → 寫檔。預設 30 fps；codec 從副檔名挑。 |
| **Output > Export all motions…** | 把 rig 裡每個動作各別 render 成一個檔（例如 `<motion-name>.mp4`）。適合批次產出反應 clip、idle loop 等。 |

錄影用跟串流一樣的**角色獨立 off-screen render**，所以你不用事後 crop 掉外殼。GIF / WebM / MP4 預設用文件長寬比、長邊上限 1080。PNG 單幀保留文件原生尺寸。

### 2.5 動作配音

一個動作可以攜帶 `sound_path` — 一個 WAV 檔的絕對路徑。動作播放時透過 `QSoundEffect` 同步播 WAV。手動在 Motion Timeline 對話框設定，或編輯 `.puppet` zip 內的 `motions/<name>.json`；v1 沒有 GUI 設定這個。

如果沒裝 `PySide6.QtMultimedia`，音訊優雅停用，動作的視覺軌仍然會播。

---

## 匯入 rig

### 從 PNG

**File > Import PNG…** 對影像跑 `auto_mesh`：

- 三角化時尊重 alpha 通道 — 邊緣不會有白邊
- 預先設定 Cubism 標準參數目錄（`ParamAngleX/Y/Z`、`ParamEyeLOpen/ROpen`、`ParamMouthOpenY`、`ParamBreath` …）
- 產生單一 drawable 的 rig，之後可以分割 / 變形

適合：快速 prototype、單張無分層的角色圖。

### 從 PSD

**File > Import PSD…** 把每個 PSD 圖層 parse 成獨立 drawable。圖層名符合 Live2D 慣例（`Head`、`Body`、`HairFront` 等）自動綁到標準 deformer。

適合：美術提供的多圖層角色檔。

### 從 Cubism `.moc3`

**File > Import Cubism…** 同時接受 `.moc3` 跟對應的 `.model3.json` manifest — 不管選哪個、只要工作區還沒開 rig，匯入器都會跑完整 sample-and-reconstruct 轉換：

1. 透過 Cubism Native SDK 載入 `.moc3`（使用者自備 — 把 SDK 解壓到 `<cwd>/sdk/` 或設 `CUBISM_CORE_DLL` 環境變數指向 DLL）。直接挑 `.moc3` 也可以，只要旁邊有同名 `.model3.json`，工作區會自動找到 manifest。
2. 把每個 Cubism 參數從 min 掃到 max，記錄每個 drawable 的形變頂點。
3. 同時擷取參數驅動的 *visibility* 切換 — 比耶 / 捂臉 / 哭等手勢切換都能完整保留。
4. 把 `.model3.json` bundle 裡既有的 motion / expression / physics / hit-area 全部 fold 進 puppet。

輸出：自包含的 `.puppet` zip，不需要附 Cubism SDK 就能散布（SDK 永不打包 — Live2D 的 Free Material License 規定）。

> **疊加到既有 rig**：如果已經開了一個 `.puppet`，這時候挑 `.model3.json` 會把它的 JSON 部分（motions、expressions、physics、hit areas、display names）疊上去 — 適合把 Cubism 動作庫嫁接到自己手繪的 PSD rig。`.moc3` 路徑永遠新建文件；要往既有 rig 加動作，挑 `.model3.json` 或單檔 `.motion3.json` / `.exp3.json`。

---

## 進階功能

### 參數

每個會動的值都是 *parameter*，有 min、max、default。參數帶 `keys`（單一值快照），runtime 線性取樣。Cubism 標準 id 參考 `Imervue/puppet/standard_params.py`。

### 變形器

- **Rotation** — 錨點 + 角度。子節點繼承父節點旋轉，所以 body lean 會帶著 head + arms 一起動。
- **Warp** — `rows × cols` bezier lattice。用於臉頰擠壓、衣服皺褶、頭髮物理。
- **Vertex morphs** — Cubism 式每 drawable 的 delta 陣列，在參數預設值跟極值之間做線性混合。`.moc3` 轉換器產生這個。

### Pose groups

互斥的 drawable 可見度。同時只顯示群組裡一個成員；切到別的隱藏其他。用於武器切換、嘴型變體、costume 切換。

### 物理

Verlet pendulum 鏈用於頭髮 / 衣物 / 緞帶。*輸入參數*（例如 `ParamAngleX`）移動鏈錨點；重力 + 阻尼 + per-particle 彈簧把鏈拉回靜止；尖端橫向位移映射回 *輸出參數*（例如 `ParamHairFront`）。

從 Bone Tree 擺放欄編輯物理鏈。

### 表情

參數覆寫堆疊，疊在滑桿 / 動作值上。模式：`additive`（最終 = base + value）、`multiply`（最終 = base × value）、`overwrite`（最終 = value）。

用於瞬時情緒：*smile*、*surprised*、*angry*。March 7th rig 內附 8 個表情（`捂脸` / `比耶` / `照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`）。

### Hit areas

rig 上的命名區域，使用者點擊內部會發出信號。可綁到動作群組（`TapHead → tap_head` 從 `TapHead` 群組隨機播一個動作），或綁到表情切換（點 body → 切換 `surprised`）。

March 7th rig 有兩個 hit area — `head` 觸發 `tap_head` 動作、`body` 切換 `surprised` 表情。

---

## 選用依賴

Puppet 分頁的核心（渲染、參數系統、動作播放、PNG / PSD / Cubism 匯入）跑在預設 `requirements.txt` 上。更重的依賴用 `try / except` 包起來，缺了也不會壞其他功能。

| 功能 | 選用依賴 | 安裝 |
|---|---|---|
| Webcam 臉部追蹤 | `opencv-python` + `mediapipe` | `pip install opencv-python mediapipe` |
| 麥克風對嘴 | `sounddevice` | `pip install sounddevice` |
| 虛擬攝影機輸出 | `pyvirtualcam` + 平台驅動 | `pip install pyvirtualcam`，見上面 Path A |
| NDI 輸出 | `ndi-python` + NDI runtime + NDI SDK（編譯時用） | 見上面 Path B |
| Cubism `.moc3` 匯入 | 使用者自備 Cubism Native SDK DLL | <https://www.live2d.com/sdk/about/> |
| 動作音訊播放 | `PySide6.QtMultimedia` | 通常跟著 PySide6；缺的話從平台的 QtMultimedia 包補 |

切到不可用的功能時工具列 / 狀態列會回報哪個依賴缺。**File > Install dependencies…** 可以一次裝齊所有 Python 選用包；Cubism SDK 跟 NDI runtime 因為授權需要手動裝。

---

## 鍵盤快捷鍵

只列 Puppet 分頁特有的。完整快捷鍵參考 `README.md`。

| 快捷鍵 | 動作 |
|---|---|
| Canvas 上 **滑鼠拖曳** | 平移（drag-track 關掉時） |
| **滑鼠滾輪** | 縮放（以游標為中心） |
| Canvas 上 **右鍵** | 清除 bone 選取 overlay |
| **E** | 切換 Edit Mesh 模式（之後拖頂點編輯 mesh） |
| **B** | 切換 Auto-blink |
| **W** | 切換 Webcam tracking |
| **M** | 切換 Mic lip-sync |
| **D** | 切換 Drag-track |
| **I** | 切換 Auto-idle |
| **Space** | 播放 / 暫停選取的動作 |
| **Esc** | 停止目前動作（淡出） |
| **Ctrl+R** | Reset to rest |

（部分快捷鍵將來可能變動 — 工具列按鈕才是權威介面。）

---

## 疑難排解

### 「Webcam tracking 開了什麼都沒發生」

預覽視窗會彈出顯示攝影機畫面；如果畫面裡沒有臉，沒有參數會被驅動。狀態列顯示 *"No face in frame"*。移到鏡頭前或改善光線。

如果預覽是黑的：攝影機被其他 app 佔用、或 OS 拒絕了攝影機存取。macOS 首次使用會要求權限 — 檢查「系統設定 → 隱私權與安全性 → 攝影機」。

### 「Auto-blink 只眨了一次」

最近 commit 修了 — blink 改用 force-write 路徑、繞過 canvas 的 no-change-skip 優化。更新到最新版。

### 「OBS 看到洋紅色背景」

設計使然 — 見上面 Path A。在 OBS 的 *Video Capture Device* 來源加 Color Key filter、`Custom Color = #FF00FF`。

### 「ndi-python 安裝失敗、找不到 cmake」

`ndi-python` 從原始碼編。裝 CMake、Visual Studio C++ Build Tools、NDI SDK — 見 Path B 前置。不需要 NDI 的話用 Path A。

### 「虛擬攝影機畫面看起來被拉長」

最近 commit 修了 — 輸出改用文件長寬比、純角色內容。更新到最新版。

### 「動作播完 rig 卡在最後一個姿勢」

點工具列 **Reset to rest**。動作停止不會自動倒帶 — 停在最後取樣值。Reset 給你乾淨基準。

### Cubism 轉換器把相機顯示成「多一隻手」

March 7th 之類 rig 的比耶 / 照相 / 捂臉手勢是用 Cubism 動態可見度旗標驅動的。最近 commit 教轉換器把這些切換存成 `opacity_keys` 曲線。如果你之前用舊版轉過 `.moc3`，從 **File > Import Cubism…** 重新轉一次，新 `.puppet` 就有正確的手勢切換。

---

## 檔案格式參考

`.puppet` 是 zip 容器、含 JSON manifest 跟 PNG 紋理。完整規格見 [`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md)。

內附 demo rig：[`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet)。
