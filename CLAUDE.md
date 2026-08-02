# Project Guidelines

## Session Progress Log — CHECK THIS FIRST

`.claude/PROGRESS.md` is the hand-off file between sessions. Gitignored scratch space: never a
deliverable, never referenced from code or shipped docs.

- **Read it at the start of every session.** If `## Pending` lists items, say so and offer to
  continue them before starting anything new. If it's empty, proceed and don't mention the file.
- **Write to it the moment something is left unfinished** — uncommitted work, an unpushed commit,
  a failing gate, a deferred follow-up, a decision waiting on an answer. One line of *what*, one
  line of the *next concrete step*. Design notes belong in the code, the commit, or the PR.
- **Delete each item the moment it lands.** A finished item left behind is worse than no file.
- When the last item is done, reset the file to `# Progress Log` + an empty `## Pending` section
  (`_(nothing pending)_`) + `## Notes`. Recreate it from that shape if it's missing.

## Definition of Done (HARD REQUIREMENT)

Every feature, bug fix, refactor, or behaviour change MUST satisfy ALL of the following before it
can be committed. No exceptions — incomplete work stays on the working copy until the gates pass.

1. **Unit tests are written and they pass.** New code without new tests is incomplete. See
   **Unit Tests** below for the coverage expectations.
2. `py -m pytest tests/` runs clean (or only skips that already existed before the change).
3. `py -m ruff check .` reports no new errors.
4. `py -m bandit -c pyproject.toml -r Imervue/` reports `No issues identified` (`-c` is REQUIRED;
   without it bandit ignores the skip config).
5. `architecture_explore.md` is updated in the same commit — see **Architecture Map**.
6. The commit message contains no AI tool/model names and no `Co-Authored-By` line.

Work through this list explicitly before staging. If a gate fails, fix it — do not ship around
it. Skipping tests "to come back later" is not allowed because later never happens.

## Architecture Map — `architecture_explore.md` (HARD REQUIREMENT)

`architecture_explore.md` at the repo root maps the whole tree: every package, a one-line purpose
for every module, the cross-cutting patterns, the known traps. Unlike `.claude/PROGRESS.md` it
**is** a tracked deliverable. A map that lags the code is worse than no map — it sends people to
the wrong file with confidence — so it is updated **in the same commit**, never in a follow-up.

Update it when a commit changes **structure or responsibility** (not merely when the diff is big):

- **Module added / deleted / renamed / moved** → fix its row in the owning package's table
  (path, line count, one-line purpose).
- **A module's purpose changed** → rewrite that row. A stale purpose is the worst kind of drift.
- **Package or subpackage added / removed** → add or remove its section, fix the §6 contents.
- **Cross-cutting pattern changed** (worker teardown, delete batching, settle-polling, HTTPS
  guard, suppressions, settings persistence) → §10.
- **Tab layout, startup sequence, or entry points changed** → §3 and §4.
- **Architectural trap fixed or introduced, or a file crossed 1000 lines** → §12.
- **Header** — the date / commit / branch / version line at the top must match the commit.

Docs-only and comment-only commits need no update, and neither does a bug fix inside an existing
module whose purpose is unchanged.

§2 carries per-area file/line totals. Regenerate them, don't hand-edit:

```bash
py -c "import os;t=0;f=0
for r,d,fs in os.walk('Imervue'):
    d[:]=[x for x in d if x!='__pycache__']
    for n in fs:
        if n.endswith('.py'):
            f+=1;t+=sum(1 for _ in open(os.path.join(r,n),encoding='utf-8'))
print(f'Imervue: {f} files, {t} lines')"
```

## No AI Attribution (HARD REQUIREMENT)

NEVER mention "Claude", "Claude Code", "AI-generated", "GPT", "Copilot", or any AI tool/model
name — in commit messages, PR titles/bodies/comments, branch names, issue bodies, code comments,
or documentation. Never add `Co-Authored-By`.

This is broken most often on PRs, because agent harnesses ship a default instruction to append a
generation footer to every PR body. **That default does not apply to this repository.** No
footer, no "Created by …", no tool link, no robot emoji — the PR body ends with real content.
Applies to `gh pr create`, `gh pr edit`, and any review or comment body.

Verify after `gh pr create` / `gh pr edit` — no output means clean; any hit must be stripped with
`gh pr edit <N> --body-file` before the PR is announced as ready:

```bash
gh pr view <N> --json title,body --jq '.title + "\n" + .body' \
  | grep -inE "claude|anthropic|copilot|chatgpt|\bgpt\b|ai-generated|generated with|🤖"
```

