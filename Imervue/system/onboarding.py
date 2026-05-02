"""Onboarding tutorial step registry.

A flat, ordered list of dataclass entries — each one a screenful of
guided-tour content shown by ``Imervue.gui.onboarding_dialog``. Adding
a new step is a one-line change and the dialog picks it up
automatically.

Strings ship as i18n lookup keys with English fallbacks so the tour
respects the user's language choice.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnboardingStep:
    """One slide of the first-launch tour."""

    title_key: str
    title_fallback: str
    body_key: str
    body_fallback: str


# Five steps covering the most impactful entry points. Keep the body
# concise — the dialog is small and users skim, not read.
ONBOARDING_STEPS: list[OnboardingStep] = [
    OnboardingStep(
        title_key="onboarding_step_welcome_title",
        title_fallback="Welcome to Imervue",
        body_key="onboarding_step_welcome_body",
        body_fallback=(
            "A quick five-step tour of the main entry points. "
            "Press Next to continue, or Skip to dismiss the tour."
        ),
    ),
    OnboardingStep(
        title_key="onboarding_step_open_title",
        title_fallback="Open a folder",
        body_key="onboarding_step_open_body",
        body_fallback=(
            "File > Open Folder, or click any folder in the left tree. "
            "Imervue scans for images and shows them in the tile grid."
        ),
    ),
    OnboardingStep(
        title_key="onboarding_step_view_title",
        title_fallback="Browse and zoom",
        body_key="onboarding_step_view_body",
        body_fallback=(
            "Double-click a tile (or press Enter) to enter deep zoom. "
            "Arrow keys move between images. Esc returns to the grid."
        ),
    ),
    OnboardingStep(
        title_key="onboarding_step_develop_title",
        title_fallback="Develop without overwriting",
        body_key="onboarding_step_develop_body",
        body_fallback=(
            "Switch to the Modify tab to adjust exposure, contrast, "
            "tone curves, masks, and more. Edits are non-destructive — "
            "your originals are never overwritten."
        ),
    ),
    OnboardingStep(
        title_key="onboarding_step_extra_title",
        title_fallback="Extra Tools and plugins",
        body_key="onboarding_step_extra_body",
        body_fallback=(
            "The Extra Tools menu hosts the heavyweight features: AI "
            "upscale, panorama stitch, contact sheets, smart crop, "
            "denoise, colorize. Plugins extend the menu further."
        ),
    ),
]


def step_count() -> int:
    """Convenience accessor used by the dialog title bar."""
    return len(ONBOARDING_STEPS)
