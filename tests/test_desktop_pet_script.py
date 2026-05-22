"""Tests for the pet-script engine.

Pure-Python — no Qt, no display required. Covers:

* defaults / `to_dict` round-trip
* JSON load handles missing / wrong-typed fields gracefully
* loader error path raises the dedicated :class:`PetScriptError`
* engine sampling is round-robin per bucket (no consecutive repeat)
* hit-area / motion / greeting fallback chain
* scheduled events fire after their interval, then reset
* swapping the script via :meth:`set_script` resets cursors
"""
from __future__ import annotations

import time

import pytest

from Imervue.desktop_pet.pet_script import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_GREETINGS,
    TIME_OF_DAY_BANDS,
    PetScript,
    PetScriptEngine,
    PetScriptError,
    ScheduledEvent,
    load_script,
    save_script,
    time_of_day_band,
)


# ---------------------------------------------------------------
# Schema / serialisation
# ---------------------------------------------------------------


def test_default_script_carries_default_greetings():
    """Without a user script the engine still talks — the
    fallback voice is the same five-line set the pet shipped
    with before customisation existed."""
    script = PetScript.default()
    assert script.greetings == list(DEFAULT_GREETINGS)
    assert script.version == CURRENT_SCHEMA_VERSION


def test_to_dict_round_trips(tmp_path):
    """Saving then loading must give back the same data. Bug
    bait: a writer that drops a key would silently lose user
    edits on reload."""
    script = PetScript(
        version=1, name="test",
        greetings=["Hi!", "Hello!"],
        hit_responses={"head": ["Hey!"], "body": ["Pat!"]},
        motion_lines={"wave": ["Hi!"]},
        scheduled=[ScheduledEvent(every_seconds=60.0, messages=["Break?"])],
    )
    out = tmp_path / "script.json"
    save_script(script, out)
    reloaded = load_script(out)
    assert reloaded.name == "test"
    assert reloaded.greetings == ["Hi!", "Hello!"]
    assert reloaded.hit_responses == {"head": ["Hey!"], "body": ["Pat!"]}
    assert reloaded.motion_lines == {"wave": ["Hi!"]}
    assert len(reloaded.scheduled) == 1
    assert reloaded.scheduled[0].every_seconds == pytest.approx(60.0)
    assert reloaded.scheduled[0].messages == ["Break?"]


# ---------------------------------------------------------------
# Loader robustness
# ---------------------------------------------------------------


def test_loader_raises_for_missing_file(tmp_path):
    with pytest.raises(PetScriptError):
        load_script(tmp_path / "nope.json")


def test_loader_raises_for_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not actual json", encoding="utf-8")
    with pytest.raises(PetScriptError):
        load_script(bad)


def test_loader_raises_for_non_object_root(tmp_path):
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(PetScriptError):
        load_script(arr)


def test_loader_coerces_partial_data(tmp_path):
    """A partial script (only greetings, no hit_responses) must
    still load — defaults fill in the gaps. Same forward-compat
    rule the user-settings file uses."""
    partial = tmp_path / "partial.json"
    partial.write_text('{"greetings": ["Hi!"]}', encoding="utf-8")
    script = load_script(partial)
    assert script.greetings == ["Hi!"]
    assert script.hit_responses == {}
    assert script.motion_lines == {}
    assert script.scheduled == []


def test_loader_skips_garbage_list_entries(tmp_path):
    """A non-string entry inside ``greetings`` must be dropped,
    not crash the load — keeps a partly-corrupted file usable."""
    garbage = tmp_path / "garbage.json"
    garbage.write_text(
        '{"greetings": ["Hi!", 42, null, "Hello!"]}',
        encoding="utf-8",
    )
    script = load_script(garbage)
    assert script.greetings == ["Hi!", "Hello!"]


def test_loader_skips_invalid_scheduled_entries(tmp_path):
    """Scheduled entries with non-positive intervals or missing
    fields drop; a single bad entry mustn't lose every chime."""
    p = tmp_path / "sched.json"
    p.write_text(
        '{"scheduled": ['
        ' {"every_seconds": 60, "messages": ["A"]},'
        ' {"every_seconds": 0, "messages": ["B"]},'
        ' {"every_seconds": -5, "messages": ["C"]},'
        ' "not a dict"'
        ']}',
        encoding="utf-8",
    )
    script = load_script(p)
    assert len(script.scheduled) == 1
    assert script.scheduled[0].messages == ["A"]


# ---------------------------------------------------------------
# Engine sampling
# ---------------------------------------------------------------


def test_greeting_round_robin_no_consecutive_repeat():
    """Consecutive clicks must show different lines — the round-
    robin cursor in the engine is what gives the pet personality
    rather than feeling like a stuck record."""
    engine = PetScriptEngine(PetScript(greetings=["A", "B", "C"]))
    seen = [engine.pick_greeting() for _ in range(6)]
    # Three lines, six picks → exact ABCABC.
    assert seen == ["A", "B", "C", "A", "B", "C"]


