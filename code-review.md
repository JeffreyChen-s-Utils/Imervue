# 程式審核：Imervue

## 審核者

工作區程式審核。日期：2026-10-22。對象：`Imervue`（套件 `Imervue/`，外掛抽樣 `plugins/`）。原始結論：有條件通過。2026-10-28 已修復 CR-01 至 CR-05，結案驗證見文末。

## 審核規範

共通規範在工作區 repo [JE-Chen/Codes](https://github.com/JE-Chen/Codes) 的 `docs/code-review-standard.md`。下面留下 2026-10-22 這次審核所用的條款，讓審核紀錄的依據對得上那一次。之後的審核以工作區那份為準。本專案更嚴的條款仍以本節與本專案的 `CLAUDE.md` 為準。

以下十條為本次判定基準。專案已寫明且更嚴者從嚴，其餘用括號內的預設。

1. 設計：純邏輯與 Qt 殼分層；入口與擴充點以 `architecture.md` §2、§3、§5 為準，不把外掛專用依賴拉進主程式。
2. 可讀性：函式長度 ≤ 80（含 docstring）、檔案 ≤ 1000、圈複雜度 ≤ 15、位置參數 ≤ 7（`self`／`cls` 不計）。未另行加嚴的巢狀 ≤ 4、行寬 ≤ 120。
3. 錯誤處理：該接的例外要記錄或再拋；工作執行緒邊界須仍發出結果。禁止寬捕捉後既不記錄也不使用例外。
4. 死碼：綁了卻從未呼叫、註解掉的實作、殘留 `TODO`／`FIXME`／`XXX`，視範圍列為發現或備註。
5. 型別與 docstring：公開函式與類別應有型別標註與一行說明。熱點審核不逐一計分。
6. 安全：子行程不得經 shell 組字串；不得 `eval`／`exec` 使用者文字；不得 `pickle`、`yaml.load`、`allow_pickle=True`、`verify=False`。使用者路徑不可穿越安裝目錄。外掛與模型下載只走 HTTPS，模型要釘修訂或雜湊。
7. 測試：本次不執行測試。只看熱點旁是否已有可隔離的失敗路徑（記錄、回退、拒絕），不把「未跑」當成失敗。
8. 效能：只記會卡住取消或洩漏子行程的路徑，不評測畫質或速度。
9. §6 外掛契約：下載器只收安全路徑元件與 `plugins`／`languages`；`WorkerHostMixin` 的取消鉤子只能動旗標或子行程，且須真的停掉子行程；GPU 顯影失敗應回到 CPU，不得拖垮匯出。
10. 文件同步：只在抽樣行為與 `architecture.md` §6 或 `CLAUDE.md` 的安全、長度、外掛契約相違時才列。不核對十語文件。

嚴重度：缺陷（未關閉則結論不得為通過）、建議、備註。通過＝無未關閉缺陷。有條件通過＝無立即損害。需修正＝有未關閉缺陷。

## 審核紀錄

### 方法

2026-10-22 工作樹熱點審核，不是逐行審完整個樹。先讀 `architecture.md` 的分層、入口與 §6，以及 `CLAUDE.md` 裡安全、長度、外掛契約、靜默例外與網路供給鏈段落。`progress.md` 的 Open 為空，沒有未竟安全項。

套件以 `Imervue/` 為主，外掛只抽有子行程或 GPU 邊界者。排除 `build/`、`dist/`、`__pycache__`、`docs/_build/`、`sdk/` 大量原生樹、`.idea`，測試目錄不展開。

在 `Imervue/**/*.py` 與 `plugins/**/*.py` 搜尋 `eval(`、`exec(`、`shell=True`、`pickle`、`yaml.load`、`verify=False`。`exec(` 幾乎全是 Qt 的 `.exec()`，不是動態執行。去掉之後，套件與外掛都沒有 `shell=True`、`eval(`、`pickle.`、`yaml.load`、`verify=False`、`allow_pickle=True`。子行程集中在少數檔，因此深讀這些熱點（超過八個，因為真正的命中不多，但每一則發現都先讀過原文）：

- `Imervue/plugin/plugin_manager.py`、`plugin_downloader.py`、`pip_installer.py`、`pip_constraints.py`、`python_finder.py`、`installation.py`、`subprocess_util.py`、`worker_host.py`、`worker_retirement.py`
- `Imervue/external/editors.py`、`Imervue/system/file_manager.py`、`wallpaper.py`、`local_llm.py`、`local_origin.py`
- `Imervue/gui/gif_video_dialog.py`、`Imervue/image/develop_backends.py`、`Imervue/puppet/cubism_native_bridge.py`、`document_io.py`（載入段）
- `plugins/ai_background_remover/ai_background_remover.py`、`plugins/object_splitter/object_splitter.py`（子行程段）、`plugins/safety_review/_workers.py`（子行程段）、`plugins/gpu_develop/renderer.py` 與 `gpu_develop_plugin.py`、`plugins/pet_integrations/webhook_server.py`、`plugins/cloud_share/uploaders.py`

### 總評

抽樣路徑沒有 shell 注入、動態 `eval`、或不安全的反序列化。外掛下載拒絕 `..` 與 Windows 非法檔名，安裝有階段目錄與失敗回滾。外部編輯器與檔案總管以參數陣列或已加引號的固定命令啟動，`shell` 維持預設關閉。GPU 顯影在算繪時把裝置錯誤包成 `RuntimeError`，批次匯出改走 CPU。原生 Cubism 在復活或初始化回傳空指標時會丟明確錯誤。

原始審核認為這些項目不是立即損害：取消 MP4 時不會殺掉 ffmpeg；去背子行程在例外路徑不會回收；本機 webhook 把 `Origin: null` 當成允許，與「擋遠端網頁」的目標不一致。沒有缺陷，故不列需修正。

#### CR-01

- 位置：`Imervue/gui/gif_video_dialog.py` `_CreateWorker.abort`（約 70–72 行）、`_create_video`（約 164–185 行）；對照 `Imervue/plugin/worker_retirement.py`（約 47–57 行）與 `worker_host.py`。
- 說明：對話框繼承 `WorkerHostMixin`。取消會呼叫 `abort()`，但該方法只把 `_abort` 設為真。影格迴圈會看這個旗標；接著的 `subprocess.run`（ffmpeg，`timeout=300`）不會。退休執行緒呼叫 `abort()` 之後無逾時地 `wait()`，編碼階段取消會一直停在「Cancelling…」，最長約 300 秒，也不會殺掉 ffmpeg。
- 依據：審核規範 3、8、9。§5／§6 要求取消鉤子停掉子行程，且不碰 GUI。
- 狀態：已關閉（2026-10-28）。嚴重度：建議。
- 建議：改為持有 `Popen`，在 `abort()` 裡走現成的 `terminate_process`（`Imervue/plugin/subprocess_util.py`）。`run` 的逾時只當最後保險。
- 修復與證據：改用持有的 `Popen`，取消及 `finally` 均回收編碼行程，並處理啟動期間取消。`tests/test_review_worker_processes.py` 使用實際子行程驗證取消、啟動競態、逾時及管線例外，確認行程結束與結果訊號。


#### CR-02

- 位置：`plugins/ai_background_remover/ai_background_remover.py` `_SubprocessRemoveWorker.run`（約 129–168 行）、`_SubprocessBatchWorker.run`（約 193–241 行）。對照 `plugins/object_splitter/object_splitter.py`（約 146–149 行）與 `plugins/safety_review/_workers.py`（約 371–391、477–502 行）。
- 說明：去背兩個子行程工作者在 `stop()` 會終止子程序，但 `run()` 的 `except` 只記錄並發出失敗。批次的 `finally` 只刪暫存路徑清單，不呼叫 `terminate_process`。執行緒若已結束，`WorkerHostMixin` 不會再呼叫 `stop()`。例外若發生在讀 stdout 途中，子程序可能繼續跑，管線寫滿後還會堵住。自帶的 `_rembg_runner.py` 進度行可被拆成整數，正常協定不會走到這條；缺口在例外路徑，不是日常成功路徑。
- 依據：審核規範 3、8、9。
- 狀態：已關閉（2026-10-28）。嚴重度：建議。
- 建議：與另外兩個外掛相同，在 `finally` 呼叫 `terminate_process`。
- 修復與證據：單張與批次去背在 `finally` 終止並清除子行程，批次仍清理暫存清單。`tests/test_review_worker_processes.py` 驗證 stdout 讀取失敗及錯誤進度資料後，實際子行程均已回收。


#### CR-03

- 位置：`Imervue/system/local_origin.py` `is_allowed_origin`（約 16–28 行）；`plugins/pet_integrations/webhook_server.py` 說明（約 26–34 行）與 `do_POST`（約 187–193 行）。
- 說明：接收器只綁迴圈介面，有本文長度上限，並在設了 bearer 時核對授權。沒有 `Origin`、`null`、`file` 與非網頁 scheme 都放行，用意是本機工具與本機檔案頁。沙箱頁或獨特來源也會送 `Origin: null`。權杖預設空字串時，這類請求會通過，並可叫寵物播動作或說話。傷害限於寵物表面，不是讀寫任意檔或起 shell。
- 依據：審核規範 6、9（桌面寵物外掛表面與 `is_allowed_origin`）。
- 狀態：已關閉（2026-10-28）。嚴重度：建議。
- 建議：預設權杖為空時拒絕 `null`，或把 `null` 與「沒有 Origin」分開；本機檔案頁改用明確的 `file` scheme。文件要寫明沙箱頁與這條約定的關係。
- 修復與證據：區分缺少 Origin 與字面值 `null`，後者即使帶有效權杖仍拒絕；拒絕空白與無效 URL／埠。保留既有本機與非網頁 scheme 政策，不宣稱完整 Origin 語法驗證。`tests/test_local_origin.py`、`tests/test_pet_integrations_webhook_server.py` 與 `tests/test_puppet_vts_origin.py` 涵蓋共用規則、實際迴圈 HTTP 請求及 VTS 握手。十語 README／Sphinx 說明瀏覽器本機檔案可能送出 null，應改由 localhost 提供頁面。


#### CR-04

- 位置：`plugins/gpu_develop/renderer.py` `probe`（約 80–88 行）、`render`（約 154–159 行）；`plugins/gpu_develop/gpu_develop_plugin.py` `_report`（約 93–98 行）；`Imervue/image/develop_backends.py` `available`／`render`（約 87–97、121–136 行）。
- 說明：算繪路徑會把 wgpu 錯誤包成 `RuntimeError`，`develop_backends.render` 再改走 CPU。`probe()` 只捕捉 `ImportError`。選單狀態直接呼叫 `probe()`。`available()` 另外捕捉 `RuntimeError` 與 `OSError`。枚舉配接器若丟出這三類以外的例外，選單與列舉都接不住。本次沒有載入 wgpu，不指定實際例外型別。
- 依據：審核規範 3、9。`renderer.py` 模組說明寫明 wgpu 失敗應成為 `RuntimeError` 並由 CPU 接手；這句涵蓋算繪，沒有涵蓋探測。
- 狀態：已關閉（2026-10-28）。嚴重度：建議。
- 建議：`probe()` 與 `_report()` 捕捉與 `available()` 相同的一組，失敗時回傳沒有裝置並寫日誌，不要讓驅動例外穿出選單槽。
- 修復與證據：`probe()` 在依賴初始化、裝置枚舉與資訊讀取處接住 ImportError、RuntimeError、OSError 及 wgpu 裝置錯誤，回傳無裝置並記錄驅動失敗。`tests/test_gpu_develop_renderer.py` 與 `tests/test_gpu_develop_plugin.py` 驗證預期錯誤、選單狀態及 CPU 可用性；程式錯誤 ValueError 仍向外傳遞。


#### CR-05

- 位置：`Imervue/puppet/cubism_native_bridge.py`。`csmHasMocConsistency` 綁在約 161 行；`CubismModel.__init__` 約 280–300 行只在 `csmReviveMocInPlace` 與 `csmInitializeModelInPlace` 回傳空指標時丟 `CubismBridgeError`。全套件沒有其他呼叫點。
- 說明：空指標有處理，簽名也有綁。一致性檢查從未執行。不一致的 moc 若在原生函式裡直接終止行程，Python 的 `except` 接不到。這是原生邊界的防禦缺口，不是已重現的崩潰。
- 依據：審核規範 3、4。
- 狀態：已關閉（2026-10-28）。嚴重度：備註。
- 建議：復活前記得呼叫 `csmHasMocConsistency`，結果為否就丟 `CubismBridgeError`，不要把位元組交給原生復活。
- 修復與證據：對已對齊且存活的 moc 緩衝區先呼叫 `csmHasMocConsistency`，為否即拋出 CubismBridgeError，不呼叫 revival。`tests/test_puppet_cubism_native_bridge.py` 以替代原生函式驗證順序、對齊、緩衝區生命週期及既有初始化失敗；沒有將損壞模型交給實際 vendor 函式來驗證崩潰。


### 已核對

- 動態執行與反序列化：套件與外掛原始碼沒有 `eval(`、`shell=True`、`pickle` 載入、`yaml.load`、`verify=False`、`allow_pickle=True`。繪圖與語意搜尋載入 NumPy 時明確 `allow_pickle=False`。Qt `.exec()` 是對話框迴圈。
- 子行程：`python_finder._verify_python`、`pip_installer` 的 pip、外部編輯器、檔案總管、桌布、去背、物件分割、安全審查，都是參數列表。桌布在 macOS 把路徑放在 `osascript` 的 argv，不拼進腳本文字。檔案總管在 Windows 把路徑放進引號，因為 Explorer 以逗號與 `=` 切欄。
- 使用者路徑與外掛載入：`is_safe_path_component` 拒絕空名、`.`、`..`、分隔字元、控制字元與 Windows 不允許的字元。下載 URL 由固定的 HTTPS 基底加上已引用路徑組成，送出前再檢查 scheme。安裝先寫階段目錄，提交失敗會把舊目錄換回。嵌入式 Python 與 pip wheel 有 SHA-256。`plugin_manager` 在匯入、建構與各 hook 捕捉例外並寫日誌，單一外掛失敗不會中斷其餘載入。外掛仍在行程內執行，這是既有模型，不是沙箱。
- 網路：`plugin_downloader`、`pip_installer`、`webcam_tracker`、`cloud_share` 的 `urlopen` 都先拒絕非 HTTPS。人臉模型下載比對固定雜湊。抽樣的 Hugging Face 呼叫帶 `revision`（放大、CLIP、安全審查）。`local_llm.validate_base_url` 只允許任意 HTTPS，以及迴圈主機上的 HTTP。
- `.puppet` 載入進記憶體，並以標頭宣告的未壓縮總量設上限，沒有把壓縮項目解到任意路徑。
- GPU 畫筆初始化失敗會 `dispose` 再拋出。檢視器一幀繪製失敗會記錄並留住畫面。RAW 開啟失敗會關掉 libraw 把手再拋出。

### 原始審核未涵蓋

未跑測試、lint 或 bandit，未啟動 GUI。未讀 `tests/`、`build_nuitka/`、`docs/_build/`、`sdk/` 內大量原生原始碼、其餘外掛的純影像運算、MCP 每個工具的路徑實作、以及十語 README。沒有逐函式量複雜度、巢狀與行寬。§6 其餘名稱（選單 object name、`ToolDialogMixin` 屬性、FrontEngine 匯入）只依文件記錄，沒有對下游倉庫。

### 本專案加嚴

相對預設規範，本次採用 `CLAUDE.md` 已寫明且更嚴的條目：檔案 ≤ 1000、函式 ≤ 80、圈複雜度 ≤ 15、位置參數 ≤ 7、禁止靜默吞例外、禁止把檔案 unpickle、`urlopen` 必須經 HTTPS 守衛、Hugging Face 必須釘修訂、外掛取消與下載契約以 `architecture.md` §6 為準。行寬 120 與巢狀 4 沒有被專案改得更嚴，本次只在熱點裡目視，沒有全樹計數。

### 結論

2026-10-22 原始審核為有條件通過，列出建議 4 則與備註 1 則。2026-10-28 的修復已關閉 CR-01 至 CR-05；這是對原列五項的結案，不是重新審核整個程式庫。

### 2026-10-28 結案驗證

- 針對性整合測試 265 passed；完整 `pytest tests/ -q -o faulthandler_timeout=90` 為 14,357 passed、1,431 skipped，跳過數與前次基準相同。
- `ruff check .` 通過；`bandit -c pyproject.toml -r Imervue/ plugins/` 無問題；十語文件結構測試 22 passed。
- 獨立程式審核未發現阻擋結案的問題。上述原生一致性檢查測試使用替代函式，驗證 Python 呼叫契約，不宣稱已實測 vendor 原生庫處理損壞模型的行為。

### 後續全專案審核

2026-10-28 另完成[全專案範圍審核](docs/reviews/2026-10-28-full-review.md)。FR-01 至 FR-16 已修復並依報告驗收結案，原 CR-01 至 CR-05 維持關閉。完整本機測試 14,447 passed、1,431 既有 skips；原生 Windows／Linux／macOS frozen 匯入與外掛發佈均已確認。這是已確認問題的結案，不是完整程式沒有其他缺陷的保證。
