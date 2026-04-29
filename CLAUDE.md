# Project Guidelines

## Definition of Done (HARD REQUIREMENT)

Every feature, bug fix, refactor, or behaviour change MUST satisfy ALL of the following before it
can be committed. No exceptions — incomplete work stays on the working copy until the gates pass.

1. **Unit tests are written and they pass.** New code without new tests is incomplete; the commit
   fails this gate. See the **Unit Tests** section below for the exact coverage expectations.
2. `py -m pytest tests/` runs clean (or only skips that already existed before the change).
3. `py -m ruff check .` reports no new errors.
4. `py -m bandit -c pyproject.toml -r Imervue/` reports `No issues identified`.
5. The commit message contains no AI tool/model names and no `Co-Authored-By` line.

When you finish editing code, work through this list explicitly before staging. If a gate fails,
fix it — do not ship around it. Skipping tests "to come back later" is not allowed because later
never happens and the gap compounds.

## Git Commits

- NEVER add `Co-Authored-By` lines to commit messages. All commits should only contain the commit message itself with no co-author attribution.
- NEVER mention "Claude", "Claude Code", "AI-generated", "GPT", "Copilot", or any AI tool/model name anywhere — including commit messages, PR titles, PR descriptions, code comments, and documentation.

## Code Quality Requirements

### Design Patterns

