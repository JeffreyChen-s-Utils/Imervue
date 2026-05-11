"""Verlet physics engine for ``.puppet`` physics rigs.

Each :class:`PhysicsRig` is one independent particle chain: its anchor
follows an input parameter, gravity + damping + per-particle springs
pull the chain back toward its rest pose, and the tip's lateral
displacement drives an output parameter.

Pure-numpy / Qt-free. The canvas drives ``PhysicsEngine.step(dt)`` on
its frame timer. Implementation choice: position-Verlet integration
(stores current + previous positions) — stable for chains of <= 16
particles at 60 FPS without iterative constraint solves.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from puppet.document import PhysicsRig, PuppetDocument

REST_LENGTH: float = 30.0
"""Distance between adjacent particles at rest, in image-space pixels."""

OUTPUT_GAIN: float = 1.0 / REST_LENGTH
"""Maps tip lateral displacement (px) to output parameter (~unit range)."""


@dataclass
class _ChainState:
    positions: np.ndarray   # (N, 2) float64 — current
    previous: np.ndarray   # (N, 2) float64 — for verlet velocity
    rig: PhysicsRig


class PhysicsEngine:
    """Drives every PhysicsRig on a document.

    Hold one engine per workspace; call :meth:`bind_document` whenever
    a new puppet loads, then :meth:`step` once per frame.
    """

    def __init__(self) -> None:
        self._chains: dict[str, _ChainState] = {}

    def bind_document(self, document: PuppetDocument | None) -> None:
        """(Re)build the per-rig state from ``document.physics_rigs``."""
        self._chains = {}
        if document is None:
            return
        for rig in document.physics_rigs:
            self._chains[rig.id] = _build_initial_state(rig)

    def chain_ids(self) -> list[str]:
        return list(self._chains.keys())

    def particle_positions(self, rig_id: str) -> np.ndarray:
        """Return the current chain positions for inspection / debug
        rendering. Returns an empty array when the rig isn't bound."""
        state = self._chains.get(rig_id)
        if state is None:
            return np.empty((0, 2), dtype=np.float64)
        return state.positions.copy()

    def reset(self) -> None:
        """Snap every chain back to its rest pose."""
        for state in self._chains.values():
            rest = _rest_positions(state.rig)
            state.positions = rest.copy()
            state.previous = rest.copy()

    def step(self, dt: float, parameter_values: dict[str, float]) -> dict[str, float]:
        """Advance every chain by ``dt`` seconds. Returns a partial
        ``{output_param_id: value}`` map the caller layers onto the
        live parameter dict before composing vertices."""
        outputs: dict[str, float] = {}
        if dt <= 0.0:
            return outputs
        for state in self._chains.values():
            anchor_input = float(parameter_values.get(state.rig.input_param, 0.0))
            output = self._step_chain(state, dt, anchor_input)
            outputs[state.rig.output_param] = output
        return outputs

    def _step_chain(
        self, state: _ChainState, dt: float, anchor_input: float,
    ) -> float:
        rig = state.rig
        positions = state.positions
        previous = state.previous
        n = positions.shape[0]
        if n == 0:
            return 0.0
        rest = _rest_positions(rig)
        # The anchor (particle 0) is pinned to a position that moves
        # laterally with the input parameter.
        positions[0] = rest[0] + np.array(
            [anchor_input * REST_LENGTH, 0.0], dtype=np.float64,
        )
        previous[0] = positions[0]
        # Integrate every non-anchor particle.
        gravity = np.asarray(rig.gravity, dtype=np.float64)
        for i in range(1, n):
            particle = rig.chain[i]
            damping = max(0.0, min(0.999, float(particle.damping)))
            velocity = (positions[i] - previous[i]) * (1.0 - damping)
            previous[i] = positions[i].copy()
            positions[i] = positions[i] + velocity + gravity * (dt * dt)
        # Springs pull each particle back toward its rest offset from
        # its parent. Single iteration is plenty at 60 FPS for short chains.
        for i in range(1, n):
            spring = max(0.0, float(rig.chain[i].spring))
            target = positions[i - 1] + (rest[i] - rest[i - 1])
            delta = target - positions[i]
            positions[i] = positions[i] + delta * min(1.0, spring * dt)
        # Tip lateral displacement → output parameter
        tip_offset_x = positions[-1, 0] - rest[-1, 0]
        return float(np.clip(tip_offset_x * OUTPUT_GAIN, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_initial_state(rig: PhysicsRig) -> _ChainState:
    rest = _rest_positions(rig)
    return _ChainState(
        positions=rest.copy(),
        previous=rest.copy(),
        rig=rig,
    )


def _rest_positions(rig: PhysicsRig) -> np.ndarray:
    """Particles hang straight down from the anchor at REST_LENGTH
    intervals — the canonical rest pose for hair / ribbon chains."""
    n = max(1, len(rig.chain))
    out = np.zeros((n, 2), dtype=np.float64)
    for i in range(n):
        out[i] = (0.0, -float(i) * REST_LENGTH)
    return out
