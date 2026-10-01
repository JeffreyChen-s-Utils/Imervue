"""Clicking a hit area plays its motion, whether it names a group or one motion.

A hit area naming a single motion only selected it in the Motions dock: the
rig stayed still until Play. These call the workspace handler on stand-ins
(``PuppetWorkspace`` builds a ``PuppetCanvas``, skipped on headless CI).
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.puppet.document import HitArea, Motion, PuppetDocument
from Imervue.puppet.workspace import PuppetWorkspace


def _host(area, motions, *, listed=True):
    doc = PuppetDocument(size=(10, 10))
    doc.hit_areas = [area]
    doc.motions = motions
    log = []
    player = SimpleNamespace(
        play=lambda: log.append("play"),
        play_group=lambda group, _motions: log.append(("play_group", group)))
    dock = SimpleNamespace(
        player=lambda: player,
        select_motion=lambda name: log.append(("select", name)) or listed)
    host = SimpleNamespace(
        _canvas=SimpleNamespace(document=lambda: doc, active_expressions=lambda: []),
        _motion_dock=dock, _announce=lambda *_args, **_kwargs: None)
    return host, log


def test_a_hit_area_naming_one_motion_plays_it():
    host, log = _host(HitArea(id="tap", drawables=[], motion="wave"),
                      [Motion(name="wave", duration=1.0)])
    PuppetWorkspace._on_hit_area_triggered(host, "tap")
    assert log == [("select", "wave"), "play"]


def test_a_hit_area_naming_a_group_plays_a_member():
    host, log = _host(HitArea(id="tap", drawables=[], motion="TapHead"),
                      [Motion(name="nod", duration=1.0, group="TapHead")])
    PuppetWorkspace._on_hit_area_triggered(host, "tap")
    assert log == [("play_group", "TapHead")]


def test_a_motion_the_dock_does_not_list_plays_nothing():
    host, log = _host(HitArea(id="tap", drawables=[], motion="gone"), [], listed=False)
    PuppetWorkspace._on_hit_area_triggered(host, "tap")
    assert log == [("select", "gone")]
