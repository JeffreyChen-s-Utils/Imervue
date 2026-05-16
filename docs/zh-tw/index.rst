Imervue 使用手冊
================

GPU 加速影像工作站，提供 **四個頂層分頁**。本手冊大部分內容圍繞這四個分頁組織。

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - 分頁
     - 功能
   * - **Imervue**
     - 瀏覽、檢視、整理、搜尋、批次處理圖庫。見「Imervue 分頁 — 圖片瀏覽與圖庫」。
   * - **Modify**
     - 非破壞顯影管線 — 滑桿、曲線、LUT、遮罩、修圖、多影像合成。見「Modify 分頁 — 非破壞顯影」。
   * - **Paint**
     - 本格的なラスター描画 風格的點陣繪圖工作室，含筆刷、圖層、動畫、漫畫工具、PSD I/O。見「Paint 分頁 — 本格的なラスター描画 風格繪圖」。
   * - **Puppet**
     - 從零打造的 2D 綁骨偶動畫器 — 網格、變形器、參數、動作、物理。見「Puppet 分頁 — 2D 綁骨偶動畫」。

接下來的「快速開始」、「參考」、「外掛系統」、「MCP 伺服器」屬於跨分頁的章節，所有分頁通用。

.. contents:: 目錄
   :depth: 2
   :local:

----

快速開始
--------

打開 Imervue 後，你會看到三個區域：

::

   ┌──────────┬──────────────────────┬──────────┐
   │  資料夾  │                      │  EXIF    │
   │  樹狀圖  │     圖片瀏覽區       │  資訊欄  │
   │          │                      │          │
   └──────────┴──────────────────────┴──────────┘

- **左邊**：資料夾目錄，點選資料夾就能瀏覽裡面的圖片
- **中間**：圖片顯示區，會以縮圖網格展示所有圖片
- **右邊**：EXIF 資訊欄，顯示圖片的拍攝資訊

----

開啟圖片
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 方法
     - 操作
   * - 開啟資料夾
     - ``檔案`` > ``開啟資料夾``，選擇你要瀏覽的目錄
   * - 開啟單張圖片
     - ``檔案`` > ``開啟圖片``，選擇一張圖片
   * - 拖曳開啟
     - 直接把圖片或資料夾拖進視窗
   * - 從檔案總管開啟
     - 右鍵圖片 > ``Open with Imervue``（需先註冊檔案關聯）
   * - 最近開啟
     - ``檔案`` > ``最近開啟``，快速回到之前看過的資料夾

支援的圖片格式
^^^^^^^^^^^^^^

- **常見格式**：PNG、JPEG、BMP、TIFF、WebP、GIF、APNG、SVG
- **RAW 格式**：CR2（Canon）、NEF（Nikon）、ARW（Sony）、DNG（Adobe）、RAF（Fujifilm）、ORF（Olympus）

----

瀏覽圖片
--------

縮圖網格模式
^^^^^^^^^^^^

開啟資料夾後，所有圖片會以縮圖網格排列。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 瀏覽圖片
     - 滑鼠滾輪上下捲動
   * - 移動畫面
     - 按住滑鼠中鍵拖曳
   * - 進入大圖模式
     - 左鍵點擊任一張縮圖
   * - 調整縮圖大小
     - 上方選單 ``縮圖大小`` > 選擇 128 / 256 / 512 / 1024
   * - 縮圖排列密度
     - ``縮圖大小`` > ``縮圖排列密度`` > 緊湊 / 標準 / 寬鬆
   * - Hover 預覽彈窗
     - 滑鼠懸停縮圖 500 ms 顯示放大預覽
   * - 框選多張圖片
     - 左鍵拖曳框選
   * - 方向鍵移動
     - ``↑`` ``↓`` ``←`` ``→`` 平移畫面，按住 ``Shift`` 可微調

縮圖會顯示狀態徽章：左緣色條（色彩標籤）、左上 ❤（最愛）、右上 ★（書籤）、左下評分星。
尚未載入完成的縮圖以旋轉點陣占位符顯示。

清單（詳細）模式
^^^^^^^^^^^^^^^^

按 ``Ctrl + L`` 可在縮圖格與可排序的清單檢視之間切換，欄位為：預覽 · 標籤 · 名稱 · 解析度 · 大小 · 類型 · 修改時間 · 星等評分（可直接點擊設定 0 – 5 星）。
雙擊列（或按 ``Enter``）進入大圖模式；按 ``Esc`` 回到清單。縮圖與元資料在背景執行緒惰性載入，
面對大型資料夾仍保持流暢。

大圖模式（Deep Zoom）
^^^^^^^^^^^^^^^^^^^^^

點擊縮圖後進入大圖模式，可以高畫質瀏覽單張圖片。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 放大／縮小
     - 滑鼠滾輪、或觸控板捏合
   * - 拖曳平移
     - 按住滑鼠中鍵
   * - 上一張圖
     - ``←`` 左方向鍵（或觸控板向右滑）
   * - 下一張圖
     - ``→`` 右方向鍵（或觸控板向左滑）
   * - 跨資料夾跳轉
     - ``Ctrl + Shift + ←`` / ``→`` 跳至前／下一個含圖片的兄弟資料夾
   * - 瀏覽歷史
     - ``Alt + ←`` 返回、``Alt + →`` 前進（類似瀏覽器）
   * - 依編號跳轉
     - ``Ctrl + G``
   * - 隨機圖片
     - ``X``
   * - 適應寬度
     - 按 ``W``
   * - 適應高度
     - 按 ``Shift + W``
   * - 重設縮放
     - 按 ``Home``
   * - 回到縮圖模式
     - 按 ``Esc``
   * - 全螢幕
     - 按 ``F``，再按一次退出
   * - 劇場模式
     - ``Shift + Tab`` 隱藏所有選單／狀態列／樹狀圖
   * - OSD 資訊疊加
     - ``F8`` 顯示檔名／尺寸／類型；``Ctrl + F8`` 顯示 Debug HUD（VRAM／快取／執行緒）
   * - 像素檢視
     - ``Shift + P``：縮放 ≥ 400 % 顯示像素網格與游標下 RGB／HEX
   * - 色彩模式
     - ``Shift + M`` 循環 正常／灰階／反相／懷舊（GLSL，非破壞性）

分割檢視與雙頁閱讀
^^^^^^^^^^^^^^^^^^

不需開啟 Compare Dialog 也能並排顯示兩張：

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 操作
     - 快捷鍵
   * - 分割檢視（任意兩張並排）
     - ``Shift + S``
   * - 雙頁閱讀（當前 + 下一張）
     - ``Shift + D``
   * - 雙頁閱讀（右至左，漫畫用）
     - ``Ctrl + Shift + D``
   * - 返回先前模式
     - ``Esc``

在雙頁模式下，方向鍵一次前進兩張。RTL 變體會交換左右面板，讓第 1 頁顯示在右側。

多螢幕視窗
^^^^^^^^^^

按 ``Ctrl + Shift + M`` 會在副螢幕開啟一個無邊框的第二視窗，鏡像顯示主 viewer 當前的圖片。
主視窗可以繼續獨立瀏覽——適合展覽、雙螢幕修圖流程、客戶簡報。再按一次 ``Ctrl + Shift + M`` 關閉，
或在第二視窗內按 ``Esc``。

----

整理圖片
--------

評分與最愛
^^^^^^^^^^

在大圖模式下，可以快速幫圖片打分數：

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 按鍵
   * - 加入最愛 ❤
     - ``0``
   * - 評 1～5 星
     - ``1`` ``2`` ``3`` ``4`` ``5``（再按一次取消）

色彩標籤 (F1 -- F5)
^^^^^^^^^^^^^^^^^^^

獨立於星等之外的 旗標式色彩 flag，適合快速分類（例如：紅=刪除候補、綠=精選、藍=待修）。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 按鍵
   * - 紅 / 黃 / 綠 / 藍 / 紫
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5``（再按同一鍵清除）
   * - 批次套用到選取
     - 框選多張縮圖後按對應 F 鍵
   * - 依色彩篩選
     - ``篩選`` > ``依色彩標籤`` > 選擇顏色／任一色／無標籤