## Code Quality

**The tool config is the source of truth, not prose.** `pyproject.toml` (`[tool.ruff]`,
`[tool.bandit]`) and `.bandit` define the enforced rule set — ruff runs `E,F,W,B,SIM,UP,PL,S,C90,N`
with `mccabe.max-complexity = 16` and a documented ignore list. Do not restate those rules here or
assume limits the config has deliberately relaxed. If a rule should change, change the config.

Rules the tools do **not** catch, which still apply:

- **File length ≤ 1000 lines** (SonarQube `python:S104`). Split large modules. The current
  over-budget list lives in §12 of `architecture_explore.md`.
- **No duplication** — don't copy a block of ≥ 3 statements across functions or files, and don't
  repeat a string literal ≥ 3 times (extract a module-level constant). Codacy and SonarCloud
  flag both; ruff does not.
- **No commented-out code, no `TODO` / `FIXME` / `XXX`** in merged code (SonarQube `python:S1135`).
  Git preserves history; file an issue for the follow-up.
- **No `print()` in production code** — use the project logger (`Imervue/system/log_setup.py`,
  `logging.getLogger("Imervue")`).
- **`assert` is for test invariants only** — it is stripped under `python -O`, so runtime
  validation must `raise` explicitly.
- **Release Qt resources** (`deleteLater`, `disconnect`) so widgets and threads don't leak.
- **MD5 / SHA-1 only for non-security use** (cache keys, de-duplication) and only with
  `usedforsecurity=False`.
- **Public functions and classes** should carry type hints and a one-line docstring.

House patterns worth following over a from-scratch design: QThread workers for background tasks,
signal/slot for UI communication, composition over inheritance, and the pure-logic / Qt-shell
split described in `architecture_explore.md` §10.

### Unit Tests

Tests are part of the change, not optional polish. Bug fixes need a regression test; refactors
must keep existing tests green and add one if they expose a previously untested path.

**Cover, for every change:** the happy path; edge cases (empty, single-element, max-size, `None`
/ missing keys); every `except` branch; boundary values just inside and outside each range,
threshold or enum; and a `to_dict → from_dict → equal` round-trip for anything that serialises
(recipe, settings, layer dict, XMP).

**Write, for every feature:**

- **Pure-helper tests.** Extract pure logic out of Qt classes (see `vram_budget.py`, `layers.py`,
  `recycle_bin_dialog.list_pending_entries`) and test it without instantiating widgets.
- **Qt smoke test.** For a dialog, instantiate it under the `qapp` fixture and assert visible
  state (row counts, button enable state, signal emissions). Use `monkeypatch` to auto-confirm
  `QMessageBox` / `QFileDialog` rather than stubbing whole modules. Pass `None` as parent — a
  transient `QWidget` parent crashes teardown.
- **Integration test where the wiring is non-obvious** — recipe pipeline, undo stack, file-tree
  model — on small synthetic inputs.

**Mechanics:** `pytest` style, one test module per production module (`tests/test_<module>.py`).
Use the shared fixtures in `tests/conftest.py` (`qapp`, `tmp_path`, `sample_*_array`,
`image_folder`); don't roll your own QApplication or RNG seed. Never write to the real
`user_setting.json` — the autouse `_isolate_user_settings` fixture redirects the path, so just
mutate `user_setting_dict` directly. A test that was already skipping for a missing optional
dependency may keep skipping, but every NEW test must actually run.

### Qt / OpenGL tests on headless CI

The GitHub Actions Windows runner crashes with `Windows fatal exception: access violation` once
enough `QOpenGLWidget` instances are built in one pytest session — the offscreen-GL surface pool
is finite and overflowing it corrupts process memory. The trace points at
`super().__init__(parent)` inside `PuppetCanvas.__init__` or another `QOpenGLWidget` subclass.

Every test file constructing `PetWindow`, `PuppetCanvas`, `PuppetWorkspace`, or any other
`QOpenGLWidget` subclass MUST import the shared skip marker at the top of the module:

```python
from _qt_skip import pytestmark  # noqa: E402,F401
```

`tests/_qt_skip.py` skips when `CI=true` or `QT_QPA_PLATFORM=offscreen`, so local runs still
cover the file while CI reports every test as `s`. Verify with
`CI=true py -m pytest <file> -q` — every test in the file must report `s`.

Before committing a test that touches Qt/GL, run the `qt-headless-ci-guard` subagent
(`.claude/agents/qt-headless-ci-guard.md`); it enumerates the GL-widget constructions and
confirms the marker is wired. Its reference body documents the root cause in detail.

