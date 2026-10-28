# 全專案程式審核 · 2026-10-28

基準提交 `34823f113e3a18b70feb55a03ef012e8376a39c8`。範圍包含現存程式，不限近期差異。前次 CR-01 至 CR-05 已修復；本報告的 FR 編號是另外發現的問題。

## 結論

初次審核確認 16 項問題，其中 P1 三項、P2 十三項。修復已整合，驗收進度見下方「修復驗收」；完整測試已通過，原生跨平台驗證及外掛發佈尚待完成。P1 表示優先處理的資料遺失風險；P2 表示有明確觸發條件的功能、生命週期或防護缺口。沒有確認 P0 問題，也不據此宣稱不存在。

初次審核只記錄問題；後續修復另附行為測試與驗收記錄。未將例外逸出等同整個行程崩潰，也未將模擬環境等同實機驗證。

## 範圍與方法

- 主程式 806 個 Python 檔、175,400 行；外掛 80 個檔、16,054 行；另盤點 972 個測試檔、163,767 行與 10 個開發腳本。
- 對主程式、外掛及腳本共 896 個 Python 檔完成 AST 解析，沒有語法錯誤。搜尋並整理 2,010 個候選 I/O、儲存、載入、刪除、子行程及等待呼叫。這是結構與風險搜尋覆蓋，不是 896 個檔案全部逐行人工審完。
- 人工深入追蹤涵蓋輸出交易、Paint 文件與匯出、工作執行緒、安裝與下載、設定檔、檔案搬移、資料庫清理、CLI／MCP、工作階段、Puppet 格式與錄影、桌寵資源生命週期及建置入口。每個發現核對呼叫端與錯誤處理。
- 分組覆蓋為介面／影像／Paint／匯出 584 檔；外掛／系統／設定／語言 149 檔；Puppet／桌寵 90 檔；其餘入口、資料庫、CLI／MCP、工作階段、巨集及腳本由整合審核處理。部分跨模組呼叫重複檢查。
- 所有重現使用暫存資料、背景子行程及 offscreen Qt。大型配置在實際配置前攔截，沒有耗盡記憶體；沒有碰觸使用者圖片、實際雲端檔案或攝影機。

## 發現摘要

| ID | 優先 | 問題 | 狀態 |
|---|---|---|---|
| FR-01 | P1 | 部分 Paint／MCP 匯出失敗會破壞既有目標 | 已修復，驗收中 |
| FR-02 | P1 | Puppet 動作名稱碰撞使批次輸出互相覆寫 | 已修復，驗收中 |
| FR-03 | P1 | 資料庫清理誤刪仍存在圖片的索引與附屬資料 | 已修復，驗收中 |
| FR-04 | P2 | pip 取消無法終止正在執行的子行程 | 已修復，驗收中 |
| FR-05 | P2 | 背景設定儲存覆蓋新建 profile | 已修復，驗收中 |
| FR-06 | P2 | 主視窗關閉未清理嵌入 Puppet／Pet 的工作 | 已修復，驗收中 |
| FR-07 | P2 | 錄影結尾寫入失敗仍回報儲存成功 | 已修復，驗收中 |
| FR-08 | P2 | 檔案搬移的存在檢查無法防止並行覆寫 | 已修復，驗收中 |
| FR-09 | P2 | 關閉 Auto-Tag 同步等待剩餘批次，阻塞 GUI | 已修復，驗收中 |
| FR-10 | P2 | 網頁相簿未編碼檔名 URL | 已修復，驗收中 |
| FR-11 | P2 | WebDAV 未編碼檔名 URL | 已修復，驗收中 |
| FR-12 | P2 | 損壞 Paint 文件的欄位例外穿出開啟錯誤處理 | 已修復，驗收中 |
| FR-13 | P2 | 損壞工作階段 JSON 的型別例外穿出開啟錯誤處理 | 已修復，驗收中 |
| FR-14 | P2 | VTS 未驗證訊息欄位型別，例外穿出 callback | 已修復，驗收中 |
| FR-15 | P2 | MCP frame 未限制輸出配置大小 | 已修復，驗收中 |
| FR-16 | P2 | 非 Windows frozen 啟動錯選 Windows OpenGL 平台 | 已修復，驗收中 |

