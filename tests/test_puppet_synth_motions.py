"""Tests for the synthetic-motion fallback used when a Cubism rig
ships zero or near-zero authored motions.

The synth pack is intentionally conservative — only emits motions for
parameters the document actually declares, never overrides authored
motions, and produces purely linear segments so the runtime sampler
can read them without any cubic-bezier plumbing.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import Parameter, PuppetDocument
from Imervue.puppet.synth_motions import synthesise_idle_motions
from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_X,
    PARAM_BREATH,
    PARAM_EYE_L_OPEN,
    PARAM_EYE_R_OPEN,
)


def _doc_with(params: list[Parameter]) -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    doc.parameters = params
    return doc


# ---------------------------------------------------------------------------
# Coverage of the four synth motions
# ---------------------------------------------------------------------------


def test_synth_returns_empty_when_no_parameters_match():
    """Rig with zero compatible parameters yields zero motions —
    avoids polluting the picker with empty placeholders."""
    doc = _doc_with([
        Parameter(id="WhateverElse", min=0.0, max=1.0, default=0.5),
    ])
    assert synthesise_idle_motions(doc) == []


def test_synth_emits_head_sway_when_angle_x_present():
    doc = _doc_with([
        Parameter(id=PARAM_ANGLE_X, min=-30.0, max=30.0, default=0.0),
    ])
    motions = synthesise_idle_motions(doc)
    names = [m.name for m in motions]
    assert "synth_head_sway" in names
    head = next(m for m in motions if m.name == "synth_head_sway")
    assert head.loop is True
    assert head.group == "Idle"
    assert head.duration == pytest.approx(4.0)
    assert any(t.param_id == PARAM_ANGLE_X for t in head.tracks)


def test_synth_emits_blink_when_both_eyes_present():
    doc = _doc_with([
        Parameter(id=PARAM_EYE_L_OPEN, min=0.0, max=1.0, default=1.0),
        Parameter(id=PARAM_EYE_R_OPEN, min=0.0, max=1.0, default=1.0),
    ])
    motions = synthesise_idle_motions(doc)
    blink = next(m for m in motions if m.name == "synth_blink")
    track_ids = {t.param_id for t in blink.tracks}
    assert track_ids == {PARAM_EYE_L_OPEN, PARAM_EYE_R_OPEN}


def test_synth_emits_breath_when_only_breath_present():
    doc = _doc_with([
        Parameter(id=PARAM_BREATH, min=0.0, max=1.0, default=0.5),
    ])
    motions = synthesise_idle_motions(doc)
    assert [m.name for m in motions] == ["synth_breath"]
    breath = motions[0]
    assert breath.tracks[0].param_id == PARAM_BREATH
    assert breath.duration == pytest.approx(3.5)


def test_synth_emits_body_lean_when_body_param_present():
    doc = _doc_with([
        Parameter(id=PARAM_BODY_ANGLE_X, min=-10.0, max=10.0, default=0.0),
    ])
    motions = synthesise_idle_motions(doc)
    body = next(m for m in motions if m.name == "synth_body_lean")
    assert body.tracks[0].param_id == PARAM_BODY_ANGLE_X


# ---------------------------------------------------------------------------
# Track-shape invariants — segments must be monotonic + non-empty
# ---------------------------------------------------------------------------


def test_synth_segments_are_monotonic_in_time():
    """Every track's segments must have p0.t < p1.t and chain
    end-to-start without overlap. A malformed timeline would crash the
    motion sampler at playback."""
    doc = _doc_with([
        Parameter(id=PARAM_ANGLE_X, min=-30.0, max=30.0, default=0.0),
        Parameter(id=PARAM_ANGLE_Z, min=-30.0, max=30.0, default=0.0),
    ])
    for motion in synthesise_idle_motions(doc):
        for track in motion.tracks:
            for seg in track.segments:
                assert seg.p0[0] < seg.p1[0]
            for prev, curr in zip(
                track.segments, track.segments[1:], strict=False,
            ):
                assert prev.p1[0] == pytest.approx(curr.p0[0])


def test_synth_motions_have_fade_durations():
    """All synth motions ship a non-zero fade so the motion player
    cross-fades rather than hard-snapping when the user clicks one."""
    doc = _doc_with([
        Parameter(id=PARAM_ANGLE_X, min=-30.0, max=30.0, default=0.0),
    ])
    for motion in synthesise_idle_motions(doc):
        assert motion.fade_in_duration > 0.0
        assert motion.fade_out_duration > 0.0


def test_synth_track_values_stay_within_parameter_range():
    """Synth motions must not push beyond a parameter's authored min /
    max. Out-of-range writes would either crash the renderer or
    introduce visible discontinuities at the playback wrap."""
    doc = _doc_with([
        Parameter(id=PARAM_ANGLE_X, min=-30.0, max=30.0, default=0.0),
        Parameter(id=PARAM_BREATH, min=0.0, max=1.0, default=0.5),
    ])
    param_lookup = {p.id: p for p in doc.parameters}
    for motion in synthesise_idle_motions(doc):
        for track in motion.tracks:
            parameter = param_lookup.get(track.param_id)
            if parameter is None:
                continue
            for seg in track.segments:
                for _, value in (seg.p0, seg.p1):
                    assert parameter.min - 1e-9 <= value <= parameter.max + 1e-9
