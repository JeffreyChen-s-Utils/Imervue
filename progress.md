# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

### 第三階段：一致的功能流程與狀態（P2）

- **#74** 外掛相依、模型下載、運算後端與失敗回復資訊缺少一致呈現：`Imervue/plugin/`、`plugins/`。
  下一步：盤點各外掛現有能力與降級流程，提供一致的可用／缺相依／下載中／失敗狀態及原因；驗證重試、重載及多視窗，實作外掛變更時同步發佈來源。

### 後續階段：依基準結果安排（P3）

- **#75** 大量縮圖磁碟快取在啟動路徑同步盤點：`Imervue/image/thumbnail_disk_cache.py:88`、`:244`；固定基準見 `docs/performance/baseline-20261007.md`。
  下一步：依基準門檻改為背景盤點或持久化索引，驗證盤點期間讀寫、配額與舊快取清理的一致性。

- **#76** [UNVERIFIED] 圖庫背景掃描與前景搜尋／標籤修改共用 SQLite 連線，需驗證並行交易行為與延遲：`Imervue/library/image_index.py:145`、`:182`、`Imervue/library/scanner.py:190`。
  下一步：壓測掃描同時搜尋與寫入、批次回滾及關閉；依結果決定獨立讀取連線與單一寫入佇列，並保持既有 schema、WAL 與批次交易能力。

- **#77** GPU 即時顯影與進階色彩流程仍需評估，現有 GPU Develop 後端主要服務批次輸出：`plugins/gpu_develop/`、`Imervue/image/develop_backends.py`。
  下一步：先完成 #62、#63 的量測與預覽改善，再評估沿用既有後端的收益；建立 CPU／GPU、預覽／匯出的色彩及像素一致性案例，確認降級與模型外掛邊界後安排實作。