def test_hit_area_falls_back_to_greeting_when_unmapped():
    """An unknown hit area returns None so the click handler can
    fall through to the generic greeting set rather than going
    silent."""
    engine = PetScriptEngine(PetScript(
        greetings=["Hi!"],
        hit_responses={"head": ["Hey!"]},
    ))
    assert engine.pick_for_hit_area("unknown_area") is None
    assert engine.pick_for_hit_area(None) is None
    assert engine.pick_for_hit_area("head") == "Hey!"


def test_motion_returns_none_when_unmapped():
    """An unscripted motion stays silent — better than blurting
    a generic greeting when the user authored an empty motion
    line bucket on purpose."""
    engine = PetScriptEngine(PetScript(motion_lines={"wave": ["Hi!"]}))
    assert engine.pick_for_motion("unknown") is None
    assert engine.pick_for_motion("wave") == "Hi!"


def test_greeting_falls_back_to_defaults_when_script_empty():
    """A script that explicitly clears the greetings still shows
    a line — the engine layers default greetings underneath so
    the pet never goes mute on a misconfigured file."""
    engine = PetScriptEngine(PetScript(greetings=[]))
    line = engine.pick_greeting()
    assert line in DEFAULT_GREETINGS


def test_set_script_resets_cursors():
    """Swapping scripts must reset the round-robin cursors so
    the new lines start from index 0 rather than continuing
    from where the old script left off."""
    engine = PetScriptEngine(PetScript(greetings=["A", "B"]))
    assert engine.pick_greeting() == "A"
    engine.set_script(PetScript(greetings=["X", "Y"]))
    assert engine.pick_greeting() == "X"


# ---------------------------------------------------------------
# Scheduled events
# ---------------------------------------------------------------


def test_scheduled_event_not_due_immediately(monkeypatch):
    """A freshly-created engine must not fire any scheduled chime
    before its interval has elapsed — otherwise opening the pet
    would binge-fire every queued event."""
    engine = PetScriptEngine(PetScript(
        scheduled=[ScheduledEvent(every_seconds=60.0, messages=["A"])],
    ))
    assert engine.due_scheduled_message() is None


def test_scheduled_event_fires_after_interval(monkeypatch):
    """Once the wall-clock interval passes, the next tick fires."""
    base = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: base[0])
    engine = PetScriptEngine(PetScript(
        scheduled=[ScheduledEvent(every_seconds=60.0, messages=["chime"])],
    ))
    # 30 s in — not due yet.
    base[0] = 1030.0
    assert engine.due_scheduled_message() is None
    # 65 s in — overdue, fire.
    base[0] = 1065.0
    assert engine.due_scheduled_message() == "chime"
    # And reset — next call doesn't immediately re-fire.
    assert engine.due_scheduled_message() is None
    # Another 60 s and we should fire again.
    base[0] = 1126.0
    assert engine.due_scheduled_message() == "chime"


def test_scheduled_event_with_empty_messages_does_not_fire(monkeypatch):
    """An entry with a valid interval but empty messages list
    must be silently skipped — not raise IndexError."""
    base = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: base[0])
    engine = PetScriptEngine(PetScript(
        scheduled=[
            ScheduledEvent(every_seconds=60.0, messages=[]),
            ScheduledEvent(every_seconds=60.0, messages=["B"]),
        ],
    ))
    base[0] = 65.0
    assert engine.due_scheduled_message() == "B"


# ---------------------------------------------------------------
# Time-of-day greetings
# ---------------------------------------------------------------


def test_time_of_day_band_thresholds():
    """Boundary check on every band edge — off-by-one here would
    mean the user wakes up to a "good night" greeting at 5 AM."""
    assert time_of_day_band(5) == "morning"     # start of morning
    assert time_of_day_band(11) == "morning"
    assert time_of_day_band(12) == "afternoon"  # start of afternoon
    assert time_of_day_band(17) == "afternoon"
    assert time_of_day_band(18) == "evening"
    assert time_of_day_band(21) == "evening"
    assert time_of_day_band(22) == "night"
    assert time_of_day_band(4) == "night"
    assert time_of_day_band(0) == "night"


def test_time_of_day_band_wraps_out_of_range():
    """Robust to garbage input — timezone math sometimes overshoots
    into negative or >=24 hour values; the band should still resolve
    rather than raise."""
    assert time_of_day_band(25) == "night"        # 25 % 24 == 1 → night
    assert time_of_day_band(-1) == "night"        # -1 % 24 == 23 → night
    assert time_of_day_band(36) == "afternoon"    # 36 % 24 == 12 → afternoon


