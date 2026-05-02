"""Tests for the onboarding tour registry and dialog."""
from __future__ import annotations

from Imervue.system.onboarding import (
    ONBOARDING_STEPS,
    OnboardingStep,
    step_count,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Step registry
# ---------------------------------------------------------------------------


def test_steps_exist():
    assert step_count() >= 1
    assert step_count() == len(ONBOARDING_STEPS)


def test_each_step_has_title_and_body():
    for step in ONBOARDING_STEPS:
        assert isinstance(step, OnboardingStep)
        assert step.title_key
        assert step.title_fallback
        assert step.body_key
        assert step.body_fallback


def test_keys_are_unique():
    """Title and body keys should be unique so the dialog never reuses a string."""
    title_keys = [s.title_key for s in ONBOARDING_STEPS]
    body_keys = [s.body_key for s in ONBOARDING_STEPS]
    assert len(title_keys) == len(set(title_keys))
    assert len(body_keys) == len(set(body_keys))


# ---------------------------------------------------------------------------
# Dialog (Qt)
# ---------------------------------------------------------------------------


def test_dialog_starts_on_first_step(qapp):
    from Imervue.gui.onboarding_dialog import OnboardingDialog
    dlg = OnboardingDialog()
    first = ONBOARDING_STEPS[0]
    # Title shows the first step's fallback when no translation is loaded
    assert dlg._title_label.text() in (first.title_fallback,
                                       first.title_key)


def test_dialog_back_disabled_at_start(qapp):
    from Imervue.gui.onboarding_dialog import OnboardingDialog
    dlg = OnboardingDialog()
    assert dlg._back_btn.isEnabled() is False


def test_dialog_advances_with_next(qapp):
    from Imervue.gui.onboarding_dialog import OnboardingDialog
    dlg = OnboardingDialog()
    initial = dlg._index
    dlg._go_next()
    assert dlg._index == initial + 1
    assert dlg._back_btn.isEnabled() is True


def test_dialog_back_returns_to_previous(qapp):
    from Imervue.gui.onboarding_dialog import OnboardingDialog
    dlg = OnboardingDialog()
    dlg._go_next()
    dlg._go_back()
    assert dlg._index == 0


def test_dialog_finish_marks_completed(qapp, monkeypatch):
    from Imervue.gui.onboarding_dialog import OnboardingDialog, _COMPLETED_KEY
    user_setting_dict.pop(_COMPLETED_KEY, None)
    dlg = OnboardingDialog()
    # Skip ahead to the last step then advance to "finish"
    dlg._index = step_count() - 1
    accepted = {"value": False}
    monkeypatch.setattr(dlg, "accept",
                        lambda: accepted.update(value=True))
    dlg._go_next()
    assert accepted["value"] is True
    assert user_setting_dict.get(_COMPLETED_KEY) is True


def test_skip_marks_completed(qapp, monkeypatch):
    from Imervue.gui.onboarding_dialog import OnboardingDialog, _COMPLETED_KEY
    user_setting_dict.pop(_COMPLETED_KEY, None)
    dlg = OnboardingDialog()
    rejected = {"value": False}
    monkeypatch.setattr(dlg, "reject",
                        lambda: rejected.update(value=True))
    dlg._skip()
    assert rejected["value"] is True
    assert user_setting_dict.get(_COMPLETED_KEY) is True


# ---------------------------------------------------------------------------
# Auto-popup gating
# ---------------------------------------------------------------------------


def test_show_onboarding_skips_when_completed(qapp, monkeypatch):
    from Imervue.gui import onboarding_dialog as mod
    user_setting_dict[mod._COMPLETED_KEY] = True
    called = {"value": False}
    monkeypatch.setattr(mod.OnboardingDialog, "exec",
                        lambda self: called.update(value=True))
    shown = mod.show_onboarding_if_first_run()
    assert shown is False
    assert called["value"] is False


def test_show_onboarding_runs_first_time(qapp, monkeypatch):
    from Imervue.gui import onboarding_dialog as mod
    user_setting_dict.pop(mod._COMPLETED_KEY, None)
    monkeypatch.setattr(mod.OnboardingDialog, "exec", lambda self: 1)
    shown = mod.show_onboarding_if_first_run()
    assert shown is True
