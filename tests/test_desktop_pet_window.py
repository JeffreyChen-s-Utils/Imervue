"""Tests for the :class:`PetWindow` overlay construction.

The overlay's GL canvas can't really render in headless CI, but
the window-flag plumbing is testable: the right flag combination
must be set before show, click-through toggle has to round-trip
without losing the other flags, and the auxiliary state (drag
offset, snap threshold) needs sane defaults.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.desktop_pet.edge_snap import DEFAULT_SNAP_THRESHOLD
from Imervue.desktop_pet.pet_window import (
    DRAG_MOTION_GROUP,
    LAND_MOTION_GROUP,
    PET_IDLE_CYCLE_DURATION_S,
    PetWindow,
)
from Imervue.puppet.document import (
    Motion,
    MotionSegment,
    MotionTrack,
    PuppetDocument,
)
from Imervue.puppet.idle_motion_cycler import DEFAULT_CYCLE_DURATION_S


def _has_flag(flags: Qt.WindowType, target: Qt.WindowType) -> bool:
    return bool(int(flags) & int(target))


def test_window_flags_include_frameless_topmost_tool(qapp):
    """A frameless, always-on-top, tool-window combo is the
    table-stakes desktop-pet flag set — every commercial widget
    uses these three together."""
    window = PetWindow()
    try:
        flags = window.windowFlags()
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)
        assert _has_flag(flags, Qt.WindowType.Tool)
    finally:
        window.deleteLater()


def test_window_starts_without_click_through(qapp):
    """Default state must be "interactive" — a click-through-by-
    default pet would be undraggable on first show, which is
    confusing UX."""
    window = PetWindow()
    try:
        assert window.click_through_enabled() is False
        flags = window.windowFlags()
        assert not _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
    finally:
        window.deleteLater()


def test_click_through_toggle_round_trip(qapp):
    """Enabling then disabling click-through must preserve the
    other window flags — the toggle rebuilds the flag bitmask
    and a buggy rebuild would silently drop FramelessWindowHint."""
    window = PetWindow()
    try:
        window.set_click_through(True)
        assert window.click_through_enabled() is True
        flags = window.windowFlags()
        assert _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)

        window.set_click_through(False)
        assert window.click_through_enabled() is False
        flags = window.windowFlags()
        assert not _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)
    finally:
        window.deleteLater()


def test_idempotent_click_through_set(qapp):
    """Calling ``set_click_through(False)`` on an already-False
    instance must be a no-op — Qt re-creates the native window on
    flag changes, so silent re-applications would cause flicker."""
    window = PetWindow()
    try:
        window.set_click_through(False)  # already False
        assert window.click_through_enabled() is False
        window.set_click_through(True)
        window.set_click_through(True)   # already True
        assert window.click_through_enabled() is True
    finally:
        window.deleteLater()


def test_translucent_background_attribute_set(qapp):
    """The translucent-background attribute is what makes the
    desktop visible through the canvas's transparent clear. Lose
    it and the pet's edges render against an opaque widget
    background (usually black)."""
    window = PetWindow()
    try:
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    finally:
        window.deleteLater()


def test_default_snap_threshold_matches_helper(qapp):
    window = PetWindow()
    try:
        assert window._snap_threshold == DEFAULT_SNAP_THRESHOLD   # noqa: SLF001
    finally:
        window.deleteLater()


def test_canvas_is_in_pet_mode(qapp):
    """The embedded canvas must be constructed in pet mode so
    its ``initializeGL`` clears to fully-transparent instead of
    the editor checker backdrop."""
    window = PetWindow()
    try:
        canvas = window.canvas()
        assert canvas._pet_mode is True   # noqa: SLF001
    finally:
        window.deleteLater()


def test_pet_mode_canvas_has_translucent_attributes(qapp):
    """Without the WA_TranslucentBackground / WA_NoSystemBackground /
    WA_AlwaysStackOnTop trio on the GL widget itself, Qt paints an
    opaque system-coloured backdrop behind it before the GL render
    runs — and the user sees a grey rectangle around the puppet on
    their desktop. The attributes have to be set on the canvas, not
    just on the host window."""
    window = PetWindow()
    try:
        canvas = window.canvas()
        assert canvas.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert canvas.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        assert canvas.testAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
    finally:
        window.deleteLater()


def test_pet_idle_cycle_duration_is_faster_than_editor_default(qapp):
    """The desktop overlay must turn idle motions over faster than
    the editor workspace — a frozen-looking pet on the user's desk
    is the bug; a slightly busier authoring preview is acceptable."""
    assert PET_IDLE_CYCLE_DURATION_S < DEFAULT_CYCLE_DURATION_S


def test_idle_cycler_uses_pet_specific_cycle_duration(qapp):
    """First-time enable of the idle-motion cycler must apply the
    desktop-pet override so users see livelier turnover than the
    8s editor default."""
    window = PetWindow()
    try:
        window.set_idle_motion_enabled(True)
        cycler = window._idle_cycler   # noqa: SLF001
        assert cycler is not None
        assert cycler.cycle_duration() == PET_IDLE_CYCLE_DURATION_S
    finally:
        window.set_idle_motion_enabled(False)
        window.deleteLater()


def test_mouse_gaze_lazy_constructed(qapp):
    """The gaze driver is heavy enough (QTimer + per-tick QCursor
    poll) that we don't pay for it until the user enables it."""
    window = PetWindow()
    try:
        assert window._mouse_gaze is None   # noqa: SLF001
        window.set_mouse_gaze_enabled(True)
        assert window._mouse_gaze is not None   # noqa: SLF001
        assert window._mouse_gaze.is_enabled() is True   # noqa: SLF001
    finally:
        window.set_mouse_gaze_enabled(False)
        window.deleteLater()


