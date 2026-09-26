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
3. **File > Examples > March 7th**（或工具列的 **Examples ▾** 下拉）。內附的 307-drawable Cubism rig 居中載入。
4. 在底部 **Motions** 擺放欄點任一個動作 — rig 立刻動起來。
5. 工具列的 **Reset to rest** 按鈕把 rig 拉回靜止姿勢。

這是基本款。下面解釋怎麼把這個 idle rig 變成直播或影片檔。

---

## Part 1 — OBS 直播整合

目標：在 OBS 上有一個 webcam 風視窗顯示你的 puppet，被你的臉 / 麥克風 / 滑鼠驅動，準備好放進直播。

### 1.1 輸入端（什麼驅動 rig）

Puppet 工具列有 6 個即時輸入 toggle（**Live** 選單也有同樣 6 個），可以同時開（彼此不衝突、只要驅動不同參數）。

| Toggle | 驅動 | 選用依賴 |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`、`ParamEyeBallX/Y` 跟著在 canvas 上移動的滑鼠游標 | 無 |
| **Auto-blink** | `ParamEyeLOpen/ROpen` 每 ~4.5 秒眨一次眼 | 無 |
| **Mic lip-sync** | `ParamMouthOpenY` 跟著麥克風音量、`ParamMouthForm` 跟著母音音色 | `sounddevice` |
| **Webcam tracking** | 臉部 landmark 驅動頭部 yaw/pitch/roll、眼睛開合、視線與嘴巴開合 | `opencv-python` + `mediapipe` |
| **Auto idle** | 呼吸循環 + 頭 / 身體輕微 drift | 無 |
| **Idle motions** | 每 8 秒從 `Idle` 群組隨機播一個動作 | 無 |

典型臉部追蹤 VTuber 設定：開 **Webcam tracking** + **Auto-blink** + **Mic lip-sync**。打開 *Webcam tracking* 時會跳出預覽視窗，顯示攝影機畫面 + 偵測到的 landmark — 用來確認 tracker 真的有看到你。

> **首次使用注意** — webcam tracking 需要 `mediapipe` 的 face-landmark 模型。Imervue 第一次啟用會自動下載（~3.7 MB，從 Google Cloud Storage）到 `<app_dir>/models/face_landmarker.task`，之後直接用快取。

**Output > VTS API** 是另一種輸入：它在 `ws://127.0.0.1:8001`（只限本機）開一個精簡版 VTube Studio Public API 伺服器，支援這個協定的臉部追蹤程式連上後，可以列出 rig 的參數並寫入數值。伺服器會自動發放並接受 token。

### 1.2 輸出端（OBS 怎麼看到 rig）

三條路。新手用 **A**，要 pixel-perfect alpha 合成用 **B**；**C** 完全不用設定。

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

**Loop** 關閉時動作會停在最後一格，**Pause** 會停在當下姿勢，即時輸入也會把參數留在最後寫入的值。點工具列 **Reset to rest**（或 **Edit > Reset to rest**）一鍵歸零：

- Motion player 直接停（不走淡出）
- 所有即時輸入 toggle 取消勾，**Record motion** 也會停止（錄到的 take 會保留）
- Active expressions 清空
- Pose groups 還原第一個 member
- 物理鏈彈回靜止姿勢
- 參數值還原到 authored defaults

狀態列確認：「*Rig reset to neutral pose.*」

---

## Part 2 — 製作動畫

目標：磁碟上有一個 `.mp4` / `.webm` / `.gif` / `.png` 檔。

### 2.1 從即時 take 錄製動作

最簡單的路徑：用臉 / 麥克風 / 滑鼠驅動 rig、即時錄下參數值，Imervue 烘焙成一個之後可以播 / 循環 / 儲存的 `Motion`。

