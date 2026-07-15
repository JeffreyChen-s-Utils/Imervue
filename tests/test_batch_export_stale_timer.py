"""The batch motion exporter must ignore a stop-timer from a cancelled run.

stop()ing a batch mid-motion then starting a new one within the pending
timer window let the stale singleShot fire and stop the NEW run's recorder early,
truncating its first clip. Stop timers are now tagged with a sequence.
Driven unbound on fakes.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.puppet.batch_export import BatchMotionExporter


def test_stop_current_recording_ignores_a_stale_sequence():
    stopped: list = []
    recorder = SimpleNamespace(is_recording=lambda: True,
                               stop=lambda: stopped.append(True))
    fake = SimpleNamespace(_record_seq=5, _recorder=recorder)
    BatchMotionExporter._stop_current_recording(fake, seq=3)   # stale run
    assert stopped == []
    BatchMotionExporter._stop_current_recording(fake, seq=5)   # current run
    assert stopped == [True]


def test_stop_bumps_the_sequence_to_invalidate_pending_timers():
    recorder = SimpleNamespace(is_recording=lambda: False, stop=lambda: None)
    fake = SimpleNamespace(_active=True, _record_seq=2, _recorder=recorder)
    BatchMotionExporter.stop(fake)
    assert fake._active is False
    assert fake._record_seq == 3   # a pending seq-2 timer is now stale