def test_time_of_day_bands_constant_lists_four_bands():
    """Schema lists exactly four bands — adding a fifth without
    updating the band function would silently drop user lines."""
    assert TIME_OF_DAY_BANDS == ("morning", "afternoon", "evening", "night")


def test_pick_time_of_day_greeting_picks_band():
    """Happy path — the engine picks from the requested band when
    that band has lines."""
    engine = PetScriptEngine(PetScript(
        time_of_day_greetings={
            "morning": ["Morning A", "Morning B"],
            "night": ["Night A"],
        },
    ))
    assert engine.pick_time_of_day_greeting(hour=7) == "Morning A"
    assert engine.pick_time_of_day_greeting(hour=7) == "Morning B"
    assert engine.pick_time_of_day_greeting(hour=23) == "Night A"


def test_pick_time_of_day_greeting_returns_none_when_empty():
    """No lines authored for the current band → ``None`` so the
    caller can fall through to ``pick_greeting``. Returning a plain
    greeting here would defeat the whole "time-of-day takes priority"
    chain in pet_window."""
    engine = PetScriptEngine(PetScript(
        time_of_day_greetings={"morning": ["Hi!"]},
        greetings=["fallback"],
    ))
    # Afternoon band — no lines, must return None even though greetings exist.
    assert engine.pick_time_of_day_greeting(hour=14) is None


def test_pick_time_of_day_greeting_with_no_section_returns_none():
    """Script without any time-of-day greetings authored → every
    band returns None. Same forward-compat rule as the other engine
    helpers."""
    engine = PetScriptEngine(PetScript(greetings=["Hi!"]))
    for hour in range(0, 24, 3):
        assert engine.pick_time_of_day_greeting(hour=hour) is None


def test_pick_time_of_day_greeting_default_hour_reads_clock():
    """No ``hour`` kwarg → engine consults ``datetime.now()``. We
    can't monkeypatch datetime cleanly, but we can verify the call
    succeeds and returns the right type."""
    engine = PetScriptEngine(PetScript(
        time_of_day_greetings={
            "morning": ["m"], "afternoon": ["a"],
            "evening": ["e"], "night": ["n"],
        },
    ))
    line = engine.pick_time_of_day_greeting()
    # Every band has a line, so any non-None hour resolves; assert
    # we got *something* rather than the actual band (which depends
    # on the wall clock at test time).
    assert line in {"m", "a", "e", "n"}


def test_loader_drops_unknown_time_of_day_bands(tmp_path):
    """Typo'd band keys like ``mornig`` must not survive load —
    otherwise they'd sit as a never-firing bucket until the user
    notices the typo (which could be never)."""
    p = tmp_path / "tod.json"
    p.write_text(
        '{"time_of_day_greetings": {'
        ' "morning": ["good morning"],'
        ' "mornig": ["typo"],'
        ' "afternoon": ["good afternoon"]'
        '}}',
        encoding="utf-8",
    )
    script = load_script(p)
    assert set(script.time_of_day_greetings.keys()) == {"morning", "afternoon"}


def test_time_of_day_round_trips_through_save_load(tmp_path):
    """Save → load preserves the section. Catches a writer that
    drops the new schema field."""
    script = PetScript(
        time_of_day_greetings={
            "evening": ["Evening!"], "night": ["Late!"],
        },
    )
    p = tmp_path / "tod_rt.json"
    save_script(script, p)
    reloaded = load_script(p)
    assert reloaded.time_of_day_greetings == {
        "evening": ["Evening!"], "night": ["Late!"],
    }


def test_time_of_day_round_robin_uses_separate_cursors():
    """Each band has its own cursor — picking morning shouldn't
    fast-forward the night cursor."""
    engine = PetScriptEngine(PetScript(
        time_of_day_greetings={
            "morning": ["A", "B"],
            "night": ["X", "Y"],
        },
    ))
    assert engine.pick_time_of_day_greeting(hour=7) == "A"
    assert engine.pick_time_of_day_greeting(hour=23) == "X"
    assert engine.pick_time_of_day_greeting(hour=7) == "B"
    assert engine.pick_time_of_day_greeting(hour=23) == "Y"


def test_set_script_resets_time_of_day_cursors():
    """``set_script`` already resets every cursor — same rule must
    apply to the new TOD buckets, otherwise the new script's first
    pick could land on index N instead of 0."""
    engine = PetScriptEngine(PetScript(
        time_of_day_greetings={"morning": ["A", "B"]},
    ))
    assert engine.pick_time_of_day_greeting(hour=7) == "A"
    engine.set_script(PetScript(
        time_of_day_greetings={"morning": ["X", "Y"]},
    ))
    assert engine.pick_time_of_day_greeting(hour=7) == "X"