1. 開啟 rig。
2. 啟用想驅動 rig 的即時輸入（webcam / drag / blink / lip-sync / idle），或準備自己拖 **Parameters** 擺放欄的滑桿。
3. **Output > Record motion**。對話框問你動作名稱（預設 `user_motion`），確認後開始錄製。
4. 表演 — 動臉 / 講話 / 移動滑鼠 — 持續多久都可以。
5. 再選一次 **Output > Record motion** 停止錄製。
6. 新動作出現在 **Motions** 擺放欄（跟既有動作同名的 take 會取代它）。加入動作會重新載入 rig，參數、表情跟物理都回到預設值。點它播放，或 **File > Save As…** 把它存進 `.puppet` 檔。

錄製速率 30 Hz。沒變動的軌（整段都不變的參數）自動丟掉。每個保留的軌在每兩個相鄰取樣之間產生一個 linear segment。錄製器讀的是參數本身的值（滑桿、動作、即時輸入），所以表情疊加跟物理輸出不會錄進 take。錄出來的動作不屬於任何群組。

### 2.2 編輯錄好的動作

**Motion Timeline** 對話框可以事後微調動作的關鍵點。

1. 在 **Motions** 擺放欄點動作讓播放器載入它，再選 **Edit > Edit motion…**。
2. 從 **Track** 清單挑一個參數。圖表顯示該軌的關鍵點：X 軸是動作長度內的時間，Y 軸固定是 −1 到 1。
3. 拖黃色的點移動關鍵點的時間跟數值。`cubic-bezier` segment 可以拖紫色控制把手塑形。每個 segment 都畫成兩個關鍵點之間的直線。
4. 對話框不能新增或刪除關鍵點，也不能改 segment 類型；四種類型（`linear`、`stepped`、`inverse-stepped`、`cubic-bezier`）來自動作檔本身。
5. 每次拖曳都會更新記憶體中的動作，並把 canvas 重新擺到播放器目前的時間點。**File > Save As…** 才會把修改寫進 `.puppet` 檔。

### 2.3 手動 keyframe 編輯（不錄 take）

Puppet 分頁沒有建立新動作用的 keyframe 編輯器。不靠即時表演也想做出動作：

1. 打開 **Output > Record motion**，自己拖 **Parameters** 擺放欄的滑桿 — 滑桿變化跟其他即時輸入一樣會被錄下。
2. 停止錄製，再用 **Edit > Edit motion…** 調整關鍵點（見 2.2）。
3. 要精準的 keyframe，就直接手寫 `.puppet` zip 裡的 `motions/<name>.json`，並把名稱加進 `puppet.json` 的 `motions`（見 [`FORMAT.md`](Imervue/puppet/FORMAT.md)）。

每個滑桿旁的 **Set key** 按鈕是綁骨用的工具，不是動作 keyframe：它把每個變形器目前的 form 存成該參數在滑桿目前值的 key。**Edit > Add Parameter** 會新增一個 `ParamN` 滑桿（−1 到 1）供你打 key。

Parameter blends — 在兩個以上參數構成的網格上替變形器 form 打 key，例如用 `ParamAngleX × ParamAngleY` 在 2D 網格上控制頭部方向 — 從 `puppet.json` 的 `parameter_blends` 讀取；Puppet 分頁沒有編輯它的介面。

### 2.4 輸出

| 動作 | 輸出 |
|---|---|
| **Output > Capture frame…** | 把目前 frame 存成透明背景的單張 PNG。適合做縮圖 / 靜態頭像。 |
| **Output > Record…** | 先選 GIF / WebM / MP4 檔，接著用 `imageio` 以 30 fps 寫入影格，直到你再次切換關閉；codec 依副檔名決定。工具列按鈕就是同一個 toggle。 |
| **Output > Export all motions…** | 選資料夾跟容器格式（`.mp4`、`.gif` 或 `.webm`）；每個動作從頭播放並錄滿它的長度，存成 `<motion-name>.<ext>`。適合批次產出反應 clip、idle loop 等。 |

錄影用跟串流一樣的**角色獨立 off-screen render**，所以你不用事後 crop 掉外殼。GIF / WebM / MP4 的影格依文件長寬比縮進長邊 1080 px，背景為白色（這些格式不帶 alpha），每邊取 16 的倍數。PNG 擷取保留文件尺寸，長邊上限 4096 px。