狀態列會顯示目前圖片的色彩 chip；縮圖左邊緣顯示對應色條；**清單模式**有獨立的「標籤」與「星等」欄可排序，星等欄可直接點擊設定 0 – 5 星。

書籤
^^^^

把常用的圖片加入書籤，方便日後快速找到。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 加入／取消書籤
     - 大圖模式下按 ``B``
   * - 管理書籤
     - ``檔案`` > ``書籤``

標籤與相簿
^^^^^^^^^^

用標籤和相簿分類管理你的圖片。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 開啟管理介面
     - 按 ``T`` 或 ``檔案`` > ``標籤與相簿``
   * - 幫圖片加標籤
     - 右鍵圖片 > ``加入標籤``
   * - 加入相簿
     - 右鍵圖片 > ``加入相簿``
   * - 依單一標籤／相簿篩選
     - ``篩選`` > ``依標籤`` / ``依相簿``
   * - 多標籤過濾 (AND / OR)
     - ``篩選`` > ``多標籤過濾…`` — 勾選多個標籤或相簿，選擇「任一 (OR)」或「全部 (AND)」

排序與篩選
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 功能
     - 選單位置
   * - 依名稱排序
     - ``排序`` > ``依名稱``
   * - 依修改日期排序
     - ``排序`` > ``依修改日期``
   * - 依檔案大小排序
     - ``排序`` > ``依檔案大小``
   * - 依解析度排序
     - ``排序`` > ``依解析度``
   * - 升冪／降冪
     - ``排序`` > ``升冪`` / ``降冪``
   * - 依副檔名篩選
     - ``篩選`` > ``JPEG`` / ``PNG`` / ``RAW`` 等
   * - 依評分篩選
     - ``篩選`` > ``依評分``
   * - 依色彩標籤篩選
     - ``篩選`` > ``依色彩標籤``（全部／任一色／無標籤／紅／黃／綠／藍／紫）
   * - 進階過濾
     - ``篩選`` > ``進階過濾…`` — 解析度範圍、檔案大小範圍、方向（橫／直／正方）、修改日期區間
   * - 清除篩選
     - ``篩選`` > ``清除篩選``

瀏覽模式（縮圖格 / 清單）
^^^^^^^^^^^^^^^^^^^^^^^^^

切換圖片瀏覽器在縮圖格與可排序的詳細清單之間：

- ``Ctrl + L`` — 切換 縮圖格 ↔ 清單
- 選單：``縮圖大小`` > ``瀏覽模式`` > 縮圖格 / 清單
- 清單模式下任一欄（包含「標籤」）皆可排序；雙擊列或按 ``Enter`` 開啟大圖模式。

----

編輯圖片（修改分頁）
--------------------

切換到上方的 **「修改」** 分頁，就能進入編輯模式。也可以在大圖模式下按 ``E`` 或右鍵 > ``修改`` 進入。

::

   ┌────────┬──────────────────────┬────────────┐
   │  工具  │                      │  繪圖屬性  │
   │  列    │   畫布（直接繪圖）    │  調色、筆刷 │
   │        │                      │  曝光調整  │
   └────────┴──────────────────────┴────────────┘

標註工具（左邊）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - 工具
     - 圖示
     - 說明
   * - 選取
     - ⬚
     - 選取已畫的標註，可拖曳移動
   * - 矩形
     - ▢
     - 畫矩形框
   * - 橢圓
     - ◯
     - 畫橢圓或圓形
   * - 直線
     - ╱
     - 畫直線
   * - 箭頭
     - →
     - 畫箭頭
   * - 手繪
     - ✎
     - 自由手繪線條
   * - 文字
     - T
     - 在圖上加文字
   * - 馬賽克
     - ▦
     - 框選區域打馬賽克
   * - 模糊
     - ◌
     - 框選區域加模糊

.. tip::
   在修改分頁中按 ``←`` ``→`` 可以切換上一張／下一張圖片。

筆刷類型（右邊）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 筆刷
     - 效果
   * - 鋼筆
     - 標準細線，最常用
   * - 麥克筆
     - 較粗、半透明的筆觸
   * - 鉛筆
     - 細淡的線條
   * - 螢光筆
     - 寬大、高透明度，像真的螢光筆
   * - 噴霧
     - 噴點效果
   * - 書法
     - 粗細隨筆劃方向變化
   * - 水彩
     - 柔和暈染效果
   * - 炭筆
     - 粗糙質感筆觸
   * - 蠟筆
     - 蠟質手感

繪圖屬性（右邊）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 屬性
     - 說明
   * - 顏色
     - 點擊色塊選擇繪圖顏色
   * - 線寬
     - 拖動滑桿調整筆觸粗細（1～40）
   * - 不透明度
     - 調整透明度（0%～100%）
   * - 字型
     - 選擇文字工具使用的字型
   * - 字型大小
     - 調整文字大小（6～200 px）

影像調整（右邊下方）
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 滑桿
     - 功能
   * - 曝光
     - 調整整體亮度
   * - 亮度
     - 微調明暗
   * - 對比
     - 調整明暗對比
   * - 飽和度
     - 調整色彩鮮豔程度
   * - 白平衡 — 色溫
     - 冷暖偏移（藍 ↔ 黃）；適合混合光源或室內照片
   * - 白平衡 — 色調
     - 洋紅 / 綠偏移；修正日光燈偏色
   * - 陰影
     - 提亮或壓暗暗部細節
   * - 中間調
     - 調整中間色調，不影響純黑與純白
   * - 高光
     - 救回過曝或進一步推亮
   * - 鮮豔度 (Vibrance)
     - 飽和度感知提升 — 保護膚色與已飽和色彩

這些調整是 **非破壞性** 的：每個滑桿皆寫入 per-image 的 Edit Recipe，隨時可以按 ``重設`` 或
``Ctrl + Z`` 逐步還原。Recipe 會在重啟後保留，也可透過 XMP sidecar 匯出 / 同步（見中繼資料一節）。

儲存與復原
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - 按鈕
     - 說明
   * - 儲存
     - 將標註和調整寫入原始檔案
   * - 復原
     - 取消上一步操作
   * - 重做
     - 重做已復原的操作
   * - 重設
     - 清除所有影像調整

----

繪圖工作區（繪圖分頁）
----------------------

第三個頂層分頁 — **繪圖** — 是 本格的なラスター描画 風格的繪圖工作區，支援多分頁文件、
向量與點陣圖層、漫畫工具、動畫影格，以及 PSD 匯入/匯出。從分頁列切換進入，
或在大圖模式下按 ``E`` 將目前圖片送入新繪圖分頁。

UX 體質升級：本格的なラスター描画 風格、會跟著 zoom 縮放的筆刷大小游標、每個工具獨立
的游標圖示、畫布底層的透明格紋、拖放高亮覆蓋、每個 tab 的「已修改」星號、
undo / redo toast 確認、status bar 的 autosave 狀態段、開啟時自動偵測前次
session 的 autosave 並提示還原。

進階快捷鍵：``Tab`` 一鍵隱藏 / 還原所有 docks 進入專心模式、``Ctrl+Tab``
切換分頁、``,`` / ``.`` 循環筆刷種類、``0–9`` 數字鍵以 10 % 為單位設定
不透明度、``Alt+[`` / ``Alt+]`` 切換 active 圖層、畫布右鍵彈出 Undo /
Redo / Select All / Deselect / Fit / 100 % 快捷選單。

顏色 dock 加入「透明 / 無顏色」槽（背景預設為透明），fill 與魔棒會尊重
alpha 邊界，擦除過後不再有殘留 RGB 污染重畫的軟邊。

::

   +------+----------------------+----------------+
   | 工具 |                      | 顏色 · 筆刷    |
   | 列   |    畫布（繪圖）       | 圖層 · 縮覽    |
   |      |                      | 素材 · …       |
   +------+----------------------+----------------+