## 詳細發現與驗收方向

### FR-01 · 匯出失敗破壞既有目標

位置 `Imervue/paint/animation_export.py:54-62`、`Imervue/paint/paint_project_export.py:51`、`Imervue/mcp_server/tools_edit.py:50-54`。Paint GUI 呼叫端為 `animation_dock.py:278` 與 `file_menu.py:479,500`；MCP writer 直接呼叫 `_save_image_to`，沒有 CLI 的 output-policy 包裝。

選取已有輸出並覆寫時，程式先截斷目標，再執行可能失敗的編碼／頁面合成。實際 GIF encoder 注入 OSError 後舊檔變成 0 bytes；CBZ 第一頁合成注入 MemoryError 後舊檔變成 22-byte 空 ZIP；MCP rotate 注入 encoder OSError 後舊 PNG 變成 `partial-image`。其他同樣直寫的格式只有原始碼證據，不聲稱都已實測。

驗收應在同目錄暫存檔完成全部輸出後原子替換，並證明寫入中途失敗時舊檔逐位元不變。證據 `.audit/repro-ui-export.py.txt`／`.log`、`.audit/repro-root-boundaries.py.txt`／`.log`。既有成功輸出測試未覆蓋舊檔保護。

### FR-02 · 批次動作輸出名稱碰撞

位置 `Imervue/puppet/batch_export.py:174-187`，由 `_record_next` 呼叫。`idle/01` 與 `idle:01` 都被轉成 `idle_01`；純中文名稱可能都變成 `motion`。未替整批保留唯一目的路徑。

使用真實 imageio、RecordingSession 與批次匯出器，僅以 QImage 畫面替代 GL canvas。紅／藍兩個動作完成後只剩一個藍色 GIF，但成功訊號列出兩筆相同路徑。

驗收應在啟動前配置不衝突的整批目的路徑，涵蓋中文、相同清理結果與既有檔案。證據 `.audit/repro-puppet-real-export.py.txt`／`.log`。

### FR-03 · 清理把未列出的檔案當成不存在

位置 `Imervue/library/maintenance.py:34-40`、`image_index.py:363-369`；GUI 入口 `Imervue/menu/right_click_menu.py:274-291`。

維護拿整個索引與指定資料夾的可見圖片清單做差集。隱藏圖片、已移除 library root 下的圖片，以及掃描失敗的資料夾內容，都可能被當成遺失。使用者同意「清除遺失」後，`delete_image` 同時刪除 notes、culling、image_tags；重新掃描不會恢復這些資料。

真實暫存 SQLite 與檔案重現顯示，隱藏圖片與範圍外圖片仍存在，但 prune 後索引均消失。另以實際移除 root、設定 note／pick／tag 後呼叫維護，確認檔案仍在，note 變空、pick 變 unflagged、tag 數從 1 變 0，證據 `.audit/repro-root-maintenance-metadata.py.txt`／`.log`。GUI 通常傳全部已登錄 roots；範圍外情境包括移除 root 後仍留下的舊索引，並非宣稱每次維護只傳目前資料夾。

驗收應區分不在掃描範圍、被隱藏、無權存取與確認不存在，只有確認遺失者可刪除附屬資料。證據 `.audit/repro-root-boundaries.py.txt`／`.log`；現有 `tests/test_maintenance.py` 只測真正缺檔。

### FR-04 · pip 子行程不受取消控制

位置 `Imervue/plugin/pip_installer.py:479-505`。`Popen` 存在區域變數 `proc`，從未指定給 `self._proc`，所以 `stop()` 呼叫 `terminate_process(None)`。stdout 迴圈先等 EOF，後面的 `wait(timeout=600)` 不能限制沒有輸出的卡住子行程。