def test_mouse_gaze_persists_to_settings(qapp):
    """Toggling the gaze driver must persist the ``mouse_gaze`` key
    so the next session restores the user's choice."""
    from Imervue.desktop_pet import settings as pet_settings

    window = PetWindow()
    try:
        window.set_mouse_gaze_enabled(True)
        drivers = pet_settings.load()["drivers"]
        assert drivers["mouse_gaze"] is True
        window.set_mouse_gaze_enabled(False)
        drivers = pet_settings.load()["drivers"]
        assert drivers["mouse_gaze"] is False
    finally:
        window.deleteLater()


def _motion_in_group(name: str, group: str) -> Motion:
    return Motion(
        name=name, duration=1.0, loop=False, group=group,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(
                type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0),
            )],
        )],
    )


def _attach_doc_with_motions(window: PetWindow, *motions: Motion) -> None:
    doc = PuppetDocument(size=(32, 32))
    doc.motions = list(motions)
    window._canvas.load_document(doc)   # noqa: SLF001


def test_play_random_motion_in_group_returns_false_without_match(qapp):
    """Rig without a Drag group → silent no-op. The desktop pet's
    drag handler relies on this return value to decide whether the
    drag started a "real" motion."""
    window = PetWindow()
    try:
        _attach_doc_with_motions(window, _motion_in_group("idle_a", "Idle"))
        assert window.play_random_motion_in_group(DRAG_MOTION_GROUP) is False
    finally:
        window.deleteLater()


def test_play_random_motion_in_group_returns_true_when_played(qapp):
    """Happy path: rig has a Drag motion → returns True and the
    motion player picks it up."""
    window = PetWindow()
    try:
        drag = _motion_in_group("drag_a", DRAG_MOTION_GROUP)
        _attach_doc_with_motions(window, drag)
        assert window.play_random_motion_in_group(DRAG_MOTION_GROUP) is True
        assert window._motion_player.motion() is drag   # noqa: SLF001
    finally:
        window.deleteLater()


def test_play_random_motion_handles_no_document(qapp):
    """No rig loaded yet → must not crash. The drag handler can
    fire before the user picks a rig."""
    window = PetWindow()
    try:
        assert window.play_random_motion_in_group(DRAG_MOTION_GROUP) is False
        assert window.play_random_motion_in_group(LAND_MOTION_GROUP) is False
    finally:
        window.deleteLater()