### 2.5 動作配音

一個動作可以攜帶 `sound_path` — 一個 WAV 檔的絕對路徑。動作開始播放時透過 `QSoundEffect` 播一次 WAV；**Pause** 跟 **Stop** 會停止聲音。把 Cubism `.model3.json` 疊加到已開啟的 rig（見*匯入 rig*）時，會從動作項目的 `Sound` 欄位填入；其他動作要編輯 `.puppet` zip 內的 `motions/<name>.json` — Puppet 分頁沒有設定它的欄位。WAV 檔本身不會存進 `.puppet`，檔案不存在時直接略過。

如果沒裝 `PySide6.QtMultimedia`，音訊優雅停用，動作的視覺軌仍然會播。

---

## 匯入 rig

### 從 PNG

**File > Import PNG…** 先詢問網格的格子大小（預設 64 px；越小網格越密），再對影像跑 `auto_mesh`：

- 用正方形格子鋪滿影像，完全透明的格子全部丟掉
- 預先設定 Cubism 標準參數目錄（`ParamAngleX/Y/Z`、`ParamEyeLOpen/ROpen`、`ParamMouthOpenY`、`ParamBreath` …）
- 產生單一 drawable、還沒有變形器的 rig — 從 **Edit** 選單加入變形器

適合：快速 prototype、單張無分層的角色圖。

### 從 PSD

**File > Import PSD…** 把每個可見、非空的圖層變成獨立 drawable — 一個裁到圖層不透明範圍的四邊形，依圖層順序疊放 — 每個圖層群組變成一個 Part。接著預先設定標準參數目錄，再依圖層名稱自動綁骨：

- 名稱含左右與開閉狀態的眼睛圖層（`eye_l_open`、`EyeRClose` …）跟著 `ParamEyeLOpen` / `ParamEyeROpen` 淡入淡出，所以 Auto-blink 會切換它們
- 嘴巴圖層（`mouth_open`、`mouth_close`、`mouth_a` … `mouth_o`）跟著 `ParamMouthOpenY` 跟 `ParamMouthForm` 淡入淡出，所以 Mic lip-sync 會切換它們
- `head` / `face` 圖層共用一個以 `ParamAngleZ` 打 key（±15°）的旋轉變形器
- `hair` / `bang` / `fringe` 圖層共用一個 warp 變形器，外加一條從 `ParamAngleX` 到 `ParamHairFront` 的物理鏈；warp 目前在 `ParamHairFront` 上還沒有 key

其他圖層（身體、手臂、衣服）不會加任何變形器。

適合：美術提供的多圖層角色檔。

### 從 Cubism `.moc3`

**File > Import Cubism…** 會先顯示匯入模式說明（勾 *Don't show this again* 以後就跳過）。它同時接受 `.moc3` 跟對應的 `.model3.json` manifest — 不管選哪個、只要工作區還沒開 rig，匯入器都會跑完整 sample-and-reconstruct 轉換：

1. 透過 Cubism Native SDK 載入 `.moc3`（使用者自備 — 把 SDK 解壓到 `<cwd>/sdk/` 或設 `CUBISM_CORE_DLL` 環境變數指向 DLL）。直接挑 `.moc3` 也可以，只要旁邊有同名 `.model3.json`，工作區會自動找到 manifest。
2. 把每個 Cubism 參數從 min 掃到 max，記錄每個 drawable 的形變頂點。
3. 同時擷取參數驅動的 *visibility* 切換 — 比耶 / 捂臉 / 哭等手勢切換都能完整保留。
4. 把 `.model3.json` bundle 裡既有的 motion / expression / physics / hit-area / display-name 全部 fold 進 puppet。bundle 的 `motions/` 資料夾裡、manifest 沒列到的動作會歸入 `Idle` 群組。

轉換好的 rig 會開在 canvas 上；用 **File > Save As…** 寫成自包含的 `.puppet` zip，不需要附 Cubism SDK 就能散布（SDK 永不打包 — Live2D 的 Free Material License 規定）。

