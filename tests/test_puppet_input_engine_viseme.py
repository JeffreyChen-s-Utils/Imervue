"""Mic lip-sync must marshal onto the GUI thread with a queued signal.

``_on_audio_block`` runs on sounddevice's callback thread, which has no Qt event
loop, so ``QTimer.singleShot`` posted there never fired and lip-sync did nothing.
It now emits ``_viseme_ready``. Driven with a fake canvas -- no GL widget, so this
runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.puppet.input_engine import InputEngine


def test_on_audio_block_emits_the_viseme_signal(qapp):
    engine = InputEngine(SimpleNamespace(
        document=lambda: object(),                 # not None -> proceeds
        set_parameter_values=lambda vals: None,
    ))
    received: list = []
    engine._viseme_ready.connect(received.append)
    engine._on_audio_block(np.zeros((256, 1), dtype=np.float32), 256, None, None)
    assert len(received) == 1
    assert isinstance(received[0], dict)


def test_on_audio_block_is_a_noop_without_a_document(qapp):
    engine = InputEngine(SimpleNamespace(document=lambda: None))
    received: list = []
    engine._viseme_ready.connect(received.append)
    engine._on_audio_block(np.zeros((256, 1), dtype=np.float32), 256, None, None)
    assert received == []
