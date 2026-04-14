# Project Guidelines

## Git Commits

- NEVER add `Co-Authored-By` lines to commit messages. All commits should only contain the commit message itself with no co-author attribution.

## Code Quality Requirements

### Design Patterns

- Apply appropriate design patterns (Strategy, Observer, Factory, Singleton, etc.) where they fit naturally.
- Prefer composition over inheritance.
- Follow SOLID principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.
- Use the existing project patterns (e.g., QThread worker pattern for background tasks, signal/slot for UI communication).

### Performance

- Always consider and implement the best-performance approach for the task.
- Use lazy loading and on-demand initialization where applicable.
- Avoid unnecessary memory allocations and copies — reuse buffers when processing large data (images, arrays).
- Prefer batch operations over per-item processing.
- Use appropriate data structures (dict for O(1) lookups, deque for queue operations, set for membership tests).
- Profile and measure before optimizing hot paths; avoid premature optimization of cold paths.

### Unit Tests

- Every code change (new feature, bug fix, refactor) MUST include corresponding unit tests.
- Tests should cover: happy path, edge cases, error handling, and boundary conditions.
- Use `unittest` framework consistent with existing test files in `tests/`.
- Test file naming: `tests/test_<module_name>.py`.
- Run all tests with `py -m pytest tests/` before committing to ensure nothing is broken.