真實 QThread 與隱藏子行程在 stop 後仍存活，worker 也未結束。驗收應持有與回收子行程、處理啟動競態，並讓逾時涵蓋 stdout 消費期間。證據 `.audit/repro-plugins-pip-cancel.py.txt`／`.log`。既有測試替換整個 subprocess 方法，未涵蓋此路徑。

### FR-05 · 設定 profile 的讀改寫競態

位置 `Imervue/user_settings/user_setting_dict.py:100-117,219-234`。背景 save 已讀到舊 profiles 後，GUI 建立新 profile；舊 save 再寫回舊 map，刪掉新 profile。取消 timer 無法取消已開始的 callback；原子檔案替換不等於完整交易序列化。

實際暫存 JSON 從 `default, client` 回到只剩 `default`，UI 仍列兩個。驗收需序列化快照、profile 狀態與整次讀改寫，並測建立、切換、刪除與背景 save 重疊。證據 `.audit/repro-plugins-profile-race.py.txt`／`.log`。

### FR-06 · 主視窗清理漏掉嵌入工作區

位置 `Imervue/Imervue_main_window.py:594,635-682`、`Imervue/puppet/workspace.py:486-509`。嵌入頁面不會因父視窗關閉收到自己的 closeEvent；主視窗已替 Paint 特別處理，但 release 未呼叫 Puppet／Pet 的清理。另一視窗仍開啟時，關閉視窗會 deleteLater，背景工作可能繼續引用已刪除物件。

執行實際 `_release_for_close`，以完整 stand-in 主視窗、可清理子工作區及真實可停止 Python thread 驗證，子工作區清理沒有被呼叫，thread 仍存活。這證明整合入口缺口，未實測攝影機或聲音裝置。Puppet 自身 shutdown 也應盤點 VTS 與錄影器。

驗收應由父視窗統一停用所有 live drivers、錄影與服務，測次要視窗關閉後其他視窗仍可操作，且沒有遺留工作。證據 `.audit/repro-puppet-parent-release.py.txt`／`.log`、`.audit/repro-puppet-shutdown.log`。

### FR-07 · 錄影完成訊號不區分失敗

位置 `Imervue/puppet/recorder.py:166-179`；消費端 `workspace_live.py:77-85`、`batch_export.py:158-164`。writer.close 拋錯後只記錄，仍無條件發出 finished(path)。append 失敗還會先走成功 stop 再發 failed。

注入 close OSError，實測 finished 含 `failed.gif`，failed 為空。驗收需成功與失敗互斥，批次不得把失敗輸出列為成功或在錯誤尚未處理時前進。證據 `.audit/repro-puppet-findings.py.txt`／`.log`。

### FR-08 · 搬移檔案的檢查與寫入有時間差

位置 `Imervue/system/file_transfer.py:56-61,88-96`。確認不存在後呼叫可覆寫的 shutil.move。若其他寫入者在這段空隙建立同名檔案，仍會被覆蓋。

以兩條 thread 同步呼叫實際 helper、只暫停在系統搬移前重現，兩個 move 都成功、兩個來源都消失，目的地只剩一張。同程序 GUI 呼叫目前同步執行；實際適用情境是不同程序或外部檔案寫入者，這項跨程序適用性由程式碼推得，未啟動兩個完整 GUI 程序。記錄中的 copy 案例因 Windows sharing violation 只成功一筆，不能宣稱同樣重現 copy 資料遺失。

驗收需跨程序有效的排他目的檔建立／不覆寫提交，並包含跨磁碟路徑。證據 `.audit/repro-plugins-transfer-race.py.txt`／`.log`。

### FR-09 · Auto-Tag 關閉阻塞 GUI

位置 `Imervue/gui/auto_tag_dialog.py:124-129,158,164`；批次迴圈 `Imervue/library/auto_tag.py:145-153`。GUI thread 呼叫無期限 wait，quit 不能中止分類迴圈。

