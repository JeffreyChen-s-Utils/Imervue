# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

### 第二階段：效能基準、操作回應與記憶體（P1）

- **#68** 工作取消與對話框關閉可能長時間阻塞 UI：`Imervue/plugin/worker_host.py` 的停止流程同步等待 worker 完成。
  下一步：量測不可立即中斷的解碼、推論及 I/O；補執行中取消／關閉／再次開啟測試，顯示取消狀態並以完成訊號協調釋放，保留 worker 與宿主生命週期。

- **#69** 缺少跨工作區、異常結束及真實 OpenGL 的完整回歸流程：`tests/` 與 `.github/workflows/test.yml`。
  下一步：補編輯切頁、多文件恢復、執行中關閉及損壞圖片／磁碟滿／無寫入權限流程；獨立安排真實 GL 測試，涵蓋貼圖淘汰、縮放、多視窗及資源釋放。

### 第三階段：一致的功能流程與狀態（P2）

- **#70** 匯出、索引、AI 處理及下載的工作狀態分散於各對話框：`Imervue/gui/`、`Imervue/library/scanner.py`、`Imervue/plugin/`。
  下一步：盤點現有進度與取消介面，建立共用工作狀態及背景工作面板，提供失敗明細、取消狀態與只重試失敗項目，驗證重試不重複處理已完成輸出。

- **#71** 文件來源、髒狀態、保存位置及最後自動儲存狀態缺少一致呈現；Paint 多文件關閉流程尚缺「儲存全部」：`Imervue/paint/workspace_tabs.py`、`Imervue/paint/workspace_status.py`。
  下一步：統一文件狀態顯示並補儲存全部流程，區分可繼續編輯的原生文件與扁平輸出；驗證儲存後 Undo／Redo 會重新標記修改，取消選檔或保存失敗時不清除髒狀態、不關閉未保存文件。

- **#72** 搜尋、比較、挑片、顯影及批次輸出的選取集合與預設缺少連貫流程：`Imervue/library/`、`Imervue/gui/`。
  下一步：以「搜尋 → 比較 → 保留／拒絕 → 套用顯影 → 批次輸出」建立整合案例，沿用同一選取集合與既有預設，驗證過濾、跨資料夾與返回上一步時的狀態。

- **#73** 各輸出入口的檔名衝突、metadata、色彩描述檔、覆寫與結果回報需要一致性稽核：`Imervue/export/`、`Imervue/gui/batch_export_dialog.py`、`Imervue/cli.py`。
  下一步：盤點 GUI／CLI／批次工具的差異，建立共用輸出政策及可點擊的成功／失敗結果；補同名來源、部分失敗、取消及 metadata 保留的跨入口測試。

- **#74** 外掛相依、模型下載、運算後端與失敗回復資訊缺少一致呈現：`Imervue/plugin/`、`plugins/`。
  下一步：盤點各外掛現有能力與降級流程，提供一致的可用／缺相依／下載中／失敗狀態及原因；驗證重試、重載及多視窗，實作外掛變更時同步發佈來源。

### 後續階段：依基準結果安排（P3）

- **#75** 大量縮圖磁碟快取在啟動路徑同步盤點：`Imervue/image/thumbnail_disk_cache.py:88`、`:244`；固定基準見 `docs/performance/baseline-20261007.md`。
  下一步：依基準門檻改為背景盤點或持久化索引，驗證盤點期間讀寫、配額與舊快取清理的一致性。

- **#76** [UNVERIFIED] 圖庫背景掃描與前景搜尋／標籤修改共用 SQLite 連線，需驗證並行交易行為與延遲：`Imervue/library/image_index.py:145`、`:182`、`Imervue/library/scanner.py:190`。
  下一步：壓測掃描同時搜尋與寫入、批次回滾及關閉；依結果決定獨立讀取連線與單一寫入佇列，並保持既有 schema、WAL 與批次交易能力。

- **#77** GPU 即時顯影與進階色彩流程仍需評估，現有 GPU Develop 後端主要服務批次輸出：`plugins/gpu_develop/`、`Imervue/image/develop_backends.py`。
  下一步：先完成 #62、#63 的量測與預覽改善，再評估沿用既有後端的收益；建立 CPU／GPU、預覽／匯出的色彩及像素一致性案例，確認降級與模型外掛邊界後安排實作。
