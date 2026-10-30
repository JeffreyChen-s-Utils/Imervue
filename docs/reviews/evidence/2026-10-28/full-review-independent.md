# Independent full-review evidence check

The goal is to validate the full-program audit findings and distinguish measured failures from source-supported risks. Target HEAD is 34823f113e3a18b70feb55a03ef012e8376a39c8. No application or test files were changed. This reviewer read the supplied reports, reproduction sources and logs, independently traced relevant production callers, and reran the root boundary reproduction with Python 3.14. No full suite, physical GUI, hardware or network service was exercised.

## Accepted findings and severity

| Finding | Verdict | Evidence qualification |
| --- | --- | --- |
| Maintenance prunes existing hidden or out-of-scope images | P1 | Independently reproduced both existing files disappearing from the index. GUI roots/current-folder choice in menu/right_click_menu.py reaches the same code. image_index.delete_image also deletes notes, culling and image_tags. Metadata loss is source-confirmed; the root reproduction only populated image rows. |
| MCP direct destination save loses previous bytes on failure | P1 when overwriting a valuable destination | Independently reproduced partial bytes replacing an existing PNG through rotate_image and its real save helper. Controlled encoder failure models write failure. No actual disk-full event was tested. |
| apply_frame lacks output-size bound | P2 | Independently reproduced an attempted RGBA allocation of 100002 by 100002. The interceptor prevented allocation. This proves the missing bound, not actual 40 GB consumption or an observed process crash. |
| Malformed session escapes menu error handling | P2 | Independently reproduced AttributeError for a list root and TypeError for integer tabs/selection. menu/file_menu.py catches only OSError/ValueError. No claim of process termination. |
| Frozen non-Windows entry selects Windows OpenGL platform | P2 | __main__.py sets nt whenever frozen and unset. Imervue_mac.spec builds that entry and pyinstaller.md documents macOS packaging. Recorded simulated darwin probe selects Win32Platform. Actual macOS execution remains untested. |
| UI-01 failed Paint overwrite export destroys previous destination | P1 | Actual GIF/CBZ exporters and logged injected encoder/composite failures prove previous bytes are lost. WebP/APNG/PDF extension of the claim is source evidence only. Can share one remediation finding with the MCP direct-write problem while retaining all affected locations. |
| UI-02 Auto-Tag close blocks GUI until batch completes | P2 | QThread.wait without timeout blocks the GUI. Batch has no cancellation check. Controlled event/timer reproduction demonstrates blocking, not production batch performance. |
| UI-03 reserved filename characters break gallery URLs | P2 | Actual gallery output plus URL parsing proves # becomes a fragment and the requested local path does not exist. No browser was driven. |
| UI-04 malformed Paint metadata escapes open-error handling | P2 | Actual damaged NPZ reaches KeyError before DocumentFiles.open can present its warning. Source tracing confirms the boundary mismatch. Existing document replacement does not occur. |
| PR-01 pip cancellation cannot reach child | P2 | Local proc never populates self._proc. Real hidden child remains alive in logged worker cancellation probe. stdout iteration precedes timeout. worker_retirement waits without timeout and main close drains it, supporting shutdown-hang risk for a stalled child. |
| PR-02 settings save races profile creation | P2 | Real JSON writes under a controlled thread schedule lose the newly created disk profile. Timer cancellation does not join an already running callback. Sequential atomic writes do not serialize the transaction. |
| PR-03 WebDAV URL lacks filename quoting | P2 | Request/HTTP serializer evidence demonstrates space and Unicode errors plus # truncation. Wrong-resource overwrite is conditional on remote resource state and was not exercised over the network. |
| PR-04 no-overwrite transfer has TOCTOU gap | P2 | Recorded move reproduction has both sources gone, one destination and two successes. Test uses two helper threads. Existing GUI callers serialize, so external writer or another process is required in ordinary app usage. Cross-process applicability follows from filesystem operations without reservation; no actual second application process was tested. |
| PUP-01 batch output filename collisions | P1 | Real recorder/imageio GIF evidence reports two identical completed paths and leaves only the second color. Sanitization causes collisions for ordinary distinct names including CJK. |
| PUP-02 embedded workspace cleanup omitted on parent close | P2 | Actual _release_for_close on a stand-in main window does not invoke child cleanup. Source confirms secondary close deletes parent and final close uses os._exit. Real camera/microphone activity or crash was not tested. Do not present the stand-in thread as a real webcam reproduction. |
| PUP-03 recorder close failure reported as saved | P2 | stop catches close errors then emits finished. Controlled failing writer proves incorrect success signal. Actual codec/full-disk corruption was not tested. |
| PUP-04 malformed VTS fields escape request boundary | P2 | Source confirms unhashable messageType and invalid data shapes escape _on_text. Recorded handler/callback probes establish protocol failure. No remote execution or process termination demonstrated. |

## Rejected or narrowed claims

- The initial PR-04 report said both copy and move logged two successes. The copy log actually records [1, 0] and a Windows sharing violation. Only move has the claimed runtime data-loss proof. Copy susceptibility remains source-supported. Parent and report owner were notified.
- Concurrent helper threads are not evidence that current GUI transfer commands overlap. The cross-process/external-writer condition must remain explicit.
- Allocation interception, simulated darwin, a stand-in canvas, a stand-in main window and injected encoder failures must retain their labels. They provide concrete boundary evidence but do not stand in for production resource exhaustion, macOS startup, GL rendering, physical device shutdown or actual disk-full behavior.
- No accepted finding establishes remote code execution, universal application termination or arbitrary memory corruption.

## Coverage and audit-trail truth

The subsystem reports explicitly distinguish inventory/search coverage from deep semantic traces. Keep that distinction in the final report. The numbers 584 UI/image/Paint modules, 149 plugin/runtime modules and 90 puppet/pet modules are reviewer inventories, not independently re-counted by this checker. The root inventory is present, but parsing all 896 files does not prove all paths were understood or exercised.

The recorded baseline full-suite ending reports 14357 passed and 1431 skipped. Root targeted tests report 102 passed. Ruff reports success and Bandit reports no issues. This checker read those log endings but did not rerun their commands or establish the baseline revision provenance. Report the full suite as a reused unchanged-source baseline, not a fresh full-suite run in this review. Existing passing tests do not invalidate the reproduced cases.

At the first read full-review.tsv contained only its header. At the last read it contained three entries timestamped 2026-10-28T19:37:58.5589678+08:00 covering coverage, verification and reproduction. These are a retrospective summary and do not provide a complete action-by-action history. No complete transcript was supplied, so this review cannot certify that every command or decision is represented. The todo still had Fan out, Aggregate and Report unchecked at the last read; parent owns finishing those states.

Remaining gaps are actual macOS frozen startup, real GPU/GL and native SDK behavior, cameras/microphones/NDI, physical Qt close integration, multi-process transfer, live upload behavior, arbitrary malformed-file fuzzing, exhaustive image/paint algorithms and third-party implementation internals. The report can truthfully claim a whole-repository risk-based audit with reproducible findings, not exhaustive correctness verification of every module.