真實 QThread 的批次以 Event 阻擋，呼叫 reject 後必須等另一 thread 放行才返回，期間已排程 GUI timer 未執行。這是同步控制實驗，不是效能基準。

驗收應檔案間合作取消、非阻塞退休，並保留工作物件直到結束。證據 `.audit/repro-ui-review.py.txt`／`.log`。現有測試用立即返回的 fake wait，無法檢出。

### FR-10 · 相簿 URL 未編碼

位置 `Imervue/export/web_gallery.py:175,206,240`。HTML escaping 不會把檔名中的 `#` 轉成 URL 路徑字元。實際匯出 `a#b.png` 後縮圖與原圖存在，但瀏覽器解析的路徑在 `#` 前截斷。

驗收應先 percent-encode 每個路徑段，再做 HTML escaping，涵蓋 `#`、`%` 與 Unicode。證據 `.audit/repro-ui-review.py.txt`／`.log`，包含真實相簿輸出與 URL 解析，未宣稱操作實際瀏覽器。

### FR-11 · WebDAV URL 未編碼

位置 `plugins/cloud_share/uploaders.py:43-58`。檔名直接拼入 URL，空白與中文導致 HTTP serializer 例外，`photo#1.png` 只請求 `/photos/photo`，可能指向錯誤遠端資源。

重現使用真實 Request 與 stdlib HTTPConnection.putrequest 序列化，沒有連線或上傳。驗收應對檔名作單一路徑段編碼，保留使用者設定的 collection URL。證據 `.audit/repro-plugins-webdav-names.py.txt`／`.log`。

### FR-12 · Paint 文件欄位驗證不足

位置 `Imervue/paint/document_io.py:254-256`、`document_files.py:94-100`。有效 NPZ 內 metadata 缺 width 時拋 KeyError，開啟端只接 OSError、ValueError、MemoryError，正常錯誤提示未執行。

使用實際 NPZ 與 DocumentFiles.open 重現。驗收應在格式邊界驗證必要欄位與型別，將格式錯誤轉成明確 ValueError，保留既有文件。證據 `.audit/repro-ui-review.py.txt`／`.log`。不宣稱行程崩潰或程式執行漏洞。

### FR-13 · 工作階段 JSON 型別驗證不足

位置 `Imervue/sessions/session_manager.py:110-138`；GUI 捕捉範圍 `Imervue/menu/file_menu.py:489-495`。頂層 `[]` 進錯誤訊息時再次呼叫 `.get`，拋 AttributeError；`tabs:42` 或 `selection:42` 拋 TypeError，兩者都不在開啟端捕捉範圍。

驗收應明確驗證 object/list/string 等結構，錯誤均經正常載入失敗提示，不改動現有工作階段。證據 `.audit/repro-root-boundaries.py.txt`／`.log`。

### FR-14 · VTS 訊息欄位型別未驗證

位置 `Imervue/puppet/vts_api.py:94-105,373-381`。`messageType:[]` 導致不可 hash，AuthenticationTokenRequest 的 `data:["bad"]` 導致 `.get` 例外。Qt callback 只處理 JSON 解碼錯誤，因此有效 JSON 仍可逸出且不回覆協定錯誤。

重現直接 handler 與實際 `_on_text`，socket 為 stand-in。需已連上的本機／允許來源 client，不宣稱遠端任意來源、程式碼執行或整個程式崩潰。驗收應在入口驗證欄位並回傳協定錯誤。證據 `.audit/repro-puppet-findings.py.txt`／`.log`。

### FR-15 · MCP frame 未限制輸出像素

位置 `Imervue/mcp_server/tools_edit.py:104-134`、`Imervue/image/photo_frame.py:46-50`。其他 MCP resize／collage 會檢查 100 MP 上限，frame 沒有；schema 也只限制最小值。

