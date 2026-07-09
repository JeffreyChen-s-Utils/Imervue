# Test layers

The test suite is split into three mutually exclusive layers. Pytest assigns a
layer during collection, so every collected test belongs to exactly one layer.

- `fast`: isolated tests without Qt widgets or cross-subsystem workflows.
- `gui`: tests using Qt application fixtures or importing Qt widget classes.
- `integration`: cross-subsystem, full-window, release, and end-to-end workflow tests.

Run the fast feedback loop while developing:

```powershell
python -m pytest --test-layer=fast -q
```

Run the other layers or the complete suite explicitly:

```powershell
python -m pytest --test-layer=gui -q
python -m pytest --test-layer=integration -q
python -m pytest --test-layer=all -q
```

Tests can declare `@pytest.mark.fast`, `@pytest.mark.gui`, or
`@pytest.mark.integration` when automatic classification is not appropriate.
Declaring more than one layer is an error. Without an explicit marker,
`conftest.py` classifies integration-style filenames first, then Qt widget
tests, and defaults the remainder to `fast`.

CI runs the fast layer on every supported Python version. GUI and integration
layers run separately on Python 3.12, keeping broad compatibility feedback fast
without dropping the slower coverage.