## Plugins vs Main Program

The dividing line is **dependency surface**, not "AI features go in plugins" (that grouping was
tried and reorganised). A feature is a **plugin** when any of these hold:

1. It needs a **heavy / optional runtime dependency** (rembg, onnxruntime, torch, opencv-python,
   downloaded model weights).
2. It needs **failure isolation** — ML / GPU / CUDA paths that can crash must not take down the
   viewer.
3. It needs an **independent release cadence** via the plugin downloader.

It stays in the **main program** when it runs on the default dep set (numpy, Pillow, PySide6,
defusedxml, watchdog, imageio), its worst failure is a one-image error, and it belongs to the
everyday browse / develop workflow.

When in doubt: *"if a user installs with the default `requirements.txt` and never opens the
plugin manager, should this work?"* Yes → main. No → plugin.

Smart Crop is pure-numpy Sobel + rule-of-thirds → main. AI Denoise has a pure-numpy bilateral
mode *and* an optional ONNX path → plugin, because the plugin gates the ONNX path and its
bilateral logic ships inside the plugin directory, so main never imports plugin-internal code.

**Layout.** Main: `Imervue/image/<feature>.py` (pure logic) + `Imervue/gui/<feature>_dialog.py`
(Qt shell) + a menu entry in `Imervue/menu/extra_tools_menu.py`. Plugin:
`plugins/<name>/__init__.py` (sets `plugin_class`) + `plugins/<name>/<name>_plugin.py` + **all
pure logic inside the plugin directory** (`plugins/ai_denoise/denoise.py`) — never under
`Imervue/image/`. Bundled models go in `plugins/<name>/models/` (gitignored) and are discovered
at runtime so users can drop in their own.

**Testing.** `Imervue/plugin/plugin_manager.py` prepends `plugins/` to `sys.path` at runtime and
`tests/conftest.py` mirrors that at collection time, so tests import plugin modules as
`from <plugin_name>.<module> import …`. Don't duplicate the path injection per test file.

### Mirror plugin changes to the distribution repo (HARD REQUIREMENT)

Plugins reach users through a **separate public repo**, not the main app:
`D:\Codes\Imervue_Plugins` → `https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins`, branch
**`main`** (a mirror committed only to `dev` never reaches users), consumed by
`Imervue/plugin/plugin_downloader.py`.

**Any change under `plugins/<name>/` — new, edited, renamed, deleted — MUST be mirrored and
pushed.** A plugin that exists only here is invisible to every downloader user.

The downloader walks `<category>/<plugin_name>/<flat files>` (e.g. `plugins/ai_denoise/denoise.py`,
`languages/spanish_translation/__init__.py`). Top-level directories are categories; dot-directories
are skipped; **only files directly inside the plugin directory are fetched** — nested `models/` or
`assets/` are not. Keep every runtime-required file flat.

1. Make and verify the change under `D:\Codes\Imervue\plugins\<name>\` (tests live in this repo).
2. Commit here — `/plugins/` is gitignored, so new files need `git add -f` or they silently
   won't commit.
3. Copy the directory into the matching category of `D:\Codes\Imervue_Plugins` (delete it there
   for a removed plugin), then commit and push **to `main`**.
4. Confirm parity — an empty list means in sync. Note this compares directory names only, so it
   cannot catch file-level drift; diff the files too when a plugin was edited rather than added:

```bash
py -c "import os;d=lambda p:{e.name for e in os.scandir(p) if e.is_dir()};a=d(r'D:\Codes\Imervue\plugins');b=d(r'D:\Codes\Imervue_Plugins\plugins')|d(r'D:\Codes\Imervue_Plugins\languages');print(sorted(a^b))"
```

The no-AI-attribution rules apply to the plugins repo exactly as they do here.

## Network & Supply-Chain Safety

- **Every `urllib.request.urlopen` call goes through a module-level `_https_urlopen` guard.**
  Canonical implementations: `Imervue/plugin/pip_installer.py`, `Imervue/plugin/plugin_downloader.py`.
  The guard `urlparse`s the URL, rejects any scheme other than `https`, then calls `urlopen` —
  defending against `http://`, `file://` or `ftp://` slipping in from a future edit or a
  compromised upstream string (SonarQube `python:S5332`, bandit `B310`).
- Do NOT call `urlopen` directly in new code; import or add a local `_https_urlopen`. The call
  inside the guard is the only allowed direct use and must carry
  `# nosec B310  # scheme validated above`.