2×2 輸入、border=50000 可抵達 100002×100002 RGBA 配置，僅畫布即約 40 GB，後續轉陣列還會複製。以真實呼叫鏈在 Image.new 前攔截，未實際配置。這會使同步 MCP／CLI 工作受不合理輸入拖垮，不是無需連線的遠端攻擊。

驗收應在配置前按最終幾何檢查一致上限，包含 border 與 bottom_extra。證據 `.audit/repro-root-boundaries.py.txt`／`.log`。

### FR-16 · frozen 非 Windows 啟動選錯 OpenGL 平台

位置 `Imervue/__main__.py:7-10`。只要 frozen／compiled 就把未設定的 PYOPENGL_PLATFORM 設為 nt，未檢查作業系統。`Imervue_mac.spec` 與 `pyinstaller.md` 明確提供 macOS 打包入口，但 PyOpenGL 因此優先選 Windows 實作。

在獨立程序模擬 `sys.platform=darwin, sys.frozen=True`，實際入口將環境設為 nt，已安裝 PyOpenGL 選出 Win32Platform。其實作依賴 Windows ctypes／OpenGL DLL。未在真實 macOS／Linux frozen 產物上重現，確認的是平台選擇錯誤，實機啟動失敗由依賴程式碼推得。

驗收應只在 Windows 設定 nt，並在 macOS／Linux 打包環境驗證啟動。證據 `.audit/repro-root-frozen-platform.py.txt`／`.log`。

## 驗證結果與證據限制

- 應用程式自完整測試後沒有改動，沿用該次結果 14,357 passed、1,431 skipped，沒有重新宣稱本次跑過完整套件。記錄 `.audit/code-review-full-tests.log`。
- 本次重新執行 Ruff 與 Bandit 均通過。Bandit 依專案設定執行，含既有排除／抑制規則，不代表沒有安全或資料遺失問題。
- 本次針對性既有測試為根模組 102 passed、介面／匯出 69 passed、Puppet 29 passed／12 skipped。Puppet 的 12 個顯示環境跳過未當成通過；另外以 offscreen 重現程式驗證上述行為。
- 重現檔與原始 log 在本機 `.audit/`，沒有納入版本控制。報告記錄觸發步驟、錯誤注入方式與預期驗收，避免只依不可攜的 log 判定。
- 未逐行人工審完所有模組。未執行實際 GPU／多平台裝置 teardown、可選 AI 模型推論、真實雲端服務、SDK 內部、全 Paint 工具幾何或所有語言文案。第三方／vendor SDK、產生檔與建置輸出不屬於第一方原始碼審核範圍。沒有進行依賴漏洞資料庫稽核。

## 修復順序

先處理 FR-01～FR-03 的資料保護，再處理 FR-04～FR-09 的取消、儲存競態與生命週期，最後處理 URL、格式邊界及平台選擇。每項修復以本報告的重現條件新增行為測試，通過完整專案 gates 後才能結案。外掛變更仍須依 CLAUDE.md 同步發佈庫。

## 獨立複核

另由獨立審核者重讀證據與相關呼叫端，並重跑根模組重現程式。接受上述發現，要求保留失敗注入、平台模擬與未驗證硬體的限制；搬移／複製實測差異已修正。詳見本機 `.audit/full-review-independent.md`。

審核完成後查詢目前分支 PR，沒有對應 PR，因此沒有外部 review-bot 討論可供比對。此次未推送或部署任何程式變更。

## 修復驗收（2026-10-28）

下列修復以初次重現失敗為基準，新增可重跑的 regression tests。歷史發現中的行號與重現結果保留，代表修復前版本。