右側面板（顏色、筆刷、圖層、縮覽圖、素材庫、歷史、色票、參考、直方圖、動畫）
全部分頁化進同一欄位，畫布因此能保留完整可見高度。拖曳任何 dock 的標題列
可重新排列或浮動，再透過 ``設定`` > ``工作區排版…`` 儲存命名後的版面。

工具列（左側）
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - 工具
     - 快速鍵
     - 用途
   * - 筆刷
     - ``B``
     - 以目前筆刷類型繪畫
   * - 橡皮擦
     - ``E``
     - 對作用中圖層做透明度擦除
   * - 油漆桶
     - ``G``
     - 容差 / 連續區域 / 取樣全部圖層 的填色
   * - 滴管
     - ``I``
     - 從畫布吸取前景色
   * - 移動
     - ``V``
     - 平移作用中圖層或選取區
   * - 矩形 / 套索 / 魔棒 / 快速選取
     - ``M`` / ``L`` / ``W``
     - 選取工具，含 替換 / 加入 / 減去 / 交集 模式
   * - 文字
     - ``T``
     - 內嵌文字編輯，可調字型 / 大小 / 粗體 / 斜體
   * - 漸層
     - ``U``
     - 線性 / 放射 / 角度 / 菱形 漸層填色
   * - 模糊 / 塗抹
     - ``R``
     - 局部像素操作
   * - 鋼筆（貝茲）
     - ``P``
     - 向量路徑，可編輯錨點 / 控制把手
   * - 仿製印章
     - ``S``
     - Shift+點擊設定來源，點擊蓋印（含羽化）
   * - 對話框
     - ``Ctrl + B``
     - 漫畫對話泡泡，自動產生指向尾巴
   * - 矩形 / 橢圓 / 直線 / 多邊形
     - ``Shift + R/E/I/P``
     - 向量形狀（含描邊與填色）
   * - 裁切
     - ``C``
     - 含長寬比預設的互動式裁切
   * - 變形
     - ``Ctrl + T``
     - 自由 / 縮放 / 旋轉 / 傾斜 變形把手
   * - 手形
     - ``H``
     - 拖曳平移畫布
   * - 縮放
     - ``Z``
     - 點擊放大，Alt+點擊縮小

筆刷
^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 筆刷
     - 效果
   * - 鋼筆
     - 銳利的抗鋸齒線條，日常使用
   * - 麥克筆 / 螢光筆
     - 半透明寬筆觸，會疊加堆疊
   * - 鉛筆
     - 細而帶點紋理的鉛筆線
   * - 噴霧
     - 由密度與流量驅動的散落點
   * - 書法
     - 筆觸寬度隨方向變化
   * - 水彩
     - 濕邊渲染與柔和混合
   * - 炭筆 / 蠟筆
     - 粗糙紋理筆觸（含壓力傾斜）

每種筆刷都在 **筆刷 dock** 與上方 **選項列** 中提供 大小 / 不透明度 / 硬度 /
密度 / 混合模式 控制。``設定`` > ``壓力曲線…`` 可重映數位板壓力到寬度或不透
明度；``編輯`` > ``擷取筆刷尖端…`` 可把選取區轉成自訂筆刷尖端。

圖層
^^^^

**圖層 dock** 提供縮圖、可見性切換、就地重新命名、拖曳排序，以及作用層的混合
模式 + 不透明度。``圖層`` 選單再加上：

- **新增 / 向量 / 複製 / 向下合併**（``Ctrl + Shift + N`` / ``Ctrl + Shift + V`` /
  ``Ctrl + J`` / ``Ctrl + E``）
- **遮罩** — 新增遮罩 / 由選取區產生 / 反向 / 套用 / 刪除
  （``Ctrl + Shift + M`` 新增；``Ctrl + Alt + Shift + M`` 由選取區產生）
- **剪裁遮罩** — 將上方圖層剪裁至目前 alpha（``Ctrl + Alt + G``）
- **圖層效果** — 投影 / 外光暈 / 描邊；可清除全部效果
- **參考圖層** — 把某層固定為滴管取色來源
- **1-bit 圖層** — 切換為線稿用的二值化圖層
- **依顏色拆分圖層** — 把單色平塗層拆成多層，便於重新填色
- **漸層映射** — 預設子選單（懷舊 / 夕陽 / 藍曬 …）

選取
^^^^

使用矩形 / 套索 / 魔棒 / 快速選取後，``編輯`` 選單中的 **描邊選取區…** 可用目前
筆刷沿選取邊緣描繪。``Q`` 切換 **快速遮罩模式** — 用任何筆刷以紅色精修選取邊
緣，再按 ``Q`` 把它轉回選取區。

動畫
^^^^

**動畫 dock** 把文件變成影格序列：

- ``新增影格`` 把目前圖層狀態存成一個關鍵影格。
- 點擊縮圖跳到該影格。
- ``洋蔥皮``（檢視選單）以低不透明度疊上相鄰影格。
- 透過 **檔案 > 匯出頁面** 匯出（漫畫閱讀器用 CBZ；列印用 PDF），或
  **動畫匯出** 輸出 MP4 / GIF。

漫畫選單
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 動作
     - 說明
   * - 分鏡切割
     - ``Ctrl + Shift + P`` — 將畫布依列數 / 行數 / 間距 / 邊框 / 邊界切成漫畫格
   * - 切換網點圖層
     - 把作用層轉成網點（halftone）圖層
   * - 蓋印頁碼
     - 在多頁文件上加上頁碼
   * - 集中線
     - 放射 / 平行 / 爆破 三種集中線產生器
   * - 動作閃光
     - 漫畫風的爆裂 / 衝擊閃光疊加
   * - 對話框工具
     - 拖出泡泡，再放下指向說話者的尾巴

濾鏡
^^^^

``濾鏡`` 開啟每個效果的即時預覽對話框：

- **色階** — 黑 / Gamma / 白 滑桿（含個別色板）
- **曲線** — 可拖曳節點（RGB / R / G / B），單調三次曲線插值
- **色調分離** — 將顏色量化成 N 階
- **臨界值** — 依切點轉成純黑 / 白
- **自動色彩平衡** — 用灰色世界 / 白點演算法消除色偏
- **底片顆粒** — 可調尺寸與強度的亮度雜訊
- **轉換為網點** — 報紙風的點狀網點

檢視輔助
^^^^^^^^

- **像素網格**（``Ctrl + Shift + '``）— 高倍率時顯示一像素網格
- **吸附像素 / 邊緣** — 將次像素位置鎖到整數座標
- **洋蔥皮** — 動畫相鄰影格疊加
- **出血標示** — 印刷出血 / 安全區指示線
- **旋轉畫布**（``Ctrl + Shift + H``）— 不破壞像素的視角旋轉

檔案 I/O
^^^^^^^^

- **開啟 PSD…**（``Ctrl + O``）與 **另存為 PSD…**（``Ctrl + S``）— Photoshop
  圖層往返，含遮罩、混合模式、圖層效果
- **匯出影像…** — 拼合並儲存為 PNG / JPEG / WebP / BMP / TIFF
- **匯出頁面 → CBZ** / **→ PDF** — 多影格的漫畫文件匯出
- **匯入 / 匯出筆刷預設集**、**匯入色盤** — 在不同安裝間共享資源
- **自動儲存快照** — 背景定期快照，可從檔案選單還原最新版

工作區排版
^^^^^^^^^^

``設定`` > ``工作區排版…`` 把 dock 排列、工具選項狀態、可見面板儲存成一個
名稱，再以一鍵切換 — 例如 "繪畫" 排版突顯筆刷與顏色 dock，"合成" 排版展開
圖層與歷史 dock。

----

旋轉與翻轉
----------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - 操作
     - 快捷鍵
     - 選單
   * - 順時針旋轉 90°
     - ``R``
     - 右鍵 > 修改 > 順時針旋轉
   * - 逆時針旋轉 90°
     - ``Shift + R``
     - 右鍵 > 修改 > 逆時針旋轉
   * - 水平翻轉
     - --
     - 右鍵 > 修改 > 水平翻轉
   * - 垂直翻轉
     - --
     - 右鍵 > 修改 > 垂直翻轉
   * - 無損旋轉（JPEG）
     - --
     - 右鍵 > 無損旋轉