> **疊加到既有 rig**：如果已經開了一個 `.puppet`，這時候挑 `.model3.json` 會把它的 JSON 部分疊到目前文件上：名稱或 id 還不存在的 motions、expressions、physics、hit areas、pose groups，再加上 display names — 適合把 Cubism 動作庫嫁接到自己手繪的 PSD rig。`.moc3` 路徑永遠新建文件；要往既有 rig 加動作，挑 `.model3.json` 或單檔 `.motion3.json` / `.exp3.json` / `.physics3.json` / `.pose3.json` / `.cdi3.json`。

---

## 進階功能

### 參數

每個會動的值都是 *parameter*，有 min、max、default。參數的每個 `key` 存的是某個參數值下的變形器 form；runtime 在目前值兩側的兩個 key 之間線性內插，超出頭尾就維持端點 key。Cubism 標準 id 參考 `Imervue/puppet/standard_params.py`。

### 變形器

- **Rotation** — 錨點 + 角度，套用在變形器自己 `drawables` 清單裡的 drawable。`parent` 只決定順序：父節點先於子節點執行，但父節點的旋轉只移動它自己列出的 drawable，子節點的錨點也不會跟著父節點動。要讓 body lean 帶著 head + arms 一起動，就把它們也列進身體的變形器。
- **Warp** — 蓋在 `bounds` 矩形上的 `rows × cols` 雙線性網格；範圍內的頂點跟著網格走，範圍外的不動。用於臉頰擠壓、衣服皺褶、頭髮擺動。
- **Bone rotation** — `bone_rotation` 變形器（骨頭 id + 錨點 + 角度）替帶有 `bone_weights` 的 drawable 做蒙皮：每個頂點依權重混合各骨頭的旋轉。骨頭之間同樣不會繼承旋轉。
- **Vertex morphs** — Cubism 式每 drawable 的 delta 陣列，在參數預設值跟極值之間做線性混合。`.moc3` 轉換器產生這個。

### Pose groups

互斥的 drawable 可見度。同時只顯示群組裡一個成員：在 **Pose** 擺放欄挑要顯示的成員，其他成員隱藏。用於武器切換、嘴型變體、costume 切換。預設顯示群組的第一個成員；成員本身的 `visible` 旗標不起作用。

### 物理

Verlet pendulum 鏈用於頭髮 / 衣物 / 緞帶。*輸入參數*（例如 `ParamAngleX`）讓鏈錨點橫向移動；重力 + 阻尼 + per-particle 彈簧把鏈拉回靜止；尖端橫向位移映射回 *輸出參數*（例如 `ParamHairFront`），限制在 −1…1。靜止時輸出等於輸入，所以輸入一變化，鏈就會延遲跟上並甩過頭，看起來就是擺動。

Puppet 分頁顯示中且 rig 有物理鏈時，canvas 用自己的時鐘每秒推進約 60 次，所以輸入停下後鏈還會繼續擺。物理鏈的輸出會蓋過滑桿、動作或表情在該參數上的值。**Reset to rest** 會把所有鏈彈回靜止。

物理鏈來自 Cubism 匯入（`.physics3.json`）、PSD 自動綁骨的頭髮規則，或 `.puppet` 檔裡的 `physics.json`；Puppet 分頁沒有物理編輯器。

### 表情

參數覆寫堆疊，疊在滑桿 / 動作值上。模式：`additive`（最終 = base + value）、`multiply`（最終 = base × value）、`overwrite`（最終 = value）。從 **Expressions** 擺放欄切換；啟用中的表情依開啟順序套用。

用於瞬時情緒：*smile*、*surprised*、*angry*。March 7th rig 內附 8 個表情（`捂脸` / `比耶` / `照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`）。

### Hit areas