| ID | 修復與驗證 |
|---|---|
| FR-01 | Paint GIF／WebP／APNG、CBZ／PDF 與 MCP 輸出共用同目錄暫存及原子替換；注入編碼／合成失敗後既有目標逐位元不變，含 MCP 同來源覆寫。 |
| FR-02 | 批次啟動前保留整組唯一目的檔名，包含既有檔案、中文、符號清理及大小寫碰撞；實際 GIF 編碼後紅／藍動作各自保留。 |
| FR-03 | 只清理可讀掃描範圍內、lstat 確認不存在的索引；隱藏、移除 root、權限失敗及範圍外圖片的 note／pick／tag 均保留。 |
| FR-04 | 安裝 worker 持有 Popen，取消與逾時會終止並回收直接子行程；逾時涵蓋 stdout 消費，實際子行程測試包含啟動競態。 |
| FR-05 | RLock 涵蓋設定快照、profile 狀態及整次讀改寫；建立／刪除／改名／切換與背景儲存交錯均有 barrier 測試。 |
| FR-06 | 主視窗主動呼叫嵌入 Puppet／Pet 的冪等 shutdown，停用 driver、錄影器、計時器及服務；次要視窗關閉保留另一視窗。攝影機讀取可能延後返回，取消後不再碰觸 Qt 物件，返回後釋放資源；以阻塞 capture 替身與已銷毀 QObject 驗證，未使用真實裝置。 |
| FR-07 | writer append／close 失敗只發 failed，成功只發 finished；先清除錄影狀態，避免批次提前前進。 |
| FR-08 | 搬移使用不覆寫 rename 或暫存副本的排他發布，無 hardlink 時以 xb 建立目標；兩個程序與強制跨磁碟路徑驗證只有一方成功。失敗不刪來源；退路可能留下不完整目的檔。 |
| FR-09 | Auto-Tag 使用 WorkerHostMixin 退休工作執行緒，取消在圖片之間生效，關閉不再同步等待剩餘批次；實際 Qt event loop 驗證。 |
| FR-10 | 相簿的檔名先作 URL path segment 編碼，再作 HTML escaping；產出 HTML 的特殊字元連結可還原原檔名。 |
| FR-11 | WebDAV 上傳與分享 URL 編碼檔名元件，保留 collection query／fragment；測試請求 URL，未呼叫真實雲端服務。 |
| FR-12 | Paint 文件／buffer 入口把損壞欄位例外轉為 ValueError，尺寸必須為正整數；實際損壞 NPZ 測試。 |
| FR-13 | Session 入口驗證 JSON object 與 tabs／selection 容器，錯誤由既有 GUI 錯誤處理接住。 |
| FR-14 | VTS 入口驗證訊息、data、參數容器與數值，無效輸入回 APIError；後續合法認證請求仍可處理。 |
| FR-15 | MCP frame 在配置前依 border 與 bottom_extra 的最終尺寸檢查 100 MP 上限。 |
| FR-16 | frozen／compiled 初始化只在 Windows 預設 nt，保留使用者設定；本機 Windows PyInstaller 真實 executable 通過。Ubuntu／macOS 原生封裝及 OpenGL.GL 匯入由 frozen-startup.yml 驗證，尚待 CI 結果。 |

主要測試位於 `tests/test_full_review_boundaries.py`、`tests/test_full_review_ui_failures.py`、`tests/test_full_review_runtime.py`、`tests/test_review_puppet_fixes.py` 與 `tests/test_frozen_startup_probe.py`。整合針對性測試 99 passed；完整套件 14,447 passed、1,431 skipped、6 個 imageio fps 棄用警告，exit 0。跳過數與基準相同。Ruff 通過，Bandit 無問題；文件與 CI 針對性檢查 108 passed。第一輪完整測試發現舊 Auto-Tag 測試綁定已移除的實作，改以真實 worker 的 Esc／關閉按鈕行為驗證後重跑完整套件通過。記錄 `.audit/full-review-fixes-full-tests-final.log`。

兩組獨立複核接受整合修復；大小寫目的路徑碰撞的追加修正已由複核者重跑真實 encoder。原生 frozen probe 僅涵蓋未修改應用入口的初始化與原生 OpenGL 匯入，不代表完整 GUI 或 GPU rendering 驗證。初次審核列出的其他證據限制仍適用。
