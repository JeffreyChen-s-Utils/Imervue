# Project Guidelines

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

- Every code change (new feature, bug fix, refactor) MUST include corresponding unit tests.
- Tests should cover: happy path, edge cases, error handling, and boundary conditions.
- Use `unittest` framework consistent with existing test files in `tests/`.
- Test file naming: `tests/test_<module_name>.py`.
- Run all tests with `py -m pytest tests/` before committing to ensure nothing is broken.