- Apply appropriate design patterns (Strategy, Observer, Factory, Singleton, Command, Builder, Adapter, Decorator, etc.) where they fit naturally.
- Prefer composition over inheritance.
- Follow SOLID principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.
- Apply DRY (Don't Repeat Yourself) — extract shared logic into reusable components.
- Use the existing project patterns (e.g., QThread worker pattern for background tasks, signal/slot for UI communication).

### Software Engineering Practices

- Separate concerns: keep UI, business logic, and data access in distinct layers.
- Write self-documenting code with clear naming; add comments only for non-obvious "why" explanations.
- Favor immutability where practical — avoid mutating shared state.
- Handle errors explicitly at system boundaries; propagate exceptions cleanly through internal layers.
- Keep functions short and focused — one function, one responsibility.
- Delete dead code immediately; do not comment it out or leave unused imports/variables.

### Performance

- Always consider and implement the best-performance approach for the task.
- Use lazy loading and on-demand initialization where applicable.
- Avoid unnecessary memory allocations and copies — reuse buffers when processing large data (images, arrays).
- Prefer batch operations over per-item processing.
- Use appropriate data structures (dict for O(1) lookups, deque for queue operations, set for membership tests).
- Profile and measure before optimizing hot paths; avoid premature optimization of cold paths.
- Use generators and iterators for large datasets to minimize memory footprint.
- Cache expensive computations with `functools.lru_cache` or manual caching where appropriate.

### Security

- Never hardcode secrets, API keys, tokens, or passwords in source code — use environment variables or secure config files.
- Validate and sanitize ALL external input (user input, file uploads, API responses, CLI arguments) at system boundaries.
- Use parameterized queries for any database operations — never concatenate user input into SQL strings.
- Apply the principle of least privilege — request only the minimum permissions required.
- Avoid `eval()`, `exec()`, `pickle.loads()` on untrusted data, and `subprocess` with `shell=True`.
- Use secure defaults: HTTPS, strong hashing (bcrypt/argon2 for passwords, SHA-256+ for integrity), constant-time comparisons for secrets.
- Sanitize file paths to prevent path traversal attacks; reject `..` segments and absolute paths from user input.
- Log security-relevant events but never log sensitive data (passwords, tokens, PII).

### Unit Tests

Tests are not optional polish — they are part of the change. A feature without tests is an
incomplete feature and MUST NOT be committed. This rule applies equally to bug fixes (regression
test required) and refactors (existing behaviour must remain green; add a test if the refactor
exposes a previously untested path).

**Required coverage for every change:**

- **Happy path** — the new code does what it advertises on a representative input.
- **Edge cases** — empty inputs, single-element inputs, max-size inputs, None / missing keys.
- **Error handling** — every `except` branch is exercised; invalid inputs raise the documented
  exception or are clamped to the documented safe range.
- **Boundary conditions** — the values just inside and just outside any range, threshold, or
  enum. Off-by-one defects live here.
- **Round-trips** — anything that serialises (recipe, settings, layer dict, XMP) needs a
  `to_dict → from_dict → equal` test.

**Required test types for every feature:**

- **Pure-helper tests.** Extract pure logic out of Qt classes into helper functions (see
  `vram_budget.py`, `layers.py`, `recycle_bin_dialog.list_pending_entries`) and unit-test
  those directly without instantiating Qt widgets. Cheap, fast, deterministic.
- **Qt smoke test.** If the feature has a dialog, instantiate it under the `qapp` fixture and
  assert the visible state (row counts, button enable state, signal emissions). Use
  `monkeypatch` to auto-confirm `QMessageBox` / `QFileDialog` instead of stubbing whole modules.
- **Integration test where the wiring is non-obvious.** If the feature plugs into another
  subsystem (recipe pipeline, undo stack, file-tree model), add a test that exercises the
  end-to-end flow on small synthetic inputs.

**Mechanics:**

- Use `pytest` style. Module-level functions and `Test*` classes are both fine; follow the
  style of the file you're adding to.
- Test file naming: `tests/test_<module_name>.py`. One test module per production module.
- Use the shared fixtures in `tests/conftest.py` (`qapp`, `tmp_path`, `sample_*_array`,
  `image_folder`). Do not roll your own QApplication or RNG seed.
- Never write to the real `user_setting.json`. The autouse `_isolate_user_settings` fixture
  redirects the path; trust it and just mutate `user_setting_dict` directly in tests.
- Run `py -m pytest tests/` before committing. If a test was already skipping because of a
  missing optional dependency, leave it skipping — but every NEW test must run, not skip.

### Linter & Static Analysis Compliance (SonarQube / Codacy / pylint / flake8 / ruff)

All new and modified code MUST pass the following rules without warnings. These mirror the
default rule sets of SonarQube, Codacy, pylint, flake8, ruff, and bandit for Python.

#### Complexity & Size

- **Cognitive complexity**: keep each function ≤ 15 (SonarQube `python:S3776`). Break nested
  branches into helper functions when exceeded.
- **Cyclomatic complexity**: keep each function ≤ 10 (pylint `R1260`, radon `C`).
- **Function length**: ≤ 75 logical lines. Split long functions into focused helpers.
- **File length**: ≤ 1000 lines (SonarQube `python:S104`). Split large modules.
- **Parameter count**: ≤ 7 per function (SonarQube `python:S107`). Group related params into a
  dataclass or dict when exceeded.
- **Nesting depth**: ≤ 4 levels (SonarQube `python:S134`). Use early returns / guard clauses.
- **Boolean expression complexity**: ≤ 3 operators in one expression (SonarQube `python:S1067`).
  Extract to named booleans.
- **Return statements**: ≤ 6 per function (pylint `R0911`).
- **Local variables**: ≤ 15 per function (pylint `R0914`).

#### Duplication

- Do NOT copy-paste blocks of ≥ 3 statements across functions or files (SonarQube
  `common-python:DuplicatedBlocks`, Codacy duplication detector). Extract shared logic.
- Do NOT declare the same string literal ≥ 3 times (SonarQube `python:S1192`). Assign to a
  module-level constant.

#### Naming (PEP 8)

- `snake_case` for functions, methods, variables, modules (SonarQube `python:S1542`, pylint `C0103`).
- `PascalCase` for classes (pylint `C0103`).
- `UPPER_CASE_WITH_UNDERSCORES` for module-level constants.
- `_leading_underscore` for private attributes / methods.
- No single-letter names except loop indices (`i`, `j`, `k`, `x`, `y`, `z`) or well-known math symbols.

#### Errors & Exceptions

- Never use bare `except:` — always specify the exception type (SonarQube `python:S5754`, flake8 `E722`).
- Never write `except Exception: pass` without a logged reason and comment explaining why it is safe.
- Never catch `BaseException` directly (covers `KeyboardInterrupt`, `SystemExit`).
- Raise specific exception types (`ValueError`, `TypeError`, `FileNotFoundError`) instead of generic `Exception`.
- Chain exceptions with `raise X from err` to preserve context (ruff `B904`).
- Never use `assert` for runtime validation (assertions are stripped under `python -O`); use
  explicit `raise` instead. `assert` is only for invariants in tests.

#### Code Smells

- No unused imports, variables, or function parameters (pyflakes `F401`, `F841`, pylint `W0612`, `W0613`).
  Prefix intentionally unused params with `_`.
- No commented-out code. Delete it — git preserves history.
- No `print()` calls in production code; use the project's logger (`Imervue/utils/logging`).
- No `TODO` / `FIXME` / `XXX` left in merged code (SonarQube `python:S1135`). File a ticket instead.
- No magic numbers — extract to `UPPER_CASE` constants (SonarQube `python:S109`). Exceptions: `0`, `1`, `-1`, `2` in obvious contexts.
- Use `is None` / `is not None` (never `== None` / `!= None`) (pycodestyle `E711`).
- Use `isinstance(x, T)` instead of `type(x) == T` (pycodestyle `E721`).
- No mutable default arguments (`def f(x=[])`) — use `None` and assign inside (ruff `B006`, pylint `W0102`).
- No global mutable state; if unavoidable, encapsulate in a module-level class or singleton.
- Prefer f-strings over `.format()` or `%` (ruff `UP032`).
- Always use context managers (`with` blocks) for file / resource handles (ruff `SIM115`).
- Prefer `dict.get(key, default)` over `if key in dict: ... else: ...` (ruff `SIM401`).
- Use comprehensions / generator expressions instead of `map` + `lambda` or manual `append` loops when clearer.
- Close / release Qt resources (`deleteLater`, `disconnect`) to prevent leaks.

#### Security (bandit / SonarQube `python:S*` security rules)

- `pickle.load(s)` on untrusted data is forbidden (`B301`, SonarQube `python:S5135`).
- `yaml.load` without `SafeLoader` is forbidden — use `yaml.safe_load` (`B506`).
- MD5 / SHA-1 are forbidden for security purposes (hashing secrets, signatures) — use SHA-256+
  or bcrypt / argon2 (`B303`, `B304`, SonarQube `python:S4790`). They are allowed for non-security
  uses (cache keys, file de-duplication) ONLY with `usedforsecurity=False`.
- `subprocess` with `shell=True` is forbidden when any argument comes from user input (`B602`).
- Never use `eval`, `exec`, `compile` on dynamic input (`B307`).
- Never use `tempfile.mktemp()` — use `tempfile.mkstemp()` or `NamedTemporaryFile` (`B306`).
- Network binds must not use `0.0.0.0` unless intentional and documented (`B104`).
- XML parsing must use `defusedxml`, never stdlib `xml.etree` on untrusted input (`B405`–`B411`).
- Random number generation for security must use `secrets` module, not `random` (`B311`).

#### Typing & Documentation

- Public functions and methods SHOULD have type hints on parameters and return type.
- Public modules and classes SHOULD have a one-line docstring describing their purpose.
- Private helpers may omit docstrings if names are self-explanatory.

#### Enforcement

When writing or modifying code, mentally check each function against the above rules before
finalising. If unavoidable rule violation (e.g. Qt callback signature forces extra parameters),
add a `# noqa: <rule>` or equivalent suppression with a brief justification comment on the same line.

## Project-Specific Compliance Patterns

These patterns were established while zeroing out the Codacy / SonarCloud / bandit backlog.
Keep following them so the CI stays green and so new maintainers have an obvious prior-art
example to copy.

### Plugins vs Main Program

The line between `Imervue/` (the main package) and `plugins/<name>/` is **not** "AI features
go in plugins" — that grouping made things inconsistent and was reorganised. The correct test
is **dependency surface**:

**A feature is a plugin when ANY of the following is true:**

1. It needs a **heavy / optional runtime dependency** that we don't want to force on every user
   (rembg, onnxruntime, torch, opencv-python, large model weights downloaded on first run).
2. It needs **failure isolation** — ML / GPU / CUDA paths that can crash should not be allowed
   to take down the main viewer.
3. It needs **independent release cadence** — the team wants to ship updated models or
   algorithms through the plugin downloader without re-shipping the main app.

**A feature stays in the main program when:**

- It runs on the default dep set (numpy, Pillow, PySide6, defusedxml, watchdog, imageio).
- Failure means at worst a one-image error — not a process crash.
- It's part of the everyday browse / develop workflow that all users should see by default.

**Examples.** Smart Crop is pure-numpy Sobel + rule-of-thirds → main. AI Denoise has both a
pure-numpy bilateral mode AND an optional ONNX path → plugin (because the plugin gates the
ONNX path; the bilateral logic ships inside the plugin directory, not in main, so the main
package never imports plugin-internal code).

#### Directory rules

- **Main program**: `Imervue/image/<feature>.py` for pure logic, `Imervue/gui/<feature>_dialog.py`
  for the Qt front-end, menu entry registered in `Imervue/menu/extra_tools_menu.py`.
- **Plugin**: `plugins/<name>/__init__.py` (sets `plugin_class`), `plugins/<name>/<name>_plugin.py`
  for the plugin shell + Qt dialog, and **all pure logic lives INSIDE the plugin directory**
  (e.g. `plugins/ai_denoise/denoise.py`). Never put plugin-internal logic under `Imervue/image/`.
- **Models**: bundled model files go to `plugins/<name>/models/` (gitignored). Plugins discover
  them at runtime so users can drop in their own.

#### Testing plugin-internal modules

Plugins are not on the default `sys.path` — at runtime `Imervue/plugin/plugin_manager.py`
prepends `plugins/` so each plugin folder becomes importable as a package. `tests/conftest.py`
mirrors that injection at session-collect time, which lets tests in `tests/` import plugin
modules with `from <plugin_name>.<module> import …`. Do not duplicate the path injection in
individual test files.

#### When in doubt

Ask: "if a user installs Imervue with the default `requirements.txt` and never touches the
plugin manager, should this feature work?" If yes → main. If no → plugin.

### Network & Supply-Chain Safety

- **All `urllib.request.urlopen` calls MUST go through a module-level `_https_urlopen` guard.**
  Canonical implementations live in `Imervue/plugin/pip_installer.py` and
  `Imervue/plugin/plugin_downloader.py`. The guard parses the URL with `urllib.parse.urlparse`,
  rejects any scheme other than `https`, then calls `urlopen`. This defends against both
  future maintainers and compromised upstream strings slipping in `http://`, `file://`, or
  `ftp://` URLs (SonarQube `python:S5332`, bandit `B310`).
- Do NOT call `urllib.request.urlopen` directly in new code. Import or add a local
  `_https_urlopen` helper instead.
- The internal `urlopen` call inside the guard is the ONLY allowed direct use, and must carry
  `# nosec B310  # scheme validated above` on the same line.
- **Hugging Face Hub downloads MUST pin a revision.** `hf_hub_download(...)` must pass
  `revision=<commit-sha-or-tag>` (bandit `B615`, "unsafe download without explicit revision").
  Default to `info.get("revision", "main")` only if the model info dict already ships an
  explicit revision per model — never leave it fully unpinned.

### Suppression Comment Conventions

Use the right comment for the right tool. They are NOT interchangeable.

| Tool         | Comment form                             | Placement   | Notes                                               |
|--------------|------------------------------------------|-------------|-----------------------------------------------------|
| ruff / flake8 | `# noqa: <CODE>` (e.g. `# noqa: S310`)  | line-level  | Must list specific codes — never bare `# noqa`.     |
| bandit        | `# nosec B<NNN>` (e.g. `# nosec B310`)  | line-level  | ruff's `# noqa` does NOT suppress bandit.           |
| SonarCloud    | `# NOSONAR`                              | line-level  | Use for hotspots that cannot be config-skipped (e.g. deliberate clear-text URLs in test inputs). |
| pylint        | `# pylint: disable=<name>`               | line-level  | Prefer refactor over suppression.                   |

Every suppression MUST include a brief justification on the same line
(`# nosec B310  # scheme validated above`). Unexplained suppressions will not pass review.

### Project-Wide Skip Configuration

Systemic false positives are skipped at the config level, never with per-line comments. The
authoritative skip lists live in:

- `.bandit` (YAML, with per-rule justification comments) — the canonical source.
- `pyproject.toml` `[tool.bandit]` — mirror for tooling that only reads `pyproject.toml`.
  Keep both files in sync.
- `.codacy.yaml` `engines.bandit.exclude_paths` — excludes `tests/**` (pytest `assert` is B101,
  narrow `except/pass` is B110) and `Imervue/multi_language/**` (translator strings like
  "API key" trip B105 hardcoded-password).

When adding a new bandit skip:
1. Add it to `.bandit` with a `# B<NNN>: <one-line reason>` comment.
2. Mirror it in `pyproject.toml` `[tool.bandit].skips`.
3. Verify locally: `py -m bandit -c pyproject.toml -r Imervue/` must return `No issues identified`.

### Local CI Reproduction

Before pushing, reproduce each engine locally so CI does not have to tell you:

- **bandit**: `py -m bandit -c pyproject.toml -r Imervue/`
  (the `-c` flag is REQUIRED — without it, bandit ignores the skip config).
- **ruff**: `py -m ruff check .`
- **pytest**: `py -m pytest tests/`

### External Dashboards

- **Codacy project issues**: https://app.codacy.com/gh/JeffreyChen-s-Utils/Imervue/issues/current
- **SonarCloud project**: https://sonarcloud.io/project/overview?id=JeffreyChen-s-Utils_Imervue
  (use `api/hotspots/search?projectKey=JeffreyChen-s-Utils_Imervue` for programmatic access
  without a token).