----

匯出圖片
--------

單張匯出
^^^^^^^^

右鍵圖片 > ``匯出 / 另存為``

- 選擇格式：PNG、JPEG、WebP、BMP、TIFF
- 調整品質（有損格式可調）
- 預覽檔案大小
- 選擇儲存位置

匯出預設組合
^^^^^^^^^^^^

對於常見輸出目標，``檔案`` > ``以預設匯出`` 可一鍵套用正確的縮放、格式與品質：

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - 預設
     - 流程
   * - **Web 1600**
     - 長邊 1600 px、JPEG 品質 85、sRGB；適合部落格 / 論壇上傳。
   * - **Print 300 dpi**
     - 全解析度 TIFF / 高品質 JPEG，附 300 dpi metadata 與色彩管理，送印專用。
   * - **Instagram 1080**
     - 正方（1080 × 1080）或直式（1080 × 1350）裁切，品質 90 JPEG。

預設可與下面的浮水印疊加搭配使用 — 啟用浮水印後，所有預設匯出都會自動附上。

浮水印疊加
^^^^^^^^^^

``檔案`` > ``浮水印…`` 提供非破壞性疊加設定，只在匯出時套用，不會動到原始像素。

- **模式**：文字或圖片。圖片浮水印支援含 alpha 的 PNG。
- **位置**：9 格錨點（四角、四邊、正中央）。
- **不透明度**：0 – 100 %。
- **縮放**：以匯出長邊百分比計算，會自動依預設尺寸縮放。

批次匯出
^^^^^^^^

選取多張圖片後，右鍵 > ``批次匯出``

- 統一格式轉換
- 設定最大寬度／高度（自動等比縮放）
- 品質控制
- 進度條即時顯示

製作 GIF / 影片
^^^^^^^^^^^^^^^^

選取多張圖片後，右鍵 > ``建立 GIF / 影片``

- 支援 GIF 和 MP4 格式
- 可拖曳排列順序
- 設定每秒幀數（FPS）
- 自訂尺寸
- 循環播放選項

----

動畫圖片播放
------------