命名的點擊區域。hit area 的範圍是它所列 drawable 在目前（已變形）位置的外框；在範圍內按左鍵（**Edit mesh** 關閉時）會執行它的動作。它的 `motion` 指定動作群組 — 從該群組隨機播一個動作（`TapHead` 會挑一個 `TapHead` 動作）；沒有動作屬於該群組時，會在 **Motions** 擺放欄選取同名動作並停住，等你按 **Play**。它的 `expression` 會切換該表情（點 body → 切換 `surprised`）。範圍重疊時，含最前面 drawable 的那個勝出。

內附的 March 7th rig 沒有定義任何 hit area，點擊它不會有反應。用 **File > Import Cubism…** 轉換的 rig 會帶入模型的 `HitAreas`，但只有範圍、沒有動作；在 `puppet.json` 的 `hit_areas` 清單替它們加上 `motion` 或 `expression` 才會有反應。Puppet 分頁沒有 hit area 編輯器。

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

切換一個缺少 Python 套件的功能時，會開啟該套件的安裝程式，裝好後自動開啟功能。套件已安裝但裝置或 runtime 失敗（沒有麥克風、沒有虛擬攝影機驅動、沒有 NDI runtime）時，toggle 會自動取消勾，狀態列會說明原因。**File > Install dependencies…** 可以一次裝齊所有 Python 選用包；Cubism SDK 跟 NDI runtime 因為授權需要手動裝。

---

## 鍵盤快捷鍵

Puppet 分頁沒有自己的鍵盤快捷鍵 — 所有指令都在它的選單跟工具列上。Canvas 接受這些滑鼠操作：

| 操作 | 動作 |
|---|---|
| **中鍵拖曳** | 平移 |
| **滑鼠滾輪** | 縮放（以游標為中心）；**Tools > Fit to Window** 重新貼合視窗 |
| **左鍵** | 觸發游標下的 hit area；**Edit mesh** 開啟時改為抓住游標 8 px 內的頂點（最前面的 drawable 優先）拖曳 |
| **右鍵** | 清除 bone 選取 overlay |

---

## 疑難排解

### 「Webcam tracking 開了什麼都沒發生」

預覽視窗會彈出顯示攝影機畫面；如果畫面裡沒有臉，沒有參數會被驅動。預覽視窗的狀態列顯示 *"No face in frame"*。移到鏡頭前或改善光線。

如果預覽是黑的：攝影機被其他 app 佔用、或 OS 拒絕了攝影機存取。macOS 首次使用會要求權限 — 檢查「系統設定 → 隱私權與安全性 → 攝影機」。

### 「OBS 看到洋紅色背景」

設計使然 — 見上面 Path A。在 OBS 的 *Video Capture Device* 來源加 Color Key filter、`Custom Color = #FF00FF`。

### 「ndi-python 安裝失敗、找不到 cmake」

`ndi-python` 從原始碼編。裝 CMake、Visual Studio C++ Build Tools、NDI SDK — 見 Path B 前置。不需要 NDI 的話用 Path A。

### 「動作播完 rig 卡在最後一個姿勢」

Motions 擺放欄的 **Loop** 關閉時，播到結尾的動作會停在最後一格，**Pause** 也會停在當下姿勢。**Stop** 會依動作的淡出時間（動作沒設定時為 0.5 秒）把動作的參數緩緩帶回預設值。工具列的 **Reset to rest** 一次把所有參數、表情、pose group 跟物理鏈還原。

### Cubism 轉換器把相機顯示成「多一隻手」

March 7th 之類 rig 的比耶 / 照相 / 捂臉手勢是用 Cubism 動態可見度旗標驅動的。轉換器把這些切換存成 `opacity_keys` 曲線，所以每個道具只在對應參數拉起時出現。如果轉換出來的 `.puppet` 一直顯示這些道具，代表它的 drawable 缺少這些曲線 — 從 **File > Import Cubism…** 重新轉換並儲存結果。

---

## 檔案格式參考

`.puppet` 是 zip 容器、含 JSON manifest 跟 PNG 紋理。完整規格見 [`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md)。

內附 demo rig：[`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet) 與 [`examples/puppet/vivian.puppet`](examples/puppet/vivian.puppet)（見 [`examples/puppet/README.md`](examples/puppet/README.md)）。