- **Hugging Face downloads MUST pin a revision** — `hf_hub_download(..., revision=<sha-or-tag>)`
  (bandit `B615`). Fall back to `info.get("revision", "main")` only when the model info dict
  already ships an explicit per-model revision; never leave it unpinned.

## Suppressions & Skip Configuration

Use the right comment for the right tool — they are NOT interchangeable, and every suppression
needs a justification on the same line (`# nosec B310  # scheme validated above`):

| Tool | Form | Notes |
|---|---|---|
| ruff / flake8 | `# noqa: <CODE>` | Must name specific codes — never bare `# noqa`. |
| bandit | `# nosec B<NNN>` | ruff's `# noqa` does NOT suppress bandit. |
| SonarCloud | `# NOSONAR` | For hotspots that can't be config-skipped. Does nothing inside a YAML block scalar. |
| pylint | `# pylint: disable=<name>` | Prefer a refactor. |

Codacy ignores inline `# nosec` / `# noqa` entirely — clear its findings via
`.codacy.yaml` `engines.<slug>.exclude_paths` (the Semgrep slug is `opengrep`, not `semgrep`) or
by fixing the code. `sonar-project.properties` issue-ignore rules do not apply either.

Systemic false positives are skipped at config level, never per line. `.bandit` is canonical
(YAML, one `# B<NNN>: reason` comment per rule); `pyproject.toml` `[tool.bandit]` mirrors it —
**keep both in sync**. `.codacy.yaml` excludes `tests/**` (pytest `assert` is B101, narrow
`except/pass` is B110) and `Imervue/multi_language/**` (translator strings like "API key" trip
B105). After adding a skip, verify `py -m bandit -c pyproject.toml -r Imervue/` returns
`No issues identified`.

## Local CI & Dashboards

Reproduce every engine locally before pushing — see gates 2-4 in **Definition of Done**.

- **Codacy**: https://app.codacy.com/gh/JeffreyChen-s-Utils/Imervue/issues/current
- **SonarCloud**: https://sonarcloud.io/project/overview?id=JeffreyChen-s-Utils_Imervue
  (`api/hotspots/search?projectKey=JeffreyChen-s-Utils_Imervue` works without a token)

**Both dashboards read ONLY the default branch (`main`).** SonarCloud analyses no other branch,
and Codacy loads `.codacy.yaml` from `main`. A config fix or dependency bump sitting on `dev`
changes nothing on either dashboard until it merges — so "the numbers didn't move" after a push
to `dev` is expected, not a failure. Querying a branch that was never analysed returns an empty
result set, which reads like a clean report; check the branch exists before trusting a zero.

API tokens live in the environment — never hardcode or echo them:

```bash
curl -u "$SonarCloudToken:" "https://sonarcloud.io/api/qualitygates/project_status?projectKey=JeffreyChen-s-Utils_Imervue"
curl -H "project-token: $CODACY_PROJECT_TOKEN" "https://app.codacy.com/api/v3/analysis/organizations/gh/JeffreyChen-s-Utils/repositories/Imervue"
```

Codacy reports `"analyzed": false` while a run is still in flight.

## Environment Gotchas

Traps specific to this machine and toolchain. Each one has silently produced a wrong result
before — the failure mode is a command that *appears* to succeed.

- **Git Bash `/tmp` is invisible to the Windows Python behind `py`.** A file written to `/tmp`
  by a shell heredoc cannot be read back by `py`, and vice versa, so a rewrite step can report
  success while the consumer still reads the old file. Put shared intermediates in the session
  scratchpad directory (a real Windows path) instead.
- **`gh pr view --json merged` is not a valid field** and the command fails outright. Use
  `mergedAt` / `mergeCommit`. When chaining `gh pr merge` with a follow-up query, a failure in
  the query can hide the merge command's own output — verify state separately.
- **The full test suite exits `-1073741819` (0xC0000005) *after* printing a passing summary.**
  Pre-existing, verified against a stashed tree. Read the reported counts, not the exit code.
- **Clipboard tests flake in full runs and pass in isolation.** `QClipboard.dataChanged` arrives
  asynchronously via `WM_CLIPBOARDUPDATE`, so two `setImage` calls separated by one
  `processEvents` can coalesce into a single signal. Before blaming a change, re-run the test
  isolated *and* repeat the full run on the unchanged dependency set.
- **`send2trash` costs ~0.27 s per call regardless of how few files it carries**, versus
  ~0.016 s/file when a whole list goes over in one call (measured 2026-07-30). Every delete path
  must batch through `Imervue/system/trash_ops.py` — never a per-file loop.