def test_drag_and_land_group_constants_distinct(qapp):
    """If these collide the drag and the land hook would race for
    the same group — kind of an obvious typo guard, but worth one
    test since the strings are user-visible Cubism conventions."""
    assert DRAG_MOTION_GROUP != LAND_MOTION_GROUP
    assert DRAG_MOTION_GROUP and LAND_MOTION_GROUP   # neither empty


def test_default_drivers_include_idle_breath_blink(qapp):
    """Fresh install must show a *moving* pet — auto_idle (breath),
    idle_motion (random cycle), and auto_blink are all zero-dep and
    expected on by default. Static figures feel broken."""
    from Imervue.desktop_pet import settings as pet_settings

    defaults = pet_settings.DEFAULTS["drivers"]
    assert defaults["auto_idle"] is True
    assert defaults["idle_motion"] is True
    assert defaults["auto_blink"] is True
    # External-dep drivers stay off — flipping them requires user
    # intent (mic permission, webcam permission, etc.).
    assert defaults["mic_lipsync"] is False
    assert defaults["webcam_tracking"] is False


def test_drivers_restored_from_settings_on_construct(qapp):
    """Persisting a driver as enabled then constructing a new pet
    window must auto-start the driver — covers the "pet launched
    from tray before workspace tab was opened" path that previously
    left the pet static."""
    from Imervue.desktop_pet import settings as pet_settings

    pet_settings.update(drivers={
        "auto_idle": True,
        "idle_motion": False,
        "auto_blink": True,
        "drag_track": False,
        "mouse_gaze": False,
        "mic_lipsync": False,
        "webcam_tracking": False,
    })
    window = PetWindow()
    try:
        assert window._idle_driver is not None   # noqa: SLF001
        assert window._idle_driver.is_enabled() is True   # noqa: SLF001
        # idle_motion was False → cycler stays uncreated.
        assert window._idle_cycler is None   # noqa: SLF001
        assert window._input_engine.blink_enabled() is True
    finally:
        window.deleteLater()


def test_reapply_flags_preserves_translucent_attribute(qapp):
    """Qt re-creates the native window on flag changes, dropping
    widget attributes. The reapply path must re-set
    WA_TranslucentBackground or the pet renders against an opaque
    backdrop after toggling click-through / always-on-bottom."""
    window = PetWindow()
    try:
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        window.set_click_through(True)
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        window.set_always_on_bottom(True)
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        window.set_click_through(False)
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    finally:
        window.deleteLater()


def test_hotkey_action_router_toggles_visibility(qapp):
    """The action router is the bridge between a hotkey hit and a
    window operation. Toggle-visible must flip between hide / show
    without going through the system menu."""
    from Imervue.desktop_pet.hotkey_manager import ACTION_TOGGLE_VISIBLE

    window = PetWindow()
    try:
        window.show()
        assert window.isVisible() is True
        window._on_hotkey_action(ACTION_TOGGLE_VISIBLE)   # noqa: SLF001
        qapp.processEvents()
        assert window.isVisible() is False
        window._on_hotkey_action(ACTION_TOGGLE_VISIBLE)   # noqa: SLF001
        qapp.processEvents()
        assert window.isVisible() is True
    finally:
        window.deleteLater()


def test_hotkey_action_router_toggles_anchor_lock(qapp):
    """Lock action flips the anchor_locked flag — same effect as
    the menu toggle."""
    from Imervue.desktop_pet.hotkey_manager import ACTION_TOGGLE_LOCK

    window = PetWindow()
    try:
        start = window._anchor_locked   # noqa: SLF001
        window._on_hotkey_action(ACTION_TOGGLE_LOCK)   # noqa: SLF001
        assert window._anchor_locked is (not start)   # noqa: SLF001
    finally:
        window.deleteLater()


def test_hotkey_action_unknown_action_is_silent(qapp):
    """Unknown action strings must be ignored — a stale binding
    from an older settings file mustn't crash the listener
    callback."""
    window = PetWindow()
    try:
        window._on_hotkey_action("nonexistent_action")   # noqa: SLF001
    finally:
        window.deleteLater()


