"""``_fit_scale_and_pan``: how the streamed puppet frame fits the document (pure, no GL)."""
from __future__ import annotations

import pytest

from Imervue.puppet.canvas import _fit_scale_and_pan


@pytest.mark.parametrize("doc, target, expected", [
    ((100, 200), (100, 200), (1.0, 0.0, 0.0)),        # exact fit
    ((100, 200), (400, 400), (2.0, 100.0, 0.0)),      # height-bound: bars left and right
    ((400, 100), (200, 200), (0.5, 0.0, 75.0)),       # width-bound: bars top and bottom
    ((300, 300), (90, 60), (0.2, 15.0, 0.0)),         # shrink to fit
])
def test_keeps_aspect_and_centres(doc, target, expected):
    scale, pan_x, pan_y = _fit_scale_and_pan(doc, *target)
    assert (scale, pan_x, pan_y) == pytest.approx(expected)
    width, height = target
    assert doc[0] * scale <= width + 1e-9 and doc[1] * scale <= height + 1e-9


@pytest.mark.parametrize("doc", [(0, 100), (100, 0), (-5, 10), (0, 0)])
def test_empty_document_has_no_fit(doc):
    assert _fit_scale_and_pan(doc, 100, 100) is None
