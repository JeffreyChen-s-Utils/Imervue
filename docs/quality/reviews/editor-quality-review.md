# Independent external editor review

The goal is to reduce the hosted quality findings while preserving configured-editor behavior and making process ownership explicit. I reviewed the frozen three-file diff in `D:/Codes/Imervue-editor-quality`, its settings dialog, and the file-menu callers. This was a read-only code review. No implementation files were changed.

## Finding

- P2, `Imervue/external/editors.py:93`. `QProcess.startDetached()` changes the Windows elevation-failure contract. The pinned and installed Qt version is 6.11.2. Its Windows implementation catches `ERROR_ELEVATION_REQUIRED` and retries through `ShellExecuteExW` with the `runas` verb. A configured executable that requires elevation now opens UAC and can wait for consent on the file-menu call path. The old `Popen` path caught the resulting `OSError`, logged it, and returned false. The new false-return mock and missing-executable integration test do not cover this branch. Preserve the prior failure behavior, or explicitly treat elevation prompting as a behavior change with appropriate review and coverage. This conclusion is source-backed; I did not trigger UAC. See [Qt 6.11.2 Windows process implementation](https://github.com/qt/qtbase/blob/v6.11.2/src/corelib/io/qprocess_win.cpp#L809-L891).

## Assessment

The API change has a legitimate ownership rationale. Qt documents a detached process that survives the caller and starts a separate Unix session. A local QProcess object is suitable for that operation because it does not own the detached child's lifetime. However, ordinary Popen children can already outlive their parent. The strongest improvement is explicit detachment and Unix session independence, not a newly universal ability to survive Imervue. The absolute executable path also removes ambiguity after checking the configured file. These are meaningful reasons beyond removing analyzer-recognized subprocess calls. See [Qt startDetached documentation](https://doc.qt.io/qt-6/qprocess.html#startDetached).

The settings shape, save scheduling, EditorEntry public import, and menu caller remain intact. Filtering valid dataclass instances remains equivalent because EditorEntry is truthy. The argument refactor preserves the existing empty-argument, placeholder, append-path, and malformed-quote behavior by inspection and focused tests. Unclosed quotes still raise ValueError before process creation; that is pre-existing behavior.

The Windows dialog has no executable-extension filter and accepts a typed path. Batch wrappers remain in scope. It would be incorrect to assert that Qt categorically rejects `.bat` or `.cmd`, or that changing to QProcess eliminates their shell interpretation. Both implementations ultimately use CreateProcess on Windows. Python and Qt explicitly document batch-file shell interpretation and metacharacter hazards. This risk predates the diff. The module's unconditional no-shell wording should be narrowed so it does not suggest the analyzer result proves batch arguments safe. See [Python subprocess security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations) and [Qt launching shells and batch files](https://doc.qt.io/qt-6/qprocess.html#launching-shells-and-batch-files).

The new argument-contract test calculates its expected values with essentially the same parser and substitution steps as production. It checks refactor wiring, but it does not independently prove what an actual external program receives after Windows serialization. The existing explicit examples help, and the real missing-executable case verifies Qt failure logging. A safe headless argument-recorder integration test would provide stronger success-path evidence when that is permitted.

## Validation and limits

- Independently ran `D:/Codes/Imervue/.venv/Scripts/python.exe -m pytest tests/test_external_editors.py -q` with `QT_QPA_PLATFORM=offscreen`. All 36 tests passed in 0.79 seconds.
- Confirmed installed PySide6 and Qt are both 6.11.2, matching the pin in pyproject.toml.
- Inspected matching upstream Qt Windows launch and command-line construction code. There is no demonstrated ordinary-executable argv regression in this diff.
- Did not launch a real successful editor, batch wrapper, elevated executable, or invalid binary. Did not repeat the prior stalled probe. Did not manipulate desktop focus, mouse, or keyboard.
- No Unix runtime, parent-exit lifetime, or real Windows argv-capture experiment was performed. Those remain validation limits, not evidence of failure.
- The parent owns the full suite, audit checks, and hosted metrics. I did not independently verify the reported 40-test aggregate, Radon change, Bandit result, or Codacy result.

Verdict: the lifetime rationale is defensible, but the change is not fully behavior-preserving on Windows. Resolve or explicitly account for the elevation branch before calling the refactor behavior-preserving and ready.

## Revised diff and P2 resolution

I independently reviewed the revised three-file diff after the worker removed QProcess. The P2 finding is resolved. `launch_editor` now retains the original `subprocess.Popen(argv, shell=False)` call, the original configured executable at `argv[0]`, and the original `except OSError` logging and false return. There is no elevation retry, absolute-path rewrite, or detached-process behavior change in the revised implementation.

The remaining production changes simplify filtering and share the shlex parse across argument branches. They preserve behavior for the actual EditorEntry dataclass and configured string arguments. Empty or whitespace-only arguments still append the image path; placeholders still replace within parsed tokens; other arguments still append the image path. Settings serialization, save scheduling, public imports, platform selection, and exception behavior remain unchanged. The new Windows batch-file caveat corrects the earlier overbroad no-shell statement.

The mocked tests now check the configured program and argument list passed to Popen, absence of wait or communicate calls, and an OSError returning false after exactly one launch attempt. I independently reran the focused module with the explicit workspace interpreter and `QT_QPA_PLATFORM=offscreen`. All 35 tests passed in 0.66 seconds. No real launch probe or full suite was run. The prior concern that the table-driven argument test resembles the implementation remains a test-quality limitation, but the explicit examples and unchanged launch API make it non-blocking for this narrow refactor.

Current verdict: no blocking correctness finding in the revised diff. This is a behavior-preserving parsing/filtering refactor, not a process-lifetime improvement. Bandit B404/B603 and hosted Opengrep audit findings remain unresolved as reported by the parent. I did not independently verify the reported 39-test aggregate, local complexity 22 to 19, or hosted analysis. Approval of this code review does not claim those audit gates are clean.