def test_virtual_camera_lazy_constructed(qapp):
    """The output is heavy (off-screen FBO + per-tick render);
    keep it lazy so users who don't enable it never pay the cost."""
    window = PetWindow()
    try:
        assert window._virtual_camera is None   # noqa: SLF001
        # Disable path runs without ever creating the object.
        window.set_virtual_camera_enabled(False)
        assert window._virtual_camera is None   # noqa: SLF001
    finally:
        window.deleteLater()


def test_virtual_camera_enable_returns_false_without_dep(qapp):
    """No pyvirtualcam (CI / headless) → ``set_enabled`` surfaces
    ``False`` and the persisted flag stays off so the next launch
    doesn't auto-retry. Verified indirectly: enabling without
    loading a rig returns False because the output refuses to start
    on an empty canvas."""
    window = PetWindow()
    try:
        ok = window.set_virtual_camera_enabled(True)
        assert ok is False
        assert window.virtual_camera_enabled() is False
    finally:
        window.deleteLater()


def test_persisted_bindings_merge_with_defaults(qapp):
    """Custom + default bindings merge so a user who saved only one
    custom binding keeps the others — same forward-compat rule
    other settings sections use."""
    from Imervue.desktop_pet import settings as pet_settings
    from Imervue.desktop_pet.hotkey_manager import (
        ACTION_TOGGLE_VISIBLE,
        DEFAULT_HOTKEY_BINDINGS,
    )

    pet_settings.update(hotkeys={ACTION_TOGGLE_VISIBLE: "ctrl+alt+m"})
    window = PetWindow()
    try:
        merged = window._persisted_bindings()   # noqa: SLF001
        assert merged[ACTION_TOGGLE_VISIBLE] == "ctrl+alt+m"
        # Defaults survived for the actions the user didn't override.
        for action, default in DEFAULT_HOTKEY_BINDINGS.items():
            if action != ACTION_TOGGLE_VISIBLE:
                assert merged[action] == default
    finally:
        window.deleteLater()


def test_pet_shadow_default_enabled(qapp):
    """Fresh install ships with the drop shadow on so the rig
    looks "grounded" without a tuning detour."""
    window = PetWindow()
    try:
        assert window.pet_shadow_enabled() is True
    finally:
        window.deleteLater()


def test_pet_shadow_toggle_persists(qapp):
    """Toggling the shadow flows through to both the canvas and
    the persisted settings — so the next launch restores the
    chosen state."""
    from Imervue.desktop_pet import settings as pet_settings

    window = PetWindow()
    try:
        window.set_pet_shadow_enabled(False)
        assert window.pet_shadow_enabled() is False
        assert pet_settings.load()["pet_shadow_enabled"] is False
        window.set_pet_shadow_enabled(True)
        assert window.pet_shadow_enabled() is True
        assert pet_settings.load()["pet_shadow_enabled"] is True
    finally:
        window.deleteLater()


def test_pet_shadow_opacity_clamps(qapp):
    from Imervue.desktop_pet import settings as pet_settings

    window = PetWindow()
    try:
        window.set_pet_shadow_opacity(5.0)
        assert pet_settings.load()["pet_shadow_opacity"] == 1.0
        window.set_pet_shadow_opacity(-1.0)
        assert pet_settings.load()["pet_shadow_opacity"] == 0.0
    finally:
        window.deleteLater()


def test_pet_shadow_scale_clamps(qapp):
    from Imervue.desktop_pet import settings as pet_settings

    window = PetWindow()
    try:
        window.set_pet_shadow_scale(5.0)
        assert pet_settings.load()["pet_shadow_scale"] == 2.0
        window.set_pet_shadow_scale(-1.0)
        assert pet_settings.load()["pet_shadow_scale"] == 0.0
    finally:
        window.deleteLater()


def test_load_puppet_file_returns_false_on_missing(qapp, tmp_path):
    """A non-existent ``.puppet`` archive must produce a False
    return rather than raising — the workspace's status label is
    the user-facing reporting channel."""
    window = PetWindow()
    try:
        result = window.load_puppet_file(tmp_path / "does-not-exist.puppet")
        assert result is False
        assert window.document() is None
    finally:
        window.deleteLater()