開啟 GIF、APNG、動態 WebP 時，會自動播放動畫。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 操作
   * - ``空白鍵``
     - 播放／暫停
   * - ``,``
     - 上一幀
   * - ``.``
     - 下一幀
   * - ``]``
     - 加速播放
   * - ``[``
     - 減速播放

----

圖片比較
--------

在縮圖模式下框選 2～4 張圖片，右鍵 > ``比較圖片``。

對話框共有四個頁籤：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 頁籤
     - 用途
   * - **並排**
     - 同時顯示 2 或 4 張圖片，各自自適應縮放。
   * - **重疊**
     - 兩張圖以 α 滑桿混合（0 → 只看 A、100 → 只看 B）。需選取 2 張。
   * - **差異**
     - 顯示 ``|A − B|`` 的逐像素差異；增益滑桿（0.10×–20×）可放大細微變化。
   * - **A | B 分割**
     - before / after 分割檢視，可拖動垂直分割線掃動。適合展示 Develop 調整或匯出差異。需選取 2 張。

尺寸不同時會自動以 Lanczos 將 B 重新取樣為 A 的尺寸。超大圖片內部會限制長邊 ≤ 2048 px 以保持即時反應。

.. seealso::
   若想直接在主視窗並排而不開啟對話框，請見 **分割檢視**（``Shift + S``）與
   **雙頁閱讀**（``Shift + D`` / ``Ctrl + Shift + D``）。

----

幻燈片
------

按 ``S`` 或右鍵 > ``幻燈片``，開始自動播放所有圖片。

- 可調整每張停留時間
- 可開啟淡入淡出效果

----

搜尋圖片
--------

按 ``Ctrl + F`` 或 ``/``，輸入關鍵字即可搜尋當前資料夾中的圖片名稱。

搜尋支援 **模糊匹配**（前綴 > 子字串 > 子序列 三級排名）與 **子字串高亮**。
按 ``Enter`` 或雙擊結果跳至對應圖片。

若想依 **編號** 跳轉，改按 ``Ctrl + G`` 開啟跳頁對話框。

----

複製與貼上
----------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 操作
     - 方法
   * - 複製圖片到剪貼簿
     - 大圖模式下按 ``Ctrl + C``
   * - 貼上剪貼簿圖片
     - ``檔案`` > ``從剪貼簿貼上``，或按 ``Ctrl + V``
   * - 自動監控剪貼簿
     - ``檔案`` > ``自動標註剪貼簿圖片`` 打勾

.. note::
   自動監控功能開啟後，每當剪貼簿出現新圖片（例如用截圖工具），就會自動開啟標註編輯。

----

刪除圖片
--------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 操作
     - 方法
   * - 刪除當前圖片
     - 按 ``Delete`` 鍵
   * - 刪除選取的多張圖片
     - 框選後按 ``Delete`` 或右鍵 > ``刪除選取``

圖片會移到系統資源回收桶，可以從那邊還原。

----

批次操作
--------

在縮圖模式下框選多張圖片後，右鍵可以進行：

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 功能
     - 說明
   * - 批次重新命名
     - 使用模板 ``{name}`` ``{n}`` ``{ext}`` 自動命名
   * - 移動／複製
     - 把圖片移動或複製到其他資料夾
   * - 全部旋轉
     - 一次旋轉所有選取的圖片
   * - 批次匯出
     - 統一轉換格式和大小
   * - 加入標籤
     - 幫所有選取的圖片加上同一個標籤
   * - 加入相簿
     - 把所有選取的圖片放進相簿

----

RGB 直方圖
----------

在大圖模式下按 ``H``，會在畫面上顯示 RGB 直方圖，方便判斷曝光狀況。再按一次隱藏。

----

設定桌布
--------

大圖模式下右鍵 > ``設為桌布``，一鍵將當前圖片設為系統桌布。

支援 Windows、macOS、Linux（GNOME）。

----

多視窗
------

``檔案`` > ``開新視窗``，可以同時開啟多個 Imervue 視窗，各自獨立瀏覽不同資料夾。

觸控板手勢
----------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 手勢
     - 動作
   * - 捏合
     - 在大圖模式放大／縮小（以捏合中心為錨點）
   * - 水平滑動
     - 上一張 / 下一張圖片

----

Windows 檔案關聯
-----------------

讓你在檔案總管中直接用 Imervue 開啟圖片：

1. ``檔案`` > ``檔案關聯`` > ``註冊 Open with Imervue``
2. 需要系統管理員權限
3. 之後右鍵任意圖片就能看到 ``Open with Imervue`` 選項

如果要移除：``檔案`` > ``檔案關聯`` > ``移除檔案關聯``

----

外掛系統
--------

Imervue 支援外掛擴充功能。

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 操作
     - 選單位置
   * - 查看已安裝外掛
     - ``外掛`` > ``管理外掛``
   * - 下載新外掛
     - ``外掛`` > ``下載外掛``
   * - 開啟外掛資料夾
     - ``外掛`` > ``開啟外掛資料夾``
   * - 重新載入
     - ``外掛`` > ``重新載入外掛``

----

語言切換
--------

``語言`` 選單可以切換介面語言：

- English
- 繁體中文
- 简体中文
- 한국어
- 日本語

切換後需要重新啟動才會生效。

----

所有快捷鍵一覽
--------------

瀏覽
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 功能
   * - ``←`` / ``→``
     - 上一張／下一張圖片
   * - 方向鍵
     - 縮圖模式下平移畫面
   * - ``Shift + 方向鍵``
     - 微調平移
   * - ``Ctrl + Shift + ←`` / ``→``
     - 跨資料夾跳至前／下一個含圖片的兄弟資料夾
   * - ``Alt + ←`` / ``Alt + →``
     - 瀏覽歷史 返回 / 前進（類似瀏覽器）
   * - ``Ctrl + G``
     - 依編號跳至圖片
   * - ``X``
     - 隨機跳一張
   * - 滑鼠滾輪 / 捏合
     - 放大縮小
   * - 水平滑動
     - 上／下一張圖片
   * - 滑鼠中鍵拖曳
     - 平移畫面
   * - ``F``
     - 全螢幕
   * - ``Shift + Tab``
     - 劇場模式（隱藏所有外殼）
   * - ``Ctrl + L``
     - 切換 縮圖格 ↔ 清單（詳細）
   * - ``Shift + S``
     - 分割檢視（兩張並排）
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - 雙頁閱讀 / 右至左（漫畫）
   * - ``Ctrl + Shift + M``
     - 副螢幕鏡像視窗
   * - ``Esc``
     - 回到縮圖模式／退出全螢幕／關閉雙圖或清單模式
   * - ``W``
     - 適應寬度
   * - ``Shift + W``
     - 適應高度
   * - ``Home``
     - 重設縮放

編輯
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 功能
   * - ``E``
     - 進入修改分頁
   * - ``R``
     - 順時針旋轉
   * - ``Shift + R``
     - 逆時針旋轉
   * - ``Ctrl + Z``
     - 復原
   * - ``Ctrl + Shift + Z``
     - 重做
   * - ``Delete``
     - 刪除圖片

整理
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 功能
   * - ``0``
     - 加入／取消最愛
   * - ``1`` ～ ``5``
     - 評分（再按取消）
   * - ``F1`` ～ ``F5``
     - 色彩標籤：紅／黃／綠／藍／紫（再按清除）
   * - ``P``
     - 分揀：Pick（標為保留）
   * - ``Shift + X``
     - 分揀：Reject（標為淘汰）
   * - ``U``
     - 分揀：取消旗標
   * - ``B``
     - 加入／取消書籤
   * - ``T``
     - 標籤與相簿管理

工具與疊加層
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 功能
   * - ``Ctrl + F`` / ``/``
     - 模糊搜尋（子字串高亮）
   * - ``Ctrl + C``
     - 複製圖片到剪貼簿
   * - ``Ctrl + V``
     - 從剪貼簿貼上
   * - ``H``
     - RGB 直方圖
   * - ``F8`` / ``Ctrl + F8``
     - OSD 資訊 / Debug HUD（VRAM、快取、執行緒）
   * - ``Shift + P``
     - 像素檢視（≥ 400 % 顯示網格與游標下 RGB 值）
   * - ``Shift + M``
     - 循環色彩模式（正常／灰階／反相／懷舊）
   * - ``S``
     - 幻燈片

動畫播放
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按鍵
     - 功能
   * - ``空白鍵``
     - 播放／暫停
   * - ``,``
     - 上一幀
   * - ``.``
     - 下一幀
   * - ``[``
     - 減速
   * - ``]``
     - 加速

圖庫與中繼資料管理
------------------

Imervue 會在 ``%LOCALAPPDATA%/Imervue/library.db``（Windows）或
``~/.cache/imervue/library.db``（POSIX）維護一個 SQLite 索引，用於跨資料夾
搜尋、階層式標籤、智慧相簿、感知雜湊、筆記與分揀旗標。下列功能多半位於
``Extra Tools``（額外功能）選單下。為了方便尋找，該選單依功能分為八個子選
單：``Batch``（批次）、``Library & Metadata``（圖庫與中繼資料）、
``Views``（檢視）、``Workflow``（工作流程）、``Export``（匯出）、
``Develop (Non-Destructive)``（調整）、``Retouch & Transform``（修復與變形）、
``Multi-Image``（多張合成），下列路徑皆以
``Extra Tools`` > ``<子選單>`` > ``<工具>`` 的形式呈現。

圖庫搜尋
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` 允許新增多個**根目錄**並在背景建立索引，
之後可依副檔名、最小寬高、檔案大小或檔名片段查詢，並把結果當作虛擬相簿
載入檢視器。

智慧相簿
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` 以友善名稱儲存一組過濾規則（副檔名、最小
尺寸、色彩標籤、評分、最愛、分揀狀態、階層式標籤、檔名片段）。再次套用時，
會依規則篩選目前資料夾。

相似圖片搜尋
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` 會對當前深度縮放的圖片（或第一張選
取圖）計算 64 位元 DCT pHash，並依 Hamming 距離遞增列出索引中的近似圖。
可藉由「Max distance」調整寬鬆度。

自動標記
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` 會將經驗式標籤套用於 ``auto/...``
（``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``）。若系統已安裝 ``onnxruntime`` 並於 ``models/clip_vit_b32.onnx``
放置 CLIP 模型，還會加入 CLIP 內容標籤。執行時以工作執行緒處理，具即時進
度列。

階層式標籤
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` 管理樹狀結構標籤（如
``animal/cat/british``）。選取節點即可列出該節點與所有子節點下的圖片；可
一鍵為目前選取的圖片加上或移除標籤。此系統與右鍵選單的扁平標籤並行。

Token 批次重新命名
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` 提供即時預覽，輸入如
``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` 的樣板，即可看到每個檔案的新
名稱；衝突會被標示。支援 tokens：``{name} {ext} {counter[:NN]} {date[:fmt]}
{width} {height} {wxh} {size_kb} {camera} {year} {month} {day} {hour}
{minute}``。

中繼資料匯出
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` 會為目前檢視的每張圖片
輸出一列，包含 EXIF、尺寸、色彩標籤、評分、最愛、階層式標籤、分揀狀態與
筆記。適合用於試算表或外部流程。

XMP Sidecar（other XMP-aware photo managers 互通）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue 支援讀寫 Adobe XMP sidecar 檔（``photo.jpg`` ↔ ``photo.xmp``），
讓星等、標題、描述、關鍵字與色彩標籤可與 other XMP-aware photo managers、other XMP-aware photo managers、Bridge
等 XMP 感知工具雙向同步。

- **為當前圖片匯入 XMP** — 從 sidecar 讀取星等 / 標題 / 關鍵字 / 色彩標籤
  寫入內部資料庫。
- **為當前圖片匯出 XMP** — 將當前星等 / 標題 / 關鍵字 / 色彩標籤寫入
  圖片旁的 sidecar 檔。
- **批次匯入 / 匯出** — 將同樣操作套用至目前選取或整個資料夾。

XML 解析透過 ``defusedxml`` 進行，避免 XXE / billion-laughs 等攻擊。
若未安裝 ``defusedxml``，XMP 選單項目會自動隱藏，也不會寫出 sidecar。

**EXIF 側邊欄** 亦提供可點擊的 **星等快速條** — 設定的星等即為 XMP 匯出的值。

分揀（Pick / Reject）
^^^^^^^^^^^^^^^^^^^^^

旗標式的三態旗標。``P`` 將當前圖片或所有選取 tile 標為 Pick；
``Shift + X`` 標為 Reject；``U`` 取消旗標。``Filter`` > ``By Cull State`` 可
只顯示某一種狀態；``Extra Tools`` > ``Workflow`` > ``Culling`` 提供對話框介面並附有
**Delete all rejects** 按鈕，可從磁碟永久刪除被淘汰的檔案。

暫存籃
^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` 是跨資料夾的暫存籃。可將任意 tile 加入
籃中（重啟後保留），再一鍵把整個籃移動或複製至目的資料夾。適合從多次
拍攝中彙整出精選再匯出。

雙窗格檔案管理
^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` 提供 雙窗格的雙樹
檢視，可在兩個資料夾之間直接移動或複製選取項目。

時間軸檢視
^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` 以「日／月／年」方式分組目前圖片集
（date-grouped library views 樣式）。日期優先使用 EXIF ``DateTimeOriginal``，否則退回檔
案修改時間。雙擊圖片即可進入深度縮放。

拖放至外部應用程式
^^^^^^^^^^^^^^^^^^

由**已選取** tile 按住拖曳，可將檔案直接丟到檔案總管、Chrome、Discord 等
支援檔案 URL 的應用程式；拖曳預覽為 tile 縮圖。

單張圖片筆記
^^^^^^^^^^^^

EXIF 側邊欄包含自由文字 **Notes** 區塊，輸入內容會經短暫去抖後自動寫入
索引；筆記依圖片路徑儲存，重新掃描資料夾也能保留。

----

進階 Develop 與合成
-------------------

色調曲線（Tone Curve）
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` 開啟可拖曳控制點的曲線編輯器，提供 RGB、
R、G、B 四條通道。點擊空白處新增控制點、拖曳移動、右鍵刪除。點之間
以 monotone cubic 插值，曲線儲存在 recipe 中，顯示時非破壞性套用。

套用 .cube LUT
^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` 可選擇任意 Adobe ``.cube`` 檔案
（1D / 3D，最大 64³）。LUT 以 ``lru_cache`` 依路徑 + mtime 快取，使用
三線性插值套用，並透過強度滑桿與原始影像混合。LUT 路徑與強度儲存在
recipe。

虛擬副本（Virtual Copies）
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` 為同一張圖建立多組命名的 recipe
快照。儲存目前編輯後可繼續實驗，之後再切回任一版本。副本與主
recipe 一起保存，即使把主 recipe 重設為 identity 也不會消失。

HDR 合成
^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` 以 OpenCV Mertens 曝光融合合併多張
不同曝光的照片。可勾選 Align 先以 ``cv2.AlignMTB`` 對齊手持晃動，
輸出寫到使用者指定路徑，不影響來源檔。

全景接圖
^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` 以 OpenCV ``Stitcher`` 接合重疊
影像。風景 / 城市用 **Panorama** 模式；平面文件或畫作用 **Scans**
模式。可自動裁掉拼接產生的黑邊。

景深合成（Focus Stacking）
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` 融合不同對焦距離的多張影像。
演算法以 Laplacian 變異數計算每像素清晰度，挑出該處最清楚的來源，
再用高斯平滑避免接縫。預設啟用 ECC 對齊以補手持輕微位移。

修復筆刷
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` 以長邊最大 720 px 的預覽顯示影像。
左鍵新增圓形斑點，右鍵移除既有斑點，半徑滑桿控制新斑點大小。
套用時使用 OpenCV inpainting（Telea 速度快，Navier-Stokes 較平滑）
修補區域，輸出為新檔。

鏡頭校正
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` 提供四個純 numpy 滑桿：
徑向失真 ``k1``（桶型 / 枕型）、暗角補光，以及紅 / 藍通道的色差
徑向縮放。因影像尺寸可能改變，結果輸出為新檔而非寫入 recipe。

地圖檢視
^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` 透過 Leaflet + OpenStreetMap（需
``PySide6.QtWebEngineWidgets``）顯示目前圖庫中所有有 GPS 的照片。
未安裝 WebEngine 時降級為 ``(路徑, 緯度, 經度)`` 列表。

行事曆檢視
^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` 以 ``QCalendarWidget`` 標示有
照片的日期（依序嘗試 EXIF ``DateTimeOriginal`` → ``DateTimeDigitized``
→ 檔案 mtime）。點選日期列出當日照片，雙擊於主視窗開啟。

人臉偵測
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` 以 OpenCV Haar 正面臉部分類器
偵測臉部並以矩形標示。在清單雙擊輸入人名，儲存後寫入 recipe 的
``extra['face_tags']``。此為經典技術，適合「找出臉的位置」，但非
現代 CNN 辨識的替代品。

局部調整遮罩
^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` 讓使用者堆疊筆刷 / 放射
/ 線性漸層遮罩。每個遮罩有各自的曝光、亮度、對比、飽和度、色溫、
色調 delta 與羽化滑桿，儲存在 ``recipe.extra['masks']`` 並以非破壞
方式於載入時混入原圖。

色調分離
^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` 對陰影與高光分別套用不同色相與
飽和度，並以平衡樞紐決定交界位置。儲存於 ``recipe.extra`` 並在
develop pipeline 的 tone curve 之後套用。

複製印章
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` 以羽化方式複製來源區塊到目的地，
為硬邊版本的修復筆刷。Shift+點擊設定來源，一般點擊蓋章，右鍵復原。
結果輸出為新檔，不會動到原圖。

裁切 / 拉直
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` 結合 0..1 正規化裁切矩形與
任意角度拉直。輸出會自動裁切到最大內接矩形，旋轉後的照片不會有
黑邊。

自動拉直
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` 以 Hough line 偵測主要的地平
線或垂直線，提出建議的旋轉角度。可以在套用前微調角度。

降噪 / 銳化
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` 先以邊緣保留的
bilateral 降噪，再以 unsharp mask 銳化。「僅亮度通道」會保留色噪，
但能壓平明度雜訊而不糊掉色彩邊緣。

天空 / 背景
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` 將偵測到的天空以漸層取代，
或直接把背景做成透明 / 白底。安裝 ``rembg`` (U²-Net) 時會自動啟用
神經網路前景分割。

螢幕校樣
^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` 載入 ICC 描述檔，將圖片轉進目的色
域再轉回，並以洋紅顯示往返過程中被裁切的像素 — 列印前快速檢查
色域的工具。

GPS 地理標記
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` 讀取現有 EXIF GPS 座標並允許編輯
或設定新的十進位度數。需要安裝 ``piexif``；會直接寫入 JPEG 檔。

列印排版
^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` 把多張圖片排版成多頁 PDF，可設
定頁面大小、方向、格線、邊界、內距與裁切標記。需要安裝
``reportlab``。

----

Puppet 工作區（Puppet 分頁）
----------------------------

第四個頂層分頁 — **Puppet** — 是從零打造的 2D 綁骨偶動畫系統。功能對標 Live2D（網格變形綁骨、參數、動作、物理、表情、姿勢群組、對嘴、攝影機追蹤），但**不依賴任何專利 SDK**、**不使用** ``live2d-py``，採用完全開放的 ``.puppet`` 檔案格式。

.. note::

   端到端教學 — 從全新安裝到 OBS 直播或產出 MP4 — 在倉庫根目錄的
   ``puppet_guide.zh-TW.md``（英文版 ``puppet_guide.md``、簡體中文版 ``puppet_guide.zh-CN.md``）。
   本章是參考手冊；那份是逐步走讀。

端到端流程
^^^^^^^^^^

1. **匯入 PNG** — 工具列 ``Import PNG…`` 跑 ``puppet.auto_mesh.puppet_from_png``：依 alpha 三角化、單一 drawable、可立即渲染。
2. **加變形器** — ``Add Rotation Deformer``（錨點 + 角度）或 ``Add Warp Deformer``（rows × cols Bezier lattice；邊界外頂點直通）。
3. **加參數** — ``Add Parameter`` 在右側 **Parameters** 擺放欄加滑桿（自動命名 ``Param1``、``Param2`` …）。
4. **設 keys** — 拖滑桿到極端值、編輯 deformer form、按 **Set key**。對中立值跟另一端重複。Runtime 接著會在滑桿移動時於相鄰 keys 之間 lerp 各欄位。
5. **儲存** — ``Save As…`` 把 rig + 紋理 + 動作 + 表情 + 物理寫成單一 ``.puppet`` zip，可分享或之後用 ``Open Puppet…`` 重開。

範例
^^^^

倉庫內附完整 rig：``examples/puppet/march_7th.puppet`` — 307-drawable 的 Cubism Live2D 角色，倉庫內轉換好。紋理跟每參數頂點 morph 全烘進 ``.puppet`` zip，使用預設 ``requirements.txt`` 就能開，無需散布 Cubism SDK。

該 rig 帶 203 個 Cubism 標準參數（``ParamAngleX/Y/Z``、``ParamEyeLOpen/ROpen``、``ParamBreath``、``ParamMouthOpenY`` …），所以所有標準輸入驅動（攝影機、眨眼、對嘴、游標追蹤）不用調整就能驅動。內附 18 個循環動作 — 作者轉換的 Cubism idle 迴圈，加上 ``Idle`` 群組和 ``Gesture`` 群組的參考手勢。

Puppet 分頁工具列 → **Examples ▾** 下拉直接選 March 7Th 或自己的 ``.puppet`` 開啟。下方 **Motions** 擺放欄點任一個動作即播。

**執行內附範例 — 逐步走讀：**

1. **啟動 Imervue**。原始碼跑：``python -m Imervue``；裝好的版本：直接執行 ``Imervue`` 執行檔 / app bundle。``examples/`` 資料夾已經打包進 wheel 跟 Nuitka EXE，rig 檔案會在安裝目錄底下。
2. 點視窗頂端的 **Puppet** 分頁。
3. 工具列 → **File > Examples > March 7Th**（或工具列上的 **Examples ▾** 下拉）。307-drawable 的 rig 居中載入，參數欄會填滿 203 個 Cubism 標準參數滑桿。
4. 在底部 **Motions** 擺放欄單擊任一個動作條目（``zhaiyan``、``zhaoxiang``、``idle_breath``、``tap_head`` …）。立即開始播放；再點一次停止，或選別的動作交叉淡入。
5. 切換工具列上的即時輸入 toggle 讓 rig 跟著你動 — **Drag-track head**（頭跟著游標）、**Auto-blink**（自動眨眼）、**Auto idle** + **Idle motions**（呼吸 + 隨機 idle 動作）、**Mic lip-sync**（麥克風 RMS 帶動嘴型）、**Webcam tracking**（MediaPipe FaceLandmarker 驅動頭 / 眼 / 嘴）。
6. 工具列 **Reset to rest** 把所有動作停掉、所有即時驅動取消勾、清掉 expressions / pose 覆寫，所有參數復位 — 標準的「重新開始」按鈕。
7. 之後要開別的 rig：**File > Open Puppet…** 從磁碟挑任何 ``.puppet`` zip；**File > Examples ▾** 永遠連到內附清單。

OBS 直播整合
^^^^^^^^^^^^

兩條輸出，都把角色獨立渲染到 off-screen framebuffer（不含棋盤格背景與編輯器外殼）再送到串流端。輸出長邊上限 1080 px，避免 Cubism 原生畫布（March 7th 是 3503×7777）被 DirectShow 虛擬攝影機驅動拒絕。

**A. Virtual Camera** — 在 OBS《視訊擷取裝置》來源清單裡以 webcam 形式出現。``pip install pyvirtualcam`` 加上平台驅動：OBS Studio 26+（Windows/macOS）會附 *OBS Virtual Camera* 驅動，第一次打開 OBS 點 *Start Virtual Camera* 註冊；Linux 用 ``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``。工具列 **Output > Virtual camera** 開始串流。

DirectShow / AVFoundation / v4l2loopback 都**只有 RGB、沒有 alpha 通道**，所以 Imervue 在角色以外的區域填**洋紅色 `#FF00FF`** 當色鍵。OBS 端去背：

1. 視訊擷取裝置來源右鍵 → **Filters**
2. **Effect Filters > + > Color Key**
3. 設定 **Key Color Type** = ``Custom Color``、**Custom Color** = HEX ``FF00FF``、**Similarity** = ``80–300``、**Smoothness** = ``30–50``

濾鏡跟著來源走，下次啟用虛擬攝影機自動套用。

**B. NDI 輸出** — LAN 上 < 50 ms 延遲、原生 RGBA，OBS / vMix 可以直接把角色疊到自己的場景上、不用色鍵。``pip install ndi-python``，加上 `NDI Tools <https://ndi.video/tools/>`_ runtime 與 `obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_ 外掛。工具列 **Output > NDI output** 開始廣播（預設來源名 *Imervue Puppet*）。

``ndi-python`` 只 ship source distribution、pip 拿到後從 C++ 編。Windows 需要 Visual Studio Build Tools 2022（含 C++ 工作負載）、CMake 加到 PATH、NDI SDK（從 <https://ndi.video/for-developers/ndi-sdk/> 取得，跟 NDI Tools 不同）裝在預設位置、環境變數 ``NDI_SDK_DIR`` 指向 SDK。

詳細逐步與疑難排解見 ``puppet_guide.zh-TW.md`` § 1.2。

錄製自訂動作
^^^^^^^^^^^^

不想手動編 keyframe？用即時 take 錄：

1. 工具列 **Record motion** 打勾，會跳出命名對話框。
2. 錄製時拖滑桿、開 **Webcam tracking**、讓物理跑 — 任何會寫參數值的事情都可以。
3. **Record motion** 取消勾 — 錄製器把 30 Hz 串流烘焙成一個 ``Motion``：每個真的有變動的參數一條 linear-segment 軌（沒變動的丟掉）。新動作立刻出現在底部 **Motions** 擺放欄。

存進 ``.puppet`` 的方式跟手寫 keys 的動作完全相同。

工具列參考
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 動作
     - 用途
   * - Open Puppet… / Examples ▾
     - 從磁碟載入 ``.puppet``，或從工具列直接挑 ``examples/puppet/`` 下內附的 rig
   * - Import PNG… / Import PSD… / Import Cubism…
     - PNG 自動 mesh、PSD 分層拆 drawable、Cubism rig sample-and-reconstruct。Cubism 檔案選擇器同時接受 ``.moc3`` 跟 ``.model3.json``；工作區還沒開 rig 時兩條路徑都跑完整 ``.moc3 → .puppet`` 轉換（SDK 使用者自備）。已經開了 rig 時挑 ``.model3.json`` 改把 JSON 部分（motions / expressions / physics）疊到既有文件
   * - Save As…
     - 把目前 rig 寫成 ``.puppet`` zip
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - 從工具列 author rig
   * - Drag-track head
     - 游標偏移 → ``ParamAngleX`` / ``ParamAngleY`` + ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - ``ParamEyeLOpen`` / ``ParamEyeROpen`` 上的 cosine close→open，每 ~4.5 秒一次（force-write 路徑繞過 canvas 的 no-change-skip，避免被其他 driver 卡住）
   * - Mic lip-sync
     - 麥克風 RMS → ``ParamMouthOpenY``（需 ``sounddevice``）
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → 頭部 yaw / pitch / roll + 眼 + 嘴（需 ``opencv-python`` + ``mediapipe``；開啟即時預覽 dialog 顯示偵測到的 landmark）
   * - Auto idle / Idle motions
     - 標準參數上的呼吸 + 漂移，加上 Idle 群組動作的隨機循環
   * - Edit mesh
     - 拖曳 canvas 上的頂點微調 mesh
   * - Record motion
     - 把參數變化錄成新的 ``Motion`` 加進文件 — take 烘焙、不用手動 author keys
   * - Capture frame… / Record… / Export all motions…
     - 存單張 PNG、開關 GIF / WebM / MP4 錄製、或批次把每個動作各別 render 成檔（全部用跟串流相同的角色獨立 off-screen render）
   * - Output > Virtual camera / NDI output
     - 直播輸出 — 見上面的「OBS 直播整合」
   * - Reset to rest
     - Motion player 直接停、所有 live driver 取消勾、清空 expressions / pose groups、參數復位
   * - Fit to Window
     - Canvas 上重新置中 + 縮放 rig

選用依賴
^^^^^^^^

* ``sounddevice`` — 麥克風對嘴
* ``opencv-python`` + ``mediapipe`` — 攝影機臉部追蹤
* ``imageio-ffmpeg`` — MP4 / WebM 錄製（已隨幻燈片影片功能附帶）
* ``pyvirtualcam`` — 虛擬攝影機輸出（見「OBS 直播整合」）
* ``ndi-python`` — NDI 輸出（見「OBS 直播整合」）
* 使用者自備 Cubism Native SDK DLL — ``.moc3 → .puppet`` 轉換（Live2D Free Material License 禁止散布；放在 ``<cwd>/sdk/`` 或設 ``CUBISM_CORE_DLL`` 環境變數）

任何缺失都會優雅停用 — 對應工具列 toggle 會自動彈回去並提示安裝。**File > Install dependencies…** 可一次裝齊所有 Python 選用包。

----

桌寵工作區（Desktop Pet 分頁）
------------------------------

第五個分頁 — **Desktop Pet** — 把任何 ``.puppet`` 角色當成無邊框、透明背景的桌面浮層放到你的桌面上。分頁本身是控制面板；真正的角色浮在其他視窗的上方（或後方）。Puppet 分頁裡能對 rig 做的所有事 — 動作、表情、物理、idle driver、webcam / 麥克風輸入 — 在這裡通通能用。

能做什麼
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - 功能
     - 說明
   * - 無邊框浮層
     - 沒有視窗外框、不出現在工作列 — 就只有角色待在你的桌面上。
   * - 透明背景
     - 角色沒覆蓋到的地方直接透出後面的桌面。
   * - 拖曳移動
     - 左鍵拖角色就能換位置。放開時若靠近螢幕邊緣，會**吸附**貼齊邊緣。
   * - 點擊穿透模式
     - 讓桌寵忽略你的滑鼠，你就能在它底下繼續工作。
   * - 鎖定位置
     - 凍結桌寵位置，避免不小心拖到。
   * - 永遠置底
     - 把桌寵塞到所有視窗的後面 — 不是永遠置頂，而是桌面小工具的感覺。
   * - 全螢幕自動隱藏
     - 當同一個螢幕上有其他 App（遊戲 / 影片 / 簡報）全螢幕時自動隱藏，全螢幕結束後再回來。
   * - 隱藏時暫停
     - 桌寵看不見時不動畫 — 不在畫面上時 CPU 用量為零。
   * - 尺寸預設
     - 小 / 中 / 大。以中心為錨點縮放，調尺寸時桌寵不會跳到螢幕另一邊。
   * - 透明度滑桿
     - 把桌寵從 10% 淡到 100%，讓它變成低調的桌面裝飾。
   * - 記得你放在哪
     - 把桌寵拖到你喜歡的角落，下次啟動它會回到原地。

點擊互動
^^^^^^^^

* **左鍵點身體** — 如果 rig 有定義 hit area（例如點頭），就播對應的動作。沒命中時桌寵會用對話泡泡跟你打招呼。
* **右鍵任意位置** — 開啟右鍵選單：隱藏桌寵、Live drivers、Play motion（rig 內所有動作的清單）、Apply expression、鎖定位置、點擊穿透、永遠置底、全螢幕自動隱藏、對話泡泡、Size。
* **系統匣圖示** — 左鍵單擊切換顯示，右鍵開啟 顯示 / 隱藏、點擊穿透、開啟 puppet、隱藏桌寵。

Live driver
^^^^^^^^^^^

從分頁或右鍵選單裡任意組合都行。每個預設都是關的 — 只開你想要的就好。

* **Auto idle** — 呼吸 + 微幅漂移，讓角色有生命感。
* **Idle motions** — 隨機循環 rig 的 idle 群組動作。
* **Auto-blink** — 自然週期性眨眼，每幾秒一次。
* **Drag-track head** — 頭部轉向追隨你的游標。
* **Mic lip-sync** — 嘴巴跟著你的聲音開合（需 ``sounddevice``）。
* **Webcam tracking** — 你的頭 / 眼 / 嘴會驅動桌寵的頭 / 眼 / 嘴（需 ``opencv-python`` 和 ``mediapipe``）。

怎麼開始
^^^^^^^^

1. 切換到 **Desktop Pet** 分頁。
2. 點 **Load bundled March 7th** 用內附的角色，或 **Open Puppet…** 選自己的 ``.puppet`` 檔。
3. 勾選 **Show pet on desktop**。
4. 把角色拖到想要的位置；挑你想要的 driver；調整透明度 / 尺寸。
5. 任何時候按右鍵叫出快速選單，或用系統匣圖示在不切回分頁的情況下藏起桌寵。

你設定的所有東西 — 位置、driver、透明度、點擊穿透、尺寸 — 都會在下次啟動時記得。

----

命令列啟動
----------

::

   imervue                        # 正常啟動
   imervue 圖片路徑               # 直接開啟指定圖片
   imervue 資料夾路徑             # 直接開啟指定資料夾
   imervue --debug                # 啟用除錯模式
   imervue --software_opengl      # 使用軟體渲染（顯卡不支援時）

----

MCP 伺服器
----------

Imervue 內建一個 `Model Context Protocol <https://modelcontextprotocol.io>`_
伺服器,讓 AI 助理(Claude Code、Claude Desktop、Cursor、Cline …)
可以直接呼叫專案的純邏輯輔助函式,而不需要啟動 GUI。一行指令啟動::

   python -m Imervue.mcp_server

伺服器不依賴 Qt,各工具按需懶載入。

可用工具
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - 工具
     - 用途
   * - ``list_images``
     - 列出資料夾內的圖片(路徑、大小、修改時間)。傳
       ``recursive=true`` 可遞迴遍歷子資料夾。
   * - ``read_image_metadata``
     - 單張圖片的尺寸、格式、EXIF、XMP sidecar。缺資料就回對應的
       空值,不會 raise。
   * - ``read_xmp_tags``
     - 僅讀 XMP 的快速路徑 — 評等、色標、關鍵字、標題、描述。
   * - ``convert_format``
     - 圖片格式轉換。目標格式由目標檔案的副檔名決定(``png`` /
       ``jpg`` / ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``)。
       JPEG/WebP 可選擇 ``quality``(1–100)。
   * - ``puppet_from_png``
     - 用 puppet 插件的 auto-mesh 從 PNG 建出 ``.puppet`` 動畫檔。
       自動帶入 Cubism 標準參數,匯入後可直接被驅動。
   * - ``puppet_inspect``
     - 開啟 ``.puppet`` 並回傳結構化盤點:drawables、deformers、
       parameters、motions、expressions、hit areas、parts、
       parameter blends、physics rigs。

所有工具的回傳會 JSON 序列化後包進 MCP 的 ``content`` / ``text``
信封;客戶端可從 ``text`` 欄位再 parse 回結構化資料。

Claude Code(專案層級)
^^^^^^^^^^^^^^^^^^^^^^

repo 根目錄已附專案層級的 ``.mcp.json``:

.. code-block:: json

   {
     "mcpServers": {
       "imervue": {
         "type": "stdio",
         "command": "python",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

用 Claude Code 開啟 repo 任何子目錄都會自動探索到這個伺服器。
首次使用時 Claude Code 會詢問是否啟用專案 MCP 伺服器,接受即可。

Claude Desktop
^^^^^^^^^^^^^^

把同樣那段加進 Claude Desktop 的設定檔:

* macOS:``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows:``%APPDATA%\Claude\claude_desktop_config.json``

請使用絕對工作目錄,或啟用裝了 Imervue 的 venv —
``python`` 必須能解析到能 ``import Imervue`` 的直譯器。

通訊協定
^^^^^^^^

伺服器走 MCP ``2025-03-26`` 版的 stdio JSON-RPC 2.0:

* ``initialize`` — 握手,廣告 ``capabilities.tools``。
* ``tools/list`` — 列出已註冊工具與其 JSON-Schema 輸入定義。
* ``tools/call`` — 用 ``{"name", "arguments"}`` 呼叫工具,結果回
  在 ``content`` 陣列。
* ``notifications/*`` — 靜默接受(不回應)。

實作在 ``Imervue/mcp_server/``:

* ``server.py`` — 協定迴圈 + 工具註冊表
* ``tools.py`` — 各工具的 handler 與預設工具集
* ``__main__.py`` — ``python -m Imervue.mcp_server`` 進入點

自訂工具可以直接 :class:`MCPServer` 然後 :meth:`MCPServer.register`,
透過 :meth:`MCPServer.handle_message` 餵訊息(或直接呼叫
:func:`run` 跑 stdio 迴圈)。
