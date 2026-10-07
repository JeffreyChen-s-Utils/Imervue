# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

### 第三階段：一致的功能流程與狀態（P2）

### 後續階段：依基準結果安排（P3）

- **#77** GPU 即時顯影與進階色彩流程仍需評估，現有 GPU Develop 後端主要服務批次輸出：`plugins/gpu_develop/`、`Imervue/image/develop_backends.py`。
  下一步：先完成 #62、#63 的量測與預覽改善，再評估沿用既有後端的收益；建立 CPU／GPU、預覽／匯出的色彩及像素一致性案例，確認降級與模型外掛邊界後安排實作。
